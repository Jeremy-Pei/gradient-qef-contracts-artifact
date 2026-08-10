#!/usr/bin/env python3
"""Run FreeCAD STEP/B-rep preflight in one subprocess per frozen model."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import os
import platform
import subprocess
import tempfile
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_occt_preflight import Model, fusion_models, manual_models, sha256_file


HERE = Path(__file__).resolve().parent
DEFAULT_FREECAD = Path("/Applications/FreeCAD.app/Contents/Resources/bin/FreeCADCmd")
DEFAULT_WORKER = HERE / "freecad_preflight/freecad_step_smoke.py"
DEFAULT_OUTPUT = HERE / "results/freecad_preflight_v3"


def write_record(path: Path, record: dict[str, Any]) -> None:
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def failed_record(model: Model, status: str, started: float, **extra: Any) -> dict[str, Any]:
    return {
        "schema": "topic4.freecad_step_preflight.v1",
        "corpus_id": model.corpus_id,
        "source_group": model.source_group,
        "model_name": model.model_name,
        "official_split": model.official_split,
        "input_path": str(model.path),
        "expected_sha256": model.expected_sha256,
        "runner_status": status,
        "tool_ok": False,
        "failure_stage": status,
        "elapsed_seconds": time.monotonic() - started,
        **extra,
    }


def run_one(
    model: Model,
    freecad: Path,
    worker: Path,
    individual_dir: Path,
    timeout: float,
) -> dict[str, Any]:
    started = time.monotonic()
    final_json = individual_dir / f"{model.corpus_id}.json"
    if not model.path.is_file():
        record = failed_record(model, "missing_file", started)
        write_record(final_json, record)
        return record

    observed_hash = sha256_file(model.path)
    if observed_hash != model.expected_sha256:
        record = failed_record(model, "hash_mismatch", started, observed_sha256=observed_hash)
        write_record(final_json, record)
        return record

    with tempfile.TemporaryDirectory(prefix=f"topic4_freecad_{model.corpus_id}_") as temporary:
        temporary_json = Path(temporary) / "result.json"
        environment = os.environ.copy()
        environment.update(
            {
                "TOPIC4_STEP_INPUT": str(model.path),
                "TOPIC4_FREECAD_OUTPUT": str(temporary_json),
                "TOPIC4_CORPUS_ID": model.corpus_id,
                "TOPIC4_SOURCE_GROUP": model.source_group,
            }
        )
        try:
            completed = subprocess.run(
                [str(freecad), str(worker)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                check=False,
                env=environment,
            )
        except subprocess.TimeoutExpired as error:
            record = failed_record(
                model,
                "timeout",
                started,
                observed_sha256=observed_hash,
                timeout_seconds=timeout,
                stdout_tail=(error.stdout or "")[-2000:] if isinstance(error.stdout, str) else "",
                stderr_tail=(error.stderr or "")[-2000:] if isinstance(error.stderr, str) else "",
            )
            write_record(final_json, record)
            return record

        if not temporary_json.is_file():
            record = failed_record(
                model,
                "no_json",
                started,
                observed_sha256=observed_hash,
                exit_code=completed.returncode,
                stdout_tail=completed.stdout[-2000:],
                stderr_tail=completed.stderr[-2000:],
            )
            write_record(final_json, record)
            return record

        try:
            record = json.loads(temporary_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            record = failed_record(
                model,
                "invalid_json",
                started,
                observed_sha256=observed_hash,
                exit_code=completed.returncode,
                json_error=str(error),
                stdout_tail=completed.stdout[-2000:],
                stderr_tail=completed.stderr[-2000:],
            )
            write_record(final_json, record)
            return record

        record.update(
            {
                "model_name": model.model_name,
                "official_split": model.official_split,
                "expected_sha256": model.expected_sha256,
                "observed_sha256": observed_hash,
                "runner_status": "completed" if record.get("tool_ok") else "tool_failure",
                "exit_code": completed.returncode,
                "stdout_tail": completed.stdout[-2000:],
                "stderr_tail": completed.stderr[-2000:],
                "elapsed_seconds": time.monotonic() - started,
            }
        )
        write_record(final_json, record)
        return record


def scalar_row(record: dict[str, Any]) -> dict[str, Any]:
    validity = record.get("validity", {})
    topology = record.get("topology", {})
    closure = record.get("brep_closure", {})
    volume = record.get("brep_volume", {})
    kernel = record.get("kernel", {})
    bbox = record.get("bbox", {})
    return {
        "corpus_id": record.get("corpus_id"),
        "source_group": record.get("source_group"),
        "model_name": record.get("model_name"),
        "official_split": record.get("official_split", ""),
        "runner_status": record.get("runner_status"),
        "exit_code": record.get("exit_code"),
        "tool_ok": record.get("tool_ok", False),
        "freecad_version": kernel.get("frontend_version"),
        "opencascade_version": kernel.get("version"),
        "shape_valid": validity.get("shape_valid"),
        "all_solids_valid": validity.get("all_solids_valid"),
        "solids": topology.get("solids"),
        "shells": topology.get("shells"),
        "faces": topology.get("faces"),
        "open_shells": closure.get("open_shells"),
        "all_shells_closed": closure.get("all_shells_closed"),
        "all_solids_closed": closure.get("all_solids_closed"),
        "positive_solids": volume.get("positive_solids"),
        "nonpositive_solids": volume.get("nonpositive_solids"),
        "all_solids_positive": volume.get("all_solids_positive"),
        "brep_signed_volume": volume.get("total_signed"),
        "bbox_diagonal": bbox.get("diagonal"),
        "failure_stage": record.get("failure_stage", ""),
        "elapsed_seconds": record.get("elapsed_seconds"),
        "expected_sha256": record.get("expected_sha256"),
        "observed_sha256": record.get("observed_sha256"),
        "input_path": record.get("input_path"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freecad", type=Path, default=DEFAULT_FREECAD)
    parser.add_argument("--worker", type=Path, default=DEFAULT_WORKER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--groups", nargs="*", default=[])
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    if not args.freecad.is_file():
        raise SystemExit(f"FreeCADCmd not found: {args.freecad}")
    if not args.worker.is_file():
        raise SystemExit(f"FreeCAD worker not found: {args.worker}")

    models = manual_models() + fusion_models()
    if args.groups:
        allowed = set(args.groups)
        models = [model for model in models if model.source_group in allowed]
    if args.limit is not None:
        models = models[: args.limit]

    args.output.mkdir(parents=True, exist_ok=True)
    individual_dir = args.output / "individual"
    individual_dir.mkdir(exist_ok=True)
    started = time.monotonic()
    records: list[dict[str, Any]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                run_one, model, args.freecad, args.worker, individual_dir, args.timeout
            ): model
            for model in models
        }
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            model = futures[future]
            try:
                record = future.result()
            except Exception as error:
                record = failed_record(model, "runner_exception", started, error=repr(error))
                write_record(individual_dir / f"{model.corpus_id}.json", record)
            records.append(record)
            if index % 25 == 0 or index == len(models):
                print(f"completed {index}/{len(models)}", flush=True)

    records.sort(key=lambda item: item["corpus_id"])
    rows = [scalar_row(record) for record in records]
    csv_path = args.output / "freecad_preflight_rows.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    group_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        counter = group_counts[record["source_group"]]
        counter["total"] += 1
        counter["tool_ok"] += int(bool(record.get("tool_ok")))
        counter["shape_valid"] += int(bool(record.get("validity", {}).get("shape_valid")))
        counter["all_shells_closed"] += int(
            bool(record.get("brep_closure", {}).get("all_shells_closed"))
        )
        counter["all_solids_positive"] += int(
            bool(record.get("brep_volume", {}).get("all_solids_positive"))
        )

    versions = Counter(
        (
            record.get("kernel", {}).get("frontend_version", "unknown"),
            record.get("kernel", {}).get("version", "unknown"),
        )
        for record in records
        if record.get("tool_ok")
    )
    aggregate = {
        "schema": "topic4.freecad_step_preflight.aggregate.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "command": " ".join(os.sys.argv),
        "elapsed_seconds": time.monotonic() - started,
        "host": {
            "machine": platform.machine(),
            "platform": platform.platform(),
            "python": os.sys.version,
        },
        "protocol": {
            "model_isolation": "one FreeCADCmd subprocess per STEP file",
            "timeout_seconds": args.timeout,
            "workers": args.workers,
            "healing_or_sewing": False,
            "same_kernel_family_as_primary": True,
            "interpretation": "cross-version and cross-frontend consistency check, not an independent CAD kernel",
        },
        "total": len(records),
        "tool_ok": sum(bool(record.get("tool_ok")) for record in records),
        "shape_valid": sum(
            bool(record.get("validity", {}).get("shape_valid")) for record in records
        ),
        "all_solids_valid": sum(
            bool(record.get("validity", {}).get("all_solids_valid")) for record in records
        ),
        "all_shells_closed": sum(
            bool(record.get("brep_closure", {}).get("all_shells_closed")) for record in records
        ),
        "all_solids_closed": sum(
            bool(record.get("brep_closure", {}).get("all_solids_closed")) for record in records
        ),
        "all_solids_positive": sum(
            bool(record.get("brep_volume", {}).get("all_solids_positive")) for record in records
        ),
        "failure_stages": dict(
            Counter(record.get("failure_stage", "") or "none" for record in records)
        ),
        "version_counts": [
            {"freecad": key[0], "opencascade": key[1], "count": count}
            for key, count in sorted(versions.items())
        ],
        "group_counts": {
            group: dict(counter) for group, counter in sorted(group_counts.items())
        },
        "records": records,
    }
    write_record(args.output / "freecad_preflight_aggregate.json", aggregate)
    print(json.dumps({key: aggregate[key] for key in ["total", "tool_ok", "shape_valid", "all_shells_closed", "all_solids_positive", "elapsed_seconds"]}, indent=2))
    return 0 if aggregate["tool_ok"] == aggregate["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
