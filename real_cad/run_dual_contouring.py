#!/usr/bin/env python3
"""Run real-CAD STEP -> OCCT mesh -> SDF -> Dual Contouring in isolation."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
PREFLIGHT_AGGREGATE = HERE / "results/occt_preflight_v1/occt_preflight_aggregate.json"
PREFLIGHT_BINARY = HERE / "occt_preflight/build/occt_step_preflight"
DC_BINARY = HERE / "dual_contouring/build/regular_grid_dc"
DEFAULT_OUTPUT = HERE / "results/dual_contouring_v1"
REPRESENTATIVES = {"N01", "C02", "G03", "F001"}


def choose_models(records: list[dict[str, Any]], fusion_count: int) -> list[dict[str, Any]]:
    admitted = [row for row in records if row.get("rejection_reason") == "admitted"]
    manual = sorted((row for row in admitted if row["source_group"] != "Fusion360Gallery"),
                    key=lambda row: row["corpus_id"])
    fusion = sorted((row for row in admitted if row["source_group"] == "Fusion360Gallery"),
                    key=lambda row: int(row["corpus_id"][1:]))[:fusion_count]
    return manual + fusion


def run_model(record: dict[str, Any], preflight: Path, dc: Path, output: Path,
              timeout: float, manual_resolution: int, fusion_resolution: int,
              lambda_value: float, tau_cell: float) -> dict[str, Any]:
    corpus_id = record["corpus_id"]
    group = record["source_group"]
    resolution = fusion_resolution if group == "Fusion360Gallery" else manual_resolution
    started = time.monotonic()
    base = {
        "corpus_id": corpus_id,
        "source_group": group,
        "model_name": record.get("model_name"),
        "input_path": record["input_path"],
        "expected_sha256": record.get("expected_sha256"),
        "resolution": resolution,
    }
    individual = output / "individual" / f"{corpus_id}.json"
    with tempfile.TemporaryDirectory(prefix=f"topic4_dc_{corpus_id}_") as temporary:
        temporary = Path(temporary)
        mesh_path = temporary / "solid_subset.obj"
        export_json = temporary / "export.json"
        export_command = [
            str(preflight), "--input", record["input_path"], "--output", str(export_json),
            "--mesh-output", str(mesh_path), "--id", corpus_id, "--group", group,
            "--relative-deflection", "0.001", "--angular-deflection", "0.35",
        ]
        try:
            exported = subprocess.run(export_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            return {**base, "runner_status": "export_timeout", "tool_ok": False,
                    "failure_stage": "export_timeout", "elapsed_seconds": time.monotonic()-started}
        if exported.returncode != 0 or not mesh_path.is_file():
            return {**base, "runner_status": "export_failure", "tool_ok": False,
                    "failure_stage": "export_failure", "exit_code": exported.returncode,
                    "stderr_tail": exported.stderr[-2000:], "elapsed_seconds": time.monotonic()-started}

        dc_json = temporary / "dc.json"
        command = [
            str(dc), "--input", str(mesh_path), "--output", str(dc_json), "--id", corpus_id,
            "--resolution", str(resolution), "--padding", "2", "--lambda", str(lambda_value),
            "--tau-cell", str(tau_cell),
        ]
        if corpus_id in REPRESENTATIVES:
            command.extend([
                "--baseline-obj", str(output / "representative_meshes" / f"{corpus_id}_baseline.obj"),
                "--fallback-obj", str(output / "representative_meshes" / f"{corpus_id}_contract_fallback.obj"),
            ])
        try:
            completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            return {**base, "runner_status": "dc_timeout", "tool_ok": False,
                    "failure_stage": "dc_timeout", "elapsed_seconds": time.monotonic()-started}
        if not dc_json.is_file():
            return {**base, "runner_status": "dc_no_json", "tool_ok": False,
                    "failure_stage": "dc_no_json", "exit_code": completed.returncode,
                    "stderr_tail": completed.stderr[-2000:], "elapsed_seconds": time.monotonic()-started}
        try:
            result = json.loads(dc_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            return {**base, "runner_status": "dc_invalid_json", "tool_ok": False,
                    "failure_stage": "dc_invalid_json", "json_error": str(error),
                    "exit_code": completed.returncode, "elapsed_seconds": time.monotonic()-started}
        result.update(base)
        if completed.returncode == 0 and result.get("tool_ok"):
            result["runner_status"] = "completed"
        elif result.get("failure_message") == "no Hermite roots generated":
            result["runner_status"] = "no_zero_crossing_at_resolution"
            result["failure_stage"] = "grid_sampling"
        else:
            result["runner_status"] = "dc_failure"
        result["exit_code"] = completed.returncode
        result["stdout_tail"] = completed.stdout[-2000:]
        result["stderr_tail"] = completed.stderr[-2000:]
        result["pipeline_elapsed_seconds"] = time.monotonic() - started
        individual.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result


def scalar(record: dict[str, Any]) -> dict[str, Any]:
    qef = record.get("qef", {})
    baseline = record.get("baseline_mesh", {})
    fallback = record.get("contract_fallback_mesh", {})
    return {
        "corpus_id": record.get("corpus_id"),
        "source_group": record.get("source_group"),
        "model_name": record.get("model_name"),
        "runner_status": record.get("runner_status"),
        "tool_ok": record.get("tool_ok", False),
        "resolution": record.get("resolution"),
        "active_cells": qef.get("active_cells"),
        "oracle_diagnostic_certified": qef.get("certified_oracle_diagnostic"),
        "oracle_diagnostic_coverage": qef.get("coverage"),
        "bound_violations": qef.get("bound_violations"),
        "outside_cell_vertices": qef.get("outside_cell_vertices"),
        "median_normal_angle_error_degrees": qef.get("median_normal_angle_error_degrees"),
        "p95_normal_angle_error_degrees": qef.get("p95_normal_angle_error_degrees"),
        "median_root_position_error_cell_units": qef.get("median_root_position_error_cell_units"),
        "p95_root_position_error_cell_units": qef.get("p95_root_position_error_cell_units"),
        "median_bound_cell_units": qef.get("median_bound_cell_units"),
        "p95_bound_cell_units": qef.get("p95_bound_cell_units"),
        "median_measured_displacement_cell_units": qef.get("median_measured_displacement_cell_units"),
        "p95_measured_displacement_cell_units": qef.get("p95_measured_displacement_cell_units"),
        "baseline_vertices": baseline.get("vertices"),
        "baseline_triangles": baseline.get("triangles"),
        "baseline_boundary_edges": baseline.get("boundary_edges"),
        "baseline_nonmanifold_edges": baseline.get("nonmanifold_edges"),
        "baseline_mean_surface_error_cell_units": baseline.get("mean_abs_surface_distance_cell_units"),
        "baseline_max_surface_error_cell_units": baseline.get("max_abs_surface_distance_cell_units"),
        "fallback_mean_surface_error_cell_units": fallback.get("mean_abs_surface_distance_cell_units"),
        "fallback_max_surface_error_cell_units": fallback.get("max_abs_surface_distance_cell_units"),
        "pipeline_elapsed_seconds": record.get("pipeline_elapsed_seconds"),
        "input_path": record.get("input_path"),
    }


def finite_values(records: list[dict[str, Any]], path: tuple[str, ...]) -> list[float]:
    values = []
    for record in records:
        value: Any = record
        for key in path:
            value = value.get(key) if isinstance(value, dict) else None
        if isinstance(value, (int, float)):
            values.append(float(value))
    return values


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    position = q * (len(values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    t = position - lower
    return (1.0 - t) * values[lower] + t * values[upper]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", type=Path, default=PREFLIGHT_BINARY)
    parser.add_argument("--dc", type=Path, default=DC_BINARY)
    parser.add_argument("--preflight-aggregate", type=Path, default=PREFLIGHT_AGGREGATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--manual-resolution", type=int, default=32)
    parser.add_argument("--fusion-resolution", type=int, default=24)
    parser.add_argument("--fusion-count", type=int, default=100)
    parser.add_argument("--lambda", dest="lambda_value", type=float, default=0.1)
    parser.add_argument("--tau-cell", type=float, default=0.10)
    args = parser.parse_args()
    preflight_data = json.loads(args.preflight_aggregate.read_text(encoding="utf-8"))
    models = choose_models(preflight_data["records"], args.fusion_count)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "individual").mkdir(exist_ok=True)
    (args.output / "representative_meshes").mkdir(exist_ok=True)
    started = time.monotonic()
    records: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(run_model, model, args.preflight, args.dc, args.output, args.timeout,
                            args.manual_resolution, args.fusion_resolution, args.lambda_value,
                            args.tau_cell): model
            for model in models
        }
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            model = futures[future]
            try:
                result = future.result()
            except Exception as error:
                result = {"corpus_id": model["corpus_id"], "source_group": model["source_group"],
                          "model_name": model.get("model_name"), "tool_ok": False,
                          "runner_status": "runner_exception", "failure_message": repr(error)}
            records.append(result)
            final_individual = args.output / "individual" / f"{model['corpus_id']}.json"
            if not final_individual.is_file():
                final_individual.write_text(
                    json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
                )
            qef = result.get("qef", {})
            print(f"[{index:03d}/{len(models):03d}] {model['corpus_id']}: {result['runner_status']} "
                  f"cells={qef.get('active_cells','-')} coverage={qef.get('coverage','-')}", flush=True)
    records.sort(key=lambda row: (row["source_group"] == "Fusion360Gallery", row["corpus_id"]))
    completed = [row for row in records if row.get("tool_ok")]
    group_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in records:
        group_counts[row["source_group"]][row.get("runner_status", "unknown")] += 1
        group_counts[row["source_group"]]["total"] += 1
    aggregate = {
        "schema": "topic4.regular_grid_dc.aggregate.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "command": " ".join(sys.argv),
        "host": {"platform": platform.platform(), "machine": platform.machine(), "python": sys.version},
        "protocol": {
            "selection": "all 22 admitted manual models plus the first 100 admitted Fusion sample rows by frozen sample_index",
            "source_preflight": str(args.preflight_aggregate),
            "manual_resolution": args.manual_resolution,
            "fusion_resolution": args.fusion_resolution,
            "lambda": args.lambda_value,
            "tau_cell_units": args.tau_cell,
            "one_subprocess_per_stage_per_model": True,
            "timeout_seconds_per_stage": args.timeout,
            "unknown_fallback": "cell center, explicitly uncertified",
            "contract_interpretation": "oracle diagnostic only; no deployable upstream field certificate is claimed",
        },
        "selected_models": len(records),
        "completed_models": len(completed),
        "failed_models": len(records) - len(completed),
        "group_counts": {group: dict(counts) for group, counts in sorted(group_counts.items())},
        "totals": {
            "active_cells": sum(row.get("qef", {}).get("active_cells", 0) for row in completed),
            "oracle_diagnostic_certified": sum(row.get("qef", {}).get("certified_oracle_diagnostic", 0) for row in completed),
            "bound_violations": sum(row.get("qef", {}).get("bound_violations", 0) for row in completed),
            "baseline_boundary_edges": sum(row.get("baseline_mesh", {}).get("boundary_edges", 0) for row in completed),
            "baseline_nonmanifold_edges": sum(row.get("baseline_mesh", {}).get("nonmanifold_edges", 0) for row in completed),
        },
        "distributions": {
            "model_coverage_median": quantile(finite_values(completed, ("qef", "coverage")), 0.5),
            "model_coverage_p05": quantile(finite_values(completed, ("qef", "coverage")), 0.05),
            "model_coverage_p95": quantile(finite_values(completed, ("qef", "coverage")), 0.95),
            "baseline_mean_surface_error_cell_units_median": quantile(finite_values(completed, ("baseline_mesh", "mean_abs_surface_distance_cell_units")), 0.5),
            "baseline_max_surface_error_cell_units_p95": quantile(finite_values(completed, ("baseline_mesh", "max_abs_surface_distance_cell_units")), 0.95),
            "model_median_normal_angle_error_degrees_median": quantile(finite_values(completed, ("qef", "median_normal_angle_error_degrees")), 0.5),
            "model_p95_normal_angle_error_degrees_p95": quantile(finite_values(completed, ("qef", "p95_normal_angle_error_degrees")), 0.95),
        },
        "elapsed_seconds": time.monotonic() - started,
        "records": records,
    }
    active = aggregate["totals"]["active_cells"]
    aggregate["totals"]["pooled_oracle_diagnostic_coverage"] = (
        aggregate["totals"]["oracle_diagnostic_certified"] / active if active else 0.0
    )
    (args.output / "dual_contouring_aggregate.json").write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    rows = [scalar(row) for row in records]
    with (args.output / "dual_contouring_rows.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({key: aggregate[key] for key in ("selected_models", "completed_models", "failed_models", "totals", "distributions")}, indent=2))
    return 0 if len(completed) == len(records) else 2


if __name__ == "__main__":
    raise SystemExit(main())
