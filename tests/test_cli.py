from click.testing import CliRunner

from simready.cli import cli


def invalid_report():
    return {
        "input_file": "broken.step",
        "status": "InvalidInput",
        "validation": {
            "is_valid": False,
            "errors": [{
                "check": "MissingDependency",
                "severity": "Critical",
                "detail": "pythonocc-core is not available.",
                "suggestion": "Install the geometry dependencies.",
            }],
        },
        "findings": [],
    }


def successful_report():
    return {
        "input_file": "valid.step",
        "status": "SimulationReady",
        "validation": {"is_valid": True, "errors": []},
        "findings": [],
    }


def test_cli_missing_file_reports_terminal_output():
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "/nonexistent/path/missing.step"])
    assert result.exit_code == 1
    assert "SimReady Analysis:" in result.output
    assert "InvalidInput" in result.output
    assert "Clean geometry" not in result.output


def test_cli_missing_file_reports_json_when_requested():
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "/nonexistent/path/missing.step", "--json"])
    assert result.exit_code == 1
    assert '"status": "InvalidInput"' in result.output


def test_cli_invalid_analysis_is_actionable_single_and_nonzero(monkeypatch):
    monkeypatch.setattr("simready.cli.analyze_file_safe", lambda *args, **kwargs: invalid_report())

    result = CliRunner().invoke(cli, ["analyze", "broken.step"])

    assert result.exit_code == 1
    assert result.output.count("SimReady Analysis:") == 1
    assert "MissingDependency" in result.output
    assert "pythonocc-core is not available." in result.output
    assert "Install the geometry dependencies." in result.output
    assert "Clean geometry" not in result.output


def test_cli_successful_analysis_is_single_and_zero(monkeypatch):
    monkeypatch.setattr("simready.cli.analyze_file_safe", lambda *args, **kwargs: successful_report())

    result = CliRunner().invoke(cli, ["analyze", "valid.step"])

    assert result.exit_code == 0
    assert result.output.count("SimReady Analysis:") == 1
    assert "No findings. Clean geometry." in result.output


def test_cli_invalid_analysis_still_writes_requested_artifacts(monkeypatch, tmp_path):
    monkeypatch.setattr("simready.cli.analyze_file_safe", lambda *args, **kwargs: invalid_report())
    monkeypatch.setattr("simready.cli.render_html_report", lambda report, path: open(path, "w", encoding="utf-8").write(report["status"]))
    json_path = tmp_path / "report.json"
    html_path = tmp_path / "report.html"

    result = CliRunner().invoke(cli, [
        "analyze", "broken.step", "--output", str(json_path), "--html", str(html_path),
    ])

    assert result.exit_code == 1
    assert '"status": "InvalidInput"' in json_path.read_text(encoding="utf-8")
    assert "InvalidInput" in html_path.read_text(encoding="utf-8")


def test_cli_export_healed_option(valid_step_file, tmp_path):
    runner = CliRunner()
    output = tmp_path / "out.step"
    result = runner.invoke(cli, ["analyze", valid_step_file, "--export-healed", str(output), "--json"])
    assert result.exit_code == 0
    assert '"heal"' in result.output


def test_cli_html_option_writes_report(valid_step_file, tmp_path):
    runner = CliRunner()
    html_path = tmp_path / "report.html"
    result = runner.invoke(cli, ["analyze", valid_step_file, "--html", str(html_path)])
    assert result.exit_code == 0
    assert html_path.exists()
