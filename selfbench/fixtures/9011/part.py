"""Self-bench fixture 9011: thin-wall shelled cover — DIRECT dimensioning.

Inference-load pair with 9013: identical solid, different drawing. Here the
body height is stated directly (38). On 9013 the reader must derive it
(overall 48 - boss 10). The geometry is held constant so the pair isolates
dimensioning-*inference* load from geometry: GPT-5.5 scores ~0.93 here vs ~0.63
on 9013 (n=3 each, near-zero variance). See selfbench/README.md
"Inference-load fixtures".

Authored via the declarative draftwright ``Sheet`` API rather than STEP
auto-recognition, which drops the boss diameter callout (draftwright#629); the
``author()`` hook below owns exactly which dimensions the drawing states.
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
    """Fully-dimensioned drawing with the body height (38) stated DIRECTLY."""
    from draftwright import Sheet

    sh = Sheet(part, title=title)
    sh.envelope()
    sh.boss(boss)                                             # Ø28
    sh.hole(bore).through()                                   # Ø12 THRU
    sh.pocket(cavity)                                         # inner 84 x 58 x 38 DEEP
    sh.dimension(kind="linear", value=H, label=str(H), dominant_axis="z",
                 ref_pts=[(-L / 2, 0, -H / 2), (-L / 2, 0, H / 2)])   # body height 38, stated
    sh.dimension(kind="linear", value=10, label="10", dominant_axis="z",
                 ref_pts=[(14, 0, H / 2), (14, 0, H / 2 + 10)])       # boss height 10
    return sh
