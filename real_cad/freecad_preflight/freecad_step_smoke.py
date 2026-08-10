"""One-file FreeCAD STEP/B-rep preflight worker.

The outer runner launches this script in a fresh FreeCADCmd process for every
model.  The worker deliberately performs no healing, sewing, or shape repair.
"""

import json
import math
import os
import time
import traceback

import FreeCAD
import Part


input_path = os.environ["TOPIC4_STEP_INPUT"]
output_path = os.environ["TOPIC4_FREECAD_OUTPUT"]
corpus_id = os.environ.get("TOPIC4_CORPUS_ID", "")
source_group = os.environ.get("TOPIC4_SOURCE_GROUP", "")
started = time.monotonic()


def finite_float(value):
    result = float(value)
    return result if math.isfinite(result) else None


try:
    shape = Part.read(input_path)
    solids = list(shape.Solids)
    full_shape_shells = list(shape.Shells)
    solid_shells = [shell for solid in solids for shell in solid.Shells]
    solid_subset = Part.makeCompound(solids)
    volumes = [finite_float(solid.Volume) for solid in solids]
    bbox = solid_subset.BoundBox

    result = {
        "schema": "topic4.freecad_step_preflight.v1",
        "corpus_id": corpus_id,
        "source_group": source_group,
        "input_path": input_path,
        "tool_ok": True,
        "failure_stage": "",
        "kernel": {
            "frontend": "FreeCAD",
            "frontend_version": ".".join(FreeCAD.Version()[:3]),
            "name": "OpenCascade",
            "version": getattr(Part, "OCC_VERSION", "not exposed"),
        },
        "no_healing_or_sewing": True,
        "shape_type": shape.ShapeType,
        "is_null": shape.isNull(),
        "validity": {
            "shape_valid": shape.isValid(),
            "all_solids_valid": bool(solids) and all(solid.isValid() for solid in solids),
        },
        "topology": {
            "solids": len(solids),
            "shells": len(solid_shells),
            "faces": len(shape.Faces),
            "edges": len(shape.Edges),
            "vertices": len(shape.Vertexes),
        },
        "solid_subset_topology": {
            "faces": sum(len(solid.Faces) for solid in solids),
            "edges": sum(len(solid.Edges) for solid in solids),
            "vertices": sum(len(solid.Vertexes) for solid in solids),
        },
        "brep_closure": {
            "closed_shells": sum(shell.isClosed() for shell in solid_shells),
            "open_shells": sum(not shell.isClosed() for shell in solid_shells),
            "all_shells_closed": bool(solid_shells) and all(
                shell.isClosed() for shell in solid_shells
            ),
            "all_solids_closed": bool(solids) and all(solid.isClosed() for solid in solids),
        },
        "full_shape_auxiliary": {
            "shells": len(full_shape_shells),
            "closed_shells": sum(shell.isClosed() for shell in full_shape_shells),
            "open_shells": sum(not shell.isClosed() for shell in full_shape_shells),
            "non_solid_shells": max(0, len(full_shape_shells) - len(solid_shells)),
        },
        "brep_volume": {
            "per_solid": volumes,
            "total_signed": finite_float(sum(volume for volume in volumes if volume is not None)),
            "positive_solids": sum(volume is not None and volume > 0.0 for volume in volumes),
            "nonpositive_solids": sum(volume is None or volume <= 0.0 for volume in volumes),
            "all_solids_positive": bool(volumes) and all(
                volume is not None and volume > 0.0 for volume in volumes
            ),
        },
        "bbox": {
            "min": [finite_float(bbox.XMin), finite_float(bbox.YMin), finite_float(bbox.ZMin)],
            "max": [finite_float(bbox.XMax), finite_float(bbox.YMax), finite_float(bbox.ZMax)],
            "diagonal": finite_float(bbox.DiagonalLength),
        },
        "elapsed_seconds": time.monotonic() - started,
    }
except Exception as error:  # retain import and kernel failures in the denominator
    result = {
        "schema": "topic4.freecad_step_preflight.v1",
        "corpus_id": corpus_id,
        "source_group": source_group,
        "input_path": input_path,
        "tool_ok": False,
        "failure_stage": "freecad_import_or_audit",
        "error_type": type(error).__name__,
        "error": str(error),
        "traceback": traceback.format_exc(),
        "kernel": {
            "frontend": "FreeCAD",
            "frontend_version": ".".join(FreeCAD.Version()[:3]),
            "name": "OpenCascade",
            "version": getattr(Part, "OCC_VERSION", "not exposed"),
        },
        "no_healing_or_sewing": True,
        "elapsed_seconds": time.monotonic() - started,
    }

with open(output_path, "w", encoding="utf-8") as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2)

print("TOPIC4_FREECAD_PREFLIGHT=" + json.dumps(result, ensure_ascii=False))
