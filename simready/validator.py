"""Validation helpers for STEP input files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from OCC.Core.BRepCheck import BRepCheck_Analyzer
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_Reader
except ImportError:  # pragma: no cover
    BRepCheck_Analyzer = None
    IFSelect_RetDone = 1
    STEPControl_Reader = None


@dataclass
class ValidationResult:
    is_valid: bool
    shape: Any | None = None
    errors: list[dict[str, str]] = field(default_factory=list)


@dataclass
class FileLoadResult:
    is_valid: bool
    shape: Any | None = None
    errors: list[dict[str, str]] = field(default_factory=list)


def validate_file_load(filepath: str) -> FileLoadResult:
    errors: list[dict[str, str]] = []

    if not Path(filepath).is_file():
        errors.append(
            {
                "check": "FileNotFound",
                "severity": "Critical",
                "detail": f"File not found: {filepath}",
                "suggestion": "Check the file path and try again.",
            }
        )
        return FileLoadResult(is_valid=False, shape=None, errors=errors)

    if STEPControl_Reader is None:
        errors.append(
            {
                "check": "MissingDependency",
                "severity": "Critical",
                "detail": "pythonocc-core is not available in the current environment.",
                "suggestion": "Install the project environment before running SimReady.",
            }
        )
        return FileLoadResult(is_valid=False, shape=None, errors=errors)

    reader = STEPControl_Reader()
    status = reader.ReadFile(filepath)
    if status != IFSelect_RetDone:
        errors.append(
            {
                "check": "LoadError",
                "severity": "Critical",
                "detail": f"STEP file read failed (status={status})",
                "suggestion": "Repair or re-export the STEP file.",
            }
        )
        return FileLoadResult(is_valid=False, shape=None, errors=errors)

    reader.TransferRoots()
    shape = reader.OneShape()

    if shape.IsNull():
        errors.append(
            {
                "check": "NullShape",
                "severity": "Critical",
                "detail": "The STEP file produced a null shape.",
                "suggestion": "Re-export the geometry from CAD and try again.",
            }
        )
        return FileLoadResult(is_valid=False, shape=None, errors=errors)

    return FileLoadResult(is_valid=True, shape=shape, errors=errors)


def validate_brep(shape: Any) -> ValidationResult:
    errors: list[dict[str, str]] = []

    if shape is None:
        errors.append(
            {
                "check": "NullShape",
                "severity": "Critical",
                "detail": "No shape was provided for OCC geometry validation.",
                "suggestion": "Check the STEP import flow before analysis.",
            }
        )
        return ValidationResult(is_valid=False, shape=None, errors=errors)

    if BRepCheck_Analyzer is None:
        return ValidationResult(is_valid=True, shape=shape, errors=errors)

    try:
        analyzer = BRepCheck_Analyzer(shape)
        is_valid = analyzer.IsValid()
    except Exception:
        is_valid = False

    if not is_valid:
        errors.append(
            {
                "check": "BRepCheckFailure",
                "severity": "Critical",
                "detail": "Global OCC geometry validation failed.",
                "suggestion": "Repair the geometry before simulation use.",
            }
        )
        return ValidationResult(is_valid=False, shape=shape, errors=errors)

    return ValidationResult(is_valid=True, shape=shape, errors=errors)


def validate_step_file(filepath: str) -> ValidationResult:
    load_result = validate_file_load(filepath)
    if not load_result.is_valid:
        return ValidationResult(is_valid=False, shape=None, errors=load_result.errors)
    return validate_brep(load_result.shape)
