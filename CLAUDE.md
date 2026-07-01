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
  The `:effort` suffix works for `claude-*` too (e.g. `claude-fable-5:xhigh`) — the Claude
  driver passes it as `claude --effort <low|medium|high|xhigh|max>`; no suffix = default effort.

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
the `cadgenbench` package is in `/Users/paul/repos/cadgenbench`.

**GOTCHA #2 (hit 2026-06-25, cadgenbench 0.2.0):** the workaround above **no longer runs locally**
on this Mac. After `/Users/paul/repos/cadgenbench` was re-pointed to the official
`huggingface/cadgenbench` (0.2.0), its deps include `open3d==0.19` (cp312-only wheels) and
`nlopt==2.10` (no macOS-x86_64 wheel), so the uv env won't build — `uv run --project ...`
fails with a "no wheel for the current platform" resolver error (not a geometry verdict).
So the official gate **cannot be run locally under 0.2.0**. Fall back to:
- the **build123d-mcp proxy gate** (what `package_submission.py` already runs) as the local
  validity prediction — it shares the core BRepCheck + mesh-manifold logic, and
- the **HF Space's own authoritative gate**, which runs at scoring time on Linux (where the
  wheels exist). Treat proxy `81/81` as "expected valid"; the Space is the real verdict.

Do not rabbit-hole trying to build open3d/nlopt from source locally — upload and let the Space gate.

## Verifying edits actually took (no-op detection)

The editing benchmark scores a no-op against a baseline, so a valid-but-unchanged output
can mask a failed edit. To audit a sweep's edits, compare each `output.step` to its
`input.step` (tessellation Hausdorff; volume/bbox fallback when tessellation fails). A pure
**tangential move** reads ~0 displacement even when correct — classify those by reading
`<id>_in/edit_description.txt`, not by the metric alone.
