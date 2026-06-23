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
import shutil
import subprocess
import sys
import zipfile
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
    # exact=True: packaging is a deliberate one-off, so use the authoritative
    # topology-stitch mesh gate. The default (inline budget) falls back to the
    # fast coordinate-weld check on large parts, which false-flags valid solids
    # (a packaged big editing fixture would be wrongly marked FAIL).
    return _gate_report(shape, exact=True)


def build_submission_zip(root, manifest, full_set_path, submitter, name):
    """Build the upload-ready zip: meta.json + every fixture dir at the root.

    Pads to the canonical full fixture set (CADGenBench requires every sample dir
    present; missing outputs score 0). meta.json's notes are auto-stamped with the
    exact system from run_meta — model, resolved build123d-mcp version, and the
    cadgenbench-build123d commit (which pins the prompts/harness) — so the upload
    is self-describing. agent_url is the commit permalink.
    """
    rm = manifest.get("run_meta", {})
    model = rm.get("model", "unknown")
    effort = rm.get("reasoning_effort")
    model_desc = (
        f"{model} (reasoning effort: {effort})"
        if effort and effort != "config-default"
        else model
    )
    mcp_version = (
        rm.get("mcp_version")
        or manifest.get("resolved_versions", {}).get("build123d_mcp")
        or "unknown"
    )
    commit = rm.get("git_commit", "unknown")

    ids = []
    for line in Path(full_set_path).read_text().splitlines():
        tok = line.split("#", 1)[0].strip()
        if tok.isdigit():
            ids.append(tok)
    if not ids:
        sys.exit(f"no fixture ids in {full_set_path}")

    n_out = sum(1 for fid in ids if (root / fid / "output.step").exists())
    agent_url = (
        f"https://github.com/pzfreo/cadgenbench-build123d/tree/{commit}"
        if commit and commit != "unknown"
        else "https://github.com/pzfreo/cadgenbench-build123d"
    )
    notes = (
        f"Model {model_desc} + build123d-mcp {mcp_version} (gate-equipped MCP server). "
        f"Harness + prompts: cadgenbench-build123d @ {commit[:12]}. "
        f"{n_out}/{len(ids)} fixtures produced."
    )[:500]
    meta = {
        "submitter_name": submitter,
        "submission_name": name,
        "agent_url": agent_url,
        "notes": notes,
        "agree_to_publish": True,
    }

    stage = Path("submit") / root.name
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    (stage / "meta.json").write_text(json.dumps(meta, indent=2))
    for fid in ids:
        d = stage / fid
        d.mkdir()
        out = root / fid / "output.step"
        if out.exists() and out.stat().st_size > 0:
            shutil.copy(out, d / "output.step")
        else:
            (d / ".keep").write_text("no candidate submitted\n")

    zip_path = Path("submit") / f"{root.name}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(stage / "meta.json", "meta.json")
        for fid in ids:
            for fn in ("output.step", ".keep"):
                f = stage / fid / fn
                if f.exists():
                    zf.write(f, f"{fid}/{fn}")
    print(f"\n=== submission zip: {zip_path} ===")
    print(f"  fixtures        : {len(ids)} dirs, {n_out} with output.step")
    print(f"  submitter_name  : {submitter}")
    print(f"  submission_name : {name}")
    print(f"  agent_url       : {agent_url}")
    print(f"  notes           : {notes}")
    return zip_path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results_dir", help="a results/<run> directory holding <id>/output.step subdirs")
    ap.add_argument(
        "--official-sanity-check",
        default=None,
        metavar="PATH",
        help="path to cadgenbench sanity_check_submission.py — the authoritative gate",
    )
    ap.add_argument(
        "--zip", action="store_true", help="build the upload-ready submission zip (auto meta.json)"
    )
    ap.add_argument(
        "--full-set", default="splits/all.txt", help="canonical full fixture-id list to pad the zip to"
    )
    ap.add_argument("--submitter", default="pzfreo", help="meta.json submitter_name")
    ap.add_argument("--name", default="pzfreo", help="meta.json submission_name")
    args = ap.parse_args()

    root = Path(args.results_dir)
    if not root.is_dir():
        sys.exit(f"not a directory: {root}")

    fixtures = sorted((d for d in root.iterdir() if d.is_dir()), key=lambda d: d.name)
    if not fixtures:
        sys.exit(f"no <id>/ subdirectories under {root}")

    manifest = {"run": root.name, "fixtures": {}}

    # Fold in the sweep-time provenance stamp (git revision, model, mcp_spec) and
    # the package versions resolved here — together they pin the exact system.
    meta_path = root / "run_meta.json"
    if meta_path.exists():
        try:
            manifest["run_meta"] = json.loads(meta_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    from importlib.metadata import PackageNotFoundError, version as _pkg_version

    def _ver(name):
        try:
            return _pkg_version(name)
        except PackageNotFoundError:
            return None

    manifest["resolved_versions"] = {
        "build123d_mcp": _ver("build123d-mcp"),
        "build123d": _ver("build123d"),
        "note": "resolved at packaging time; the run logs hold the authoritative sweep-time version",
    }

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
    if args.zip:
        build_submission_zip(root, manifest, args.full_set, args.submitter, args.name)

    print("\nnext steps:")
    print("  1. run the official sanity check on every output.step (see CADGenBench docs)")
    print("  2. upload the submission zip at")
    print("     https://huggingface.co/spaces/HuggingAI4Engineering/CADGenBench")


if __name__ == "__main__":
    main()
