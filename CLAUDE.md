# CLAUDE.md — cadgenbench-build123d

Project-specific guidance. Merges with the global `~/.claude/CLAUDE.md`.

This repo is a **reproducible pipeline** for submitting to CADGenBench. The pipeline
(run → package → official-check) *is* the contribution, so provenance must be faithful.
Always drive it with the repo's own scripts — never hand-rolled loops, which skip the
provenance stamping and force error-prone retrofitting before packaging.

## Run a sweep — use `run_sweep.sh`, never a bespoke driver

```bash
./run_sweep.sh <fixtures_file> <run_name> <model> <mcp_spec> <jobs>
# full set, GPT-5.5 medium, pinned MCP, 5 concurrent:
./run_sweep.sh splits/all.txt gpt55-v0359-medium-full gpt-5.5:medium build123d-mcp==0.3.59 5
```

It writes the canonical `results/<run>/<id>/output.step` **and** auto-generates
`results/<run>/run_meta.json` (+ `uncommitted.patch` if the tree is dirty) — the exact
provenance `package_submission.py` consumes. A hand-rolled loop over `run_fixture*.sh`
writes `work/<id>_run/` with **no** run_meta and forces manual staging + a hand-authored
run_meta later; don't do that.

- **Commit** prompt/harness changes BEFORE the sweep so run_meta pins a clean commit
  (a dirty tree warns and records `git_dirty=true`).
- **Pin** `<mcp_spec>` to an exact version (`build123d-mcp==0.3.59`), never `@latest` —
  a moving spec breaks reproducibility.
- `gpt-5.5:medium` — the `:effort` suffix is part of the scored system; `run_sweep.sh`
  splits it into `model` + `reasoning_effort` in run_meta. `claude-*` models route to
  `run_fixture.sh`, everything else to `run_fixture_codex.sh` (needs `codex` logged in).

## Package + authoritative validity check

```bash
uv run --python 3.12 --with build123d-mcp==<ver> --with trimesh --with scipy \
  python package_submission.py results/<run> --zip --name "<submission-name>"
```

Builds `submit/<run>.zip` (`meta.json` auto-stamped from run_meta + `<id>/output.step`,
padded to `splits/all.txt`). The in-tool gate is a **proxy** — the authoritative gate is
CADGenBench's own `sanity_check_submission.py`.

**GOTCHA (hit 2026-06-25):** `package_submission.py --official-sanity-check <path>` runs the
checker with `sys.executable` — the packager's ephemeral uv env, which lacks the
`cadgenbench` package. It then records `official_status=FAIL` for **every** fixture, but the
`official_output` is a `ModuleNotFoundError` traceback, **not** a geometry verdict. Run the
official check under the cadgenbench source env instead:

```bash
# cadgenbench source repo (uv project, src-layout) provides cadgenbench.common.validity
uv run --project /Users/paul/repos/cadgenbench python \
  ~/.cache/huggingface/hub/datasets--HuggingAI4Engineering--cadgenbench-data/snapshots/*/sanity_check_submission.py \
  results/<run>/<id>/output.step          # PASS/FAIL per STEP — loop over all 81
```

The official `sanity_check_submission.py` ships in the HF dataset cache (the path above);
the `cadgenbench` package is in `/Users/paul/repos/cadgenbench`. **Never upload a zip until
every `output.step` passes this real check.**

## Verifying edits actually took (no-op detection)

The editing benchmark scores a no-op against a baseline, so a valid-but-unchanged output
can mask a failed edit. To audit a sweep's edits, compare each `output.step` to its
`input.step` (tessellation Hausdorff; volume/bbox fallback when tessellation fails). A pure
**tangential move** reads ~0 displacement even when correct — classify those by reading
`<id>_in/edit_description.txt`, not by the metric alone.
