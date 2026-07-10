#!/usr/bin/env bash
# Codex / GPT-5.5 counterpart of run_fixture.sh: run one drawing->solid fixture
# through the Codex CLI + the same gate-equipped build123d-mcp, producing the same
# output.step + stream.jsonl + filtered.log layout. Same arg interface as the
# Claude driver so run_sweep.sh can dispatch to either by model id.
#
# Usage:
#   harness/run_fixture_codex.sh <fixture_input_dir> <work_dir> [model] [mcp_spec] [exec_timeout]
#
#   fixture_input_dir : holds input.png (generation) and optionally input.step (editing)
#   work_dir          : output.step + stream.jsonl + filtered.log land here
#   model             : codex model id (default: gpt-5.5)
#   mcp_spec          : build123d-mcp version spec for uv tool run (default: build123d-mcp@latest)
#   exec_timeout      : seconds, passed as --exec-timeout (default: server's own, 120s)
#
# Live log (in another terminal):
#   tail -n0 -f <work_dir>/stream.jsonl | python3 harness/stream_filter_codex.py <work_dir>
#
# Requires: `codex` (Codex CLI, logged in) and `uv` on PATH.
set -euo pipefail
FIX="${1:?fixture input dir}"
WORK="${2:?work dir}"
MODEL="${3:-gpt-5.5}"
MCP_SPEC="${4:-build123d-mcp@latest}"
EXEC_TIMEOUT="${5:-}"
HERE="$(cd "$(dirname "$0")" && pwd)"

# Optional reasoning-effort suffix on the model id: "gpt-5.5:high" -> model
# "gpt-5.5" + effort "high" (passed to codex as model_reasoning_effort). No
# suffix => inherit the user's ~/.codex/config.toml default. Effort is a scored
# part of the system, so it's surfaced in the banner and recorded by run_sweep.
MODEL_EFFORT=""
case "$MODEL" in
  *:*) MODEL_EFFORT="${MODEL##*:}"; MODEL="${MODEL%%:*}" ;;
esac

command -v codex >/dev/null || { echo "ERROR: 'codex' (Codex CLI) not on PATH"; exit 1; }
command -v uv    >/dev/null || { echo "ERROR: 'uv' not on PATH"; exit 1; }

# --- Run isolation: execute in a scratch dir OUTSIDE the repo, mirror artifacts back. ---
# The agent is handed its CWD (--cd) and the $OUT path inside the prompt. When those sit
# under the repo, a full-bypass agent can walk up to the repo root and read PRIOR sweeps'
# logs/ and work/ for the SAME fixture id — laundering an earlier run's (often wrong)
# answer and silently breaking run independence (observed on fixture 241, which lifted a
# previous run's parameters and reported them as "confirmed"). Running in a repo-external
# temp dir removes that breadcrumb. We just repoint WORK at the scratch dir: every body
# reference (inputs, prompt.txt, $OUT, stream.jsonl) then lands there, and the EXIT trap
# copies the artifacts back into the real work dir so run_sweep.sh is unchanged. (This is
# not a hard OS sandbox — full bypass is kept for MCP/uv friction — but it closes the
# only path the agent actually used to reach prior runs.)
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
# Build the same prompt the Claude driver uses (identical prompt files — the
# benchmark scores a *system*, and keeping the prompts generic + shared is what
# makes "Codex + build123d-mcp" a fair second system, not a re-tuned one).
if [[ -f "$FIX/edit_description.txt" ]]; then
  cp "$FIX/edit_description.txt" "$WORK"/ 2>/dev/null || true
  cp -R "$FIX/renders" "$WORK"/ 2>/dev/null || true
  python3 -c "import sys,pathlib; t=pathlib.Path(sys.argv[1]).read_text(); print(t.replace('{EDIT}', pathlib.Path(sys.argv[2]).read_text().strip()).replace('{OUTPUT}', sys.argv[3]), end='')" \
    "$HERE/prompt_editing.txt" "$FIX/edit_description.txt" "$OUT" > "$WORK/prompt.txt"
  TASK="editing"
else
  sed "s|{OUTPUT}|$OUT|g" "$HERE/prompt_generation.txt" > "$WORK/prompt.txt"
  TASK="generation"
fi

# The drawing/renders reach the vision model two ways: attached to the initial
# prompt with -i (below), and re-inspectable mid-run via Codex's built-in
# view_image tool (the agent crops with shell + view_image to read small dimension
# callouts) — the Codex analogue of the Claude driver's Read + Bash-crop flow.
# (-i FILE pairs, built as a flat array so empty expands cleanly under set -u)
IMG_ARGS=()
if [[ "$TASK" == "editing" ]]; then
  for v in front top right iso; do
    [[ -f "$WORK/renders/$v.png" ]] && IMG_ARGS+=(-i "$WORK/renders/$v.png")
  done
else
  [[ -f "$WORK/input.png" ]] && IMG_ARGS+=(-i "$WORK/input.png")
fi

echo "fixture: $FIX  ($TASK)"
echo "work:    $WORK"
echo "model:   $MODEL    effort: ${MODEL_EFFORT:-<config default>}    mcp: $MCP_SPEC  exec-timeout: ${EXEC_TIMEOUT:-<default 120s>}  (--no-sandbox)"
echo "images:  ${IMG_ARGS[*]:-<none>}"
echo "live:    tail -n0 -f $WORK/stream.jsonl | python3 $HERE/stream_filter_codex.py $WORK"
echo "running codex exec ..."

cd "$WORK"

# Pre-warm the tool environment so build123d-mcp is installed before Codex's MCP startup timeout
# fires on a cold cache (first-run install can be slow).
uv tool run --python 3.12 "$MCP_SPEC" --version >/dev/null 2>&1 || true

# Codex has no per-call tool allowlist (unlike Claude's --allowedTools); it exposes
# all of build123d-mcp's tools to the model. We launch the server with --no-sandbox
# for the same reason the Claude driver does: trusted, isolated benchmark env, no
# AST-check friction. MCP wiring is via -c TOML overrides (Codex has no
# --mcp-config flag). --json emits the JSONL event stream; full bypass +
# skip-git-repo-check make it run unattended in a non-repo work dir.
# --disable-tool-groups drawing drops the 6-tool 2D drawing-authoring suite
# (irrelevant here, pure schema-context overhead) — since Codex has no allowlist
# to hide them client-side, this server-side flag is the ONLY way to keep them
# out of a codex-driven run. Requires build123d-mcp >= 0.3.68.
# EXEC_TIMEOUT (optional) raises the default 120s execute() timeout — field
# evidence (fixtures 202/240) shows heavy sew/defeature/boolean repairs on large
# imports genuinely need more wall-clock time, and the replay-recovery safety
# net (#361) has its own budget, so avoiding the timeout beats recovering from
# it. Keep it comfortably under tool_timeout_sec below, or Codex's own
# client-side wait gives up first with a less graceful failure.
MCP_ARGS_JSON="\"tool\",\"run\",\"--python\",\"3.12\",\"$MCP_SPEC\",\"--no-sandbox\",\"--disable-tool-groups\",\"drawing\""
[[ -n "$EXEC_TIMEOUT" ]] && MCP_ARGS_JSON="$MCP_ARGS_JSON,\"--exec-timeout\",\"$EXEC_TIMEOUT\""
codex exec \
  --model "$MODEL" \
  ${MODEL_EFFORT:+-c model_reasoning_effort="$MODEL_EFFORT"} \
  --cd "$WORK" \
  --skip-git-repo-check \
  --dangerously-bypass-approvals-and-sandbox \
  --json \
  -c 'mcp_servers.build123d.command="uv"' \
  -c "mcp_servers.build123d.args=[$MCP_ARGS_JSON]" \
  -c 'mcp_servers.build123d.startup_timeout_sec=120' \
  -c 'mcp_servers.build123d.tool_timeout_sec=600' \
  "${IMG_ARGS[@]+"${IMG_ARGS[@]}"}" \
  < prompt.txt > stream.jsonl 2>&1
  # ^ prompt via stdin, NOT a positional arg: codex's -i/--image is greedy variadic
  #   and would otherwise swallow the prompt string as an image path. With no
  #   positional present, codex reads the instructions from stdin (prompt.txt).

echo
if [[ -f output.step ]]; then
  echo "output.step produced ($(wc -c < output.step) bytes)"
else
  echo "NO output.step (the agent stopped early or errored) — see stream.jsonl"
fi
