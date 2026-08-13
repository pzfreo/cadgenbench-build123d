#!/usr/bin/env python3
"""Render the official CADGenBench build123d system prompt at a pinned commit.

The two upstream source files are cached outside individual fixture workdirs so
parallel Claude Code workers use the same prompt bytes.  A short transport
adapter is appended: the official runner executes returned Python itself,
whereas our subscription-backed Claude Code harness gives the model local
Read/Bash tools to perform that loop in one session.
"""

from __future__ import annotations

import importlib.util
import sys
import urllib.request
from pathlib import Path


UPSTREAM_COMMIT = "33304cf771fc5639144b1df9611e347251052cf8"
RAW_ROOT = f"https://raw.githubusercontent.com/huggingface/cadgenbench/{UPSTREAM_COMMIT}/src/cadgenbench/baseline"
FILES = ("prompt.py", "build123d_cheat_sheet.md", "cadquery_cheat_sheet.md")

DIRECT_ADAPTER = """
## Claude Code harness transport adapter

This experiment runs the official prompt through Claude Code using the user's
Claude Code subscription, rather than through the reference LiteLLM turn
executor. The task files are in your current working directory. For generation
tasks inspect `input.png` with Read; for editing tasks, `input.step` and
reference-view PNGs are present.

Use Write/Edit and Bash to carry out the prompt's Python-code loop yourself in
this persistent session. Run each candidate with `.venv/bin/python`, inspect
stdout/stderr and PNGs with Read, and continue refining. The reference
executor's automatic validation/render feedback is not injected, so perform
those checks yourself. You must leave the final artifact at `output.step`.
""".strip()

MINIMAL_MCP_ADAPTER = """
## Claude Code harness transport adapter

This experiment runs the official prompt through Claude Code using the user's
Claude Code subscription. The engineering drawing is `input.png` in the current
working directory. Use Read to inspect it and Write/Edit to maintain your Python
candidate in `model.py`.

Near the start, call `prepare_drawing(image_path="input.png")` once and inspect
its labelled overview and relevant crops instead of scripting repetitive basic
crop generation. Its regions are spatial evidence only, not interpreted CAD
features; you remain responsible for reading dimensions and understanding form.
When a particular callout or profile remains ambiguous, use `crop_drawing` for
one exact enlarged region. Use `calibrate_drawing` only when printed dimensions
provide trustworthy point correspondences within the same orthographic view;
never calibrate an isometric view or treat pixel scale as stronger evidence than
a printed dimension.

Use the available build123d MCP tools only as execution instruments: promote a
candidate with execute_file, inspect it when useful with measure, render_view, or
cross_sections, check it with validate, and write the final artifact to
`output.step` with export.
You choose the modelling strategy, verification sequence, revisions, and stopping
point. No additional CAD workflow or modelling skill is imposed.
""".strip()


def main() -> None:
    adapter = MINIMAL_MCP_ADAPTER if "--minimal-mcp" in sys.argv[1:] else DIRECT_ADAPTER
    cache = Path(__file__).resolve().parent / ".official_baseline_prompt" / UPSTREAM_COMMIT
    cache.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        path = cache / name
        if not path.exists():
            with urllib.request.urlopen(f"{RAW_ROOT}/{name}", timeout=60) as response:
                path.write_bytes(response.read())

    spec = importlib.util.spec_from_file_location("cgb_official_prompt", cache / "prompt.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load pinned official prompt module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.stdout.write(module.assemble_system_prompt("build123d"))
    sys.stdout.write("\n\n" + adapter + "\n")


if __name__ == "__main__":
    main()
