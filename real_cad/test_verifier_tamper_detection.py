#!/usr/bin/env python3
"""Negative tests: representative result and input tampering must be rejected."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Callable

import verify_real_cad_results as verifier


HERE = Path(__file__).resolve().parent


def expect_rejected(label: str, action: Callable[[], None]) -> None:
    try:
        action()
    except verifier.VerificationError as error:
        print(f"REJECTED {label}: {error}")
        return
    raise RuntimeError(f"tamper probe was incorrectly accepted: {label}")


def main() -> int:
    preflight_dir = HERE / "results/occt_preflight_v1"
    freecad_dir = HERE / "results/freecad_preflight_v3"
    crosscheck_dir = HERE / "results/brep_crosscheck_v1"
    dc_dir = HERE / "results/dual_contouring_v3"

    preflight = verifier.load(preflight_dir / "occt_preflight_aggregate.json")
    freecad = verifier.load(freecad_dir / "freecad_preflight_aggregate.json")
    crosscheck = verifier.load(crosscheck_dir / "brep_crosscheck_aggregate.json")
    dc = verifier.load(dc_dir / "dual_contouring_aggregate.json")
    rescue = verifier.load(dc_dir / "resolution_rescue_diagnostic.json")

    # Establish that the unmodified row sets satisfy their independent checks.
    occt_records = verifier.verify_occt(preflight_dir, preflight)
    freecad_records = verifier.verify_freecad(freecad_dir, freecad)
    verifier.verify_crosscheck(crosscheck, occt_records, freecad_records)
    dc_ids = verifier.verify_dc(dc_dir, occt_records, dc, rescue)

    changed_freecad_summary = copy.deepcopy(freecad)
    changed_freecad_summary["shape_valid"] -= 1
    expect_rejected(
        "FreeCAD summary count",
        lambda: verifier.verify_freecad(freecad_dir, changed_freecad_summary),
    )

    changed_crosscheck_row = copy.deepcopy(crosscheck)
    changed_crosscheck_row["rows"][0]["comparison_pass"] = False
    expect_rejected(
        "crosscheck row",
        lambda: verifier.verify_crosscheck(changed_crosscheck_row, occt_records, freecad_records),
    )

    changed_dc_metric = copy.deepcopy(dc)
    changed_dc_metric["distributions"]["model_coverage_median"] += 0.01
    expect_rejected(
        "continuous DC metric",
        lambda: verifier.verify_dc(dc_dir, occt_records, changed_dc_metric, rescue),
    )

    anchors = verifier.build_external_input_anchors(HERE)
    changed_input_row = copy.deepcopy(preflight["records"][0])
    changed_input_row["expected_sha256"] = "0" * 64
    expect_rejected(
        "external input hash",
        lambda: verifier.verify_input_anchors(
            [changed_input_row], anchors, "tampered input",
            expected_ids={changed_input_row["corpus_id"]},
        ),
    )

    changed_rescue = copy.deepcopy(rescue)
    first_success = next(
        attempt for attempt in changed_rescue["models"][0]["attempts"]
        if attempt["tool_ok"]
    )
    first_success["resolution"] = 64
    expect_rejected(
        "resolution-rescue first success",
        lambda: verifier.verify_dc(dc_dir, occt_records, dc, changed_rescue),
    )

    require_ids = {row["corpus_id"] for row in dc["records"]}
    if dc_ids != require_ids:
        raise RuntimeError("baseline DC ID set changed during tamper test")
    print("PASS: 5/5 representative tamper probes were rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
