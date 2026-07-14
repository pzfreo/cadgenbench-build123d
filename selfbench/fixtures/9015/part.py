"""Self-bench fixture 9015: square thin-wall cover — derived body height.

Square-footprint variant of the 9013 derived-height trap. The drawing states the
overall height (50) and the boss height (10), forcing the body height to be
derived (50 - 10 = 40). GPT-5.5 reads the overall as the body height and stacks
the boss into a too-tall part. Inference-load hard fixture (< 0.65 for GPT-5.5).

Declarative draftwright ``Sheet`` drawing (see 9011).
"""

from build123d import Box, Cylinder, Pos

title = "Square Cover"

WALL = 3.0
L, W, H = 82, 82, 40                                         # body (outer envelope)
outer = Box(L, W, H)                                         # z: -20 .. 20
cavity = Pos(0, 0, -WALL) * Box(L - 2 * WALL, W - 2 * WALL, H)  # open-bottom pocket, 3 mm walls
boss = Pos(0, 0, H / 2 + 5) * Cylinder(14, 10)             # Ø28 x 10 boss (z: 20 .. 30)
bore = Pos(0, 0, 12) * Cylinder(6, 80)                     # Ø12 THRU bore

part = outer - cavity + boss - bore


def author():
    """Overall height (50) + boss (10) stated; body height must be derived."""
    from draftwright import Sheet

    sh = Sheet(part, title=title)
    sh.envelope()
    sh.boss(boss)                                            # Ø28
    sh.hole(bore).through()                                  # Ø12 THRU
    sh.pocket(cavity)                                        # inner 76 x 76 x 40 DEEP
    sh.dimension(kind="linear", value=H + 10, label=str(H + 10), dominant_axis="z",
                 ref_pts=[(-L / 2, 0, -H / 2), (-L / 2, 0, H / 2 + 10)])  # OVERALL 50
    sh.dimension(kind="linear", value=10, label="10", dominant_axis="z",
                 ref_pts=[(14, 0, H / 2), (14, 0, H / 2 + 10)])          # boss 10 -> body = 50 - 10
    return sh
