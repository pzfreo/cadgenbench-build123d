# selfbench — a local, owned-ground-truth dev set

CADGenBench's ground truth is held out, so the only correctness signal is a slow
upload to the HF Space. This is a **local geometric-accuracy signal** you own:
author a part, render a CADGenBench-style drawing from it with
[draftwright](https://github.com/pzfreo/draftwright), run the *same* pipeline
(`run_sweep.sh`), then score the output against your own ground truth using the
**real CADGenBench metric** (`cadgenbench.eval.shape_similarity`) — the same code
the Space runs.

```
author part.py (own GT) → draftwright drawing → run_sweep.sh → output.step → local_score.py
```

## ⚠️ Honest-use — this is a dev set, not a result

Treat selfbench exactly like `splits/dev.txt`: **tune on it, never report its
numbers, never let a fixture's specifics leak into the generic prompts.** A gain
here is a *hypothesis* to confirm on the real HF Space, not a reportable score.
Two biases to keep in mind:

- **Optimism.** draftwright renders clean, complete drawings from perfect solids;
  real fixtures can be hand-dimensioned, ambiguous, or missing views. Absolute
  scores here run high, and variant *rankings* may not fully transfer.
- **It's a predictor.** The metric is faithful; the fixture distribution is ours.
  The Space is the authority.

## Layout

```
selfbench/
  fixtures/<id>/part.py   the ONLY committed source per fixture: defines a
                          module-level `part` (build123d solid) = ground truth,
                          and optional `title` for the drawing title block.
  selfbench.txt           fixture-id list for run_sweep.sh (ids >= 9000 to avoid
                          colliding with real fixtures 101-150 / 201+).
  author_fixtures.py      part.py -> ground_truth.step + input.png + description.yaml
  local_score.py          score results/<run>/ vs ground truth (real cgb metric)
```

`ground_truth.step`, `input.png`, `description.yaml` are **generated** (gitignored)
— `part.py` is the source of truth; regenerate the rest any time.

## Use

```bash
# 1. Author fixtures (build GT + drawing + description) from part.py
uv run --with build123d --with draftwright --with pymupdf \
    python selfbench/author_fixtures.py            # all, or pass an id

# 2. Run the pipeline — identical to a real sweep; fetch_fixture.py serves
#    selfbench/fixtures/<id> locally (drawing + description only, never the GT)
./run_sweep.sh selfbench/selfbench.txt selfbench-v1 claude-opus-4-8 build123d-mcp==0.3.72 1

# 3. Score outputs against your ground truth with the real CADGenBench metric
uv run --with 'cadgenbench @ git+https://github.com/huggingface/cadgenbench.git@8ae1432' \
    python selfbench/local_score.py results/selfbench-v1
```

`local_score.py` reports `shape_surface_distance_f1`, `shape_volume_iou`, and
their mean `shape_similarity_score` in `[0, 1]` per fixture (candidate is
ICP-aligned to GT first, so pose doesn't matter), plus a mean, and writes
`selfbench/scores/<run>.json`.

## Adding a fixture

Drop a new `selfbench/fixtures/<id>/part.py` (id >= 9000) defining `part` (and
optionally `title`), add the id to `selfbench.txt`, re-run `author_fixtures.py`.
Keep parts unambiguous from the drawing alone — you're testing the agent's CAD,
not its guesswork.

## Notes

- The scorer pins `cadgenbench` to the commit the Space used at build time
  (`8ae1432`); bump it to track the Space. It installs cleanly on Linux (the
  `CLAUDE.md` "won't build locally" gotcha is macOS-only).
- Renders are skipped in scoring (no headless VTK/OSMesa needed); only the
  geometry metric runs.
