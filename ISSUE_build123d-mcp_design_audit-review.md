# Draft issue for `pzfreo/build123d-mcp`

> Could not be filed automatically — this session's GitHub access is scoped to
> `pzfreo/cadgenbench-build123d` only (`Access denied: repository "pzfreo/build123d-mcp"
> is not configured for this session`). Paste the title + body below into a new issue at
> <https://github.com/pzfreo/build123d-mcp/issues/new>, or expand the session scope and
> re-file. Cross-referenced from cadgenbench-build123d#34.

**Repo:** `pzfreo/build123d-mcp`

**Title:**

```
design_audit(): summary over-counts robustness, delta_pct mislabels discrete bumps, budget can starve later params, small-int perturbation floor
```

**Body:**

---

Review of the new `design_audit()` tool (commit b0deea5 / v0.3.60, `tools/design_audit.py` + `_design_audit_subprocess.py`). Overall this is a well-designed, well-tested, paper-faithful addition — the subprocess isolation, incremental atomic salvage, security-config mirroring, and graceful degradations are the hard 80% and they're done right. The notes below are polish; **none breaks correctness**, but #1 and #4 affect what the returned `summary` *claims* and whether multi-param audits actually complete, so they're worth folding in before the release.

### 1. Inconclusive (reassigned) params are counted as "robust"
`_format` computes `robust = n_audited - brittle_count`. A `reassigned` parameter's perturbation rewrites only the *first* top-level assignment (`_rewrite`), which the later assignment overwrites, so its rebuild equals baseline → never `brittle` → silently added to `robust`. It's correctly flagged with a per-param `note`, but a caller reading `summary.robust` is over-reassured.

**Suggest:** add an `inconclusive` bucket so `robust + brittle + inconclusive == audited`, and exclude reassigned params from `robust`.

### 2. `delta_pct` mislabels discrete integer bumps
For a count `4 → 5` (the `int(round(...)) == value → value + sign` discrete floor in `_perturbations`), the entry reports `delta_pct: 10` though the realized change is +25%. `volume_delta_pct` is computed from real volume so it's correct; only the nominal label is off.

**Suggest:** report the realized percentage, or rename the field to `epsilon_pct` and add a separate `actual_delta_pct`.

### 3. Small integer counts can perturb to 0 / negative
`n = 1`, −ε → `int(round(0.9)) == 1` → `value + (-1)` → `0`. A count of `0` can empty a pattern / `range(0)` and fail the gate, flagging brittleness for what is really a "remove the feature" edit, not a ±ε edit — a potential false positive on legitimately robust count params.

**Suggest:** clamp discrete count perturbations to `>= 1`, or annotate the entry when the discrete floor was hit so the caller can discount it.

### 4. One slow rebuild can starve the rest of the audit
`per_run_cap` is passed as `budget` (= `op_budget`, default 120) while the subprocess soft budget `budget_s` is ~95s, so `cap() = max(3, min(per_run_cap, remaining())) = remaining()`. A single heavy first parameter can consume the whole soft budget, leaving later params unaudited (salvage then yields only the baseline). Because params are audited in source order, ordering decides who gets probed.

**Suggest:** give each param a share floor (e.g. `budget_s / n_params`) so a late brittle param still gets a shot; and skip the guaranteed-no-op rebuilds for `reassigned` params (ties to #1) to reclaim budget.

### 5. Computed / derived parameters are invisible to Θ (scope note)
Only literal-valued top-level names are surfaced, so `radius = diameter / 2` or `thickness = 2 * wall` never appear as knobs (the paper's Θ includes derived params). Perturbing the upstream *literal* flows through correctly, so this is a reasonable scope choice — but a design's most load-bearing knob is sometimes a derived one. Worth a one-line "known limitation" in the docstring.

### Minor: doc-vs-code mismatch in the PR summary
The PR summary mentions a "topology insight — large volume changes from legitimate count params reported as info, not brittle." The code doesn't classify that: brittleness is purely gate-based and `volume_delta_pct` is just reported as a number. The simpler behavior is fine — the summary just oversells it.

---
Context: I reviewed this as a downstream consumer (the CADGenBench build123d submission pipeline). Happy to send a PR for #1 + #4 if useful.
</content>
