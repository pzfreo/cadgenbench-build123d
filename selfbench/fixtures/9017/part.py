"""Self-bench fixture 9017: multi-level derived-dimension housing.

The drawing states the complete 67 mm height, 9 mm base flange, and 14 mm
top boss. The housing body must be derived as 67 - 9 - 14 = 44 mm. A deep
underside cavity, counterbored central bore, and four-hole flange pattern make
the interpretation and feature inventory materially harder than fixture 9016.
"""

from build123d import Box, Cylinder, Pos

title = "Counterbored Flange Housing"

FLANGE_LENGTH = 138.0
FLANGE_WIDTH = 96.0
FLANGE_HEIGHT = 9.0
BODY_LENGTH = 116.0
BODY_WIDTH = 74.0
BODY_HEIGHT = 44.0
BOSS_HEIGHT = 14.0
OVERALL_HEIGHT = FLANGE_HEIGHT + BODY_HEIGHT + BOSS_HEIGHT

WALL = 7.0
ROOF = 6.0
BOSS_DIAMETER = 48.0
BORE_DIAMETER = 20.0
COUNTERBORE_DIAMETER = 34.0
COUNTERBORE_DEPTH = 6.0
MOUNT_HOLE_DIAMETER = 9.0
MOUNT_SPAN_X = 116.0
MOUNT_SPAN_Y = 74.0

base_z = -OVERALL_HEIGHT / 2
flange_center_z = base_z + FLANGE_HEIGHT / 2
body_bottom_z = base_z + FLANGE_HEIGHT
body_center_z = body_bottom_z + BODY_HEIGHT / 2
body_top_z = body_bottom_z + BODY_HEIGHT
boss_center_z = body_top_z + BOSS_HEIGHT / 2
boss_top_z = body_top_z + BOSS_HEIGHT

flange = Pos(0, 0, flange_center_z) * Box(FLANGE_LENGTH, FLANGE_WIDTH, FLANGE_HEIGHT)
body = Pos(0, 0, body_center_z) * Box(BODY_LENGTH, BODY_WIDTH, BODY_HEIGHT)

# The nominal cutter is BODY_HEIGHT deep and starts below the body, leaving a
# visible ROOF-thick top after intersection with the housing body.
cavity = Pos(0, 0, body_center_z - ROOF) * Box(
    BODY_LENGTH - 2 * WALL, BODY_WIDTH - 2 * WALL, BODY_HEIGHT
)

boss = Pos(0, 0, boss_center_z) * Cylinder(BOSS_DIAMETER / 2, BOSS_HEIGHT)
bore = Pos(0, 0, body_top_z + (BOSS_HEIGHT - ROOF) / 2) * Cylinder(
    BORE_DIAMETER / 2, BOSS_HEIGHT + ROOF
)
counterbore = Pos(0, 0, boss_top_z - COUNTERBORE_DEPTH / 2) * Cylinder(
    COUNTERBORE_DIAMETER / 2, COUNTERBORE_DEPTH
)

mount_holes = []
for x in (-MOUNT_SPAN_X / 2, MOUNT_SPAN_X / 2):
    for y in (-MOUNT_SPAN_Y / 2, MOUNT_SPAN_Y / 2):
        mount_holes.append(
            Pos(x, y, flange_center_z) * Cylinder(MOUNT_HOLE_DIAMETER / 2, FLANGE_HEIGHT)
        )

part = flange + body - cavity + boss - bore - counterbore
for hole in mount_holes:
    part -= hole


def author():
    """Declare all features while leaving the body height as a three-level chain."""
    from draftwright import Sheet

    sh = Sheet(part, title=title)
    sh.envelope()
    sh.boss(boss)
    sh.hole(bore).through().cbore(
        diameter=COUNTERBORE_DIAMETER, depth=COUNTERBORE_DEPTH
    )
    sh.pocket(cavity)
    for hole in mount_holes:
        sh.hole(hole).through()

    sh.dimension(kind="linear", value=OVERALL_HEIGHT, label="67", dominant_axis="z",
                 ref_pts=[(-FLANGE_LENGTH / 2, 0, base_z),
                          (-FLANGE_LENGTH / 2, 0, boss_top_z)])
    sh.dimension(kind="linear", value=FLANGE_HEIGHT, label="9", dominant_axis="z",
                 ref_pts=[(FLANGE_LENGTH / 2, 0, base_z),
                          (FLANGE_LENGTH / 2, 0, body_bottom_z)])
    sh.dimension(kind="linear", value=BOSS_HEIGHT, label="14", dominant_axis="z",
                 ref_pts=[(BOSS_DIAMETER / 2, 0, body_top_z),
                          (BOSS_DIAMETER / 2, 0, boss_top_z)])
    sh.notes([
        "4X DIA 9 THRU ON 116 X 74 RECTANGULAR CENTERS",
        "CENTER BORE DIA 20 THRU",
        "COUNTERBORE DIA 34 X 6 DEEP",
    ], title="FEATURES", number=False, prefer="tr")
    return sh
