# Opus 5 MCP versus official-baseline usage

This report compares the same model and effort (`claude-opus-5`, `xhigh`) in
two CADGenBench runs:

- MCP: `build123d-mcp-v0381-claude-opus-5-xhigh-full-r1`
- no MCP: `opus5-xhigh-official-baseline-prompt-full-r1`

It records usage and elapsed time without publishing prompts, responses, tool
arguments, environment data, credentials, or raw event streams. The reported
cost is the runner's API-equivalent `total_cost_usd`; it is not necessarily the
amount charged under a subscription plan.

## Raw-log paired result (70 fixtures)

The checked-in CSV and JSON were generated from the final `result` event in
each locally retained `stream.jsonl`. Repeated intermediate assistant usage
events were not summed.

| Metric | No MCP | MCP | No-MCP overhead |
|---|---:|---:|---:|
| API-equivalent cost | $776.20 | $628.40 | +23.5% |
| Output tokens | 9.58M | 7.11M | +34.8% |
| All reported tokens | 796.78M | 680.64M | +17.1% |
| Turns | 6,055 | 4,570 | +32.5% |
| Runtime | 2,834.2 min | 2,022.4 min | +40.1% |

`all_reported_tokens` is the sum of input, cache-creation input, cache-read
input, and output tokens. Because it includes cache reads, it must not be
interpreted as newly generated tokens or multiplied by one uniform token
price.

## Recovered checkpoint (9 additional fixtures)

An earlier run-status checkpoint preserved rounded aggregate results for nine
of the eleven fixtures whose no-MCP raw streams were later lost during an
environment reset:

`117, 130, 132, 138, 140, 150, 202, 203, 225`

| Metric | No MCP | MCP | No-MCP overhead |
|---|---:|---:|---:|
| API-equivalent cost | $122.42 | $96.37 | +27.0% |
| Output tokens | 1.37M | 1.08M | +26.2% |
| All reported tokens | 135.67M | 104.07M | +30.4% |
| Runtime | 438 min | 335 min | +31.0% |

The checkpoint also retained individual costs for fixtures 150 ($18.40 versus
$9.27), 203 ($11.98 versus $5.08), and 225 ($6.14 versus $3.46). The remaining
six per-fixture records cannot be reconstructed. These checkpoint values are
therefore evidence-backed but rounded and are deliberately not inserted into
the raw-derived CSV.

## Combined benchmark coverage (79 of 81 fixtures)

Combining the raw-derived 70-fixture totals with the rounded nine-fixture
checkpoint gives:

| Metric | No MCP | MCP | No-MCP overhead |
|---|---:|---:|---:|
| API-equivalent cost | ~$898.62 | ~$724.77 | +24.0% |
| Output tokens | ~10.95M | ~8.19M | +33.7% |
| All reported tokens | ~932.45M | ~784.71M | +18.8% |
| Runtime | ~3,272 min | ~2,357 min | +38.8% |

This covers 97.5% of the 81-fixture benchmark. No direct no-MCP usage data is
available for fixtures 240 and 245, so no exact 81-fixture no-MCP total is
claimed.

## Interpretation and limitations

The observed system-level result is that the MCP run was materially more
efficient. The 70 fully paired raw records show 23.5% lower API-equivalent
cost, 34.8% fewer output tokens, and 40.1% less elapsed time with MCP. The
recovered 79-fixture aggregate supports the same conclusion.

The official submitted geometry reports also show that the additional no-MCP
consumption did not produce a higher overall benchmark score:

| Submitted metric | No MCP | MCP | Difference (MCP - no MCP) |
|---|---:|---:|---:|
| Benchmark score | 0.627 | 0.639 | +0.012 |
| Validity | 75/81 (92.6%) | 80/81 (98.8%) | +5 valid outputs |
| Generation score | 0.631 | 0.596 | -0.035 |
| Editing score | 0.621 | 0.706 | +0.085 |

Sources: [official-baseline/no-MCP report](https://huggingai4engineering-cadgenbench.hf.space/reports/pzfreo_opus5-xhigh-official-baseline-prompt-nom_20260811-034944.html)
and [build123d-MCP report](https://huggingai4engineering-cadgenbench.hf.space/reports/pzfreo_build123d-mcp-v0381-claude-opus-5-xhigh-_20260807-101147.html).

MCP's overall advantage is 0.012 score points and 6.2 percentage points of
validity. The category split is important: no MCP scores 0.035 higher on
generation, while MCP scores 0.085 higher on editing. Consequently the result
supports MCP for the tested end-to-end configuration, especially for editing;
it does not establish that MCP improves every task category.

This is a comparison of the complete run configurations, not a perfectly
isolated causal estimate of MCP alone: the MCP and official-baseline harnesses
also differ in prompt and tool interface. Geometry scores should be evaluated
alongside efficiency before drawing a quality-adjusted conclusion.

## Reproduction

When both local raw-stream directories are available, regenerate the safe
artifacts with:

```sh
python3 tools/compare_claude_usage.py \
  work/build123d-mcp-v0381-claude-opus-5-xhigh-full-r1 \
  work/opus5-xhigh-official-baseline-prompt-full-r1 \
  analysis/opus5-mcp-vs-official-baseline
```

The generator reads only final result records and emits
`paired_fixture_usage.csv` and `paired_summary.json`.
