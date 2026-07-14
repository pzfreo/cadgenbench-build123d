"""Self-bench fixture 9013: thin-wall shelled cover — DERIVED-height dimensioning.

Inference-load pair with 9011: the SAME solid, but the drawing states the
overall height (48) and the boss height (10), forcing the reader to derive the
body height (48 - 10 = 38). GPT-5.5 reliably mis-reads this — it treats the
overall 48 as the body height and stacks the boss to a 58-tall part (3/3
samples), scoring ~0.63 vs ~0.93 on the direct-dimensioned 9011. A ~0.30 swing
from one dimensioning change on identical geometry: the difficulty is
dimension *inference*, not the shell. Mirrors CADGenBench's deliberately
awkward, standards-departing dimensioning. See selfbench/README.md
"Inference-load fixtures".

Authored via the declarative draftwright ``Sheet`` API (see 9011).
"""

from build123d import Box, Cylinder, Pos

title = "Thin-Wall Cover"

WALL = 3.0
L, W, H = 90, 64, 38                                          # outer envelope
outer = Box(L, W, H)                                          # z: -19 .. 19
cavity = Pos(0, 0, -WALL) * Box(L - 2 * WALL, W - 2 * WALL, H)  # open-bottom pocket, 3 mm walls
boss = Pos(0, 0, H / 2 + 5) * Cylinder(14, 10)               # Ø28 x 10 boss on top (z: 19 .. 29)
bore = Pos(0, 0, 15) * Cylinder(6, 40)                       # Ø12 THRU bore

part = outer - cavity + boss - bore


def author():
    """Drawing forces the body height to be DERIVED: overall 48 - boss 10."""
    from draftwright import Sheet

    sh = Sheet(part, title=title)
    sh.envelope()
    sh.boss(boss)                                             # Ø28
    sh.hole(bore).through()                                   # Ø12 THRU
    sh.pocket(cavity)                                         # inner 84 x 58 x 38 DEEP
    sh.dimension(kind="linear", value=H + 10, label=str(H + 10), dominant_axis="z",
                 ref_pts=[(-L / 2, 0, -H / 2), (-L / 2, 0, H / 2 + 10)])  # OVERALL 48 (body + boss)
    sh.dimension(kind="linear", value=10, label="10", dominant_axis="z",
                 ref_pts=[(14, 0, H / 2), (14, 0, H / 2 + 10)])           # boss 10 -> body = 48 - 10
    return sh
