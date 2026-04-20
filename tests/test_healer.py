from pathlib import Path

from simready.healer import export_healed_shape, heal_shape
from simready.validator import validate_step_file


def test_heal_shape_returns_summary(valid_step_file):
    validation = validate_step_file(valid_step_file)
    result = heal_shape(validation.shape)
    assert result.healed_shape is not None
    assert result.summary["attempted"] in {True, False}
    assert "notes" in result.summary


def test_export_healed_shape(valid_step_file, tmp_path):
    validation = validate_step_file(valid_step_file)
    output = tmp_path / "healed.step"
    exported = export_healed_shape(validation.shape, str(output))
    if exported is not None:
        assert Path(exported).exists()
