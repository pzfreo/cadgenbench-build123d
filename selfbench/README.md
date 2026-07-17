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

By default the drawing is rendered from the STEP by draftwright's feature
recognition. A `part.py` may instead define an **`author()` hook** returning a
configured draftwright `Sheet`; then the fixture *declares* its own drawing
(which features and dimensions appear, stated vs. inferred) with recognition
skipped. Use this when recognition drops or crowds a callout, or to control the
dimensioning deliberately (see below). See `fixtures/9011/part.py`.

## Inference-load fixtures

The current 9001–9010 use clean, direct dimensioning — the very "optimism bias"
flagged above — and GPT-5.5 saturates them (~0.9–1.0). Real CADGenBench drawings
are the opposite: fixture 125's title block literally reads *"deliberately
departs from drafting standards."* Their difficulty is largely in **reading and
inference** — derived, chained, off-datum, angular dimensions — not exotic
geometry.

**9011 / 9013** isolate that axis. Both are the *same* shelled cover; only the
drawing differs. 9011 states the body height directly (38); 9013 states the
overall height (48) and boss height (10) and forces the reader to derive the
body (48 − 10). On identical geometry GPT-5.5 scores **~0.93** on 9011 and
**~0.63** on 9013 (n=3 each, near-zero variance) — it mis-reads the overall as
the body height and builds a 58-tall part. A ~0.30 swing from one dimensioning
change: the lever for a discriminating dev set is dimension *inference*, not
geometry. Author such fixtures with the declarative `author()` hook, which lets
you choose exactly which dimensions are stated vs. inferred.

**9016** applies the same inference class to a differently proportioned
pedestal housing. Its drawing states the overall and boss heights, requiring
the body height to be derived while the deep underside cavity and visible roof
are reconciled. It provides an independent check against overfitting the
specific values and geometry of 9011/9013.

**9017** extends that check to a three-level height chain: overall height minus
base flange and top boss. It adds a deep cored body, counterbored central bore,
and four-hole rectangular mounting pattern so success requires both correct
dimension inference and a substantially richer feature inventory.

## Notes

- The scorer pins `cadgenbench` to the commit the Space used at build time
  (`8ae1432`); bump it to track the Space. It installs cleanly on Linux (the
  `CLAUDE.md` "won't build locally" gotcha is macOS-only).
- Renders are skipped in scoring (no headless VTK/OSMesa needed); only the
  geometry metric runs.
