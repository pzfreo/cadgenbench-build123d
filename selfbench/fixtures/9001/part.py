"""Self-bench fixture 9001: rectangular plate with a centred through hole.

Authoring contract (see selfbench/README.md): each fixture's ``part.py`` must
define a module-level ``part`` (a build123d solid/compound) — this is the
*ground truth* the agent is scored against. An optional ``title`` string is
used for the drawing's title block. Nothing here is ever shown to the agent;
only the rendered ``input.png`` + ``description.yaml`` are.
"""

from build123d import Box, Cylinder, Pos

title = "Plate with Centred Bore"

part = Box(60, 40, 10) - Pos(0, 0, 0) * Cylinder(6, 40)
