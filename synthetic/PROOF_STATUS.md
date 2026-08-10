# Topic 4 proof and evidence status

| ID | Claim | Analytic status | Executable evidence | Publication status |
|---|---|---|---|---|
| T1 | Hard Boolean has no uniform branch-independent single-normal continuity near a switch | Closed elementary construction; avoids evaluating at a non-differentiable tie | 30 deterministic cases, zero construction violations | Assistant line audit complete; independent human review and author sign-off remain |
| T2 | Certified branch separation transfers the active operand gradient contract | Closed interval argument | Covered indirectly by deterministic construction/tests | Assistant line audit complete; independent human review and author sign-off remain |
| P3 | Switch-set generalized gradients are enclosed by the convex hull of active operand gradients | Standard Clarke-calculus specialization | No finite test can prove the set inclusion | Assistant specialization audit complete; independent human review remains |
| T4 | Binary log-sum-exp propagates a coupled value/gradient bound | Closed mean-value and triangle-inequality chain | 250,000 cases, zero complete-bound violations; 31,479 failures when the coupling term is removed | Assistant line audit complete; independent human review and author sign-off remain |
| T5-L7 | Field value/gradient budgets transfer to edge-root, unit-normal, and local-plane budgets | Closed mean-value, normalization, and Cauchy–Schwarz chains | 30,000 nonlinear monotone edge tests, zero root-bound violations | Assistant line audit complete; independent human review and author sign-off remain |
| L8-T9 | Regularization plus an observed-side spectral lower bound gives a QEF vertex-displacement certificate | Closed matrix perturbation chain using Weyl; theorem now states $\lambda\geq 0$ explicitly | 60,000 regularized systems; zero complete-bound violations; the original 40,000-case conditioning audit has 20,396 geometry-identifiable systems | Assistant line audit complete; independent human review and author sign-off remain |
| D1 | QEF slack can be decomposed into declared-budget, realized-budget, and exact-matrix diagnostic arms | Diagnostic only; the latter two inspect true quantities and are not deployable certificates | At tolerance 0.10: 46.75%, 53.52%, and 76.32% coverage; all three arms have zero observed bound violations | May support conservatism analysis only, not a new theorem |
| D2 | QEF evidence is not restricted to compatible common-point planes | Diagnostic coverage extension; no new theorem | 10,000 controlled inconsistent plane systems and 10,000 sphere/paraboloid Hermite patches; nonzero median data residuals and zero complete-bound violations | Supports implementation coverage only |
| D3 | A direct Neumann-series replacement cannot tighten the current regularized spectral guard | Closed algebraic comparison: when Neumann applies it reproduces the observed spectral term, while the current guard also takes the maximum with the regularizer | No numerical evidence required or claimed | Added as an explanatory remark, not a new contribution |
| D4 | A certified structured row budget may replace the Frobenius aggregation | Closed algebraic substitution: any computable $\eta_N^{\mathrm{op}}\geq\|N-\widehat N\|_2$ can replace $\eta_N$ in the downstream lemmas | No new numerical evidence claimed; realized true-row norms remain diagnostic only | Clarifies a future certificate interface rather than claiming a tighter current experiment |
| A1 | Hermite point-position budget is logically necessary in the QEF chain | Analytic necessity follows from the right-hand-side perturbation | Omitting it caused 2,874 violations among 60,000 regularized systems | Evidence supports, but does not replace, proof |
| C1 | End-to-end adaptive Dual Contouring on real CAD/ThingiCSG | Open | Not implemented in the current package | Must not be claimed in the draft |
| C2 | Deep mixed CSG DAG composition | Open | Not tested | Future work |
| C3 | Sampled/neural field certificate production | Open | No certified producer | Empirical-only extension if later added |

## Frozen evidence

- Seed: `20260808`
- Record: `results/topic4_results.json`
- Figure: `figures/fig_topic4_contract_audit.png`
- Residual-stress figure: `figures/fig_topic4_residual_stress.png`
- Regression command: `python3 tests/test_contracts.py`
- Schema: `hybridcad.topic4.gradient-hermite-qef.v3`
- Line audit: `PROOF_AUDIT_V5.md`
- Targeted close-work audit: `NOVELTY_AUDIT_V5.md`

The JSON explicitly states that finite sampling is implementation evidence and
not a mathematical proof.
