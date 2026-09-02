# Gemini via Codex + Vercel Gateway versus Agy

**Engineering report for reuse in another agent/MCP project**  
**Date:** 2 September 2026

## Executive summary

We tested two ways to run Gemini 3.7 Flash as an autonomous, image-aware MCP agent:

1. **Codex CLI through Vercel AI Gateway**, reusing an existing Codex harness.
2. **Google Antigravity CLI (`agy`)**, using Gemini's native agent and MCP path.

Both approaches can work, but they are not operationally equivalent. For a project whose primary target is Gemini and whose tools are already exposed through MCP, **Agy is the recommended default**. It required less protocol adaptation, was substantially faster in this experiment, exposed useful per-step timing, and completed the full 81-task sweep after a quota-aware resume.

Codex through Vercel remains valuable when the project needs one agent harness across multiple model providers, centralized gateway routing or billing, or direct behavioral comparison with existing Codex runs. Its cost is an additional compatibility layer. In this experiment, Codex 0.152.0 serialized MCP tools in a namespace form that the non-OpenAI Responses provider did not accept directly, so we had to flatten and restore the tool schema through a loopback proxy. The six-task smoke run produced four outputs and encountered both long-running agent behavior and provider/gateway failures.

This was an **engineering integration comparison, not a controlled model-quality A/B**. The Codex run used medium reasoning in a single-turn harness; the Agy run used high reasoning with a plan-then-execute conversation.

## Systems tested

| Component | Codex + Vercel | Agy |
|---|---|---|
| Model | `google/gemini-3.7-flash` | `gemini-3.7-flash-high` |
| Reasoning | Medium | High |
| Agent CLI | Codex 0.152.0 | Agy 1.1.23 |
| Provider path | Codex → loopback adapter → Vercel AI Gateway → Vertex/Google | Agy → Google Antigravity managed backend |
| Agent flow | One autonomous turn | Read-only plan, then resumed accept-edits turn |
| MCP transport | Codex MCP namespace flattened into Responses functions | Native Agy MCP dispatch |
| MCP version | `build123d-mcp==0.3.83` | `build123d-mcp==0.3.83` |
| Vision path | Initial `-i` attachments; shell crop + `view_image` | File/image tools; shell crop available inside sandbox |
| Isolation | External temporary working directory; full-bypass Codex process | External temporary working directory plus Agy terminal sandbox |

Codex officially supports custom model providers with a provider `base_url`, an environment-supplied key, and the Responses wire API. Provider settings must be supplied through user-level configuration or command-line overrides rather than project-local configuration. See the [official Codex configuration reference](https://developers.openai.com/codex/config-reference/). Our harness used command-line overrides and `--ignore-user-config`, keeping the gateway experiment separate from the user's normal Codex provider.

## Implementation findings

### Codex through Vercel AI Gateway

The attractive feature of this route is harness reuse. Existing Codex prompts, image attachment, MCP startup, event collection, isolated work directories, packaging and provenance could all be retained. The provider was changed per run rather than globally.

The main integration problem was the MCP wire representation. In the tested Codex release, MCP tools were sent as an OpenAI-specific namespace container. The Vercel/Gemini Responses translation expected ordinary top-level function tools. A loopback-only adapter therefore had to:

- flatten the `build123d` namespace into 32 standard function definitions;
- map returned function calls back to the original namespace and tool name;
- relay streaming responses;
- retry a small set of transient gateway errors; and
- avoid logging request bodies, authorization headers or secrets.

The adapter proved that the route was viable: many requests returned HTTP 200, Gemini called MCP correctly, and four valid outputs were preserved. However, it added another stateful streaming boundary and another retry policy. Relevant implementation files are [run_fixture_codex.sh](harness/run_fixture_codex.sh) and [vercel_codex_mcp_proxy.mjs](harness/vercel_codex_mcp_proxy.mjs).

The observed six-task smoke outcome was:

- **4/6 outputs produced**;
- **4/4 produced outputs passed the local exact proxy gate**;
- editing fixtures that completed had gateway-proxy lifetimes of roughly 15–16 minutes;
- generation fixture 125 completed after a proxy lifetime of about 56 minutes;
- generation fixtures 105 and 115 did not produce outputs before the experiment ended, after proxy lifetimes of about 90 and 155 minutes respectively; and
- fixture 203 produced a valid output, then its final turn failed after Vercel recorded a Vertex 503 followed by a Google fallback 400.

Failure attribution matters:

- The original namespace incompatibility was an **agent-harness/provider interop issue**. The adapter fixed it.
- Repeated `fetch failed`, HTTP 502, Vertex 503 and provider fallback failures were **gateway or backend transport issues**.
- Fixture 115's long image-inspection path, including attempts to view a missing crop, was primarily **agent behavior/harness interaction**, not demonstrated gateway failure.
- A nonzero or failed final turn did not necessarily mean the CAD artifact was bad. Fixture 203 had already exported a valid STEP. The harness was right to preserve artifacts independently of agent exit status.

The smoke run metadata and local validity results are recorded in [run_meta.json](results/gemini37-flash-v0383-medium-smoke6-r1/run_meta.json) and [manifest.json](results/gemini37-flash-v0383-medium-smoke6-r1/manifest.json).

### Agy native Gemini path

Agy accepted the pinned MCP command directly. We configured the MCP server once, then launched one isolated conversation per fixture. Each fixture used two turns:

1. Plan mode inspected the drawing and input files and committed to an implementation approach.
2. Accept-edits mode resumed the same conversation and executed the plan through MCP.

Both turns required `--sandbox`. An early unsandboxed test showed that Plan mode could search outside the fixture directory when broad permissions were enabled. After sandboxing, shell attempts to enumerate the repository failed with `Operation not permitted`, while the MCP subprocess remained usable. Plan mode should therefore be treated as an active tool-capable agent, not as a harmless text-only preprocessor.

Agy's MCP configuration was user-level. That is convenient, but it creates a concurrency risk for unrelated Agy sessions if different projects rewrite the same server entry. A production runner should use a dedicated Agy profile/home if available, or protect MCP configuration changes with a lock.

The six-task high-reasoning smoke run produced **6/6 locally valid outputs**. Its official per-fixture scores were:

| Task | 105 | 115 | 125 | 203 | 209 | 218 |
|---|---:|---:|---:|---:|---:|---:|
| Score | 0.800 | 0.329 | 0.440 | 0.980 | 0.745 | 0.986 |

The conditional six-task mean was **0.713**. Generation averaged **0.523** and editing averaged **0.904**. The published report is the [CADGenBench smoke report](https://huggingai4engineering-cadgenbench.hf.space/reports/pzfreo_agy-gemini37-flash-high-plan-mcp0383-smo_20260901-190641.html). The headline leaderboard-style score on that page is diluted by 75 intentionally missing fixtures, so it should not be used as the six-task mean.

The subsequent full high-reasoning sweep produced **81/81 non-empty STEP files**. The local exact proxy gate passed 80/81; fixture 202 remained a tolerance-sensitive B-rep with fine-mesh open edges. The official scorer confirmed exactly that result: **98.8% validity (80/81)**, with fixture 202 as the sole invalid output.

The [official full-run report](https://huggingai4engineering-cadgenbench.hf.space/reports/pzfreo_build123d-mcp-0-3-83-gemini-flash-3-7_20260902-022750.html) scored **0.5078 overall**, comprising **0.4108 generation** and **0.6564 editing**. It ranked 15th on the leaderboard when checked on 2 September 2026.

| Published full run | Overall | Generation | Editing | Validity |
|---|---:|---:|---:|---:|
| Gemini 3.7 Flash high via Agy | **0.5078** | 0.4108 | 0.6564 | 98.8% |
| Project's GPT-5.6 Sol xhigh | 0.5319 | 0.4507 | 0.6562 | 98.8% |
| Best published GPT-5.6 Sol run | 0.5745 | 0.5010 | 0.6870 | 100% |
| Best Opus 5 run | 0.6771 | 0.6583 | 0.7058 | 98.8% |

Gemini essentially tied the project's GPT-5.6 Sol editing score, trailing by only 0.0241 overall because generation was 0.0399 lower. Against the best published GPT run, Gemini trailed by 0.0902 on generation but only 0.0306 on editing. Against Opus, the corresponding gaps were 0.2474 and 0.0493. The practical optimization target is therefore drawing-to-CAD generation, not the editing workflow.

The repeated six-fixture smoke subset was reasonably stable. Its conditional mean was 0.713 in the smoke submission and 0.721 within the full run. Individual geometry varied, but the small-sample conclusion—weak-to-moderate generation and strong editing—survived the full benchmark.

## Performance and observability

Agy's raw events include `duration_seconds` for completed model responses and tool calls, allowing a useful client-observed split. "AI time" below includes model service, networking and provider queueing; it is not a measurement of Google's private accelerator time.

| Final 81-task Agy run | Generation (49) | Editing (32) | All tasks |
|---|---:|---:|---:|
| Mean fixture wall time | 10.86 min | 6.26 min | **9.04 min** |
| Median fixture wall time | 10.24 min | 4.49 min | **7.91 min** |
| Mean AI-response time | 9.90 min | 3.55 min | 7.39 min |
| Mean tool time | 0.67 min | 2.23 min | 1.29 min |
| AI share of fixture wall time | 91.2% | 56.7% | 81.7% |
| Tool share of fixture wall time | 6.2% | 35.6% | 14.3% |

Total accumulated worker time was **12.21 hours**: 9.98 hours in model responses and 1.74 hours in tools. Generation was overwhelmingly model-latency-bound. Editing spent more time in local geometry operations, so CPU performance matters more there.

Seventeen workers were used on an 18-core M5 Max. The first batch produced 48 outputs in about 35 minutes, then hit Agy's hard individual account quota. The backend supplied a precise reset countdown. At reset, the harness reran only the 33 missing fixtures; all 33 completed in roughly 55 further minutes. Active sweep wall time was therefore about 90 minutes, while end-to-end elapsed time was about 5 hours 51 minutes because of the quota wait.

The quota event was not an MCP or CAD failure. It was an account/backend limit and was operationally recoverable because the sweep was idempotent at fixture granularity.

Codex's retained readable logs did not provide an equivalent AI/tool duration split. The gateway proxy logs did provide request timestamps and routing errors, but proxy lifetime is not the same as model inference time. Future comparisons should normalize event timing at collection time rather than trying to infer it from filtered logs afterward.

## Reliability comparison

| Criterion | Codex + Vercel | Agy |
|---|---|---|
| MCP setup | Required namespace compatibility adapter | Native dispatch |
| Smoke completion | 4/6 outputs | 6/6 outputs |
| Full sweep | Not attempted after smoke instability | 81/81 after quota resume |
| Transport failures | Fetch failures, 502, Vertex 503, fallback 400 observed | No comparable transport cascade observed |
| Capacity failure | No firm conclusion from partial run | Hard individual quota after 48 outputs; deterministic reset |
| Artifact recovery | Valid outputs survived failed/nonzero turns | Fixture-level outputs survived quota boundary |
| Timing telemetry | Incomplete for AI/tool separation | Per-response and per-tool durations available |
| Configuration isolation | Strong: inline provider overrides | MCP server entry is user-level and should be isolated/locked |

The Agy result is stronger operational evidence, but it does not prove that every Agy deployment will be more reliable than every gateway deployment. It shows that, for this model, CLI versions, MCP server and date, native dispatch removed a fragile translation layer and delivered the better outcome.

## Recommendation for another project

Use **Agy by default** when all of the following are true:

- Gemini is the primary model;
- the required tools are available through MCP;
- native Gemini agent behavior is acceptable;
- a subscription/account quota can be monitored and resumed around; and
- project isolation can be enforced with sandboxing and a dedicated MCP configuration context.

Use **Codex through a gateway** when one or more of these benefits outweigh the adapter complexity:

- the same harness must run OpenAI, Google and other providers;
- centralized gateway billing, routing or provider fallback is a firm requirement;
- existing Codex-specific approvals, prompts, event processing or evaluation infrastructure must be retained; or
- the project is explicitly studying harness effects while holding the outer agent runtime constant.

Do not select the gateway route solely because of a temporary price promotion without measuring completed-task cost. This experiment did not retain comparable billing data, and retries, long turns and missing artifacts can erase a nominal token discount.

## Recommended runner architecture

Regardless of agent, use the same durable contract around each task:

1. Create a repository-external temporary workspace containing only task inputs.
2. Pin the exact model, effort, CLI version, MCP package and harness commit.
3. Sandbox every agent phase, including planning.
4. Write the required artifact to one deterministic path.
5. Preserve the artifact even when the agent exits nonzero.
6. Record raw events plus a safe timing/usage summary.
7. Validate the artifact independently of the agent's self-report.
8. Mark a task complete only from artifact presence and validation status.
9. Resume only missing tasks after quota or provider recovery.
10. Separate failure labels into harness, gateway, provider/backend, account quota, MCP/tool and agent-behavior categories.

Before a full sweep, run a canary containing at least three generation and three editing tasks. Generation and editing have materially different latency profiles, and a test containing only one category can give the wrong capacity estimate.

For concurrency, use available cores as an upper bound rather than the only bound. Account quotas, provider burst limits and per-task memory can dominate. High parallelism did not increase total inference spend here, but it consumed the Agy account allowance quickly enough to expose the hard quota during the first batch.

## Bottom line

For this experiment, **Agy was the simpler and more successful Gemini harness**: native MCP, better timing telemetry, 81/81 artifact completion, and a recoverable quota failure. **Codex + Vercel was a workable interoperability path, not the preferred production path**: it reused valuable infrastructure and generated valid artifacts, but required a custom MCP translation proxy and showed more ambiguous failure behavior.

The portable lesson is not that one CLI is universally superior. It is that the provider protocol and tool transport are part of the evaluated system. A model name alone does not determine reliability, speed or quality; the agent runtime, reasoning mode, MCP representation, retry policy, sandbox and resume semantics all belong in the benchmark record.
