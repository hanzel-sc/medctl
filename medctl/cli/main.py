"""Unified CLI entry point for MEDCTL.

Registers all subcommands and provides --version and --help.
"""

from __future__ import annotations

import typer

from medctl import __version__
from medctl.cli.anonymize import anonymize_command
from medctl.cli.convert import convert_command
from medctl.cli.inspect import inspect_command
from medctl.cli.validate import validate_command

app = typer.Typer(
    name="medctl",
    help="MEDCTL — Medical Imaging Dataset Control.\n\n"
    "A production-quality CLI for DICOM dataset engineering and secure processing.",
    add_completion=False,
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"medctl {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show the version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """MEDCTL — Medical Imaging Dataset Control."""


app.command("inspect", help="Inspect a DICOM dataset and display a summary report.")(
    inspect_command
)
app.command("validate", help="Validate a DICOM dataset for structural correctness.")(
    validate_command
)
app.command("anonymize", help="Anonymize a DICOM dataset with configurable rules.")(
    anonymize_command
)
app.command("convert", help="Convert DICOM files to PNG for visual inspection.")(
    convert_command
)


if __name__ == "__main__":
    app()
