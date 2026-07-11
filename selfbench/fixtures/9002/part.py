"""Self-bench fixture 9002: asymmetric mounting plate — counterbore + 3 holes + keyed corner.

Deliberately harder than 9001 and fully asymmetric (no doubly-symmetric datum
trap): a non-square plate with three off-centre through holes, one counterbored
hole (draftwright renders a Section A-A for it), and a chamfered corner that keys
orientation. Off-centre features force real 2D location dimensions on both axes.
"""

from build123d import (
    Axis, Box, Cylinder, Pos, chamfer,
)

title = "Asymmetric Mounting Plate"

# Plate: 90 x 60 x 20, centred at origin (top face at z = +10).
plate = Box(90, 60, 20)

# Key one vertical corner (+X, +Y) with a 12 mm chamfer -> unambiguous orientation.
corner = plate.edges().filter_by(Axis.Z).sort_by(lambda e: e.center().X + e.center().Y)[-1]
plate = chamfer(corner, 12)

# Three Ø7 through holes — every hole has a distinct, well-separated X and Y so
# each location dim places legibly (no crowded-ladder drops).
for cx, cy in [(-33, -18), (15, -8), (30, 18)]:
    plate -= Pos(cx, cy, 0) * Cylinder(3.5, 20)

# Counterbored hole at (-15, 8): Ø9 through, Ø18 counterbore 6 mm deep from the top.
plate -= Pos(-15, 8, 0) * Cylinder(4.5, 20)     # through bore
plate -= Pos(-15, 8, 7) * Cylinder(9, 6)         # counterbore (z = +4 .. +10)

part = plate
