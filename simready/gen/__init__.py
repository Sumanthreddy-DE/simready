"""Geometry generation (geometry-gen-mvp).

The LLM emits a typed ``PartSpec`` via the ``build_part`` tool; a trusted
executor maps it to pythonOCC primitives and writes a STEP file. No LLM code
is ever exec'd. See ``docs/exec-plans/geometry-gen-mvp.md`` and
``docs/adr/0001-geometry-gen-dsl-over-codegen.md``.
"""

from simready.gen.spec import BoxOp, CutOp, CylOp, FuseOp, PartSpec, Op

__all__ = ["BoxOp", "CutOp", "CylOp", "FuseOp", "Op", "PartSpec"]
