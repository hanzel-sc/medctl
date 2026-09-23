"""Dataset-level consistency checks.

Provides additional validation checks that operate on an already-scanned
list of DicomFileMetadata objects:
  - Duplicate file detection (by content hash)
  - Duplicate SOP Instance UID detection
  - Missing required identifiers
  - UID hierarchy validation
  - Modality consistency within series

These checks complement the file-level validation in dicom.validator.
"""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

from medctl.core.models import (
    DicomFileMetadata,
    Severity,
    ValidationFinding,
)
from medctl.validation.integrity import compute_sha256

logger = logging.getLogger(__name__)


def check_duplicate_files(
    metadata_list: list[DicomFileMetadata],
) -> list[ValidationFinding]:
    """Detect duplicate files by computing content hashes.

    Returns findings for files with identical SHA-256 hashes.
    """
    findings: list[ValidationFinding] = []
    hash_to_paths: dict[str, list[str]] = {}

    for meta in metadata_list:
        fpath = Path(meta.file_path)
        if not fpath.exists():
            continue
        try:
            file_hash = compute_sha256(fpath)
            hash_to_paths.setdefault(file_hash, []).append(meta.file_path)
        except (PermissionError, OSError):
            continue

    for file_hash, paths in hash_to_paths.items():
        if len(paths) > 1:
            findings.append(ValidationFinding(
                severity=Severity.WARNING,
                code="DUPLICATE_FILE_CONTENT",
                message=f"Duplicate file content detected ({len(paths)} copies).",
                details={"count": len(paths), "hash_prefix": file_hash[:16]},
            ))

    return findings


def check_duplicate_sop_uids(
    metadata_list: list[DicomFileMetadata],
) -> list[ValidationFinding]:
    """Detect duplicate SOP Instance UIDs across files."""
    findings: list[ValidationFinding] = []
    sop_counter: Counter[str] = Counter()

    for meta in metadata_list:
        if meta.sop_instance_uid:
            sop_counter[meta.sop_instance_uid] += 1

    for uid, count in sop_counter.items():
        if count > 1:
            findings.append(ValidationFinding(
                severity=Severity.WARNING,
                code="DUPLICATE_SOP_UID",
                message=f"Duplicate SOPInstanceUID ({count} occurrences).",
                details={"count": count},
            ))

    return findings


def check_missing_identifiers(
    metadata_list: list[DicomFileMetadata],
) -> list[ValidationFinding]:
    """Check for files missing critical identifiers."""
    findings: list[ValidationFinding] = []
    required = [
        ("patient_id", "PatientID"),
        ("study_instance_uid", "StudyInstanceUID"),
        ("series_instance_uid", "SeriesInstanceUID"),
        ("sop_instance_uid", "SOPInstanceUID"),
    ]

    for meta in metadata_list:
        for field, tag_name in required:
            if not getattr(meta, field, None):
                findings.append(ValidationFinding(
                    severity=Severity.WARNING,
                    code="MISSING_IDENTIFIER",
                    message=f"Missing {tag_name}.",
                    file_path=meta.file_path,
                ))

    return findings


def check_uid_hierarchy(
    metadata_list: list[DicomFileMetadata],
) -> list[ValidationFinding]:
    """Validate that UID hierarchy is consistent.

    - Each series should belong to exactly one study.
    - Each SOP instance should belong to exactly one series.
    """
    findings: list[ValidationFinding] = []

    series_to_studies: dict[str, set[str]] = {}
    sop_to_series: dict[str, set[str]] = {}

    for meta in metadata_list:
        if meta.series_instance_uid and meta.study_instance_uid:
            series_to_studies.setdefault(meta.series_instance_uid, set()).add(
                meta.study_instance_uid
            )
        if meta.sop_instance_uid and meta.series_instance_uid:
            sop_to_series.setdefault(meta.sop_instance_uid, set()).add(
                meta.series_instance_uid
            )

    for series_uid, study_uids in series_to_studies.items():
        if len(study_uids) > 1:
            findings.append(ValidationFinding(
                severity=Severity.ERROR,
                code="SERIES_MULTI_STUDY",
                message="Series belongs to multiple studies.",
            ))

    for sop_uid, series_uids in sop_to_series.items():
        if len(series_uids) > 1:
            findings.append(ValidationFinding(
                severity=Severity.ERROR,
                code="SOP_MULTI_SERIES",
                message="SOP instance belongs to multiple series.",
            ))

    return findings


def check_modality_consistency(
    metadata_list: list[DicomFileMetadata],
) -> list[ValidationFinding]:
    """Check that each series has a consistent modality."""
    findings: list[ValidationFinding] = []
    series_modalities: dict[str, set[str]] = {}

    for meta in metadata_list:
        if meta.series_instance_uid and meta.modality:
            series_modalities.setdefault(meta.series_instance_uid, set()).add(meta.modality)

    for series_uid, modalities in series_modalities.items():
        if len(modalities) > 1:
            findings.append(ValidationFinding(
                severity=Severity.WARNING,
                code="MIXED_MODALITY_SERIES",
                message=f"Series contains mixed modalities: {', '.join(sorted(modalities))}",
            ))

    return findings


def run_all_checks(
    metadata_list: list[DicomFileMetadata],
) -> list[ValidationFinding]:
    """Run all dataset-level consistency checks.

    Returns a combined list of all findings.
    """
    findings: list[ValidationFinding] = []
    findings.extend(check_duplicate_sop_uids(metadata_list))
    findings.extend(check_missing_identifiers(metadata_list))
    findings.extend(check_uid_hierarchy(metadata_list))
    findings.extend(check_modality_consistency(metadata_list))
    return findings
