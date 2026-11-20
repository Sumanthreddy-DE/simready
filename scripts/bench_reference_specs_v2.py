"""Emit simready/bench/prompts/reference_specs_v2.json (SP2 Task 4)."""
import json
import sys


class S:
    def __init__(self):
        self.steps = []

    def add(self, op, **kw):
        self.steps.append({"op": op, **kw})
        return len(self.steps) - 1

    def box(self, dx, dy, dz, at=(0, 0, 0)):
        return self.add("box", dx=dx, dy=dy, dz=dz, at=list(at))

    def cyl(self, r, h, at=(0, 0, 0), axis="z"):
        return self.add("cyl", r=r, h=h, at=list(at), axis=axis)

    def cone(self, r1, r2, h, at=(0, 0, 0), axis="z"):
        return self.add("cone", r1=r1, r2=r2, h=h, at=list(at), axis=axis)

    def sphere(self, r, at=(0, 0, 0)):
        return self.add("sphere", r=r, at=list(at))

    def prism(self, points, h, at=(0, 0, 0), axis="z"):
        return self.add("prism", points=[list(p) for p in points], h=h, at=list(at), axis=axis)

    def rprism(self, sides, af, h, at=(0, 0, 0), axis="z"):
        return self.add("regular_prism", sides=sides, across_flats=af, h=h, at=list(at), axis=axis)

    def polar(self, of, count, center, axis="z"):
        return self.add("polar", of=of, count=count, center=list(center), axis=axis)

    def grid(self, of, nx, ny, dx, dy):
        return self.add("grid", of=of, nx=nx, ny=ny, dx=dx, dy=dy)

    def fillet(self, a, r, edges):
        return self.add("fillet", a=a, r=r, edges=edges)

    def chamfer(self, a, d, edges):
        return self.add("chamfer", a=a, d=d, edges=edges)

    def fuse(self, a, b):
        return self.add("fuse", a=a, b=b)

    def cut(self, a, b):
        return self.add("cut", a=a, b=b)

    def spec(self):
        return {"steps": self.steps}


def c022():
    s = S()
    leaf = s.box(60, 30, 3)
    hole = s.cyl(2.25, 3, (10, 15, 0))
    sink = s.cone(2.25, 4.5, 2.25, (10, 15, 0.75))
    s.cut(leaf, s.grid(s.fuse(hole, sink), 3, 1, 20, 0))
    return s.spec()


def c026():
    s = S()
    body = s.fuse(s.box(50, 40, 5), s.box(50, 5, 40))
    body = s.cut(body, s.grid(s.cyl(2.75, 5, (12.5, 25, 0)), 2, 1, 25, 0))
    s.cut(body, s.grid(s.cyl(2.75, 5, (12.5, 0, 25), "y"), 2, 1, 25, 0))
    return s.spec()


def hex_nut(af, h, bore_r):
    s = S()
    s.cut(s.rprism(6, af, h), s.cyl(bore_r, h))
    return s.spec()


def c037():
    s = S()
    body = s.cut(s.box(60, 30, 20), s.cyl(12.5, 30, (30, 0, 20), "y"))
    s.cut(body, s.grid(s.cyl(3.3, 20, (8, 15, 0)), 2, 1, 44, 0))
    return s.spec()


def c040():
    s = S()
    disc = s.cut(s.cyl(50, 10), s.cyl(15, 10))
    s.cut(disc, s.polar(s.cyl(4.5, 10, (37.5, 0, 0)), 8, (0, 0, 0)))
    return s.spec()


def c041():
    s = S()
    s.fillet(s.box(80, 50, 10), 3, ">z")
    return s.spec()


def c042():
    s = S()
    s.chamfer(s.cyl(5.9975, 60), 1, "all")
    return s.spec()


def c043():
    s = S()
    outer = s.fuse(s.cone(7.5, 40, 60, (0, 0, 30)), s.cyl(7.5, 30))
    inner = s.fuse(s.cone(5.5, 5.5 + 32.5 * 61 / 60, 61, (0, 0, 30)), s.cyl(5.5, 32, (0, 0, -1)))
    s.cut(outer, inner)
    return s.spec()


def c047():
    s = S()
    s.cut(s.cyl(4.9975, 50), s.cyl(1.5025, 12, (-6, 0, 25), "x"))
    return s.spec()


def c051():
    s = S()
    body = s.fuse(s.cyl(3, 20.5), s.cyl(5, 6, (0, 0, 20)))
    s.cut(body, s.rprism(6, 5.02, 4, (0, 0, 23)))
    return s.spec()


def c054():
    s = S()
    body = s.fuse(s.cyl(4, 30.5), s.cyl(7, 3, (0, 0, 30)))
    s.cut(body, s.cyl(1, 20, (-10, 0, 3.5), "x"))
    return s.spec()


def c055():
    s = S()
    body = s.fuse(s.box(60, 40, 5), s.box(5, 40, 60))
    body = s.fuse(body, s.prism([(5, 5), (35, 5), (5, 35)], 5, (0, 17.5, 0), "y"))
    s.cut(body, s.grid(s.cyl(3.3, 5, (35, 7.5, 0)), 1, 2, 0, 25))
    return s.spec()


def c056():
    s = S()
    plate = s.cut(s.box(100, 100, 8), s.cyl(20, 8, (50, 50, 0)))
    plate = s.cut(plate, s.polar(s.cyl(3.3, 8, (80, 50, 0)), 6, (50, 50, 0)))
    s.cut(plate, s.grid(s.cyl(4.5, 8, (10, 10, 0)), 2, 2, 80, 80))
    return s.spec()


def c059():
    s = S()
    shaft = s.chamfer(s.cyl(5, 40), 0.5, "all")
    ring = s.cut(s.cyl(6, 1.1, (0, 0, 5)), s.cyl(4.8, 3.1, (0, 0, 4)))
    s.cut(shaft, ring)
    return s.spec()


def c060(d):
    s = S()
    h = (16 - d) / 2
    tube = s.cut(s.cyl(10, 15), s.cyl(d / 2, 17, (0, 0, -1)))
    s.cut(tube, s.cone(d / 2, 9, h + 1, (0, 0, 15 - h)))
    return s.spec()


def c061():
    s = S()
    body = s.fuse(s.cyl(10, 12), s.sphere(10, (0, 0, 12)))
    body = s.cut(body, s.box(40, 40, 40, (-20, -20, -40)))
    s.cut(body, s.cyl(4.25, 11, (0, 0, -1)))
    return s.spec()


def c062():
    s = S()
    tube = s.cut(s.cyl(12.5, 80), s.cyl(7.5, 82, (0, 0, -1)))
    tube = s.cut(tube, s.cyl(2.5, 30, (-15, 0, 40), "x"))
    s.cut(tube, s.cyl(2.5, 30, (0, -15, 40), "y"))
    return s.spec()


def c063():
    s = S()
    body = s.fuse(s.box(80, 30, 10), s.box(44, 30, 17, (18, 0, 10)))
    body = s.fuse(body, s.cyl(22, 30, (40, 0, 27), "y"))
    body = s.cut(body, s.cyl(10.9975, 32, (40, -1, 27), "y"))
    s.cut(body, s.grid(s.cyl(4.5, 12, (9, 15, -1)), 2, 1, 62, 0))
    return s.spec()


def c064():
    s = S()
    shell = s.cut(s.box(80, 60, 30), s.box(76, 56, 30, (2, 2, 2)))
    body = s.fuse(shell, s.grid(s.cyl(3.5, 28, (6, 6, 2)), 2, 2, 68, 48))
    s.cut(body, s.grid(s.cyl(1.25, 11, (6, 6, 20)), 2, 2, 68, 48))
    return s.spec()


def c065():
    s = S()
    block = s.cut(s.box(40, 40, 30), s.cyl(5, 42, (-1, 12, 10), "x"))
    block = s.cut(block, s.cyl(4, 42, (28, -1, 20), "y"))
    s.cut(block, s.cyl(3, 32, (12, 28, -1)))
    return s.spec()


# c044 has no v2 spec: its frozen bbox check needs all three extents at 30 mm, and an
# axis-aligned hole removes one pole (29.61 mm). Out of v2 vocab (user decision 2026-11-20).
SPECS = {
    "c022": c022(), "c026": c026(), "c033": hex_nut(5.5, 10, 1.25), "c034": hex_nut(12.95, 6.75, 3.4),
    "c037": c037(), "c040": c040(), "c041": c041(), "c042": c042(), "c043": c043(),
    "c047": c047(), "c051": c051(), "c054": c054(), "c055": c055(), "c056": c056(), "c059": c059(),
    # c060: explicit bore 8.4-8.6 and engineer bore 8.9-9.1 are disjoint, so one spec per phrasing.
    "c060": {"explicit": c060(8.5), "engineer": c060(9.0), "intent": c060(8.5)},
    "c061": c061(), "c062": c062(), "c063": c063(), "c064": c064(), "c065": c065(),
}

if __name__ == "__main__":
    out = sys.argv[1]
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(dict(sorted(SPECS.items())), fh, indent=1)
        fh.write("\n")
    print(f"wrote {out} ({len(SPECS)} concepts)")
