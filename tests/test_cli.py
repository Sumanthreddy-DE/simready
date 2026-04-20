from click.testing import CliRunner

from simready.cli import cli


def test_cli_missing_file_reports_json():
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "/nonexistent/path/missing.step"])
    assert result.exit_code == 0
    assert '"status": "InvalidInput"' in result.output
