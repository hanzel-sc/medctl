"""Cryptographic integrity checking for datasets.

Provides SHA-256 hash calculation, integrity manifest generation,
and manifest verification against the current state of a dataset.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from medctl.core.exceptions import FileNotFoundError_, IntegrityError
from medctl.core.models import (
    FileIntegrityRecord,
    IntegrityManifest,
    IntegrityVerification,
    VerificationStatus,
)
from medctl.dicom.reader import is_dicom_file

logger = logging.getLogger(__name__)

# Buffer size for streaming hash calculation (64 KiB)
_HASH_BUFFER_SIZE = 65536


def compute_sha256(file_path: str | Path) -> str:
    """Compute the SHA-256 hash of a file using streaming reads.

    Parameters
    ----------
    file_path : str | Path
        Path to the file.

    Returns
    -------
    str
        Hexadecimal SHA-256 digest.
    """
    sha = hashlib.sha256()
    with open(file_path, "rb") as fh:
        while True:
            chunk = fh.read(_HASH_BUFFER_SIZE)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()


def generate_manifest(
    dataset_path: str | Path,
    output_path: str | Path | None = None,
    dicom_only: bool = False,
) -> IntegrityManifest:
    """Generate a SHA-256 integrity manifest for all files in a dataset.

    Parameters
    ----------
    dataset_path : str | Path
        Root directory of the dataset.
    output_path : str | Path | None
        If provided, write the manifest JSON to this file.
    dicom_only : bool
        If True, only include DICOM files.

    Returns
    -------
    IntegrityManifest
        The generated manifest.
    """
    root = Path(dataset_path)
    if not root.exists():
        raise FileNotFoundError_(str(root))

    all_files = sorted(f for f in root.rglob("*") if f.is_file())
    records: list[FileIntegrityRecord] = []

    for file_path in all_files:
        if dicom_only and not is_dicom_file(file_path):
            continue

        try:
            size = file_path.stat().st_size
            sha = compute_sha256(file_path)
            relative = str(file_path.relative_to(root))
            records.append(FileIntegrityRecord(
                path=relative,
                size=size,
                sha256=sha,
            ))
        except (PermissionError, OSError) as exc:
            logger.warning("Cannot hash file %s: %s", file_path, exc)

    manifest = IntegrityManifest(
        dataset_path=str(root),
        generated_at=datetime.now(timezone.utc).isoformat(),
        files=records,
    )

    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(manifest.model_dump(), indent=2),
            encoding="utf-8",
        )
        logger.info("Manifest written to %s (%d files)", out, len(records))

    return manifest


def verify_manifest(
    manifest_path: str | Path,
    dataset_path: str | Path,
) -> IntegrityVerification:
    """Verify a dataset against a previously generated manifest.

    Parameters
    ----------
    manifest_path : str | Path
        Path to the JSON manifest file.
    dataset_path : str | Path
        Root directory of the dataset to verify.

    Returns
    -------
    IntegrityVerification
        Verification result with matched, mismatched, missing, and extra files.
    """
    mpath = Path(manifest_path)
    dpath = Path(dataset_path)

    if not mpath.exists():
        raise FileNotFoundError_(str(mpath))
    if not dpath.exists():
        raise FileNotFoundError_(str(dpath))

    try:
        raw = json.loads(mpath.read_text(encoding="utf-8"))
        manifest = IntegrityManifest(**raw)
    except Exception as exc:
        raise IntegrityError(f"Cannot parse manifest: {mpath} ({exc})") from exc

    result = IntegrityVerification(
        manifest_path=str(mpath),
        dataset_path=str(dpath),
        total_in_manifest=len(manifest.files),
    )

    # Build set of current files (relative paths)
    current_files: set[str] = set()
    for f in dpath.rglob("*"):
        if f.is_file():
            current_files.add(str(f.relative_to(dpath)))

    manifest_paths: set[str] = set()

    for record in manifest.files:
        manifest_paths.add(record.path)
        file_abs = dpath / record.path

        if not file_abs.exists():
            result.missing.append(record.path)
            continue

        try:
            current_hash = compute_sha256(file_abs)
        except (PermissionError, OSError):
            result.mismatched.append(record.path)
            continue

        if current_hash == record.sha256:
            result.matched += 1
        else:
            result.mismatched.append(record.path)

    # Extra files (in dataset but not in manifest)
    result.extra = sorted(current_files - manifest_paths)

    return result
