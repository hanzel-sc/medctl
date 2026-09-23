"""CLI command: medimg convert

Converts DICOM files to PNG for visual inspection.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import typer

from medctl.conversion.converter import SUPPORTED_FORMATS, convert_dicom_to_png
from medctl.core.exceptions import MedctlError
from medctl.reporting.console import print_conversion_report

logger = logging.getLogger(__name__)


def convert_command(
    input_path: str = typer.Argument(..., help="Path to a DICOM file or directory."),
    output: str = typer.Option(
        ..., "--output", "-o", help="Output file or directory path."
    ),
    format: str = typer.Option(
        "png", "--format", "-f", help="Output format (currently: png)."
    ),
    window_center: Optional[float] = typer.Option(
        None, "--window-center", help="Override DICOM Window Center for contrast."
    ),
    window_width: Optional[float] = typer.Option(
        None, "--window-width", help="Override DICOM Window Width for contrast."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging."),
) -> None:
    """Convert DICOM files to PNG for visual inspection.

    Note: Converted images are visual derivatives only and do NOT
    retain medical metadata.
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    fmt = format.lower().strip()
    if fmt not in SUPPORTED_FORMATS:
        typer.echo(
            f"Error: Unsupported format '{fmt}'. Supported: {', '.join(sorted(SUPPORTED_FORMATS))}",
            err=True,
        )
        raise typer.Exit(code=1)

    inp = Path(input_path)
    out = Path(output)

    if not inp.exists():
        typer.echo(f"Error: Input path does not exist: {input_path}", err=True)
        raise typer.Exit(code=1)

    try:
        if out.resolve() == inp.resolve():
            typer.echo("Error: Output path must differ from input path.", err=True)
            raise typer.Exit(code=1)
    except Exception:
        pass

    try:
        result = convert_dicom_to_png(inp, out, window_center, window_width)
        print_conversion_report(result)

        if not result.success:
            raise typer.Exit(code=1)

    except MedctlError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as exc:
        if verbose:
            logger.exception("Unexpected error during conversion")
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
