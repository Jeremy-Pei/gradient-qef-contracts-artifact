#!/usr/bin/env python3
"""Render human-facing artifacts from frozen JSON; run no experiments."""

from __future__ import annotations

import hashlib
import csv
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PREFLIGHT = HERE / "results/occt_preflight_v1/occt_preflight_aggregate.json"
FREECAD = HERE / "results/freecad_preflight_v3/freecad_preflight_aggregate.json"
CROSSCHECK = HERE / "results/brep_crosscheck_v1/brep_crosscheck_aggregate.json"
DC = HERE / "results/dual_contouring_v3/dual_contouring_aggregate.json"
RESCUE = HERE / "results/dual_contouring_v3/resolution_rescue_diagnostic.json"
REPORT = HERE / "REAL_CAD_EXPERIMENT_REPORT_2026-08-10.md"
LATEX = HERE / "real_cad_experiment_section_v1.tex"
FIGURE = HERE / "fig_real_cad_experiment_v1.svg"
MANIFEST = HERE / "RESULTS_MANIFEST_2026-08-10.sha256"
ADMISSION_TABLE = HERE / "preflight_admission_by_source.csv"
LEDGER_SUMMARY = HERE / "manual_candidate_ledger_50_to_28_summary.json"


def percent(value: float) -> str:
    return f"{100.0 * value:.2f}%"


def svg_bar(x: float, y: float, width: float, value: float, maximum: float,
            color: str, label: str, value_label: str) -> str:
    length = width * value / maximum if maximum else 0.0
    return (
        f'<text x="{x}" y="{y+16}" class="label">{label}</text>'
        f'<rect x="{x+165}" y="{y}" width="{width}" height="22" rx="3" fill="#edf1f5"/>'
        f'<rect x="{x+165}" y="{y}" width="{length:.2f}" height="22" rx="3" fill="{color}"/>'
        f'<text x="{x+175+length:.2f}" y="{y+16}" class="value">{value_label}</text>'
    )


def make_figure(preflight: dict, freecad: dict, crosscheck: dict, dc: dict) -> str:
    group_rows = []
    for group in sorted({row["source_group"] for row in dc["records"]}):
        records = [row for row in dc["records"] if row["source_group"] == group and row.get("tool_ok")]
        active = sum(row["qef"]["active_cells"] for row in records)
        certified = sum(row["qef"]["certified_oracle_diagnostic"] for row in records)
        group_rows.append((group, certified / active if active else 0.0))
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1680" height="560" viewBox="0 0 1680 560">',
        '<rect width="1680" height="560" fill="white"/>',
        '<style>.title{font:700 24px Arial,sans-serif;fill:#1f2933}.sub{font:16px Arial,sans-serif;fill:#52606d}.label{font:15px Arial,sans-serif;fill:#25313c}.value{font:700 14px Arial,sans-serif;fill:#25313c}.note{font:14px Arial,sans-serif;fill:#7b8794}</style>',
        '<text x="40" y="42" class="title">a  STEP/B-rep preflight (all 528 models)</text>',
        '<text x="590" y="42" class="title">b  End-to-end Dual Contouring</text>',
        '<text x="1110" y="42" class="title">c  Oracle-diagnostic QEF coverage</text>',
    ]
    gates = [
        ("Imported", 528, "#2f855a"),
        ("Valid solid subset", 528, "#2f855a"),
        ("Watertight mesh", 520, "#3182ce"),
        ("Edge-manifold mesh", 519, "#3182ce"),
        ("DC admitted", 511, "#805ad5"),
    ]
    for index, (label, value, color) in enumerate(gates):
        parts.append(svg_bar(40, 82 + 64 * index, 285, value, 528, color, label, f"{value}/528"))
    parts += [
        f'<text x="40" y="430" class="note">FreeCAD/OCCT 7.8.1 cross-check: {crosscheck["comparison_pass"]}/528.</text>',
        '<text x="40" y="458" class="note">No healing/sewing; same kernel family.</text>',
        '<text x="590" y="100" class="label">Selected models</text>',
        '<text x="820" y="100" class="value">122</text>',
        '<text x="590" y="150" class="label">Completed extractions</text>',
        '<text x="820" y="150" class="value">118</text>',
        '<text x="590" y="200" class="label">Coarse-grid misses</text>',
        '<text x="820" y="200" class="value">4</text>',
        '<text x="590" y="250" class="label">Active QEF cells</text>',
        f'<text x="820" y="250" class="value">{dc["totals"]["active_cells"]:,}</text>',
        '<text x="590" y="300" class="label">Bound violations</text>',
        f'<text x="820" y="300" class="value">{dc["totals"]["bound_violations"]}</text>',
        '<text x="590" y="350" class="label">Boundary edges</text>',
        f'<text x="820" y="350" class="value">{dc["totals"]["baseline_boundary_edges"]}</text>',
        '<text x="590" y="400" class="label">Non-manifold edges</text>',
        f'<text x="820" y="400" class="value">{dc["totals"]["baseline_nonmanifold_edges"]:,}</text>',
        '<text x="590" y="455" class="note">4 misses reappear at resolution 32 or 48.</text>',
    ]
    for index, (label, coverage) in enumerate(group_rows):
        parts.append(svg_bar(1110, 82 + 58 * index, 285, coverage, 0.40, "#d97706",
                             label, percent(coverage)))
    parts += [
        f'<text x="1110" y="455" class="note">Pooled: {percent(dc["totals"]["pooled_oracle_diagnostic_coverage"])}</text>',
        '<text x="1110" y="485" class="note">Measured mesh errors; not deployable certificates.</text>',
        '</svg>',
    ]
    return "".join(parts)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    preflight = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
    freecad = json.loads(FREECAD.read_text(encoding="utf-8"))
    crosscheck = json.loads(CROSSCHECK.read_text(encoding="utf-8"))
    dc = json.loads(DC.read_text(encoding="utf-8"))
    rescue = json.loads(RESCUE.read_text(encoding="utf-8"))
    ledger_summary = json.loads(LEDGER_SUMMARY.read_text(encoding="utf-8"))
    complete = [row for row in dc["records"] if row.get("tool_ok")]
    preflight_gates = {
        "imported": sum(row.get("tool_ok", False) for row in preflight["records"]),
        "full_shape_valid": sum(row.get("validity", {}).get("shape_valid", False) for row in preflight["records"]),
        "solid_subset_valid": sum(row.get("validity", {}).get("solid_subset_valid", False) for row in preflight["records"]),
        "positive_brep_volume": sum(row.get("brep_volume", {}).get("all_solids_positive", False) for row in preflight["records"]),
        "closed_solid_shells": sum(row.get("brep_closure", {}).get("all_shells_closed", False) for row in preflight["records"]),
        "watertight_mesh": sum(row.get("mesh", {}).get("watertight", False) for row in preflight["records"]),
        "edge_manifold_mesh": sum(row.get("mesh", {}).get("edge_manifold", False) for row in preflight["records"]),
        "positive_mesh_volume": sum(row.get("mesh", {}).get("positive_signed_volume", False) for row in preflight["records"]),
        "admitted": preflight["admitted"],
    }
    admission_rows = []
    admission_markdown = []
    admission_latex = []
    for group, counts in sorted(preflight["group_counts"].items()):
        row = {
            "source_group": group,
            "total": counts.get("total", 0),
            "admitted": counts.get("admitted", 0),
            "mesh_boundary": counts.get("mesh_boundary", 0),
            "mesh_nonmanifold": counts.get("mesh_nonmanifold", 0),
        }
        row["rejected"] = row["total"] - row["admitted"]
        admission_rows.append(row)
        admission_markdown.append(
            f"| {group} | {row['total']} | {row['admitted']} | "
            f"{row['mesh_boundary']} | {row['mesh_nonmanifold']} | {row['rejected']} |"
        )
        admission_latex.append(
            f"{group.replace('&', r'\&')} & {row['total']} & {row['admitted']} & "
            f"{row['mesh_boundary']} & {row['mesh_nonmanifold']} \\\\"
        )
    with ADMISSION_TABLE.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "source_group", "total", "admitted", "mesh_boundary",
            "mesh_nonmanifold", "rejected",
        ])
        writer.writeheader()
        writer.writerows(admission_rows)
    group_lines = []
    latex_group_lines = []
    for group in sorted({row["source_group"] for row in dc["records"]}):
        selected = [row for row in dc["records"] if row["source_group"] == group]
        rows = [row for row in selected if row.get("tool_ok")]
        active = sum(row["qef"]["active_cells"] for row in rows)
        certified = sum(row["qef"]["certified_oracle_diagnostic"] for row in rows)
        coverage = certified / active if active else 0.0
        group_lines.append(f"| {group} | {len(selected)} | {len(rows)} | {active:,} | {percent(coverage)} |")
        latex_group_lines.append(
            f"{group.replace('&', r'\&')} & {len(selected)} & {len(rows)} & {active:,} & {100*coverage:.2f}\\% \\\\"
        )
    nonmanifold_models = sum(row["baseline_mesh"]["nonmanifold_edges"] > 0 for row in complete)
    degenerate = sum(row["baseline_mesh"]["degenerate_triangles"] for row in complete)
    fallback_mean_errors = sorted(row["contract_fallback_mesh"]["mean_abs_surface_distance_cell_units"] for row in complete)
    fallback_median = fallback_mean_errors[len(fallback_mean_errors)//2]
    report = f"""# Real-CAD preflight and Dual Contouring experiment (2026-08-10)

## Outcome

The fixed corpus contains 528 STEP files: 28 manually curated public/industrial
models and a deterministic 500-model Fusion 360 Gallery sample. OpenCascade
7.9.3 imported all 528 files. The imported full shape and every extracted solid
subset passed `BRepCheck_Analyzer`; every solid subset had closed shells and
strictly positive B-rep volume.

The same 528 files were then processed in isolated FreeCAD 1.1.1 subprocesses,
whose Part module is backed by OpenCascade 7.8.1. All files imported, and all
validity, solid/shell/face-count, closure, auxiliary-shell, and positive-volume
classifications agreed. Every volume pair was within a relative tolerance of
1e-4; the maximum relative difference was
{crosscheck['volume_relative_difference']['maximum']:.8g} on
{crosscheck['volume_relative_difference']['maximum_corpus_id']}. This is a
cross-version and cross-frontend consistency check within the OpenCascade
family, not an independent second-kernel validation.

The no-healing tessellation gate admitted 511/528 models. Eight derived meshes
had boundary edges and nine had non-manifold edges. These 17 rows remain in the
denominator. No crash, timeout, missing file, hash mismatch, or invalid JSON was
observed.

The manual corpus is now backed by a complete 50-to-28 candidate ledger. It
enumerates all 33 STEP members in the frozen NIST archive and all 17 external
download receipts. Twenty-two NIST alternatives were excluded by explicit,
reproducible rules (11 AP203 geometry-only duplicates, five AP203 PMI
duplicates, and six AP242 alternatives outside the preregistered core/replacement
rule); all 17 external candidates were retained. The NIST archive and every
selected STEP file are independently rehashed against their receipt or sample
manifest before any result record is trusted.

| Preflight gate | Passed |
|---|---:|
| STEP import | {preflight_gates['imported']}/528 |
| Full imported shape valid | {preflight_gates['full_shape_valid']}/528 |
| Solid subset valid | {preflight_gates['solid_subset_valid']}/528 |
| All solid shells closed | {preflight_gates['closed_solid_shells']}/528 |
| All B-rep solid volumes positive | {preflight_gates['positive_brep_volume']}/528 |
| Derived mesh watertight | {preflight_gates['watertight_mesh']}/528 |
| Derived mesh edge-manifold | {preflight_gates['edge_manifold_mesh']}/528 |
| Derived mesh signed volume positive | {preflight_gates['positive_mesh_volume']}/528 |
| Dual Contouring admitted | {preflight_gates['admitted']}/528 |

The 17 no-healing rejections decompose by source as follows. The six manual
rejections and eleven Fusion rejections are retained as explicit rows rather
than being silently removed.

| Source group | Total | Admitted | Boundary rejection | Non-manifold rejection | Rejected |
|---|---:|---:|---:|---:|---:|
{chr(10).join(admission_markdown)}

## End-to-end protocol

All 22 admitted manually curated models and the first 100 admitted Fusion rows
in frozen sample order were selected. Manual models used resolution 32 and
Fusion models resolution 24 across the longest bounding-box axis. Each model
ran in isolated OpenCascade-export and Dual-Contouring subprocesses. The
pipeline sampled a fast-winding signed distance, created Hermite constraints on
sign-changing edges, solved a cell-centred regularized QEF with lambda=0.1, and
connected cell vertices with the standard uniform-grid Dual Contouring rule.

| Source group | Selected | Completed | Active cells | Pooled oracle-diagnostic coverage |
|---|---:|---:|---:|---:|
{chr(10).join(group_lines)}

The main run completed 118/122 models. Four thin/anisotropic Fusion parts had no
grid-node sign change at resolution 24. A diagnostic-only ladder recovered
F054 and F085 at resolution 32, and F034 and F083 at resolution 48. The four
main-run failures were not replaced by the rescue results.

Across 162,216 active cells, 36,866 met the tau=0.10 oracle-diagnostic QEF
bound (pooled coverage {percent(dc['totals']['pooled_oracle_diagnostic_coverage'])});
the model-wise median coverage was {percent(dc['distributions']['model_coverage_median'])}.
There were zero violations of the complete QEF displacement bound. The median,
over models, of the median normal-angle error was
{dc['distributions']['model_median_normal_angle_error_degrees_median']:.2f} degrees;
the 95th percentile across model-level 95th-percentile normal errors was
{dc['distributions']['model_p95_normal_angle_error_degrees_p95']:.2f} degrees.

The baseline DC meshes had zero boundary edges and zero degenerate triangles,
but {dc['totals']['baseline_nonmanifold_edges']:,} non-manifold edges across
{nonmanifold_models}/118 completed models. This is a material limitation of the
standard sign-pattern connectivity and motivates a manifold/adaptive DC stage.
The median model mean surface error was
{dc['distributions']['baseline_mean_surface_error_cell_units_median']:.4f} cell
units, while the 95th percentile of per-model maximum error was
{dc['distributions']['baseline_max_surface_error_cell_units_p95']:.4f} cell
units.

## Interpretation boundary

The original triangle mesh supplies closest points and pseudo-normals for the
QEF audit. Consequently the reported bound coverage is an **oracle diagnostic**
of the theorem-to-implementation chain, not a deployable certificate. The real
CAD files do not provide certified value/gradient budgets. A cell-centre
fallback was generated for `Unknown` cells and is explicitly uncertified; its
median mean error ({fallback_median:.4f} cell units) is worse than the baseline,
so the contract should be presented as a status/guard mechanism, not an
automatic geometry improvement.

FreeCAD initially aborted only inside the Codex sandbox because that environment
masked ARM NEON capability detection. The same native arm64 installation ran
normally outside the sandbox and completed the 528-model cross-check. Because
FreeCAD Part is itself backed by OpenCascade, this corroborates the primary
OpenCascade 7.9.3 results across versions and frontends but does not supply an
independent CAD kernel. Assimp routed AP214 STEP to its IFC importer and is
excluded from B-rep claims. The derived-mesh topology audit is likewise not
described as CAD-kernel validation.

![Experiment summary]({FIGURE.name})

## Reproduction

```sh
export GRADIENT_QEF_CAD_ROOT=/path/to/CAD_Tests_Models
cmake -S occt_preflight -B occt_preflight/build -DCMAKE_BUILD_TYPE=Release
cmake --build occt_preflight/build -j4
cmake -S dual_contouring -B dual_contouring/build -DCMAKE_BUILD_TYPE=Release
cmake --build dual_contouring/build -j4
python3 run_occt_preflight.py --workers 4 --timeout 120
python3 run_freecad_preflight.py --workers 4 --timeout 120 --output results/freecad_preflight_v3
python3 compare_brep_preflights.py
python3 run_dual_contouring.py --workers 4 --timeout 180 --fusion-count 100
python3 run_resolution_rescue.py
python3 build_manual_candidate_ledger.py
python3 summarize_real_cad_results.py
python3 verify_real_cad_results.py
python3 test_verifier_tamper_detection.py
```
"""
    REPORT.write_text(report, encoding="utf-8")
    FIGURE.write_text(make_figure(preflight, freecad, crosscheck, dc), encoding="utf-8")

    latex = rf"""% Generated from frozen JSON by summarize_real_cad_results.py.
% This is an insertion candidate for a new manuscript version; v5 is untouched.
\subsection{{Real-CAD end-to-end audit}}
\label{{sec:real-cad-audit}}

We additionally audited a frozen corpus of 528 STEP files: 28 manually curated
public or industrial models and a deterministic 500-model Fusion~360 Gallery
sample.  OpenCascade~7.9.3 imported all files.  The complete imported shapes and
the extracted solid subsets passed the kernel validity check, and every solid
subset had closed shells and positive B-rep volume.  Without healing, sewing,
or fusion, the derived-mesh gate admitted 511 models; eight meshes had boundary
edges and nine had non-manifold edges.  All failures remain in the denominator.
The frozen 50-to-28 manual-candidate ledger records all 33 STEP members of the
NIST archive and all 17 external download receipts, together with each inclusion
or exclusion reason.  Before verification, the archive and all 528 selected
STEP inputs are independently rehashed against their receipts or deterministic
Fusion sample manifest.

\begin{{table}}[t]
\centering
\caption{{No-healing preflight admission by source. Boundary and non-manifold
columns are mutually exclusive rejection reasons.}}
\label{{tab:real-cad-admission}}
\begin{{tabular}}{{lrrrr}}
\toprule
Source & Total & Admitted & Boundary & Non-manifold \\
\midrule
{chr(10).join(admission_latex)}
\bottomrule
\end{{tabular}}
\end{{table}}

An isolated FreeCAD~1.1.1 pipeline backed by OpenCascade~7.8.1 also imported all
528 files.  The two pipelines agreed on validity, solid/shell/face counts,
auxiliary-shell inventory, closure, and positive-volume classification; every
B-rep volume pair agreed within \(10^{{-4}}\) relative error (maximum
{crosscheck['volume_relative_difference']['maximum']:.2e}).  This is a
cross-version and cross-frontend consistency check within the OpenCascade
family, not an independent second-kernel result.

The end-to-end arm used all 22 admitted manual models and the first 100 admitted
Fusion rows in frozen sample order.  Manual and Fusion models used respectively
32 and 24 cells along the longest box axis.  Each isolated run performed STEP
import, solid-subset tessellation, signed-distance sampling, Hermite extraction,
regularized per-cell QEF solution (\(\lambda=0.1\)), and uniform-grid Dual
Contouring connectivity.

\begin{{table}}[t]
\centering
\caption{{Real-CAD end-to-end results. Coverage uses the source mesh as an
oracle and is not a deployable certificate.}}
\label{{tab:real-cad-dc}}
\begin{{tabular}}{{lrrrr}}
\toprule
Source & Selected & Completed & Active cells & Coverage \\
\midrule
{chr(10).join(latex_group_lines)}
\bottomrule
\end{{tabular}}
\end{{table}}

The main run completed 118/122 models.  Four thin or anisotropic Fusion parts
had no grid-node sign change at resolution 24; a diagnostic-only ladder recovered
two at resolution 32 and two at resolution 48, without replacing the four main
failures.  Across 162,216 active cells, 36,866 met the \(\tau=0.10\)
oracle-diagnostic bound (22.73\% pooled coverage), and the complete displacement
bound had zero violations.  The model-wise median coverage was 13.76\%.
The model-median normal-angle error was 3.72 degrees, while the 95th percentile
across model-level 95th-percentile errors was 74.29 degrees.

The extracted meshes had zero boundary edges and zero degenerate triangles, but
2,632 non-manifold edges across 79/118 completed models.  This exposes a
connectivity limitation of standard sign-pattern Dual Contouring rather than a
contract failure, and motivates manifold or adaptive connectivity in future
work.  The median model mean surface error was 0.0462 cell units.

The real-CAD files do not provide certified value and gradient budgets.  We
therefore use source-mesh closest points and pseudo-normals only to audit the
theorem-to-implementation chain.  These measured errors are nondeployable and
must not be labelled \Certified.  An explicit cell-centre fallback for
\Unknown cells increased the median mean error from 0.0462 to
{fallback_median:.4f} cell units, confirming that the contract is a status and
admission mechanism rather than an automatic geometry repair.
"""
    LATEX.write_text(latex, encoding="utf-8")

    manifest_paths = [
        HERE / "occt_preflight/CMakeLists.txt",
        HERE / "occt_preflight/occt_step_preflight.cpp",
        HERE / "dual_contouring/CMakeLists.txt",
        HERE / "dual_contouring/regular_grid_dc.cpp",
        HERE / "run_occt_preflight.py",
        HERE / "freecad_preflight/freecad_step_smoke.py",
        HERE / "run_freecad_preflight.py",
        HERE / "compare_brep_preflights.py",
        HERE / "run_dual_contouring.py",
        HERE / "run_resolution_rescue.py",
        HERE / "build_manual_candidate_ledger.py",
        HERE / "summarize_real_cad_results.py",
        HERE / "verify_real_cad_results.py",
        HERE / "test_verifier_tamper_detection.py",
        HERE / "KERNEL_ENVIRONMENT_AUDIT_2026-08-10.md",
        HERE / "EXPERIMENT_COMPLETION_2026-08-10_CN.md",
        HERE / "selected_model_manifest_v1.csv",
        HERE / "fusion360_sample500_manifest_2026-08-10.csv",
        HERE / "traceparts_receipt_2026-08-10.csv",
        HERE / "3dfindit_receipt_2026-08-10.csv",
        HERE / "3dcontentcentral_receipt_2026-08-10.csv",
        HERE / "grabcad_receipt_2026-08-10.csv",
        HERE / "corpus_v1/manifests/download_receipts.csv",
        HERE / "manual_candidate_ledger_50_to_28.csv",
        LEDGER_SUMMARY,
        ADMISSION_TABLE,
        PREFLIGHT,
        HERE / "results/occt_preflight_v1/occt_preflight_rows.csv",
        FREECAD,
        HERE / "results/freecad_preflight_v3/freecad_preflight_rows.csv",
        CROSSCHECK,
        HERE / "results/brep_crosscheck_v1/brep_crosscheck_rows.csv",
        HERE / "results/brep_crosscheck_v1/BREP_CROSSCHECK_REPORT.md",
        DC,
        HERE / "results/dual_contouring_v3/dual_contouring_rows.csv",
        RESCUE,
        REPORT,
        LATEX,
        FIGURE,
    ]
    MANIFEST.write_text("".join(
        f"{sha256(path)}  {path.relative_to(HERE)}\n" for path in manifest_paths
    ), encoding="utf-8")
    print(REPORT)
    print(LATEX)
    print(FIGURE)
    print(MANIFEST)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
