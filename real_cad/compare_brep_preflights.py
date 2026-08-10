#!/usr/bin/env python3
"""Compare OCCT 7.9.3 and FreeCAD/OCCT 7.8.1 STEP/B-rep audits."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DEFAULT_OCCT = HERE / "results/occt_preflight_v1/occt_preflight_aggregate.json"
DEFAULT_FREECAD = HERE / "results/freecad_preflight_v3/freecad_preflight_aggregate.json"
DEFAULT_OUTPUT = HERE / "results/brep_crosscheck_v1"


def load_records(path: Path) -> dict[str, dict[str, Any]]:
    aggregate = json.loads(path.read_text(encoding="utf-8"))
    records = {record["corpus_id"]: record for record in aggregate["records"]}
    if len(records) != len(aggregate["records"]):
        raise RuntimeError(f"duplicate corpus_id in {path}")
    return records


def relative_difference(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1.0e-300)


def quantile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return math.nan
    index = min(len(ordered) - 1, max(0, int(math.ceil(fraction * len(ordered))) - 1))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--occt", type=Path, default=DEFAULT_OCCT)
    parser.add_argument("--freecad", type=Path, default=DEFAULT_FREECAD)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--volume-relative-tolerance", type=float, default=1.0e-4)
    parser.add_argument("--bbox-relative-tolerance", type=float, default=1.0e-6)
    args = parser.parse_args()

    occt = load_records(args.occt)
    freecad = load_records(args.freecad)
    if set(occt) != set(freecad):
        raise RuntimeError(
            f"corpus mismatch: only_occt={sorted(set(occt)-set(freecad))}, "
            f"only_freecad={sorted(set(freecad)-set(occt))}"
        )

    rows: list[dict[str, Any]] = []
    for corpus_id in sorted(occt):
        primary = occt[corpus_id]
        check = freecad[corpus_id]
        pvalid = primary.get("validity", {})
        cvalid = check.get("validity", {})
        ptop = primary.get("topology", {})
        ctop = check.get("topology", {})
        pclose = primary.get("brep_closure", {})
        cclose = check.get("brep_closure", {})
        pvolume = primary.get("brep_volume", {})
        cvolume = check.get("brep_volume", {})
        pbbox = primary.get("bbox", {})
        cbbox = check.get("bbox", {})
        paux = primary.get("full_shape_auxiliary", {})
        caux = check.get("full_shape_auxiliary", {})

        categorical_match = all(
            [
                bool(primary.get("tool_ok")) == bool(check.get("tool_ok")),
                bool(pvalid.get("shape_valid")) == bool(cvalid.get("shape_valid")),
                bool(pvalid.get("solid_subset_valid")) == bool(cvalid.get("all_solids_valid")),
                bool(pclose.get("all_shells_closed")) == bool(cclose.get("all_shells_closed")),
                bool(pvolume.get("all_solids_positive"))
                == bool(cvolume.get("all_solids_positive")),
            ]
        )
        topology_match = all(
            ptop.get(key) == ctop.get(key) for key in ["solids", "shells", "faces"]
        )
        auxiliary_shell_match = all(
            paux.get(key) == caux.get(key)
            for key in ["shells", "closed_shells", "open_shells", "non_solid_shells"]
        )
        volume_relative_difference = relative_difference(
            float(pvolume["total_signed"]), float(cvolume["total_signed"])
        )
        bbox_relative_difference = relative_difference(
            float(pbbox["diagonal"]), float(cbbox["diagonal"])
        )
        row = {
            "corpus_id": corpus_id,
            "source_group": primary["source_group"],
            "categorical_match": categorical_match,
            "topology_match": topology_match,
            "auxiliary_shell_match": auxiliary_shell_match,
            "occt_solids": ptop.get("solids"),
            "freecad_solids": ctop.get("solids"),
            "occt_shells": ptop.get("shells"),
            "freecad_shells": ctop.get("shells"),
            "occt_faces": ptop.get("faces"),
            "freecad_faces": ctop.get("faces"),
            "occt_volume": pvolume.get("total_signed"),
            "freecad_volume": cvolume.get("total_signed"),
            "volume_relative_difference": volume_relative_difference,
            "volume_within_tolerance": volume_relative_difference
            <= args.volume_relative_tolerance,
            "occt_bbox_diagonal": pbbox.get("diagonal"),
            "freecad_bbox_diagonal": cbbox.get("diagonal"),
            "bbox_relative_difference": bbox_relative_difference,
            "bbox_within_tolerance": bbox_relative_difference <= args.bbox_relative_tolerance,
        }
        row["comparison_pass"] = all(
            [
                row["categorical_match"],
                row["topology_match"],
                row["auxiliary_shell_match"],
                row["volume_within_tolerance"],
            ]
        )
        rows.append(row)

    volume_differences = [row["volume_relative_difference"] for row in rows]
    bbox_differences = [row["bbox_relative_difference"] for row in rows]
    volume_outliers = sorted(
        [row for row in rows if row["volume_relative_difference"] > 1.0e-12],
        key=lambda row: row["volume_relative_difference"],
        reverse=True,
    )
    aggregate = {
        "schema": "topic4.brep_crosscheck.aggregate.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": {"occt": str(args.occt), "freecad": str(args.freecad)},
        "interpretation": {
            "primary": "OpenCascade 7.9.3 direct STEPControl_Reader pipeline",
            "crosscheck": "FreeCAD 1.1.1 Part.read pipeline backed by OpenCascade 7.8.1",
            "claim_boundary": "cross-version and cross-frontend consistency; not an independent CAD-kernel validation",
        },
        "tolerances": {
            "volume_relative": args.volume_relative_tolerance,
            "bbox_diagonal_relative": args.bbox_relative_tolerance,
        },
        "total": len(rows),
        "comparison_pass": sum(row["comparison_pass"] for row in rows),
        "categorical_match": sum(row["categorical_match"] for row in rows),
        "topology_match": sum(row["topology_match"] for row in rows),
        "auxiliary_shell_match": sum(row["auxiliary_shell_match"] for row in rows),
        "volume_within_tolerance": sum(row["volume_within_tolerance"] for row in rows),
        "bbox_within_diagnostic_tolerance": sum(
            row["bbox_within_tolerance"] for row in rows
        ),
        "volume_relative_difference": {
            "median": statistics.median(volume_differences),
            "p95": quantile(volume_differences, 0.95),
            "p99": quantile(volume_differences, 0.99),
            "maximum": max(volume_differences),
            "maximum_corpus_id": max(
                rows, key=lambda row: row["volume_relative_difference"]
            )["corpus_id"],
            "nonzero_above_1e-12": len(volume_outliers),
        },
        "bbox_relative_difference": {
            "median": statistics.median(bbox_differences),
            "p95": quantile(bbox_differences, 0.95),
            "p99": quantile(bbox_differences, 0.99),
            "maximum": max(bbox_differences),
            "maximum_corpus_id": max(
                rows, key=lambda row: row["bbox_relative_difference"]
            )["corpus_id"],
        },
        "volume_outliers_above_1e-12": volume_outliers,
        "rows": rows,
    }

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "brep_crosscheck_aggregate.json").write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (args.output / "brep_crosscheck_rows.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    report = f"""# B-rep cross-version and cross-frontend audit

The frozen 528-model STEP corpus was imported through two isolated pipelines:
direct OpenCascade 7.9.3 and FreeCAD 1.1.1 backed by OpenCascade 7.8.1.  This is
a cross-version and cross-frontend consistency check within the OpenCascade
kernel family, not an independent second-kernel validation.

| Check | Agreement |
|---|---:|
| Import/validity/closure/positive-volume classifications | {aggregate['categorical_match']}/{aggregate['total']} |
| Solid, solid-shell, and full-shape face counts | {aggregate['topology_match']}/{aggregate['total']} |
| Auxiliary-shell inventory | {aggregate['auxiliary_shell_match']}/{aggregate['total']} |
| B-rep volume within relative tolerance {args.volume_relative_tolerance:.0e} | {aggregate['volume_within_tolerance']}/{aggregate['total']} |
| Solid-subset bbox diagonal within diagnostic relative tolerance {args.bbox_relative_tolerance:.0e} | {aggregate['bbox_within_diagnostic_tolerance']}/{aggregate['total']} |
| Complete comparison gate | {aggregate['comparison_pass']}/{aggregate['total']} |

The complete gate uses categorical, topology, auxiliary-shell, and volume
agreement.  Bounding-box agreement is retained as a diagnostic only because
the two versions/frontends use different tolerance-enlargement details.

The maximum relative B-rep-volume difference was
{aggregate['volume_relative_difference']['maximum']:.8g} for
{aggregate['volume_relative_difference']['maximum_corpus_id']}.  Only
{aggregate['volume_relative_difference']['nonzero_above_1e-12']} models exceeded
1e-12 relative difference.  The maximum relative bbox-diagonal difference was
{aggregate['bbox_relative_difference']['maximum']:.8g}.

No healing, sewing, fusion, or topology repair was applied in either pipeline.
Assimp is excluded from B-rep claims because its AP214 detection routed the
input to an IFC importer.  Derived triangle-mesh audits remain downstream mesh
checks and are not presented as CAD-kernel validation.
"""
    (args.output / "BREP_CROSSCHECK_REPORT.md").write_text(report, encoding="utf-8")
    print(report)
    return 0 if aggregate["comparison_pass"] == aggregate["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
