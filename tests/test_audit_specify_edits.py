from harness.audit_specify_edits import summarize_edit_diff


def _plane(fid: int, area: float, centroid: list[float], direction: list[float]) -> dict:
    return {
        "id": fid,
        "kind": "plane",
        "area": area,
        "centroid": centroid,
        "direction": direction,
        "radius": None,
    }


def test_summarize_edit_diff_detects_noop():
    analysis = {
        "faces": [
            _plane(0, 100.0, [0.0, 0.0, 10.0], [0.0, 0.0, 1.0]),
            _plane(1, 100.0, [0.0, 0.0, 0.0], [0.0, 0.0, -1.0]),
        ]
    }
    report = {
        "verdict": "ok",
        "features": [],
        "measures": {
            "old": {"volume": 1000.0, "area": 600.0},
            "new": {"volume": 1000.0, "area": 600.0},
        },
    }

    summary = summarize_edit_diff(analysis, analysis, report)

    assert "verdict" not in summary
    assert summary["no_op"] is True
    assert summary["classification"] == "no_op"
    assert summary["unchanged_faces"] == 2


def test_summarize_edit_diff_catches_tangential_move_at_zero_volume_delta():
    old_analysis = {
        "faces": [
            {
                "id": 0,
                "kind": "cylinder",
                "area": 157.08,
                "centroid": [10.0, 0.0, 5.0],
                "direction": [0.0, 0.0, 1.0],
                "radius": 2.5,
            }
        ]
    }
    new_analysis = {
        "faces": [
            {
                "id": 0,
                "kind": "cylinder",
                "area": 157.08,
                "centroid": [18.0, 0.0, 5.0],
                "direction": [0.0, 0.0, 1.0],
                "radius": 2.5,
            }
        ]
    }
    report = {
        "verdict": "ok",
        "features": [{"id": "holes:0", "status": "adapted", "moved": [8.0, 0.0, 0.0]}],
        "measures": {
            "old": {"volume": 900.0, "area": 550.0},
            "new": {"volume": 900.0, "area": 550.0},
        },
    }

    summary = summarize_edit_diff(old_analysis, new_analysis, report)

    assert summary["no_op"] is False
    assert summary["classification"] == "feature_edit"
    assert summary["adapted_count"] == 1
    assert summary["orphaned_count"] == 0
    assert summary["unchanged_faces"] == 0


def test_summarize_edit_diff_catches_bare_planar_offset_and_orphaned_collateral():
    old_analysis = {
        "faces": [
            _plane(0, 100.0, [0.0, 0.0, 10.0], [0.0, 0.0, 1.0]),
            _plane(1, 100.0, [0.0, 0.0, 0.0], [0.0, 0.0, -1.0]),
        ]
    }
    new_analysis = {
        "faces": [
            _plane(0, 100.0, [0.0, 0.0, 15.0], [0.0, 0.0, 1.0]),
            _plane(1, 100.0, [0.0, 0.0, 0.0], [0.0, 0.0, -1.0]),
        ]
    }
    bare_report = {
        "verdict": "ok",
        "features": [],
        "measures": {
            "old": {"volume": 1000.0, "area": 600.0},
            "new": {"volume": 1500.0, "area": 800.0},
        },
    }

    bare_summary = summarize_edit_diff(old_analysis, new_analysis, bare_report)
    assert bare_summary["no_op"] is False
    assert bare_summary["classification"] == "analytic_face_edit"
    assert bare_summary["unchanged_faces"] == 1
    assert bare_summary["changed_new_faces"] == 1

    collateral_report = dict(
        bare_report,
        features=[
            {"id": "fillets:0", "status": "orphaned"},
            {"id": "fillets:1", "status": "orphaned"},
        ],
    )
    collateral_summary = summarize_edit_diff(
        old_analysis, new_analysis, collateral_report
    )
    assert collateral_summary["classification"] == "feature_edit"
    assert collateral_summary["orphaned_count"] == 2
    assert collateral_summary["orphaned_ids"] == ["fillets:0", "fillets:1"]
