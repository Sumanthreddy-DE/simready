"""CLI entrypoints for SimReady."""

from __future__ import annotations

import json

import click

from simready.html_report import render_html_report
from simready.pipeline import analyze_file
from simready.report import render_terminal_report


@click.group()
def cli() -> None:
    """SimReady CLI."""


@cli.command()
@click.argument("input_file", type=click.Path(exists=False))
@click.option("--output", "output_path", type=click.Path(), default=None)
@click.option("--export-healed", "export_healed_path", type=click.Path(), default=None)
@click.option("--json", "emit_json", is_flag=True, default=False)
@click.option("--html", "html_path", type=click.Path(), default=None)
@click.option("--verbose", is_flag=True, default=False)
@click.option("--timeout", type=int, default=120, help="Analysis timeout in seconds")
def analyze(input_file: str, output_path: str | None, export_healed_path: str | None, emit_json: bool, html_path: str | None, verbose: bool, timeout: int) -> None:
    """Analyze a STEP file and emit terminal, JSON, or HTML output."""
    report = analyze_file(input_file, export_healed_path=export_healed_path, timeout=timeout)
    payload = json.dumps(report, indent=2)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    if html_path:
        render_html_report(report, html_path)
    if emit_json:
        click.echo(payload)
    else:
        click.echo(render_terminal_report(report, verbose=verbose))


if __name__ == "__main__":
    cli()
