#!/usr/bin/env python3
"""Deterministically select raw STEP members from Fusion 360 Gallery s2.0.1.

Selection is deliberately performed before CAD import.  Files that later fail
to import or validate remain part of the experiment denominator.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path


DEFAULT_SEED = "gradient-qef-fusion360-s2.0.1-v1"
DEFAULT_COUNT = 500


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rank_key(seed: str, relative_path: str) -> str:
    payload = f"{seed}\n{relative_path}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def discover_step_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".step", ".stp"}
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    args = parser.parse_args()

    root = args.dataset_root.resolve()
    if not root.is_dir():
        parser.error(f"dataset root is not a directory: {root}")
    if args.count <= 0:
        parser.error("--count must be positive")

    files = discover_step_files(root)
    if len(files) < args.count:
        parser.error(
            f"requested {args.count} STEP files but found only {len(files)}"
        )

    ranked: list[tuple[str, str, Path]] = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        ranked.append((rank_key(args.seed, relative), relative, path))
    ranked.sort(key=lambda item: (item[0], item[1]))
    selected = ranked[: args.count]

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "selection_index",
                "dataset_release",
                "seed",
                "rank_sha256",
                "relative_path",
                "file_size_bytes",
                "file_sha256",
                "import_status",
                "validation_status",
                "failure_category",
            ],
        )
        writer.writeheader()
        for index, (rank, relative, path) in enumerate(selected, start=1):
            writer.writerow(
                {
                    "selection_index": index,
                    "dataset_release": "s2.0.1-extended-step",
                    "seed": args.seed,
                    "rank_sha256": rank,
                    "relative_path": relative,
                    "file_size_bytes": path.stat().st_size,
                    "file_sha256": file_sha256(path),
                    "import_status": "pending",
                    "validation_status": "pending",
                    "failure_category": "",
                }
            )

    print(
        f"selected {len(selected)} of {len(files)} STEP files; "
        f"manifest: {args.output_csv}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
