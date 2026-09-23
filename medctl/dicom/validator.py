"""DICOM structural validation at file and dataset level.

File-level: readable, valid DICOM, parseable metadata, valid structure.
Dataset-level: duplicates, missing/invalid identifiers, UID consistency,
modality consistency.

This is software/structural validation only — no clinical claims.
"""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

from medctl.core.exceptions import FileNotFoundError_
from medctl.core.models import (
    DicomFileMetadata,
    Severity,
    ValidationFinding,
    ValidationResult,
)
from medctl.dicom.reader import is_dicom_file, read_dicom_file
from medctl.dicom.metadata import extract_metadata

logger = logging.getLogger(__name__)

# Required tags — every valid DICOM image should have these
_REQUIRED_TAGS = [
    ("patient_id", "PatientID"),
    ("study_instance_uid", "StudyInstanceUID"),
    ("series_instance_uid", "SeriesInstanceUID"),
    ("sop_instance_uid", "SOPInstanceUID"),
    ("modality", "Modality"),
]


def validate_dataset(dataset_path: str | Path) -> ValidationResult:
    """Run full file-level and dataset-level validation on a directory.

    Parameters
    ----------
    dataset_path : str | Path
        Root directory of the dataset.

    Returns
    -------
    ValidationResult
        Structured validation findings.
    """
    root = Path(dataset_path)
    if not root.exists():
        raise FileNotFoundError_(str(root))

    result = ValidationResult(dataset_path=str(root))
    findings: list[ValidationFinding] = []
    metadata_list: list[DicomFileMetadata] = []

    all_files = sorted(f for f in root.rglob("*") if f.is_file())
    result.files_scanned = len(all_files)

    sop_uid_counter: Counter[str] = Counter()

    for file_path in all_files:
        # File-level: existence and readability
        if not file_path.is_file():
            findings.append(ValidationFinding(
                severity=Severity.ERROR,
                code="FILE_NOT_FOUND",
                message="File does not exist.",
                file_path=str(file_path),
            ))
            continue

        try:
            _ = file_path.stat()
        except PermissionError:
            findings.append(ValidationFinding(
                severity=Severity.ERROR,
                code="FILE_PERMISSION",
                message="Cannot read file (permission denied).",
                file_path=str(file_path),
            ))
            result.invalid_dicom += 1
            continue

        # File-level: is it DICOM?
        if not is_dicom_file(file_path):
            result.non_dicom_files += 1
            findings.append(ValidationFinding(
                severity=Severity.INFO,
                code="NON_DICOM",
                message="File is not DICOM.",
                file_path=str(file_path),
            ))
            continue

        # File-level: parseable?
        ds = read_dicom_file(file_path)
        if ds is None:
            findings.append(ValidationFinding(
                severity=Severity.ERROR,
                code="DICOM_PARSE_ERROR",
                message="DICOM file could not be parsed.",
                file_path=str(file_path),
            ))
            result.invalid_dicom += 1
            continue

        result.valid_dicom += 1
        meta = extract_metadata(ds, file_path, file_path.stat().st_size)
        metadata_list.append(meta)

        # File-level: required tags
        for field, tag_name in _REQUIRED_TAGS:
            value = getattr(meta, field, None)
            if not value:
                findings.append(ValidationFinding(
                    severity=Severity.WARNING,
                    code="MISSING_TAG",
                    message=f"Missing required tag: {tag_name}",
                    file_path=str(file_path),
                ))

        # Track SOP UIDs for duplicate detection
        if meta.sop_instance_uid:
            sop_uid_counter[meta.sop_instance_uid] += 1

    # Dataset-level: duplicate SOP Instance UIDs
    for uid, count in sop_uid_counter.items():
        if count > 1:
            result.duplicates += 1
            findings.append(ValidationFinding(
                severity=Severity.WARNING,
                code="DUPLICATE_SOP_UID",
                message=f"Duplicate SOPInstanceUID found ({count} occurrences).",
                details={"count": count},
            ))

    # Dataset-level: UID hierarchy consistency
    _check_uid_hierarchy(metadata_list, findings)

    # Dataset-level: modality consistency
    _check_modality_consistency(metadata_list, findings)

    result.findings = findings
    return result


def _check_uid_hierarchy(
    metadata_list: list[DicomFileMetadata],
    findings: list[ValidationFinding],
) -> None:
    """Check that series UIDs are consistent within studies."""
    # Map: series_uid → set of study_uids
    series_to_studies: dict[str, set[str]] = {}
    for meta in metadata_list:
        if meta.series_instance_uid and meta.study_instance_uid:
            series_to_studies.setdefault(meta.series_instance_uid, set()).add(
                meta.study_instance_uid
            )

    for series_uid, study_uids in series_to_studies.items():
        if len(study_uids) > 1:
            findings.append(ValidationFinding(
                severity=Severity.ERROR,
                code="UID_HIERARCHY_MISMATCH",
                message="Series belongs to multiple studies.",
                details={"series_uid_suffix": series_uid[-8:]},
            ))


def _check_modality_consistency(
    metadata_list: list[DicomFileMetadata],
    findings: list[ValidationFinding],
) -> None:
    """Check for modality consistency within each series."""
    # Map: series_uid → set of modalities
    series_modalities: dict[str, set[str]] = {}
    for meta in metadata_list:
        if meta.series_instance_uid and meta.modality:
            series_modalities.setdefault(meta.series_instance_uid, set()).add(meta.modality)

    for series_uid, modalities in series_modalities.items():
        if len(modalities) > 1:
            findings.append(ValidationFinding(
                severity=Severity.WARNING,
                code="MODALITY_INCONSISTENCY",
                message=f"Series contains mixed modalities: {', '.join(sorted(modalities))}",
                details={"series_uid_suffix": series_uid[-8:]},
            ))
