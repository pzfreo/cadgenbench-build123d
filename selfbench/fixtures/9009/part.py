"""Self-bench fixture 9009: dense 10-feature plate (hard, reading load).

A large plate carrying ten located features across four sizes plus two
counterbores. Nothing exotic — the difficulty is parsing a dense dimension
ladder and pairing each callout with the right location without slips.
"""

from build123d import Box, Cylinder, Pos

title = "Ten-Feature Plate"

plate = Box(130, 90, 20)                         # x:-65..65  y:-45..45

for cx, cy in [(-55, -36), (55, 36)]:            # 2× Ø14 through
    plate -= Pos(cx, cy, 0) * Cylinder(7, 20)
for cx, cy in [(-35, 20), (45, -20)]:            # 2× Ø10 through
    plate -= Pos(cx, cy, 0) * Cylinder(5, 20)
for cx, cy in [(-15, -12), (5, 28), (25, -4)]:   # 3× Ø6 through
    plate -= Pos(cx, cy, 0) * Cylinder(3, 20)
for cx, cy in [(-45, 4), (15, -28), (35, 12)]:   # 3× counterbore (Ø9 THRU / Ø18 ↓6)
    plate -= Pos(cx, cy, 0) * Cylinder(4.5, 20)
    plate -= Pos(cx, cy, 7) * Cylinder(9, 6)

part = plate
