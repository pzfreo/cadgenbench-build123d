"""Self-bench fixture 9006: dense multi-feature plate (hard).

A fully-asymmetric plate carrying six features of three kinds — two Ø10 and two
Ø6 through holes plus two counterbored holes (Ø9 THRU / Ø18 c'bore 6 deep). Every
feature has a distinct, well-separated X and Y so all location dims place
legibly. The densest fixture: lots to read and place correctly, all feature
types draftwright dimensions cleanly.
"""

from build123d import Box, Cylinder, Pos

title = "Multi-Feature Plate"

plate = Box(110, 70, 20)                        # x:-55..55  y:-35..35

for cx, cy in [(-43, -23), (43, 27)]:           # 2× Ø10 through
    plate -= Pos(cx, cy, 0) * Cylinder(5, 20)
for cx, cy in [(-7, -3), (11, 17)]:             # 2× Ø6 through
    plate -= Pos(cx, cy, 0) * Cylinder(3, 20)
for cx, cy in [(-25, 7), (29, -13)]:            # 2× counterbore (Ø9 THRU / Ø18 ↓6)
    plate -= Pos(cx, cy, 0) * Cylinder(4.5, 20)
    plate -= Pos(cx, cy, 7) * Cylinder(9, 6)

part = plate
