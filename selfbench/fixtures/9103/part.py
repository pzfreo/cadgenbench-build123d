"""Self-bench editing fixture 9103: chamfer -> fillet on the extreme end face.

A thick-walled flanged tube along X. Both end faces carry 2 mm chamfers on
their inner and outer circular edges. Only the end face furthest in -X is to change. Tests
selecting the face by an extreme-position qualifier, converting both edges on
it, and leaving the identical-looking opposite end untouched. The new fillets
are much larger than the old chamfers so the change is big enough for the
shape metric to register (a like-for-like 2 mm swap is below its resolution).
"""

from build123d import Align, Cylinder, Pos, Rot, chamfer, fillet

edit = ("Both circular edges (inner and outer) of the end face furthest in the -X "
        "direction are chamfered. Replace those two chamfers with fillets of "
        "radius 6 mm.")

ALONG_X = (Align.CENTER, Align.CENTER, Align.MIN)


def _end_edges(shape, at_max: bool):
    bb = shape.bounding_box()
    x = bb.max.X if at_max else bb.min.X
    return [e for e in shape.edges()
            if e.geom_type.name == "CIRCLE" and abs(e.center().X - x) < 1e-6]


def build(minus_x_fillet: bool):
    body = Rot(0, 90, 0) * Cylinder(28, 60, align=ALONG_X)
    body += Pos(46, 0, 0) * Rot(0, 90, 0) * Cylinder(42, 14, align=ALONG_X)
    body -= Rot(0, 90, 0) * Cylinder(12, 60, align=ALONG_X)
    body = chamfer(_end_edges(body, True), 2)
    minus = _end_edges(body, False)
    return fillet(minus, 6) if minus_x_fillet else chamfer(minus, 2)


input_part = build(False)
part = build(True)
