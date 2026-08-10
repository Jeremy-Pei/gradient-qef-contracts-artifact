#!/usr/bin/env python3
"""Build the auditable 50-to-28 manual-corpus selection ledger."""

from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
NIST_ARCHIVE = HERE / "corpus_v1/originals/nist/_archives/NIST-PMI-STEP-Files.zip"
NIST_RECEIPTS = HERE / "corpus_v1/manifests/download_receipts.csv"
OUTPUT_CSV = HERE / "manual_candidate_ledger_50_to_28.csv"
OUTPUT_JSON = HERE / "manual_candidate_ledger_50_to_28_summary.json"

EXTERNAL_RECEIPTS = [
    ("TraceParts", HERE / "traceparts_receipt_2026-08-10.csv"),
    ("3Dfindit", HERE / "3dfindit_receipt_2026-08-10.csv"),
    ("3D ContentCentral", HERE / "3dcontentcentral_receipt_2026-08-10.csv"),
    ("GrabCAD", HERE / "grabcad_receipt_2026-08-10.csv"),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def nist_exclusion_reason(member: str) -> str:
    if "/AP203 geometry only/" in member:
        return "excluded_duplicate_geometry_only_ap203_prefer_ap242"
    if "/AP203 with PMI/" in member:
        return "excluded_duplicate_ap203_pmi_prefer_ap242"
    return "excluded_outside_preregistered_stc_ctc_core_single_ftc11_replacement"


def main() -> int:
    nist_receipts = read_csv(NIST_RECEIPTS)
    selected_nist = {
        row["original_filename"]: (row["corpus_id"], row["file_sha256"])
        for row in nist_receipts
    }
    rows: list[dict[str, object]] = []
    with zipfile.ZipFile(NIST_ARCHIVE) as archive:
        members = sorted(name for name in archive.namelist() if name.lower().endswith(".stp"))
    if len(members) != 33:
        raise RuntimeError(f"expected 33 NIST STEP candidates, found {len(members)}")

    for member in members:
        filename = Path(member).name
        selected = filename in selected_nist
        corpus_id, selected_hash = selected_nist.get(filename, ("", ""))
        rows.append(
            {
                "candidate_index": 0,
                "source_group": "NIST",
                "candidate_locator": member,
                "filename": filename,
                "selected": selected,
                "corpus_id": corpus_id,
                "decision_reason": (
                    "selected_pre_registered_stc_ctc_core_or_ftc11_replacement"
                    if selected
                    else nist_exclusion_reason(member)
                ),
                "selected_step_sha256": selected_hash,
            }
        )

    for source_group, receipt_path in EXTERNAL_RECEIPTS:
        for receipt in read_csv(receipt_path):
            rows.append(
                {
                    "candidate_index": 0,
                    "source_group": source_group,
                    "candidate_locator": receipt["local_step_file"],
                    "filename": receipt["local_step_file"],
                    "selected": True,
                    "corpus_id": receipt["corpus_id"],
                    "decision_reason": "selected_pre_registered_manual_stratum",
                    "selected_step_sha256": receipt["step_sha256"],
                }
            )

    rows.sort(key=lambda row: (str(row["source_group"]), str(row["candidate_locator"])))
    for index, row in enumerate(rows, 1):
        row["candidate_index"] = index

    if len(rows) != 50:
        raise RuntimeError(f"expected 50 manual candidates, found {len(rows)}")
    if sum(bool(row["selected"]) for row in rows) != 28:
        raise RuntimeError("manual selection does not contain exactly 28 selected candidates")
    selected_ids = [str(row["corpus_id"]) for row in rows if row["selected"]]
    if len(selected_ids) != len(set(selected_ids)):
        raise RuntimeError("duplicate selected corpus_id")

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    groups: dict[str, Counter[str]] = defaultdict(Counter)
    reasons: Counter[str] = Counter()
    for row in rows:
        groups[str(row["source_group"])]["candidates"] += 1
        groups[str(row["source_group"])]["selected"] += int(bool(row["selected"]))
        groups[str(row["source_group"])]["excluded"] += int(not bool(row["selected"]))
        reasons[str(row["decision_reason"])] += 1
    summary = {
        "schema": "topic4.manual_candidate_ledger.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "nist_archive": str(NIST_ARCHIVE.relative_to(HERE)),
        "nist_archive_sha256": sha256(NIST_ARCHIVE),
        "total_candidates": len(rows),
        "selected": sum(bool(row["selected"]) for row in rows),
        "excluded": sum(not bool(row["selected"]) for row in rows),
        "group_counts": {group: dict(counts) for group, counts in sorted(groups.items())},
        "decision_reason_counts": dict(sorted(reasons.items())),
        "selected_corpus_ids": sorted(selected_ids),
    }
    OUTPUT_JSON.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
