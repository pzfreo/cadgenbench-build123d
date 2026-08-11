#!/usr/bin/env bash
# Resume an interrupted Claude Code no-MCP fixture without replaying its tokens.
set -euo pipefail

TEMP_WORK="${1:?temporary fixture workdir}"
REAL_WORK="${2:?persistent fixture workdir}"
RESULT_DIR="${3:?result fixture directory}"
MODEL="${4:?model}"
SESSION_ID="${5:?Claude session id}"

HERE="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_BIN="${CLAUDE_BIN:-/home/teleclaude/.npm-global/bin/claude}"
MODEL_EFFORT=""
case "$MODEL" in
  *:*) MODEL_EFFORT="${MODEL##*:}"; MODEL="${MODEL%%:*}" ;;
esac
EFFORT_ARG=()
[[ -n "$MODEL_EFFORT" ]] && EFFORT_ARG=(--effort "$MODEL_EFFORT")

mkdir -p "$REAL_WORK" "$RESULT_DIR"
cd "$TEMP_WORK"
"$CLAUDE_BIN" -p \
  --resume "$SESSION_ID" \
  --model "$MODEL" \
  ${EFFORT_ARG[@]+"${EFFORT_ARG[@]}"} \
  --output-format stream-json --verbose \
  --mcp-config mcp_config.json --strict-mcp-config \
  --dangerously-skip-permissions --disable-slash-commands \
  --allowedTools "Read,Write,Edit,Bash,Glob,Grep" \
  "Continue the CAD task from exactly where you left off. Complete, inspect, and validate output.step. Do not stop merely because the previous transport disconnected." \
  >> stream.jsonl 2>&1

cp -a "$TEMP_WORK"/. "$REAL_WORK"/
if [[ -f "$TEMP_WORK/output.step" ]]; then
  cp "$TEMP_WORK/output.step" "$RESULT_DIR/output.step"
  echo "RESUMED DONE ($(wc -c < "$TEMP_WORK/output.step" | tr -d ' ') bytes)"
else
  echo "RESUMED MISSING output.step"
fi

python3 "$HERE/stream_filter.py" "$REAL_WORK" < "$REAL_WORK/stream.jsonl" >/dev/null 2>&1 || true
