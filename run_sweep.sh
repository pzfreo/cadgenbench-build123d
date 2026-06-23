#!/usr/bin/env bash
# Run a list of CADGenBench fixtures through the harness, optionally in parallel,
# and collect results into the submission layout:
#   results/<run_name>/<id>/output.step
#
# Usage:
#   run_sweep.sh <fixtures_file> <run_name> [model] [mcp_spec] [jobs]
#
#   fixtures_file : one fixture id per line (# comments and blanks ignored)
#   run_name      : names the work/ and results/ subdirectory for this sweep
#   model         : agent model id             (default: claude-opus-4-8).
#                   claude-* routes to Claude Code; any other id (e.g. gpt-5.5)
#                   routes to the Codex CLI driver. Both produce one output.step.
#   mcp_spec      : build123d-mcp spec for uvx  (default: build123d-mcp@latest;
#                   pass "build123d-mcp @ file:///path" to test a local build)
#   jobs          : fixtures to run concurrently (default 4). Each fixture has
#                   its own work dir, so parallel runs never collide. If you hit
#                   API rate limits (429s), lower this.
#
# Watch one fixture live:
#   tail -n0 -f work/<run>/<id>_run/stream.jsonl | python3 harness/stream_filter.py work/<run>/<id>_run
#
# Requires: uvx + uv, and the agent CLI for your chosen model — claude (Claude
# Code) for claude-* models, or codex (Codex CLI, logged in) for others.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

# ---- single-fixture worker (invoked by the parallel fan-out below) ----
if [[ "${1:-}" == "--one" ]]; then
  fid="$2"; RUN="$3"; MODEL="$4"; MCP_SPEC="$5"
  WORKROOT="$HERE/work/$RUN"; RESULTS="$HERE/results/$RUN"
  IN="$WORKROOT/${fid}_in"; WORK="$WORKROOT/${fid}_run"
  mkdir -p "$WORKROOT" "$RESULTS/$fid"
  echo "[$fid] start"
  if ! uv run --with huggingface_hub python "$HERE/harness/fetch_fixture.py" "$fid" "$IN" \
        > "$WORKROOT/${fid}.fetch.log" 2>&1; then
    echo "[$fid] FETCH FAILED (see work/$RUN/${fid}.fetch.log)"; exit 0
  fi
  # Pick the agent driver by model id: claude-* -> Claude Code, anything else
  # (e.g. gpt-5.5) -> Codex CLI. Both drivers take the same args and produce the
  # same output.step / stream.jsonl / filtered.log layout.
  case "$MODEL" in
    claude*|"") DRIVER="run_fixture.sh";      FILTER="stream_filter.py" ;;
    *)          DRIVER="run_fixture_codex.sh"; FILTER="stream_filter_codex.py" ;;
  esac
  "$HERE/harness/$DRIVER" "$IN" "$WORK" "$MODEL" "$MCP_SPEC" \
        > "$WORKROOT/${fid}.driver.log" 2>&1 || echo "[$fid] run_fixture returned nonzero"
  # Save a readable, committable run log as verification evidence. stream_filter
  # drops the init event (paths/session id) and image blocks, and truncates — so
  # filtered.log is safe to publish. Raw stream.jsonl stays in work/ (gitignored:
  # huge, embeds base64 renders).
  if [[ -f "$WORK/stream.jsonl" ]]; then
    mkdir -p "$HERE/logs/$RUN"
    python3 "$HERE/harness/$FILTER" "$WORK" < "$WORK/stream.jsonl" >/dev/null 2>&1 || true
    [[ -f "$WORK/filtered.log" ]] && cp "$WORK/filtered.log" "$HERE/logs/$RUN/${fid}.log"
  fi
  if [[ -f "$WORK/output.step" ]]; then
    cp "$WORK/output.step" "$RESULTS/$fid/output.step"
    echo "[$fid] DONE ($(wc -c < "$WORK/output.step" | tr -d ' ') bytes)"
  else
    echo "[$fid] MISSING output.step"
  fi
  exit 0
fi

# ---- sweep driver ----
LIST="${1:?fixtures list file (one id per line)}"
RUN="${2:?run name}"
MODEL="${3:-claude-opus-4-8}"
MCP_SPEC="${4:-build123d-mcp@latest}"
JOBS="${5:-4}"

# A reasoning-effort suffix on the model id ("gpt-5.5:high", codex only) is part
# of the scored system but otherwise silently inherits ~/.codex/config.toml.
# Split it out so run_meta pins both the base model and the effort. The full
# token (with suffix) is still what's passed to the driver, which re-splits it.
REASONING_EFFORT="config-default"
MODEL_ID="$MODEL"
case "$MODEL" in
  claude*|"") : ;;
  *:*) REASONING_EFFORT="${MODEL##*:}"; MODEL_ID="${MODEL%%:*}" ;;
esac

mkdir -p "$HERE/work/$RUN" "$HERE/results/$RUN"
FIXES="$(sed 's/#.*//' "$LIST" | tr -d '[:blank:]' | grep -E '^[0-9]+$' || true)"
n="$(printf '%s\n' "$FIXES" | grep -c . || true)"
[[ "$n" -gt 0 ]] || { echo "no fixture ids in $LIST"; exit 1; }

# ---- provenance stamp: tie this run to the exact code that produced it ----
GIT_COMMIT="$(git -C "$HERE" rev-parse HEAD 2>/dev/null || echo unknown)"
GIT_BRANCH="$(git -C "$HERE" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
GIT_DIRTY=false
if [[ -n "$(git -C "$HERE" status --porcelain 2>/dev/null)" ]]; then
  # porcelain catches untracked files too, which `git diff` misses
  GIT_DIRTY=true
  git -C "$HERE" diff HEAD > "$HERE/results/$RUN/uncommitted.patch" 2>/dev/null || true
fi
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
FIX_JSON="$(printf '%s\n' "$FIXES" | awk 'NF{if(c++)printf ",";printf "\"%s\"",$0}')"
# Resolve the spec to the actual installed version (e.g. build123d-mcp@latest -> 0.3.52)
# so provenance pins a concrete version, not a moving '@latest'.
MCP_VERSION="$(uvx --python 3.12 "$MCP_SPEC" --version 2>/dev/null | awk '{print $NF}' || true)"
[[ -n "$MCP_VERSION" ]] || MCP_VERSION="unknown"
cat > "$HERE/results/$RUN/run_meta.json" <<JSON
{
  "run": "$RUN",
  "timestamp_utc": "$TS",
  "model": "$MODEL_ID",
  "reasoning_effort": "$REASONING_EFFORT",
  "mcp_spec": "$MCP_SPEC",
  "mcp_version": "$MCP_VERSION",
  "git_commit": "$GIT_COMMIT",
  "git_branch": "$GIT_BRANCH",
  "git_dirty": $GIT_DIRTY,
  "fixture_list": "$LIST",
  "fixtures": [$FIX_JSON]
}
JSON
[[ "$GIT_DIRTY" == true ]] && echo "WARNING: working tree dirty — run_meta records git_dirty=true (+ uncommitted.patch). Commit for clean provenance."

echo "sweep '$RUN': $n fixtures, $JOBS in parallel, model=$MODEL_ID, effort=$REASONING_EFFORT, mcp=$MCP_SPEC"
echo "provenance: $GIT_COMMIT ($GIT_BRANCH, dirty=$GIT_DIRTY) mcp=$MCP_VERSION -> results/$RUN/run_meta.json"
echo

printf '%s\n' "$FIXES" | xargs -P "$JOBS" -I{} bash "$HERE/run_sweep.sh" --one {} "$RUN" "$MODEL" "$MCP_SPEC"

echo
collected="$(find "$HERE/results/$RUN" -name output.step 2>/dev/null | wc -l | tr -d ' ')"
echo "sweep '$RUN' done: $collected/$n collected"
echo "package: uv run --with build123d-mcp --with trimesh --with scipy python package_submission.py results/$RUN"
