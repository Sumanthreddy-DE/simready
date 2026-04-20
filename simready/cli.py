"""CLI entrypoints for SimReady."""

from __future__ import annotations

import json

import click

from simready.pipeline import analyze_file


@click.group()
def cli() -> None:
    """SimReady CLI."""


@cli.command()
@click.argument("input_file", type=click.Path(exists=False))
@click.option("--output", "output_path", type=click.Path(), default=None)
@click.option("--export-healed", "export_healed_path", type=click.Path(), default=None)
def analyze(input_file: str, output_path: str | None, export_healed_path: str | None) -> None:
    """Analyze a STEP file and emit JSON output."""
    report = analyze_file(input_file, export_healed_path=export_healed_path)
    payload = json.dumps(report, indent=2)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    click.echo(payload)


if __name__ == "__main__":
    cli()
