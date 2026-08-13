#!/usr/bin/env bash
# Official CADGenBench generation prompt with a deliberately narrow MCP
# execution surface. Arguments mirror run_sweep.sh.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export CGB_PROMPT_STYLE=official-baseline-minimal-mcp
exec "$HERE/run_sweep.sh" "$@"
