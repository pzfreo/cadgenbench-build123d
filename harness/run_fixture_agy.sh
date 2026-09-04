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
PROMPT_STYLE="${CGB_PROMPT_STYLE:-default}"
FORCE_RECOGNITION="${CGB_FORCE_RECOGNITION:-0}"
RECOGNITION_POLICY="${CGB_RECOGNITION_POLICY:-default}"
if [[ "$RECOGNITION_POLICY" == "default" && "$FORCE_RECOGNITION" == "1" ]]; then
  RECOGNITION_POLICY="required-in-edit-planning-with-corrective-turn"
fi
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
  case "$PROMPT_STYLE" in
    default|official-baseline-minimal-mcp) EDIT_PROMPT="$HERE/prompt_editing.txt" ;;
    mcp-guided-compact) EDIT_PROMPT="$HERE/prompt_editing_mcp_guided_compact.txt" ;;
    *) echo "ERROR: unsupported CGB_PROMPT_STYLE=$PROMPT_STYLE"; exit 1 ;;
  esac
  python3 -c "import sys,pathlib; t=pathlib.Path(sys.argv[1]).read_text(); print(t.replace('{EDIT}', pathlib.Path(sys.argv[2]).read_text().strip()).replace('{OUTPUT}', sys.argv[3]), end='')" \
    "$EDIT_PROMPT" "$FIX/edit_description.txt" "$OUT" > "$WORK/prompt.txt"
  TASK="editing"
else
  if [[ "$PROMPT_STYLE" == "official-baseline-minimal-mcp" ]]; then
    python3 "$HERE/render_official_baseline_prompt.py" --minimal-mcp > "$WORK/system_prompt.txt"
    python3 - "$FIX/description.yaml" > "$WORK/prompt.txt" <<'PY'
from pathlib import Path
import re
import sys

text = Path(sys.argv[1]).read_text()
match = re.search(r"(?ms)^description:\s*(?:[>|][-+]?\s*)?\n?(.*?)(?=^\S|\Z)", text)
description = " ".join(line.strip() for line in match.group(1).splitlines()) if match else text.strip()
print(description)
print("\nThe engineering drawing is available as `input.png` in the working directory.")
PY
  else
    sed "s|{OUTPUT}|$OUT|g" "$HERE/prompt_generation.txt" > "$WORK/prompt.txt"
  fi
  TASK="generation"
fi

echo "fixture: $FIX  ($TASK)"
echo "work:    $WORK"
echo "model:   $MODEL    effort: ${MODEL_EFFORT:-model default}    driver: agy $(agy --version 2>/dev/null || echo unknown)"
echo "mcp:     $MCP_SPEC  exec-timeout: ${EXEC_TIMEOUT:-configured by sweep}"
echo "mode:    read-only plan, then resumed accept-edits execution"
echo "prompt:  $PROMPT_STYLE"

cd "$WORK"
uv tool run --python 3.12 "$MCP_SPEC" --version >/dev/null 2>&1 || true

PROMPT_TEXT="$(< prompt.txt)"
if [[ "$PROMPT_STYLE" == "official-baseline-minimal-mcp" && "$TASK" == "generation" ]]; then
  PLAN_INSTRUCTION="The only project workspace for this fixture is $WORK. Inspect input.png and call the build123d MCP prepare_drawing tool exactly once near the start. Inspect its labelled overview and only relevant crops with the available image-viewing tool; use crop_drawing for an exact enlarged region when a callout or profile remains ambiguous. Then make a concise, concrete CAD implementation plan covering dimensions, body family, construction order, validation, and the final output.step export. This planning turn may create drawing-evidence PNGs but must not create model.py, modify CAD geometry, or export output.step. Do not delegate to subagents and do not use the browser or web. Return a plan executable immediately in the next turn."
  PROMPT_TEXT="$(< system_prompt.txt)

$(< prompt.txt)"
elif [[ "$TASK" == "editing" && "$RECOGNITION_POLICY" == "required-in-edit-planning-with-corrective-turn" ]]; then
  PLAN_INSTRUCTION="The only project workspace for this fixture is $WORK. Inspect input.png, input.step, edit_description.txt, and renders/ using read-only file and image tools. Import input.step into the build123d MCP as object_name='part', then you MUST call recognise_features(object_name='part') once with families omitted for the compact inventory before manually walking topology. After reading that inventory, call recognise_features again with only the family or families relevant to the requested edit when any are available, and use returned feature records or exact face evidence to resolve the target. An explicit empty family is evidence of a recogniser miss: record it and continue with conventional inspection rather than substituting a nearby feature. Then make a concise, concrete CAD implementation plan covering the confirmed target, dimensions, construction order, validation, and final output.step export. This planning turn may import and inspect geometry but must not modify it or export output.step. Do not delegate to subagents and do not use the browser or web. Do not finish the plan before the required compact-inventory recognise_features call has completed."
elif [[ "$TASK" == "editing" && "$RECOGNITION_POLICY" == "repair-first-then-strict-recognition" ]]; then
  PLAN_INSTRUCTION="The only project workspace for this fixture is $WORK. Inspect input.png, input.step, edit_description.txt, and renders/ using read-only file and image tools. Import input.step as object_name='part' and validate it. If the imported B-rep is not gate-clean, call locate_gate_defects(object_name='part') and repair_advice with the reported defect classes, then make a general defect-class repair plan using topology and geometric evidence rather than brittle face indices. The execution turn will have a fresh MCP session, so do not rely on planning-session objects or snapshots. Plan to establish a repaired baseline that passes validate after STEP export and re-import before calling the unchanged strict recognise_features tool or attempting the requested edit. This planning turn may inspect geometry but must not mutate it or export output.step. Do not delegate to subagents and do not use the browser or web."
else
  PLAN_INSTRUCTION="The only project workspace for this fixture is $WORK. First inspect its input.png and, when present, input.step, edit_description.txt, and renders/ using read-only file and image tools. Then make a concise, concrete CAD implementation plan. Resolve the visible dimensions, target features, construction order, validation checks, and final export path. This is the planning turn: do not modify files or geometry yet. Do not delegate to subagents and do not use the browser or web. Return a final plan that can be executed immediately in the next turn."
fi

agy --print "$PLAN_INSTRUCTION

$PROMPT_TEXT" \
  --mode plan \
  --dangerously-skip-permissions \
  --sandbox \
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

recognition_completed() {
  jq -e 'select(
    .event == "step_update"
    and .step_update.state == "DONE"
    and .step_update.step_type == "tool"
    and (
      .step_update.tool_info.parameters.ToolName == "recognise_features"
      or (.step_update.tool_name // "" | endswith("recognise_features"))
      or (.step_update.tool_info.name // "" | endswith("recognise_features"))
    )
  )' plan.stream.jsonl >/dev/null
}

if [[ "$TASK" == "editing" && "$RECOGNITION_POLICY" == "required-in-edit-planning-with-corrective-turn" ]] && ! recognition_completed; then
  echo "required recognise_features call missing; issuing corrective planning turn"
  agy --print "The required recognition step is still missing. Before finalizing the plan, import input.step through the build123d MCP as object_name='part' if needed, call recognise_features(object_name='part') with families omitted, inspect its compact inventory, and then update the plan. Do not edit geometry or export output.step in this planning turn." \
    --conversation "$CONVERSATION_ID" \
    --mode plan \
    --dangerously-skip-permissions \
    --sandbox \
    --add-dir "$WORK" \
    --model "$MODEL" \
    "${EFFORT_ARGS[@]}" \
    --output-format stream-json \
    --print-timeout 90m \
    >> plan.stream.jsonl
fi

if [[ "$TASK" == "editing" && "$RECOGNITION_POLICY" == "required-in-edit-planning-with-corrective-turn" ]] && ! recognition_completed; then
  echo "ERROR: forced-recognition policy not satisfied after corrective planning turn"
  cp plan.stream.jsonl stream.jsonl
  exit 1
fi

cp plan.stream.jsonl stream.jsonl
if [[ "$PROMPT_STYLE" == "official-baseline-minimal-mcp" && "$TASK" == "generation" ]]; then
  EXECUTE_INSTRUCTION="Execute the plan now. Maintain the complete reproducible candidate in model.py and promote every complete revision with the build123d MCP execute_file tool. Use measure, render_view, and cross_sections only when they answer a specific fidelity question; validate before export, and export the final clean STEP exactly to $OUT. Do not merely restate or revise the plan. Do not delegate to subagents and do not use the browser or web. Continue until a validate/export-clean STEP exists at that exact path."
elif [[ "$TASK" == "editing" && "$RECOGNITION_POLICY" == "required-in-edit-execution" ]]; then
  EXECUTE_INSTRUCTION="Execute the plan now. This execution turn has a fresh build123d MCP session: do not rely on any object, snapshot, face number, or @feature handle from planning. First import input.step as object_name='part', validate it, export the unchanged valid baseline to $OUT, and save a baseline snapshot. Before manually walking topology, you MUST call recognise_features(object_name='part') once with families omitted, then call it with only the relevant supported family or families from the returned targetable inventory. When that targeted call returns candidate features, immediately use recognition_faces('@feature[...]') inside execute() in this same session and operate on or inspect the returned Face objects directly; do not use Python list.index() or assume object identity with part.faces(). If recognition errors or returns no matching feature, record a recogniser miss and use a bounded conventional fallback: after at most eight exploratory execute() calls without a validate-clean candidate, retain the banked baseline. Work autonomously in this directory and use build123d MCP tools for all CAD work. After editing, compare against a freshly imported immutable input, verify that bounding-box changes occur only on axes and by amounts implied by the request, validate, export to exactly $OUT, re-import that STEP, and repeat the invariant check. Reject the candidate and retain the baseline if unrelated extents, components, or protected geometry changed. Do not merely restate or revise the plan. Do not delegate to subagents and do not use the browser or web."
elif [[ "$TASK" == "editing" && "$RECOGNITION_POLICY" == "repair-first-then-strict-recognition" ]]; then
  EXECUTE_INSTRUCTION="Execute the plan now. This execution turn has a fresh build123d MCP session; do not reuse planning-session objects, snapshots, face numbers, or handles. Import input.step as object_name='part' and validate it. If it fails, do not bank or describe that invalid import as a clean baseline. Call locate_gate_defects(object_name='part') and repair_advice using the reported defect classes, then follow the general repair ladder: diagnose exact local topology, make the smallest defensible repair, validate, export the repaired candidate to a temporary STEP, re-import it, and validate the round trip. Reject repairs that materially change the envelope, components, or volume outside the defect tolerance. Use geometric/topological selection on each fresh import rather than fixed face indices. Continue repair work until a gate-clean round-tripped solid exists; do not attempt the requested edit on an invalid baseline. Register the clean repaired solid as object_name='part', save a repaired-baseline snapshot, and export it to $OUT as the safe floor. Only then call the unchanged strict recognise_features(object_name='part') with families omitted and make a targeted family call. If candidates are returned, use recognition_faces('@feature[...]') in execute() in this same session and operate on the returned Face objects directly. Apply the requested edit to the repaired baseline, compare it against that baseline and a freshly imported immutable input, and verify that bounding-box changes occur only on the requested axis and by the requested amount. Validate, export exactly to $OUT, re-import, and validate again before promotion. A changed candidate that fails the round-trip gate must never replace the clean repaired baseline. Do not merely restate the plan, delegate, or use the browser or web."
else
  EXECUTE_INSTRUCTION="Execute the plan now. Work autonomously in this directory, using the build123d MCP tools for all CAD construction, inspection, validation, and export. Do not merely restate or revise the plan. Do not delegate to subagents and do not use the browser or web. Continue until a validate/export-clean STEP exists exactly at $OUT; for an editing fixture, preserve the banked baseline unless a changed candidate is proven better."
fi

agy --print "$EXECUTE_INSTRUCTION" \
  --conversation "$CONVERSATION_ID" \
  --mode accept-edits \
  --dangerously-skip-permissions \
  --sandbox \
  --add-dir "$WORK" \
  --model "$MODEL" \
  "${EFFORT_ARGS[@]}" \
  --output-format stream-json \
  --print-timeout 90m \
  > execute.stream.jsonl

cat execute.stream.jsonl >> stream.jsonl

if [[ "$TASK" == "editing" && ( "$RECOGNITION_POLICY" == "required-in-edit-execution" || "$RECOGNITION_POLICY" == "repair-first-then-strict-recognition" ) ]]; then
  python3 "$HERE/audit_agy_recognition.py" execute.stream.jsonl > recognition_audit.json
  if ! jq -e '.recognition_completed and .resolution_requirement_satisfied' recognition_audit.json >/dev/null; then
    echo "WARNING: execution-phase recognition policy was not fully satisfied; see recognition_audit.json"
  fi
fi

echo
if [[ -f output.step ]]; then
  echo "output.step produced ($(wc -c < output.step) bytes)"
else
  echo "NO output.step — see stream.jsonl"
fi
