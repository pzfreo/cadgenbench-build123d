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
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

CANDIDATE_NAMES = ("output.step", "output.stp", "output.stl", "output.obj", "output.off", "output.3mf", "output.ply")


def _mcp_version(manifest):
    """Return the sweep-time MCP version, falling back to package-time metadata."""
    rm = manifest.get("run_meta", {})
    return (
        rm.get("mcp_version")
        or manifest.get("resolved_versions", {}).get("build123d_mcp")
    )


def _model_slug(model, effort):
    """Normalize a provider model ID for a compact leaderboard identity."""
    slug = str(model).strip().lower()
    for prefix in ("anthropic/", "google/", "agy/"):
        if slug.startswith(prefix):
            slug = slug[len(prefix):]
    if slug.startswith("claude-"):
        slug = slug[len("claude-"):]
    slug = re.sub(r"[^a-z0-9.]+", "-", slug).strip("-")

    # Agy model IDs sometimes carry effort as a suffix even though run_meta also
    # records it separately. Keep the generated name canonical and non-repeated.
    if effort and effort != "config-default" and slug.endswith(f"-{effort}"):
        slug = slug[: -(len(effort) + 1)]

    # Anthropic API IDs spell minor versions with a hyphen (fable-5-1), while
    # the public model name is Fable 5.1. Preserve family names and render the
    # version compactly for the leaderboard.
    match = re.fullmatch(r"(fable|opus|sonnet|haiku)-(\d+)-(\d+)", slug)
    if match:
        slug = f"{match.group(1)}-{match.group(2)}.{match.group(3)}"
    return slug


def derive_submission_name(manifest):
    """Derive a truthful leaderboard name from immutable sweep provenance."""
    rm = manifest.get("run_meta")
    if not isinstance(rm, dict):
        raise ValueError("cannot package ZIP without results/<run>/run_meta.json")

    model = rm.get("model")
    if not model or model == "unknown":
        raise ValueError("cannot package ZIP: run_meta.json has no resolved model")
    effort = rm.get("reasoning_effort")
    model_slug = _model_slug(model, effort)
    if not model_slug:
        raise ValueError("cannot package ZIP: model does not produce a valid name slug")

    mcp_version = _mcp_version(manifest)
    if not mcp_version or mcp_version == "unknown":
        raise ValueError("cannot package ZIP: build123d-mcp version is unresolved")
    if mcp_version == "none":
        parts = ["build123d-direct", model_slug]
    else:
        parts = ["build123d-mcp", str(mcp_version), model_slug]
    if effort and effort != "config-default":
        parts.append(re.sub(r"[^a-z0-9.]+", "-", str(effort).lower()).strip("-"))
    return "-".join(parts)


def resolve_submission_name(manifest, requested_name=None):
    """Return the automatic name, rejecting manual names that obscure identity."""
    derived = derive_submission_name(manifest)
    if not requested_name:
        return derived
    if not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", requested_name):
        raise ValueError(
            "invalid --name: use lowercase letters, digits, single hyphens, and dots only"
        )
    if requested_name != derived and not requested_name.startswith(f"{derived}-"):
        raise ValueError(
            f"invalid --name {requested_name!r}; it must be {derived!r} or begin "
            f"with {derived + '-'!r}"
        )
    return requested_name


# CADGenBench's validity gate rejects STEP files above this size outright
# (cadgenbench.common.validity.MAX_STEP_FILE_BYTES), before any geometry check.
# The build123d-mcp gate does not check file size, so mirror it here.
MAX_STEP_FILE_BYTES = 50_000_000


def proxy_gate(step_path):
    """Run the build123d-mcp validity gate on a STEP/STL and return its report."""
    size = Path(step_path).stat().st_size
    if str(step_path).lower().endswith((".step", ".stp")) and size > MAX_STEP_FILE_BYTES:
        return {
            "passes_gate": False,
            "reasons": [
                f"STEP file is {size} bytes, over CADGenBench's "
                f"{MAX_STEP_FILE_BYTES}-byte ceiling; the grader rejects it unread"
            ],
            "mesh_check": "skipped",
            "warnings": [],
        }
    from build123d import import_step
    from build123d_mcp.tools.validate import _gate_report, _run_mesh_gate_subprocess

    shp = import_step(str(step_path))
    solids = shp.solids()
    if not solids:
        shape = shp
    elif len(solids) == 1:
        shape = solids[0]
    else:
        from build123d import Compound

        shape = Compound(children=list(solids))
    # exact=True alone is not enough on a large part: _gate_report's in-process
    # exact check shares interactive validate()'s 35s wall-clock budget, and on
    # a big/slow-to-stitch solid it silently falls back to the fast coordinate-
    # weld check — which cannot detect open edges at all (hardcoded to 0), only
    # non-manifold ones. That let a submission with 6 real mesh open edges
    # proxy-PASS locally while both the agent's own export() (which runs this
    # same check out-of-process, unbounded by the 35s budget) and the real
    # CADGenBench gate correctly failed it. Packaging is a one-off with no live
    # session to protect, so run the exact check out-of-process ourselves, the
    # same way export() does, with a generous timeout instead of that budget.
    mesh_override = None
    if str(step_path).lower().endswith((".step", ".stp")):
        mesh_override = _run_mesh_gate_subprocess(str(step_path), timeout=180)
    return _gate_report(
        shape,
        exact=True,
        mesh_override=mesh_override if mesh_override is not None else (0, 0, 0, 0, 0, False),
    )


def describe_task_sources(task_sources):
    """Render task and fixture-override provenance for submission notes."""
    source_notes = []
    for task_name in ("generation", "editing"):
        source = task_sources.get(task_name)
        if not isinstance(source, dict):
            continue
        count = source.get("fixture_count", "?")
        action = "reused unchanged from" if source.get("reused") else "from"
        source_mcp = source.get("mcp_version", "unknown")
        source_mcp_commit = source.get("mcp_git_commit")
        source_revision = (
            f" @ {source_mcp_commit[:12]}"
            if source_mcp_commit
            and source_mcp_commit not in {"unknown", "not-applicable"}
            else ""
        )
        source_harness = source.get("harness_commit", "unknown")
        source_agent = source.get("agent", "")
        agent_suffix = f", {source_agent}" if source_agent else ""
        source_notes.append(
            f"{task_name.capitalize()}: {count} outputs {action} build123d-mcp "
            f"{source_mcp}{source_revision}, harness {source_harness[:12]}"
            f"{agent_suffix}"
        )

        for override in source.get("fixture_overrides", []):
            if not isinstance(override, dict):
                continue
            fixture_ids = [str(fid) for fid in override.get("fixture_ids", [])]
            if not fixture_ids:
                continue
            override_mcp = override.get("mcp_version", "unknown")
            override_harness = override.get("harness_commit", "unknown")
            override_policy = override.get("recognition_policy")
            policy_suffix = f", policy {override_policy}" if override_policy else ""
            source_notes.append(
                f"{task_name.capitalize()} fixtures {','.join(fixture_ids)} overridden from "
                f"build123d-mcp {override_mcp}, harness {override_harness[:12]}"
                f"{policy_suffix}"
            )
    return source_notes


def build_submission_zip(root, manifest, full_set_path, submitter, name=None):
    """Build the upload-ready zip: meta.json + every fixture dir at the root.

    Pads to the canonical full fixture set (CADGenBench requires every sample dir
    present; missing outputs score 0). Empty fixture directories are written as
    explicit zip directory entries, not placeholder files. meta.json's notes are
    auto-stamped with the exact system from run_meta — model, resolved
    build123d-mcp version, and the cadgenbench-build123d commit (which pins the
    prompts/harness) — so the upload is self-describing. agent_url is the commit
    permalink.
    """
    name = resolve_submission_name(manifest, name)
    rm = manifest.get("run_meta", {})
    model = rm.get("model", "unknown")
    effort = rm.get("reasoning_effort")
    model_desc = (
        f"{model} (reasoning effort: {effort})"
        if effort and effort != "config-default"
        else model
    )
    provider = rm.get("model_provider")
    driver = rm.get("agent_driver")
    credential = rm.get("credential_source")
    if provider == "vercel-ai-gateway":
        provider_desc = " via Codex CLI + Vercel AI Gateway"
    elif driver == "antigravity-cli":
        agy_version = rm.get("agy_cli_version", "unknown")
        agent_mode = rm.get("agent_mode", "default")
        provider_desc = (
            f" via Google Antigravity CLI {agy_version} "
            f"({agent_mode})"
        )
    else:
        provider_desc = ""
    if driver == "claude-code" and credential:
        provider_desc += f" using {credential}"
    mcp_version = _mcp_version(manifest) or "unknown"
    mcp_commit = rm.get("mcp_git_commit")
    mcp_revision = (
        f" @ {mcp_commit[:12]}"
        if mcp_commit and mcp_commit not in {"unknown", "not-applicable"}
        else ""
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
    if mcp_version == "none":
        system_desc = f"Model {model_desc}{provider_desc} + direct build123d/Python (no MCP server)"
    else:
        system_desc = (
            f"Model {model_desc}{provider_desc} + build123d-mcp {mcp_version}{mcp_revision} "
            "(gate-equipped MCP server)"
        )
    task_sources = rm.get("task_sources")
    if isinstance(task_sources, dict) and task_sources:
        source_notes = describe_task_sources(task_sources)
        notes = (
            f"Mixed-task package. {'; '.join(source_notes)}. "
            f"Model {model_desc}; {n_out}/{len(ids)} fixtures produced."
        )[:500]
    else:
        notes = (
            f"{system_desc}. Harness + prompts: cadgenbench-build123d @ {commit[:12]}. "
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

    zip_path = Path("submit") / f"{name}.zip"
    legacy_zip_path = Path("submit") / f"{root.name}.zip"
    if legacy_zip_path != zip_path and legacy_zip_path.exists():
        legacy_zip_path.unlink()
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(stage / "meta.json", "meta.json")
        for fid in ids:
            zf.write(stage / fid, f"{fid}/")
            f = stage / fid / "output.step"
            if f.exists():
                zf.write(f, f"{fid}/output.step")
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
    ap.add_argument(
        "--name",
        default=None,
        help=(
            "optional suffix-bearing submission_name; by default it is derived from "
            "run_meta.json, and any override must retain the complete derived prefix"
        ),
    )
    args = ap.parse_args()

    root = Path(args.results_dir)
    if not root.is_dir():
        sys.exit(f"not a directory: {root}")

    fixtures = sorted(
        (d for d in root.iterdir() if d.is_dir() and d.name.isdigit()),
        key=lambda d: int(d.name),
    )
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
                entry["proxy_mesh_check"] = rep.get("mesh_check")
                entry["proxy_warnings"] = rep.get("warnings", [])
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
        try:
            build_submission_zip(root, manifest, args.full_set, args.submitter, args.name)
        except ValueError as exc:
            sys.exit(f"cannot build submission ZIP: {exc}")

    print("\nnext steps:")
    print("  1. run the official sanity check on every output.step (see CADGenBench docs)")
    print("  2. upload the submission zip at")
    print("     https://huggingface.co/spaces/HuggingAI4Engineering/CADGenBench")


if __name__ == "__main__":
    main()
