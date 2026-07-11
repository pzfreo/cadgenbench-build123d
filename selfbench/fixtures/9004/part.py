"""Self-bench fixture 9004: slotted plate (medium).

A plate with a central obround (rounded-end) slot and two off-centre Ø8 through
holes. Tests draftwright's slot dimensioning (overall length + width + location)
alongside plain holes.
"""

from build123d import Box, Cylinder, Pos

title = "Slotted Plate"

plate = Box(100, 50, 10)                      # x:-50..50  y:-25..25

# Central obround slot: 40 long straight + Ø12 rounded ends -> 52 overall, 12 wide.
slot = (
    Box(40, 12, 10)
    + Pos(20, 0, 0) * Cylinder(6, 10)
    + Pos(-20, 0, 0) * Cylinder(6, 10)
)
plate -= slot

# Two off-centre Ø8 through holes (distinct X and Y -> clean 2D location dims).
plate -= Pos(-40, 14, 0) * Cylinder(4, 10)
plate -= Pos(40, -14, 0) * Cylinder(4, 10)

part = plate
