# STEP model shortlist for the real-CAD Dual Contouring experiment

Screening date: 2026-08-09

Constraint: the experiment must not introduce CGAL.

## Screening rules

A model enters the primary set only when its detail page explicitly lists an
actual `.step` or `.stp` file. Preference is given to a single mechanical part
with a closed solid, holes or internal passages, curved and planar regions, and
features that exercise Hermite normals and QEF conditioning. Assemblies,
decorative objects, electronics, fasteners, converted STL shells, and entries
whose STEP file cannot be verified are excluded.

The following is a discovery shortlist, not yet the import-qualified corpus.
Each downloaded file must still pass the solid-validity gate below.

## Primary six-model set

| ID | Model and source | Verified files | Geometric role | Expected difficulty | Decision |
|---|---|---|---|---|---|
| P1 | [L-Bracket with Triangular Gusset / Rigid Corner Connector](https://grabcad.com/library/l-bracket-with-triangular-gusset-rigid-corner-connector-1), Yusuf Altay, 2026-06-13 | `Parça 59.STEP`, `Parça 59.STL` | Planar faces, right-angle junction, triangular gusset, circular holes | Low--medium; baseline sharp-feature case | Include |
| P2 | [Multi-Purpose Slotted Adjustment Bracket / Precision Positioning Interface](https://grabcad.com/library/multi-purpose-slotted-adjustment-bracket-precision-positioning-interface-2), Yusuf Altay, 2026-07-08 | `Parça 76.STEP`, `Parça 76.STL` | Long rounded slot, thin plate, mixed line/arc boundary | Medium; tests close parallel surfaces and slot-end normals | Include |
| P3 | [Flanged Bearing Housing / Rotary Hub](https://grabcad.com/library/flanged-bearing-housing-rotary-hub-1), Yusuf Altay, 2026-05-26 | `Parça 5.STEP`, `Parça 5.STL` | Stepped internal bore, cylindrical/planar transitions, two mounting holes | Medium; compact curved-solid case | Include |
| P4 | [50 mm 90-Degree Flanged Pipe Elbow -- 6 Hole Flange Connection](https://grabcad.com/library/50mm-90-degree-flanged-pipe-elbow-6-hole-flange-connection-1), Tarkeshwar Pandey, 2026-08-01 | `Elbow.step` | Hollow curved pipe, two flanges, twelve bolt holes, internal passage | Medium--high; curvature plus repeated perforations | Include |
| P5 | [Gate Valve Body 2 Inch Class 150 ASME API 600](https://grabcad.com/library/gate-valve-body-2-inch-class-150-asme-api-600-1), chibuikem onodingene, 2026-05-02 | `Gate valve body...STEP`, engineering PDF | Multiple flanges, bonnet opening, internal flow passage and blends | High; industrial stress case and topology test | Include after confirming one valid closed solid |
| P6 | [Jet Impeller in Fusion 360, STL, STEP files](https://grabcad.com/library/jet-impeller-in-fusion-360-stl-step-files-1), jesus carrillo, 2025-01-15 | `MY INPROVED IMPELLER 2.step`, matching `.stl`, Fusion source | Thin curved blades, high curvature, narrow gaps and repeated rotational features | High; QEF and adaptive-resolution stress case | Include after minimum-feature-size check |

### Reserve model

[6204 Bearing Housing / Bearing Block](https://grabcad.com/library/6204-bearing-housing-bearing-block-simple-industrial-design-1)
provides `AF20.STEP`, `AF20.SLDASM`, and `AF20.IGS`. It is a useful replacement
for P3 if author diversity is prioritised, but the presence of an assembly file
means that the STEP solid/body count must be checked before admission.

## Experimental strata

- Baseline sharp-feature stratum: P1 and P2.
- Mixed analytic-surface stratum: P3 and P4.
- Industrial/topological stress stratum: P5.
- Thin-feature/high-curvature stress stratum: P6.

The main paper should report results per model as well as macro-averages. P5 and
P6 must not be silently dropped after a failure; an import, topology, memory, or
resolution failure is itself an experimental outcome.

## Mandatory import and validity gate

For every downloaded STEP file:

1. Preserve the original file unchanged and record URL, uploader, download
   date, filename, byte size and SHA-256.
2. Import with FreeCAD/OpenCascade, not CGAL.
3. Record compound, solid, shell and face counts. Select a single intended
   solid only by a documented rule; do not repair or delete bodies silently.
4. Run OpenCascade shape validation (`BRepCheck_Analyzer` or the equivalent
   FreeCAD check). Require a closed solid with positive volume.
5. Reject or separately label invalid shells, self-intersections, zero-area
   faces, duplicated solids and unit/scale ambiguity.
6. Normalize by the bounding-box diagonal only after preserving the original
   unit metadata and transformation.
7. Tessellate at at least two fixed deflection settings and record the settings,
   triangle counts and watertightness. When a matching STL is supplied, use it
   only as a cross-check, not as the source of truth.

## No-CGAL processing route

The intended route is:

`STEP -> FreeCAD/OpenCascade validation and tessellation -> OpenVDB meshToLevelSet
-> sampled SDF/gradient field -> adaptive Dual Contouring -> contracted Hermite
admission -> QEF solve -> mesh and certificate metrics`.

This route uses OpenCascade for STEP/B-rep handling and OpenVDB for level-set
construction. It does not require CGAL. The uncontracted and contracted methods
must use the same imported shape, grid, octree policy, root finder and QEF
regularisation; only the Hermite/normal admission rule should differ.

## STLFinder disposition

The supplied STLFinder query reports thousands of mixed results and describes
STLFinder as an index of models hosted on other platforms. Its first page mixes
STEP-bearing entries with printing accessories, decorative objects, assemblies,
and entries that merely discuss file conversion. Detail pages were also blocked
by a Cloudflare verification step during this audit. Therefore:

- STLFinder may be used for discovery only;
- its result page is not the source-of-record for an experiment;
- a model discovered there enters the corpus only after the originating page,
  actual STEP filename, uploader and applicable terms are independently
  verified.

No STLFinder-only entry is admitted to the primary six-model set at this stage.

## Rights and reproducibility note

GrabCAD states that uploaded CAD files are third-party user submissions. Its
current terms grant site users a non-commercial, internal-use cross-licence, but
that should not be treated as permission to redistribute the STEP files or the
uploader's renderings in a journal supplement. The safe package is therefore:

- cite the model page and uploader;
- publish filenames, download dates, hashes, import diagnostics, derived
  numerical results and independently generated plots;
- do not upload the original STEP/STL files to the paper repository without
  explicit permission from the uploader;
- obtain permission before reproducing model-page images or screenshots.

Relevant pages:

- GrabCAD terms: https://grabcad.com/terms
- STLFinder query: https://www.stlfinder.com/3dmodels/free-step-files/

This note is a conservative reproducibility practice, not legal advice.

