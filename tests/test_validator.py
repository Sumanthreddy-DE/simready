from simready.validator import validate_brep, validate_file_load, validate_step_file


def test_missing_file_returns_critical(missing_step_file):
    result = validate_step_file(missing_step_file)
    assert result.is_valid is False
    assert result.shape is None
    assert result.errors[0]["check"] == "FileNotFound"


def test_invalid_step_without_occ_reports_critical(invalid_step_file):
    result = validate_step_file(invalid_step_file)
    assert result.is_valid is False
    assert result.errors
    assert result.errors[0]["severity"] == "Critical"


def test_valid_step_returns_shape(valid_step_file):
    result = validate_step_file(valid_step_file)
    assert result.is_valid is True
    assert result.shape is not None
    assert result.errors == []


def test_validate_file_load_valid_step_returns_shape(valid_step_file):
    result = validate_file_load(valid_step_file)
    assert result.is_valid is True
    assert result.shape is not None
    assert result.errors == []


def test_validate_brep_rejects_none_shape():
    result = validate_brep(None)
    assert result.is_valid is False
    assert result.errors[0]["check"] == "NullShape"
