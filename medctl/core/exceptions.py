"""Standardized exceptions for the MEDIMG toolkit.

All domain-specific exceptions inherit from MedctlError so callers can
catch a single base type when they want to handle any toolkit error.
"""

from __future__ import annotations


class MedctlError(Exception):
    """Base exception for all MEDIMG errors."""


# ---------------------------------------------------------------------------
# File and I/O errors
# ---------------------------------------------------------------------------

class FileNotFoundError_(MedctlError):
    """Raised when an expected file or directory does not exist."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Path not found: {path}")


class FileReadError(MedctlError):
    """Raised when a file cannot be read (permissions, corruption, etc.)."""

    def __init__(self, path: str, reason: str = "") -> None:
        self.path = path
        self.reason = reason
        detail = f" ({reason})" if reason else ""
        super().__init__(f"Cannot read file: {path}{detail}")


# ---------------------------------------------------------------------------
# DICOM errors
# ---------------------------------------------------------------------------

class DicomParseError(MedctlError):
    """Raised when a file cannot be parsed as valid DICOM."""

    def __init__(self, path: str, reason: str = "") -> None:
        self.path = path
        self.reason = reason
        detail = f" ({reason})" if reason else ""
        super().__init__(f"Invalid DICOM file: {path}{detail}")


class DicomWriteError(MedctlError):
    """Raised when a DICOM file cannot be written."""

    def __init__(self, path: str, reason: str = "") -> None:
        self.path = path
        self.reason = reason
        detail = f" ({reason})" if reason else ""
        super().__init__(f"Cannot write DICOM file: {path}{detail}")


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

class ValidationError(MedctlError):
    """Raised when dataset validation fails with critical errors."""

    def __init__(self, message: str, error_count: int = 0) -> None:
        self.error_count = error_count
        super().__init__(message)


class IntegrityError(MedctlError):
    """Raised when an integrity check (e.g. SHA-256 manifest) fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


# ---------------------------------------------------------------------------
# Anonymization errors
# ---------------------------------------------------------------------------

class AnonymizationError(MedctlError):
    """Raised when de-identification cannot be completed safely."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class VerificationError(MedctlError):
    """Raised when post-anonymization verification detects residual PHI."""

    def __init__(self, message: str, phi_remaining: int = 0) -> None:
        self.phi_remaining = phi_remaining
        super().__init__(message)


# ---------------------------------------------------------------------------
# Conversion errors
# ---------------------------------------------------------------------------

class ConversionError(MedctlError):
    """Raised when format conversion fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class UnsupportedFormatError(ConversionError):
    """Raised for unsupported target conversion formats."""

    def __init__(self, fmt: str) -> None:
        self.fmt = fmt
        super().__init__(f"Unsupported conversion format: {fmt}")


# ---------------------------------------------------------------------------
# Configuration errors
# ---------------------------------------------------------------------------

class ConfigError(MedctlError):
    """Raised for configuration loading or validation failures."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


# ---------------------------------------------------------------------------
# Output / path errors
# ---------------------------------------------------------------------------

class OutputPathError(MedctlError):
    """Raised when the output path is invalid or not writable."""

    def __init__(self, path: str, reason: str = "") -> None:
        self.path = path
        self.reason = reason
        detail = f" ({reason})" if reason else ""
        super().__init__(f"Invalid output path: {path}{detail}")
