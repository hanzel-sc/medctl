"""Quick utility to inspect and compare a DICOM file Before vs After anonymization.

Usage:
    python scripts/compare.py <original_file.dcm> <anonymized_file.dcm>
Or run without arguments to compare the default Douglas Davidson test file.
"""

import sys
from pathlib import Path
import hashlib
import pydicom

DEFAULT_ORIGINAL = Path(
    r"data\pseudo_phi_dicom_data\292821506\2013-07-13-XR CHEST AP PORTABLE for Douglas Davidson-46198\1001-37718\60d7d4e2-31c6-4a38-9dc1-672edd745417.dcm"
)


def find_latest_anonymized_file() -> Path | None:
    """Find the first DICOM file in the most recent run folder or output directory."""
    for base in [Path("runs"), Path("output"), Path("anonymized")]:
        if base.exists():
            # Check latest subfolder or base
            dcm_files = sorted(base.rglob("*.dcm"), key=lambda p: p.stat().st_mtime, reverse=True)
            if dcm_files:
                return dcm_files[0]
    return None

def compare_dicoms(orig_path: Path, anon_path: Path):
    if not orig_path.exists():
        print(f"Error: Original file not found at: {orig_path}")
        return
    if not anon_path.exists():
        print(f"Error: Anonymized file not found at: {anon_path}")
        return

    ds_orig = pydicom.dcmread(str(orig_path))
    ds_anon = pydicom.dcmread(str(anon_path))

    # Tags to inspect
    tags = [
        ("Patient Name", "PatientName"),
        ("Patient ID", "PatientID"),
        ("Patient Birth Date", "PatientBirthDate"),
        ("Patient Sex", "PatientSex"),
        ("Study Date", "StudyDate"),
        ("Study Time", "StudyTime"),
        ("Accession Number", "AccessionNumber"),
        ("Institution Name", "InstitutionName"),
        ("Referring Physician", "ReferringPhysicianName"),
        ("Study Instance UID", "StudyInstanceUID"),
        ("Series Instance UID", "SeriesInstanceUID"),
        ("SOP Instance UID", "SOPInstanceUID"),
    ]

    print("\n" + "=" * 80)
    print("           MEDCTL BEFORE VS AFTER ANONYMIZATION AUDIT")
    print("=" * 80)
    print(f"Original:   {orig_path}")
    print(f"Anonymized: {anon_path}")
    print("-" * 80)
    print(f"{'DICOM Attribute':<24} | {'BEFORE (Original)':<24} | {'AFTER (Anonymized)':<26}")
    print("-" * 80)

    for label, attr in tags:
        val_orig = str(getattr(ds_orig, attr, "<NOT PRESENT>"))
        val_anon = str(getattr(ds_anon, attr, "<REMOVED / STRIPPED>"))
        if len(val_orig) > 22:
            val_orig = val_orig[:19] + "..."
        if len(val_anon) > 24:
            val_anon = val_anon[:21] + "..."
        print(f"{label:<24} | {val_orig:<24} | {val_anon:<26}")

    print("-" * 80)
    
    # Pixel verification
    orig_px_hash = hashlib.sha256(ds_orig.pixel_array.tobytes()).hexdigest()[:12]
    anon_px_hash = hashlib.sha256(ds_anon.pixel_array.tobytes()).hexdigest()[:12]
    pixel_match = orig_px_hash == anon_px_hash

    print(f"Pixel Array Integrity:   {'MATCH (Diagnostic image preserved)' if pixel_match else 'MISMATCH'}")
    print(f"Pixel Array Hash:        Original: {orig_px_hash} | Anonymized: {anon_px_hash}")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    if len(sys.argv) == 3:
        p_orig = Path(sys.argv[1])
        p_anon = Path(sys.argv[2])
    else:
        p_orig = DEFAULT_ORIGINAL
        p_anon = find_latest_anonymized_file()
        if p_anon is None:
            print("No anonymized files found. Run anonymization first or pass path explicitly.")
            sys.exit(1)
    compare_dicoms(p_orig, p_anon)
