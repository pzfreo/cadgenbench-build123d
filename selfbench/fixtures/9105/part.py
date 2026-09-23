"""Self-bench editing fixture 9105: lower the round-topped bosses.

A plate carrying four cylindrical bosses with filleted (rounded) tops and two
square flat-topped bosses of the same height as decoys. The request lowers the
rounded bosses by 5 mm. Tests the qualifier ("top-rounded, cylindrical") and
that the rounded top is preserved at the new height rather than cut flat.
"""

from build123d import Align, Box, Cylinder, Pos, fillet

edit = "Reduce the height of the cylindrical bosses with rounded tops by 5 mm each."

UP = (Align.CENTER, Align.CENTER, Align.MIN)


def build(boss_h: float):
    body = Box(120, 80, 10, align=UP)
    for x, y in ((-40, -22), (-40, 22), (40, -22), (40, 22)):
        boss = Pos(x, y, 10) * Cylinder(7, boss_h, align=UP)
        top = boss.edges().sort_by(lambda e: e.center().Z)[-1]
        body += fillet(top, 3)
    for x in (-12, 12):
        body += Pos(x, 0, 10) * Box(12, 12, 20, align=UP)
    return body


input_part = build(20)
part = build(15)
