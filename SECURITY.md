# MEDCTL Security Policy

## Principles

MEDCTL handles sensitive medical imaging data (DICOM). The following security principles are enforced throughout the codebase.

## 1. Source Data Preservation

- **Source datasets are never modified by default.** All operations that produce output (anonymize, convert) write to a separate output directory.
- The anonymization engine explicitly checks that the output path differs from the input path and is not a subdirectory of the input.
- After anonymization, a lightweight check confirms that source files still exist.

## 2. No Raw PHI in Logs or Reports

- Console output displays **presence indicators** (e.g., `PRESENT` / `MISSING`) rather than raw field values for sensitive DICOM tags.
- Audit reports contain **operation metadata** (field counts, UID counts, verification status) but never raw patient names, IDs, or dates.
- The JSON report serializer includes a defence-in-depth sanitization pass that strips any PHI-like keys from report dictionaries.
- Python logging uses `logger.debug()` for internal operations and never interpolates raw PHI into log messages.

## 3. Anonymization Security

- **Field removal**: Sensitive tags (PatientName, PatientBirthDate, InstitutionName, etc.) are deleted from the DICOM dataset.
- **Pseudonymization**: PatientID is replaced with sequential pseudonyms (SUBJ-000001) that are consistent within a session but not reversible.
- **UID regeneration**: Uses a per-session random salt with SHA-256 hashing. The salt is generated using `uuid.uuid4()` and is not stored. This means UID mappings are:
  - **Deterministic within one session** (same original UID → same new UID)
  - **Not reproducible across sessions** (different salt → different mappings)
- **No hardcoded secrets**: The anonymization salt is always randomly generated unless explicitly provided.

## 4. Post-Anonymization Verification

- Verification is **mandatory by default** (`verify_after_anonymization: true`).
- After writing anonymized files, the system re-scans the output directory for any remaining PHI.
- If PHI remains, the verification status is set to `FAIL` and the CLI exits with a non-zero code.
- UID consistency is verified: each series should map to exactly one study.

## 5. File Safety

- **No silent overwrites**: Output directories are created but existing files are not silently replaced.
- **Input validation**: All paths are checked for existence and permissions before operations begin.
- **Safe filesystem operations**: `Path.mkdir(parents=True, exist_ok=True)` is used for directory creation. File writes use explicit paths.

## 6. Error Handling

- Domain exceptions inherit from `MedctlError` for consistent catching.
- CLI commands catch all exceptions and display user-friendly messages.
- Python stack traces are only shown when `--verbose` is enabled.
- The CLI uses meaningful exit codes: `0` for success, `1` for errors.

## 7. Configuration Security

- Configuration files are loaded and validated through Pydantic models.
- Invalid configuration produces clear error messages, not silent defaults.
- The configuration system does not execute arbitrary code or import untrusted modules.

## 8. Known Limitations

- **Pixel-level PHI**: MEDCTL does not detect or remove text burned into pixel data (e.g., patient names overlaid on images). This requires OCR-based detection, which is out of scope for the current version.
- **Private DICOM tags**: Some equipment vendors store PHI in private tags. The current rule set covers standard DICOM tags only. Custom rules can be added via configuration.
- **Metadata in nested sequences**: Deep nested DICOM sequences may contain PHI that is not covered by the flat tag scanning. Future versions may add recursive sequence scanning.

## 9. Recommended Practices

- Always run `medimg validate` on anonymized datasets before sharing.
- Use integrity manifests (`--integrity-manifest`) to detect unauthorized modifications.
- Review the anonymization audit report to confirm the expected number of fields were processed.
- Keep anonymization configuration files under version control.
- Do not store UID mapping salts or pseudonym mappings alongside anonymized data.
