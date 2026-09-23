"""Console output formatting for MEDIMG reports.

Produces structured, readable terminal output using Rich tables and
panels.  Never prints raw PHI values — only presence indicators and
aggregated counts.
"""

from __future__ import annotations

import sys
from typing import TextIO

from medctl.core.models import (
    AnonymizationReport,
    ConversionResult,
    DatasetStats,
    IntegrityVerification,
    Severity,
    ValidationResult,
    VerificationStatus,
)


def _separator(width: int = 40) -> str:
    return "─" * width


def _status_badge(status: VerificationStatus) -> str:
    labels = {
        VerificationStatus.PASS: "✓ PASS",
        VerificationStatus.FAIL: "✗ FAIL",
        VerificationStatus.WARNING: "⚠ WARNING",
    }
    return labels.get(status, str(status))


def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable size string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0  # type: ignore[assignment]
    return f"{size_bytes:.1f} PB"


# ---------------------------------------------------------------------------
# Inspection report
# ---------------------------------------------------------------------------

def print_inspection_report(stats: DatasetStats, out: TextIO | None = None) -> None:
    """Print a formatted dataset inspection report."""
    if out is None:
        out = sys.stdout
    lines: list[str] = []
    lines.append("")
    lines.append("MEDCTL DATASET INSPECTION")
    lines.append(_separator(40))
    lines.append("")
    lines.append(f"  Dataset:       {stats.dataset_path}")
    lines.append("")
    lines.append("  Files:")
    lines.append(f"    Total:       {stats.total_files}")
    lines.append(f"    DICOM:       {stats.dicom_files}")
    lines.append(f"    Non-DICOM:   {stats.non_dicom_files}")
    lines.append(f"    Invalid:     {stats.invalid_files}")
    lines.append(f"    Total size:  {_human_size(stats.total_size_bytes)}")
    lines.append("")
    lines.append(f"  Patients:      {stats.unique_patients}")
    lines.append(f"  Studies:       {stats.unique_studies}")
    lines.append(f"  Series:        {stats.unique_series}")
    lines.append("")

    if stats.modality_counts:
        lines.append("  Modalities:")
        for mc in stats.modality_counts:
            lines.append(f"    {mc.modality:<12} {mc.count}")
        lines.append("")

    lines.append("  Metadata:")
    lines.append(f"    Patient ID:  {'PRESENT' if stats.has_patient_id else 'MISSING'}")
    lines.append(f"    Study UID:   {'PRESENT' if stats.has_study_uid else 'MISSING'}")
    lines.append(f"    Series UID:  {'PRESENT' if stats.has_series_uid else 'MISSING'}")
    lines.append(f"    SOP UID:     {'PRESENT' if stats.has_sop_uid else 'MISSING'}")
    lines.append("")

    out.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Validation report
# ---------------------------------------------------------------------------

def print_validation_report(result: ValidationResult, out: TextIO | None = None) -> None:
    """Print a formatted dataset validation report."""
    if out is None:
        out = sys.stdout
    lines: list[str] = []
    lines.append("")
    lines.append("MEDCTL DATASET VALIDATION")
    lines.append(_separator(40))
    lines.append("")
    lines.append(f"  Files scanned:     {result.files_scanned}")
    lines.append(f"  Valid DICOM:       {result.valid_dicom}")
    lines.append(f"  Non-DICOM:         {result.non_dicom_files}")
    lines.append(f"  Invalid DICOM:     {result.invalid_dicom}")
    lines.append(f"  Duplicates:        {result.duplicates}")
    lines.append("")
    lines.append(f"  Errors:            {len(result.errors)}")
    lines.append(f"  Warnings:          {len(result.warnings)}")
    lines.append("")

    # Print findings grouped by severity
    for severity in (Severity.ERROR, Severity.WARNING, Severity.INFO):
        items = [f for f in result.findings if f.severity == severity]
        if items:
            lines.append(f"  {severity.value}S:")
            for finding in items[:20]:  # Limit output
                loc = f" [{finding.file_path}]" if finding.file_path else ""
                lines.append(f"    [{finding.code}] {finding.message}{loc}")
            if len(items) > 20:
                lines.append(f"    ... and {len(items) - 20} more")
            lines.append("")

    lines.append(f"  STATUS: {_status_badge(result.status)}")
    lines.append("")

    out.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Integrity verification report
# ---------------------------------------------------------------------------

def print_integrity_report(result: IntegrityVerification, out: TextIO | None = None) -> None:
    """Print a formatted integrity verification report."""
    if out is None:
        out = sys.stdout
    lines: list[str] = []
    lines.append("")
    lines.append("MEDCTL INTEGRITY VERIFICATION")
    lines.append(_separator(40))
    lines.append("")
    lines.append(f"  Manifest:          {result.manifest_path}")
    lines.append(f"  Dataset:           {result.dataset_path}")
    lines.append(f"  Files in manifest: {result.total_in_manifest}")
    lines.append(f"  Matched:           {result.matched}")
    lines.append(f"  Mismatched:        {len(result.mismatched)}")
    lines.append(f"  Missing:           {len(result.missing)}")
    lines.append(f"  Extra:             {len(result.extra)}")
    lines.append("")

    if result.mismatched:
        lines.append("  Mismatched files:")
        for p in result.mismatched[:10]:
            lines.append(f"    - {p}")
        if len(result.mismatched) > 10:
            lines.append(f"    ... and {len(result.mismatched) - 10} more")
        lines.append("")

    if result.missing:
        lines.append("  Missing files:")
        for p in result.missing[:10]:
            lines.append(f"    - {p}")
        if len(result.missing) > 10:
            lines.append(f"    ... and {len(result.missing) - 10} more")
        lines.append("")

    lines.append(f"  STATUS: {_status_badge(result.status)}")
    lines.append("")

    out.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Anonymization report
# ---------------------------------------------------------------------------

def print_anonymization_report(report: AnonymizationReport, out: TextIO | None = None) -> None:
    """Print a formatted anonymization audit report."""
    if out is None:
        out = sys.stdout
    lines: list[str] = []
    lines.append("")
    lines.append("MEDCTL ANONYMIZATION REPORT")
    lines.append(_separator(40))
    lines.append("")
    lines.append(f"  Input:             {report.input_path}")
    lines.append(f"  Output:            {report.output_path}")
    lines.append(f"  Input files:       {report.input_files}")
    lines.append(f"  Output files:      {report.output_files}")
    lines.append("")
    lines.append(f"  Fields removed:        {report.fields_removed}")
    lines.append(f"  Fields replaced:       {report.fields_replaced}")
    lines.append(f"  Fields pseudonymized:  {report.fields_pseudonymized}")
    lines.append(f"  UIDs regenerated:      {report.uids_regenerated}")
    lines.append(f"  Paths sanitized:       {report.paths_sanitized}")
    lines.append("")

    if report.verification:
        v = report.verification
        lines.append("  Verification:")
        lines.append(f"    PHI before:      {v.phi_before}")
        lines.append(f"    PHI after:       {v.phi_after}")
        lines.append(f"    UID consistency: {_status_badge(v.uid_consistency)}")
        lines.append(f"    Path privacy:    {_status_badge(v.path_privacy)}")
        lines.append(f"    Status:          {_status_badge(v.status)}")
        lines.append("")

    lines.append(f"  Source modified:   {'YES' if report.source_modified else 'NO'}")
    lines.append("")

    overall = VerificationStatus.PASS
    if report.verification and report.verification.status != VerificationStatus.PASS:
        overall = report.verification.status
    if report.source_modified:
        overall = VerificationStatus.FAIL

    lines.append(f"  ANONYMIZATION STATUS: {_status_badge(overall)}")
    lines.append("")

    out.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Conversion report
# ---------------------------------------------------------------------------

def print_conversion_report(result: ConversionResult, out: TextIO | None = None) -> None:
    """Print a formatted conversion result."""
    if out is None:
        out = sys.stdout
    lines: list[str] = []
    lines.append("")
    lines.append("MEDCTL FORMAT CONVERSION")
    lines.append(_separator(40))
    lines.append("")
    lines.append(f"  Input:           {result.input_path}")
    lines.append(f"  Output:          {result.output_path}")
    lines.append(f"  Format:          {result.output_format.upper()}")
    lines.append(f"  Files converted: {result.files_converted}")
    lines.append(f"  Status:          {'✓ SUCCESS' if result.success else '✗ FAILED'}")
    lines.append("")
    if result.message:
        lines.append(f"  Note: {result.message}")
        lines.append("")

    out.write("\n".join(lines))
