"""CLI command: medimg anonymize

Runs de-identification on a DICOM dataset with configurable rules,
deterministic UID regeneration, and mandatory post-anonymization
verification.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import typer

from medctl.core.config import load_config
from medctl.core.exceptions import MedctlError
from medctl.core.models import VerificationStatus
from medctl.dicom.anonymizer import anonymize_dataset
from medctl.reporting.console import print_anonymization_report
from medctl.reporting.json_report import write_json_report

logger = logging.getLogger(__name__)


def anonymize_command(
    dataset: str = typer.Argument(..., help="Path to the input DICOM dataset directory."),
    output: str = typer.Option(
        ..., "--output", "-o", help="Output directory for anonymized files."
    ),
    config: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to a YAML/JSON configuration file."
    ),
    report: Optional[str] = typer.Option(
        None, "--report", "-r", help="Write anonymization audit report to a JSON file."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging."),
) -> None:
    """Anonymize a DICOM dataset with configurable de-identification rules."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    dataset_path = Path(dataset)
    output_path = Path(output)

    if not dataset_path.exists():
        typer.echo(f"Error: Input dataset path does not exist: {dataset}", err=True)
        raise typer.Exit(code=1)
    if not dataset_path.is_dir():
        typer.echo(f"Error: Input path is not a directory: {dataset}", err=True)
        raise typer.Exit(code=1)

    # Prevent overwriting input
    try:
        if output_path.resolve() == dataset_path.resolve():
            typer.echo("Error: Output path must differ from input path.", err=True)
            raise typer.Exit(code=1)
    except Exception:
        pass

    try:
        cfg = load_config(config)
        result = anonymize_dataset(dataset_path, output_path, cfg)
        print_anonymization_report(result)

        if report:
            write_json_report(result, report)
            typer.echo(f"Audit report written to: {report}")

        # Exit with error if verification failed
        if result.verification and result.verification.status != VerificationStatus.PASS:
            typer.echo(
                "Warning: Post-anonymization verification did not fully pass.",
                err=True,
            )
            raise typer.Exit(code=1)

        if result.source_modified:
            typer.echo("Error: Source dataset appears to have been modified!", err=True)
            raise typer.Exit(code=1)

    except MedctlError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as exc:
        if verbose:
            logger.exception("Unexpected error during anonymization")
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
