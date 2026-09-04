#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/cgb_recognition_test.XXXXXX")"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

mkdir -p "$TMP/in" "$TMP/out"
: > "$TMP/in/input.png"
: > "$TMP/in/input.step"
printf '%s\n' 'Remove the target hole.' > "$TMP/in/edit_description.txt"

PATH="$ROOT/tests/fake-bin-recognition:$PATH" \
  "$ROOT/harness/run_fixture.sh" \
  "$TMP/in" "$TMP/out" claude-opus-5:xhigh build123d-mcp==0.3.84 240 \
  > "$TMP/driver.log" 2>&1

test -s "$TMP/out/output.step"
jq -e '.recognition_completed and .resolution_requirement_satisfied' \
  "$TMP/out/recognition_audit.json" >/dev/null
grep -q 'exited 1 despite a successful terminal event' "$TMP/driver.log"
grep -q 'edited and exported' "$TMP/out/stream.jsonl"

PATH="$ROOT/tests/fake-bin-recognition:$PATH" \
FAKE_CLAUDE_SKIP_RECOGNITION=1 \
  "$ROOT/harness/run_fixture.sh" \
  "$TMP/in" "$TMP/out-no-recognition" claude-opus-5:xhigh build123d-mcp==0.3.84 240 \
  > "$TMP/driver-no-recognition.log" 2>&1

test -s "$TMP/out-no-recognition/output.step"
jq -e '.recognition_completed == false' \
  "$TMP/out-no-recognition/recognition_audit.json" >/dev/null
grep -q 'prompt-guided recognition workflow was not fully used' \
  "$TMP/driver-no-recognition.log"
echo "Claude recognition flow integration: PASS"
