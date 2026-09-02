#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/cgb_quota_test.XXXXXX")"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

mkdir -p "$TMP/in" "$TMP/out"
: > "$TMP/in/input.png"

PATH="$ROOT/tests/fake-bin:$PATH" \
CGB_QUOTA_RESET_GRACE_SECONDS=0 \
CGB_QUOTA_RESUME_SPACING_SECONDS=0 \
  "$ROOT/harness/run_fixture.sh" \
  "$TMP/in" "$TMP/out" claude-fable-5-1:high build123d-mcp==0.3.83 240 \
  > "$TMP/driver.log" 2>&1

test -s "$TMP/out/output.step"
grep -q 'quota rejected: retaining fixture process' "$TMP/driver.log"
grep -q '"status":"rejected"' "$TMP/out/stream.jsonl"
grep -q '"result":"resumed and exported"' "$TMP/out/stream.jsonl"
grep -q 'Uvicorn running on http://127.0.0.1:' "$TMP/out/mcp_http.log"
echo "quota resume integration: PASS"
