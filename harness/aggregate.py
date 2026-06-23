#!/usr/bin/env python3
"""Average CADGenBench runs and A/B-compare them above the run-to-run noise.

Per-fixture scores swing wildly between identical runs (std ~0.16), so the
whole-benchmark mean has a ~0.018 error bar — a single before/after can't see a
+0.01-0.02 change. Run each variant >=3x (harness/run_repeated.sh), extract each
report's per-fixture table to a text file, then:

  # within-variant: per-fixture mean/std + overall mean +/- run-to-run stderr
  python harness/aggregate.py runA-r1.txt runA-r2.txt runA-r3.txt

  # A/B (paired by fixture): does B beat A above the noise?
  python harness/aggregate.py A-r1.txt A-r2.txt --vs B-r1.txt B-r2.txt

Table file format: one fixture per line, e.g. "136 generation valid 0.076".
Parsed tolerantly: first token = fixture id, last numeric token = cad score.
"""
import sys, re, statistics as st
from math import sqrt

def load(path):
    d = {}
    for ln in open(path):
        toks = ln.split()
        if not toks: continue
        fid = toks[0]
        nums = [t for t in toks if re.fullmatch(r"-?\d+\.?\d*", t)]
        if not fid[0].isdigit() or len(nums) < 1: continue
        d[fid] = float(nums[-1])           # last numeric = score
    return d

def side(files):
    """Average per-fixture across runs; return (mean_by_fixture, per_run_overall)."""
    runs = [load(f) for f in files]
    fids = set().union(*runs)
    mean = {f: st.mean([r[f] for r in runs if f in r]) for f in fids}
    overall = [st.mean(r.values()) for r in runs]      # one overall score per run
    return mean, overall, runs

def report_overall(name, overall):
    m = st.mean(overall)
    if len(overall) > 1:
        se = st.stdev(overall) / sqrt(len(overall))
        print(f"  {name}: overall {m:.3f} +/- {se:.3f}  (n={len(overall)} runs: "
              f"{', '.join(f'{x:.3f}' for x in overall)})")
    else:
        print(f"  {name}: overall {m:.3f}  (n=1 run -- no within-variant variance)")
    return m

def main():
    args = sys.argv[1:]
    if "--vs" in args:
        i = args.index("--vs"); A, B = args[:i], args[i+1:]
        ma, oa, _ = side(A); mb, ob, _ = side(B)
        print(f"=== A ({len(A)} run(s)) vs B ({len(B)} run(s)) ===")
        report_overall("A", oa); report_overall("B", ob)
        common = sorted(set(ma) & set(mb), key=int)
        deltas = [mb[f] - ma[f] for f in common]
        md = st.mean(deltas); sd = st.pstdev(deltas) if len(deltas)<2 else st.stdev(deltas)
        se = sd / sqrt(len(deltas)); t = md/se if se else 0.0
        print(f"\n  paired over {len(common)} fixtures:  mean delta(B-A) = {md:+.3f}")
        print(f"  per-fixture delta std = {sd:.3f}  ->  SE of mean = {se:.3f}  (the noise band)")
        print(f"  |t| = {abs(t):.2f}  ->  {'SIGNIFICANT (>2)' if abs(t)>2 else 'WITHIN NOISE (need a bigger effect or more runs)'}")
        mv = sorted(((f, mb[f]-ma[f]) for f in common), key=lambda x: -abs(x[1]))
        print("  biggest movers:", ", ".join(f"{f}{d:+.2f}" for f,d in mv[:6]))
        if len(A)==1 or len(B)==1:
            print("\n  NOTE: >=3 runs per side recommended; with 1 run the paired SE still")
            print("  estimates detectability, but can't separate variant change from variance.")
    else:
        mean, overall, runs = side(args)
        print(f"=== {len(args)} run(s), {len(mean)} fixtures ===")
        report_overall("variant", overall)
        if len(runs) > 1:
            spread = {f: (st.mean([r[f] for r in runs if f in r]),
                          st.pstdev([r[f] for r in runs if f in r])) for f in mean}
            noisy = sorted(spread.items(), key=lambda x:-x[1][1])[:6]
            print("  noisiest fixtures (mean, std across runs):",
                  ", ".join(f"{f}={m:.2f}±{s:.2f}" for f,(m,s) in noisy))

if __name__ == "__main__":
    main()
