# medctl — Modular Medical Imaging Analytics Toolkit

A production-quality, modular command-line toolkit for processing medical imaging datasets, primarily DICOM. Built for engineers and researchers who need reliable, auditable dataset operations.

## Features

### Objective 1 — Dataset Engineering
- **Inspect**: Recursive DICOM dataset scanning with metadata extraction and aggregated statistics
- **Validate**: Structural and dataset-level validation (missing tags, duplicate detection, UID hierarchy, modality consistency)
- **Integrity**: SHA-256 manifest generation and verification for dataset integrity checking
- **Convert**: DICOM → PNG conversion with windowing support for visual inspection

### Objective 2 — Secure Processing
- **PHI Detection**: Configurable scanning of DICOM metadata for sensitive patient information
- **Anonymization**: De-identification with field removal, pseudonymization, and deterministic UID regeneration
- **Verification**: Mandatory post-anonymization PHI scan to confirm complete de-identification
- **Audit Reporting**: Structured JSON reports documenting all anonymization operations (no raw PHI logged)

## Installation

```bash
# Clone the repository
cd med-img

# Option A: Install dependencies via requirements file
pip install -r requirements-dev.txt
pip install -e .

# Option B: Direct editable install with dev dependencies
pip install -e ".[dev]"
```

### Dependencies
- `pydicom` — DICOM reading and manipulation
- `typer[all]` — CLI framework
- `pydantic` — Data validation and configuration
- `numpy` — Pixel array operations
- `Pillow` — Image conversion
- `PyYAML` — Configuration file parsing
- `pytest` — Testing (dev dependency)

## CLI Usage

### Help and Version
```bash
medctl --help
medctl --version
```

### Inspect a Dataset
```bash
medctl inspect ./data

# Save as JSON
medctl inspect ./data --json-output report.json
```

### Validate a Dataset
```bash
medctl validate ./data

# Generate integrity manifest
medctl validate ./data --integrity-manifest manifest.json

# Verify against existing manifest
medctl validate ./data --verify-manifest manifest.json
```

### Anonymize a Dataset
```bash
medctl anonymize ./data --output ./anonymized

# With custom config
medctl anonymize ./data --output ./anonymized --config anon_config.yaml

# With audit report
medctl anonymize ./data --output ./anonymized --report audit.json
```

### Convert to PNG
```bash
medctl convert ./image.dcm --output ./preview.png --format png

# With custom windowing
medctl convert ./image.dcm --output ./preview.png --format png \
    --window-center 40 --window-width 400
```

## Architecture

```
medctl/
├── cli/         # Typer CLI commands (inspect, validate, anonymize, convert)
├── core/        # Domain models, config, dataset scanning, pipeline, exceptions
├── dicom/       # DICOM reader, metadata, validator, anonymizer, UID mapper, rules
├── validation/  # Integrity checking (SHA-256), dataset consistency checks
├── conversion/  # Format conversion (DICOM → PNG)
└── reporting/   # Console and JSON report output
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed design documentation.

## Configuration

Anonymization rules can be configured via YAML:

```yaml
anonymization:
  remove:
    - PatientName
    - PatientBirthDate
    - InstitutionName

  pseudonymize:
    - PatientID

  replace:
    AccessionNumber: ""

  regenerate_uids: true
  verify_after_anonymization: true
```

## Example Workflow

```bash
# 1. Inspect the dataset
medctl inspect ./data

# 2. Validate structural integrity
medctl validate ./data

# 3. Generate integrity manifest
medctl validate ./data --integrity-manifest manifest.json

# 4. Anonymize with verification
medctl anonymize ./data --output ./anonymized --report audit.json

# 5. Validate the anonymized dataset
medctl validate ./anonymized

# 6. Convert for visual inspection
medctl convert ./anonymized/image.dcm --output ./preview.png --format png
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=medctl

# Run a specific test module
pytest tests/test_anonymization.py -v
```

Tests use synthetic DICOM fixtures — no real patient data is required.

## TCIA Pseudo-PHI Dataset

For demonstration with intentionally-inserted synthetic PHI:

1. Download the **TCIA Pseudo-PHI-DICOM-Data** dataset
2. Place it in `./data/` (or configure path as needed)
3. Run: `medctl anonymize ./data --output ./anonymized`

## Security

- Source datasets are **never modified** by default
- Raw PHI is **never logged** or printed in reports
- Audit reports contain operation metadata only, not sensitive values
- Files are **never silently overwritten**
- Post-anonymization verification is **mandatory** by default

See [SECURITY.md](SECURITY.md) for the complete security policy.

## Limitations

- Conversion currently supports DICOM → PNG only
- Anonymization handles standard DICOM header tags; pixel-level PHI (burned-in text) is not detected
- No support for DICOMDIR files
- Single-threaded processing (adequate for typical dataset sizes)

## Future Modules (Not Yet Implemented)

The architecture supports clean extension for:
- Image quality assessment
- Longitudinal comparison and change detection
- Visualization and visual summaries
- Additional medical image formats (NIfTI, etc.)
- AI/ML integration

## License

MIT License
