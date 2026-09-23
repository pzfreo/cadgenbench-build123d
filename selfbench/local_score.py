"""Score a sweep's outputs against self-bench ground truth, locally.

This runs the *real* CADGenBench shape-similarity metric
(``cadgenbench.eval.shape_similarity.compare_step_files``) — the same code the
leaderboard Space runs — against ground truth we authored ourselves. It aligns
each candidate to GT (ICP) then reports ``shape_surface_distance_f1``,
``shape_volume_iou`` and their mean ``shape_similarity_score`` in [0, 1].

    uv run --with 'cadgenbench @ git+https://github.com/huggingface/cadgenbench.git@8ae1432' \
        python selfbench/local_score.py results/<run_name>

For each ``results/<run>/<id>/output.step`` with a matching
``selfbench/fixtures/<id>/ground_truth.step`` it prints one row and writes a
JSON summary to ``selfbench/scores/<run>.json``.

Editing fixtures (those with an ``input.step``) are scored the way the Space
scores edits: the shape axis is renormalised against the no-op baseline
``b = shape_similarity(input.step, GT)`` as ``max(0, (s - b) / (1 - b))``, and
``edit_score = (0.6 * s_renorm + 0.1 * topo_match) / 0.7`` — the Space's
``0.6/0.3/0.1`` weights renormalised over the axes we have (self-bench
fixtures carry no interface regions). A no-op scores ~0.14 on this scale.

NOTE: renders are intentionally skipped (no ``*_renders_dir``) — the headless
VTK/OSMesa stack the Space uses for preview PNGs isn't needed to compute the
score, and omitting it avoids a segfault on plain installs.

Honest-use: this is a dev-set predictor. A gain here is a hypothesis to confirm
on the real HF Space, not a reportable number. See selfbench/README.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO / "selfbench" / "fixtures"


def _edit_scores(out_step: Path, gt: Path, input_step: Path, sim: float) -> dict:
    from cadgenbench.eval.shape_similarity import compare_step_files
    from cadgenbench.eval.topo_match import topo_match

    base = compare_step_files(str(input_step), str(gt), align=True)
    b = base.scores["shape_similarity_score"]
    renorm = max(0.0, (sim - b) / (1 - b)) if b < 1 else 0.0
    topo = topo_match(out_step, gt).score
    return {"baseline_shape_similarity": b, "shape_similarity_renormalized": renorm,
            "topo_match": topo, "edit_score": (0.6 * renorm + 0.1 * topo) / 0.7}


def score_run(run_dir: Path) -> dict:
    from cadgenbench.eval.shape_similarity import compare_step_files

    rows: list[dict] = []
    for out_step in sorted(run_dir.glob("*/output.step")):
        fid = out_step.parent.name
        gt = FIXTURES_DIR / fid / "ground_truth.step"
        if not gt.is_file():
            print(f"{fid:>6}  SKIP  no ground_truth.step (not a self-bench fixture)")
            continue
        r = compare_step_files(str(out_step), str(gt), align=True)
        scores = {k: v for k, v in r.scores.items()}
        rows.append({"id": fid, "scores": scores, "errors": r.metric_errors,
                     "alignment_rmse": r.alignment_rmse})
        sim = scores.get("shape_similarity_score")
        f1 = scores.get("shape_surface_distance_f1")
        iou = scores.get("shape_volume_iou")
        edit = ""
        input_step = FIXTURES_DIR / fid / "input.step"
        if input_step.is_file():
            e = _edit_scores(out_step, gt, input_step, sim)
            rows[-1]["edit"] = e
            edit = (f"  EDIT={e['edit_score']:.4f}  renorm={e['shape_similarity_renormalized']:.4f}"
                    f"  noop_sim={e['baseline_shape_similarity']:.4f}  topo={e['topo_match']:.4f}")
        print(f"{fid:>6}  score={sim:.4f}  surfF1={f1:.4f}  volIoU={iou:.4f}" + edit
              + (f"  errors={r.metric_errors}" if r.metric_errors else ""))

    gen = [r["scores"].get("shape_similarity_score", 0.0) for r in rows if "edit" not in r]
    edits = [r["edit"]["edit_score"] for r in rows if "edit" in r]
    mean = sum(gen) / len(gen) if gen else 0.0
    edit_mean = sum(edits) / len(edits) if edits else None
    if gen:
        print(f"\nmean shape_similarity_score over {len(gen)} generation fixture(s): {mean:.4f}")
    if edits:
        print(f"mean edit_score over {len(edits)} editing fixture(s): {edit_mean:.4f}")
    return {"run": run_dir.name, "mean_shape_similarity_score": mean,
            "mean_edit_score": edit_mean, "fixtures": rows}


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: local_score.py results/<run_name>", file=sys.stderr)
        return 1
    run_dir = Path(argv[0]).resolve()
    if not run_dir.is_dir():
        print(f"not a directory: {run_dir}", file=sys.stderr)
        return 1
    summary = score_run(run_dir)
    out = REPO / "selfbench" / "scores"
    out.mkdir(exist_ok=True)
    dest = out / f"{run_dir.name}.json"
    dest.write_text(json.dumps(summary, indent=2))
    print(f"wrote {dest.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
