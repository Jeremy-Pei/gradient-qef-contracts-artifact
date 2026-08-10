# Download and freeze checklist v1

Use this sheet before any benchmark result is inspected.

## Directory layout

```
corpus_v1/
  originals/
    nist/
    traceparts/
    3dfindit/
    3dcontentcentral/
    grabcad/
    fusion360_s2.0.1/
  manifests/
  import_reports/
  derived/
```

Files under `originals/` are immutable.  Converted meshes, level sets and
renderings belong under `derived/`.

## Download order

1. Download NIST N01--N10 and replacement N11R first.  Select AP242.  The
   original HTC record N11 is retained as withdrawn because no direct STEP is
   supplied.
2. Download T01--T04 from TraceParts as STEP AP242.
3. Download D01--D04 from 3Dfindit.  Record the final configured part number,
   nominal size and generated filename because those details are hidden before
   login on some pages.
4. Download C01--C04 from 3D ContentCentral as neutral STEP.
5. Download G01--G05 from GrabCAD using the filenames recorded in the corpus
   selection document.
6. Download and extract the Fusion 360 Gallery `s2.0.1` extended STEP archive.
   Run the deterministic selector before opening or filtering individual
   files.

## Per-file freeze record

Immediately after each download, add:

- corpus ID;
- original page URL;
- manufacturer/uploader and part number;
- UTC download timestamp;
- original filename and byte size;
- SHA-256;
- STEP schema and unit if visible in the file header;
- applicable terms/license URL;
- whether raw redistribution is permitted, prohibited or unresolved.

Do not rename the original.  If a normalized name is needed, create a symlink
or copied working file under `derived/` and retain the mapping.

## Fusion 360 deterministic selection

After extracting the extended STEP archive:

```
python3 select_fusion360_subset.py \
  /absolute/path/to/fusion360_s2.0.1 \
  manifests/fusion360_selected_500.csv
```

The expected output has exactly 500 data rows.  Do not remove a selected row
after import failure.  Fill `import_status`, `validation_status`, and
`failure_category` during the benchmark.

## Pre-result freeze gate

The corpus is frozen only after:

- all 28 manual-source records have either a downloaded file or a documented
  pre-download availability failure;
- the 500-row Fusion manifest exists;
- hashes have been calculated;
- the source and configuration fields contain no blank values;
- a read-only copy or version-control snapshot of the manifests exists.

Only then should the contracted and uncontracted Dual Contouring runs begin.
