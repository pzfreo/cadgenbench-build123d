"""Download one CADGenBench fixture's inputs from the public HF dataset.

The inputs (drawing image, description, and for editing fixtures the starting
STEP) are public; the ground truth is held out. Generation fixtures are 101-150,
editing fixtures 201+.

Usage:
  uv run --with huggingface_hub python eval/fetch_fixture.py <id> <dest_dir>
e.g.
  uv run --with huggingface_hub python eval/fetch_fixture.py 102 /tmp/cgb_102
"""

import shutil
import sys
from pathlib import Path

REPO = "HuggingAI4Engineering/cadgenbench-data"

# Agent-facing inputs only. A self-bench fixture dir also holds part.py and
# ground_truth.step; those must NEVER be copied into the run input dir (that
# would hand the agent the answer). Mirrors what the HF dataset exposes.
SELFBENCH_INPUTS = ("description.yaml", "input.png", "input.step")


def _try_local(fid: str, dest: Path) -> bool:
    """Serve a self-bench fixture from selfbench/fixtures/<id> if present."""
    local = Path(__file__).resolve().parent.parent / "selfbench" / "fixtures" / fid
    if not (local / "description.yaml").is_file():
        return False
    dest.mkdir(parents=True, exist_ok=True)
    for name in SELFBENCH_INPUTS:
        src = local / name
        if src.is_file():
            shutil.copyfile(src, dest / name)
            print("fetched (self-bench)", dest / name)
    return True


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    fid, dest = sys.argv[1], Path(sys.argv[2])
    if _try_local(fid, dest):
        return
    from huggingface_hub import snapshot_download

    snap = snapshot_download(repo_id=REPO, repo_type="dataset", allow_patterns=f"{fid}/*")
    src = Path(snap) / fid
    if not src.is_dir():
        print(f"fixture {fid} not found in {REPO}")
        sys.exit(1)
    dest.mkdir(parents=True, exist_ok=True)
    for f in src.rglob("*"):
        if f.is_dir():
            continue
        out = dest / f.relative_to(src)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(f.read_bytes())
        print("fetched", out)


if __name__ == "__main__":
    main()
