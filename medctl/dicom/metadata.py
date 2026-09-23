"""DICOM metadata extraction and normalisation.

Extracts a standardised set of DICOM tags from a pydicom Dataset and
returns a structured DicomFileMetadata model.  Never exposes raw
sensitive values in logs.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydicom.dataset import Dataset

from medctl.core.models import DicomFileMetadata

logger = logging.getLogger(__name__)

# Tags to extract — maps internal field name → DICOM keyword
_TAG_MAP: dict[str, str] = {
    "patient_name": "PatientName",
    "patient_id": "PatientID",
    "patient_birth_date": "PatientBirthDate",
    "patient_sex": "PatientSex",
    "study_instance_uid": "StudyInstanceUID",
    "study_date": "StudyDate",
    "study_time": "StudyTime",
    "study_description": "StudyDescription",
    "accession_number": "AccessionNumber",
    "series_instance_uid": "SeriesInstanceUID",
    "series_description": "SeriesDescription",
    "modality": "Modality",
    "sop_instance_uid": "SOPInstanceUID",
    "sop_class_uid": "SOPClassUID",
    "institution_name": "InstitutionName",
    "manufacturer": "Manufacturer",
    "rows": "Rows",
    "columns": "Columns",
    "slice_thickness": "SliceThickness",
}


def _safe_str(value: Any) -> str | None:
    """Convert a pydicom value to a plain string, or None."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _safe_int(value: Any) -> int | None:
    """Convert a pydicom value to int, or None."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _safe_float(value: Any) -> float | None:
    """Convert a pydicom value to float, or None."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_float_list(value: Any) -> list[float] | None:
    """Convert a pydicom MultiValue or sequence to list[float], or None."""
    if value is None:
        return None
    try:
        return [float(v) for v in value]
    except (ValueError, TypeError):
        return None


def extract_metadata(
    ds: Dataset,
    file_path: str | Path,
    file_size: int = 0,
) -> DicomFileMetadata:
    """Extract normalised metadata from a pydicom Dataset.

    Parameters
    ----------
    ds : Dataset
        A parsed pydicom Dataset.
    file_path : str | Path
        The file path (stored in the result, not re-read).
    file_size : int
        Pre-computed file size in bytes.

    Returns
    -------
    DicomFileMetadata
        Structured metadata for the file.
    """

    def _get(keyword: str) -> Any:
        """Safely get a DICOM element value by keyword."""
        return getattr(ds, keyword, None)

    pixel_spacing = _safe_float_list(_get("PixelSpacing"))

    meta = DicomFileMetadata(
        file_path=str(file_path),
        file_size=file_size,
        patient_name=_safe_str(_get("PatientName")),
        patient_id=_safe_str(_get("PatientID")),
        patient_birth_date=_safe_str(_get("PatientBirthDate")),
        patient_sex=_safe_str(_get("PatientSex")),
        study_instance_uid=_safe_str(_get("StudyInstanceUID")),
        study_date=_safe_str(_get("StudyDate")),
        study_time=_safe_str(_get("StudyTime")),
        study_description=_safe_str(_get("StudyDescription")),
        accession_number=_safe_str(_get("AccessionNumber")),
        series_instance_uid=_safe_str(_get("SeriesInstanceUID")),
        series_description=_safe_str(_get("SeriesDescription")),
        modality=_safe_str(_get("Modality")),
        sop_instance_uid=_safe_str(_get("SOPInstanceUID")),
        sop_class_uid=_safe_str(_get("SOPClassUID")),
        institution_name=_safe_str(_get("InstitutionName")),
        manufacturer=_safe_str(_get("Manufacturer")),
        rows=_safe_int(_get("Rows")),
        columns=_safe_int(_get("Columns")),
        slice_thickness=_safe_float(_get("SliceThickness")),
        pixel_spacing=pixel_spacing,
    )
    return meta
