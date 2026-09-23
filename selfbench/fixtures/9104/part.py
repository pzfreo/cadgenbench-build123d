"""Self-bench editing fixture 9104: thicken the ribs on the underside.

A plate with three stiffening ribs on its underside (running along X) and two
thinner gussets on top (running along Y) as decoys. The request thickens the
underside ribs. Ground-truth convention: each rib grows symmetrically about its
own mid-plane (centre and height unchanged) — the natural reading of "thicker
rib", but an assumption; keep it in mind if a variant disagrees on this one.
"""

from build123d import Align, Box, Pos

edit = ("Increase the thickness of the ribs on the underside of the plate by 4 mm "
        "each, from 6 mm to 10 mm.")


def build(rib_t: float):
    body = Box(110, 80, 10, align=(Align.CENTER, Align.CENTER, Align.MIN))
    for y in (-26, 0, 26):
        body += Pos(0, y, 0) * Box(110, rib_t, 18, align=(Align.CENTER, Align.CENTER, Align.MAX))
    for x in (-35, 35):
        body += Pos(x, 0, 10) * Box(4, 80, 12, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return body


input_part = build(6)
part = build(10)
