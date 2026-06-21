# cadgenbench-build123d

A reproducible pipeline for submitting to [**CADGenBench**](https://huggingface.co/spaces/HuggingAI4Engineering/CADGenBench)
using **Claude Code + [build123d-mcp](https://github.com/pzfreo/build123d-mcp)**
(a gate-equipped build123d MCP server) as the CAD stack.

CADGenBench is tool-agnostic: a submission is just one `output.step` per fixture,
scored behind a hard validity gate. This repo drives an agent to produce those
STEPs, collects them into the submission layout, and validity-checks them before
you upload.

## What the system is (and what's measured)

The benchmark scores a **system**, not a bare model. Here the system is:

> **Claude (Opus 4.8) + build123d-mcp + the generic prompts in `harness/`.**

That whole pipeline is the contribution. When you publish a result, disclose all
three parts.

## Honest-use rules (read before reporting a number)

CADGenBench's ground truth is **held out**, so you can't fit to it — good. To stay
on the right side of the line:

- **Prompts are generic, per task-type** (`prompt_generation.txt`,
  `prompt_editing.txt`). Never encode a specific fixture's answer in a prompt —
  that's doing the CAD yourself, not measuring the AI.
- **Don't report on fixtures you tuned on.** The prompts were developed against
  the `splits/dev.txt` fixtures; report only on `splits/test.txt` (disjoint).
- The editing prompt banks the **unchanged import** as a valid fallback (the
  benchmark scores a no-op as a baseline). That's insurance, not the goal — the
  prompt still attempts the real edit. Don't farm the baseline.

## Prerequisites

- `claude` (Claude Code), `uvx`, and `uv` on `PATH`.
- The run installs `build123d-mcp@latest` from PyPI by default. To test an
  unreleased build, pass a spec as the 4th arg (see below).

## Run a sweep

```bash
# one fixture id per line; work/ and results/ are created per run name
./run_sweep.sh splits/test.txt opus48-v1
```

Each fixture is fetched, run through `harness/run_fixture.sh` (generation or
editing is auto-detected from the fixture's files), and the result copied to
`results/opus48-v1/<id>/output.step`. Per-fixture failures don't abort the sweep.

Test an unreleased build123d-mcp (e.g. local `main`):

```bash
./run_sweep.sh splits/test.txt opus48-main \
    claude-opus-4-8 "build123d-mcp @ file:///path/to/build123d-mcp"
```

Watch one fixture live (in another terminal):

```bash
tail -n0 -f work/opus48-v1/<id>_run/stream.jsonl \
    | python3 harness/stream_filter.py work/opus48-v1/<id>_run
```

## Validate / package the submission

```bash
uv run --python 3.12 --with build123d-mcp --with trimesh --with scipy \
    python package_submission.py results/opus48-v1 --zip \
    --official-sanity-check /path/to/cadgenbench/sanity_check_submission.py
```

This writes `results/opus48-v1/manifest.json` (present / missing / gate verdict
per fixture) and, with `--zip`, the upload-ready `submit/opus48-v1.zip` — the
full fixture set with an auto-generated `meta.json` whose notes are stamped from
the run's provenance (model + resolved build123d-mcp version + the
cadgenbench-build123d commit that pins the prompts), `agent_url` set to that
commit's permalink, and `submitter_name`/`submission_name` = `pzfreo` (override
with `--submitter` / `--name`). The validity gate runs `exact=True` so large
parts aren't false-flagged.

The **build123d-mcp gate is only a proxy** — the authoritative gate is
CADGenBench's own `sanity_check_submission.py`; always run it (via
`--official-sanity-check`) before uploading `submit/opus48-v1.zip` on the
[leaderboard Space](https://huggingface.co/spaces/HuggingAI4Engineering/CADGenBench).

## Layout

```
harness/
  fetch_fixture.py        pull a fixture's public inputs from the HF dataset
  run_fixture.sh          drive claude -p + build123d-mcp; auto-selects the prompt
  prompt_generation.txt   drawing -> solid (checkpoint-first, validity-as-invariant)
  prompt_editing.txt      STEP + change request -> edited solid
  stream_filter.py        live readable log of a single run
  score.py                local proxy: validity gate (+ indicative shape score vs GT)
run_sweep.sh              batch a fixture list into results/<run>/<id>/output.step
package_submission.py     validity-check the layout + write manifest.json
splits/                   dev (tuned-on) vs test (reportable) fixture lists
```

## Scoring caveat

`harness/score.py` reports the build123d-mcp validity gate and, if you supply a
ground-truth STEP, an **indicative** shape score (uniform-scale + rigid-align
search → surface-distance F1). It is **not** the official CADGenBench metric
(which forbids scale search and blends F1 with volume-IoU, plus interface and
topology terms). Use it for relative comparison only.
