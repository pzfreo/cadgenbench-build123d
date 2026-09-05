# GPT-6 Astra (High): full 81-fixture submission evidence

Evidence for [build123d-mcp 0.3.85.dev0 with GPT-6 Astra (High)](https://huggingai4engineering-cadgenbench.hf.space/reports/pzfreo_build123d-mcp-0-3-85-dev0-with-gpt-6-ast_20260905-073202.html), submitted 5 September 2026.

This is an archive of existing execution evidence, not a rerun or a changed submission. Publishing logs does not itself confer verified status; that is for the benchmark reviewers to determine.

## What is included

- `101.log` … `250.log`: all 81 readable, abbreviated session logs (49 generation + 32 editing).
- `raw/<fixture>.jsonl`: all 81 original Codex CLI streams, including full tool arguments/results and final agent messages. Files retain incidental non-JSON CLI diagnostic lines; parsers should skip those while preserving the archive.
- `prompts/<fixture>.txt`: exact dispatched prompts, including the distinct generation and editing paths.
- `source_runs/*/run_meta.json`: original metadata for the 12-fixture smoke test and 69-fixture continuation.
- `run_meta.json`: original merged-run metadata and fixture/source-run mapping.
- `submission_meta.json`: metadata copied unchanged from the submitted ZIP.
- `proxy_manifest.json`: original local proxy gate manifest, not an official score report or task-success certificate.
- `evidence_manifest.json`: per-fixture source provenance, SHA-256 hashes of logs/prompts/streams/outputs, thread IDs, terminal events, and observed banking calls. `final_snapshot_banked` means a successful bank with snapshot name `final`, not reference correctness.

All copied evidence is byte-identical to the local source files. Raw logs retain ordinary local workspace paths and session identifiers. A credential-pattern scan found no provider keys, bearer credentials, or private-key blocks in the published files. No `.secrets`, authentication configuration, input geometry, generated STEP files, or unrelated run logs are included.

Readable-log `[0s]` timestamps are filter-relative and are not reliable elapsed-time evidence. Use the full transcript to inspect actions; do not infer instantaneous execution from those labels.

## Run provenance

| Item | Recorded value |
|---|---|
| Model / effort | `gpt-6-astra` / `high` |
| Driver / authentication | Codex CLI 0.153.2 / Codex subscription |
| MCP | `0.3.85.dev0`, native MCP transport |
| MCP commit | [`6947a12ca9aa580c172bccdd087d10a9fc3e185b`](https://github.com/pzfreo/build123d-mcp/tree/6947a12ca9aa580c172bccdd087d10a9fc3e185b) |
| Smoke12 harness commit | [`7f40496a56eec6558ed5bad2f28479e96dedbe29`](https://github.com/pzfreo/cadgenbench-build123d/tree/7f40496a56eec6558ed5bad2f28479e96dedbe29) |
| Continuation69 harness commit | [`f7e5deeda2640afc5f4eb8435b2d05e60c3db2a2`](https://github.com/pzfreo/cadgenbench-build123d/tree/f7e5deeda2640afc5f4eb8435b2d05e60c3db2a2) |
| Submitted ZIP filename | `build123d-mcp-0.3.85.dev0-gpt-6-astra-high.zip` |
| Submitted ZIP SHA-256 | `4a16368efefaf5b87a7d10d4f3846a5bccb6e02ac9df7eb69650667198555511` |

The original `agent_url` in submission metadata points to the run's harness commit, which predates this evidence publication. This verification branch is based on that same continuation commit and adds only the evidence directory. Use this directory's immutable publication commit URL as the supplementary evidence link for review; the original ZIP/metadata have not been rewritten.

## Reuse and completion caveats

The 12 smoke fixtures were reused unchanged: **105, 115, 125, 135, 145, 150, 202, 206, 214, 217, 229, 240**. The other 69 came from the continuation. Both source runs used the recorded Astra high/MCP configuration. This is a disjoint 12+69 assembly, not per-fixture best-of selection. All 81 merged readable logs match their respective source-run logs. Output SHA-256 hashes match the source work directories, merged results, and actual ZIP members for all 81 fixtures.

All 81 streams contain `turn.completed`, and all 81 STEP files are present. **This does not mean all requested edits succeeded.** The full transcripts show eight baseline-only editing outcomes:

| Fixture | Final outcome |
|---|---|
| 201 | Pocket edit attempts failed; unchanged baseline retained. |
| 204 | Requested hole spacing/axes could not be reconciled; asked for clarification. |
| 208 | Signed-axis mapping unresolved; asked which annular end was intended. |
| 217 | Requested Y-axis bore versus observed Z-axis bore; asked for clarification. |
| 218 | Requested +Z fillet versus observed −Z fillet; asked for clarification. |
| 229 | Requested Ø15 bore versus observed Ø25 bore; asked for clarification. |
| 241 | Blend removal attempts returned unchanged geometry; baseline retained. |
| 249 | Rib offsets/fusions failed; baseline retained, ribs still 25 mm thick. |

These eight logs show only baseline banking and explicitly disclose no completed edit in the final agent response. The remaining 24 edit transcripts contain successful `final` snapshot banks; that is evidence of artifact promotion, not a claim that the reference edit is correct. There were no follow-up clarification answers or replacement outputs added during this publication.

## Reviewer checks

1. Inspect `source_runs` and each exact prompt to establish the model, MCP, harness and task paths.
2. Follow each fixture's full raw stream rather than relying on truncated readable tool lines.
3. Use the output hashes in `evidence_manifest.json` to connect transcripts to the submitted artifacts.
4. Distinguish baseline-only outcomes, promoted edited candidates, geometric validity, and official scores.
5. Treat this publication as supporting evidence, not a statement that HF has already verified the submission.
