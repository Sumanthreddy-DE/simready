"""Benchmark concept file: schema, loader and hash. No OCC, no network.

One JSONL line per concept. Each concept has three phrasings (explicit /
engineer / intent), a check list per phrasing, the standards the ranges
come from, and, for in-vocab concepts, a hand-built ``reference_spec``
that must pass all of its own checks (tests/test_bench_reference_specs.py).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

PHRASINGS = ("explicit", "engineer", "intent")

BENCH_DIR = Path(__file__).resolve().parent
CONCEPTS_V1 = BENCH_DIR / "prompts" / "concepts_v1.jsonl"
CONCEPTS_V1_FROZEN = BENCH_DIR / "prompts" / "concepts_v1.sha256"

Bound = Optional[float]
Range = tuple[Bound, Bound]  # inclusive; None = open-ended


def in_range(value: float, rng: Range) -> bool:
    lo, hi = rng
    return (lo is None or value >= lo) and (hi is None or value <= hi)


class _Check(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BBoxSorted(_Check):
    """Bounding-box extents, compared smallest-to-largest (placement-invariant)."""

    type: Literal["bbox_sorted"]
    ranges: tuple[Range, Range, Range]


class BBoxMinDim(_Check):
    """Smallest bounding-box extent is at least ``min`` (e.g. plate thickness)."""

    type: Literal["bbox_min_dim"]
    min: float


class VolumeCheck(_Check):
    type: Literal["volume"]
    range: Range  # mm^3


class HoleSet(_Check):
    """Full concave cylinders with diameter in range (and through/depth if given).

    ``count`` is how many such holes must exist. ``pattern`` = the sorted
    pairwise axis distances between them, as ranges; needs an exact count.
    """

    type: Literal["hole_set"]
    diameter: Range
    count: Range
    through: Optional[bool] = None
    depth_min: Optional[float] = None
    pattern: Optional[list[Range]] = None

    @model_validator(mode="after")
    def _pattern_shape(self) -> "HoleSet":
        if self.pattern is None:
            return self
        lo, hi = self.count
        if lo is None or lo != hi:
            raise ValueError("pattern requires an exact count [n, n]")
        n = int(lo)
        pairs = n * (n - 1) // 2
        if len(self.pattern) != pairs:
            raise ValueError(f"pattern for {n} holes needs {pairs} distances, got {len(self.pattern)}")
        return self


class Bore(_Check):
    """At least one full concave cylinder with diameter in range (and depth/through if given)."""

    type: Literal["bore"]
    diameter: Range
    depth_min: Optional[float] = None
    through: Optional[bool] = None


class Boss(_Check):
    """Full convex cylinders (boss, shaft, tube OD) with diameter in range."""

    type: Literal["boss"]
    diameter: Range
    height_min: Optional[float] = None
    count: Range = (1, None)


class AnyOf(_Check):
    """Passes if any sub-check passes (intent phrasings with several valid answers)."""

    type: Literal["any_of"]
    checks: list["Check"] = Field(min_length=2)


class NotChecked(_Check):
    """A genuinely free design choice, logged as not_checked, never silently passed."""

    type: Literal["not_checked"]
    what: str


Check = Annotated[
    Union[BBoxSorted, BBoxMinDim, VolumeCheck, HoleSet, Bore, Boss, AnyOf, NotChecked],
    Field(discriminator="type"),
]
AnyOf.model_rebuild()
CHECK_LIST: TypeAdapter[list[Check]] = TypeAdapter(list[Check])


class Prompts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explicit: str = Field(min_length=10)
    engineer: str = Field(min_length=10)
    intent: str = Field(min_length=10)


class PhrasingChecks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explicit: list[Check] = Field(min_length=1)
    engineer: list[Check] = Field(min_length=1)
    intent: list[Check] = Field(min_length=1)


class Concept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_id: str = Field(pattern=r"^c\d{3}$")
    name: str
    in_vocab: bool
    solids: int = Field(default=1, ge=1)
    prompts: Prompts
    checks: PhrasingChecks
    sources: list[str] = Field(default_factory=list)
    reference_spec: Optional[dict] = None

    @model_validator(mode="after")
    def _reference_iff_in_vocab(self) -> "Concept":
        if self.in_vocab and self.reference_spec is None:
            raise ValueError(f"{self.concept_id}: in-vocab concept needs reference_spec")
        if not self.in_vocab and self.reference_spec is not None:
            raise ValueError(f"{self.concept_id}: out-of-vocab concept must not carry reference_spec")
        return self


def load_concepts(path: str | Path = CONCEPTS_V1) -> list[Concept]:
    concepts: list[Concept] = []
    seen: set[str] = set()
    for lineno, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        concept = Concept.model_validate_json(line)
        if concept.concept_id in seen:
            raise ValueError(f"line {lineno}: duplicate concept_id {concept.concept_id}")
        seen.add(concept.concept_id)
        concepts.append(concept)
    return concepts


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen_sha256(path: str | Path = CONCEPTS_V1_FROZEN) -> str | None:
    p = Path(path)
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8").strip() or None
