#!/usr/bin/env python3
"""Independent input-anchor, row-level, arithmetic, and manifest verification."""

from __future__ import annotations

import csv
import argparse
import hashlib
import json
import math
import os
import subprocess
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


HERE = Path(__file__).resolve().parent
MODEL_ROOT = Path(os.environ.get(
    "GRADIENT_QEF_CAD_ROOT", str(HERE / "inputs")
)).expanduser().resolve()
FUSION_ROOT = MODEL_ROOT / "Fusion360Gallery/s2.0.1_extended_step/sample_500"


class VerificationError(RuntimeError):
    """A frozen artifact failed an independently recomputed condition."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def require_close(actual: float, expected: float, message: str,
                  *, rel_tol: float = 1.0e-12, abs_tol: float = 1.0e-15) -> None:
    require(
        math.isfinite(float(actual))
        and math.isfinite(float(expected))
        and math.isclose(float(actual), float(expected), rel_tol=rel_tol, abs_tol=abs_tol),
        f"{message}: actual={actual!r}, expected={expected!r}",
    )


def ensure_finite(value: Any, path: str = "root") -> None:
    if isinstance(value, float):
        require(math.isfinite(value), f"non-finite JSON number at {path}")
    elif isinstance(value, dict):
        for key, child in value.items():
            ensure_finite(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            ensure_finite(child, f"{path}[{index}]")


def load(path: Path) -> dict[str, Any]:
    document = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    require(isinstance(document, dict), f"JSON root is not an object: {path}")
    ensure_finite(document, str(path))
    return document


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def linear_quantile(values: Iterable[float], q: float) -> float:
    ordered = sorted(float(value) for value in values)
    require(bool(ordered), "quantile received no values")
    position = q * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return (1.0 - fraction) * ordered[lower] + fraction * ordered[upper]


def ceiling_quantile(values: Iterable[float], q: float) -> float:
    ordered = sorted(float(value) for value in values)
    require(bool(ordered), "quantile received no values")
    index = min(len(ordered) - 1, max(0, int(math.ceil(q * len(ordered))) - 1))
    return ordered[index]


def relative_difference(a: float, b: float) -> float:
    return abs(float(a) - float(b)) / max(abs(float(a)), abs(float(b)), 1.0e-300)


def record_map(records: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    require(all(isinstance(row, dict) and row.get("corpus_id") for row in records),
            f"{label} contains a missing/empty corpus_id row")
    mapped = {str(row["corpus_id"]): row for row in records}
    require(len(mapped) == len(records), f"{label} contains duplicate corpus_id values")
    return mapped


def verify_individual_files(directory: Path, records: list[dict[str, Any]], label: str) -> None:
    mapped = record_map(records, label)
    files = sorted((directory / "individual").glob("*.json"))
    require(len(files) == len(records),
            f"{label} individual count {len(files)} != record count {len(records)}")
    require({path.stem for path in files} == set(mapped), f"{label} individual ID set mismatch")
    for path in files:
        require(load(path) == mapped[path.stem], f"{label} individual differs from aggregate: {path.stem}")


def build_external_input_anchors(root: Path) -> dict[str, dict[str, Any]]:
    selected_rows = read_csv(root / "selected_model_manifest_v1.csv")
    selected_manual = {
        row["corpus_id"]
        for row in selected_rows
        if row["source_group"] != "Fusion 360 Gallery"
        and row["selection_status"].startswith("locked")
    }
    require(len(selected_manual) == 28, f"selected manual manifest count is {len(selected_manual)}, not 28")

    anchors: dict[str, dict[str, Any]] = {}
    for row in read_csv(root / "corpus_v1/manifests/download_receipts.csv"):
        path = root / row["stored_step_path"]
        anchors[row["corpus_id"]] = {
            "source_group": "NIST",
            "path": path,
            "sha256": row["file_sha256"],
            "bytes": int(row["file_size_bytes"]),
        }

    external_receipts = [
        ("TraceParts", root / "traceparts_receipt_2026-08-10.csv"),
        ("3Dfindit", root / "3dfindit_receipt_2026-08-10.csv"),
        ("3D ContentCentral", root / "3dcontentcentral_receipt_2026-08-10.csv"),
        ("GrabCAD", root / "grabcad_receipt_2026-08-10.csv"),
    ]
    external_index: dict[str, list[Path]] = defaultdict(list)
    for path in MODEL_ROOT.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".stp", ".step"} and FUSION_ROOT not in path.parents:
            external_index[path.name].append(path)
    for source_group, receipt_path in external_receipts:
        for row in read_csv(receipt_path):
            matches = external_index[row["local_step_file"]]
            require(len(matches) == 1,
                    f"external receipt path is not unique for {row['corpus_id']}: {matches}")
            anchors[row["corpus_id"]] = {
                "source_group": source_group,
                "path": matches[0],
                "sha256": row["step_sha256"],
                "bytes": int(row["step_bytes"]),
            }
    require(set(anchors) == selected_manual,
            f"manual receipt IDs differ from selected manifest: {sorted(set(anchors)^selected_manual)}")

    fusion_rows = read_csv(root / "fusion360_sample500_manifest_2026-08-10.csv")
    require(len(fusion_rows) == 500, f"Fusion manifest has {len(fusion_rows)} rows, not 500")
    require(Counter(row["official_split"] for row in fusion_rows) == {"train": 425, "test": 75},
            "Fusion train/test allocation differs from 425/75")
    seed = b"GradientQEF-Fusion360-s2.0.1-v1"
    for row in fusion_rows:
        expected_rank = hashlib.sha256(seed + b"\0" + row["model_id"].encode("utf-8")).hexdigest()
        require(row["selection_rank_sha256"] == expected_rank,
                f"Fusion selection rank mismatch: {row['model_id']}")
        corpus_id = f"F{int(row['sample_index']):03d}"
        anchors[corpus_id] = {
            "source_group": "Fusion360Gallery",
            "path": FUSION_ROOT / row["step_file"],
            "sha256": row["step_sha256"],
            "bytes": int(row["step_bytes"]),
        }
    require(len(anchors) == 528, f"external anchor inventory has {len(anchors)} rows, not 528")
    return anchors


def verify_candidate_ledger(root: Path, anchors: dict[str, dict[str, Any]]) -> None:
    ledger = read_csv(root / "manual_candidate_ledger_50_to_28.csv")
    summary = load(root / "manual_candidate_ledger_50_to_28_summary.json")
    require(len(ledger) == 50 == summary["total_candidates"], "manual candidate total is not 50")
    selected = [row for row in ledger if row["selected"] == "True"]
    excluded = [row for row in ledger if row["selected"] == "False"]
    require(len(selected) == 28 == summary["selected"], "manual selected total is not 28")
    require(len(excluded) == 22 == summary["excluded"], "manual excluded total is not 22")
    manual_ids = {corpus_id for corpus_id in anchors if not corpus_id.startswith("F")}
    require({row["corpus_id"] for row in selected} == manual_ids,
            "candidate ledger selected IDs differ from external receipt anchors")

    archive = root / summary["nist_archive"]
    require(sha256(archive) == summary["nist_archive_sha256"], "NIST archive hash mismatch")
    with zipfile.ZipFile(archive) as stream:
        nist_members = {name for name in stream.namelist() if name.lower().endswith(".stp")}
    ledger_nist = {row["candidate_locator"] for row in ledger if row["source_group"] == "NIST"}
    require(nist_members == ledger_nist, "candidate ledger does not enumerate all NIST STEP members")

    reason_counts = Counter(row["decision_reason"] for row in ledger)
    require(dict(sorted(reason_counts.items())) == summary["decision_reason_counts"],
            "candidate decision-reason summary mismatch")
    group_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in ledger:
        counter = group_counts[row["source_group"]]
        counter["candidates"] += 1
        counter["selected"] += int(row["selected"] == "True")
        counter["excluded"] += int(row["selected"] == "False")
    require({group: dict(counts) for group, counts in sorted(group_counts.items())}
            == summary["group_counts"], "candidate group-count summary mismatch")


def verify_input_anchors(records: list[dict[str, Any]], anchors: dict[str, dict[str, Any]],
                         label: str, expected_ids: set[str] | None = None,
                         hash_cache: dict[Path, str] | None = None) -> None:
    mapped = record_map(records, label)
    if expected_ids is None:
        expected_ids = set(anchors)
    require(set(mapped) == expected_ids, f"{label} ID set differs from independently built anchors")
    cache = hash_cache if hash_cache is not None else {}
    for corpus_id, row in mapped.items():
        anchor = anchors[corpus_id]
        path = Path(anchor["path"])
        require(path.is_file(), f"anchored input file missing: {corpus_id}: {path}")
        require(path.stat().st_size == anchor["bytes"], f"anchored byte size mismatch: {corpus_id}")
        if path not in cache:
            cache[path] = sha256(path)
        observed = cache[path]
        require(observed == anchor["sha256"], f"external receipt/manifest hash mismatch: {corpus_id}")
        require(row.get("expected_sha256") == anchor["sha256"],
                f"{label} expected hash is not externally anchored: {corpus_id}")
        require(row.get("observed_sha256", anchor["sha256"]) == observed,
                f"{label} observed hash mismatch: {corpus_id}")
        require(Path(row["input_path"]).name == path.name,
                f"{label} input filename differs from external anchor: {corpus_id}")
        require(row["source_group"] == anchor["source_group"],
                f"{label} source group differs from external anchor: {corpus_id}")


def verify_occt(preflight_dir: Path, preflight: dict[str, Any]) -> dict[str, dict[str, Any]]:
    require(preflight["schema"] == "topic4.occt_step_preflight.aggregate.v1", "OCCT schema mismatch")
    records = preflight["records"]
    require(len(records) == 528 == preflight["total"], "OCCT total mismatch")
    verify_individual_files(preflight_dir, records, "OCCT")
    require(all(row["tool_ok"] for row in records), "OCCT contains a tool failure")
    require(sum(row["validity"]["shape_valid"] for row in records) == 528, "OCCT full-shape validity mismatch")
    require(sum(row["validity"]["solid_subset_valid"] for row in records) == 528, "OCCT solid validity mismatch")
    require(sum(row["brep_closure"]["all_shells_closed"] for row in records) == 528, "OCCT closure mismatch")
    require(sum(row["brep_volume"]["all_solids_positive"] for row in records) == 528, "OCCT positive-volume mismatch")
    require(sum(row["mesh"]["watertight"] for row in records) == 520, "OCCT watertight count mismatch")
    require(sum(row["mesh"]["edge_manifold"] for row in records) == 519, "OCCT manifold count mismatch")
    require(sum(row["admission"]["dual_contouring_candidate"] for row in records) == 511, "OCCT admission count mismatch")

    reasons = Counter(row["rejection_reason"] for row in records)
    require(dict(reasons) == preflight["reason_counts"]
            == {"admitted": 511, "mesh_boundary": 8, "mesh_nonmanifold": 9},
            "OCCT rejection reasons are not row-recomputed")
    group_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in records:
        group_counts[row["source_group"]]["total"] += 1
        group_counts[row["source_group"]][row["rejection_reason"]] += 1
    require({group: dict(counts) for group, counts in sorted(group_counts.items())}
            == preflight["group_counts"], "OCCT group counts are not row-recomputed")
    return record_map(records, "OCCT")


def verify_freecad(freecad_dir: Path, freecad: dict[str, Any]) -> dict[str, dict[str, Any]]:
    require(freecad["schema"] == "topic4.freecad_step_preflight.aggregate.v1", "FreeCAD schema mismatch")
    records = freecad["records"]
    require(len(records) == 528 == freecad["total"], "FreeCAD total mismatch")
    verify_individual_files(freecad_dir, records, "FreeCAD")
    recomputed = {
        "tool_ok": sum(bool(row.get("tool_ok")) for row in records),
        "shape_valid": sum(bool(row.get("validity", {}).get("shape_valid")) for row in records),
        "all_solids_valid": sum(bool(row.get("validity", {}).get("all_solids_valid")) for row in records),
        "all_shells_closed": sum(bool(row.get("brep_closure", {}).get("all_shells_closed")) for row in records),
        "all_solids_closed": sum(bool(row.get("brep_closure", {}).get("all_solids_closed")) for row in records),
        "all_solids_positive": sum(bool(row.get("brep_volume", {}).get("all_solids_positive")) for row in records),
    }
    for key, value in recomputed.items():
        require(value == freecad[key] == 528, f"FreeCAD {key} is not row-recomputed")
    versions = Counter(
        (row["kernel"]["frontend_version"], row["kernel"]["version"])
        for row in records if row.get("tool_ok")
    )
    expected_versions = [
        {"freecad": key[0], "opencascade": key[1], "count": count}
        for key, count in sorted(versions.items())
    ]
    require(freecad["version_counts"] == expected_versions
            == [{"count": 528, "freecad": "1.1.1", "opencascade": "7.8.1"}],
            "FreeCAD version counts are not row-recomputed")
    failures = Counter(row.get("failure_stage", "") or "none" for row in records)
    require(dict(failures) == freecad["failure_stages"] == {"none": 528},
            "FreeCAD failure stages are not row-recomputed")
    group_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in records:
        counter = group_counts[row["source_group"]]
        counter["total"] += 1
        counter["tool_ok"] += int(bool(row.get("tool_ok")))
        counter["shape_valid"] += int(bool(row.get("validity", {}).get("shape_valid")))
        counter["all_shells_closed"] += int(bool(row.get("brep_closure", {}).get("all_shells_closed")))
        counter["all_solids_positive"] += int(bool(row.get("brep_volume", {}).get("all_solids_positive")))
    require({group: dict(counts) for group, counts in sorted(group_counts.items())}
            == freecad["group_counts"], "FreeCAD group counts are not row-recomputed")
    return record_map(records, "FreeCAD")


def derive_crosscheck_row(corpus_id: str, primary: dict[str, Any], check: dict[str, Any],
                          volume_tolerance: float, bbox_tolerance: float) -> dict[str, Any]:
    categorical_match = all([
        bool(primary.get("tool_ok")) == bool(check.get("tool_ok")),
        bool(primary["validity"]["shape_valid"]) == bool(check["validity"]["shape_valid"]),
        bool(primary["validity"]["solid_subset_valid"]) == bool(check["validity"]["all_solids_valid"]),
        bool(primary["brep_closure"]["all_shells_closed"]) == bool(check["brep_closure"]["all_shells_closed"]),
        bool(primary["brep_volume"]["all_solids_positive"]) == bool(check["brep_volume"]["all_solids_positive"]),
    ])
    topology_match = all(
        primary["topology"][key] == check["topology"][key]
        for key in ["solids", "shells", "faces"]
    )
    auxiliary_shell_match = all(
        primary["full_shape_auxiliary"][key] == check["full_shape_auxiliary"][key]
        for key in ["shells", "closed_shells", "open_shells", "non_solid_shells"]
    )
    volume_difference = relative_difference(
        primary["brep_volume"]["total_signed"], check["brep_volume"]["total_signed"]
    )
    bbox_difference = relative_difference(primary["bbox"]["diagonal"], check["bbox"]["diagonal"])
    return {
        "corpus_id": corpus_id,
        "source_group": primary["source_group"],
        "categorical_match": categorical_match,
        "topology_match": topology_match,
        "auxiliary_shell_match": auxiliary_shell_match,
        "volume_relative_difference": volume_difference,
        "volume_within_tolerance": volume_difference <= volume_tolerance,
        "bbox_relative_difference": bbox_difference,
        "bbox_within_tolerance": bbox_difference <= bbox_tolerance,
        "comparison_pass": categorical_match and topology_match and auxiliary_shell_match
        and volume_difference <= volume_tolerance,
    }


def verify_crosscheck(crosscheck: dict[str, Any], occt_records: dict[str, dict[str, Any]],
                      freecad_records: dict[str, dict[str, Any]]) -> None:
    require(crosscheck["schema"] == "topic4.brep_crosscheck.aggregate.v1", "crosscheck schema mismatch")
    rows = crosscheck["rows"]
    mapped = record_map(rows, "crosscheck")
    require(len(rows) == 528 == crosscheck["total"], "crosscheck total mismatch")
    require(set(mapped) == set(occt_records) == set(freecad_records), "crosscheck ID set mismatch")
    volume_tolerance = float(crosscheck["tolerances"]["volume_relative"])
    bbox_tolerance = float(crosscheck["tolerances"]["bbox_diagonal_relative"])
    derived_rows = []
    for corpus_id, stored in mapped.items():
        derived = derive_crosscheck_row(
            corpus_id, occt_records[corpus_id], freecad_records[corpus_id],
            volume_tolerance, bbox_tolerance,
        )
        for key in ["source_group", "categorical_match", "topology_match",
                    "auxiliary_shell_match", "volume_within_tolerance",
                    "bbox_within_tolerance", "comparison_pass"]:
            require(stored.get(key) == derived[key], f"crosscheck row mismatch {corpus_id}.{key}")
        require_close(stored["volume_relative_difference"], derived["volume_relative_difference"],
                      f"crosscheck volume difference {corpus_id}")
        require_close(stored["bbox_relative_difference"], derived["bbox_relative_difference"],
                      f"crosscheck bbox difference {corpus_id}")
        require(stored.get("occt_solids") == occt_records[corpus_id]["topology"]["solids"],
                f"crosscheck OCCT solid count mismatch {corpus_id}")
        require(stored.get("freecad_solids") == freecad_records[corpus_id]["topology"]["solids"],
                f"crosscheck FreeCAD solid count mismatch {corpus_id}")
        require_close(stored["occt_volume"], occt_records[corpus_id]["brep_volume"]["total_signed"],
                      f"crosscheck OCCT volume mismatch {corpus_id}")
        require_close(stored["freecad_volume"], freecad_records[corpus_id]["brep_volume"]["total_signed"],
                      f"crosscheck FreeCAD volume mismatch {corpus_id}")
        derived_rows.append(derived)

    count_fields = {
        "comparison_pass": "comparison_pass",
        "categorical_match": "categorical_match",
        "topology_match": "topology_match",
        "auxiliary_shell_match": "auxiliary_shell_match",
        "volume_within_tolerance": "volume_within_tolerance",
        "bbox_within_diagnostic_tolerance": "bbox_within_tolerance",
    }
    for aggregate_key, row_key in count_fields.items():
        count = sum(bool(row[row_key]) for row in derived_rows)
        require(crosscheck[aggregate_key] == count,
                f"crosscheck {aggregate_key} is not row-recomputed")
    require(crosscheck["comparison_pass"] == 528, "crosscheck complete gate is not 528/528")

    volumes = [row["volume_relative_difference"] for row in derived_rows]
    bboxes = [row["bbox_relative_difference"] for row in derived_rows]
    max_volume_row = max(derived_rows, key=lambda row: row["volume_relative_difference"])
    max_bbox_row = max(derived_rows, key=lambda row: row["bbox_relative_difference"])
    volume_summary = crosscheck["volume_relative_difference"]
    bbox_summary = crosscheck["bbox_relative_difference"]
    for key, value in {
        "median": sorted(volumes)[len(volumes) // 2] if len(volumes) % 2 else
        0.5 * (sorted(volumes)[len(volumes)//2-1] + sorted(volumes)[len(volumes)//2]),
        "p95": ceiling_quantile(volumes, 0.95),
        "p99": ceiling_quantile(volumes, 0.99),
        "maximum": max_volume_row["volume_relative_difference"],
    }.items():
        require_close(volume_summary[key], value, f"crosscheck volume summary {key}")
    require(volume_summary["maximum_corpus_id"] == max_volume_row["corpus_id"] == "C04",
            "crosscheck maximum-volume model mismatch")
    require(volume_summary["nonzero_above_1e-12"] == sum(value > 1.0e-12 for value in volumes) == 4,
            "crosscheck nonzero-volume count mismatch")
    require_close(volume_summary["maximum"], 5.985833581736324e-05,
                  "published maximum volume difference", rel_tol=1.0e-13)

    for key, value in {
        "median": sorted(bboxes)[len(bboxes) // 2] if len(bboxes) % 2 else
        0.5 * (sorted(bboxes)[len(bboxes)//2-1] + sorted(bboxes)[len(bboxes)//2]),
        "p95": ceiling_quantile(bboxes, 0.95),
        "p99": ceiling_quantile(bboxes, 0.99),
        "maximum": max_bbox_row["bbox_relative_difference"],
    }.items():
        require_close(bbox_summary[key], value, f"crosscheck bbox summary {key}")
    require(bbox_summary["maximum_corpus_id"] == max_bbox_row["corpus_id"] == "F021",
            "crosscheck maximum-bbox model mismatch")
    require_close(bbox_summary["maximum"], 0.0012392315742341712,
                  "published maximum bbox difference", rel_tol=1.0e-13)


def verify_dc(dc_dir: Path, preflight_records: dict[str, dict[str, Any]], dc: dict[str, Any],
              rescue: dict[str, Any]) -> set[str]:
    require(dc["schema"] == "topic4.regular_grid_dc.aggregate.v1", "DC schema mismatch")
    records = dc["records"]
    require(len(records) == 122 == dc["selected_models"], "DC selected total mismatch")
    verify_individual_files(dc_dir, records, "DC")
    mapped = record_map(records, "DC")

    admitted = [row for row in preflight_records.values() if row["rejection_reason"] == "admitted"]
    manual = sorted((row for row in admitted if row["source_group"] != "Fusion360Gallery"),
                    key=lambda row: row["corpus_id"])
    fusion = sorted((row for row in admitted if row["source_group"] == "Fusion360Gallery"),
                    key=lambda row: int(row["corpus_id"][1:]))[:100]
    expected_ids = {row["corpus_id"] for row in manual + fusion}
    require(len(manual) == 22 and len(fusion) == 100 and set(mapped) == expected_ids,
            "DC model selection is not reproduced from preflight rows")

    completed = [row for row in records if row.get("tool_ok")]
    failed = [row for row in records if not row.get("tool_ok")]
    require(len(completed) == dc["completed_models"] == 118, "DC completion count mismatch")
    require(len(failed) == dc["failed_models"] == 4, "DC failure count mismatch")
    failure_ids = {"F034", "F054", "F083", "F085"}
    require({row["corpus_id"] for row in failed} == failure_ids, "DC failure ID set mismatch")
    require(all(row["runner_status"] == "no_zero_crossing_at_resolution" for row in failed),
            "DC failure reason mismatch")
    require(all(row["resolution"] == (24 if row["source_group"] == "Fusion360Gallery" else 32)
                for row in records), "DC frozen resolution policy mismatch")
    require(all(row.get("expected_sha256") == preflight_records[row["corpus_id"]]["expected_sha256"]
                for row in records), "DC hashes differ from preflight records")

    active = sum(row["qef"]["active_cells"] for row in completed)
    certified = sum(row["qef"]["certified_oracle_diagnostic"] for row in completed)
    violations = sum(row["qef"]["bound_violations"] for row in completed)
    boundary_edges = sum(row["baseline_mesh"]["boundary_edges"] for row in completed)
    nonmanifold_edges = sum(row["baseline_mesh"]["nonmanifold_edges"] for row in completed)
    require(active == dc["totals"]["active_cells"] == 162216, "DC active-cell total mismatch")
    require(certified == dc["totals"]["oracle_diagnostic_certified"] == 36866,
            "DC oracle-diagnostic count mismatch")
    require(violations == dc["totals"]["bound_violations"] == 0, "DC bound violations are nonzero")
    require(boundary_edges == dc["totals"]["baseline_boundary_edges"] == 0,
            "DC boundary-edge total mismatch")
    require(nonmanifold_edges == dc["totals"]["baseline_nonmanifold_edges"] == 2632,
            "DC nonmanifold-edge total mismatch")
    require(sum(row["baseline_mesh"]["degenerate_triangles"] for row in completed) == 0,
            "DC degenerate triangle count is nonzero")
    require(sum(row["baseline_mesh"]["nonmanifold_edges"] > 0 for row in completed) == 79,
            "DC affected-model count mismatch")
    require(all(row["baseline_mesh"]["signed_volume"] > 0 for row in completed),
            "DC contains a nonpositive baseline mesh volume")
    pooled = certified / active
    require_close(dc["totals"]["pooled_oracle_diagnostic_coverage"], pooled,
                  "DC pooled coverage")
    require_close(pooled, 0.22726488139271095, "published pooled coverage", rel_tol=1.0e-14)

    distribution_specs = {
        "model_coverage_median": ([row["qef"]["coverage"] for row in completed], 0.5,
                                  0.13762612146513),
        "model_coverage_p05": ([row["qef"]["coverage"] for row in completed], 0.05, 0.0),
        "model_coverage_p95": ([row["qef"]["coverage"] for row in completed], 0.95,
                               0.6344328747688166),
        "baseline_mean_surface_error_cell_units_median":
            ([row["baseline_mesh"]["mean_abs_surface_distance_cell_units"] for row in completed],
             0.5, 0.0462479643467759),
        "baseline_max_surface_error_cell_units_p95":
            ([row["baseline_mesh"]["max_abs_surface_distance_cell_units"] for row in completed],
             0.95, 0.7987360281207849),
        "model_median_normal_angle_error_degrees_median":
            ([row["qef"]["median_normal_angle_error_degrees"] for row in completed],
             0.5, 3.72324354210701),
        "model_p95_normal_angle_error_degrees_p95":
            ([row["qef"]["p95_normal_angle_error_degrees"] for row in completed],
             0.95, 74.28975908034599),
    }
    for key, (values, q, published) in distribution_specs.items():
        recomputed = linear_quantile(values, q)
        require_close(dc["distributions"][key], recomputed, f"DC distribution {key}")
        require_close(recomputed, published, f"published DC distribution {key}", rel_tol=1.0e-13)

    fallback_values = sorted(
        row["contract_fallback_mesh"]["mean_abs_surface_distance_cell_units"]
        for row in completed
    )
    fallback_upper_median = fallback_values[len(fallback_values) // 2]
    require_close(fallback_upper_median, 0.28415216688748,
                  "published fallback upper median", rel_tol=1.0e-13)

    expected_group_coverage = {
        "3D ContentCentral": (11522, 4156, 0.36070126714112133),
        "3Dfindit": (7037, 915, 0.130027000142106),
        "Fusion360Gallery": (99516, 25402, 0.25525543631174885),
        "GrabCAD": (15125, 2218, 0.14664462809917356),
        "NIST": (20387, 3010, 0.14764310590081914),
        "TraceParts": (8629, 1165, 0.13500985050411404),
    }
    group_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in records:
        group_counts[row["source_group"]]["total"] += 1
        group_counts[row["source_group"]][row["runner_status"]] += 1
    require({group: dict(counts) for group, counts in sorted(group_counts.items())}
            == dc["group_counts"], "DC group status counts are not row-recomputed")
    for group, (expected_active, expected_certified, expected_coverage) in expected_group_coverage.items():
        rows = [row for row in completed if row["source_group"] == group]
        group_active = sum(row["qef"]["active_cells"] for row in rows)
        group_certified = sum(row["qef"]["certified_oracle_diagnostic"] for row in rows)
        require(group_active == expected_active and group_certified == expected_certified,
                f"DC group totals mismatch: {group}")
        require_close(group_certified / group_active, expected_coverage,
                      f"published group coverage {group}", rel_tol=1.0e-13)

    require(rescue["schema"] == "topic4.regular_grid_dc.resolution_rescue.v1",
            "rescue schema mismatch")
    rescue_map = record_map(rescue["models"], "rescue")
    require(set(rescue_map) == failure_ids, "rescue ID set mismatch")
    expected_first_success = {"F034": 48, "F054": 32, "F083": 48, "F085": 32}
    for corpus_id, row in rescue_map.items():
        require(row["main_resolution"] == 24, f"rescue main resolution mismatch: {corpus_id}")
        successes = [attempt for attempt in row["attempts"] if attempt["tool_ok"]]
        require(bool(successes), f"rescue has no successful attempt: {corpus_id}")
        require(successes[0]["resolution"] == expected_first_success[corpus_id],
                f"rescue first-success resolution mismatch: {corpus_id}")
        require(all(attempt["resolution"] in {32, 48, 64, 96} for attempt in row["attempts"]),
                f"rescue contains an unplanned resolution: {corpus_id}")
    return expected_ids


def verify_admission_table(root: Path, preflight: dict[str, Any]) -> None:
    rows = read_csv(root / "preflight_admission_by_source.csv")
    mapped = {row["source_group"]: row for row in rows}
    require(set(mapped) == set(preflight["group_counts"]), "admission table source groups mismatch")
    for group, counts in preflight["group_counts"].items():
        row = mapped[group]
        expected = {
            "total": counts.get("total", 0),
            "admitted": counts.get("admitted", 0),
            "mesh_boundary": counts.get("mesh_boundary", 0),
            "mesh_nonmanifold": counts.get("mesh_nonmanifold", 0),
        }
        expected["rejected"] = expected["total"] - expected["admitted"]
        for key, value in expected.items():
            require(int(row[key]) == value, f"admission table mismatch: {group}.{key}")
    manual_rejected = sum(int(row["rejected"]) for group, row in mapped.items()
                          if group != "Fusion360Gallery")
    fusion_rejected = int(mapped["Fusion360Gallery"]["rejected"])
    require(manual_rejected == 6 and fusion_rejected == 11,
            "admission rejection split is not manual=6, Fusion=11")


def verify_manifest(root: Path) -> None:
    manifest_path = root / "RESULTS_MANIFEST_2026-08-10.sha256"
    entries: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        require(relative not in entries, f"duplicate manifest path: {relative}")
        entries[relative] = expected
    required = {
        "occt_preflight/CMakeLists.txt",
        "occt_preflight/occt_step_preflight.cpp",
        "dual_contouring/CMakeLists.txt",
        "dual_contouring/regular_grid_dc.cpp",
        "run_occt_preflight.py",
        "freecad_preflight/freecad_step_smoke.py",
        "run_freecad_preflight.py",
        "compare_brep_preflights.py",
        "run_dual_contouring.py",
        "run_resolution_rescue.py",
        "build_manual_candidate_ledger.py",
        "summarize_real_cad_results.py",
        "verify_real_cad_results.py",
        "test_verifier_tamper_detection.py",
        "selected_model_manifest_v1.csv",
        "fusion360_sample500_manifest_2026-08-10.csv",
        "traceparts_receipt_2026-08-10.csv",
        "3dfindit_receipt_2026-08-10.csv",
        "3dcontentcentral_receipt_2026-08-10.csv",
        "grabcad_receipt_2026-08-10.csv",
        "corpus_v1/manifests/download_receipts.csv",
        "manual_candidate_ledger_50_to_28.csv",
        "manual_candidate_ledger_50_to_28_summary.json",
        "preflight_admission_by_source.csv",
        "results/occt_preflight_v1/occt_preflight_aggregate.json",
        "results/occt_preflight_v1/occt_preflight_rows.csv",
        "results/freecad_preflight_v3/freecad_preflight_aggregate.json",
        "results/freecad_preflight_v3/freecad_preflight_rows.csv",
        "results/brep_crosscheck_v1/brep_crosscheck_aggregate.json",
        "results/brep_crosscheck_v1/brep_crosscheck_rows.csv",
        "results/dual_contouring_v3/dual_contouring_aggregate.json",
        "results/dual_contouring_v3/dual_contouring_rows.csv",
        "results/dual_contouring_v3/resolution_rescue_diagnostic.json",
        "REAL_CAD_EXPERIMENT_REPORT_2026-08-10.md",
        "real_cad_experiment_section_v1.tex",
        "fig_real_cad_experiment_v1.svg",
    }
    missing = sorted(required - set(entries))
    require(not missing, f"manifest omits required paths: {missing}")
    for relative, expected in entries.items():
        path = root / relative
        require(path.is_file(), f"manifest file missing: {relative}")
        require(sha256(path) == expected, f"manifest hash mismatch: {relative}")


def verify(root: Path = HERE, *, check_link: bool = True, check_manifest: bool = True,
           check_inputs: bool = True) -> None:
    preflight_dir = root / "results/occt_preflight_v1"
    freecad_dir = root / "results/freecad_preflight_v3"
    crosscheck_dir = root / "results/brep_crosscheck_v1"
    dc_dir = root / "results/dual_contouring_v3"
    preflight = load(preflight_dir / "occt_preflight_aggregate.json")
    freecad = load(freecad_dir / "freecad_preflight_aggregate.json")
    crosscheck = load(crosscheck_dir / "brep_crosscheck_aggregate.json")
    dc = load(dc_dir / "dual_contouring_aggregate.json")
    rescue = load(dc_dir / "resolution_rescue_diagnostic.json")

    occt_records = verify_occt(preflight_dir, preflight)
    freecad_records = verify_freecad(freecad_dir, freecad)
    verify_crosscheck(crosscheck, occt_records, freecad_records)
    dc_ids = verify_dc(dc_dir, occt_records, dc, rescue)
    verify_admission_table(root, preflight)

    if check_inputs:
        anchors = build_external_input_anchors(root)
        verify_candidate_ledger(root, anchors)
        hash_cache: dict[Path, str] = {}
        verify_input_anchors(preflight["records"], anchors, "OCCT", hash_cache=hash_cache)
        verify_input_anchors(freecad["records"], anchors, "FreeCAD", hash_cache=hash_cache)
        verify_input_anchors(dc["records"], anchors, "DC", expected_ids=dc_ids, hash_cache=hash_cache)

    if check_link:
        linked = subprocess.run(
            ["otool", "-L", str(root / "occt_preflight/build/occt_step_preflight")],
            capture_output=True, text=True, check=True,
        ).stdout
        require("DRAW" not in linked.upper(), "OCCT preflight binary links a DRAW library")
    if check_manifest:
        verify_manifest(root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-only", action="store_true",
        help="verify frozen row-level results and arithmetic without locally acquired STEP inputs",
    )
    args = parser.parse_args()
    verify(check_inputs=not args.artifact_only, check_link=not args.artifact_only)
    mode = "artifact-only" if args.artifact_only else "full-input"
    print(
        f"PASS ({mode}): 528 OCCT rows; "
        "528 FreeCAD rows; 528 derived cross-check rows; 122 DC rows; "
        "continuous manuscript metrics; rescue resolutions; required manifest files"
        + ("" if args.artifact_only else "; external input anchors; 50-to-28 ledger")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
