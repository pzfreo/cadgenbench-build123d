#!/usr/bin/env bash
# Run one drawing->solid fixture through Claude Code + gate-equipped build123d-mcp,
# with a live JSON stream you can tail. Portable: no hardcoded machine paths.
#
# Usage:
#   eval/run_fixture.sh <fixture_input_dir> <work_dir> [model] [mcp_spec]
#
#   fixture_input_dir : holds input.png (generation) and optionally input.step (editing)
#   work_dir          : output.step + stream.jsonl + filtered.log land here
#   model             : claude model id (default: claude-opus-4-8)
#   mcp_spec          : build123d-mcp version spec for uvx (default: build123d-mcp@latest)
#
# Live log (in another terminal):
#   tail -n0 -f <work_dir>/stream.jsonl | python3 eval/stream_filter.py <work_dir>
#
# Requires: `claude` (Claude Code) and `uvx` on PATH.
set -euo pipefail
FIX="${1:?fixture input dir}"
WORK="${2:?work dir}"
MODEL="${3:-claude-opus-4-8}"
MCP_SPEC="${4:-build123d-mcp@latest}"

# Optional reasoning-effort suffix on the model id: "claude-fable-5:xhigh" ->
# model "claude-fable-5" + --effort xhigh (levels: low|medium|high|xhigh|max).
# No suffix => Claude Code's default effort. Mirrors run_fixture_codex.sh so
# effort is a launch-time, provenance-stamped part of the scored system.
MODEL_EFFORT=""
case "$MODEL" in
  *:*) MODEL_EFFORT="${MODEL##*:}"; MODEL="${MODEL%%:*}" ;;
esac
EFFORT_ARG=()
[[ -n "$MODEL_EFFORT" ]] && EFFORT_ARG=(--effort "$MODEL_EFFORT")
HERE="$(cd "$(dirname "$0")" && pwd)"

command -v claude >/dev/null || { echo "ERROR: 'claude' (Claude Code) not on PATH"; exit 1; }
command -v uvx    >/dev/null || { echo "ERROR: 'uvx' not on PATH"; exit 1; }

# --- Run isolation: execute in a scratch dir OUTSIDE the repo, mirror artifacts back. ---
# The agent runs with CWD=$WORK and is given the $OUT path in its prompt. When those sit
# under the repo, a permission-skipping agent can read PRIOR sweeps' logs/ and work/ for
# the SAME fixture id via Bash — laundering an earlier run's answer and breaking run
# independence. Repointing WORK at a repo-external temp dir removes that breadcrumb; the
# EXIT trap mirrors output.step/stream.jsonl/filtered.log/etc. back into the real work dir
# so run_sweep.sh is unchanged. (Same fix as run_fixture_codex.sh.)
REAL_WORK="$WORK"
mkdir -p "$REAL_WORK"
REAL_WORK="$(cd "$REAL_WORK" && pwd)"   # absolute: the run cd's into the sandbox, so the trap needs a fixed path
WORK="$(mktemp -d "${TMPDIR:-/tmp}/cgb_fixture.XXXXXX")"
trap 'cp -a "$WORK"/. "$REAL_WORK"/ 2>/dev/null || true; rm -rf "$WORK"' EXIT

mkdir -p "$WORK"
rm -f "$WORK/output.step" "$WORK/stream.jsonl" "$WORK/filtered.log"
cp "$FIX"/input.png  "$WORK"/ 2>/dev/null || true
cp "$FIX"/input.step "$WORK"/ 2>/dev/null || true

OUT="$WORK/output.step"
if [[ -f "$FIX/edit_description.txt" ]]; then
  # editing fixture: bring along the change request + reference renders, and
  # build the editing prompt (literal substitution — the edit text is arbitrary).
  cp "$FIX/edit_description.txt" "$WORK"/ 2>/dev/null || true
  cp -R "$FIX/renders" "$WORK"/ 2>/dev/null || true
  python3 -c "import sys,pathlib; t=pathlib.Path(sys.argv[1]).read_text(); print(t.replace('{EDIT}', pathlib.Path(sys.argv[2]).read_text().strip()).replace('{OUTPUT}', sys.argv[3]), end='')" \
    "$HERE/prompt_editing.txt" "$FIX/edit_description.txt" "$OUT" > "$WORK/prompt.txt"
  TASK="editing"
else
  sed "s|{OUTPUT}|$OUT|g" "$HERE/prompt_generation.txt" > "$WORK/prompt.txt"
  TASK="generation"
fi

# The benchmark runs in a trusted, isolated environment, so we launch the MCP
# server with --no-sandbox: the AST check is skipped and user code gets full
# builtins. This removes sandbox friction (blocked getattr/vars, retries) that
# cost the agent turns. Requires build123d-mcp >= 0.3.54. --disable-tool-groups
# drawing drops the 6-tool 2D drawing-authoring suite (inspect_drawing,
# lint_drawing, render_drawing, view_axes, save_drawing_annotations,
# suggest_view_layout) — irrelevant to this pipeline (no drawing-authoring task)
# and pure schema-context overhead otherwise. Requires build123d-mcp >= 0.3.68.
cat > "$WORK/mcp_config.json" <<JSON
{"mcpServers":{"build123d":{"command":"uvx","args":["--python","3.12","$MCP_SPEC","--no-sandbox","--disable-tool-groups","drawing"]}}}
JSON

echo "fixture: $FIX  ($TASK)"
echo "work:    $WORK"
echo "model:   $MODEL    effort: ${MODEL_EFFORT:-<default>}    mcp: $MCP_SPEC  (--no-sandbox)"
echo "live:    tail -n0 -f $WORK/stream.jsonl | python3 $HERE/stream_filter.py $WORK"
echo "running claude -p ..."

cd "$WORK"

# Allowed toolset. Base set (both tasks) plus session_state/last_error/resolve —
# recovery + debug + selector tools the agent demonstrably reached for in the
# opus48 sweeps. locate_gate_defects (mcp >= 0.3.58) returns the 3D coordinates +
# B-rep identity of a validity-gate failure so the agent repairs the exact spot
# instead of blind (the codex path already sees it; the Claude allowlist lacked
# it). shape_compare is editing-only (verify the edit changed only what was
# asked). load_part/search_library (no library), the 2D-drawing-authoring tools,
# reset, and diagnostics are intentionally excluded as irrelevant here.
# verify_spec/suggest_spec are DELIBERATELY excluded (not just unprompted): across
# two full 81-fixture runs, fixtures where the agent called them scored worse on
# average than fixtures that didn't (-0.037/-0.049 vs -0.009/+0.017), because a
# "conforms: true" result reliably reads to the model as a stop signal regardless
# of prompt caveats saying otherwise (build123d-mcp#362). The Codex driver has no
# equivalent allowlist, so this can only be hard-blocked here.
ALLOWED="mcp__build123d__execute,mcp__build123d__render_view,mcp__build123d__measure,mcp__build123d__validate,mcp__build123d__export,mcp__build123d__import_cad_file,mcp__build123d__save_snapshot,mcp__build123d__restore_snapshot,mcp__build123d__find_holes,mcp__build123d__find_hole_patterns,mcp__build123d__find_bosses,mcp__build123d__cross_sections,mcp__build123d__clearance,mcp__build123d__session_state,mcp__build123d__last_error,mcp__build123d__resolve,mcp__build123d__locate_gate_defects"
if [[ "$TASK" == "editing" ]]; then
  ALLOWED="$ALLOWED,mcp__build123d__shape_compare"
fi

# Eagerly load the build123d MCP tool schemas instead of deferring them behind
# the ToolSearch tool (Claude Code's default). Deferral cost ~3 ToolSearch calls
# per run, ~36% of them mismatching the tool names — pure wasted turns for a
# fixed, known toolset. See docs.claude.com/en/mcp "Tool Search".
export ENABLE_TOOL_SEARCH=false
claude -p "$(cat prompt.txt)" \
  --model "$MODEL" \
  ${EFFORT_ARG[@]+"${EFFORT_ARG[@]}"} \
  --output-format stream-json --verbose \
  --mcp-config mcp_config.json \
  --strict-mcp-config \
  --dangerously-skip-permissions \
  --disable-slash-commands \
  --allowedTools "$ALLOWED" \
  > stream.jsonl 2>&1

echo
if [[ -f output.step ]]; then
  echo "output.step produced ($(wc -c < output.step) bytes)"
else
  echo "NO output.step (timeout or the agent stopped early) — see stream.jsonl"
fi
