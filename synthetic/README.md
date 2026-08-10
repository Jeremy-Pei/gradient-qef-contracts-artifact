# Topic 4 research package

This directory contains the version-5 research slice for the project
"Gradient-domain field contracts for verifiable Hermite/QEF inputs".

The package deliberately separates analytic claims from numerical evidence:

- `theory/derivations.md` states definitions, theorems, and proof chains.
- `scripts/generate_results.py` generates the frozen JSON record. It does not
  draw figures.
- `scripts/plot_results.py` reads the JSON record and only draws figures.
- `tests/test_contracts.py` checks the executable proof obligations and the
  two ablations, as well as two nondeployable QEF slack diagnostics.
- `paper/gradient_qef_contracts_v5.tex` is the version-5 paper draft.
- `PROOF_AUDIT_V5.md` records a claim-by-claim assistant line audit; it does
  not replace independent human review or author sign-off.
- `NOVELTY_AUDIT_V5.md` records a bounded, targeted close-work search and its
  limits; it is not an exhaustive priority proof.

## Reproduce

From this directory:

```bash
python3 scripts/generate_results.py --out results/topic4_results.json
python3 tests/test_contracts.py
python3 scripts/plot_results.py \
  results/topic4_results.json figures/fig_topic4_contract_audit.png
cd paper && latexmk -pdf -interaction=nonstopmode gradient_qef_contracts_v5.tex
```

Or run the complete chain:

```bash
python3 scripts/run_all.py
```

The random seed and every experiment count are stored in the JSON output.
The QEF record distinguishes a deployable declared-budget certificate from a
realized-budget diagnostic and an exact-matrix diagnostic.  The latter two use
true synthetic quantities and must not be presented as runtime certificates.
Version 5 retains the 20,000 residual-stress systems introduced in version 3:
10,000 controlled
inconsistent plane systems and 10,000 sphere/paraboloid Hermite patches.  The
separate residual-stress figure is generated from the same frozen JSON.
It also states algebraically why a direct Neumann-series substitution cannot
tighten the existing regularized spectral guard.
Version 5 additionally clarifies that the Frobenius row aggregation is the
deployable worst-case certificate currently evaluated.  A certified upstream
operator-norm or correlation-aware row certificate can replace it
algebraically, but realized true-row errors are diagnostic and are not used as
runtime certificates.  The related-work discussion and bibliography were
expanded around Boolean/SDF bounds, differentiable Boolean operations,
topology-aware contouring, and neural-field certificate producers.
The current package uses analytic fields and cell-level QEF systems; it is not
yet a production adaptive Dual Contouring implementation and does not claim a
ThingiCSG-scale result.
