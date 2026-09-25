#!/usr/bin/env bash
set -euo pipefail

# Regression: run_fixture.sh must survive a large Claude stream. Its session-id
# probe (`jq ... | head -n1`) used to SIGPIPE under `set -o pipefail`, killing
# the driver right after Claude returned: no attempt-log cleanup, no
# recognition audit, and no quota-resume handling.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/cgb_large_stream_test.XXXXXX")"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

mkdir -p "$TMP/in" "$TMP/out"
: > "$TMP/in/input.step"
echo "Increase the bore diameter from 10 mm to 12 mm." > "$TMP/in/edit_description.txt"

PATH="$ROOT/tests/fake-bin:$PATH" FAKE_CLAUDE_MODE=large-success \
  "$ROOT/harness/run_fixture.sh" \
  "$TMP/in" "$TMP/out" claude-fable-5-1:high build123d-mcp==0.3.83 240 \
  > "$TMP/driver.log" 2>&1

test -s "$TMP/out/output.step"
grep -q 'output.step produced' "$TMP/driver.log"
test -s "$TMP/out/recognition_audit.json"
! ls "$TMP/out"/attempt.*.stream.jsonl >/dev/null 2>&1
echo "driver large-stream regression: PASS"
