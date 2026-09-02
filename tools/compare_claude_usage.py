#!/usr/bin/env python3
"""Extract safe, aggregate Claude usage data from paired sweep streams.

Only the final ``result`` event is read. Prompts, responses, tool arguments, and
other stream content are never copied to the generated artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


TOKEN_FIELDS = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
)


def load_results(root: Path) -> dict[int, dict[str, int | float]]:
    results: dict[int, dict[str, int | float]] = {}
    for stream in root.glob("*_run/stream.jsonl"):
        fixture = int(stream.parent.name.removesuffix("_run"))
        result = None
        with stream.open(encoding="utf-8") as handle:
            for line in handle:
                event = json.loads(line)
                if event.get("type") == "result":
                    result = event
        if result is None:
            continue
        usage = result.get("usage", {})
        row: dict[str, int | float] = {
            field: int(usage.get(field, 0)) for field in TOKEN_FIELDS
        }
        row.update(
            cost_usd=float(result.get("total_cost_usd", 0)),
            duration_ms=int(result.get("duration_ms", 0)),
            turns=int(result.get("num_turns", 0)),
        )
        row["all_reported_tokens"] = sum(int(row[field]) for field in TOKEN_FIELDS)
        results[fixture] = row
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mcp_root", type=Path)
    parser.add_argument("baseline_root", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    mcp = load_results(args.mcp_root)
    baseline = load_results(args.baseline_root)
    fixtures = sorted(mcp.keys() & baseline.keys())
    args.output_dir.mkdir(parents=True, exist_ok=True)

    metrics = (*TOKEN_FIELDS, "all_reported_tokens", "cost_usd", "duration_ms", "turns")
    csv_path = args.output_dir / "paired_fixture_usage.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        fields = ["fixture"] + [f"{arm}_{metric}" for arm in ("baseline", "mcp") for metric in metrics]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for fixture in fixtures:
            row: dict[str, int | float] = {"fixture": fixture}
            for arm, source in (("baseline", baseline), ("mcp", mcp)):
                for metric in metrics:
                    value = source[fixture][metric]
                    row[f"{arm}_{metric}"] = f"{value:.9f}" if metric == "cost_usd" else value
            writer.writerow(row)

    totals = {
        arm: {metric: sum(source[fixture][metric] for fixture in fixtures) for metric in metrics}
        for arm, source in (("baseline", baseline), ("mcp", mcp))
    }
    summary = {
        "schema_version": 1,
        "paired_fixture_count": len(fixtures),
        "paired_fixtures": fixtures,
        "missing_baseline_raw_fixtures": sorted(mcp.keys() - baseline.keys()),
        "method": "final_result_event_usage_only",
        "totals": totals,
        "baseline_overhead_percent": {
            metric: (totals["baseline"][metric] / totals["mcp"][metric] - 1) * 100
            for metric in metrics
            if totals["mcp"][metric]
        },
    }
    (args.output_dir / "paired_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
