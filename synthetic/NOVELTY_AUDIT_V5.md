# Version 5 targeted novelty audit

Audit date: 2026-08-09

## Mechanism tested

The reverse novelty probe was:

> A local, fail-closed contract that takes explicit value and gradient error
> budgets for an approximate implicit CSG cell, propagates them through branch
> selection or a smooth Boolean, an edge root, a normalized normal, and a
> Hermite plane, and returns a computable worst-case displacement bound for a
> regularized QEF vertex.

This is a targeted screen, not proof of priority. The manuscript therefore does
not use an unqualified "first" claim.

## Candidate screen

Twelve close primary technical works were screened against the mechanism.

| Work | Strongest overlap | Missing relative to the probe |
|---|---|---|
| Ju et al. 2002, Dual Contouring | Hermite points, normals, QEF and rank handling | No bounded upstream-error-to-QEF displacement contract |
| Trettner and Kobbelt 2020 | Point/normal uncertainty in quadrics | Probabilistic expectation rather than fail-closed worst-case sets |
| Chen et al. 2022 | Learned Dual Contouring vertices and topology | No local deterministic certificate |
| Zhang et al. 2023 | Unreliable UDF gradients and filtered tangent planes | Produces a reconstruction method, not the stated contract chain |
| Carrera et al. 2026 | Dual Contouring from sampled signed-distance data | Reconstruction objective rather than value/gradient budget propagation |
| Kohlbrenner and Alexa 2026 | Gradient approximation and contact filtering | No compositional worst-case QEF displacement certificate |
| Schaefer et al. 2007 | Manifold adaptive Dual Contouring | Certifies topology/connectivity, not uncertain Hermite input motion |
| Plantinga and Vegter 2004 | Fail-closed interval predicates and isotopic meshing | Certifies global topology under interval subdivision, not QEF displacement |
| Bálint et al. 2023 | Distance-estimate behavior and precision loss through CSG | Value/tracing semantics rather than gradient-to-Hermite-QEF transfer |
| Barbier et al. 2025 | Regionally exact active-subtree pruning for hard and smooth CSG | No derivative uncertainty or QEF consumer guarantee |
| Wang et al. 2025 | Producer-side convergence toward a true neural SDF | Asymptotic field production rather than a finite per-query contract |
| Liu et al. 2024 | Differentiable hard/smooth Boolean design | Optimizable operator family rather than worst-case uncertainty propagation |

No exact mechanism match was found among these twelve candidates. This null
result is bounded by the stated search set and should be refreshed before
submission.

## Position retained in the manuscript

The problem diagnosis is not claimed as novel: prior work already establishes
that approximate distance fields, gradients, contact points, topology, and QEF
conditioning can fail. The narrower contribution is the explicit alignment of
local geometric assumptions, computable error budgets, and a fail-closed QEF
consumer rule.

## Primary identifiers checked

- `10.1145/566654.566586`
- `10.1111/cgf.13933`
- `10.1145/3528223.3530108`
- `10.1109/ICCV51070.2023.02059`
- `10.1109/TVCG.2007.1012`
- `10.2312/SGP/SGP04/251-260`
- `10.14733/cadaps.2023.1154-1174`
- `10.1111/cgf.70057`
- `10.1145/3641519.3657484`
- CVPR 2025, pages 1276-1286 (HotSpot)
