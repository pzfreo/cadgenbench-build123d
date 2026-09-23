"""Self-bench editing fixture 9102: widen ALL pockets on one side.

A plate with a central through bore and eight identical blind rectangular
pockets — four on each side of the bore. The request names the four on the +X
side. Tests (a) honouring the side qualifier and (b) completing the edit on
every instance — a partial edit (2 of 4) must not be accepted as done.
"""

from build123d import Box, Cylinder, Pos, Align

edit = ("Widen each of the four rectangular pockets on the +X side of the central "
        "bore from 10 mm to 14 mm in X, keeping each pocket centred where it is.")


def build(plus_x_width: float):
    body = Box(140, 70, 16)
    body -= Cylinder(12, 16)
    for sx, w in ((1, plus_x_width), (-1, 10.0)):
        for x in (30, 52):
            for y in (-16, 16):
                body -= Pos(sx * x, y, 8) * Box(w, 20, 7, align=(Align.CENTER, Align.CENTER, Align.MAX))
    return body


input_part = build(10)
part = build(14)
