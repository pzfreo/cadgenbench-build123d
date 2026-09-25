#!/usr/bin/env bash
# Run one drawing->solid fixture through Claude Code + gate-equipped build123d-mcp,
# with a live JSON stream you can tail. Portable: no hardcoded machine paths.
#
# Usage:
#   eval/run_fixture.sh <fixture_input_dir> <work_dir> [model] [mcp_spec] [exec_timeout]
#
#   fixture_input_dir : holds input.png (generation) and optionally input.step (editing)
#   work_dir          : output.step + stream.jsonl + filtered.log land here
#   model             : claude model id (default: claude-opus-4-8)
#   mcp_spec          : build123d-mcp version spec for uv tool run (default: build123d-mcp==0.3.89)
#   exec_timeout      : seconds, passed as --exec-timeout (default: server's own, 120s)
#
# Live log (in another terminal):
#   tail -n0 -f <work_dir>/stream.jsonl | python3 eval/stream_filter.py <work_dir>
#
# Requires: `claude` (Claude Code) and `uv` on PATH.
set -euo pipefail
FIX="${1:?fixture input dir}"
WORK="${2:?work dir}"
MODEL="${3:-claude-opus-4-8}"
MCP_SPEC="${4:-build123d-mcp==0.3.89}"
EXEC_TIMEOUT="${5:-}"

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
command -v uv     >/dev/null || { echo "ERROR: 'uv' not on PATH"; exit 1; }
command -v jq     >/dev/null || { echo "ERROR: 'jq' not on PATH"; exit 1; }

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
MCP_HTTP_PID=""
HELD_RESUME_LOCK=""
cleanup() {
  if [[ -n "$HELD_RESUME_LOCK" ]]; then
    rm -f "$HELD_RESUME_LOCK/pid" 2>/dev/null || true
    rmdir "$HELD_RESUME_LOCK" 2>/dev/null || true
  fi
  if [[ -n "$MCP_HTTP_PID" ]] && kill -0 "$MCP_HTTP_PID" 2>/dev/null; then
    kill "$MCP_HTTP_PID" 2>/dev/null || true
    wait "$MCP_HTTP_PID" 2>/dev/null || true
  fi
  cp -a "$WORK"/. "$REAL_WORK"/ 2>/dev/null || true
  rm -rf "$WORK"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

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
# EXEC_TIMEOUT (optional) raises the default 120s execute() timeout — field
# evidence (fixtures 202/240) shows heavy sew/defeature/boolean repairs on
# large imports genuinely need more wall-clock time, and the replay-recovery
# safety net (#361) has its own budget, so avoiding the timeout beats recovering
# from it. Kept comfortably under Claude Code's own MCP tool-call timeout.
# Keep MCP outside Claude Code's process tree. Claude exits when subscription
# quota is exhausted; a stdio MCP child dies with it and loses the entire CAD
# namespace. A fixture-local loopback HTTP server survives while this wrapper
# waits and while Claude resumes the same conversation after quota reset.
MCP_HTTP_PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"
HTTP_MCP_SPEC="${MCP_SPEC/build123d-mcp/build123d-mcp[http]}"
MCP_HTTP_ARGS=(--no-sandbox --disable-tool-groups drawing --transport http --host 127.0.0.1 --port "$MCP_HTTP_PORT" --session-idle-timeout 0)
[[ -n "$EXEC_TIMEOUT" ]] && MCP_HTTP_ARGS+=(--exec-timeout "$EXEC_TIMEOUT")
uv tool run --python 3.12 "$HTTP_MCP_SPEC" "${MCP_HTTP_ARGS[@]}" > "$WORK/mcp_http.log" 2>&1 &
MCP_HTTP_PID=$!

MCP_READY=false
for _ in $(seq 1 120); do
  kill -0 "$MCP_HTTP_PID" 2>/dev/null || {
    echo "ERROR: persistent MCP HTTP server exited during startup"
    tail -n 30 "$WORK/mcp_http.log" || true
    exit 1
  }
  if python3 -c 'import socket,sys; s=socket.socket(); s.settimeout(.2); sys.exit(s.connect_ex(("127.0.0.1", int(sys.argv[1]))))' "$MCP_HTTP_PORT"; then
    MCP_READY=true
    break
  fi
  sleep 0.25
done
[[ "$MCP_READY" == true ]] || { echo "ERROR: persistent MCP HTTP server did not become ready"; exit 1; }

cat > "$WORK/mcp_config.json" <<JSON
{"mcpServers":{"build123d":{"type":"http","url":"http://127.0.0.1:$MCP_HTTP_PORT/mcp"}}}
JSON

echo "fixture: $FIX  ($TASK)"
echo "work:    $WORK"
echo "model:   $MODEL    effort: ${MODEL_EFFORT:-<default>}    mcp: $MCP_SPEC  exec-timeout: ${EXEC_TIMEOUT:-<default 120s>}  (--no-sandbox)"
echo "mcp wire: persistent loopback HTTP on port $MCP_HTTP_PORT (survives Claude quota waits)"
echo "live:    tail -n0 -f $WORK/stream.jsonl | python3 $HERE/stream_filter.py $WORK"
echo "running claude -p ..."

cd "$WORK"

# Allowed toolset. Base set (both tasks) plus session_state/last_error/resolve —
# recovery + debug + selector tools the agent demonstrably reached for in the
# opus48 sweeps. locate_gate_defects (mcp >= 0.3.58) returns the 3D coordinates +
# B-rep identity of a validity-gate failure so the agent repairs the exact spot
# instead of blind (the codex path already sees it; the Claude allowlist lacked
# it). compare verifies fit and, for editing, verifies the edit changed only what
# was asked. load_part/search_library (no library), the 2D-drawing-authoring
# tools, reset, and diagnostics are intentionally excluded as irrelevant here.
# verify_spec/suggest_spec are DELIBERATELY excluded (not just unprompted): across
# two full 81-fixture runs, fixtures where the agent called them scored worse on
# average than fixtures that didn't (-0.037/-0.049 vs -0.009/+0.017), because a
# "conforms: true" result reliably reads to the model as a stop signal regardless
# of prompt caveats saying otherwise (build123d-mcp#362). The Codex driver has no
# equivalent allowlist, so this can only be hard-blocked here.
ALLOWED="mcp__build123d__execute,mcp__build123d__render_view,mcp__build123d__measure,mcp__build123d__compare,mcp__build123d__validate,mcp__build123d__export,mcp__build123d__import_cad_file,mcp__build123d__save_snapshot,mcp__build123d__restore_snapshot,mcp__build123d__find_holes,mcp__build123d__find_hole_patterns,mcp__build123d__find_bosses,mcp__build123d__find_bored_bosses,mcp__build123d__cross_sections,mcp__build123d__session_state,mcp__build123d__last_error,mcp__build123d__resolve,mcp__build123d__locate_gate_defects,mcp__build123d__repair_advice,mcp__build123d__recognise_features"

# Eagerly load the build123d MCP tool schemas instead of deferring them behind
# the ToolSearch tool (Claude Code's default). Deferral cost ~3 ToolSearch calls
# per run, ~36% of them mismatching the tool names — pure wasted turns for a
# fixed, known toolset. See docs.claude.com/en/mcp "Tool Search".
export ENABLE_TOOL_SEARCH=false

quota_reset_epoch() {
  jq -r '
    select(.type == "rate_limit_event" and .rate_limit_info.status == "rejected")
    | .rate_limit_info.resetsAt // 0
  ' "$1" 2>/dev/null | tail -n1
}

quota_rejected() {
  local reset
  reset="$(quota_reset_epoch "$1")"
  [[ "$reset" =~ ^[0-9]+$ && "$reset" -gt 0 ]] || grep -q "You've hit your session limit" "$1"
}

# Space simultaneous resumes from a parallel sweep. The lock protects a shared
# next-start timestamp; it is held for only a few seconds, never for a model run.
quota_resume_gate() {
  local root lock owner next now delay spacing
  root="$(dirname "$REAL_WORK")"
  lock="$root/.claude_quota_resume_lock"
  spacing="${CGB_QUOTA_RESUME_SPACING_SECONDS:-5}"
  [[ "$spacing" =~ ^[0-9]+$ ]] || spacing=5
  while ! mkdir "$lock" 2>/dev/null; do
    owner="$(cat "$lock/pid" 2>/dev/null || true)"
    if [[ "$owner" =~ ^[0-9]+$ ]] && ! kill -0 "$owner" 2>/dev/null; then
      rm -f "$lock/pid" 2>/dev/null || true
      rmdir "$lock" 2>/dev/null || true
      continue
    fi
    sleep 1
  done
  HELD_RESUME_LOCK="$lock"
  printf '%s\n' "$$" > "$lock/pid"
  next="$(cat "$root/.claude_quota_next_resume" 2>/dev/null || echo 0)"
  now="$(date +%s)"
  [[ "$next" =~ ^[0-9]+$ ]] || next=0
  delay=$((next - now))
  (( delay > 0 )) && sleep "$delay"
  now="$(date +%s)"
  printf '%s\n' "$((now + spacing))" > "$root/.claude_quota_next_resume"
  rm -f "$lock/pid"
  rmdir "$lock"
  HELD_RESUME_LOCK=""
}

wait_for_quota_reset() {
  local reset target now remaining step grace
  reset="$1"
  grace="${CGB_QUOTA_RESET_GRACE_SECONDS:-5}"
  [[ "$grace" =~ ^[0-9]+$ ]] || grace=5
  now="$(date +%s)"
  if [[ ! "$reset" =~ ^[0-9]+$ ]]; then
    reset=$((now + 60))
  elif (( reset < now )); then
    reset=$now
  fi
  target=$((reset + grace))
  while true; do
    now="$(date +%s)"
    remaining=$((target - now))
    (( remaining <= 0 )) && break
    step=$remaining
    (( step > 60 )) && step=60
    echo "quota wait: ${remaining}s until retry; fixture workspace and MCP session retained"
    # Mirror a recoverable checkpoint while the live temp workspace stays put.
    cp -a "$WORK"/. "$REAL_WORK"/ 2>/dev/null || true
    sleep "$step"
  done
  quota_resume_gate
}

CLAUDE_ARGS=(
  --model "$MODEL"
  "${EFFORT_ARG[@]}"
  --output-format stream-json --verbose
  --mcp-config mcp_config.json
  --strict-mcp-config
  --dangerously-skip-permissions
  --disable-slash-commands
  --allowedTools "$ALLOWED"
)

: > stream.jsonl
SESSION_ID=""
ATTEMPT=1
while true; do
  ATTEMPT_LOG="attempt.${ATTEMPT}.stream.jsonl"
  set +e
  if [[ -z "$SESSION_ID" ]]; then
    claude -p "$(cat prompt.txt)" "${CLAUDE_ARGS[@]}" > "$ATTEMPT_LOG" 2>&1
  else
    claude -p \
      "Subscription quota interrupted the previous turn. Continue the same fixture from exactly where you stopped. The workspace and build123d MCP session were deliberately kept alive; inspect session_state if needed, then finish validation and export to $OUT." \
      --resume "$SESSION_ID" \
      "${CLAUDE_ARGS[@]}" > "$ATTEMPT_LOG" 2>&1
  fi
  CLAUDE_RC=$?
  set -e

  cat "$ATTEMPT_LOG" >> stream.jsonl
  if [[ -z "$SESSION_ID" ]]; then
    # The init event normally arrives first, but rejected rate-limit events also
    # carry the conversation id. Accept either so an unusually early rejection
    # can still be resumed rather than abandoning the fixture.
    # first(...) stops jq at the first match with no pipe: `jq | head -n1` made jq
    # die of SIGPIPE on a large stream, which under pipefail killed the driver
    # right here (skipping cleanup, the audit and quota resume).
    SESSION_ID="$(jq -Rrn 'first(inputs | fromjson? | select(.session_id? | type == "string") | .session_id) // empty' "$ATTEMPT_LOG" 2>/dev/null || true)"
    [[ "$SESSION_ID" != "null" ]] || SESSION_ID=""
  fi

  if quota_rejected "$ATTEMPT_LOG"; then
    [[ -n "$SESSION_ID" ]] || { echo "ERROR: quota rejection arrived without a resumable Claude session id"; exit 1; }
    RESET_EPOCH="$(quota_reset_epoch "$ATTEMPT_LOG")"
    echo "quota rejected: retaining fixture process, workspace, Claude conversation $SESSION_ID, and live MCP session"
    wait_for_quota_reset "$RESET_EPOCH"
    ATTEMPT=$((ATTEMPT + 1))
    continue
  fi

  rm -f "$ATTEMPT_LOG"
  (( CLAUDE_RC == 0 )) || exit "$CLAUDE_RC"
  break
done

# Report-only recognition audit for editing runs: did the agent use
# recognise_features() and resolve a handle via recognition_faces()?
if [[ "$TASK" == "editing" ]]; then
  python3 "$HERE/audit_claude_recognition.py" stream.jsonl > recognition_audit.json 2>/dev/null || true
  if ! jq -e '.recognition_completed and .resolution_requirement_satisfied' recognition_audit.json >/dev/null 2>&1; then
    echo "NOTE: prompt-guided recognition workflow was not fully used; see recognition_audit.json"
  fi
fi

echo
if [[ -f output.step ]]; then
  echo "output.step produced ($(wc -c < output.step) bytes)"
else
  echo "NO output.step (timeout or the agent stopped early) — see stream.jsonl"
fi
