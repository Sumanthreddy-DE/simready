"""Conservative healing helpers for Phase 1B."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from OCC.Core.BRepCheck import BRepCheck_Analyzer
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
    from OCC.Core.ShapeFix import ShapeFix_Shape
except ImportError:  # pragma: no cover
    BRepCheck_Analyzer = None
    IFSelect_RetDone = None
    STEPControl_AsIs = None
    STEPControl_Writer = None
    ShapeFix_Shape = None


@dataclass
class HealResult:
    healed_shape: Any
    applied: bool
    export_path: str | None = None
    summary: dict[str, Any] = field(default_factory=dict)


def heal_shape(shape: Any, export_path: str | None = None) -> HealResult:
    if ShapeFix_Shape is None:
        return HealResult(
            healed_shape=shape,
            applied=False,
            export_path=None,
            summary={
                "attempted": False,
                "applied": False,
                "valid_before": None,
                "valid_after": None,
                "notes": ["Healing dependencies are not available in the current environment."],
            },
        )

    valid_before = None
    if BRepCheck_Analyzer is not None:
        try:
            valid_before = BRepCheck_Analyzer(shape).IsValid()
        except Exception:
            valid_before = None

    fixer = ShapeFix_Shape(shape)
    fixer.Perform()
    healed_shape = fixer.Shape()

    valid_after = None
    if BRepCheck_Analyzer is not None:
        try:
            valid_after = BRepCheck_Analyzer(healed_shape).IsValid()
        except Exception:
            valid_after = None

    applied = healed_shape is not None
    exported_to = None
    notes: list[str] = []

    if export_path:
        exported_to = export_healed_shape(healed_shape, export_path)
        if exported_to is None:
            notes.append("Healed STEP export failed.")
        else:
            notes.append("Healed STEP export succeeded.")

    if valid_before is False and valid_after is True:
        notes.append("Global OCC validity improved after healing.")
    elif valid_before == valid_after:
        notes.append("Healing completed with no global validity change detected.")

    return HealResult(
        healed_shape=healed_shape,
        applied=applied,
        export_path=exported_to,
        summary={
            "attempted": True,
            "applied": applied,
            "valid_before": valid_before,
            "valid_after": valid_after,
            "notes": notes,
        },
    )


def export_healed_shape(shape: Any, export_path: str) -> str | None:
    if STEPControl_Writer is None or STEPControl_AsIs is None or IFSelect_RetDone is None:
        return None

    output = Path(export_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    status = writer.Write(str(output))
    if status != IFSelect_RetDone:
        return None
    return str(output)
