"""End-to-End Pipeline Runner for MEDIMG.

Creates a dedicated, timestamped directory under `runs/` for each execution:
    runs/run_YYYYMMDD_HHMMSS/
        ├── inspect_report.json
        ├── manifest.json
        ├── anonymized/
        │   └── patient_0001/...
        ├── audit_report.json
        └── preview/
            └── sample.png

Usage:
    python scripts/run_pipeline.py [DATASET_PATH]
"""

from __future__ import annotations

import datetime
import subprocess
import sys
from pathlib import Path

DEFAULT_DATASET = Path("data")


def main() -> None:
    dataset_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATASET
    if not dataset_path.exists():
        print(f"Error: Dataset path does not exist: {dataset_path}")
        sys.exit(1)

    # 1. Create dedicated run folder
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path("runs") / f"run_{timestamp}"
    anon_dir = run_dir / "anonymized"
    preview_dir = run_dir / "preview"
    run_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 70)
    print(f"  MEDCTL END-TO-END PIPELINE RUN: {run_dir.name}")
    print("=" * 70)
    print(f"Input Dataset:  {dataset_path.resolve()}")
    print(f"Dedicated Run:  {run_dir.resolve()}\n")

    cmd_base = [sys.executable, "-m", "medctl.cli.main"]

    # 2. Inspect
    print(">>> [Step 1/5] Inspecting Dataset...")
    inspect_json = run_dir / "inspect_report.json"
    subprocess.run([*cmd_base, "inspect", str(dataset_path), "-j", str(inspect_json)], check=True)

    # 3. Validate & Generate Manifest
    print("\n>>> [Step 2/5] Validating Dataset and Generating SHA-256 Manifest...")
    manifest_path = run_dir / "manifest.json"
    subprocess.run([*cmd_base, "validate", str(dataset_path), "-m", str(manifest_path)], check=True)

    # 4. Anonymize
    print("\n>>> [Step 3/5] Anonymizing Dataset with Policy-Aware Verification...")
    audit_report = run_dir / "audit_report.json"
    subprocess.run([
        *cmd_base, "anonymize", str(dataset_path),
        "-o", str(anon_dir),
        "-r", str(audit_report),
    ], check=True)

    # 5. Validate Anonymized Output
    print("\n>>> [Step 4/5] Validating Anonymized Dataset...")
    subprocess.run([*cmd_base, "validate", str(anon_dir)], check=True)

    # 6. Format Conversion (Sample image)
    print("\n>>> [Step 5/5] Generating Visual Derivatives (PNG)...")
    sample_dicoms = sorted(anon_dir.rglob("*.dcm"))
    if sample_dicoms:
        sample_img = sample_dicoms[0]
        png_out = preview_dir / f"{sample_img.stem}.png"
        subprocess.run([*cmd_base, "convert", str(sample_img), "-o", str(png_out), "-f", "png"], check=True)
        print(f"Sample converted: {png_out}")

    print("\n" + "=" * 70)
    print("  RUN COMPLETED SUCCESSFULLY")
    print("=" * 70)
    print(f"Outputs stored in: {run_dir.resolve()}")
    print(f"  - Inspection Report: {inspect_json.name}")
    print(f"  - Integrity Manifest: {manifest_path.name}")
    print(f"  - Anonymized Dataset: anonymized/ ({len(sample_dicoms)} files)")
    print(f"  - Audit Report:       {audit_report.name}")
    print(f"  - Visual Previews:    preview/")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
