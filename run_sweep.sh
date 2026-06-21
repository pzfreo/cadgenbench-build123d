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
#   model         : claude model id            (default: claude-opus-4-8)
#   mcp_spec      : build123d-mcp spec for uvx  (default: build123d-mcp@latest;
#                   pass "build123d-mcp @ file:///path" to test a local build)
#   jobs          : fixtures to run concurrently (default 4). Each fixture has
#                   its own work dir, so parallel runs never collide. If you hit
#                   API rate limits (429s), lower this.
#
# Watch one fixture live:
#   tail -n0 -f work/<run>/<id>_run/stream.jsonl | python3 harness/stream_filter.py work/<run>/<id>_run
#
# Requires: claude (Claude Code), uvx, and uv on PATH.
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
  "$HERE/harness/run_fixture.sh" "$IN" "$WORK" "$MODEL" "$MCP_SPEC" \
        > "$WORKROOT/${fid}.driver.log" 2>&1 || echo "[$fid] run_fixture returned nonzero"
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

mkdir -p "$HERE/work/$RUN" "$HERE/results/$RUN"
FIXES="$(sed 's/#.*//' "$LIST" | tr -d '[:blank:]' | grep -E '^[0-9]+$' || true)"
n="$(printf '%s\n' "$FIXES" | grep -c . || true)"
[[ "$n" -gt 0 ]] || { echo "no fixture ids in $LIST"; exit 1; }

echo "sweep '$RUN': $n fixtures, $JOBS in parallel, model=$MODEL, mcp=$MCP_SPEC"
echo

printf '%s\n' "$FIXES" | xargs -P "$JOBS" -I{} bash "$HERE/run_sweep.sh" --one {} "$RUN" "$MODEL" "$MCP_SPEC"

echo
collected="$(find "$HERE/results/$RUN" -name output.step 2>/dev/null | wc -l | tr -d ' ')"
echo "sweep '$RUN' done: $collected/$n collected"
echo "package: uv run --with build123d-mcp --with trimesh --with scipy python package_submission.py results/$RUN"
