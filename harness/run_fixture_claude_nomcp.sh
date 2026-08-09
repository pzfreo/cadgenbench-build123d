#!/usr/bin/env bash
# Run one generation fixture through Claude Code with direct build123d/Python,
# deliberately without an MCP server. This is the MCP ablation driver.
set -euo pipefail

FIX="${1:?fixture input dir}"
WORK="${2:?work dir}"
MODEL="${3:-claude-opus-5}"
MCP_SPEC="${4:-none}"
EXEC_TIMEOUT="${5:-}"

[[ "$MCP_SPEC" == "none" ]] || { echo "ERROR: no-MCP driver requires mcp_spec=none"; exit 1; }
if [[ -f "$FIX/edit_description.txt" ]]; then
  echo "ERROR: no-MCP ablation driver currently supports generation fixtures only"
  exit 1
fi

MODEL_EFFORT=""
case "$MODEL" in
  *:*) MODEL_EFFORT="${MODEL##*:}"; MODEL="${MODEL%%:*}" ;;
esac
EFFORT_ARG=()
[[ -n "$MODEL_EFFORT" ]] && EFFORT_ARG=(--effort "$MODEL_EFFORT")

HERE="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_BIN="$(command -v claude 2>/dev/null || true)"
if [[ -z "$CLAUDE_BIN" && -x /home/teleclaude/.npm-global/bin/claude ]]; then
  CLAUDE_BIN=/home/teleclaude/.npm-global/bin/claude
fi
[[ -n "$CLAUDE_BIN" ]] || { echo "ERROR: claude executable not found"; exit 1; }
command -v uv >/dev/null || { echo "ERROR: uv executable not found"; exit 1; }

REAL_WORK="$WORK"
mkdir -p "$REAL_WORK"
REAL_WORK="$(cd "$REAL_WORK" && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/cgb_nomcp.XXXXXX")"
trap 'cp -a "$WORK"/. "$REAL_WORK"/ 2>/dev/null || true; rm -rf "$WORK"' EXIT

cp "$FIX/input.png" "$WORK/input.png"
OUT="$WORK/output.step"
sed "s|{OUTPUT}|$OUT|g" "$HERE/prompt_generation_nomcp.txt" > "$WORK/prompt.txt"
printf '%s\n' '{"mcpServers":{}}' > "$WORK/mcp_config.json"

uv venv --python 3.12 "$WORK/.venv" >/dev/null
uv pip install --python "$WORK/.venv/bin/python" 'build123d==0.11.1' pillow trimesh >/dev/null

echo "fixture: $FIX  (generation, direct build123d; NO MCP)"
echo "work:    $WORK"
echo "model:   $MODEL    effort: ${MODEL_EFFORT:-<default>}"
echo "running claude -p without MCP configuration ..."

cd "$WORK"
"$CLAUDE_BIN" -p "$(cat prompt.txt)" \
  --model "$MODEL" \
  ${EFFORT_ARG[@]+"${EFFORT_ARG[@]}"} \
  --output-format stream-json --verbose \
  --mcp-config mcp_config.json \
  --strict-mcp-config \
  --dangerously-skip-permissions \
  --disable-slash-commands \
  --allowedTools "Read,Write,Edit,Bash,Glob,Grep" \
  > stream.jsonl 2>&1

if [[ -f output.step ]]; then
  echo "output.step produced ($(wc -c < output.step) bytes)"
else
  echo "NO output.step — see stream.jsonl"
fi
