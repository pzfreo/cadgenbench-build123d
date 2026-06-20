#!/usr/bin/env bash
# Run a list of CADGenBench fixtures through the harness and collect the results
# into the submission layout: results/<run_name>/<id>/output.step
#
# Usage:
#   run_sweep.sh <fixtures_file> <run_name> [model] [mcp_spec]
#
#   fixtures_file : one fixture id per line (blank lines and #comments ignored);
#                   e.g. splits/test.txt
#   run_name      : names the work/ and results/ subdirectory for this sweep
#   model         : claude model id        (default: claude-opus-4-8)
#   mcp_spec      : build123d-mcp spec for uvx (default: build123d-mcp@latest;
#                   pass "build123d-mcp @ file:///path/to/build123d-mcp" to test
#                   an unreleased local build)
#
# Per-fixture failures do not abort the sweep — a missing output.step is recorded
# as a gap and reported by package_submission.py.
#
# Requires: `claude` (Claude Code), `uvx`, and `uv` on PATH.
set -uo pipefail
LIST="${1:?fixtures list file (one id per line)}"
RUN="${2:?run name}"
MODEL="${3:-claude-opus-4-8}"
MCP_SPEC="${4:-build123d-mcp@latest}"
HERE="$(cd "$(dirname "$0")" && pwd)"

WORKROOT="$HERE/work/$RUN"
RESULTS="$HERE/results/$RUN"
mkdir -p "$WORKROOT" "$RESULTS"

total=0; collected=0; missing=0
while read -r fid; do
  fid="${fid%%#*}"; fid="$(echo "$fid" | tr -d '[:space:]')"
  [[ -z "$fid" ]] && continue
  total=$((total+1))
  IN="$WORKROOT/${fid}_in"; WORK="$WORKROOT/${fid}_run"
  echo "==================== fixture $fid ===================="
  if ! uv run --with huggingface_hub python "$HERE/harness/fetch_fixture.py" "$fid" "$IN"; then
    echo "  fetch failed for $fid — skipping"; missing=$((missing+1)); continue
  fi
  "$HERE/harness/run_fixture.sh" "$IN" "$WORK" "$MODEL" "$MCP_SPEC" || echo "  run_fixture returned nonzero for $fid"
  mkdir -p "$RESULTS/$fid"
  if [[ -f "$WORK/output.step" ]]; then
    cp "$WORK/output.step" "$RESULTS/$fid/output.step"
    collected=$((collected+1)); echo "  collected -> results/$RUN/$fid/output.step"
  else
    missing=$((missing+1)); echo "  MISSING output.step for $fid"
  fi
done < "$LIST"

echo
echo "sweep '$RUN' done: $collected/$total collected, $missing missing"
echo "next: uv run --with build123d-mcp --with trimesh --with scipy \\"
echo "        python package_submission.py results/$RUN"
