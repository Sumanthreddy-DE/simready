from simready.splitter import split_bodies
from simready.validator import validate_step_file


def test_split_bodies_single_body(valid_step_file):
    validation = validate_step_file(valid_step_file)
    result = split_bodies(validation.shape)
    assert result.body_count == 1
    assert len(result.bodies) == 1


def test_split_bodies_multi_body_fixture():
    validation = validate_step_file("tests/data/multi_body.step")
    result = split_bodies(validation.shape)
    assert result.body_count == 2
    assert len(result.bodies) == 2
