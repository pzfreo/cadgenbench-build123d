#!/usr/bin/env bash
# Run one CADGenBench fixture through Google Antigravity CLI (agy) and the
# gate-equipped build123d MCP server. The sweep driver configures the pinned
# MCP command once before parallel workers start.
#
# Each fixture deliberately uses two headless turns in one conversation:
#   1. read-only Plan mode inspects the inputs and commits to an approach;
#   2. accept-edits mode resumes that conversation and executes the plan.
#
# Usage:
#   harness/run_fixture_agy.sh <fixture_input_dir> <work_dir> \
#       [agy/model-id] [mcp_spec] [exec_timeout]
set -euo pipefail

FIX="${1:?fixture input dir}"
WORK="${2:?work dir}"
MODEL="${3:-agy/gemini-3.7-flash-high}"
MCP_SPEC="${4:-build123d-mcp==0.3.83}"
EXEC_TIMEOUT="${5:-}"
HERE="$(cd "$(dirname "$0")" && pwd)"

MODEL="${MODEL#agy/}"
MODEL_EFFORT=""
case "$MODEL" in
  *:*) MODEL_EFFORT="${MODEL##*:}"; MODEL="${MODEL%%:*}-$MODEL_EFFORT" ;;
  *-low) MODEL_EFFORT="low" ;;
  *-medium) MODEL_EFFORT="medium" ;;
  *-high) MODEL_EFFORT="high" ;;
esac

command -v agy >/dev/null || { echo "ERROR: 'agy' not on PATH"; exit 1; }
command -v uv  >/dev/null || { echo "ERROR: 'uv' not on PATH"; exit 1; }
command -v jq  >/dev/null || { echo "ERROR: 'jq' not on PATH"; exit 1; }
[[ "$MCP_SPEC" != "none" ]] || { echo "ERROR: the Agy driver requires build123d MCP"; exit 1; }
EFFORT_ARGS=()
[[ -n "$MODEL_EFFORT" ]] && EFFORT_ARGS=(--effort "$MODEL_EFFORT")

# Keep each conversation outside the repository so it cannot discover prior
# attempts for the same fixture. Mirror all artifacts back on exit.
REAL_WORK="$WORK"
mkdir -p "$REAL_WORK"
REAL_WORK="$(cd "$REAL_WORK" && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/cgb_fixture.XXXXXX")"
cleanup() {
  cp -a "$WORK"/. "$REAL_WORK"/ 2>/dev/null || true
  rm -rf "$WORK"
}
trap cleanup EXIT

cp "$FIX"/input.png "$WORK"/ 2>/dev/null || true
cp "$FIX"/input.step "$WORK"/ 2>/dev/null || true
OUT="$WORK/output.step"

if [[ -f "$FIX/edit_description.txt" ]]; then
  cp "$FIX/edit_description.txt" "$WORK"/
  cp -R "$FIX/renders" "$WORK"/ 2>/dev/null || true
  python3 -c "import sys,pathlib; t=pathlib.Path(sys.argv[1]).read_text(); print(t.replace('{EDIT}', pathlib.Path(sys.argv[2]).read_text().strip()).replace('{OUTPUT}', sys.argv[3]), end='')" \
    "$HERE/prompt_editing.txt" "$FIX/edit_description.txt" "$OUT" > "$WORK/prompt.txt"
  TASK="editing"
else
  sed "s|{OUTPUT}|$OUT|g" "$HERE/prompt_generation.txt" > "$WORK/prompt.txt"
  TASK="generation"
fi

echo "fixture: $FIX  ($TASK)"
echo "work:    $WORK"
echo "model:   $MODEL    effort: ${MODEL_EFFORT:-model default}    driver: agy $(agy --version 2>/dev/null || echo unknown)"
echo "mcp:     $MCP_SPEC  exec-timeout: ${EXEC_TIMEOUT:-configured by sweep}"
echo "mode:    read-only plan, then resumed accept-edits execution"

cd "$WORK"
uv tool run --python 3.12 "$MCP_SPEC" --version >/dev/null 2>&1 || true

PLAN_INSTRUCTION="The only project workspace for this fixture is $WORK. First inspect its input.png and, when present, input.step, edit_description.txt, and renders/ using read-only file and image tools. Then make a concise, concrete CAD implementation plan. Resolve the visible dimensions, target features, construction order, validation checks, and final export path. This is the planning turn: do not modify files or geometry yet. Do not delegate to subagents and do not use the browser or web. Return a final plan that can be executed immediately in the next turn."
PROMPT_TEXT="$(< prompt.txt)"

agy --print "$PLAN_INSTRUCTION

$PROMPT_TEXT" \
  --mode plan \
  --dangerously-skip-permissions \
  --add-dir "$WORK" \
  --model "$MODEL" \
  "${EFFORT_ARGS[@]}" \
  --output-format stream-json \
  --print-timeout 90m \
  > plan.stream.jsonl

CONVERSATION_ID="$(jq -r 'select(.event == "init") | .conversation_id' plan.stream.jsonl | head -n1)"
[[ -n "$CONVERSATION_ID" && "$CONVERSATION_ID" != "null" ]] || {
  echo "ERROR: Agy planning turn did not return a conversation id"
  cp plan.stream.jsonl stream.jsonl
  exit 1
}

cp plan.stream.jsonl stream.jsonl
EXECUTE_INSTRUCTION="Execute the plan now. Work autonomously in this directory, using the build123d MCP tools for all CAD construction, inspection, validation, and export. Do not merely restate or revise the plan. Do not delegate to subagents and do not use the browser or web. Continue until a validate/export-clean STEP exists exactly at $OUT; for an editing fixture, preserve the banked baseline unless a changed candidate is proven better."

agy --print "$EXECUTE_INSTRUCTION" \
  --conversation "$CONVERSATION_ID" \
  --mode accept-edits \
  --dangerously-skip-permissions \
  --add-dir "$WORK" \
  --model "$MODEL" \
  "${EFFORT_ARGS[@]}" \
  --output-format stream-json \
  --print-timeout 90m \
  >> stream.jsonl

echo
if [[ -f output.step ]]; then
  echo "output.step produced ($(wc -c < output.step) bytes)"
else
  echo "NO output.step — see stream.jsonl"
fi
