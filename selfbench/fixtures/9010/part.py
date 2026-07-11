"""Self-bench fixture 9010: countersunk + counterbored holes (hard, feature-type).

Three 90° countersunk holes (Ø6 THRU, csk to Ø14) plus one counterbored hole
(Ø9 THRU, Ø18 c'bore) on one plate. Forces the agent to distinguish a
countersink (conical) from a counterbore (cylindrical) and get the csk angle
right — a common confusion.
"""

from build123d import Box, Cone, Cylinder, Pos

title = "Countersunk Plate"

plate = Box(90, 60, 12)                          # x:-45..45  y:-30..30  z:-6..6

# Three Ø6 THRU with a 90° countersink to Ø14 at the top face (z=+6).
for cx, cy in [(-30, -15), (5, 12), (30, -8)]:
    plate -= Pos(cx, cy, 0) * Cylinder(3, 12)        # through bore
    plate -= Pos(cx, cy, 4) * Cone(3, 7, 4)          # 90° csk, Ø6->Ø14 over z:2..6

# One counterbore for contrast (Ø9 THRU, Ø18 c'bore 6 deep from top).
plate -= Pos(-10, 18, 0) * Cylinder(4.5, 12)
plate -= Pos(-10, 18, 3) * Cylinder(9, 6)

part = plate
