# CADGenBench (build123d) — Analysis of run `opus48-v0352`

## Headline numbers

| Run | mcp version | PASS | FAIL | Pass rate |
|---|---|---|---|---|
| **opus48-v0352** (latest) | 0.3.52 released (`@latest`) | 76 | 5 | **93.8%** |
| **opus48-full-v1** (earlier) | ~0.3.51 / 0.3.52.dev0 (local `file://` checkout) | 78 | 3 | **96.3%** |

81 fixtures each (49 generation `1xx` + 32 editing `2xx`), identical fixture set in both runs. **Net: −2 fixtures, −2.5 pp.** v0352 broken down: gen 47/49, edit 29/32.

## What the gate measures

`proxy_status`/`proxy_reasons` come from `harness/score.py` → `_gate_report(solid, exact=True)`: it imports the STEP, extracts solids (strips PMI curves), and runs the authoritative topology-stitch mesh gate — checks for a real solid body, non-degenerate volume, watertight/manifold shell (open edges), mesh non-manifold edges, and a well-formed B-rep (OCCT BRepCheck). PASS = valid/scoreable solid, **not** shape-match. The surface-F1 shape score only runs with a ground truth and is absent from these manifests.

## v0352 FAILs and reason tally

- **122** (gen): zero volume; 76 open edges; no solid body
- **125** (gen): zero volume; 61 open edges; no solid body
- **202** (edit): B-rep not well-formed (BRepCheck failed)
- **240** (edit): 1 mesh non-manifold edge
- **249** (edit): B-rep not well-formed

Tally: 2× zero/degenerate volume, 2× no solid body, 2× BRepCheck fail, 2× open-edge (76/61), 1× mesh non-manifold.

## The diff — and why the headline is misleading

Flips: **PASS→FAIL: 122, 240, 249** | **FAIL→PASS: 205** (125 and 202 fail in both runs).

Critically, **the two runs are independent single-shot agent re-runs — every compared `output.step` differs in bytes.** So flips mix gate-strictness changes with generation stochasticity. Re-scoring full-v1's STEPs with the current 0.3.52 exact gate separates them:

| Fixture | full-v1 STEP under 0.3.52 gate | Cause of flip |
|---|---|---|
| 122 | **PASS** | Agent variance — v0352 re-run produced loose shells; full-v1's part was fine |
| 249 | **PASS** | Agent variance — v0352 re-run produced a BRepCheck-invalid part |
| 240 | **FAIL** (mesh non-manifold) | **True gate improvement** — old gate gave a false PASS to an always-defective part; #282 now catches it |
| 205 | **PASS** | **Gate fix** — old gate false-FAILed it; 0.3.52 correctly passes |

**Conclusion on the key question: the v0.3.52 gate changes did NOT regress outcomes.** The gate became strictly more correct (fixed false-FAIL 205, fixed false-PASS 240). The 2.5 pp drop is dominated by single-shot agent run-to-run variance (122, 249); the only gate-driven score moves are a correctly-fixed false PASS offset by a correctly-fixed false FAIL — a wash on score, a win on accuracy.

## Failure themes

- **Theme A — STEP round-trip degradation (122, 125), the most important finding.** The agent's in-session MCP gate reported a valid watertight solid at export (122 log: `Validity gate: PASS ... volume 39186 ... watertight_manifold: true`), but the on-disk `output.step` has **0 solids — only loose shells** (122: 0 solids/10 shells/18 faces; 125: 0 solids/3 shells/22 faces). The solid didn't survive the STEP write/read; the sweep-time export gate validated the in-memory shape, not the reimported file. **This is exactly the bug fixed by PR #284 ("export gate validates the written-and-reimported STEP"), which landed Jun 22 04:36 — AFTER the v0352 sweep ran (Jun 21 20:48). #284 is in neither run.** Both are thin-wall casting parts (shell ops prone to open shells).
- **Theme B — BRepCheck-invalid on editing fixtures (202, 249).** 202's *input* STEP was itself BRepCheck-invalid (agent attempted healing); 202 fails in both runs (persistently hard, not a regression). 249 is a rib-thickening edit producing a malformed B-rep.
- **Theme C — mesh non-manifold (240).** Single self-touching-faces defect; precisely what the #282 topology-stitch check was added to catch.

Editing fixtures fail at 3/32 (9.4%) vs generation 2/49 (4.1%) — the harder regime, as expected.

## Red flags / data quality

1. **`opus48-full-v1` has no real run_meta** — `run_meta.json` is absent and the manifest's `run_meta` is just `{"run": "opus48-full-v1"}`. Its MCP version/model/commit had to be inferred from file timestamps, git history, and `mcp_config.json` (a local `file://` checkout). Future runs should serialize the resolved MCP version into the manifest.
2. **Different MCP sources** — full-v1 used a local working-tree checkout (possibly with uncommitted changes); v0352 used published `@latest` 0.3.52.
3. **#284 is in neither run** — and 2 of 5 v0352 failures (122, 125) are exactly that bug. **The 93.8% understates a current-build sweep; a re-sweep including #284 is recommended before finalizing any pass-rate for a release decision** (likely recovers 122/125).
4. **Single-shot, high variance** — independent re-runs flip fixtures (122, 249) purely from generation noise; a 2.5 pp swing on 81 single-shot fixtures is within noise. Don't read it as signal without multiple seeds or a re-sweep.
5. No missing fixtures, no zero-byte STEPs, identical 81-fixture coverage. `splits/all.txt` = 81 ids + 3 comment lines (clean). Minor clutter: stray `results/sonnet-calib-v1 2` dir and `.zip` snapshots.
</content>
</invoke>
