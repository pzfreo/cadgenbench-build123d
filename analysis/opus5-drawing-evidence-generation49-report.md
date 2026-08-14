# Opus 5 drawing-evidence MCP generation sweep

**Date:** 2026-08-14

**Verified report:** [CADGenBench report](https://huggingai4engineering-cadgenbench.hf.space/reports/pzfreo_pzfreo-opus5-xhigh-mcp-drawing-evidence-_20260814-072949.html)

**Model:** Claude Opus 5, `xhigh` reasoning effort

**Generation system:** official CADGenBench baseline prompt plus a narrow build123d-mcp drawing-evidence and CAD-execution surface

**Editing system:** unchanged outputs from the earlier Opus 5 + build123d-mcp 0.3.81 run

## Executive summary

The drawing-evidence workflow achieved a verified full-benchmark score of **0.677**, compared with **0.639** for the previous Opus 5 MCP run and **0.627** for the official-prompt Opus 5 no-MCP baseline. Because the 32 editing outputs were reused unchanged, the entire improvement over the previous MCP result came from the new 49-fixture generation sweep.

Generation improved from 0.596 to **0.658** versus the previous MCP run and from 0.631 to **0.658** versus no-MCP. The principal improvements were shape similarity and interface match; aggregate topology was effectively unchanged from no-MCP. The new workflow also raised the median substantially and reduced the number of weak fixtures.

The logs show that MCP helped primarily by making drawing regions and CAD execution reliably available while leaving the modelling strategy to Opus. It did not replace model reasoning or custom Python image analysis. In particular, `calibrate_drawing` was never called. The remaining failures are dominated by semantic interpretation errors: precise, valid, well-measured models that are nevertheless the wrong part.

## Verified score comparison

| Metric | Drawing-evidence MCP | Previous MCP | No MCP |
|---|---:|---:|---:|
| Full benchmark | **0.677** | 0.639 | 0.627 |
| Generation mean | **0.658** | 0.596 | 0.631 |
| Generation median | **0.713** | 0.620 | 0.595 |
| Shape similarity mean | **0.656** | 0.566 | 0.615 |
| Interface match mean | **0.634** | 0.594 | 0.605 |
| Topology match mean | 0.712 | 0.659 | **0.713** |
| Generation fixtures below 0.60 | **19** | 24 | 25 |
| Generation fixtures at least 0.90 | 7 | 4 | **8** |

Against the previous MCP run, drawing-evidence MCP won 37 of 49 generation fixtures and lost 12, gaining 3.073 total generation-score points, or 0.063 per fixture.

Against no-MCP, it won 25 and lost 24, gaining 1.343 total points, or 0.027 per fixture. No-MCP fixture 137 scored zero and accounts for 0.755 of that gain. Excluding 137, drawing-evidence MCP still leads by approximately 0.012 per remaining fixture. The stronger median and six fewer sub-0.60 fixtures show that the result is not solely an invalid-baseline outlier.

## Tool use and workflow behavior

Across the completed generation runs:

- `prepare_drawing` was normally called once per fixture.
- `crop_drawing` was used heavily, commonly 12–18 times.
- `calibrate_drawing` was called **zero times**.
- Opus continued to write Bash/Python image-analysis scripts for thresholding, line extraction, Hough detection, coordinate grids, radial profiles and numerical fitting.
- `execute_file`, `render_view`, `validate` and `export` supplied the persistent CAD loop.

The new tools therefore contributed as evidence-routing and execution infrastructure, not as an autonomous drawing interpreter.

### Visual-investigation sweet spot

For the 47 fixtures with clean terminal telemetry, crop usage was nonlinear:

| Crop calls | Mean score | Mean difference vs no-MCP |
|---|---:|---:|
| 5–12 | 0.508 | -0.002 |
| 12–15 | **0.808** | **+0.122** |
| 15–18 | 0.714 | +0.028 |
| 19–31 | 0.620 | -0.042 |

This is observational rather than causal: hard drawings provoke more inspection. Nevertheless, the logs repeatedly show diminishing returns when additional crops no longer resolve a distinct geometric question.

A longer pre-modelling phase also correlated modestly with lower absolute score. Fixtures with at most 67 tool calls before the first model write averaged 0.695; those with more averaged 0.633. The latter group was more expensive and contained more difficult fixtures, so this should be treated as a diagnostic signal rather than a crop or tool-call limit.

### Iteration and rendering

Render count correlated negatively with final score (Pearson -0.415, Spearman -0.404). This does not imply that rendering causes poor results: difficult and already-wrong models naturally trigger more renders. It does show that repeated viewing did not reliably correct a bad semantic interpretation.

Additional `execute_file` iterations correlated modestly positively with score. Productive iteration changed a concrete geometric hypothesis; unproductive iteration repeatedly rendered or polished approximately the same wrong body family.

## Strong improvements

### Fixture 108: 0.815, +0.638 vs no-MCP

Opus correctly recognized a sheet-metal flat pattern and mapped it into the folded form. Scores were 0.890 shape, 0.647 interface and 1.000 topology. The decisive step was choosing the correct construction family; crops supplied the evidence but did not themselves solve the model.

### Fixture 115: 0.892, +0.421

Opus noticed that two nearly identical views carried different dimension overlays and combined them to isolate real geometry. It calibrated a millimetre grid, reconstructed the sheet-metal part, repaired a self-intersecting curl, and replaced faceted bends with cylindrical surfaces. Scores reached 0.928 shape, 0.878 interface and 0.846 topology.

### Fixture 118: 0.863, +0.437

Programmatic extraction plus section views established that a 10 x 10 feature was a through cut and confirmed the Z levels from sections B-B and C-C. Interface match rose from 0.419 to **0.964**.

### Fixture 149: 0.903, +0.482

Opus solved pocket geometry numerically and recovered clean design parameters: apex radius 60, corner radius 5, and centres 46 apart. Shape reached 0.929, interface rose from 0.068 to 0.829, and topology was perfect.

### Fixture 119: 0.829, +0.234

Topology increased from 0.111 to 1.000, indicating recovery of the correct feature structure rather than only a closer silhouette.

The common successful sequence was:

1. isolate the relevant views and sections;
2. form a semantic body-family hypothesis;
3. solve dimensions or clean design parameters;
4. build a parametric candidate;
5. compare projections and sections;
6. revise a named discrepancy;
7. validate and export.

## Important regressions and failure modes

### Fixture 150: 0.146, -0.631 vs no-MCP

Scores were 0.193 shape, 0.155 interface and 0.033 topology. Opus made 21 crops but only one Bash analysis call and two main executions. It built a plausible valid part with the claimed envelope and 49 holes, but the dominant mass and feature structure were wrong. Bounding-box, feature-table and validity checks created confidence without verifying the interpretation.

### Fixture 130: 0.444, -0.492

Topology remained perfect, but shape fell from 0.849 to 0.232 and interface from 0.990 to 0.378. Precise image calibration could not rescue an incorrect view-to-3D/body interpretation.

### Fixture 135: 0.266, -0.388

The log dismissed a suspicious bounding-box result as a conservative NURBS bound and declared the geometry exact. Verified shape, interface and topology were only 0.257, 0.284 and 0.250. This is a false-confidence and contradictory-evidence-handling failure.

### Fixture 116: 0.274, -0.281

Opus concentrated on matching the plan outline, but interface was 0.206 and topology 0.309. A convincing 2D silhouette masked incorrect sectional/internal mass.

### Fixture 145: 0.388, -0.179

Several renders warned that faces could not be tessellated. Opus continued to use the incomplete renders as comparison evidence. The exported part was valid, but interface remained 0.157 and topology 0.563 versus no-MCP's 1.000.

### Fixture 136: 0.066

This drawing was difficult for every system. Drawing-evidence MCP spent 107 tool calls before modelling yet finished with 0.125 shape, zero interface match and 0.078 topology. This is the clearest example of analysis saturation.

## Cost and efficiency

### New MCP versus previous MCP, all 49 generation fixtures

| Metric | Drawing-evidence MCP | Previous MCP | Difference |
|---|---:|---:|---:|
| API-equivalent cost | $670.62 | $596.67 | +12.4% |
| Summed runtime | 36.34 h | 28.76 h | +26.3% |
| All reported tokens | 669.39M | 664.88M | +0.7% |
| Output tokens | 8.44M | 6.55M | +28.9% |
| Turns | 5,220 | 4,074 | +28.1% |
| Generation score | **0.658** | 0.596 | +10.5% |

Cost per aggregate generation-score point was approximately unchanged: $20.79 for drawing-evidence MCP versus $20.45 previously. The quality gain was therefore accompanied by substantially more runtime, output and interaction.

### New MCP versus no-MCP, matched telemetry set

Complete comparable raw no-MCP telemetry was available for 43 fixtures. On that matched set:

| Metric | Drawing-evidence MCP | No MCP | Difference |
|---|---:|---:|---:|
| API-equivalent cost | **$597.79** | $637.29 | -6.2% |
| Summed runtime | **1,939 min** | 2,105 min | -7.9% |
| All reported tokens | **598.8M** | 654.6M | -8.5% |
| Output tokens | **7.51M** | 7.87M | -4.6% |
| Mean verified score | **0.656** | 0.611 | +0.046 |

This matched-set result supports both a quality and efficiency advantage, but it is not a randomized experiment and should not be extrapolated as a complete-run total. Six fixtures lack directly comparable no-MCP telemetry.

## Conclusions

The experiment validates a narrow, task-specific MCP surface. It also validates source-backed drawing evidence as a useful complement to a frontier model: shape and mating-interface accuracy improved, the median rose sharply, and weak results became less frequent.

It does **not** validate every new API. `calibrate_drawing` was unused, and crop or render volume alone did not predict success. The strongest results came from model-generated analysis techniques combined with correct semantic interpretation and disciplined geometric iteration.

The principal remaining problem is semantic error detection. The system can produce a precise, valid, extensively measured model and still model the wrong object.

## Recommended follow-up experiments

1. **Interpretation checkpoint**
   - Record the body family, view-to-axis mapping, open faces, section-derived internal mass, and at least one rejected alternative before modelling.
   - Test first on 130, 135, 150 and 116.

2. **Evidence ledger instead of arbitrary crop limits**
   - Associate every requested crop with a specific unresolved question.
   - Require contradictory or genuinely new evidence before repeating inspection of the same question.

3. **Projection discrepancy attribution**
   - Report excess/missing occupied regions, silhouette agreement, and mismatched internal openings by view.
   - Avoid a scalar conformance score that could become a false stopping signal.

4. **Render-health gate**
   - Mark a render with missing tessellation as incomplete evidence.
   - Require repair, simplification or an alternative representation before using it as final confirmation.

5. **Selective calibration experiment**
   - Either improve the prompt/schema so `calibrate_drawing` is used on an explicit fixture sample, or remove it from the advertised surface.
   - Measure whether it replaces custom Bash calibration without reducing score.

6. **Matched ablations**
   - Run a small stratified sample with: prepare only; prepare plus crops; crops plus interpretation checkpoint; and full evidence workflow.
   - Compare score, cost, time, pre-model calls and failure type rather than relying only on aggregate leaderboard movement.

## Data caveats

- Correlations are observational and confounded by fixture difficulty.
- Fixtures 111 and 131 exported valid scored geometry but hit a quota boundary during their final response; their score data are valid, while their termination telemetry differs.
- Full new-versus-old-MCP telemetry covers all 49 generation fixtures.
- New-versus-no-MCP efficiency figures use the 43-fixture matched telemetry subset.
- The full submitted editing set was reused unchanged, including editing fixture 202, which scored zero as in the prior MCP report.
