# Gemini 3.7 Flash vs Opus 5 and GPT-5.6 Sol with MCP

The [Gemini 3.7 Flash high-plan submission](https://huggingai4engineering-cadgenbench.hf.space/reports/pzfreo_build123d-mcp-0-3-83-gemini-flash-3-7_20260902-022750.html) scored **0.5078 overall**, placing it close to the project’s [GPT-5.6 Sol xhigh MCP run](https://huggingai4engineering-cadgenbench.hf.space/reports/pzfreo_gpt-5-6-sol-xhigh-floor-chain-v0379_20260717-045810.html) at **0.5319**: Gemini was effectively tied on editing (0.6564 versus 0.6562) but was 0.0399 behind on generation. The best [Opus 5 xhigh MCP submission](https://huggingai4engineering-cadgenbench.hf.space/reports/pzfreo_pzfreo-opus5-xhigh-mcp-drawing-evidence-_20260814-072949.html) remained clearly ahead at **0.6771**, driven mainly by its substantially stronger 0.6583 generation score; all three systems produced 80 valid models from 81 fixtures.

| System | Overall | Generation | Editing | Validity |
|---|---:|---:|---:|---:|
| Gemini 3.7 Flash, high plan, MCP 0.3.83 via Agy | 0.5078 | 0.4108 | 0.6564 | 80/81 |
| GPT-5.6 Sol, xhigh, MCP 0.3.79 via Codex | 0.5319 | 0.4507 | 0.6562 | 80/81 |
| Opus 5, xhigh, MCP 0.3.81 | 0.6771 | 0.6583 | 0.7058 | 80/81 |

Using GPT-5.6 Sol as the 100% token baseline, Gemini consumed about 16% more tokens per fixture and Opus about 44% more; equivalently, GPT used about 13% fewer than Gemini, while Gemini used about 20% fewer than Opus. These are directional comparisons rather than billing-equivalent measurements: each harness reports caching differently, the Opus usage covers 79 fixtures and belongs to the base MCP run underlying the later composite score, and neither subscription-backed Gemini nor GPT run exposes an actual charge. Although [official OpenAI pricing](https://developers.openai.com/api/docs/pricing) lists GPT-5.6 Sol rates by uncached input, cached input, cache writes, output, and context length, the retained GPT logs merge the required categories, so a defensible dollar comparison cannot be reconstructed; Opus’s ~$724.77 is therefore the only directly recorded API-equivalent cost in this comparison.
