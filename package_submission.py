"""Validate and summarize a CADGenBench submission directory.

Walks ``results/<run>/<id>/output.step``, runs the build123d-mcp validity gate on
each candidate, and writes ``manifest.json`` plus a console summary.

IMPORTANT: the build123d-mcp gate here is a PROXY for the official one. The
authoritative gate is CADGenBench's own ``sanity_check_submission.py``; a STEP
that passes the proxy can still be rejected upstream. Pass
``--official-sanity-check <path>`` to also run the official checker and record
its verdict as ``official_status`` — that, not the proxy, decides acceptance.

Usage:
  uv run --with build123d-mcp --with trimesh --with scipy \\
      python package_submission.py results/<run> [--official-sanity-check PATH]
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

CANDIDATE_NAMES = ("output.step", "output.stp", "output.stl", "output.obj", "output.off", "output.3mf", "output.ply")


def proxy_gate(step_path):
    """Run the build123d-mcp validity gate on a STEP/STL and return its report."""
    from build123d import import_step
    from build123d_mcp.tools.validate import _gate_report

    shp = import_step(str(step_path))
    solids = shp.solids()
    if not solids:
        shape = shp
    elif len(solids) == 1:
        shape = solids[0]
    else:
        from build123d import Compound

        shape = Compound(children=list(solids))
    return _gate_report(shape)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results_dir", help="a results/<run> directory holding <id>/output.step subdirs")
    ap.add_argument(
        "--official-sanity-check",
        default=None,
        metavar="PATH",
        help="path to cadgenbench sanity_check_submission.py — the authoritative gate",
    )
    args = ap.parse_args()

    root = Path(args.results_dir)
    if not root.is_dir():
        sys.exit(f"not a directory: {root}")

    fixtures = sorted((d for d in root.iterdir() if d.is_dir()), key=lambda d: d.name)
    if not fixtures:
        sys.exit(f"no <id>/ subdirectories under {root}")

    manifest = {"run": root.name, "fixtures": {}}
    n_present = n_valid = n_official_pass = 0

    for d in fixtures:
        step = next((d / name for name in CANDIDATE_NAMES if (d / name).exists()), None)
        entry = {"present": step is not None, "file": step.name if step else None}

        if step is None:
            entry["proxy_status"] = "missing"
        else:
            n_present += 1
            try:
                rep = proxy_gate(step)
                entry["proxy_status"] = "PASS" if rep["passes_gate"] else "FAIL"
                entry["proxy_reasons"] = rep.get("reasons", [])
                if rep["passes_gate"]:
                    n_valid += 1
            except Exception as exc:  # noqa: BLE001 - record and continue
                entry["proxy_status"] = "ERROR"
                entry["error"] = str(exc)

            if args.official_sanity_check and step is not None:
                proc = subprocess.run(
                    [sys.executable, args.official_sanity_check, str(step)],
                    capture_output=True,
                    text=True,
                )
                ok = proc.returncode == 0
                entry["official_status"] = "PASS" if ok else "FAIL"
                entry["official_output"] = (proc.stdout + proc.stderr).strip()[:500]
                if ok:
                    n_official_pass += 1

        manifest["fixtures"][d.name] = entry

    (root / "manifest.json").write_text(json.dumps(manifest, indent=2))

    n = len(fixtures)
    print(f"\n=== submission '{root.name}' ===")
    print(f"fixtures listed   : {n}")
    print(f"output present    : {n_present}/{n}  ({n - n_present} missing -> score 0)")
    print(f"proxy gate PASS   : {n_valid}/{n_present} present  (proxy only — NOT authoritative)")
    if args.official_sanity_check:
        print(f"official gate PASS: {n_official_pass}/{n_present} present")
    else:
        print("official gate     : not run — pass --official-sanity-check PATH before submitting")
    print(f"manifest          : {root / 'manifest.json'}")
    print("\nnext steps:")
    print("  1. run the official sanity check on every output.step (see CADGenBench docs)")
    print("  2. zip the run directory and upload at")
    print("     https://huggingface.co/spaces/HuggingAI4Engineering/CADGenBench")


if __name__ == "__main__":
    main()
