import json
from pathlib import Path

from harness.audit_agy_recognition import audit


def _event(name: str, parameters: dict) -> str:
    return json.dumps(
        {
            "event": "step_update",
            "step_update": {
                "state": "DONE",
                "step_type": "tool",
                "tool_name": "call_mcp_tool",
                "tool_info": {
                    "parameters": {
                        "ToolName": name,
                        "Arguments": parameters,
                    }
                },
            },
        }
    )


def test_audit_accepts_same_turn_recognition_and_resolution(tmp_path: Path):
    stream = tmp_path / "stream.jsonl"
    stream.write_text(
        "\n".join(
            [
                _event("import_cad_file", {"name": "part", "path": "input.step"}),
                _event("recognise_features", {"object_name": "part"}),
                _event("recognise_features", {"object_name": "part", "families": "holes"}),
                _event(
                    "execute",
                    {"code": "faces = recognition_faces('@feature[r1/holes/0]')"},
                ),
            ]
        )
    )

    result = audit(stream)

    assert result["recognition_completed"] is True
    assert result["resolution_requirement_satisfied"] is True
    assert result["recognition_faces_calls"] == 1


def test_audit_rejects_targeted_recognition_without_resolution(tmp_path: Path):
    stream = tmp_path / "stream.jsonl"
    stream.write_text(
        "\n".join(
            [
                _event("import_cad_file", {"name": "part", "path": "input.step"}),
                _event("recognise_features", {"object_name": "part"}),
                _event("recognise_features", {"object_name": "part", "families": "bosses"}),
            ]
        )
    )

    result = audit(stream)

    assert result["recognition_completed"] is True
    assert result["resolution_requirement_satisfied"] is False


def test_audit_supports_direct_agy_tool_names(tmp_path: Path):
    stream = tmp_path / "stream.jsonl"
    direct = {
        "event": "step_update",
        "step_update": {
            "state": "DONE",
            "step_type": "tool",
            "tool_name": "mcp_build123d_recognise_features",
            "tool_info": {
                "name": "mcp_build123d_recognise_features",
                "parameters": {"object_name": "part"},
            },
        },
    }
    stream.write_text(
        "\n".join(
            [
                _event("import_cad_file", {"name": "part", "path": "input.step"}),
                json.dumps(direct),
            ]
        )
    )

    result = audit(stream)

    assert result["recognition_completed"] is True
    assert result["inventory_calls"] == 1
