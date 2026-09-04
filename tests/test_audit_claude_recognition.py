import json
from pathlib import Path

from harness.audit_claude_recognition import audit


def _assistant(tool_id: str, name: str, arguments: dict) -> str:
    return json.dumps(
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": tool_id,
                        "name": f"mcp__build123d__{name}",
                        "input": arguments,
                    }
                ]
            },
        }
    )


def _result(tool_id: str, payload: dict, *, is_error: bool = False) -> str:
    return json.dumps(
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "is_error": is_error,
                        "content": json.dumps({"result": json.dumps(payload)}),
                    }
                ]
            },
        }
    )


def test_audit_accepts_inventory_targeted_hit_and_resolution(tmp_path: Path):
    stream = tmp_path / "stream.jsonl"
    stream.write_text(
        "\n".join(
            [
                _assistant(
                    "import", "import_cad_file", {"path": "input.step", "name": "part"}
                ),
                _assistant("inventory", "recognise_features", {"object_name": "part"}),
                _result("inventory", {"inventory": {"holes": 1}, "returned": 0}),
                _assistant(
                    "targeted",
                    "recognise_features",
                    {"object_name": "part", "families": "holes"},
                ),
                _result("targeted", {"matched": 1, "returned": 1}),
                _assistant(
                    "execute",
                    "execute",
                    {"code": "faces = recognition_faces('@feature[r1/holes/0]')"},
                ),
            ]
        )
    )

    result = audit(stream)

    assert result["recognition_completed"] is True
    assert result["targeted_hits"] == 1
    assert result["recognition_faces_calls"] == 1
    assert result["resolution_requirement_satisfied"] is True


def test_audit_rejects_targeted_hit_without_resolution(tmp_path: Path):
    stream = tmp_path / "stream.jsonl"
    stream.write_text(
        "\n".join(
            [
                _assistant(
                    "import", "import_cad_file", {"path": "input.step", "name": "part"}
                ),
                _assistant("inventory", "recognise_features", {"object_name": "part"}),
                _assistant(
                    "targeted",
                    "recognise_features",
                    {"object_name": "part", "families": ["bosses"]},
                ),
                _result("targeted", {"matched": 1, "returned": 1}),
            ]
        )
    )

    result = audit(stream)

    assert result["recognition_completed"] is True
    assert result["resolution_requirement_satisfied"] is False


def test_audit_accepts_explicit_targeted_miss_without_resolution(tmp_path: Path):
    stream = tmp_path / "stream.jsonl"
    stream.write_text(
        "\n".join(
            [
                _assistant(
                    "import", "import_cad_file", {"path": "input.step", "name": "part"}
                ),
                _assistant("inventory", "recognise_features", {"object_name": "part"}),
                _assistant(
                    "targeted",
                    "recognise_features",
                    {"object_name": "part", "families": "pockets"},
                ),
                _result("targeted", {"matched": 0, "returned": 0, "features": []}),
            ]
        )
    )

    result = audit(stream)

    assert result["targeted_misses"] == 1
    assert result["resolution_requirement_satisfied"] is True


def test_audit_requires_import_before_inventory(tmp_path: Path):
    stream = tmp_path / "stream.jsonl"
    stream.write_text(
        "\n".join(
            [
                _assistant("inventory", "recognise_features", {"object_name": "part"}),
                _assistant(
                    "import", "import_cad_file", {"path": "input.step", "name": "part"}
                ),
            ]
        )
    )

    assert audit(stream)["recognition_completed"] is False


def test_audit_requires_targeted_call_after_inventory(tmp_path: Path):
    stream = tmp_path / "stream.jsonl"
    stream.write_text(
        "\n".join(
            [
                _assistant(
                    "import", "import_cad_file", {"path": "input.step", "name": "part"}
                ),
                _assistant("inventory", "recognise_features", {"object_name": "part"}),
            ]
        )
    )

    assert audit(stream)["recognition_completed"] is False
