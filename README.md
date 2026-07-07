# cadgenbench-build123d

A reproducible pipeline for submitting to [**CADGenBench**](https://huggingface.co/spaces/HuggingAI4Engineering/CADGenBench)
using **Claude Code + [build123d-mcp](https://github.com/pzfreo/build123d-mcp)**
(a gate-equipped build123d MCP server) as the CAD stack.

CADGenBench is tool-agnostic: a submission is just one `output.step` per fixture,
scored behind a hard validity gate. This repo drives an agent to produce those
STEPs, collects them into the submission layout, and validity-checks them before
you upload.

This file is the source of truth for the pipeline. If you're an AI agent working
in this repo, also read `CLAUDE.md` — it layers behavioral rules and hard-won
gotchas on top of what's documented here; it should never contradict this file.

## What the system is (and what's measured)

The benchmark scores a **system**, not a bare model. Here the system is:

> **Claude (or Codex/GPT-5.5) + build123d-mcp (a pinned version) + the generic
> prompts in `harness/`.**

That whole pipeline is the contribution. When you publish a result, disclose all
three parts, including the exact `build123d-mcp` version.

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

- `claude` (Claude Code), `uvx`, and `uv` on `PATH`. For the Codex/GPT-5.5 path,
  a logged-in `codex` CLI (`codex login`) too.

## Run a sweep

```bash
./run_sweep.sh <fixtures_file> <run_name> [model] [mcp_spec] [jobs] [exec_timeout]

# one fixture id per line; work/ and results/ are created per run name
./run_sweep.sh splits/test.txt opus48-v1 claude-opus-4-8 build123d-mcp==0.3.72 5 240
```

`model` defaults to `claude-opus-4-8` (`claude-*` routes to Claude Code; any
other id, e.g. `gpt-5.5`, routes to the Codex CLI driver — see below). `mcp_spec`
defaults to `build123d-mcp@latest` (unpinned). `jobs` (fixtures run concurrently;
each has its own work dir, so parallel runs never collide) defaults to `4` —
lower it if you hit API rate limits (429s). `exec_timeout` (seconds, passed to
both drivers as `--exec-timeout`) defaults to each server's own default
(currently 120s); Codex's own client-side `tool_timeout_sec` is fixed at 600s in
`run_fixture_codex.sh`, so keep this under that or Codex gives up first. Each
fixture is fetched, run through `harness/run_fixture.sh` (generation or editing
is auto-detected from the fixture's files), and the result copied to
`results/<run_name>/<id>/output.step`. Per-fixture failures don't abort the sweep.

**Pin `mcp_spec` to an exact version** (`build123d-mcp==0.3.72`) for any run you
intend to report or compare against another run — the unpinned default is only
for quick, throwaway exploration. A moving spec breaks reproducibility: two runs
of "the same" sweep can silently use different build123d-mcp code.

Test an unreleased build (e.g. a local branch or `main`):

```bash
./run_sweep.sh splits/test.txt opus48-main \
    claude-opus-4-8 "build123d-mcp @ file:///path/to/build123d-mcp" 5
```

**Commit prompt/harness changes before the sweep.** The sweep auto-generates
`results/<run_name>/run_meta.json` (model, resolved `reasoning_effort`, the
pinned `mcp_spec`, and the exact git commit of this repo) — the provenance
`package_submission.py` later consumes to stamp the submission's `meta.json`. If
the working tree is dirty at sweep time, `run_meta.json` records `git_dirty:
true` and a `uncommitted.patch` is saved alongside it, but a clean commit is what
makes a run's provenance actually reproducible — don't leave it to the patch file.

Never drive fixtures with a hand-rolled loop over `run_fixture*.sh` directly — it
writes `work/<id>_run/` with **no** `run_meta.json` and forces manual staging and
a hand-authored `run_meta` later, which is error-prone and easy to get wrong.
Always go through `run_sweep.sh`.

Watch one fixture live (in another terminal):

```bash
tail -n0 -f work/opus48-v1/<id>_run/stream.jsonl \
    | python3 harness/stream_filter.py work/opus48-v1/<id>_run
```

## Second system: Codex / GPT-5.5

The same pipeline can be driven by the **Codex CLI + GPT-5.5** instead of Claude
Code, against the *same* build123d-mcp and the *same* generic prompts — a second
*system* to compare, not a re-tuned one. The model id selects the backend:
`claude-*` routes to Claude Code, anything else routes to the Codex driver.

```bash
./run_sweep.sh splits/test.txt gpt55-v1 gpt-5.5 build123d-mcp==0.3.72 5
```

**Reasoning effort** is part of the scored system, so pin it explicitly with a
`model:effort` suffix instead of letting it inherit `~/.codex/config.toml`:

```bash
./run_sweep.sh splits/test.txt gpt55-hi gpt-5.5:high build123d-mcp==0.3.72 5   # -c model_reasoning_effort=high
./run_sweep.sh splits/test.txt gpt55-lo gpt-5.5:low  build123d-mcp==0.3.72 5
./run_sweep.sh splits/test.txt gpt55-md gpt-5.5      build123d-mcp==0.3.72 5   # no suffix -> config default
```

The driver splits the suffix off (`-m gpt-5.5 -c model_reasoning_effort=high`),
and `run_meta.json` records `model` + `reasoning_effort` so the run is fully
pinned (the packaged `meta.json` notes disclose the effort too). `claude-*`
models route to Claude Code's own `--effort <low|medium|high|xhigh|max>` flag
via the same `:effort` suffix (e.g. `claude-fable-5:xhigh`); no suffix means
default effort.

Each fixture runs through `harness/run_fixture_codex.sh`, which mirrors the Claude
driver: it builds the identical prompt, attaches the drawing/renders to the model
(`codex exec -i …`, plus Codex's built-in `view_image` tool for mid-run zoom
crops), wires build123d-mcp via `-c mcp_servers.*` TOML overrides (Codex has no
`--mcp-config` flag), and writes the same `output.step` + `stream.jsonl`. Watch
one live with the Codex stream filter:

```bash
tail -n0 -f work/gpt55-v1/<id>_run/stream.jsonl \
    | python3 harness/stream_filter_codex.py work/gpt55-v1/<id>_run
```

Two behavioural differences from the Claude path, both disclosed for honesty:
Codex has no per-call tool allowlist, so the model sees all of build123d-mcp's
tools (the Claude driver curates a 17-tool subset); and the prompts' "read
`input.png`" / zoom-crop guidance is satisfied via `-i` + `view_image` rather
than Claude Code's `Read` + `Bash`-crop. The prompts themselves are unchanged.

## Validate / package the submission

```bash
uv run --python 3.12 --with build123d-mcp==0.3.72 --with trimesh --with scipy \
    python package_submission.py results/opus48-v1 --zip --name "<submission-name>"
```

This writes `results/opus48-v1/manifest.json` (present / missing / gate verdict
per fixture) and, with `--zip`, the upload-ready `submit/opus48-v1.zip` — the
full fixture set with an auto-generated `meta.json` whose notes are stamped from
the run's provenance (model + resolved build123d-mcp version + the
cadgenbench-build123d commit that pins the prompts), `agent_url` set to that
commit's permalink, and `submitter_name`/`submission_name` = `pzfreo` (override
with `--submitter` / `--name`). The validity gate runs `exact=True` so large
parts aren't false-flagged.

### The build123d-mcp gate is a proxy, not the authoritative gate

CADGenBench's own `sanity_check_submission.py` is authoritative, but **running it
locally does not currently work on this machine** (cadgenbench 0.2.0's deps —
`open3d==0.19`, `nlopt==2.10` — have no macOS-x86_64 wheels, so the required
`uv --project` env fails to build). `package_submission.py --official-sanity-check
<path>` exists but is **not usable here** for the same reason (and separately, it
runs the checker under the packager's own ephemeral env, which lacks the
`cadgenbench` package entirely — either way you'd get a `ModuleNotFoundError`
traceback per fixture, not a geometry verdict). Do not pass
`--official-sanity-check` on this machine; do not try to build open3d/nlopt from
source to work around it.

Instead:
- Trust the **build123d-mcp proxy gate** (what `package_submission.py` already
  runs, no flag needed) as the local validity prediction — it shares the core
  BRepCheck + mesh-manifold logic with the real checker.
- The **HF Space's own gate**, which runs at scoring time on Linux (where the
  wheels exist), is the real, authoritative verdict. Treat a local `81/81` proxy
  pass as "expected valid," not as a substitute for uploading and checking the
  Space's result.

## Layout

```
harness/
  fetch_fixture.py        pull a fixture's public inputs from the HF dataset
  run_fixture.sh          drive claude -p + build123d-mcp; auto-selects the prompt
  run_fixture_codex.sh    same, driven by codex exec + GPT-5.5 (second system)
  prompt_generation.txt   drawing -> solid (checkpoint-first, validity-as-invariant)
  prompt_editing.txt      STEP + change request -> edited solid
  stream_filter.py        live readable log of a single Claude run
  stream_filter_codex.py  live readable log of a single Codex run
  score.py                local proxy: validity gate (+ indicative shape score vs GT)
run_sweep.sh              batch a fixture list into results/<run>/<id>/output.step
package_submission.py     validity-check the layout + write manifest.json
splits/                   dev (tuned-on) vs test (reportable) fixture lists
logs/                     per-fixture session logs — committed (see below)
work/, results/, submit/  sweep artifacts — gitignored, regenerable from a rerun
```

`logs/<run_name>/<id>.log` is intentionally **committed**, unlike `work/`,
`results/`, and `submit/` (all gitignored as large and regenerable). A
submission's `agent_url` points reviewers at the exact commit; the logs let them
also see the actual session that produced a given `output.step`, for HF audit
purposes. Never gitignore `logs/`.

## Scoring caveat

`harness/score.py` reports the build123d-mcp validity gate and, if you supply a
ground-truth STEP, an **indicative** shape score (uniform-scale + rigid-align
search → surface-distance F1). It is **not** the official CADGenBench metric
(which forbids scale search and blends F1 with volume-IoU, plus interface and
topology terms). Use it for relative comparison only.
