#!/usr/bin/env python3
"""Audit execution-phase build123d recognition in a Claude Code JSON stream."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


def _tool_name(block: dict[str, Any]) -> str:
    return str(block.get("name", "")).removeprefix("mcp__build123d__")


def _result_payload(content: Any) -> dict[str, Any] | None:
    """Decode Claude's tool result, including the MCP {"result": "<json>"} wrapper."""
    if isinstance(content, list):
        content = "\n".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    if not isinstance(content, str):
        return None
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    nested = payload.get("result")
    if isinstance(nested, str):
        try:
            decoded = json.loads(nested)
        except json.JSONDecodeError:
            return payload
        if isinstance(decoded, dict):
            return decoded
    return payload


def _is_step_path_target(arguments: dict[str, Any]) -> bool:
    target = str(arguments.get("target", "")).strip().lower()
    return target.endswith((".step", ".stp"))


def _has_result_hits(result: dict[str, Any]) -> bool:
    if result.get("returned", 0) > 0:
        return True
    features = result.get("features")
    if isinstance(features, list) and len(features) > 0:
        return True
    if isinstance(features, dict) and any(bool(v) for v in features.values()):
        return True
    return False


def audit(path: Path) -> dict[str, Any]:
    recognition_calls = 0
    inventory_calls = 0
    targeted_calls = 0
    detail_calls = 0
    targeted_hits = 0
    targeted_misses = 0
    targeted_errors = 0
    targeted_unknown = 0
    select_faces_calls = 0
    legacy_recognition_faces_calls = 0
    diff_step_calls = 0
    imported_part = False
    recognition_after_import = False
    pending: dict[str, tuple[str, dict[str, Any]]] = {}

    for raw_line in path.read_text(errors="replace").splitlines():
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        message = event.get("message", {})
        content = message.get("content", []) if isinstance(message, dict) else []
        if not isinstance(content, list):
            continue

        if event.get("type") == "assistant":
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                name = _tool_name(block)
                arguments = block.get("input", {}) or {}
                if not isinstance(arguments, dict):
                    arguments = {}
                tool_id = block.get("id")
                if isinstance(tool_id, str):
                    pending[tool_id] = (name, arguments)

                if name == "import_cad_file" and arguments.get("name") == "part":
                    imported_part = True
                elif name in {"inspect_features", "recognise_features"}:
                    recognition_calls += 1
                    valid_source = imported_part or (
                        name == "inspect_features" and _is_step_path_target(arguments)
                    )
                    recognition_after_import = recognition_after_import or valid_source
                    families = arguments.get("families")
                    feature_ids = arguments.get("feature_ids")
                    has_families = families not in (None, "", [])
                    has_feature_ids = feature_ids not in (None, "", [])
                    if has_feature_ids:
                        detail_calls += 1
                    if not has_families and not has_feature_ids:
                        inventory_calls += 1
                    elif has_families:
                        targeted_calls += 1
                elif name == "diff_step":
                    diff_step_calls += 1
                elif name == "execute":
                    code = str(arguments.get("code", ""))
                    if re.search(r"\bimport_step\s*\(", code):
                        imported_part = True
                    select_faces_calls += len(re.findall(r"\bselect_faces\s*\(", code))
                    legacy_recognition_faces_calls += len(
                        re.findall(r"\brecognition_faces\s*\(", code)
                    )

        elif event.get("type") == "user":
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_result":
                    continue
                call = pending.get(str(block.get("tool_use_id", "")))
                if call is None or call[0] not in {"inspect_features", "recognise_features"}:
                    continue
                families = call[1].get("families")
                if families in (None, "", []):
                    continue
                if block.get("is_error"):
                    targeted_errors += 1
                    continue
                result = _result_payload(block.get("content"))
                if result is None:
                    targeted_unknown += 1
                elif result.get("error"):
                    targeted_errors += 1
                elif _has_result_hits(result):
                    targeted_hits += 1
                else:
                    targeted_misses += 1

    face_resolution_calls = select_faces_calls + legacy_recognition_faces_calls
    recognition_completed = (
        recognition_after_import
        and inventory_calls > 0
        and targeted_calls > 0
    )
    resolution_required = targeted_hits > 0 or targeted_unknown > 0
    resolution_requirement_satisfied = (
        not resolution_required or face_resolution_calls > 0
    )
    return {
        "imported_part": imported_part,
        "recognition_calls": recognition_calls,
        "inventory_calls": inventory_calls,
        "targeted_calls": targeted_calls,
        "detail_calls": detail_calls,
        "targeted_hits": targeted_hits,
        "targeted_misses": targeted_misses,
        "targeted_errors": targeted_errors,
        "targeted_unknown": targeted_unknown,
        "select_faces_calls": select_faces_calls,
        "recognition_faces_calls": legacy_recognition_faces_calls,
        "diff_step_calls": diff_step_calls,
        "recognition_completed": recognition_completed,
        "resolution_requirement_satisfied": resolution_requirement_satisfied,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {Path(sys.argv[0]).name} <claude-stream.jsonl>", file=sys.stderr)
        return 2
    print(json.dumps(audit(Path(sys.argv[1])), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
