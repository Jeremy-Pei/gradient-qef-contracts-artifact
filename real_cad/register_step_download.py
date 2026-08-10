#!/usr/bin/env python3
"""Copy a manually downloaded STEP file into the frozen corpus and receipt it.

The source file is never moved or modified.  Existing corpus files are never
overwritten.  This script registers one selected manual model at a time.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


BASE = Path(__file__).resolve().parent
SELECTION_MANIFEST = BASE / "selected_model_manifest_v1.csv"
CORPUS_ROOT = BASE / "corpus_v1"
RECEIPTS = CORPUS_ROOT / "manifests" / "download_receipts.csv"

RECEIPT_FIELDS = [
    "corpus_id",
    "source_group",
    "model_name",
    "source_model_or_part_number",
    "source_url",
    "download_timestamp_utc",
    "original_filename",
    "stored_step_path",
    "file_size_bytes",
    "file_sha256",
    "step_schema",
    "original_archive_filename",
    "stored_archive_path",
    "archive_size_bytes",
    "archive_sha256",
    "notes",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_selection(corpus_id: str) -> dict[str, str]:
    with SELECTION_MANIFEST.open(newline="", encoding="utf-8") as stream:
        matches = [
            row
            for row in csv.DictReader(stream)
            if row["corpus_id"].strip().upper() == corpus_id.upper()
        ]
    if len(matches) != 1:
        raise ValueError(
            f"corpus ID {corpus_id!r} has {len(matches)} matches in selection manifest"
        )
    row = matches[0]
    if row["source_group"] == "Fusion 360 Gallery":
        raise ValueError("F500 must be registered with the batch selection workflow")
    return row


def safe_group_name(source_group: str) -> str:
    value = source_group.lower().replace("3d ", "3d_")
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


def detect_schema(path: Path) -> str:
    try:
        header = path.read_bytes()[:256_000].decode("latin-1", errors="ignore")
    except OSError:
        return ""
    match = re.search(r"FILE_SCHEMA\s*\(\s*\((.*?)\)\s*\)\s*;", header, re.I | re.S)
    if not match:
        return ""
    names = re.findall(r"'([^']+)'", match.group(1))
    return " | ".join(names)


def copy_immutable(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256(source) == sha256(destination):
            return
        raise FileExistsError(f"refusing to overwrite different file: {destination}")
    shutil.copy2(source, destination)


def recorded_path(path: Path) -> str:
    """Prefer a project-relative receipt path, with an absolute fallback."""
    try:
        return str(path.relative_to(BASE))
    except ValueError:
        return str(path)


def existing_ids() -> set[str]:
    if not RECEIPTS.exists():
        return set()
    with RECEIPTS.open(newline="", encoding="utf-8") as stream:
        return {row["corpus_id"] for row in csv.DictReader(stream)}


def append_receipt(row: dict[str, object]) -> None:
    RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
    write_header = not RECEIPTS.exists()
    with RECEIPTS.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=RECEIPT_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus_id", help="for example N01, T01, C04 or G05")
    parser.add_argument("step_file", type=Path)
    parser.add_argument("--archive", type=Path, help="optional original ZIP archive")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    corpus_id = args.corpus_id.upper()
    selection = read_selection(corpus_id)
    step_file = args.step_file.expanduser().resolve()
    if not step_file.is_file():
        parser.error(f"STEP file not found: {step_file}")
    if step_file.suffix.lower() not in {".step", ".stp"}:
        parser.error("step_file must end in .step or .stp")
    if corpus_id in existing_ids():
        parser.error(f"{corpus_id} already has a download receipt")

    archive = args.archive.expanduser().resolve() if args.archive else None
    if archive is not None and not archive.is_file():
        parser.error(f"archive not found: {archive}")

    group = safe_group_name(selection["source_group"])
    model_dir = CORPUS_ROOT / "originals" / group / corpus_id
    stored_step = model_dir / step_file.name
    copy_immutable(step_file, stored_step)

    stored_archive = ""
    archive_size: int | str = ""
    archive_hash = ""
    archive_name = ""
    if archive is not None:
        # One source ZIP may contain several selected STEP files.  Preserve one
        # immutable shared copy instead of duplicating the archive per model.
        archive_destination = (
            CORPUS_ROOT / "originals" / group / "_archives" / archive.name
        )
        copy_immutable(archive, archive_destination)
        stored_archive = recorded_path(archive_destination)
        archive_size = archive.stat().st_size
        archive_hash = sha256(archive)
        archive_name = archive.name

    receipt = {
        "corpus_id": corpus_id,
        "source_group": selection["source_group"],
        "model_name": selection["model_name"],
        "source_model_or_part_number": selection["source_model_or_part_number"],
        "source_url": selection["source_url"],
        "download_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "original_filename": step_file.name,
        "stored_step_path": recorded_path(stored_step),
        "file_size_bytes": step_file.stat().st_size,
        "file_sha256": sha256(step_file),
        "step_schema": detect_schema(step_file),
        "original_archive_filename": archive_name,
        "stored_archive_path": stored_archive,
        "archive_size_bytes": archive_size,
        "archive_sha256": archive_hash,
        "notes": args.note,
    }
    append_receipt(receipt)
    print(f"registered {corpus_id}: {stored_step}")
    print(f"SHA-256: {receipt['file_sha256']}")
    print(f"STEP schema: {receipt['step_schema'] or 'not detected'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
