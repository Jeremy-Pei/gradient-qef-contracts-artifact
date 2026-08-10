# Topic 4 v5 release manifest

Built and checked on 2026-08-09.

## Version boundary

- Parent manuscript: `research/topic4_v4/paper/gradient_qef_contracts_v4.tex`
- The v4 directory remains unchanged.
- The prior default active package was frozen under
  `research/topic4/frozen/pre_v5_promotion_20260809/` before promotion.
- The numerical protocol remains schema
  `hybridcad.topic4.gradient-hermite-qef.v3`; version 5 changes the manuscript,
  proof/novelty audit records, and package documentation, not the frozen
  experiment.
- Random seed: `20260808`.

## Scientific changes in v5

- The QEF theorem now states `lambda >= 0` explicitly, and the direct Neumann
  comparison states the positive-definiteness premise needed for inversion.
- The row-aggregation discussion separates the deployable Frobenius bound from
  a future certified operator-norm or correlation-aware upstream interface.
  No oracle-derived empirical factor is used as a runtime certificate.
- Related work now distinguishes the manuscript from topology/isotopy
  guarantees, CSG value estimates, regional Lipschitz pruning, differentiable
  Boolean operators, and neural-SDF certificate producers.
- A line-by-line proof audit and a bounded close-work novelty audit are included.

## Verification

- Complete generation/test/plot/build chain: passed.
- Contract regression tests: passed; finite sampling is recorded as
  implementation evidence, not proof.
- Frozen JSON matches version 4 byte-for-byte.
- LaTeX build: passed; 14 A4 pages.
- Final LaTeX log: no undefined references, citation warnings, overfull boxes,
  or underfull boxes.
- Visual inspection: all 14 rendered pages checked; equations, tables, figures,
  captions, references, and page breaks are legible.
- Citation integrity: 14 bibliography entries, 14 cited, 0 missing, 0 uncited.
- Targeted novelty screen: 12 close primary works; no exact mechanism match in
  that bounded set.  This is not an exhaustive priority proof.

## SHA-256 checksums

| Artifact | SHA-256 |
|---|---|
| `output/pdf/gradient_qef_contracts_v5.pdf` | `33455164d65a73cc3170698e61d53d4edef409a60e3873213847d3e26d2b9463` |
| `paper/gradient_qef_contracts_v5.tex` | `40841f3397892a879d47c9cbda5428e17e84d99a3ea6ed9ea56395180508f6c5` |
| `results/topic4_results.json` | `b8cc3f10ad70cd2207d762397db061fdb7be4d62bd7a083e4aaecba48fb00f43` |
| `figures/fig_topic4_contract_audit.pdf` | `ea78b54e0820cfd4bc21154e9cc5391193ef870a3e05fc4f620ddca50bd6fd73` |
| `figures/fig_topic4_residual_stress.pdf` | `28bbf9025f040e343f10f22bc763816b07497899dc31471636fa661fd22e1644` |
| `scripts/generate_results.py` | `3425d3784010fb2cb1be14891647ce257873bb2f2c00524c917c5a49f5656353` |
| `scripts/plot_results.py` | `0c26653226acbb384a6db5a49d86873919a5472d74167708b6f15252744e8934` |
| `scripts/run_all.py` | `30885b88c45c4e9cdfe48ffc6458e76fc984092272c3c19332cde39ec869be4c` |
| `tests/test_contracts.py` | `a16319eafa62e9b21cba638646ceb01984788f45f13fe2e6653dbd7795dbb301` |
| `README.md` | `15cd56f6f9f107dbbfaaffde2e1642b832733f431a9fed1aaece7b65ec270ad2` |
| `PROOF_STATUS.md` | `fab4e983c76671be08dbf4790d4c96d0c8b637fcdf6cf6095ab8b0dbf6e38be7` |
| `PROOF_AUDIT_V5.md` | `7590488256da035790793207c5c6121a0c3fb964ddcc22e4f58d7dae813d4146` |
| `NOVELTY_AUDIT_V5.md` | `60cc86818f094892e2afdf7d0c14c10b63c95092b0291ae58d3c177dc1be3964` |
| `theory/derivations.md` | `773b13a66de9158ffbf77f224288288a1980fe8ab58fa25f3916a16f442d72bb` |

