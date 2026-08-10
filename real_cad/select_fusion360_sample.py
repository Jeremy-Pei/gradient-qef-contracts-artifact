#!/usr/bin/env python3
"""Extract a deterministic, split-proportional Fusion 360 STEP sample.

The selection is independent of ZIP member order and Python's random module:
within each official split, identifiers are ranked by SHA-256(seed + NUL + id).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path


PREFIX = "s2.0.1_extended_step"
STEP_PREFIX = f"{PREFIX}/breps/step/"
SEG_PREFIX = f"{PREFIX}/breps/seg/"
TIMELINE_PREFIX = f"{PREFIX}/timeline_info/"


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rank_id(seed: str, model_id: str) -> str:
    return digest_bytes(seed.encode("utf-8") + b"\0" + model_id.encode("utf-8"))


def first_quoted_value(text: str, keyword: str) -> str:
    match = re.search(rf"{keyword}\s*\(\(\s*'([^']*)'", text, flags=re.I | re.S)
    return match.group(1).strip() if match else "unspecified"


def allocate_counts(split_sizes: dict[str, int], sample_size: int) -> dict[str, int]:
    total = sum(split_sizes.values())
    raw = {key: sample_size * value / total for key, value in split_sizes.items()}
    counts = {key: int(value) for key, value in raw.items()}
    remainder = sample_size - sum(counts.values())
    order = sorted(raw, key=lambda key: (-(raw[key] - counts[key]), key))
    for key in order[:remainder]:
        counts[key] += 1
    return counts


def write_member(zf: zipfile.ZipFile, member: str, destination: Path) -> bytes:
    data = zf.read(member)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=500)
    parser.add_argument("--seed", default="GradientQEF-Fusion360-s2.0.1-v1")
    args = parser.parse_args()

    sample_root = args.dataset_root / f"sample_{args.sample_size}"
    if sample_root.exists() and any(sample_root.rglob("*.stp")):
        raise SystemExit(f"Refusing to overwrite an existing sample: {sample_root}")

    archive_sha256 = digest_bytes(args.archive.read_bytes())
    with zipfile.ZipFile(args.archive) as zf:
        members = set(zf.namelist())
        split_member = f"{PREFIX}/train_test.json"
        splits: dict[str, list[str]] = json.loads(zf.read(split_member))
        split_sizes = {key: len(value) for key, value in splits.items()}
        split_counts = allocate_counts(split_sizes, args.sample_size)

        selected: list[tuple[str, str, str]] = []
        for split_name in sorted(splits):
            ranked = sorted(
                ((rank_id(args.seed, model_id), model_id) for model_id in splits[split_name]),
                key=lambda item: (item[0], item[1]),
            )
            selected.extend(
                (split_name, model_id, rank)
                for rank, model_id in ranked[: split_counts[split_name]]
            )
        selected.sort(key=lambda item: (item[0], item[2], item[1]))

        rows: list[dict[str, object]] = []
        for split_name, model_id, rank in selected:
            step_member = f"{STEP_PREFIX}{model_id}.stp"
            seg_member = f"{SEG_PREFIX}{model_id}.seg"
            timeline_member = f"{TIMELINE_PREFIX}{model_id}.json"
            missing = [m for m in (step_member, seg_member, timeline_member) if m not in members]
            if missing:
                raise RuntimeError(f"Missing associated members for {model_id}: {missing}")

            step_data = write_member(zf, step_member, sample_root / "step" / f"{model_id}.stp")
            write_member(zf, seg_member, sample_root / "seg" / f"{model_id}.seg")
            write_member(
                zf,
                timeline_member,
                sample_root / "timeline_info" / f"{model_id}.json",
            )
            text = step_data.decode("latin-1", errors="replace")
            rows.append(
                {
                    "sample_index": len(rows) + 1,
                    "model_id": model_id,
                    "official_split": split_name,
                    "selection_rank_sha256": rank,
                    "step_file": f"step/{model_id}.stp",
                    "step_bytes": len(step_data),
                    "step_sha256": digest_bytes(step_data),
                    "file_description": first_quoted_value(text, "FILE_DESCRIPTION"),
                    "file_schema": first_quoted_value(text, "FILE_SCHEMA"),
                    "manifold_solid_brep": text.upper().count("MANIFOLD_SOLID_BREP"),
                    "brep_with_voids": text.upper().count("BREP_WITH_VOIDS"),
                    "closed_shell": text.upper().count("CLOSED_SHELL"),
                    "advanced_face": text.upper().count("ADVANCED_FACE"),
                    "has_step_end_marker": text.rstrip().endswith("END-ISO-10303-21;"),
                    "validation_status": "text_audited_kernel_validation_pending",
                }
            )

        metadata_root = args.dataset_root / "metadata"
        metadata_members = [
            f"{PREFIX}/Fusion 360 Gallery Dataset Public License.docx",
            f"{PREFIX}/train_test.json",
            f"{PREFIX}/additional_breps_train_test.json",
            f"{PREFIX}/additional_breps.json",
            f"{PREFIX}/segment_names.json",
        ]
        for member in metadata_members:
            write_member(zf, member, metadata_root / Path(member).name)

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with args.manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "dataset": "Fusion 360 Gallery Segmentation Extended STEP Dataset",
        "version": "s2.0.1",
        "official_archive_url": (
            "https://fusion-360-gallery-dataset.s3.us-west-2.amazonaws.com/"
            "segmentation/s2.0.1/s2.0.1_extended_step.zip"
        ),
        "archive_file": str(args.archive),
        "archive_bytes": args.archive.stat().st_size,
        "archive_sha256": archive_sha256,
        "population_step_count": sum(split_sizes.values()),
        "official_split_sizes": split_sizes,
        "sample_size": args.sample_size,
        "sample_split_counts": split_counts,
        "selection_seed": args.seed,
        "selection_method": "lowest SHA-256(seed + NUL + model_id) within each split",
        "sample_root": str(sample_root),
        "all_selected_have_step_end_marker": all(
            bool(row["has_step_end_marker"]) for row in rows
        ),
        "distinct_step_sha256": len({str(row["step_sha256"]) for row in rows}),
        "validation_scope": "ZIP integrity and STEP text audit only; kernel validation pending",
        "license_scope": "non-commercial research; do not redistribute the dataset in its entirety",
    }
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    shutil.copy2(args.manifest, args.dataset_root / args.manifest.name)
    shutil.copy2(args.summary, args.dataset_root / args.summary.name)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
