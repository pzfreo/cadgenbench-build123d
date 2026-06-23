#!/usr/bin/env bash
# Run a fixture set N times to average out LLM run-to-run variance.
# The benchmark's per-fixture score swings ±0.4-0.5 between identical runs, so the
# whole-benchmark mean has a ~±0.018 run-to-run error bar — a single A/B can't see
# a +0.01-0.02 change. Run each variant >=3x and average (see aggregate.py).
#
#   harness/run_repeated.sh <list> <base_name> [model] [mcp_spec] [jobs] [N]
# Produces results/<base_name>-r1 .. -rN. Package + upload each, then:
#   python harness/aggregate.py <base_name>-r1.txt ... (tables extracted from reports)
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
LIST="${1:?fixture list}"; BASE="${2:?base run name}"
MODEL="${3:-claude-opus-4-8}"; MCP="${4:-build123d-mcp@latest}"; JOBS="${5:-5}"; N="${6:-3}"
echo "repeated run: $N x '$BASE' (model=$MODEL mcp=$MCP jobs=$JOBS) over $LIST"
echo "WARNING: cost is N x a normal sweep. Use a SUBSET list for cheap A/B measurement."
for k in $(seq 1 "$N"); do
  echo "=== repetition $k/$N -> ${BASE}-r${k} ==="
  bash "$HERE/run_sweep.sh" "$LIST" "${BASE}-r${k}" "$MODEL" "$MCP" "$JOBS"
done
echo "done. Package+upload each results/${BASE}-r* , then aggregate the reports."
