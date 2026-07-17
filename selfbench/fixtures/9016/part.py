"""Self-bench fixture 9016: derived-height pedestal housing.

The drawing states the 58 mm overall height, 13 mm top boss, and a nominal
45 mm-deep underside cavity. The reader must derive the housing body as
58 - 13 = 45 mm while preserving the visible 5 mm roof.
"""

from build123d import Box, Cylinder, Pos

title = "Pedestal Housing"

LENGTH = 112.0
WIDTH = 76.0
BODY_HEIGHT = 45.0
BOSS_HEIGHT = 13.0
OVERALL_HEIGHT = BODY_HEIGHT + BOSS_HEIGHT
WALL = 6.0
ROOF = 5.0
BOSS_DIAMETER = 36.0
BORE_DIAMETER = 16.0

outer = Box(LENGTH, WIDTH, BODY_HEIGHT)
cavity = Pos(0, 0, -ROOF) * Box(LENGTH - 2 * WALL, WIDTH - 2 * WALL, BODY_HEIGHT)
boss = Pos(0, 0, BODY_HEIGHT / 2 + BOSS_HEIGHT / 2) * Cylinder(BOSS_DIAMETER / 2, BOSS_HEIGHT)
bore = Pos(0, 0, BODY_HEIGHT / 2 + (BOSS_HEIGHT - ROOF) / 2) * Cylinder(
    BORE_DIAMETER / 2, ROOF + BOSS_HEIGHT
)

part = outer - cavity + boss - bore


def author():
    """State overall and boss heights; body height remains derived."""
    from draftwright import Sheet

    sh = Sheet(part, title=title)
    sh.envelope()
    sh.boss(boss)
    sh.hole(bore).through()
    sh.pocket(cavity)
    sh.dimension(kind="linear", value=OVERALL_HEIGHT, label="58", dominant_axis="z",
                 ref_pts=[(-LENGTH / 2, 0, -BODY_HEIGHT / 2),
                          (-LENGTH / 2, 0, BODY_HEIGHT / 2 + BOSS_HEIGHT)])
    sh.dimension(kind="linear", value=BOSS_HEIGHT, label="13", dominant_axis="z",
                 ref_pts=[(BOSS_DIAMETER / 2, 0, BODY_HEIGHT / 2),
                          (BOSS_DIAMETER / 2, 0, BODY_HEIGHT / 2 + BOSS_HEIGHT)])
    return sh
