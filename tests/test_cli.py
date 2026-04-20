from click.testing import CliRunner

from simready.cli import cli


def test_cli_missing_file_reports_json():
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "/nonexistent/path/missing.step"])
    assert result.exit_code == 0
    assert '"status": "InvalidInput"' in result.output


def test_cli_export_healed_option(valid_step_file, tmp_path):
    runner = CliRunner()
    output = tmp_path / "out.step"
    result = runner.invoke(cli, ["analyze", valid_step_file, "--export-healed", str(output)])
    assert result.exit_code == 0
    assert '"heal"' in result.output
