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
        print(f"{fid:>6}  score={sim:.4f}  surfF1={f1:.4f}  volIoU={iou:.4f}"
              + (f"  errors={r.metric_errors}" if r.metric_errors else ""))

    sims = [r["scores"].get("shape_similarity_score", 0.0) for r in rows]
    mean = sum(sims) / len(sims) if sims else 0.0
    print(f"\nmean shape_similarity_score over {len(rows)} fixture(s): {mean:.4f}")
    return {"run": run_dir.name, "mean_shape_similarity_score": mean, "fixtures": rows}


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
