"""CLI command: medimg inspect

Recursively scans a DICOM dataset and produces a summary report
with file counts, patient/study/series counts, modality distribution,
and metadata presence indicators.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import typer

from medctl.core.dataset import scan_dataset
from medctl.core.exceptions import MedctlError
from medctl.reporting.console import print_inspection_report
from medctl.reporting.json_report import write_json_report

logger = logging.getLogger(__name__)


def inspect_command(
    dataset: str = typer.Argument(..., help="Path to the DICOM dataset directory."),
    json_output: Optional[str] = typer.Option(
        None, "--json-output", "-j", help="Write inspection report to a JSON file."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging."),
) -> None:
    """Inspect a DICOM dataset and display a summary report."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    dataset_path = Path(dataset)
    if not dataset_path.exists():
        typer.echo(f"Error: Dataset path does not exist: {dataset}", err=True)
        raise typer.Exit(code=1)
    if not dataset_path.is_dir():
        typer.echo(f"Error: Dataset path is not a directory: {dataset}", err=True)
        raise typer.Exit(code=1)

    try:
        _metadata_list, stats = scan_dataset(dataset_path)
        print_inspection_report(stats)

        if json_output:
            write_json_report(stats, json_output)
            typer.echo(f"JSON report written to: {json_output}")

    except MedctlError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
    except Exception as exc:
        if verbose:
            logger.exception("Unexpected error during inspection")
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
