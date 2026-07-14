"""Self-bench fixture 9016: long thin-wall cover — derived body height.

Elongated-footprint variant of the 9013 derived-height trap (squat shelled box,
single boss on top). The drawing states the overall height (50) and the boss
height (12), forcing the body height to be derived (50 - 12 = 38). GPT-5.5 reads
the overall as the body height and stacks the boss into a too-tall part.
Inference-load hard fixture (< 0.65 for GPT-5.5).

Declarative draftwright ``Sheet`` drawing (see 9011).
"""

from build123d import Box, Cylinder, Pos

title = "Long Cover"

WALL = 3.0
L, W, H = 130, 54, 38                                        # body (outer envelope)
outer = Box(L, W, H)                                         # z: -19 .. 19
cavity = Pos(0, 0, -WALL) * Box(L - 2 * WALL, W - 2 * WALL, H)  # open-bottom pocket, 3 mm walls
boss = Pos(0, 0, H / 2 + 6) * Cylinder(14, 12)             # Ø28 x 12 boss (z: 19 .. 31)
bore = Pos(0, 0, 12) * Cylinder(6, 80)                     # Ø12 THRU bore

part = outer - cavity + boss - bore


def author():
    """Overall height (50) + boss (12) stated; body height must be derived."""
    from draftwright import Sheet

    sh = Sheet(part, title=title)
    sh.envelope()
    sh.boss(boss)                                            # Ø28
    sh.hole(bore).through()                                  # Ø12 THRU
    sh.pocket(cavity)                                        # inner 124 x 48 x 38 DEEP
    sh.dimension(kind="linear", value=H + 12, label=str(H + 12), dominant_axis="z",
                 ref_pts=[(-L / 2, 0, -H / 2), (-L / 2, 0, H / 2 + 12)])  # OVERALL 50
    sh.dimension(kind="linear", value=12, label="12", dominant_axis="z",
                 ref_pts=[(14, 0, H / 2), (14, 0, H / 2 + 12)])          # boss 12 -> body = 50 - 12
    return sh
