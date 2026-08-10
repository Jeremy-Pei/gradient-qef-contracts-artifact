# Regular-grid Dual Contouring demonstration

This executable consumes only meshes admitted by the OpenCascade preflight. It
samples the mesh signed-distance field on a uniform grid, creates Hermite data
on sign-changing edges, solves one regularized QEF per active cell, and builds
the standard edge-connected Dual Contouring mesh.

The source triangle mesh is also used as an oracle to measure root and normal
errors.  Bounds assembled from those measured errors are explicitly labelled
`oracle diagnostic only`: they test the theorem-to-implementation chain but are
not deployable certificates.  A deployable `Certified` result still requires
an upstream field producer that supplies valid value and gradient budgets.

Unknown cells use their cell center only in the separately reported
`contract_fallback_mesh`; this fallback is intentionally not called certified.

