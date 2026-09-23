"""Domain data models for MEDIMG.

Pydantic models for structured representation of DICOM metadata,
dataset statistics, validation results, and processing outcomes.
"""

from __future__ import annotations

import enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Severity(str, enum.Enum):
    """Severity level for validation findings."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class TagAction(str, enum.Enum):
    """Action to apply to a DICOM tag during anonymization."""

    PRESERVE = "PRESERVE"
    REMOVE = "REMOVE"
    REPLACE = "REPLACE"
    PSEUDONYMIZE = "PSEUDONYMIZE"
    REGENERATE_UID = "REGENERATE_UID"


class VerificationStatus(str, enum.Enum):
    """Overall status of a verification check."""

    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


# ---------------------------------------------------------------------------
# DICOM file-level metadata
# ---------------------------------------------------------------------------

class DicomFileMetadata(BaseModel):
    """Metadata extracted from a single DICOM file."""

    file_path: str
    file_size: int = 0

    # Patient
    patient_name: str | None = None
    patient_id: str | None = None
    patient_birth_date: str | None = None
    patient_sex: str | None = None

    # Study
    study_instance_uid: str | None = None
    study_date: str | None = None
    study_time: str | None = None
    study_description: str | None = None
    accession_number: str | None = None

    # Series
    series_instance_uid: str | None = None
    series_description: str | None = None
    modality: str | None = None

    # Instance
    sop_instance_uid: str | None = None
    sop_class_uid: str | None = None

    # Technical
    institution_name: str | None = None
    manufacturer: str | None = None
    rows: int | None = None
    columns: int | None = None
    slice_thickness: float | None = None
    pixel_spacing: list[float] | None = None

    class Config:
        """Allow arbitrary types for flexibility."""
        arbitrary_types_allowed = True


# ---------------------------------------------------------------------------
# Dataset-level aggregation
# ---------------------------------------------------------------------------

class ModalityCount(BaseModel):
    """Count of files per modality."""

    modality: str
    count: int


class DatasetStats(BaseModel):
    """Aggregated statistics for a scanned dataset."""

    dataset_path: str
    total_files: int = 0
    dicom_files: int = 0
    non_dicom_files: int = 0
    invalid_files: int = 0
    total_size_bytes: int = 0

    unique_patients: int = 0
    unique_studies: int = 0
    unique_series: int = 0

    modality_counts: list[ModalityCount] = Field(default_factory=list)

    # Metadata presence indicators (not raw values)
    has_patient_id: bool = False
    has_study_uid: bool = False
    has_series_uid: bool = False
    has_sop_uid: bool = False


# ---------------------------------------------------------------------------
# Validation results
# ---------------------------------------------------------------------------

class ValidationFinding(BaseModel):
    """A single validation finding (issue or note)."""

    severity: Severity
    code: str
    message: str
    file_path: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    """Complete validation result for a dataset."""

    dataset_path: str
    files_scanned: int = 0
    valid_dicom: int = 0
    non_dicom_files: int = 0
    invalid_dicom: int = 0
    duplicates: int = 0

    findings: list[ValidationFinding] = Field(default_factory=list)

    @property
    def errors(self) -> list[ValidationFinding]:
        return [f for f in self.findings if f.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationFinding]:
        return [f for f in self.findings if f.severity == Severity.WARNING]

    @property
    def infos(self) -> list[ValidationFinding]:
        return [f for f in self.findings if f.severity == Severity.INFO]

    @property
    def status(self) -> VerificationStatus:
        if self.errors:
            return VerificationStatus.FAIL
        if self.warnings:
            return VerificationStatus.WARNING
        return VerificationStatus.PASS


# ---------------------------------------------------------------------------
# Integrity manifest
# ---------------------------------------------------------------------------

class FileIntegrityRecord(BaseModel):
    """Integrity record for a single file."""

    path: str
    size: int
    sha256: str


class IntegrityManifest(BaseModel):
    """Integrity manifest for an entire dataset."""

    dataset_path: str
    generated_at: str = ""
    files: list[FileIntegrityRecord] = Field(default_factory=list)


class IntegrityVerification(BaseModel):
    """Result of verifying a dataset against a manifest."""

    manifest_path: str
    dataset_path: str
    total_in_manifest: int = 0
    matched: int = 0
    mismatched: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    extra: list[str] = Field(default_factory=list)

    @property
    def status(self) -> VerificationStatus:
        if self.mismatched or self.missing:
            return VerificationStatus.FAIL
        if self.extra:
            return VerificationStatus.WARNING
        return VerificationStatus.PASS


# ---------------------------------------------------------------------------
# Anonymization
# ---------------------------------------------------------------------------

class AnonymizationVerification(BaseModel):
    """Policy-aware verification results from post-anonymization checks."""

    phi_before: int = 0
    phi_after: int = 0  # Unintended PHI remaining (0 means full pass)
    uid_consistency: VerificationStatus = VerificationStatus.PASS
    path_privacy: VerificationStatus = VerificationStatus.PASS
    status: VerificationStatus = VerificationStatus.PASS

    fields_checked: int = 0
    fields_passed: int = 0
    fields_failed: int = 0
    failures: list[str] = Field(default_factory=list)


class AnonymizationReport(BaseModel):
    """Structured report for a completed anonymization operation."""

    operation: str = "anonymization"
    input_path: str = ""
    output_path: str = ""
    input_files: int = 0
    output_files: int = 0
    fields_removed: int = 0
    fields_replaced: int = 0
    fields_pseudonymized: int = 0
    uids_regenerated: int = 0
    paths_sanitized: int = 0

    verification: AnonymizationVerification | None = None
    source_modified: bool = False


class PhiScanResult(BaseModel):
    """Result of scanning a dataset for PHI/PII."""

    total_files: int = 0
    files_with_phi: int = 0
    total_phi_fields: int = 0
    phi_fields_by_tag: dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

class ConversionResult(BaseModel):
    """Result of a format conversion operation."""

    input_path: str
    output_path: str
    input_format: str = "DICOM"
    output_format: str = ""
    success: bool = False
    message: str = ""
    files_converted: int = 0
