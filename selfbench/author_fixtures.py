"""Author self-bench fixtures: build123d part.py -> ground truth + drawing.

For each ``selfbench/fixtures/<id>/part.py`` this:

1. execs ``part.py`` and pulls its module-level ``part`` (the ground truth),
2. exports ``ground_truth.step`` (held locally; never shown to the agent),
3. renders a CADGenBench-style engineering drawing with draftwright (PDF) —
   either from the STEP via auto-recognition (default), or, when ``part.py``
   defines an ``author()`` hook, from an explicitly-declared draftwright
   ``Sheet`` (see "Inference-load fixtures" in selfbench/README.md),
4. rasterises page 1 to ``input.png`` (the agent's only visual input),
5. writes ``description.yaml`` in the canonical generation-fixture format.

Run it with the authoring deps on the path:

    uv run --with build123d --with draftwright --with pymupdf \
        python selfbench/author_fixtures.py            # all fixtures
    uv run --with build123d --with draftwright --with pymupdf \
        python selfbench/author_fixtures.py 9001       # just one

These are *dev-set* fixtures we own the ground truth for. They exist to give
prompt/harness changes a fast local geometric signal — never report their
scores and never leak their specifics into the generic prompts. See
selfbench/README.md.
"""

from __future__ import annotations

import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# The canonical generation-fixture prompt, byte-for-byte as the real
# CADGenBench dataset ships it (work/<run>/<id>_in/description.yaml).
DESCRIPTION_YAML = """description: >
  Reproduce the geometry as accurately as possible from the drawing.

input_files:
  - input.png

input_type: text+image
"""

RASTER_DPI = 260  # ~3040x2150 for an A4 page — matches real fixture input.png


def _load_part(part_py: Path):
    """Exec a fixture's part.py and return its namespace (with ``part``, ``title``)."""
    ns = runpy.run_path(str(part_py))
    if "part" not in ns:
        raise SystemExit(f"{part_py} defines no module-level `part`")
    return ns


def _drawing_pdf(ns: dict, gt_step: Path, title: str, tmp: Path) -> Path:
    """Render the drawing PDF and return its path.

    Two paths, one output. If ``part.py`` defines an ``author()`` hook it must
    return a configured draftwright ``Sheet``; we build and export that (the
    declarative path — the fixture owns exactly which dimensions are stated vs.
    inferred). Otherwise draftwright recognises features from the STEP.
    """
    author = ns.get("author")
    if callable(author):
        drawing = author().build()
        return Path(drawing.export_pdf(str(tmp / "dwg")))

    prefix = tmp / "dwg"
    subprocess.run(
        ["draftwright", str(gt_step), "--format", "pdf",
         "--out", str(prefix), "--title", title],
        check=True,
    )
    return prefix.with_suffix(".pdf")


def author_one(fixture_dir: Path) -> None:
    part_py = fixture_dir / "part.py"
    if not part_py.is_file():
        raise SystemExit(f"no part.py in {fixture_dir}")

    from build123d import export_step  # local import: needs the authoring env

    ns = _load_part(part_py)
    part = ns["part"]
    title = ns.get("title") or fixture_dir.name

    gt_step = fixture_dir / "ground_truth.step"
    export_step(part, str(gt_step))

    with tempfile.TemporaryDirectory() as tmp:
        pdf = _drawing_pdf(ns, gt_step, title, Path(tmp))

        # Rasterise page 1 -> input.png (the agent's only visual input).
        import fitz  # pymupdf

        pix = fitz.open(str(pdf))[0].get_pixmap(dpi=RASTER_DPI)
        pix.save(str(fixture_dir / "input.png"))

    (fixture_dir / "description.yaml").write_text(DESCRIPTION_YAML)
    print(f"authored {fixture_dir.name}: ground_truth.step, input.png, description.yaml")


def main(argv: list[str]) -> int:
    ids = argv or sorted(p.name for p in FIXTURES_DIR.iterdir() if p.is_dir())
    for fid in ids:
        author_one(FIXTURES_DIR / fid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
