"""DSL version registry: one place that maps a version to schema, executor and tool."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

DSL_VERSIONS = ("v1", "v2")


def spec_model(version: str) -> type[BaseModel]:
    if version == "v1":
        from simready.gen.spec import PartSpec
        return PartSpec
    if version == "v2":
        from simready.gen.spec_v2 import PartSpecV2
        return PartSpecV2
    raise ValueError(f"unknown DSL version {version!r}")


def known_ops(version: str) -> frozenset[str]:
    if version == "v1":
        return frozenset({"box", "cyl", "fuse", "cut"})
    from simready.gen.spec_v2 import KNOWN_OPS_V2
    spec_model(version)  # raises for an unknown version
    return KNOWN_OPS_V2


def tool_schema(version: str) -> dict:
    if version == "v1":
        from simready.gen.spec import BUILD_PART_TOOL_SCHEMA
        return BUILD_PART_TOOL_SCHEMA
    from simready.gen.spec_v2 import BUILD_PART_TOOL_SCHEMA_V2
    spec_model(version)
    return BUILD_PART_TOOL_SCHEMA_V2


def build(version: str, spec_dict: dict) -> Any:
    spec = spec_model(version).model_validate(spec_dict)
    if version == "v1":
        from simready.gen.build import build_shape
        return build_shape(spec)
    from simready.gen.build_v2 import build_shape_v2
    return build_shape_v2(spec)
