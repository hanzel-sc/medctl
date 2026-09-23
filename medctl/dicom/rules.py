"""De-identification rule definitions for DICOM metadata.

Categorises DICOM tags into SAFE/PRESERVE, SENSITIVE/REMOVE,
UID/REGENERATE, and CONFIGURABLE groups following DICOM PS 3.15
Annex E guidelines.

Rules are configurable through the MedctlConfig system.
"""

from __future__ import annotations

from medctl.core.models import TagAction

# ---------------------------------------------------------------------------
# Default tag classification
# ---------------------------------------------------------------------------

# Tags that are safe to preserve (technical / imaging metadata)
SAFE_TAGS: set[str] = {
    "Modality",
    "SOPClassUID",
    "Rows",
    "Columns",
    "BitsAllocated",
    "BitsStored",
    "HighBit",
    "PixelRepresentation",
    "SamplesPerPixel",
    "PhotometricInterpretation",
    "SliceThickness",
    "PixelSpacing",
    "SpacingBetweenSlices",
    "ImageOrientationPatient",
    "ImagePositionPatient",
    "RescaleSlope",
    "RescaleIntercept",
    "WindowCenter",
    "WindowWidth",
    "Manufacturer",
    "ManufacturerModelName",
    "KVP",
    "ExposureTime",
    "XRayTubeCurrent",
    "RepetitionTime",
    "EchoTime",
    "MagneticFieldStrength",
    "FlipAngle",
    "SliceLocation",
    "ImageType",
    "BodyPartExamined",
    "ProtocolName",
    "ConvolutionKernel",
    "TransferSyntaxUID",
    "ImplementationClassUID",
    "SpecificCharacterSet",
}

# Tags containing PHI that should be removed by default
SENSITIVE_REMOVE_TAGS: set[str] = {
    "PatientName",
    "PatientBirthDate",
    "PatientBirthTime",
    "PatientAge",
    "PatientAddress",
    "PatientTelephoneNumbers",
    "OtherPatientIDs",
    "OtherPatientNames",
    "OtherPatientIDsSequence",
    "InstitutionName",
    "InstitutionAddress",
    "InstitutionalDepartmentName",
    "ReferringPhysicianName",
    "ReferringPhysicianAddress",
    "ReferringPhysicianTelephoneNumbers",
    "PerformingPhysicianName",
    "OperatorsName",
    "NameOfPhysiciansReadingStudy",
    "PhysiciansOfRecord",
    "RequestingPhysician",
    "ResponsiblePerson",
    "ResponsibleOrganization",
    "MedicalRecordLocator",
    "EthnicGroup",
    "Occupation",
    "AdditionalPatientHistory",
    "PatientComments",
    "RequestAttributesSequence",
    "ContentSequence",
}

# Tags that should be pseudonymised (replaced with consistent fake values)
SENSITIVE_PSEUDONYMIZE_TAGS: set[str] = {
    "PatientID",
}

# Tags that should be replaced with empty/safe values
SENSITIVE_REPLACE_TAGS: dict[str, str] = {
    "AccessionNumber": "",
    "StudyDescription": "",
    "SeriesDescription": "",
    "StudyDate": "",
    "StudyTime": "",
}

# UID tags that need deterministic regeneration
UID_REGENERATE_TAGS: set[str] = {
    "StudyInstanceUID",
    "SeriesInstanceUID",
    "SOPInstanceUID",
    "FrameOfReferenceUID",
}

# All known sensitive tags (union for PHI scanning)
ALL_SENSITIVE_TAGS: set[str] = (
    SENSITIVE_REMOVE_TAGS
    | SENSITIVE_PSEUDONYMIZE_TAGS
    | set(SENSITIVE_REPLACE_TAGS.keys())
)


def get_tag_action(keyword: str) -> TagAction:
    """Determine the default action for a DICOM tag keyword.

    Parameters
    ----------
    keyword : str
        DICOM keyword (e.g. "PatientName").

    Returns
    -------
    TagAction
        The action to take: PRESERVE, REMOVE, REPLACE, PSEUDONYMIZE,
        or REGENERATE_UID.
    """
    if keyword in SAFE_TAGS:
        return TagAction.PRESERVE
    if keyword in SENSITIVE_REMOVE_TAGS:
        return TagAction.REMOVE
    if keyword in SENSITIVE_PSEUDONYMIZE_TAGS:
        return TagAction.PSEUDONYMIZE
    if keyword in SENSITIVE_REPLACE_TAGS:
        return TagAction.REPLACE
    if keyword in UID_REGENERATE_TAGS:
        return TagAction.REGENERATE_UID
    # Default: preserve unknown tags (conservative approach — only remove
    # what we explicitly know is sensitive)
    return TagAction.PRESERVE


def build_action_map(
    remove: list[str] | None = None,
    pseudonymize: list[str] | None = None,
    replace: dict[str, str] | None = None,
    regenerate_uids: bool = True,
) -> dict[str, TagAction]:
    """Build a tag→action map from configuration overrides.

    The returned map only contains tags with non-PRESERVE actions.
    Tags not in the map are implicitly PRESERVE.
    """
    action_map: dict[str, TagAction] = {}

    # Defaults
    for tag in SENSITIVE_REMOVE_TAGS:
        action_map[tag] = TagAction.REMOVE
    for tag in SENSITIVE_PSEUDONYMIZE_TAGS:
        action_map[tag] = TagAction.PSEUDONYMIZE
    for tag in SENSITIVE_REPLACE_TAGS:
        action_map[tag] = TagAction.REPLACE
    if regenerate_uids:
        for tag in UID_REGENERATE_TAGS:
            action_map[tag] = TagAction.REGENERATE_UID

    # User overrides
    if remove is not None:
        for tag in remove:
            action_map[tag] = TagAction.REMOVE
    if pseudonymize is not None:
        for tag in pseudonymize:
            action_map[tag] = TagAction.PSEUDONYMIZE
    if replace is not None:
        for tag, val in replace.items():
            action_map[tag] = TagAction.REPLACE

    return action_map
