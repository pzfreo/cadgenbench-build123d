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

**Editing fixtures.** If ``part.py`` also defines ``input_part`` (the starting
solid) and ``edit`` (the change request), the fixture is an editing task:
``part`` is the edited ground truth, and instead of a drawing we write
``input.step``, ``edit_description.txt`` and ``renders/{iso,front,top,right}.png``
of the starting solid — the same inputs a real CADGenBench editing fixture
ships. Renders need a display; on a headless Linux box without one we start
``Xvfb`` ourselves.

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

EDIT_DESCRIPTION_YAML = """description: >
  {edit}

task_type: editing
input_files:
  - input.step

input_type: text+step
"""

# Camera presets mirrored from cadgenbench.common.camera_presets (Z-up;
# direction points from the target toward the camera).
_S3 = 3 ** -0.5
RENDER_VIEWS = {
    "iso": ((_S3, -_S3, _S3), (0, 0, 1)),
    "front": ((0, -1, 0), (0, 0, 1)),
    "top": ((0, 0, 1), (0, 1, 0)),
    "right": ((1, 0, 0), (0, 0, 1)),
}

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


def _ensure_display() -> None:
    """Start a private Xvfb for VTK when running headless (no DISPLAY)."""
    import os
    import time

    if os.environ.get("DISPLAY") or sys.platform != "linux":
        return
    subprocess.Popen(["Xvfb", ":379", "-screen", "0", "1024x768x24"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    os.environ["DISPLAY"] = ":379"


def _render_views(shape, renders_dir: Path) -> None:
    """Shaded PNG renders of *shape* at the CADGenBench default views."""
    _ensure_display()
    import pyvista as pv
    from build123d import export_stl

    renders_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        stl = Path(tmp) / "shape.stl"
        export_stl(shape, str(stl), tolerance=0.01, angular_tolerance=0.1)
        mesh = pv.read(str(stl))
    for name, (direction, up) in RENDER_VIEWS.items():
        pl = pv.Plotter(off_screen=True, window_size=(1024, 768))
        pl.set_background("white")
        pl.add_mesh(mesh, color="#dfe2e6", specular=0.2)
        pl.camera_position = [direction, (0, 0, 0), up]
        pl.reset_camera()
        pl.camera.focal_point = mesh.center
        pl.screenshot(str(renders_dir / f"{name}.png"))
        pl.close()


def _author_edit(fixture_dir: Path, ns: dict) -> None:
    from build123d import export_step

    export_step(ns["input_part"], str(fixture_dir / "input.step"))
    export_step(ns["part"], str(fixture_dir / "ground_truth.step"))
    edit = " ".join(ns["edit"].split())
    (fixture_dir / "edit_description.txt").write_text(edit + "\n")
    (fixture_dir / "description.yaml").write_text(EDIT_DESCRIPTION_YAML.format(edit=edit))
    _render_views(ns["input_part"], fixture_dir / "renders")
    print(f"authored {fixture_dir.name} (editing): input.step, ground_truth.step, "
          "edit_description.txt, renders/, description.yaml")


def author_one(fixture_dir: Path) -> None:
    part_py = fixture_dir / "part.py"
    if not part_py.is_file():
        raise SystemExit(f"no part.py in {fixture_dir}")

    from build123d import export_step  # local import: needs the authoring env

    ns = _load_part(part_py)
    if "input_part" in ns:
        _author_edit(fixture_dir, ns)
        return
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
