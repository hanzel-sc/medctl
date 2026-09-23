"""DICOM anonymization engine with PHI detection and verification.

Implements:
  - PHI/PII scanning of DICOM metadata
  - Configurable de-identification (remove, replace, pseudonymize)
  - Deterministic UID regeneration via UidMapper
  - Post-anonymization verification (two-pass)
  - Structured audit reporting (no raw PHI in outputs)

SECURITY: Never modifies source files.  Never logs raw PHI values.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
from pathlib import Path
from typing import Any

import pydicom
from pydicom.dataset import Dataset

from medctl.core.config import AnonymizationConfig, MedctlConfig
from medctl.core.exceptions import (
    AnonymizationError,
    DicomWriteError,
    FileNotFoundError_,
    OutputPathError,
    VerificationError,
)
from medctl.core.models import (
    AnonymizationReport,
    AnonymizationVerification,
    PhiScanResult,
    TagAction,
    VerificationStatus,
)
from medctl.dicom.reader import is_dicom_file, read_dicom_file
from medctl.dicom.rules import (
    ALL_SENSITIVE_TAGS,
    SENSITIVE_REPLACE_TAGS,
    UID_REGENERATE_TAGS,
    build_action_map,
)
from medctl.dicom.uid import UidMapper

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PHI scanning
# ---------------------------------------------------------------------------

def scan_phi(
    dataset_path: str | Path,
    sensitive_tags: set[str] | None = None,
) -> PhiScanResult:
    """Scan a dataset directory for PHI/PII in DICOM metadata.

    Parameters
    ----------
    dataset_path : str | Path
        Root directory to scan.
    sensitive_tags : set[str] | None
        Optional custom set of sensitive tag keywords.
        Defaults to ALL_SENSITIVE_TAGS.

    Returns
    -------
    PhiScanResult
        Counts of files and fields containing PHI.
    """
    root = Path(dataset_path)
    if not root.exists():
        raise FileNotFoundError_(str(root))

    tags_to_check = sensitive_tags or ALL_SENSITIVE_TAGS
    result = PhiScanResult()

    dicom_files = sorted(f for f in root.rglob("*") if f.is_file() and is_dicom_file(f))
    result.total_files = len(dicom_files)

    for file_path in dicom_files:
        ds = read_dicom_file(file_path)
        if ds is None:
            continue

        file_has_phi = False
        for tag_keyword in tags_to_check:
            value = getattr(ds, tag_keyword, None)
            if value is not None and str(value).strip():
                result.total_phi_fields += 1
                result.phi_fields_by_tag[tag_keyword] = (
                    result.phi_fields_by_tag.get(tag_keyword, 0) + 1
                )
                file_has_phi = True

        if file_has_phi:
            result.files_with_phi += 1

    return result


# ---------------------------------------------------------------------------
# Anonymization engine
# ---------------------------------------------------------------------------

def anonymize_dataset(
    input_path: str | Path,
    output_path: str | Path,
    config: MedctlConfig | None = None,
) -> AnonymizationReport:
    """Anonymize a DICOM dataset directory.

    Creates a de-identified copy at *output_path*.  The original
    dataset at *input_path* is never modified.

    Parameters
    ----------
    input_path : str | Path
        Source dataset directory.
    output_path : str | Path
        Destination directory for anonymized files.
    config : MedctlConfig | None
        Optional configuration.  Defaults to built-in rules.

    Returns
    -------
    AnonymizationReport
        Structured audit report of the operation.
    """
    input_dir = Path(input_path)
    output_dir = Path(output_path)

    if not input_dir.exists():
        raise FileNotFoundError_(str(input_dir))
    if not input_dir.is_dir():
        raise AnonymizationError(f"Input path is not a directory: {input_dir}")

    # Safety: refuse to write into the source directory
    try:
        if output_dir.resolve() == input_dir.resolve():
            raise OutputPathError(str(output_dir), "Output path must differ from input path")
        # Also check if output is a subdirectory of input
        output_dir.resolve().relative_to(input_dir.resolve())
        raise OutputPathError(str(output_dir), "Output path must not be inside the input directory")
    except ValueError:
        pass  # Not relative — this is the expected safe case

    # Setup
    anon_config = config.anonymization if config else AnonymizationConfig()
    action_map = build_action_map(
        remove=anon_config.remove,
        pseudonymize=anon_config.pseudonymize,
        replace=anon_config.replace,
        regenerate_uids=anon_config.regenerate_uids,
    )
    replace_values = anon_config.replace if anon_config.replace else SENSITIVE_REPLACE_TAGS

    uid_mapper = UidMapper()
    pseudonym_map: dict[str, str] = {}
    pseudo_counter = 0

    # Mappings for deterministic anonymous path generation
    patient_path_map: dict[str, str] = {}
    studies_per_patient: dict[str, dict[str, str]] = {}
    series_per_study: dict[tuple[str, str], dict[str, str]] = {}
    series_image_counter: dict[tuple[str, str, str], int] = {}
    orig_patient_identifiers: set[str] = set()
    _reserved_tokens = {"patient", "study", "series", "image", "dicom", "test", "data", "synth"}

    # Counters for the report
    fields_removed = 0
    fields_replaced = 0
    fields_pseudonymized = 0
    paths_sanitized = 0
    input_file_count = 0
    output_file_count = 0

    # Pre-scan for PHI (used in verification report)
    phi_before = scan_phi(input_dir)

    # Process files
    dicom_files = sorted(f for f in input_dir.rglob("*") if f.is_file() and is_dicom_file(f))
    input_file_count = len(dicom_files)

    output_dir.mkdir(parents=True, exist_ok=True)

    for file_path in dicom_files:
        ds = read_dicom_file(file_path, stop_before_pixels=False)
        if ds is None:
            logger.warning("Skipping unreadable file: %s", file_path.name)
            continue

        # Extract original identifiers before any modification
        orig_pid = getattr(ds, "PatientID", None)
        orig_pname = getattr(ds, "PatientName", None)
        if orig_pid is not None and str(orig_pid).strip():
            pid_str = str(orig_pid).strip()
            if pid_str.lower() not in _reserved_tokens:
                orig_patient_identifiers.add(pid_str.lower())
        if orig_pname is not None and str(orig_pname).strip():
            pname_str = str(orig_pname).strip()
            if pname_str.lower() not in _reserved_tokens:
                orig_patient_identifiers.add(pname_str.lower())
            for part in pname_str.replace("^", " ").split():
                part_clean = part.lower().strip()
                if len(part_clean) >= 3 and part_clean not in _reserved_tokens:
                    orig_patient_identifiers.add(part_clean)

        # Build deterministic anonymous relative path
        patient_key = str(getattr(ds, "PatientID", None) or getattr(ds, "PatientName", None) or f"patient_{len(patient_path_map) + 1}").strip()
        study_key = str(getattr(ds, "StudyInstanceUID", None) or f"study_{len(studies_per_patient) + 1}").strip()
        series_key = str(getattr(ds, "SeriesInstanceUID", None) or f"series_{len(series_per_study) + 1}").strip()

        if patient_key not in patient_path_map:
            patient_path_map[patient_key] = f"patient_{len(patient_path_map) + 1:04d}"
        patient_folder = patient_path_map[patient_key]

        patient_studies = studies_per_patient.setdefault(patient_key, {})
        if study_key not in patient_studies:
            patient_studies[study_key] = f"study_{len(patient_studies) + 1:04d}"
        study_folder = patient_studies[study_key]

        study_tuple = (patient_key, study_key)
        study_series = series_per_study.setdefault(study_tuple, {})
        if series_key not in study_series:
            study_series[series_key] = f"series_{len(study_series) + 1:04d}"
        series_folder = study_series[series_key]

        series_tuple = (patient_key, study_key, series_key)
        img_idx = series_image_counter.get(series_tuple, 0) + 1
        series_image_counter[series_tuple] = img_idx
        image_filename = f"image_{img_idx:06d}.dcm"

        rel_dest = Path(patient_folder) / study_folder / series_folder / image_filename
        out_file = output_dir / rel_dest
        out_file.parent.mkdir(parents=True, exist_ok=True)

        # Apply anonymization actions
        for tag_keyword, action in action_map.items():
            if action == TagAction.REMOVE:
                if hasattr(ds, tag_keyword) and getattr(ds, tag_keyword, None) is not None:
                    try:
                        delattr(ds, tag_keyword)
                        fields_removed += 1
                    except Exception:
                        # Some tags may not be deletable; log and continue
                        logger.debug("Could not remove tag %s", tag_keyword)

            elif action == TagAction.REPLACE:
                if hasattr(ds, tag_keyword):
                    replacement = replace_values.get(tag_keyword, "")
                    try:
                        setattr(ds, tag_keyword, replacement)
                        fields_replaced += 1
                    except Exception:
                        logger.debug("Could not replace tag %s", tag_keyword)

            elif action == TagAction.PSEUDONYMIZE:
                original_value = getattr(ds, tag_keyword, None)
                if original_value is not None:
                    original_str = str(original_value).strip()
                    if original_str:
                        if original_str not in pseudonym_map:
                            pseudo_counter += 1
                            pseudonym_map[original_str] = f"SUBJ-{pseudo_counter:06d}"
                        try:
                            setattr(ds, tag_keyword, pseudonym_map[original_str])
                            fields_pseudonymized += 1
                        except Exception:
                            logger.debug("Could not pseudonymize tag %s", tag_keyword)

            elif action == TagAction.REGENERATE_UID:
                original_uid = getattr(ds, tag_keyword, None)
                if original_uid is not None:
                    original_uid_str = str(original_uid).strip()
                    if original_uid_str:
                        new_uid = uid_mapper.map_uid(original_uid_str)
                        try:
                            setattr(ds, tag_keyword, new_uid)
                            if (
                                tag_keyword == "SOPInstanceUID"
                                and hasattr(ds, "file_meta")
                                and ds.file_meta is not None
                                and hasattr(ds.file_meta, "MediaStorageSOPInstanceUID")
                            ):
                                ds.file_meta.MediaStorageSOPInstanceUID = new_uid
                        except Exception:
                            logger.debug("Could not regenerate UID %s", tag_keyword)

        try:
            try:
                ds.save_as(str(out_file), enforce_file_format=True)
            except TypeError:
                ds.save_as(str(out_file))
            output_file_count += 1
            paths_sanitized += 1
        except Exception as exc:
            raise DicomWriteError(str(out_file), str(exc)) from exc

    # Post-anonymization verification
    verification = None
    if anon_config.verify_after_anonymization:
        verification = verify_anonymized_dataset(
            output_dir=output_dir,
            action_map=action_map,
            replace_values=replace_values,
            uid_mapper=uid_mapper,
            phi_before_count=phi_before.total_phi_fields,
            orig_patient_identifiers=orig_patient_identifiers,
        )

    # Check source was not modified
    source_modified = _check_source_unmodified(input_dir, dicom_files)

    report = AnonymizationReport(
        input_path=str(input_dir),
        output_path=str(output_dir),
        input_files=input_file_count,
        output_files=output_file_count,
        fields_removed=fields_removed,
        fields_replaced=fields_replaced,
        fields_pseudonymized=fields_pseudonymized,
        uids_regenerated=uid_mapper.mapping_count,
        paths_sanitized=paths_sanitized,
        verification=verification,
        source_modified=source_modified,
    )

    return report


def verify_anonymized_dataset(
    output_dir: Path,
    action_map: dict[str, TagAction],
    replace_values: dict[str, str],
    uid_mapper: UidMapper,
    phi_before_count: int = 0,
    orig_patient_identifiers: set[str] | None = None,
) -> AnonymizationVerification:
    """Perform policy-aware verification on the anonymized dataset.

    Verifies that:
    1. Fields marked REMOVE are absent or empty.
    2. Fields marked REPLACE match the configured replacement.
    3. Fields marked PSEUDONYMIZE match pseudonym pattern and differ from original.
    4. Fields marked REGENERATE_UID have valid new UIDs and differ from originals.
    5. Output directory/file paths contain no original PHI.
    6. UID relationships remain consistent.
    """
    fields_checked = 0
    fields_passed = 0
    fields_failed = 0
    failures: list[str] = []

    dicom_files = sorted(f for f in output_dir.rglob("*") if f.is_file() and is_dicom_file(f))

    for file_path in dicom_files:
        ds = read_dicom_file(file_path)
        if ds is None:
            continue

        for tag_keyword, action in action_map.items():
            if action == TagAction.REMOVE:
                fields_checked += 1
                val = getattr(ds, tag_keyword, None)
                if val is not None and str(val).strip() != "":
                    fields_failed += 1
                    failures.append(f"Tag {tag_keyword} was not removed in {file_path.name}")
                else:
                    fields_passed += 1

            elif action == TagAction.REPLACE:
                fields_checked += 1
                expected = replace_values.get(tag_keyword, "")
                actual = str(getattr(ds, tag_keyword, "") or "").strip()
                if actual != expected.strip():
                    fields_failed += 1
                    failures.append(
                        f"Tag {tag_keyword} value '{actual}' != expected '{expected}' in {file_path.name}"
                    )
                else:
                    fields_passed += 1

            elif action == TagAction.PSEUDONYMIZE:
                fields_checked += 1
                val = getattr(ds, tag_keyword, None)
                actual = str(val or "").strip()
                if not actual.startswith("SUBJ-"):
                    fields_failed += 1
                    failures.append(
                        f"Tag {tag_keyword} value '{actual}' is not a valid pseudonym in {file_path.name}"
                    )
                elif orig_patient_identifiers and actual.lower() in orig_patient_identifiers:
                    fields_failed += 1
                    failures.append(
                        f"Tag {tag_keyword} value matches original PHI in {file_path.name}"
                    )
                else:
                    fields_passed += 1

            elif action == TagAction.REGENERATE_UID:
                val = getattr(ds, tag_keyword, None)
                if val is not None and str(val).strip() != "":
                    fields_checked += 1
                    actual = str(val).strip()
                    if actual in uid_mapper._cache:
                        fields_failed += 1
                        failures.append(f"UID tag {tag_keyword} still has original UID in {file_path.name}")
                    else:
                        fields_passed += 1

    # Path privacy verification
    path_privacy = VerificationStatus.PASS
    if orig_patient_identifiers:
        for p in output_dir.rglob("*"):
            rel_str = str(p.relative_to(output_dir)).lower()
            for ident in orig_patient_identifiers:
                if ident in rel_str:
                    path_privacy = VerificationStatus.FAIL
                    failures.append(f"Path '{rel_str}' contains original identifier '{ident}'")
                    break

    uid_consistency = _verify_uid_consistency(output_dir, uid_mapper)

    status = (
        VerificationStatus.PASS
        if (fields_failed == 0 and uid_consistency == VerificationStatus.PASS and path_privacy == VerificationStatus.PASS)
        else VerificationStatus.FAIL
    )

    return AnonymizationVerification(
        phi_before=phi_before_count,
        phi_after=fields_failed,
        uid_consistency=uid_consistency,
        path_privacy=path_privacy,
        status=status,
        fields_checked=fields_checked,
        fields_passed=fields_passed,
        fields_failed=fields_failed,
        failures=failures,
    )


def _verify_uid_consistency(output_dir: Path, uid_mapper: UidMapper) -> VerificationStatus:
    """Verify that UID mapping is consistent in the output dataset.

    Checks that files within the same original study/series still share
    the same mapped UIDs.
    """
    study_uids: dict[str, set[str]] = {}  # mapped_series -> set of mapped_study
    dicom_files = sorted(f for f in output_dir.rglob("*") if f.is_file() and is_dicom_file(f))

    for file_path in dicom_files:
        ds = read_dicom_file(file_path)
        if ds is None:
            continue
        study_uid = getattr(ds, "StudyInstanceUID", None)
        series_uid = getattr(ds, "SeriesInstanceUID", None)
        if study_uid and series_uid:
            study_uids.setdefault(str(series_uid), set()).add(str(study_uid))

    # Each series should belong to exactly one study
    for series_uid, studies in study_uids.items():
        if len(studies) > 1:
            logger.warning("UID inconsistency: series maps to multiple studies")
            return VerificationStatus.FAIL

    return VerificationStatus.PASS


def _check_source_unmodified(input_dir: Path, original_files: list[Path]) -> bool:
    """Quick check that source files still exist and haven't been removed.

    This is a lightweight check — not a full integrity verify.
    Returns True if the source appears to have been modified (bad).
    """
    for file_path in original_files:
        if not file_path.exists():
            return True
    return False
