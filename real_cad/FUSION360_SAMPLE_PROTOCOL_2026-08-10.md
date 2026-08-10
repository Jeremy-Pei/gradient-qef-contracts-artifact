# Fusion 360 Gallery stress-sample protocol

## Source

- Dataset: Fusion 360 Gallery Segmentation Extended STEP Dataset.
- Version: `s2.0.1`.
- Official repository: <https://github.com/AutodeskAILab/Fusion360GalleryDataset>.
- Official archive: <https://fusion-360-gallery-dataset.s3.us-west-2.amazonaws.com/segmentation/s2.0.1/s2.0.1_extended_step.zip>.
- Archive size: 506,333,119 bytes.
- Archive SHA-256:
  `9bebcf0722951bef166c2160cda6e2d3225692b90a90d7dc9cf34dd80fc5a39e`.
- Population: 42,912 STEP models: 36,458 official train and 6,454 official
  test identifiers.

The archive passed `unzip -tq` before sampling.

## Deterministic selection

The experiment freezes a 500-model sample. For each official split separately,
every model identifier is assigned the rank key

```text
SHA-256("GradientQEF-Fusion360-s2.0.1-v1" + NUL + model_id)
```

Identifiers are ordered by `(rank key, model_id)`. The lowest 425 train and 75
test identifiers are selected. These counts are the proportional integer
allocation induced by the official 36,458/6,454 split.

This rule is independent of ZIP member order and Python's pseudorandom-number
implementation. It can be reproduced with
`select_fusion360_sample.py`.

## Frozen artifacts

For every selected identifier, the frozen sample includes:

- `step/<model_id>.stp`;
- `seg/<model_id>.seg`;
- `timeline_info/<model_id>.json`.

The archive's split files, segment names, additional-B-rep metadata and public
license document are preserved under `metadata/`. The row-level record is
`fusion360_sample500_manifest_2026-08-10.csv`.

## Verified facts and limits

- 500 STEP files, 500 segmentation files and 500 timeline JSON files exist.
- All 500 STEP SHA-256 values are distinct.
- All 500 STEP files end with `END-ISO-10303-21;`.
- All sampled files declare an `AUTOMOTIVE_DESIGN` AP214 schema.
- Text-level entity counts show no selected file with zero
  `MANIFOLD_SOLID_BREP` plus `BREP_WITH_VOIDS` occurrences.

These checks do not establish successful OpenCascade import, valid topology,
watertight tessellation or positive volume. Those fields remain pending until
the kernel-level preflight is run.

## License boundary

The Autodesk dataset license permits access, use, reproduction and modification
only for non-commercial research. It prohibits redistribution of the Dataset in
its entirety and imposes conditions on redistribution of portions or modified
sets. The original public license document from the archive is preserved with
the frozen metadata. Publication artifacts should normally distribute the
selection manifest and source link, not the full source archive.
