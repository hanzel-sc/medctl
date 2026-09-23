"""Configuration loading and validation for MEDIMG.

Supports YAML and JSON configuration files with Pydantic validation.
Default configuration is used when no file is provided.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from medctl.core.exceptions import ConfigError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration models
# ---------------------------------------------------------------------------

class AnonymizationConfig(BaseModel):
    """Configuration for anonymization rules."""

    remove: list[str] = Field(default_factory=lambda: [
        "PatientName",
        "PatientBirthDate",
        "PatientBirthTime",
        "PatientAddress",
        "OtherPatientIDs",
        "OtherPatientNames",
        "InstitutionName",
        "InstitutionAddress",
        "ReferringPhysicianName",
        "PerformingPhysicianName",
        "OperatorsName",
    ])

    pseudonymize: list[str] = Field(default_factory=lambda: [
        "PatientID",
    ])

    replace: dict[str, str] = Field(default_factory=lambda: {
        "AccessionNumber": "",
    })

    regenerate_uids: bool = True
    verify_after_anonymization: bool = True


class MedctlConfig(BaseModel):
    """Top-level configuration model for the MEDIMG toolkit."""

    anonymization: AnonymizationConfig = Field(default_factory=AnonymizationConfig)

    # Extension point for future modules
    extra: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_config(config_path: str | Path | None = None) -> MedctlConfig:
    """Load configuration from a YAML or JSON file.

    If *config_path* is ``None``, returns the default configuration.
    """
    if config_path is None:
        logger.debug("No config file specified, using defaults.")
        return MedctlConfig()

    path = Path(config_path)
    if not path.exists():
        raise ConfigError(f"Configuration file not found: {path}")
    if not path.is_file():
        raise ConfigError(f"Configuration path is not a file: {path}")

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Cannot read configuration file: {path} ({exc})") from exc

    suffix = path.suffix.lower()
    try:
        if suffix in (".yaml", ".yml"):
            raw = yaml.safe_load(text)
        elif suffix == ".json":
            raw = json.loads(text)
        else:
            raise ConfigError(
                f"Unsupported configuration format '{suffix}'. Use .yaml, .yml, or .json."
            )
    except (yaml.YAMLError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Failed to parse configuration file: {path} ({exc})") from exc

    if raw is None:
        raw = {}

    if not isinstance(raw, dict):
        raise ConfigError(f"Configuration file must contain a mapping, got {type(raw).__name__}.")

    try:
        return MedctlConfig(**raw)
    except Exception as exc:
        raise ConfigError(f"Invalid configuration: {exc}") from exc
