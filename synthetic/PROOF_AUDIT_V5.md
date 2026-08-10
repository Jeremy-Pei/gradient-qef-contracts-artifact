# Version 5 proof-chain audit

Audit date: 2026-08-09

This is an independent assistant audit of the written argument, not a substitute
for author sign-off or external peer review. Numerical tests are cited only as
implementation checks and are not used to prove a universal statement.

## Result

No unresolved algebraic gap was found in the stated local chains after adding
the explicit assumption `lambda >= 0` to the regularized QEF theorem and
stating the positive-definiteness premise of the Neumann comparison.

## Line audit

| Label | Checked argument | Audit result | Remaining boundary |
|---|---|---|---|
| `thm:hard-negative` | Half-space construction, branch reversal, fixed normal jump | Closed by direct substitution | Local counterexample only |
| `thm:branch` | Interval value bounds imply strict branch order | Closed | Requires the strict cell-wide separation test |
| `prop:clarke` | Clarke enclosure at a hard minimum | Correct specialization of the cited nonsmooth result | Set-valued; not a unique normal |
| `thm:smooth` | Weight perturbation plus operand-gradient errors | Closed by the logistic derivative bound and triangle inequality | Binary log-sum-exp only |
| `thm:root` | Field-value error to edge-root displacement | Closed by continuity, monotonicity, and the mean-value theorem | Requires a certified derivative lower bound on the whole edge |
| `lem:normal` | Normalization transfer | Closed by the reverse triangle inequality | Requires `g < mu` |
| `lem:plane` | Root and normal errors to local plane offset | Closed by expansion and Cauchy-Schwarz | Requires a cell-radius bound |
| `lem:qef-budgets` | Row budgets to matrix and right-hand-side budgets | Closed by `||E||_2 <= ||E||_F` and submultiplicativity | Conservative unless an upstream operator-norm budget is supplied |
| `thm:qef` | Observed-side spectral lower bound and QEF displacement | Closed for `lambda >= 0`; the manuscript now states this premise | Compares true and approximate minimizers at the same regularizer |
| `rem:neumann` | Direct Neumann substitution versus the existing guard | Closed when `Hhat` is positive definite | It is an explanatory comparison, not a tighter certificate |
| `rem:row-structure` | Replacement by a certified operator-norm row budget | Algebraically valid because every use of `eta_N` bounds `||E||_2` | The producer of that tighter budget is future work |

## Explicitly unproved global claims

- deep mixed CSG-tree composition;
- certificate production for arbitrary sampled or neural fields;
- crack-free or manifold adaptive connectivity;
- end-to-end Dual Contouring accuracy and performance;
- bias relative to an unregularized feature intersection.

These remain stated as limitations in the manuscript.
