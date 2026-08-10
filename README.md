# Gradient-to-QEF contracts: reproducibility artifact

This repository accompanies **Fail-Closed Gradient-to-QEF Contracts for
Approximate Implicit CSG** by Jeremy Pei.

It contains two evidence layers:

- `synthetic/`: deterministic analytic stress tests, frozen JSON, regression
  checks, and figures used for the theorem-to-implementation audit.
- `real_cad/`: OpenCascade/FreeCAD STEP preflight code, a regular-grid Dual
  Contouring implementation, frozen row-level results, input receipts and
  SHA-256 values, a 50-to-28 selection ledger, and fail-closed verification.
- `manuscript/`: the post-v5 manuscript source and rendered PDF containing the
  real-CAD experiment.

## Important scope boundary

The real-CAD coverage values use source-mesh closest points and pseudo-normals.
They are **oracle diagnostics**, not deployable certificates. FreeCAD uses the
same OpenCascade kernel family and is a cross-version/cross-frontend check, not
an independent second CAD kernel.

## Quick verification without STEP inputs

```bash
cd real_cad
python3 verify_real_cad_results.py --artifact-only
```

This checks the frozen per-model records against their aggregates, recomputes
the OCCT/FreeCAD cross-check, all reported continuous metrics, group coverage,
rescue resolutions, and the artifact manifest. It does not claim to re-import
the third-party STEP files.

## Full input verification

Third-party STEP files are not redistributed. Acquire them from the recorded
sources and reconstruct the input tree using
`real_cad/COLLECTION_STATUS_2026-08-10.md`, the source receipt CSV files, and
`real_cad/selected_model_manifest_v1.csv`, then run:

```bash
export GRADIENT_QEF_CAD_ROOT=/absolute/path/to/CAD_Tests_Models
cd real_cad
python3 verify_real_cad_results.py
python3 test_verifier_tamper_detection.py
```

The full mode recomputes every available input hash against the download
receipts and deterministic Fusion sample manifest before accepting a result
record.

## Synthetic audit

```bash
cd synthetic
python3 scripts/generate_results.py --out results/topic4_results.json
python3 tests/test_contracts.py
python3 scripts/plot_results.py \
  results/topic4_results.json figures/fig_topic4_contract_audit.png
```

Finite sampling checks implementation consistency; it does not replace the
analytic proofs.

## Archived release

Release checksums are in `SHA256SUMS.txt`. The intended public repository is
<https://github.com/Jeremy-Pei/gradient-qef-contracts-artifact>.
