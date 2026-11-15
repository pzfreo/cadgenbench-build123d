import json
from pathlib import Path

from harness.audit_agy_recognition import audit


def _event(name: str, parameters: dict, output: str = "") -> str:
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
                    },
                    "output": output,
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
                _event(
                    "recognise_features",
                    {"object_name": "part", "families": "holes"},
                    json.dumps({"matched": 1, "returned": 1}),
                ),
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
                _event(
                    "recognise_features",
                    {"object_name": "part", "families": "bosses"},
                    json.dumps({"matched": 1, "returned": 1}),
                ),
            ]
        )
    )

    result = audit(stream)

    assert result["recognition_completed"] is True
    assert result["resolution_requirement_satisfied"] is False


def test_audit_accepts_targeted_recogniser_miss_without_resolution(tmp_path: Path):
    stream = tmp_path / "stream.jsonl"
    stream.write_text(
        "\n".join(
            [
                _event("import_cad_file", {"name": "part", "path": "input.step"}),
                _event("recognise_features", {"object_name": "part"}),
                _event(
                    "recognise_features",
                    {"object_name": "part", "families": "pockets"},
                    json.dumps({"matched": 0, "returned": 0, "features": []}),
                ),
            ]
        )
    )

    result = audit(stream)

    assert result["targeted_misses"] == 1
    assert result["resolution_requirement_satisfied"] is True


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


def test_audit_accepts_specify_inspect_features_select_faces_and_diff_step(
    tmp_path: Path,
):
    stream = tmp_path / "stream.jsonl"
    stream.write_text(
        "\n".join(
            [
                _event("inspect_features", {"target": "input.step"}),
                _event(
                    "inspect_features",
                    {"target": "input.step", "families": ["bosses", "holes"]},
                    json.dumps({"features": [{"id": "bosses:0"}]}),
                ),
                _event(
                    "inspect_features",
                    {"target": "input.step", "feature_ids": ["bosses:0"]},
                ),
                _event(
                    "execute",
                    {"code": "faces = select_faces(part, kind='cylinder', radius=32.5)"},
                ),
                _event("diff_step", {"old": "input.step", "new": "edited"}),
            ]
        )
    )

    result = audit(stream)

    assert result["recognition_completed"] is True
    assert result["inventory_calls"] == 1
    assert result["targeted_calls"] == 1
    assert result["detail_calls"] == 1
    assert result["targeted_hits"] == 1
    assert result["select_faces_calls"] == 1
    assert result["diff_step_calls"] == 1
    assert result["resolution_requirement_satisfied"] is True
