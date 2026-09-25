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

- `claude` (Claude Code) and `uv` on `PATH`. For the Codex/GPT-5.5 path,
  a logged-in `codex` CLI (`codex login`) too. For google/* models through
  Vercel AI Gateway, export `AI_GATEWAY_API_KEY` as well.

## Run a sweep

```bash
./run_sweep.sh <fixtures_file> <run_name> [model] [mcp_spec] [jobs] [exec_timeout]

# one fixture id per line; work/ and results/ are created per run name
./run_sweep.sh splits/test.txt opus48-v1 claude-opus-4-8 build123d-mcp==0.3.72 5 240
```

`model` defaults to `claude-opus-4-8` (`claude-*` routes to Claude Code; any
other id, e.g. `gpt-5.5`, routes to the Codex CLI driver — see below). `mcp_spec`
defaults to the reproducible pin `build123d-mcp==0.3.90`. `jobs` (fixtures run concurrently;
each has its own work dir, so parallel runs never collide) defaults to `4` —
lower it if you hit API rate limits (429s). `exec_timeout` (seconds, passed to
both drivers as `--exec-timeout`) defaults to each server's own default
(currently 120s); Codex's own client-side `tool_timeout_sec` is fixed at 600s in
`run_fixture_codex.sh`, so keep this under that or Codex gives up first. Each
fixture is fetched, run through `harness/run_fixture.sh` (generation or editing
is auto-detected from the fixture's files), and the result copied to
`results/<run_name>/<id>/output.step`. Per-fixture failures don't abort the sweep.
Editing-only sweeps (all fixture ids 2xx or self-bench 91xx) are capped at 3
concurrent fixtures, because edit sessions import large source parts and 4 or
more exhausted RAM on an 8 GB host; override with `CGB_EDIT_MAX_JOBS`.

Override `mcp_spec` explicitly when testing another release or a local build.
Reported comparisons should always use an exact version; a moving `@latest`
spec can silently change the build123d-mcp code between runs.

For a Claude direct-build123d ablation with no MCP server, pass `none` as the
MCP spec. The separate ablation driver gives Claude only file/shell tools plus
a pinned build123d environment and supports both generation and editing:

```bash
./run_sweep.sh selfbench/selfbench.txt opus5-nomcp-selfbench-r1 \
    claude-opus-5:xhigh none 1
```

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

## Third system: Google Antigravity CLI (Agy)

Prefix an Agy model slug with `agy/` to use Antigravity's native agent and MCP
stack. Each fixture uses two headless turns in one conversation: Plan mode
inspects the fixture files and drawing, then an autonomous accept-edits turn
resumes that exact conversation and executes the plan. Six fixtures can run as
six independent Agy conversations in parallel. Both turns enable Agy's terminal
sandbox so file and shell discovery cannot escape the isolated fixture workspace;
the separately configured build123d MCP subprocess remains available for CAD.

```bash
./run_sweep.sh splits/gemini37-flash-smoke6.txt agy-gemini37-high-plan \
    agy/gemini-3.7-flash-high build123d-mcp==0.3.83 6 240
```

`run_sweep.sh` pins the selected MCP command in Agy's user-level `build123d`
server entry before fan-out. The driver records the Agy version, model, effort,
native MCP transport, and `plan-then-accept-edits` mode in `run_meta.json`.
Raw events use Agy's JSONL format and can be watched with:

```bash
tail -n0 -f work/agy-gemini37-high-plan/<id>_run/stream.jsonl \
    | python3 harness/stream_filter_agy.py work/agy-gemini37-high-plan/<id>_run
```

Editing experiments can require recognition in the accept-edits turn rather
than the disposable planning MCP process:

```bash
CGB_RECOGNITION_POLICY=required-in-edit-execution \
  ./run_sweep.sh splits/recognition-execution-diagnostic8.txt \
  agy-gemini38-recognition-execution-diagnostic8 \
  agy/gemini-3.8-flash-high \
  'build123d-mcp @ file:///absolute/path/to/build123d-mcp' 8 240
```

The execution prompt re-imports the starting part, runs compact and targeted
recognition, requires same-session `recognition_faces()` use for returned
features, and bounds conventional fallback after a miss. Each fixture writes
`recognition_audit.json`; `run_meta.json` records the selected recognition
policy. `CGB_FORCE_RECOGNITION=1` remains the legacy planning-turn policy.

Broken-input experiments can require a clean repaired baseline before strict
recognition without weakening or special-casing `b123d-recognisers`:

```bash
CGB_RECOGNITION_POLICY=repair-first-then-strict-recognition \
  ./run_sweep.sh splits/retest-202-240-timeout.txt \
  build123d-mcp-repair-first-broken2 \
  agy/gemini-3.8-flash-high \
  'build123d-mcp @ file:///path/to/build123d-mcp' 2 600
```

This policy uses the MCP's generic defect locator and repair ladder, requires a
gate-clean STEP round trip before calling the unchanged strict recogniser, and
contains no fixture IDs, face indices, coordinates, or expected constructions.

### Gemini through Codex + Vercel AI Gateway

`google/*` model ids reuse the Codex driver and its MCP/image orchestration but
route Responses API traffic through Vercel AI Gateway's Codex compatibility
endpoint. The gateway configuration is passed inline for each run, so it does
not modify or depend on the default provider in `~/.codex/config.toml`.

```bash
export AI_GATEWAY_API_KEY="..."
./run_sweep.sh splits/gemini37-flash-smoke6.txt gemini37-flash-v1 \
    google/gemini-3.7-flash:medium build123d-mcp==0.3.83 1 240
```

The model id, reasoning effort, agent driver, gateway provider/endpoint, MCP
version, and harness commit are recorded in `run_meta.json`. Gemini 3.7 Flash
supports `low`, `medium`, and `high` reasoning effort; do not use `xhigh`.

Current Codex releases serialize MCP tools with an OpenAI-specific namespace
wrapper that non-OpenAI Responses providers do not expand. For `google/*` runs,
the driver starts a loopback-only compatibility proxy which flattens only the
`build123d` namespace into standard Responses function tools and maps calls back
before Codex dispatches them. The proxy never logs request bodies, headers, or
credentials; `run_meta.json` records `mcp_tool_transport` and the Codex version.

## Validate / package the submission

Run the packager after every sweep you care about. It always writes a local
proxy-gate manifest first:

```bash
uv run --python 3.12 --with build123d-mcp==0.3.72 --with trimesh --with scipy \
    python package_submission.py results/opus48-v1
```

This writes `results/opus48-v1/manifest.json` with one entry per result
subdirectory: whether `output.step` is present, whether the local
build123d-mcp proxy gate passed, and any warnings. Treat this as the local
pre-flight check, not as the official leaderboard verdict.

To build the upload artifact, add `--zip`:

```bash
uv run --python 3.12 --with build123d-mcp==0.3.72 --with trimesh --with scipy \
    python package_submission.py results/opus48-v1 \
    --zip
```

By default `--zip` pads to `splits/all.txt`, producing
an automatically named `submit/build123d-mcp-<version>-<model>-<effort>.zip`
with all canonical CADGenBench fixture directories at the zip root. Directories
with a submitted candidate contain `output.step`;
directories without a candidate are written as explicit empty directory entries
inside the zip. Missing outputs are expected to score zero.

For a smoke/debug upload that should contain only a smaller fixture universe,
override the padding list explicitly:

```bash
uv run --python 3.12 --with build123d-mcp==0.3.72 --with trimesh --with scipy \
    python package_submission.py results/gpt55-v0372-smoke5 \
    --zip --full-set splits/smoke4-v0372.txt
```

For a leaderboard-style upload from a partial run where you still want every
canonical fixture directory present, keep the default `--full-set splits/all.txt`:

```bash
uv run --python 3.12 --with build123d-mcp==0.3.72 --with trimesh --with scipy \
    python package_submission.py results/gpt55-v0372-smoke5 \
    --zip
```

That writes an automatically named ZIP with all 81 fixture directories and only
the produced outputs filled in.

The generated zip includes an auto-generated root `meta.json`. Its notes are
stamped from `run_meta.json`: model, reasoning effort, resolved build123d-mcp
version, and the cadgenbench-build123d commit that pins prompts/harness.
`agent_url` points at that commit permalink. `submitter_name` defaults to
`pzfreo`. For MCP runs, `submission_name` is automatically derived as
`build123d-mcp-<resolved-version>-<normalized-model>-<effort>`; direct/no-MCP
ablations use `build123d-direct-<model>-<effort>`. An optional `--name` may add a
suffix such as `-smoke6`, but the packager rejects names that do not retain the
complete derived identity. ZIP packaging also fails rather than emitting
ambiguous metadata when `run_meta.json`, the model, or the MCP version is absent.

### Claude subscription quota recovery

Claude MCP fixtures keep build123d-mcp in a fixture-local, loopback-only HTTP
process owned by the harness rather than by Claude Code. If Claude returns a
subscription quota rejection, the fixture worker does not exit: it retains the
scratch workspace, Claude conversation ID, and live CAD namespace, waits until
the provider's reported reset time, and resumes that conversation against the
same MCP process. Because the worker remains allocated, `xargs` cannot dispatch
later fixtures into a closed quota window. Parallel workers share a start gate
that spaces resumed requests by five seconds; override this with
`CGB_QUOTA_RESUME_SPACING_SECONDS` when necessary. A machine reboot or force-kill
still loses the in-memory CAD namespace, so ordinary checkpoint/package hygiene
remains necessary for multi-day runs.

Claude run metadata also stamps `credential_source` as either
`anthropic-api-key` or `claude-subscription`, based on whether
`ANTHROPIC_API_KEY` was present at launch. The packager carries this distinction
into the submission notes so API and subscription runs cannot be confused.

Sanity-check the zip before upload when in doubt:

```bash
python3 - <<'PY'
import zipfile
from pathlib import Path
p = Path("submit/build123d-mcp-0.3.72-gpt-5.5-high.zip")
with zipfile.ZipFile(p) as z:
    names = z.namelist()
    dirs = {n.split("/")[0] for n in names if "/" in n and n.split("/")[0].isdigit()}
    outputs = [n for n in names if n.endswith("/output.step")]
    print("fixture_dirs", len(dirs))
    print("outputs", len(outputs), sorted(n.split("/")[0] for n in outputs))
    print("has_meta", "meta.json" in names)
PY
```

Upload the zip through the CADGenBench Hugging Face Space:
<https://huggingface.co/spaces/HuggingAI4Engineering/CADGenBench>. After upload,
the Space runs the authoritative Linux-side validity/scoring pipeline and
reports the accepted/missing/invalid status per fixture.

After the Space finishes processing, query the published leaderboard directly:

```bash
python3 tools/fetch_leaderboard.py
```

That reads the same `results.jsonl` dataset used by the Space UI, writes
`leaderboard.csv`, and records a deduplicated history under
`tools/.leaderboard-store/`. For machine-readable output:

```bash
python3 tools/fetch_leaderboard.py --format json
```

To inspect the local change timeline later:

```bash
python3 tools/fetch_leaderboard.py --log
```

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
