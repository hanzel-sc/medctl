"""CLI command: medimg validate

Runs structural and dataset-level validation, optionally generates
or verifies a SHA-256 integrity manifest.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import typer

from medctl.core.exceptions import MedctlError
from medctl.core.models import VerificationStatus
from medctl.dicom.validator import validate_dataset
from medctl.reporting.console import print_integrity_report, print_validation_report
from medctl.reporting.json_report import write_json_report
from medctl.validation.integrity import generate_manifest, verify_manifest

logger = logging.getLogger(__name__)


def validate_command(
    dataset: str = typer.Argument(..., help="Path to the DICOM dataset directory."),
    integrity_manifest: Optional[str] = typer.Option(
        None, "--integrity-manifest", "-m", help="Generate a SHA-256 integrity manifest at this path."
    ),
    verify_manifest_path: Optional[str] = typer.Option(
        None, "--verify-manifest", help="Verify the dataset against an existing manifest."
    ),
    json_output: Optional[str] = typer.Option(
        None, "--json-output", "-j", help="Write validation report to a JSON file."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging."),
) -> None:
    """Validate a DICOM dataset for structural correctness and integrity."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    dataset_path = Path(dataset)
    if not dataset_path.exists():
        typer.echo(f"Error: Dataset path does not exist: {dataset}", err=True)
        raise typer.Exit(code=1)
    if not dataset_path.is_dir():
        typer.echo(f"Error: Dataset path is not a directory: {dataset}", err=True)
        raise typer.Exit(code=1)

    exit_code = 0

    try:
        # Structural validation
        result = validate_dataset(dataset_path)
        print_validation_report(result)

        if result.status == VerificationStatus.FAIL:
            exit_code = 1

        if json_output:
            write_json_report(result, json_output)
            typer.echo(f"JSON report written to: {json_output}")

        # Generate integrity manifest
        if integrity_manifest:
            typer.echo(f"\nGenerating integrity manifest...")
            manifest = generate_manifest(dataset_path, integrity_manifest)
            typer.echo(
                f"Manifest written to: {integrity_manifest} ({len(manifest.files)} files)"
            )

        # Verify existing manifest
        if verify_manifest_path:
            typer.echo(f"\nVerifying dataset against manifest...")
            verification = verify_manifest(verify_manifest_path, dataset_path)
            print_integrity_report(verification)

            if verification.status == VerificationStatus.FAIL:
                exit_code = 1

    except MedctlError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
    except Exception as exc:
        if verbose:
            logger.exception("Unexpected error during validation")
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    if exit_code != 0:
        raise typer.Exit(code=exit_code)
