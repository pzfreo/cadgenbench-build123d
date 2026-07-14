"""Self-bench fixture 9014: wide thin-wall cover — derived body height.

Same failure mode as 9013 (squat shelled box, small boss on top) on a wider
footprint. The drawing states the overall height (48) and the boss height (10),
forcing the body height to be derived (48 - 10 = 38). GPT-5.5 reads the overall
as the body height and stacks the boss into a too-tall part; the thin walls make
that a large volume error. Inference-load hard fixture (< 0.65 for GPT-5.5).

Declarative draftwright ``Sheet`` drawing (see 9011).
"""

from build123d import Box, Cylinder, Pos

title = "Wide Cover"

WALL = 3.0
L, W, H = 104, 58, 38                                        # body (outer envelope)
outer = Box(L, W, H)                                         # z: -19 .. 19
cavity = Pos(0, 0, -WALL) * Box(L - 2 * WALL, W - 2 * WALL, H)  # open-bottom pocket, 3 mm walls
boss = Pos(0, 0, H / 2 + 5) * Cylinder(15, 10)              # Ø30 x 10 boss (z: 19 .. 29)
bore = Pos(0, 0, 12) * Cylinder(7, 80)                      # Ø14 THRU bore

part = outer - cavity + boss - bore


def author():
    """Overall height (48) + boss (10) stated; body height must be derived."""
    from draftwright import Sheet

    sh = Sheet(part, title=title)
    sh.envelope()
    sh.boss(boss)                                            # Ø30
    sh.hole(bore).through()                                  # Ø14 THRU
    sh.pocket(cavity)                                        # inner 98 x 52 x 38 DEEP
    sh.dimension(kind="linear", value=H + 10, label=str(H + 10), dominant_axis="z",
                 ref_pts=[(-L / 2, 0, -H / 2), (-L / 2, 0, H / 2 + 10)])  # OVERALL 48
    sh.dimension(kind="linear", value=10, label="10", dominant_axis="z",
                 ref_pts=[(15, 0, H / 2), (15, 0, H / 2 + 10)])          # boss 10 -> body = 48 - 10
    return sh
