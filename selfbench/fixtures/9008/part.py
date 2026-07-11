"""Self-bench fixture 9008: L angle bracket, holes on two faces (hard, 3D/off-axis).

An L-bracket: a horizontal base and a vertical wall at 90°, each carrying holes.
The base holes are drilled through Z; the wall holes are drilled through Y
(side-drilled). Genuinely harder than the plate fixtures — the agent has to build
two perpendicular plates and place holes on non-parallel faces.
"""

from build123d import Box, Cylinder, Pos, Rotation

title = "Angle Bracket"

base = Pos(0, 0, 5) * Box(80, 60, 10)          # x:-40..40  y:-30..30  z:0..10
wall = Pos(0, 25, 35) * Box(80, 10, 50)        # back wall  y:20..30  z:10..60
bracket = base + wall

# Base: 2× Ø10 through Z, toward the front (clear of the wall).
for cx in (-24, 24):
    bracket -= Pos(cx, -15, 5) * Cylinder(5, 12)

# Wall: 2× Ø8 through Y (side-drilled), Rotation about X turns the axis to Y.
for cx in (-22, 22):
    bracket -= Pos(cx, 25, 38) * Rotation(90, 0, 0) * Cylinder(4, 14)

part = bracket
