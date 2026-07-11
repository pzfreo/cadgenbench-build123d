"""Self-bench fixture 9007: multi-step turned shaft with a groove (hard, rotational).

Five coaxial diameter steps, a narrow retaining groove, and a through bore. The
difficulty is the profile chain — five diameters and five lengths that must all
be read and stacked correctly; a single wrong length shifts everything above it.
"""

from build123d import Cylinder, Pos

title = "Multi-Step Shaft"

shaft = (
    Pos(0, 0, 7.5) * Cylinder(30, 15)    # Ø60 flange   z:0..15
    + Pos(0, 0, 32) * Cylinder(20, 34)   # Ø40 body     z:15..49
    + Pos(0, 0, 53) * Cylinder(13, 8)    # Ø26 groove   z:49..57
    + Pos(0, 0, 74) * Cylinder(20, 34)   # Ø40 body     z:57..91
    + Pos(0, 0, 107) * Cylinder(14, 32)  # Ø28 nose     z:91..123
)
shaft -= Pos(0, 0, 61.5) * Cylinder(8, 123)  # Ø16 through bore

part = shaft
