# CLAUDE.md — cadgenbench-build123d

Project-specific guidance. Merges with the global `~/.claude/CLAUDE.md`.

**`README.md` is the source of truth for this pipeline** — full sweep/validate/
package walkthrough, argument defaults, layout. Read it first. This file adds
agent-specific behavioral rules and hard-won gotchas on top; it should never
restate README's content in a way that could drift out of sync with it.

This repo is a **reproducible pipeline** for submitting to CADGenBench. The pipeline
(run → package → official-check) *is* the contribution, so provenance must be faithful.
Always drive it with the repo's own scripts (`run_sweep.sh`, `package_submission.py`) —
never hand-rolled loops, which skip the provenance stamping and force error-prone
retrofitting before packaging. See README.md § "Run a sweep" for the full command
signature and defaults, and § "Commit prompt/harness changes before the sweep" for
why a clean commit matters before every reportable run.

## Package + authoritative validity check

See README.md § "Validate / package the submission" for the command and what it writes.

**GOTCHA (hit 2026-06-25):** `package_submission.py --official-sanity-check <path>` runs the
checker with `sys.executable` — the packager's ephemeral uv env, which lacks the
`cadgenbench` package. It then records `official_status=FAIL` for **every** fixture, but the
`official_output` is a `ModuleNotFoundError` traceback, **not** a geometry verdict. Do not
pass this flag — see GOTCHA #2 below for why the intended workaround doesn't help either.

**GOTCHA #2 (hit 2026-06-25, cadgenbench 0.2.0):** running the real
`sanity_check_submission.py` locally (even directly, bypassing `--official-sanity-check`,
via `uv run --project /Users/paul/repos/cadgenbench python .../sanity_check_submission.py
results/<run>/<id>/output.step`) **no longer works on this Mac**. After
`/Users/paul/repos/cadgenbench` was re-pointed to the official `huggingface/cadgenbench`
(0.2.0), its deps include `open3d==0.19` (cp312-only wheels) and `nlopt==2.10` (no
macOS-x86_64 wheel), so the uv env won't build — `uv run --project ...` fails with a "no
wheel for the current platform" resolver error (not a geometry verdict). So the official
gate **cannot be run locally under 0.2.0** at all. Fall back to what README.md's
"proxy, not authoritative" section describes: trust the local proxy gate as a prediction,
treat the HF Space's own gate as the real verdict. Do not rabbit-hole trying to build
open3d/nlopt from source locally — upload and let the Space gate.

## Verifying edits actually took (no-op detection)

The editing benchmark scores a no-op against a baseline, so a valid-but-unchanged output
can mask a failed edit. To audit a sweep's edits, compare each `output.step` to its
`input.step` (tessellation Hausdorff; volume/bbox fallback when tessellation fails). A pure
**tangential move** reads ~0 displacement even when correct — classify those by reading
`<id>_in/edit_description.txt`, not by the metric alone.
