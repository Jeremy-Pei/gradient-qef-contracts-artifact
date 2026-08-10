# Model collection status -- 2026-08-10

## Completed

- Source download inspected: `${GRADIENT_QEF_CAD_ROOT}/NIST-PMI-STEP-Files.zip`.
- Archive SHA-256:
  `8fa78429e6d8d9b0d7681d223b6aa9ec98c3772185c55b1a0e3679b21c181911`.
- N01--N05 registered from the STC AP242 files.
- N06--N10 registered from the CTC AP242 files.
- N11R registered from the FTC-11 AP242 file as the documented replacement.
- Eleven distinct STEP SHA-256 values were recorded.
- One immutable shared archive copy was preserved; the ZIP was not duplicated
  ten times.
- All eleven selected files declare an AP242 managed model-based 3D engineering
  schema.
- Preliminary text audit found one `MANIFOLD_SOLID_BREP` and one
  `CLOSED_SHELL` declaration in every selected file.
- TraceParts T01--T04 were downloaded as STEP AP242 and frozen under
  `${GRADIENT_QEF_CAD_ROOT}/TraceParts/`.
- The four TraceParts STEP files have distinct SHA-256 values and explicitly
  declare the AP242 managed model-based 3D engineering schema.
- T01 contains three `MANIFOLD_SOLID_BREP` components; T02 and T03 contain one
  each. T04 is represented as one `BREP_WITH_VOIDS` with nineteen
  `CLOSED_SHELL` declarations. These are text-level structure observations,
  not kernel-validity claims.
- 3Dfindit D01--D04 were downloaded as STEP AP242 and frozen under
  `${GRADIENT_QEF_CAD_ROOT}/3Dfindit/`, together with each original
  ZIP and the provider's terms-of-use text.
- D01 is SKF FNL 505 A (smallest `DA=52`, with the A variant used as the
  deterministic tie-break); D02 is norelem 24080-010 (smallest listed size
  10); D03 is BENE INOX 664376-40 (smallest listed DN 40, valve open); D04 is
  Buerkert 6281-270852 (minimum visible DN 13, lower item-number tie-break).
- All four 3Dfindit STEP files explicitly declare the AP242 managed
  model-based 3D engineering schema and have distinct STEP and source-ZIP
  SHA-256 values recorded in `3dfindit_receipt_2026-08-10.csv`.
- The preliminary text structure counts are: D01, three
  `MANIFOLD_SOLID_BREP` and 280 `ADVANCED_FACE`; D02, one and 98; D03, two and
  458; D04, three and 341. These remain text observations rather than
  OpenCascade validation results.
- 3D ContentCentral C01--C04 were downloaded and frozen under
  `${GRADIENT_QEF_CAD_ROOT}/3DContentCentral/`, together with their
  original ZIP packages.
- C01 is UCF 305; C02 is part `0.0.003.20` (the generated download alias is
  `30077`); C03 is `Moderate- Mounting Bracket`; C04 is `S7215-2.5`.
- C01 and C02 were requested through the provider's AP203 UI option, whereas
  their exported headers state `STEP AP214` and `AUTOMOTIVE_DESIGN`. C03 and
  C04 were requested as AP214 and carry the same embedded declarations. This
  UI/header mismatch is preserved rather than silently normalized.
- The preliminary text structure counts are: C01, two
  `MANIFOLD_SOLID_BREP` and 51 `ADVANCED_FACE`; C02, three and 45; C03, one and
  197; C04, one `BREP_WITH_VOIDS`, three `CLOSED_SHELL`, and 1317
  `ADVANCED_FACE`. Each file ends with `END-ISO-10303-21;` and has a distinct
  SHA-256 value recorded in `3dcontentcentral_receipt_2026-08-10.csv`.
- GrabCAD G01--G05 were downloaded after authenticated access and frozen under
  `${GRADIENT_QEF_CAD_ROOT}/GrabCAD/`, with each original ZIP retained.
- The embedded schemas are heterogeneous by design: G01--G02 declare AP214
  `AUTOMOTIVE_DESIGN`; G03 and G05 declare an AP242 managed model-based schema;
  G04 declares AP203 `CONFIG_CONTROL_DESIGN`.
- The preliminary text structure counts are: G01, one
  `MANIFOLD_SOLID_BREP` and 44 `ADVANCED_FACE`; G02, one and 26; G03, one and
  24; G04, one and 187; G05, twelve and 476. G05 is therefore a twelve-solid
  STEP assembly/compound at the text level, which must be handled explicitly
  in the later import and sampling policy.
- All five GrabCAD STEP files end with `END-ISO-10303-21;`, have distinct
  STEP and ZIP SHA-256 values, and are recorded in
  `grabcad_receipt_2026-08-10.csv`.
- The official Fusion 360 Gallery s2.0.1 Extended STEP archive was downloaded
  from Autodesk and frozen once under
  `${GRADIENT_QEF_CAD_ROOT}/Fusion360Gallery/s2.0.1_extended_step/`.
- The archive is 506,333,119 bytes with SHA-256
  `9bebcf0722951bef166c2160cda6e2d3225692b90a90d7dc9cf34dd80fc5a39e`;
  its compressed-data test passed and it contains 42,912 STEP files.
- A deterministic split-proportional sample of 500 models was extracted using
  the seed `GradientQEF-Fusion360-s2.0.1-v1` and the lowest
  `SHA-256(seed + NUL + model_id)` ranks within each official split. The sample
  contains 425 train and 75 test models, matching the source split proportions
  after integer allocation.
- Each selected model retains its STEP file, segmentation label and timeline
  JSON. All 500 STEP hashes are distinct, all 500 files end with the STEP end
  marker, and none has zero text-level B-rep solid entities. The selected STEP
  files range from 5,346 to 1,743,212 bytes and from 1 to 530
  `ADVANCED_FACE` records.
- The complete selection, hashes and text observations are recorded in
  `fusion360_sample500_manifest_2026-08-10.csv`; the sampling protocol is
  recorded in `FUSION360_SAMPLE_PROTOCOL_2026-08-10.md`.

## Important qualification

The preliminary text audit is not an OpenCascade validity proof.  It does not
establish that the shape imports successfully, is geometrically valid, is
watertight after tessellation or has positive volume.

FreeCAD is installed at `/Applications/FreeCAD.app`, but its bundled command
line executable failed before importing any file with:

```
Incompatible processor. This Qt build requires the following features:
    neon
```

Therefore kernel-level import/validity fields remain explicitly pending.  No
model has been reported as OpenCascade-valid yet.

## Pre-benchmark selection correction

- Original N11 (Hole Test Case) was withdrawn because NIST supplies native
  CATIA/Creo/NX files rather than a direct STEP file.
- N11R (FTC-11 AP242) was selected from the already downloaded official NIST
  STEP archive as the documented replacement.

## Collection boundary reached

- All planned source groups have now been downloaded and frozen: NIST,
  TraceParts, 3Dfindit, 3D ContentCentral, GrabCAD and the Fusion 360 Gallery
  stress-test sample.
- Kernel-level STEP import, shape validity, watertightness, positive volume and
  downstream Dual Contouring experiments remain pending. These are validation
  and benchmark tasks rather than model-collection tasks.

## Source README warning retained

The NIST archive README states that these are test artifacts rather than
error-free reference STEP files, and that syntax/conformance tools can report
errors.  This warning is retained in the receipt for N01 and must be reflected
when interpreting later failures.
