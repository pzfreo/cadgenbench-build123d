"""Self-bench editing fixture 9101: shrink the one horizontal bore.

A base block carries two vertical bores and one upright lug with a horizontal
bore. The large vertical bore has the SAME starting diameter (Ø16) as the
horizontal one, so matching the stated "from" value alone cannot pick the
target — only the orientation qualifier ("horizontal") does. Tests resolving a
feature by an axis qualifier among numerically identical decoys.
"""

from build123d import Box, Cylinder, Pos, Rot, Align

edit = "Decrease the diameter of the only horizontal bore from 16 mm to 10 mm."


def build(h_bore_d: float):
    base = Box(90, 60, 18, align=(Align.CENTER, Align.CENTER, Align.MIN))
    lug = Pos(0, 22, 18) * Box(40, 16, 32, align=(Align.CENTER, Align.CENTER, Align.MIN))
    body = base + lug
    body -= Pos(-28, -8, 0) * Cylinder(8, 18, align=(Align.CENTER, Align.CENTER, Align.MIN))
    body -= Pos(30, -12, 0) * Cylinder(3.5, 18, align=(Align.CENTER, Align.CENTER, Align.MIN))
    body -= Pos(30, 12, 0) * Cylinder(3.5, 18, align=(Align.CENTER, Align.CENTER, Align.MIN))
    body -= Pos(0, 22, 36) * Rot(90, 0, 0) * Cylinder(h_bore_d / 2, 16)
    return body


input_part = build(16)
part = build(10)
