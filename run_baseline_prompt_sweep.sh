#!/usr/bin/env bash
# Run the official CADGenBench baseline prompt through the subscription-backed
# Claude Code harness (direct build123d, no MCP). Arguments mirror run_sweep.sh.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export CGB_PROMPT_STYLE=official-baseline
exec "$HERE/run_sweep.sh" "$@"
