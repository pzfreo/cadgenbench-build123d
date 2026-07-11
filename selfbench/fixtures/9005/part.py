"""Self-bench fixture 9005: stepped shaft (medium-hard, rotational).

A coaxial two-diameter turned shaft with a concentric through bore. Tests
draftwright's rotational path — turned-diameter callouts (Ø40, Ø24), the
step-length chain, and a concentric bore located by the centreline.
"""

from build123d import Cylinder, Pos

title = "Stepped Shaft"

big = Pos(0, 0, 7.5) * Cylinder(20, 15)     # Ø40, z:0..15
small = Pos(0, 0, 30) * Cylinder(12, 30)    # Ø24, z:15..45
bore = Pos(0, 0, 22.5) * Cylinder(5, 45)    # Ø10 concentric through bore

part = big + small - bore
