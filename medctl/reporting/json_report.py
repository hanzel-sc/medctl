"""JSON report serialiser for MEDIMG.

Writes structured reports to JSON files.  Ensures that no raw PHI values
are included in the output — only operation metadata, counts, and
status fields.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from medctl.core.models import (
    AnonymizationReport,
    ConversionResult,
    DatasetStats,
    IntegrityManifest,
    IntegrityVerification,
    ValidationResult,
)

logger = logging.getLogger(__name__)


def write_json_report(
    report: BaseModel,
    output_path: str | Path,
) -> None:
    """Write a Pydantic model to a JSON file.

    Parameters
    ----------
    report : BaseModel
        Any Pydantic report model.
    output_path : str | Path
        Destination file path.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    data = report.model_dump()

    # Strip any raw PHI fields that might have leaked into the model
    _sanitise_dict(data)

    out.write_text(
        json.dumps(data, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("JSON report written to %s", out)


def report_to_dict(report: BaseModel) -> dict[str, Any]:
    """Convert a report model to a sanitised dictionary."""
    data = report.model_dump()
    _sanitise_dict(data)
    return data


def _sanitise_dict(data: dict[str, Any]) -> None:
    """Remove any keys that could contain raw PHI from a report dict.

    This is a safety net — the report models themselves should not
    contain PHI, but this provides defence in depth.
    """
    phi_keys = {
        "patient_name", "patient_id", "patient_birth_date",
        "institution_name", "referring_physician_name",
    }
    keys_to_remove = [k for k in data if k in phi_keys]
    for k in keys_to_remove:
        del data[k]

    # Recurse into nested dicts and lists
    for v in data.values():
        if isinstance(v, dict):
            _sanitise_dict(v)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    _sanitise_dict(item)
