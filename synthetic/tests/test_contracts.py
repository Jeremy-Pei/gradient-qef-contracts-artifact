#!/usr/bin/env python3
"""Regression checks for the frozen topic-4 experiment record."""

from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results" / "topic4_results.json"


def main() -> None:
    if not RESULT.exists():
        raise SystemExit(f"missing {RESULT}; run scripts/generate_results.py first")
    data = json.loads(RESULT.read_text(encoding="utf-8"))
    ex = data["experiments"]
    assert data["schema"] == "hybridcad.topic4.gradient-hermite-qef.v3"
    assert data["all_required_checks_pass"] is True
    assert ex["hard_switch"]["violations"] == 0
    assert ex["smooth_min"]["complete_violations"] == 0
    assert ex["smooth_min"]["naive_without_coupling_violations"] > 0
    assert ex["hermite_root"]["complete_violations"] == 0
    assert ex["qef"]["complete_violations"] == 0
    assert ex["qef"]["realized_budget_diagnostic_violations"] == 0
    assert ex["qef"]["matrix_oracle_diagnostic_violations"] == 0
    assert ex["qef"]["incomplete_bridge_violations"] > 0
    assert ex["qef"]["finite_bounds"] == ex["qef"]["sample_count"]
    assert ex["qef"]["sample_count"] == 40_000
    assert ex["qef"]["unregularized_data_residual"]["max"] < 1e-12
    assert math.isclose(
        ex["qef"]["tolerance_coverage"]["0.10"]
        ["measured_actual_coverage"],
        0.998475, rel_tol=0.0, abs_tol=1e-12)
    for config in ("orthogonal", "random", "edge20", "near_planar"):
        row = ex["qef"]["by_configuration"][config]
        assert row["complete_violations"] == 0
        assert row["realized_budget_diagnostic_violations"] == 0
        assert row["matrix_oracle_diagnostic_violations"] == 0
        for tolerance in ("0.01", "0.05", "0.10", "0.25"):
            coverage = row["tolerance_coverage"][tolerance]
            assert 0.0 <= coverage["declared_contract"] <= 1.0
            assert (coverage["declared_contract"]
                    <= coverage["realized_budget_diagnostic"]
                    <= coverage["matrix_oracle_diagnostic"])

    stress = ex["qef_residual_stress"]
    assert stress["sample_count"] == 20_000
    assert stress["complete_violations"] == 0
    assert stress["incomplete_bridge_violations"] > 0
    assert stress["surface_subtypes"] == {"sphere": 5_000,
                                          "paraboloid": 5_000}
    assert stress["unregularized_data_residual"]["q50"] > 1e-3
    for kind in ("inconsistent_planes", "curved_patch"):
        row = stress["by_kind"][kind]
        assert row["sample_count"] == 10_000
        assert row["complete_violations"] == 0
        assert row["unregularized_data_residual"]["q50"] > 1e-3
        for tolerance in ("0.01", "0.05", "0.10", "0.25"):
            coverage = row["tolerance_coverage"][tolerance]
            assert (0.0 <= coverage["declared_contract"]
                    <= coverage["measured_actual"] <= 1.0)
    print("topic4 contract regression checks: PASS")
    print("Reminder: these checks validate the implementation, not the universal proofs.")


if __name__ == "__main__":
    main()
