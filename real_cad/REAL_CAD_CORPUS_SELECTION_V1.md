# Real-CAD STEP corpus selection v1

Selection frozen: 2026-08-10

Purpose: end-to-end STEP-to-SDF-to-adaptive-Dual-Contouring evaluation for the
Gradient--QEF manuscript.  The processing route must use OpenCascade/FreeCAD
and OpenVDB and must not introduce CGAL.

## Corpus summary

| Stratum | Source | Frozen size | Status |
|---|---|---:|---|
| Public reproducibility core | NIST MBE PMI STEP test cases | 11 | Model identifiers locked; public download pending |
| Industrial A | TraceParts | 4 | Product and configuration locked; login/download pending |
| Industrial B | 3Dfindit/CADENAS | 4 | Product family and configuration rule locked; login/download pending |
| Industrial C | 3D ContentCentral | 4 | Model page and part number locked; login/download pending |
| Large-scale pressure test | Fusion 360 Gallery extended STEP s2.0.1 | 500 | Dataset and deterministic sampling rule locked |
| Complex supplemental cases | GrabCAD | 5 | Model pages locked; login/download pending |

The total intended experiment is therefore 28 manually interpretable models
plus 500 deterministically sampled models.  The 28-model count excludes any
replacement model and treats the NIST Hole Test Case as one test-family item.

## A. NIST public reproducibility core: 11 models

Source of record:
https://www.nist.gov/ctl/smart-connected-systems-division/smart-connected-manufacturing-systems-group/mbe-pmi-0

NIST explicitly states that these test cases, CAD models and STEP files may be
used without restriction, while requesting acknowledgement.  Use AP242 where
available and do not mix an STC and its geometrically identical FTC version.

| ID | NIST identifier | Reason for inclusion |
|---|---|---|
| N01 | STC-06 | Simplified prismatic test part; baseline for planar and cylindrical features |
| N02 | STC-07 | Box component from the related assembly family |
| N03 | STC-08 | Lid component; thin regions and mating geometry |
| N04 | STC-09 | Plate component; repeated holes and planar regions |
| N05 | STC-10 | Fifth distinct simplified test geometry |
| N06 | CTC-01 | Combined-feature test geometry |
| N07 | CTC-02 | Combined-feature part participating in an assembly pair |
| N08 | CTC-03 | Independent combined-feature test geometry |
| N09 | CTC-04 | Companion of the CTC-02 assembly pair |
| N10 | CTC-05 | Independent combined-feature test geometry |
| N11 | HTC | Withdrawn before benchmarking: NIST currently supplies native CATIA/Creo/NX models, not a direct STEP file |
| N11R | FTC-11 | Replacement distinct public AP242 geometry from the same official NIST STEP archive |

N11R replaces N11 before any geometry benchmark is run.  The replacement is
required because the frozen corpus is a STEP-input benchmark and converting a
native HTC model would introduce an uncontrolled exporter.  The withdrawn N11
record is retained in the manifest rather than erased.

## B. TraceParts industrial set: 4 models

All four pages explicitly advertise STEP AP203/AP214/AP242.  Download STEP
AP242 and the exact configuration stated below.

| ID | Locked model/configuration | Geometric role | Source |
|---|---|---|---|
| T01 | Motion Industries / AMI Bearings BPFL6-17, item 03767329 | Two-bolt flange, bore, thin pressed housing and repeated holes | https://www.traceparts.com/en/product/motion-industries-flangemount-ball-bearing-unit-bpfl617?CatalogPath=TRACEPARTS%3ATP01002001001&Product=90-28092021-036675 |
| T02 | Lokring MAS-3000-EL90-P12, 3/4-inch 90-degree elbow | Curved internal passage and pipe/fitting transitions | https://www.traceparts.com/en/product/lokring-technology-90deg-elbow-carbon-steel-pipe-solutions?CatalogPath=TRACEPARTS%3ATP12002005003003&Product=90-29062023-064841 |
| T03 | Stafford 5EFL008REM, 1/2-inch Flange Adapter Max | Bore, flange steps, repeated circular features | https://www.traceparts.com/en/product/stafford-manufacturing-corp-flange-adapter-max?CatalogPath=TRACEPARTS%3ATP01005007&Product=90-14072023-047794 |
| T04 | Automatic Valve L21, L2103AAWR-A | Compact valve body with ports and blends | https://www.traceparts.com/en/product/automatic-valve-l21-series-valve?CatalogPath=ROSS_249594946%3AROOT&Product=90-17072024-050933 |

If a downloaded file is an assembly/compound rather than a single solid, do
not silently extract the easiest body.  Record the body count and apply the
common admission rule below.

## C. 3Dfindit/CADENAS industrial set: 4 models

3Dfindit exposes some content at family level before login.  The family and
configuration rule below are frozen; the final part number and generated STEP
filename must be added immediately after download.

| ID | Locked family/configuration rule | Geometric role | Source |
|---|---|---|---|
| D01 | SKF FNL flanged housing family `AFC_HC_001`; choose the smallest available FNL configuration with a generated STEP file | Cast housing, bore and mounting flange | https://www.3dfindit.com/en/cad-bim-library/manufacturer/skf/bearings-units-and-housings/bearing-housings/flanged-housings?path=skf%2Fbearings_units_and_housings%2Fbearing_housings%2Fflanged_housings |
| D02 | norelem `24080` fixed bearing unit, flange version; choose the smallest listed configuration | Compact flange and repeated holes | https://www.3dfindit.com/en/cad-bim-library/classification/mounted-bearing-unit/rolling-bearing-plain-bearing-spherical-plain-bearing/machine-element-fixing-mounting/eclass/91/flanged-housing-unit?path=cls%2Feclass9.1%2F23%2F05%2F16%2F02 |
| D03 | `Model 64376`, two-way ball valve with square flange and round holes; choose the smallest stainless-steel configuration | Internal passage, flange and valve-body blends | https://www.3dfindit.com/en/keywords/valvulasdedosvias |
| D04 | Buerkert `6281`, 2/2-way servo-assisted solenoid valve; choose the smallest configuration that exports as a single STEP product | Ported valve body and mixed fillets | https://www.3dfindit.com/en/keywords/servovalves |

The words "smallest configuration" mean minimum nominal bore/size shown by the
platform, not minimum downloaded file size.

## D. 3D ContentCentral industrial set: 4 models

Prefer the site's generated neutral STEP output.  Each model still has to pass
the same import gate as all other sources.

| ID | Locked model/configuration | Geometric role | Source |
|---|---|---|---|
| C01 | Nomo UCF3 complete flange bearing housing; configuration UCF 305 | Four-bolt flange housing and central bore | https://www.3dcontentcentral.com/download-model.aspx?catalogid=3063&id=144969 |
| C02 | item profiili oy Angle Bracket, part 30077 | Simple industrial baseline with sharp junctions and holes | https://www.3dcontentcentral.com/download-model.aspx?catalogid=5824&id=211991 |
| C03 | SOLIDWORKS Part Reviewer Mounting Bracket, part `Moderate- Mounting Bracket` | Bent sheet-like solid and multiple angles | https://www.3dcontentcentral.com/download-model.aspx?catalogid=11199&id=661337 |
| C04 | VSI 2.5-inch S7215 two-way ball valve, part S7215-2.5 | Flanged valve, internal passage and assembly/compound stress | https://www.3dcontentcentral.com/download-model.aspx?catalogid=11581&id=925981 |

C04 is deliberately retained even if it is a compound.  A compound import
failure or rejection is a reported result, not a reason to replace it after
seeing the outcome.

## E. Fusion 360 Gallery large-scale pressure test: 500 STEP files

Dataset of record:
https://github.com/AutodeskAILab/Fusion360GalleryDataset

Use the `Segmentation Extended STEP Dataset`, release `s2.0.1` (the repository
describes 42,912 STEP files).  The experimental sample is exactly 500 archive
members selected without replacement by `select_fusion360_subset.py` using:

```
seed = gradient-qef-fusion360-s2.0.1-v1
count = 500
```

The ranking key is SHA-256 of `seed + newline + relative archive path`, sorted
lexicographically.  Selection occurs before import.  Invalid STEP files,
multi-solid files, memory failures and timeouts remain in the denominator and
are reported by failure category.  This prevents post-hoc survivorship bias.

## F. GrabCAD complex supplemental set: 5 models

These models are retained from `STEP_MODEL_SHORTLIST_NO_CGAL.md`:

| ID | Locked model | Role | Source |
|---|---|---|---|
| G01 | L-Bracket with Triangular Gusset | Sharp junction and holes | https://grabcad.com/library/l-bracket-with-triangular-gusset-rigid-corner-connector-1 |
| G02 | Multi-Purpose Slotted Adjustment Bracket | Thin plate and rounded slot | https://grabcad.com/library/multi-purpose-slotted-adjustment-bracket-precision-positioning-interface-2 |
| G03 | 50 mm 90-Degree Flanged Pipe Elbow | Hollow curved pipe and repeated flange holes | https://grabcad.com/library/50mm-90-degree-flanged-pipe-elbow-6-hole-flange-connection-1 |
| G04 | Gate Valve Body 2 Inch Class 150 | Industrial topology and internal flow passage | https://grabcad.com/library/gate-valve-body-2-inch-class-150-asme-api-600-1 |
| G05 | Jet Impeller | Thin curved blades, narrow gaps and high curvature | https://grabcad.com/library/jet-impeller-in-fusion-360-stl-step-files-1 |

The former P3 flanged bearing housing is removed because bearing/flange
geometry is now represented by T01, D01, D02 and C01.  This also reduces
uploader and geometry-family duplication.

## Common admission and reporting rule

1. Preserve every original download unchanged and record its URL, page title,
   uploader/manufacturer, page date if present, download date, byte size and
   SHA-256.
2. Import through FreeCAD/OpenCascade.  Record STEP schema, declared units,
   compounds, solids, shells and faces.
3. Run OpenCascade shape validation.  Record invalidity rather than repairing
   it silently.
4. The main single-solid benchmark accepts only a valid closed solid with
   positive volume.  Compounds and assemblies are reported in a separate
   import/compound stratum unless a source-specified union is available.
5. Do not delete small bodies, merge components or heal topology without a
   named ablation and a preserved pre-repair result.
6. Keep all selected files in the denominator.  Report import, validity,
   resource and numerical failures separately.
7. Do not redistribute TraceParts, 3Dfindit, 3D ContentCentral or GrabCAD raw
   files unless the applicable terms or rights holder explicitly permit it.
   Publish links, part numbers, hashes, diagnostics and derived results.
8. Acknowledge NIST if its models or screenshots are used.  Follow the Fusion
   360 Gallery dataset license and citation instructions.

## Frozen replacement policy

No model may be replaced after results are inspected.  Replacement is allowed
only when the source page disappears before the first download or the platform
cannot generate any STEP file for the locked configuration.  A replacement
must be chosen by the same written rule, assigned an `R` suffix, and recorded
with the reason and date.
