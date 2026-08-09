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

OUT="$WORK/output.step"
cp "$FIX/input.png" "$WORK/input.png"
if [[ -f "$FIX/edit_description.txt" ]]; then
  cp "$FIX/input.step" "$WORK/input.step"
  cp "$FIX/edit_description.txt" "$WORK/edit_description.txt"
  cp -R "$FIX/renders" "$WORK/renders" 2>/dev/null || true
  python3 -c "import pathlib,sys; t=pathlib.Path(sys.argv[1]).read_text(); print(t.replace('{EDIT}', pathlib.Path(sys.argv[2]).read_text().strip()).replace('{OUTPUT}', sys.argv[3]), end='')" \
    "$HERE/prompt_editing_nomcp.txt" "$FIX/edit_description.txt" "$OUT" > "$WORK/prompt.txt"
  TASK=editing
else
  sed "s|{OUTPUT}|$OUT|g" "$HERE/prompt_generation_nomcp.txt" > "$WORK/prompt.txt"
  TASK=generation
fi
printf '%s\n' '{"mcpServers":{}}' > "$WORK/mcp_config.json"

uv venv --python 3.12 "$WORK/.venv" >/dev/null
uv pip install --python "$WORK/.venv/bin/python" 'build123d==0.11.1' pillow trimesh >/dev/null

echo "fixture: $FIX  ($TASK, direct build123d; NO MCP)"
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
