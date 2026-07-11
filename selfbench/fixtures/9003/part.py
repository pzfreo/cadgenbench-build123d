"""Self-bench fixture 9003: circular flange with a bolt-hole circle (medium).

A round flange with a central bore and six equally-spaced bolt holes on a pitch
circle. Tests draftwright's hole-pattern recognition and PCD dimensioning — a
feature type distinct from the prismatic fixtures.
"""

import math

from build123d import Cylinder, Pos

title = "Bolt-Circle Flange"

disk = Cylinder(40, 10)                       # Ø80, 10 thick
disk -= Cylinder(10, 10)                       # central Ø20 bore
for i in range(6):                             # 6× Ø8 on a Ø60 pitch circle
    a = math.radians(60 * i)
    disk -= Pos(30 * math.cos(a), 30 * math.sin(a), 0) * Cylinder(4, 10)

part = disk
