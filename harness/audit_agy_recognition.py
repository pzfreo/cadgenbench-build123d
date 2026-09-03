#!/usr/bin/env python3
"""Audit execution-phase use of build123d recognition in an Agy JSON stream."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def _tool_name(step: dict) -> str:
    info = step.get("tool_info", {})
    parameters = info.get("parameters", {}) or {}
    name = parameters.get("ToolName") or step.get("tool_name") or info.get("name") or ""
    return name.removeprefix("mcp_build123d_")


def _arguments(step: dict) -> dict:
    parameters = step.get("tool_info", {}).get("parameters", {}) or {}
    return parameters.get("Arguments", parameters) or {}


def audit(path: Path) -> dict:
    recognition_calls = 0
    inventory_calls = 0
    targeted_calls = 0
    face_resolution_calls = 0
    imported_part = False
    recognition_after_import = False

    for raw_line in path.read_text(errors="replace").splitlines():
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        step = event.get("step_update", {})
        if step.get("state") != "DONE" or step.get("step_type") != "tool":
            continue

        name = _tool_name(step)
        arguments = _arguments(step)
        if name == "import_cad_file" and arguments.get("name") == "part":
            imported_part = True
        elif name == "recognise_features":
            recognition_calls += 1
            recognition_after_import = recognition_after_import or imported_part
            families = arguments.get("families")
            if families is None or families == "" or families == []:
                inventory_calls += 1
            else:
                targeted_calls += 1
        elif name == "execute":
            code = str(arguments.get("code", ""))
            face_resolution_calls += len(re.findall(r"\brecognition_faces\s*\(", code))

    recognition_completed = imported_part and recognition_after_import and inventory_calls > 0
    # A target-specific query must be followed by an attempted resolver call.
    # If the inventory itself failed and no target query was possible, retain a
    # truthful audit without forcing the agent to invent an unsupported family.
    resolution_requirement_satisfied = targeted_calls == 0 or face_resolution_calls > 0
    return {
        "imported_part": imported_part,
        "recognition_calls": recognition_calls,
        "inventory_calls": inventory_calls,
        "targeted_calls": targeted_calls,
        "recognition_faces_calls": face_resolution_calls,
        "recognition_completed": recognition_completed,
        "resolution_requirement_satisfied": resolution_requirement_satisfied,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {Path(sys.argv[0]).name} <agy-stream.jsonl>", file=sys.stderr)
        return 2
    print(json.dumps(audit(Path(sys.argv[1])), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
