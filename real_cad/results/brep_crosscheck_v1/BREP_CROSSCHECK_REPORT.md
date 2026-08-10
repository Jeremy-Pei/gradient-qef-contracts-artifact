# B-rep cross-version and cross-frontend audit

The frozen 528-model STEP corpus was imported through two isolated pipelines:
direct OpenCascade 7.9.3 and FreeCAD 1.1.1 backed by OpenCascade 7.8.1.  This is
a cross-version and cross-frontend consistency check within the OpenCascade
kernel family, not an independent second-kernel validation.

| Check | Agreement |
|---|---:|
| Import/validity/closure/positive-volume classifications | 528/528 |
| Solid, solid-shell, and full-shape face counts | 528/528 |
| Auxiliary-shell inventory | 528/528 |
| B-rep volume within relative tolerance 1e-04 | 528/528 |
| Solid-subset bbox diagonal within diagnostic relative tolerance 1e-06 | 472/528 |
| Complete comparison gate | 528/528 |

The complete gate uses categorical, topology, auxiliary-shell, and volume
agreement.  Bounding-box agreement is retained as a diagnostic only because
the two versions/frontends use different tolerance-enlargement details.

The maximum relative B-rep-volume difference was
5.9858336e-05 for
C04.  Only
4 models exceeded
1e-12 relative difference.  The maximum relative bbox-diagonal difference was
0.0012392316.

No healing, sewing, fusion, or topology repair was applied in either pipeline.
Assimp is excluded from B-rep claims because its AP214 detection routed the
input to an IFC importer.  Derived triangle-mesh audits remain downstream mesh
checks and are not presented as CAD-kernel validation.
