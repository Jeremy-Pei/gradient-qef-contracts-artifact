#!/usr/bin/env python3
"""Diagnostic-only resolution ladder for coarse-grid zero-crossing misses."""

from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
PREFLIGHT = HERE / "occt_preflight/build/occt_step_preflight"
DC = HERE / "dual_contouring/build/regular_grid_dc"
PREFLIGHT_RESULTS = HERE / "results/occt_preflight_v1/occt_preflight_aggregate.json"
MAIN_DC_RESULTS = HERE / "results/dual_contouring_v3/dual_contouring_aggregate.json"
OUTPUT = HERE / "results/dual_contouring_v3/resolution_rescue_diagnostic.json"


def main() -> int:
    preflight = json.loads(PREFLIGHT_RESULTS.read_text(encoding="utf-8"))
    main_dc = json.loads(MAIN_DC_RESULTS.read_text(encoding="utf-8"))
    misses = [row for row in main_dc["records"]
              if row.get("runner_status") == "no_zero_crossing_at_resolution"]
    rows = []
    for miss in misses:
        source = next(row for row in preflight["records"] if row["corpus_id"] == miss["corpus_id"])
        with tempfile.TemporaryDirectory(prefix=f"topic4_rescue_{miss['corpus_id']}_") as directory:
            directory = Path(directory)
            mesh = directory / "source.obj"
            export_json = directory / "export.json"
            exported = subprocess.run([
                str(PREFLIGHT), "--input", source["input_path"], "--output", str(export_json),
                "--mesh-output", str(mesh), "--id", miss["corpus_id"], "--group", miss["source_group"],
            ], capture_output=True, text=True, timeout=180, check=False)
            attempts = []
            if exported.returncode == 0:
                for resolution in (32, 48, 64, 96):
                    output = directory / f"dc_{resolution}.json"
                    completed = subprocess.run([
                        str(DC), "--input", str(mesh), "--output", str(output), "--id", miss["corpus_id"],
                        "--resolution", str(resolution), "--padding", "2", "--lambda", "0.1",
                        "--tau-cell", "0.1",
                    ], capture_output=True, text=True, timeout=180, check=False)
                    result = json.loads(output.read_text(encoding="utf-8"))
                    attempts.append({
                        "resolution": resolution,
                        "exit_code": completed.returncode,
                        "tool_ok": result.get("tool_ok", False),
                        "active_cells": result.get("qef", {}).get("active_cells", 0),
                        "oracle_diagnostic_coverage": result.get("qef", {}).get("coverage"),
                        "failure_message": result.get("failure_message"),
                    })
                    if result.get("tool_ok"):
                        break
            rows.append({
                "corpus_id": miss["corpus_id"],
                "source_group": miss["source_group"],
                "main_resolution": miss["resolution"],
                "main_failure": miss.get("failure_message"),
                "attempts": attempts,
            })
    document = {
        "schema": "topic4.regular_grid_dc.resolution_rescue.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "role": "diagnostic only; results do not replace failures in the frozen main protocol",
        "models": rows,
    }
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(document, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
