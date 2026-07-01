# Paper review: *Arko-T: Text-to-Design Generation for Parametric CAD* — proposed prompt & MCP enhancements

Source: `2606.30429v1` (Wang, Xi, Xiang, Meng, Zhang, Zhou, Liu, Chen; Spatial Design
Intelligence Lab / Wuhan Univ., Jun 2026). Reviewed 2026-07-01.

This is a **proposal**, not an applied change. Prompt edits in this repo are gated
behind a smoke test / repeated-run A/B before a sweep (see `harness/run_repeated.sh`
and the git history — a fidelity lever was already reverted once for a smoke-test
regression). Nothing below touches the live prompts; each lever is written so the
maintainer can cherry-pick it into an A/B run.

---

## 1. TL;DR — what actually transfers

Arko-T is a *training* paper (a 4B model fine-tuned on 1.3M normalized Build123d
programs). Our system is the opposite end: a frontier model + `build123d-mcp` +
generic prompts. So the **training-side** contributions (data curation, LoRA SFT,
corpus normalization) do **not** transfer as methods. Two things transfer strongly:

1. **The design-state formalization `z = (F, Θ, C, H, A)`** — reusable as a
   *code-structure and self-verification target* for our prompts, and as a
   *tool surface* for the MCP server. This is the paper's core idea and it is
   backend-agnostic (their backend is Build123d — the same as ours).
2. **The empirical failure-mode catalog (§5.5)** — the concrete geometry errors a
   Build123d generator makes are the same ones our runs make, and each maps to a
   targeted prompt/MCP lever.

One caveat worth stating up front: the paper's task is **text → design** and
single-part. Our generation task is **drawing(image) → STEP**, and we also run an
**editing** task the paper doesn't cover — though the paper's Future Work explicitly
names "iterative editing … local modifications to an existing design state," which is
exactly our editing prompt. The design-state lens applies to both.

---

## 2. Paper synopsis (the parts we can use)

**Design state (Eq. 2):** a useful CAD output is not just a valid solid; it is
`z = (F, Θ, C, H, A)`:

| Sym | Meaning | Paper's normalization rule (§4.3) |
|-----|---------|-----------------------------------|
| **F** | feature vocabulary (holes, ribs, fillets, shells, patterns) | each feature realized through a *canonical code pattern* |
| **Θ** | named parameters (radii, thicknesses, spacings, counts) | *extracted to a parameter block at the top*, descriptive names + **unit annotations** |
| **C** | constraints/relations (symmetry, coplanarity, spacing) | expressed *explicitly*, not computed implicitly |
| **H** | construction history | consistent order: **sketch → extrude → secondary features → finishing** |
| **A** | attachments (feature→face/edge/plane references) | face/edge references expressed *explicitly*, not by magic coordinates |

**Validity gate (§5.1):** program must (a) execute and (b) yield a *non-empty,
valid, manifold* solid. Identical in spirit to our `validate()`/export gate.

**"Metrics can mask missing features" (§5.1, §6):** CD and IoU "can still score well
when individual features are absent … a part can score well while omitting a rib or a
bolt pattern." Hence they add *feature-realization* checking. Our grader has the same
blind spot — this is the strongest argument for a **feature-realization self-audit**.

**Failure modes that persist (§5.5)** — after all their training:
- **Precise coordinate reasoning** — revolves, sweeps along complex paths.
- **Thin-walled constructions** — "small numerical errors collapse the geometry."
- **Polar patterns** — model must *infer the array axis and count from context*.
- **L2 multi-feature robustness** — their one real weakness vs. Gemini is L2 invalid
  rate (~10 pts). "Robust multi-feature construction" is the open frontier.

**Two prompt registers (§5.1):** *Geo* (lay-user, names dimensions/shapes) vs *Pro*
(expert, ordered construction sequence). Not directly usable — our inputs are
drawings, not text — but see §4 note on the editing prompt.

---

## 3. Insight → repo lever (map)

| Paper insight | Where it bites us | Proposed lever | Kind |
|---|---|---|---|
| Θ: named param block, units | buried inline constants → arithmetic slips, hard self-check | Gen prompt: lift the dimension table into a **named-parameter block** in code | prompt |
| A/C: explicit references & relations | polar/bolt patterns hand-typed → wrong axis/count | Gen prompt: place patterns via `PolarLocations`/`GridLocations` about a *confirmed* axis, not literals | prompt |
| Failure: polar axis/count | §5.5 named failure | MCP: `find_hole_patterns` already exists — prompt to *confirm count+axis* with it before finishing; add axis/count to its report | prompt + MCP |
| Failure: thin-wall collapse | our castings/covers guidance already flags shells, but no way to *measure* min wall | MCP: **`min_wall()` / thinnest-section probe**; prompt to check it before export | MCP + prompt |
| Failure: revolve/sweep coord reasoning | gen prompt's curved-form fallback | Gen prompt: name the *axis/plane* discipline for revolves explicitly | prompt |
| "Metrics mask missing features" | our feature-count priority is right but verified piecemeal | MCP: **`feature_audit()`** one-call feature census; prompt: audit requested-vs-present before export | MCP + prompt |
| H: canonical construction order | implicit in gen prompt | Gen prompt: state the order once, explicitly | prompt (low value) |
| Execution-grounded selection | single-shot per fixture | Harness: **best-of-N by validity + proxy shape**, already half-built (`run_repeated.sh`) | harness |
| Design-state editing (future work) | our editing task | Editing prompt: frame the edit as a *design-state delta* (which of F/Θ/C/H/A changes) | prompt |

---

## 4. Prompt enhancements (concrete, prioritized)

Each is written to drop into an A/B against `splits/dev.txt` via
`harness/run_repeated.sh`. **Fairness note applies to all:** every lever below is a
*generic* fidelity/verification discipline — none encodes a fixture answer, none
games the grader (they change code structure and self-checks, not geometry-for-score).
That is consistent with the repo's "fairness-safe lever" history.

### P1 (generation) — Named-parameter block [highest value, lowest risk]
The prompt already asks for a **text** dimension table (step 1) but lets the model
scatter those numbers as inline constants in `execute()`. Arko-T's Θ rule says: lift
them into a named block *in the code*. Proposed addition to step 1 / the Geometry
rules:

> After the dimension table is written, **define those dimensions as named variables
> at the top of your first `execute()`** (`plate_thickness = 12.0  # mm`,
> `bolt_circle_dia = 64.0  # mm`, `hole_count = 4`) and build every feature by
> referencing them — never re-type a raw number downstream. This makes a mis-keyed
> dimension a one-line fix, lets `measure()` be checked against a *named* target, and
> prevents the same length drifting between two features.

Why it helps (not just tidiness): most of our size/placement misses are *arithmetic*
(a bolt circle radius re-derived twice, a thickness typed as 12 in one cut and 1.2 in
another). A single source of truth removes that class. Fairness-safe: pure code
structure, identical geometry. **Risk:** low; verify it doesn't lengthen runs past
budget.

### P2 (generation) — Patterns as relations, not coordinates [targets §5.5]
Directly attacks the paper's *polar-pattern axis/count* failure and *coordinate
reasoning*. Proposed addition to the "Reproduce repeating-feature fields" rule:

> Place hole/rib/boss fields by their **generating relation**, not by hand-typed
> centres: a bolt circle is `PolarLocations(radius, count)` about the confirmed bore
> axis; a grid is `GridLocations(dx, dy, nx, ny)` about the part centre; a mirrored
> pair is built once and mirrored across the named plane. Read the *count* and the
> *axis* off the drawing first, then let the pattern place the instances — do not
> type N sets of x/y. After the pattern, confirm the realized **count and axis** with
> `find_hole_patterns()`/`find_holes()` before finishing.

Fairness-safe (generic construction idiom). **Risk:** low–medium; a model that
mis-reads count now mis-reads it once instead of N times — strictly better.

### P3 (generation) — Thin-wall min-thickness gate [targets §5.5 collapse]
The prompt already tells the model to shell thin-walled parts, but gives it no way to
catch a *collapsing* shell before the export gate eats the run. Pairs with the MCP
`min_wall()` proposal (§5). Prompt side, in the Validity block:

> For any shelled/offset thin-walled body, after the shell **measure the realized
> minimum wall** (`min_wall()`, or a `cross_sections()` read of the thinnest web). If
> it is below ~1 mm or below the wall the section shows, the offset has partially
> collapsed — increase the wall or rebuild as outer-solid minus inner-offset before
> validating, rather than discovering the collapse only at export.

Fairness-safe. **Risk:** low; depends on the MCP probe (P3 is most valuable once §5.1
lands, but the `cross_sections` fallback works today).

### P4 (generation) — Revolve/sweep axis discipline [targets §5.5 coord reasoning]
Tighten the existing curved-form fallback with the paper's specific failure cause
(coordinate reasoning for revolves/sweeps):

> When the dominant form is a body of revolution, build the **half-profile in the
> plane that contains the axis** and revolve about that named axis — do not revolve a
> profile drawn in the wrong plane. Confirm the swept envelope with `measure()` on the
> revolved solid before adding features. For a sweep, verify the path direction with a
> single `render_view()` before committing secondary features on top of it.

Fairness-safe. **Risk:** low.

### P5 (editing) — Frame the edit as a design-state delta [uses paper's future-work framing]
The editing prompt is already excellent on *proving* the edit (shape_compare). Add
the paper's lens at step 2 to sharpen *feature identification*:

> Before editing, name which part of the design state the request changes — a
> parameter value (**Θ**: "bore 20→30"), a feature's presence (**F**: add/remove a
> rib), a relation (**C**: spacing/symmetry), or a reference (**A**: which face a hole
> sits on) — and confirm you are touching *only* that component. An edit that changes
> Θ must leave F, C, A intact; `shape_compare`'s `unchanged_elsewhere=true` is the
> proof.

Fairness-safe; reinforces the existing "preserve everything else" priority.
**Risk:** very low (framing only) — may be too subtle to move the metric; A/B before
keeping.

### P6 (both) — Explicit construction order [low value, include only if free]
State Arko-T's H order once in the working-approach header:
`sketch → extrude → secondary features (holes/pockets/patterns) → finishing
(fillets/chamfers)`. The gen prompt already implies this; making it explicit is cheap
but likely below the noise floor (±0.018 whole-benchmark, per `run_repeated.sh`).
Bundle it with P1–P2 rather than A/B-ing it alone.

---

## 5. MCP server enhancements (`build123d-mcp`)

The Claude path exposes a curated 17-tool set (`run_fixture.sh`): `execute`,
`render_view`, `measure`, `validate`, `export`, `import_cad_file`,
`save_snapshot`/`restore_snapshot`, `find_holes`/`find_hole_patterns`/`find_bosses`,
`cross_sections`, `clearance`, `session_state`, `last_error`, `resolve`
(+ `shape_compare` for editing). The gaps below follow directly from the paper.

### M1 — `feature_audit()` : one-call feature census [F; "metrics mask missing features"]
Today the model confirms feature realization piecemeal (`find_holes` +
`find_bosses` + `cross_sections`). The paper's central measurement gap — *a valid
part can silently omit a feature* — argues for a single tool that returns the whole
**F** census: counts and positions of holes, counter-bores, bosses/hubs, pockets,
fillets/chamfers, ribs, and detected patterns, in one structured report. The agent
(and any future auto-scorer) can then diff *requested features* against *realized
features* in one step. This is the MCP analog of the paper's Future-Work
"feature-level evaluation." Highest-leverage MCP add.

### M2 — `min_wall()` / thinnest-section probe [thin-wall collapse §5.5]
No current tool reports **minimum wall thickness** or the thinnest web of a solid.
The paper flags thin-wall collapse as a top persistent failure. A probe that returns
the minimum material thickness (e.g. via inward ray/medial sampling or a distance
field over the solid) lets the agent (P3) catch a collapsed/near-collapsed shell
*before* the export gate destroys the run. Guard it against the `is_inside`-grid
timeout trap the prompts already warn about — implement it as a bounded analytic/mesh
query, not a Python point loop.

### M3 — pattern report: axis + count [polar-pattern §5.5]
`find_hole_patterns()` exists; extend its report to state the **inferred pattern axis
and instance count** explicitly (polar: axis + radius + count; linear/grid:
direction + pitch + n). The paper's failure mode is precisely *inferring axis and
count* — surfacing them as first-class fields lets the agent verify against the
drawing in one read (feeds P2). Small, high-value change to an existing tool.

### M4 — `design_state()` summary [Θ, H; optional]
A read-only summary of the current session's **named parameters** (Θ, if the agent
followed P1) and **operation history** (H). Lets the agent verify its parameter table
against the drawing and confirm construction order without re-reading its own code.
Lower priority for image→STEP scoring (geometry is what's graded), but it is the
natural substrate for the paper's self-improving/feature-eval loop and would make
runs far more auditable in `stream.jsonl`.

### M5 — export-gate diagnostic detail [robustness, not from paper but adjacent]
The prompts lean hard on the export "VALIDITY GATE FAIL" message. When it fails,
returning *where* (which face/edge is non-manifold, which shell is open) would let the
agent repair instead of reverting to a blocky checkpoint — directly reducing the L2
invalid-rate weakness the paper calls the open frontier. `last_error` exists; enrich
the gate's failure payload similarly.

**Priority order:** M1 ≈ M3 (cheap, direct hits on the two measurement gaps) > M2
(needs care to avoid timeouts) > M5 > M4.

---

## 6. Harness enhancement (brief)

Arko-T's supervision is **execution-grounded** — only kernel-valid programs count —
and their Future Work proposes a **self-improving loop** (valid outputs → new data).
We can't retrain, but the same principle says: **select best-of-N by the validity
gate + proxy shape score.** `harness/run_repeated.sh` already produces N repetitions
to average variance; a small `select_best.py` that, per fixture, picks the
gate-passing `output.step` with the best `score.py` proxy F1 would convert that
variance-averaging run into a variance-*exploiting* one. Fairness caveat: selection
must use only the **local proxy** (`score.py`) and the **validity gate**, never the
held-out ground truth — otherwise it fits the benchmark. Framed that way it's an
honest "sample-3, keep-the-valid-best" system, disclosed as such.

---

## 7. What does *not* transfer / guardrails

- **Training methods** (LoRA, corpus normalization, execution-filtered SFT) — no
  analog in a prompt+MCP pipeline; do not try to "normalize" fixtures.
- **Geo/Pro registers** — our generation input is a drawing, not text; there is no
  register to switch. (Only tangential relevance to the editing prompt's *text* request.)
- **Cost claims** — Arko-T's headline is 10–65× cheaper than frontier APIs. Our
  system *is* the frontier-API side of that comparison; the paper is, if anything, an
  argument that a specialized local model would beat our cost — not a lever for us.
- **Fairness line (README §Honest-use):** every prompt lever here is generic and
  verification-oriented; none encodes a fixture answer. The best-of-N harness idea is
  the only one with a fairness edge — keep its selection strictly on the local proxy +
  validity gate, never ground truth, and disclose it.

---

## 8. Recommended rollout (respect the smoke-test gate)

1. **A/B P1 + P2 together** on `splits/dev.txt` via `run_repeated.sh` (N≥3) — these
   are the highest-value, lowest-risk levers and both are pure code-structure/relation
   discipline. Aggregate before keeping (±0.018 noise floor).
2. In parallel, land **M1** and **M3** in `build123d-mcp` (cheap, they only *add*
   information) and wire the confirmation half of P2/feature-audit into the prompts.
3. **A/B P3 + M2** once the `min_wall` probe exists — thin-wall parts are a known weak
   fixture class.
4. P4, P5, P6 as a second cosmetic-discipline batch; expect small effects, A/B in a
   bundle rather than individually.
5. Commit each kept lever *before* the scored sweep so `run_meta.json` pins a clean
   commit (per `CLAUDE.md`).
</content>
</invoke>
