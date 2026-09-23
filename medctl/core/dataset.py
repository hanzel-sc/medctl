"""Recursive dataset scanner and file indexing.

Provides utilities for discovering and indexing DICOM files within a
directory tree, and for computing dataset-level statistics.
"""

from __future__ import annotations

import logging
from pathlib import Path

from medctl.core.exceptions import FileNotFoundError_
from medctl.core.models import DatasetStats, DicomFileMetadata, ModalityCount
from medctl.dicom.reader import read_dicom_file, is_dicom_file
from medctl.dicom.metadata import extract_metadata

logger = logging.getLogger(__name__)


def scan_dataset(dataset_path: str | Path) -> tuple[list[DicomFileMetadata], DatasetStats]:
    """Recursively scan a directory for DICOM files and compute statistics.

    Parameters
    ----------
    dataset_path : str | Path
        Root directory of the dataset to scan.

    Returns
    -------
    tuple[list[DicomFileMetadata], DatasetStats]
        A tuple of (list of per-file metadata, aggregated dataset statistics).

    Raises
    ------
    FileNotFoundError_
        If the dataset path does not exist.
    """
    root = Path(dataset_path)
    if not root.exists():
        raise FileNotFoundError_(str(root))

    # Collect all files (recursively)
    all_files: list[Path] = sorted(f for f in root.rglob("*") if f.is_file())

    metadata_list: list[DicomFileMetadata] = []
    total_files = len(all_files)
    dicom_count = 0
    non_dicom_count = 0
    invalid_count = 0
    total_size = 0

    patient_ids: set[str] = set()
    study_uids: set[str] = set()
    series_uids: set[str] = set()
    modality_counter: dict[str, int] = {}

    has_patient_id = False
    has_study_uid = False
    has_series_uid = False
    has_sop_uid = False

    for file_path in all_files:
        file_size = file_path.stat().st_size
        total_size += file_size

        if not is_dicom_file(file_path):
            non_dicom_count += 1
            continue

        ds = read_dicom_file(file_path)
        if ds is None:
            invalid_count += 1
            continue

        dicom_count += 1
        meta = extract_metadata(ds, file_path, file_size)
        metadata_list.append(meta)

        # Aggregate
        if meta.patient_id:
            patient_ids.add(meta.patient_id)
            has_patient_id = True
        if meta.study_instance_uid:
            study_uids.add(meta.study_instance_uid)
            has_study_uid = True
        if meta.series_instance_uid:
            series_uids.add(meta.series_instance_uid)
            has_series_uid = True
        if meta.sop_instance_uid:
            has_sop_uid = True
        if meta.modality:
            modality_counter[meta.modality] = modality_counter.get(meta.modality, 0) + 1

    modality_counts = [
        ModalityCount(modality=m, count=c)
        for m, c in sorted(modality_counter.items())
    ]

    stats = DatasetStats(
        dataset_path=str(root),
        total_files=total_files,
        dicom_files=dicom_count,
        non_dicom_files=non_dicom_count,
        invalid_files=invalid_count,
        total_size_bytes=total_size,
        unique_patients=len(patient_ids),
        unique_studies=len(study_uids),
        unique_series=len(series_uids),
        modality_counts=modality_counts,
        has_patient_id=has_patient_id,
        has_study_uid=has_study_uid,
        has_series_uid=has_series_uid,
        has_sop_uid=has_sop_uid,
    )

    return metadata_list, stats
