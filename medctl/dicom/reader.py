"""DICOM file reading with robust error handling.

Provides safe wrappers around pydicom for reading DICOM files,
detecting whether a file is DICOM, and handling corrupt/invalid files
without raising unhandled exceptions.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pydicom
from pydicom.dataset import Dataset
from pydicom.errors import InvalidDicomError

logger = logging.getLogger(__name__)

# DICOM preamble magic bytes: 128-byte preamble followed by "DICM"
_DICM_MAGIC = b"DICM"
_PREAMBLE_LEN = 128

# File extensions that are definitively NOT DICOM — skip them to avoid
# false positives from pydicom's force=True mode which parses anything.
_NON_DICOM_EXTENSIONS: set[str] = {
    ".csv", ".txt", ".json", ".xml", ".yaml", ".yml", ".log", ".md",
    ".pdf", ".html", ".htm", ".png", ".jpg", ".jpeg", ".gif", ".bmp",
    ".tiff", ".tif", ".zip", ".tar", ".gz", ".py", ".js", ".ts",
    ".cfg", ".ini", ".toml", ".rst", ".doc", ".docx", ".xls", ".xlsx",
}

# Minimum DICOM tags that a valid DICOM file should have at least one of
_DICOM_INDICATOR_TAGS: tuple[str, ...] = (
    "SOPClassUID", "Modality", "PatientID", "StudyInstanceUID",
    "SeriesInstanceUID", "SOPInstanceUID", "BitsAllocated",
)


def is_dicom_file(path: str | Path) -> bool:
    """Check if a file is likely DICOM by inspecting the preamble.

    Checks for the standard 128-byte preamble + 'DICM' marker.
    Falls back to attempting a parse for files without a preamble
    (some legacy DICOM files omit it), but only if the file extension
    is not a known non-DICOM type.
    """
    path = Path(path)
    if not path.is_file():
        return False

    # Reject known non-DICOM extensions before any parsing
    if path.suffix.lower() in _NON_DICOM_EXTENSIONS:
        return False

    try:
        with open(path, "rb") as fh:
            # Try the standard preamble check first
            header = fh.read(_PREAMBLE_LEN + 4)
            if len(header) >= _PREAMBLE_LEN + 4:
                if header[_PREAMBLE_LEN: _PREAMBLE_LEN + 4] == _DICM_MAGIC:
                    return True

        # Fallback: attempt a lightweight parse for preamble-less DICOM.
        # force=True will parse almost anything, so we must validate
        # that the result actually contains real DICOM tags.
        ds = pydicom.dcmread(str(path), stop_before_pixels=True, force=True)
        return _has_dicom_tags(ds)
    except Exception:
        return False


def has_dicom_tags(ds: Dataset) -> bool:
    """Check whether a parsed Dataset contains at least one real DICOM tag."""
    for tag_keyword in _DICOM_INDICATOR_TAGS:
        if hasattr(ds, tag_keyword) and getattr(ds, tag_keyword, None) is not None:
            return True
    return False


def read_dicom_file(
    path: str | Path,
    stop_before_pixels: bool = True,
    force: bool = False,
) -> Dataset | None:
    """Read a DICOM file and return the parsed Dataset, or None on failure.

    Parameters
    ----------
    path : str | Path
        Path to the DICOM file.
    stop_before_pixels : bool
        If True, skip reading pixel data (faster for metadata-only operations).
    force : bool
        If True, force reading even without a proper DICOM preamble.

    Returns
    -------
    Dataset | None
        Parsed pydicom Dataset, or None if the file cannot be read/parsed.
    """
    path = Path(path)
    if not path.is_file():
        logger.warning("File does not exist: %s", path)
        return None

    try:
        ds = pydicom.dcmread(str(path), stop_before_pixels=stop_before_pixels, force=force)
        if not has_dicom_tags(ds):
            logger.debug("File %s does not contain valid DICOM tags", path)
            return None
        return ds
    except InvalidDicomError:
        logger.debug("Invalid DICOM file: %s", path)
        return None
    except PermissionError:
        logger.warning("Permission denied reading file: %s", path)
        return None
    except Exception as exc:
        logger.debug("Error reading %s: %s", path, exc)
        return None


def read_dicom_file_with_pixels(path: str | Path) -> Dataset | None:
    """Read a DICOM file including pixel data.

    Used when pixel data is needed (e.g., format conversion).
    """
    return read_dicom_file(path, stop_before_pixels=False, force=False)
