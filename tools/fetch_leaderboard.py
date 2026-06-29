#!/usr/bin/env python3
"""Fetch the CADGenBench leaderboard (bypassing the Gradio/TS UI), highlight what
changed since the last recorded state, and keep an append-only history.

Source of truth = results.jsonl in the cadgenbench-submissions dataset — exactly
what the Space's _load_rows_from_hub() reads. Stdlib only.

History (gitignored) grows by ONE entry only when the leaderboard content actually
changes (deduped by content hash), so the log is a clean timeline of real events.

  python3 fetch_leaderboard.py                 # human table, diff vs last recorded state
  python3 fetch_leaderboard.py --format json   # machine-readable diff (for an AI to summarize/analyse)
  python3 fetch_leaderboard.py --log           # timeline of every recorded change
  python3 fetch_leaderboard.py --log --format json   # the whole history as JSON
  flags: --no-color  --csv PATH  --store DIR
"""
import argparse, csv, hashlib, json, os, sys, time, urllib.request
from datetime import datetime, timezone

URL = ("https://huggingface.co/datasets/HuggingAI4Engineering/"
       "cadgenbench-submissions/resolve/main/results.jsonl")
WATCH = ["status", "validation_status", "aggregate_score", "validity_rate"]   # change-worthy fields
HASH_FIELDS = WATCH + ["score_by_task_type"]                                  # what counts as "different"
KEEP = ["submission_id", "submission_name", "submitter_name", "hf_username", "agent_url",
        "submitted_at", "cadgenbench_version"] + WATCH + ["score_by_task_type", "_rank"]
CSV_COLUMNS = ["submission_id","status","validation_status","validation_method",
  "submitter_name","submission_name","hf_username","aggregate_score","validity_rate",
  "agent_url","submitted_at","cadgenbench_version","cadgenbench_data_revision",
  "submission_blob_url","submission_sha256","notes","failure_reason"]


def fetch():
    req = urllib.request.Request(f"{URL}?t={int(time.time())}",
            headers={"Cache-Control": "no-cache", "User-Agent": "cadgenbench-csv/1"})
    raw = urllib.request.urlopen(req, timeout=30).read().decode()
    return [json.loads(l) for l in raw.splitlines() if l.strip()]


def num(x):
    try: return float(x)
    except (TypeError, ValueError): return -1.0


def rank_and_compact(rows):
    scored = sorted([r for r in rows if num(r.get("aggregate_score")) >= 0],
                    key=lambda r: -num(r.get("aggregate_score")))
    rank = {r.get("submission_id"): i for i, r in enumerate(scored, 1)}
    out = []
    for r in rows:
        r2 = {k: r.get(k) for k in KEEP if k != "_rank"}
        r2["_rank"] = rank.get(r.get("submission_id"))
        out.append(r2)
    out.sort(key=lambda r: (r["_rank"] is None, r["_rank"] or 0))
    return out


def content_hash(rows):
    payload = sorted(({k: r.get(k) for k in HASH_FIELDS + ["submission_id"]} for r in rows),
                     key=lambda r: r["submission_id"] or "")
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def diff(prev_rows, cur_rows):
    prev = {r["submission_id"]: r for r in (prev_rows or [])}
    cur = {r["submission_id"]: r for r in cur_rows}
    new, changed = [], []
    for sid, r in cur.items():
        p = prev.get(sid)
        if p is None:
            new.append(r); continue
        ch = [{"field": k, "old": p.get(k), "new": r.get(k)}
              for k in WATCH if str(p.get(k)) != str(r.get(k))]
        if p.get("_rank") != r.get("_rank"):
            ch.append({"field": "rank", "old": p.get("_rank"), "new": r.get("_rank")})
        if ch:
            changed.append({"submission_id": sid, "submission_name": r.get("submission_name"),
                            "rank": r.get("_rank"), "aggregate_score": r.get("aggregate_score"),
                            "changes": ch})
    gone = [{"submission_id": s, "submission_name": prev[s].get("submission_name")}
            for s in set(prev) - set(cur)]
    new.sort(key=lambda r: (r["_rank"] is None, r["_rank"] or 0))
    changed.sort(key=lambda r: (r["rank"] is None, r["rank"] or 0))
    return new, changed, gone


def load_history(path):
    if not os.path.exists(path): return []
    return [json.loads(l) for l in open(path) if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".leaderboard-store"),
        help="gitignored dir holding history.jsonl (default: next to this script)")
    ap.add_argument("--csv", default="leaderboard.csv")
    ap.add_argument("--format", choices=["table", "json"], default="table")
    ap.add_argument("--log", action="store_true", help="show the recorded-change timeline instead of fetching")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.store, exist_ok=True)
    hist_path = os.path.join(args.store, "history.jsonl")
    color = sys.stdout.isatty() and not args.no_color and not os.environ.get("NO_COLOR")
    def c(s, code): return f"\033[{code}m{s}\033[0m" if color else s

    history = load_history(hist_path)

    # ---- --log: report the timeline of recorded changes, no fetch ----
    if args.log:
        events = []
        for i in range(1, len(history)):
            n, ch, g = diff(history[i-1]["rows"], history[i]["rows"])
            events.append({"captured_at": history[i]["captured_at"],
                           "new": n, "changed": ch, "gone": g})
        if args.format == "json":
            print(json.dumps({"baseline_at": history[0]["captured_at"] if history else None,
                              "events": events}, indent=2))
        else:
            if history: print(f"baseline {history[0]['captured_at']}  ({len(history[0]['rows'])} rows)")
            for e in events:
                names = [r["submission_name"] for r in e["new"]] + \
                        [f"{x['submission_name']}*" for x in e["changed"]]
                print(f"{e['captured_at']}  +{len(e['new'])} new  ~{len(e['changed'])} changed  "
                      f"-{len(e['gone'])} gone   {', '.join(n[:30] for n in names[:6])}")
            print(f"\n{len(history)} recorded states.")
        return

    # ---- normal run: fetch, diff vs last recorded state, maybe append ----
    rows = rank_and_compact(fetch())
    raw_rows = rows  # compact already
    with open(args.csv, "w", newline="") as f:
        # CSV parity needs full rows; re-fetch fields kept in compact + fill blanks
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)

    prev = history[-1]["rows"] if history else None
    new, changed, gone = diff(prev, rows)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    h = content_hash(rows)
    baseline = not history
    appended = baseline or (history and history[-1]["hash"] != h)
    if appended:
        with open(hist_path, "a") as f:
            f.write(json.dumps({"captured_at": now, "hash": h, "rows": rows}) + "\n")

    if args.format == "json":
        print(json.dumps({
            "captured_at": now, "baseline": baseline,
            "previous_captured_at": history[-1]["captured_at"] if history else None,
            "recorded_new_state": bool(appended),
            "summary": {"total": len(rows), "new": len(new), "changed": len(changed), "gone": len(gone)},
            "new": new, "changed": changed, "gone": gone,
        }, indent=2))
        return

    # human table
    print(f"{'#':>2} {'agg':>6} {'valid':>7}  submission")
    chg_ids = {x["submission_id"] for x in changed}
    new_ids = {r["submission_id"] for r in new}
    chg_by_id = {x["submission_id"]: x for x in changed}
    for r in rows:
        if r["_rank"] is None: continue
        name = (r.get("submission_name") or "")[:44]
        line = f"{r['_rank']:2} {num(r.get('aggregate_score')):6.3f} {str(r.get('validity_rate','')):>7}  {name}"
        if baseline:
            print(line)
        elif r["submission_id"] in new_ids:
            print(c("+NEW ", "1;32") + c(line, "32"))
        elif r["submission_id"] in chg_ids:
            det = "  ".join(
                (f"rank #{x['old']}->#{x['new']} ({'↑' if (x['new'] or 0)<(x['old'] or 0) else '↓'}{abs((x['new'] or 0)-(x['old'] or 0))})"
                 if x["field"]=="rank" else f"{x['field']} {x['old']}->{x['new']}")
                for x in chg_by_id[r["submission_id"]]["changes"])
            print(c("~CHG ", "1;33") + c(line, "33") + c("   [" + det + "]", "2;33"))
        else:
            print(c("     " + line, "2") if color else "     " + line)
    for x in gone:
        print(c(f"-GONE  {(x['submission_name'] or '')[:44]}", "31"))

    if baseline:
        print(f"\nbaseline recorded ({len(rows)} rows) -> {hist_path}")
    else:
        tag = "recorded new state" if appended else "no change since last recorded state"
        print(f"\n{len(new)} new, {len(changed)} changed, {len(gone)} gone — {tag}.")


if __name__ == "__main__":
    main()
