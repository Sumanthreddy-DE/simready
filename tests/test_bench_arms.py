"""Arm plumbing: v1 stays byte-identical, v2 is selectable and pinned."""

from __future__ import annotations

from simready.bench.attempt import F9, classify_spec
from simready.bench.prompting import (
    BUILD_PART_TOOL,
    bench_tool,
    build_messages,
    system_prompt_sha256,
)
from simready.gen.dsl import known_ops, spec_model

SP1_HASH = "3dd19661924d5de944e4325eeed84d99ea14cab0483a3b595289d37185224d0c"
FILLET = {"steps": [{"op": "box", "dx": 8, "dy": 6, "dz": 5}, {"op": "fillet", "a": 0, "r": 1, "edges": ">z"}]}


def test_v1_prompt_hash_unchanged():
    assert system_prompt_sha256() == SP1_HASH
    assert system_prompt_sha256("dsl-v1") == SP1_HASH
    assert bench_tool("dsl-v1") == BUILD_PART_TOOL


def test_v2_prompt_differs_and_has_no_agent_sentence():
    assert system_prompt_sha256("dsl-v2") != SP1_HASH
    desc = bench_tool("dsl-v2")["function"]["description"]
    assert "analyze_geometry" not in desc and "polar" in desc


def test_fillet_is_out_of_vocab_in_v1_and_valid_in_v2():
    assert classify_spec(FILLET)[0] == F9
    assert classify_spec(FILLET, dsl="v2") == (None, [])
    assert known_ops("v1") == frozenset({"box", "cyl", "fuse", "cut"})
    spec_model("v2").model_validate(FILLET)


def test_messages_per_arm():
    assert build_messages("x")[0]["content"] == build_messages("x", "dsl-v2")[0]["content"]
    assert bench_tool("build123d") is None
