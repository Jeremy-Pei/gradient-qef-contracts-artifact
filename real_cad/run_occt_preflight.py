#!/usr/bin/env python3
"""Run the no-healing OpenCascade STEP preflight in isolated processes."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]
MODEL_ROOT = Path(os.environ.get(
    "GRADIENT_QEF_CAD_ROOT", str(HERE / "inputs")
)).expanduser().resolve()
FUSION_ROOT = MODEL_ROOT / "Fusion360Gallery/s2.0.1_extended_step/sample_500"
DEFAULT_BINARY = HERE / "occt_preflight/build/occt_step_preflight"
DEFAULT_OUTPUT = HERE / "results/occt_preflight_v1"


@dataclass(frozen=True)
class Model:
    corpus_id: str
    source_group: str
    model_name: str
    path: Path
    expected_sha256: str
    official_split: str = ""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def manual_models() -> list[Model]:
    selection = {
        row["corpus_id"]: row
        for row in read_csv(HERE / "selected_model_manifest_v1.csv")
        if row["corpus_id"] not in {"N11", "F500"}
    }
    models: dict[str, Model] = {}

    nist_receipts = read_csv(HERE / "corpus_v1/manifests/download_receipts.csv")
    for row in nist_receipts:
        corpus_id = row["corpus_id"]
        path = HERE / row["stored_step_path"]
        models[corpus_id] = Model(
            corpus_id=corpus_id,
            source_group="NIST",
            model_name=selection[corpus_id]["model_name"],
            path=path,
            expected_sha256=row["file_sha256"],
        )

    receipt_specs = [
        (HERE / "traceparts_receipt_2026-08-10.csv", "TraceParts"),
        (HERE / "3dfindit_receipt_2026-08-10.csv", "3Dfindit"),
        (HERE / "3dcontentcentral_receipt_2026-08-10.csv", "3D ContentCentral"),
        (HERE / "grabcad_receipt_2026-08-10.csv", "GrabCAD"),
    ]
    external_files: dict[str, Path] = {}
    for path in MODEL_ROOT.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".stp", ".step"} and FUSION_ROOT not in path.parents:
            match = re.match(r"([TDCG]\d{2})_", path.name)
            if match:
                external_files[match.group(1)] = path

    for receipt_path, group in receipt_specs:
        for row in read_csv(receipt_path):
            corpus_id = row["corpus_id"]
            models[corpus_id] = Model(
                corpus_id=corpus_id,
                source_group=group,
                model_name=selection[corpus_id]["model_name"],
                path=external_files[corpus_id],
                expected_sha256=row["step_sha256"],
            )

    expected_ids = set(selection)
    if set(models) != expected_ids:
        raise RuntimeError(
            f"manual inventory mismatch; missing={sorted(expected_ids-set(models))}, "
            f"unexpected={sorted(set(models)-expected_ids)}"
        )
    return [models[key] for key in sorted(models)]


def fusion_models() -> list[Model]:
    rows = read_csv(HERE / "fusion360_sample500_manifest_2026-08-10.csv")
    if len(rows) != 500:
        raise RuntimeError(f"expected 500 Fusion rows, found {len(rows)}")
    return [
        Model(
            corpus_id=f"F{int(row['sample_index']):03d}",
            source_group="Fusion360Gallery",
            model_name=row["model_id"],
            path=FUSION_ROOT / row["step_file"],
            expected_sha256=row["step_sha256"],
            official_split=row["official_split"],
        )
        for row in rows
    ]


def rejection_reason(record: dict[str, Any]) -> str:
    if not record.get("tool_ok"):
        return str(record.get("failure_stage", "tool_failure"))
    validity = record["validity"]
    closure = record["brep_closure"]
    volume = record["brep_volume"]
    mesh = record["mesh"]
    if not validity.get("solid_subset_valid", False) or validity["invalid_solids"] or validity["invalid_shells"] or validity["invalid_faces"]:
        return "invalid_brep"
    if not closure["all_shells_closed"]:
        return "open_brep_shell"
    if not volume["all_solids_positive"]:
        return "nonpositive_brep_volume"
    if not mesh["meshing_done"] or not mesh["triangles"]:
        return "triangulation_failure"
    if not mesh["watertight"]:
        return "mesh_boundary"
    if not mesh["edge_manifold"]:
        return "mesh_nonmanifold"
    if not mesh["positive_signed_volume"]:
        return "nonpositive_mesh_volume"
    return "admitted"


def run_one(model: Model, binary: Path, individual_dir: Path, timeout: float) -> dict[str, Any]:
    started = time.monotonic()
    base = {
        "corpus_id": model.corpus_id,
        "source_group": model.source_group,
        "model_name": model.model_name,
        "input_path": str(model.path),
        "official_split": model.official_split,
        "expected_sha256": model.expected_sha256,
    }
    if not model.path.is_file():
        return {**base, "runner_status": "missing_file", "tool_ok": False,
                "failure_stage": "missing_file", "elapsed_seconds": time.monotonic() - started,
                "rejection_reason": "missing_file"}
    observed_hash = sha256_file(model.path)
    if observed_hash != model.expected_sha256:
        return {**base, "observed_sha256": observed_hash, "runner_status": "hash_mismatch",
                "tool_ok": False, "failure_stage": "hash_mismatch",
                "elapsed_seconds": time.monotonic() - started,
                "rejection_reason": "hash_mismatch"}

    final_json = individual_dir / f"{model.corpus_id}.json"
    with tempfile.TemporaryDirectory(prefix=f"topic4_{model.corpus_id}_") as temporary:
        temporary_json = Path(temporary) / "result.json"
        command = [
            str(binary), "--input", str(model.path), "--output", str(temporary_json),
            "--id", model.corpus_id, "--group", model.source_group,
            "--relative-deflection", "0.001", "--angular-deflection", "0.35",
        ]
        try:
            completed = subprocess.run(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired as error:
            return {**base, "observed_sha256": observed_hash, "runner_status": "timeout",
                    "tool_ok": False, "failure_stage": "timeout", "timeout_seconds": timeout,
                    "stdout_tail": (error.stdout or "")[-2000:] if isinstance(error.stdout, str) else "",
                    "stderr_tail": (error.stderr or "")[-2000:] if isinstance(error.stderr, str) else "",
                    "elapsed_seconds": time.monotonic() - started,
                    "rejection_reason": "timeout"}
        if not temporary_json.is_file():
            return {**base, "observed_sha256": observed_hash,
                    "runner_status": "no_json", "tool_ok": False,
                    "failure_stage": "no_json", "exit_code": completed.returncode,
                    "stdout_tail": completed.stdout[-2000:], "stderr_tail": completed.stderr[-2000:],
                    "elapsed_seconds": time.monotonic() - started,
                    "rejection_reason": "no_json"}
        try:
            record = json.loads(temporary_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            return {**base, "observed_sha256": observed_hash,
                    "runner_status": "invalid_json", "tool_ok": False,
                    "failure_stage": "invalid_json", "exit_code": completed.returncode,
                    "json_error": str(error), "stdout_tail": completed.stdout[-2000:],
                    "stderr_tail": completed.stderr[-2000:],
                    "elapsed_seconds": time.monotonic() - started,
                    "rejection_reason": "invalid_json"}
        record.update({
            "model_name": model.model_name,
            "official_split": model.official_split,
            "expected_sha256": model.expected_sha256,
            "observed_sha256": observed_hash,
            "runner_status": "completed" if completed.returncode == 0 else "tool_nonzero",
            "exit_code": completed.returncode,
            "stdout_tail": completed.stdout[-2000:],
            "stderr_tail": completed.stderr[-2000:],
        })
        record["rejection_reason"] = rejection_reason(record)
        final_json.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return record


def scalar_row(record: dict[str, Any]) -> dict[str, Any]:
    topology = record.get("topology", {})
    validity = record.get("validity", {})
    closure = record.get("brep_closure", {})
    volume = record.get("brep_volume", {})
    mesh = record.get("mesh", {})
    admission = record.get("admission", {})
    return {
        "corpus_id": record.get("corpus_id"),
        "source_group": record.get("source_group"),
        "model_name": record.get("model_name"),
        "official_split": record.get("official_split", ""),
        "runner_status": record.get("runner_status"),
        "exit_code": record.get("exit_code"),
        "tool_ok": record.get("tool_ok", False),
        "shape_valid": validity.get("shape_valid"),
        "solid_subset_valid": validity.get("solid_subset_valid"),
        "solids": topology.get("solids"),
        "shells": topology.get("shells"),
        "faces": topology.get("faces"),
        "open_shells": closure.get("open_shells"),
        "all_shells_closed": closure.get("all_shells_closed"),
        "positive_solids": volume.get("positive_solids"),
        "nonpositive_solids": volume.get("nonpositive_solids"),
        "all_solids_positive": volume.get("all_solids_positive"),
        "brep_signed_volume": volume.get("total_signed"),
        "mesh_vertices": mesh.get("welded_vertices"),
        "mesh_triangles": mesh.get("triangles"),
        "mesh_boundary_edges": mesh.get("boundary_edges"),
        "mesh_nonmanifold_edges": mesh.get("nonmanifold_edges"),
        "mesh_components": mesh.get("connected_components"),
        "mesh_watertight": mesh.get("watertight"),
        "mesh_positive_signed_volume": mesh.get("positive_signed_volume"),
        "dual_contouring_candidate": admission.get("dual_contouring_candidate", False),
        "rejection_reason": record.get("rejection_reason"),
        "elapsed_seconds": record.get("elapsed_seconds"),
        "expected_sha256": record.get("expected_sha256"),
        "observed_sha256": record.get("observed_sha256"),
        "input_path": record.get("input_path"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--groups", nargs="*", default=[])
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    models = manual_models() + fusion_models()
    if args.groups:
        allowed = set(args.groups)
        models = [model for model in models if model.source_group in allowed]
    if args.limit is not None:
        models = models[: args.limit]
    if not args.binary.is_file():
        raise SystemExit(f"preflight binary not found: {args.binary}")

    args.output.mkdir(parents=True, exist_ok=True)
    individual_dir = args.output / "individual"
    individual_dir.mkdir(exist_ok=True)
    started = time.monotonic()
    records: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(run_one, model, args.binary, individual_dir, args.timeout): model
            for model in models
        }
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            model = futures[future]
            try:
                record = future.result()
            except Exception as error:  # preserve harness errors in denominator
                record = {
                    **asdict(model), "path": str(model.path), "runner_status": "runner_exception",
                    "tool_ok": False, "failure_stage": "runner_exception",
                    "failure_message": repr(error), "rejection_reason": "runner_exception",
                }
            records.append(record)
            print(f"[{index:03d}/{len(models):03d}] {model.corpus_id}: {record.get('rejection_reason')}", flush=True)

    records.sort(key=lambda row: row["corpus_id"])
    reason_counts = Counter(row.get("rejection_reason", "unknown") for row in records)
    group_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in records:
        group_counts[row["source_group"]][row.get("rejection_reason", "unknown")] += 1
        group_counts[row["source_group"]]["total"] += 1
    aggregate = {
        "schema": "topic4.occt_step_preflight.aggregate.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "command": " ".join(sys.argv),
        "host": {"platform": platform.platform(), "machine": platform.machine(), "python": sys.version},
        "protocol": {
            "kernel": "OpenCascade 7.9.3",
            "model_isolation": "one subprocess per STEP file",
            "timeout_seconds": args.timeout,
            "workers": args.workers,
            "healing_or_sewing": False,
            "relative_linear_deflection": 0.001,
            "angular_deflection_radians": 0.35,
            "all_failures_retained_in_denominator": True,
        },
        "total": len(records),
        "admitted": reason_counts.get("admitted", 0),
        "reason_counts": dict(sorted(reason_counts.items())),
        "group_counts": {group: dict(sorted(counts.items())) for group, counts in sorted(group_counts.items())},
        "elapsed_seconds": time.monotonic() - started,
        "records": records,
    }
    (args.output / "occt_preflight_aggregate.json").write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    rows = [scalar_row(row) for row in records]
    with (args.output / "occt_preflight_rows.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"total": len(records), "admitted": aggregate["admitted"],
                      "reason_counts": aggregate["reason_counts"]}, indent=2))
    return 0 if len(records) == len(models) else 2


if __name__ == "__main__":
    raise SystemExit(main())
