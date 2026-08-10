# CAD-kernel environment audit (2026-08-10)

## Usable primary kernel

- Host architecture: Apple arm64.
- OpenCascade: 7.9.3, native Homebrew installation.
- The preflight executable links no `TK*DRAW` library (`otool -L` match count:
  0), so a library-installed exit handler cannot mask a failing process status.
- No healing, sewing, fusion, or topology mutation is applied before admission.

## Usable cross-version/cross-frontend check

- FreeCAD 1.1.1, its command-line executable, and its bundled Qt 6.8.3 are
  native Apple arm64 binaries.  `FreeCADCmd` initially exited with code 134
  only inside the Codex sandbox because that environment masked ARM NEON
  capability detection.  The same executable ran normally outside the sandbox.
- FreeCAD Part is backed by OpenCascade 7.8.1.  In isolated per-model
  subprocesses it imported all 528 frozen STEP files.  All 528 shapes and solid
  subsets were valid; all solid shells were closed; and all solid volumes were
  positive.
- Against the direct OpenCascade 7.9.3 results, all 528 categorical decisions,
  solid/shell/face counts, and auxiliary-shell inventories agreed.  All B-rep
  volumes agreed within 1e-4 relative difference; the maximum was
  5.9858336e-05 on C04.

This is a cross-version and cross-frontend consistency check within the same
OpenCascade kernel family.  It is not labelled an independent second-kernel
validation.

## Excluded importers

- Assimp 6.0.5 advertises `.step`, but routes a Fusion 360 AP214 STEP file to
  its IFC importer and exits with code 3: `IFC: Unrecognized file schema:
  AUTOMOTIVE_DESIGN ...`.  Assimp is a mesh/asset importer rather than a B-rep
  CAD kernel and is not counted as a CAD-kernel validation.
- CGAL was intentionally excluded at the user's request.

Accordingly, primary B-rep validity, shell-closure, and volume claims remain
direct OpenCascade 7.9.3 results, now corroborated by FreeCAD/OpenCascade 7.8.1.
The derived triangle mesh receives a separate combinatorial audit, but that
audit is not called a second CAD-kernel check.
