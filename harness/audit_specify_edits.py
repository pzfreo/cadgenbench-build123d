#!/usr/bin/env python3
"""Audit CADGenBench editing outputs with specify-core (no OCCT or Hausdorff).

Compares each fixture's ``input.step`` against ``results/<run>/<id>/output.step``
using ``specify-core``'s pure-Rust STEP loader, feature recogniser, and revision
differ plus an analytic face-signature multiset diff (covering bare planar wall
offsets and pure tangential feature slides without mesh tessellation).

Usage:
  uv run --with specify-core python harness/audit_specify_edits.py \\
      work/<run> results/<run>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def _round_seq(values: Any, digits: int = 2) -> tuple[float, ...] | None:
    if not isinstance(values, (list, tuple)):
        return None
    return tuple(round(float(v) + 0.0, digits) for v in values)


def face_signature(face: dict[str, Any]) -> tuple[Any, ...]:
    """Canonical analytic signature for fast, index-independent face matching."""
    radius = face.get("radius")
    return (
        str(face.get("kind", "")),
        round(float(face.get("area", 0.0)), 2),
        _round_seq(face.get("centroid"), 2),
        _round_seq(face.get("direction"), 3),
        round(float(radius), 3) if radius is not None else None,
    )


def summarize_edit_diff(
    old_analysis: dict[str, Any],
    new_analysis: dict[str, Any],
    diff_report: dict[str, Any],
    *,
    same_bytes: bool = False,
) -> dict[str, Any]:
    """Classify an edit candidate from specify-core analyse() + diff() payloads."""
    # Never forward specify-core's PMI migration verdict ("ok") as CAD correctness.
    features = [
        item
        for item in diff_report.get("features", [])
        if isinstance(item, dict)
    ]
    adapted = [f for f in features if f.get("status") == "adapted"]
    orphaned = [f for f in features if f.get("status") == "orphaned"]
    added = [f for f in features if f.get("status") == "new"]

    old_faces = old_analysis.get("faces", [])
    new_faces = new_analysis.get("faces", [])
    old_counts = Counter(face_signature(f) for f in old_faces if isinstance(f, dict))
    new_counts = Counter(face_signature(f) for f in new_faces if isinstance(f, dict))
    unchanged_faces = sum((old_counts & new_counts).values())
    old_only_faces = sum((old_counts - new_counts).values())
    new_only_faces = sum((new_counts - old_counts).values())

    measures = diff_report.get("measures", {})
    old_m = measures.get("old", {}) if isinstance(measures, dict) else {}
    new_m = measures.get("new", {}) if isinstance(measures, dict) else {}
    vol_delta = float(new_m.get("volume", 0.0)) - float(old_m.get("volume", 0.0))
    area_delta = float(new_m.get("area", 0.0)) - float(old_m.get("area", 0.0))

    has_feature_delta = bool(adapted or orphaned or added)
    has_measure_delta = abs(vol_delta) > 1e-3 or abs(area_delta) > 1e-2
    has_face_delta = old_only_faces > 0 or new_only_faces > 0

    is_noop = same_bytes or (
        not has_feature_delta and not has_measure_delta and not has_face_delta
    )
    if is_noop:
        classification = "no_op"
    elif adapted or orphaned or added:
        classification = "feature_edit"
    else:
        # Pure bare-plane offset or unrecognised freeform edit caught by face signatures.
        classification = "analytic_face_edit"

    return {
        "classification": classification,
        "no_op": is_noop,
        "same_bytes": same_bytes,
        "volume_delta": round(vol_delta, 4),
        "area_delta": round(area_delta, 4),
        "old_face_count": len(old_faces),
        "new_face_count": len(new_faces),
        "unchanged_faces": unchanged_faces,
        "changed_old_faces": old_only_faces,
        "changed_new_faces": new_only_faces,
        "adapted_count": len(adapted),
        "orphaned_count": len(orphaned),
        "added_count": len(added),
        "adapted_ids": [str(f.get("id", "")) for f in adapted],
        "orphaned_ids": [str(f.get("id", "")) for f in orphaned],
        "added_ids": [str(f.get("id", "")) for f in added],
    }


def audit_pair(input_step: Path, output_step: Path) -> dict[str, Any]:
    """Run specify-core on one (input.step, output.step) pair."""
    from specify_core import api

    old_bytes = input_step.read_bytes()
    new_bytes = output_step.read_bytes()
    if hashlib.sha256(old_bytes).digest() == hashlib.sha256(new_bytes).digest():
        loaded = api.load(input_step)
        analysis = api.analyse(loaded)
        return summarize_edit_diff(
            analysis,
            analysis,
            {"features": [], "measures": {"old": {}, "new": {}}},
            same_bytes=True,
        )

    old_part = api.load(input_step)
    new_part = api.load(output_step)
    old_analysis = api.analyse(old_part)
    new_analysis = api.analyse(new_part)
    diff_report = api.diff(old_part, new_part)
    return summarize_edit_diff(old_analysis, new_analysis, diff_report)


def _find_input_step(inputs_root: Path, fid: str) -> Path | None:
    for candidate in (
        inputs_root / f"{fid}_in" / "input.step",
        inputs_root / fid / "input.step",
    ):
        if candidate.is_file():
            return candidate
    return None


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("inputs_dir", help="work/<run> (holding <id>_in/input.step) or fixture dir")
    ap.add_argument("results_dir", help="results/<run> directory holding <id>/output.step")
    ap.add_argument("--json-out", default=None, help="optional path to write full JSON report")
    args = ap.parse_args()

    inputs_root = Path(args.inputs_dir)
    results_root = Path(args.results_dir)
    if not results_root.is_dir():
        print(f"not a directory: {results_root}", file=sys.stderr)
        return 2

    report: dict[str, Any] = {"run": results_root.name, "fixtures": {}}
    fixtures = sorted(
        (d for d in results_root.iterdir() if d.is_dir() and d.name.isdigit()),
        key=lambda d: int(d.name),
    )

    for fdir in fixtures:
        fid = fdir.name
        in_step = _find_input_step(inputs_root, fid)
        if in_step is None:
            continue  # generation fixture
        out_step = fdir / "output.step"
        if not out_step.is_file():
            report["fixtures"][fid] = {"classification": "missing", "no_op": False}
            continue
        summary = audit_pair(in_step, out_step)
        report["fixtures"][fid] = summary
        print(
            f"[{fid}] {summary['classification']:18s} "
            f"dV={summary['volume_delta']:+10.2f} "
            f"adapted={summary['adapted_count']} "
            f"orphaned={summary['orphaned_count']} "
            f"added={summary['added_count']} "
            f"unchanged_faces={summary['unchanged_faces']}/{summary['old_face_count']}"
        )

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
