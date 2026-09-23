"""Deterministic DICOM UID generation and mapping.

Generates valid DICOM UIDs that are:
  - Deterministic within a single anonymization operation
  - Consistent: same original UID always maps to the same new UID
  - Valid: conform to DICOM UID format (max 64 chars, digits and dots)
  - Hierarchically correct: related files keep consistent study/series UIDs

Uses a keyed hash approach with a per-operation salt so that UID mappings
are not reproducible across separate runs without the salt.
"""

from __future__ import annotations

import hashlib
import logging
import uuid

logger = logging.getLogger(__name__)

# DICOM UID root — using a well-known test/implementation root
# In production, organisations register their own root with IANA
_UID_ROOT = "1.2.826.0.1.3680043.8.498."

# Maximum DICOM UID length
_MAX_UID_LEN = 64


class UidMapper:
    """Deterministic UID mapper for a single anonymization session.

    Within one session, the same original UID is always mapped to the
    same anonymized UID.  Different sessions use different salts.

    Parameters
    ----------
    salt : str | None
        Optional salt for deterministic mapping.  If None, a random
        salt is generated (recommended for security).
    """

    def __init__(self, salt: str | None = None) -> None:
        self._salt = salt or uuid.uuid4().hex
        self._cache: dict[str, str] = {}
        logger.debug("UidMapper initialised (salt length: %d)", len(self._salt))

    @property
    def mapping_count(self) -> int:
        """Number of UIDs that have been mapped so far."""
        return len(self._cache)

    def map_uid(self, original_uid: str) -> str:
        """Map an original UID to a deterministic anonymised UID.

        Parameters
        ----------
        original_uid : str
            The original DICOM UID string.

        Returns
        -------
        str
            A valid, deterministic anonymised UID.
        """
        if original_uid in self._cache:
            return self._cache[original_uid]

        new_uid = self._generate_uid(original_uid)
        self._cache[original_uid] = new_uid
        return new_uid

    def _generate_uid(self, original_uid: str) -> str:
        """Generate a valid DICOM UID from the original using keyed hashing."""
        # Hash the salt + original UID
        digest = hashlib.sha256(
            f"{self._salt}:{original_uid}".encode("utf-8")
        ).hexdigest()

        # Convert hex digest to numeric string (DICOM UIDs are digits + dots)
        # Take enough hex chars and convert to decimal
        numeric = str(int(digest[:32], 16))

        # Build UID: root + numeric suffix, truncated to 64 chars
        uid = _UID_ROOT + numeric
        if len(uid) > _MAX_UID_LEN:
            uid = uid[:_MAX_UID_LEN]

        return uid

    def has_mapping(self, original_uid: str) -> bool:
        """Check if an original UID has already been mapped."""
        return original_uid in self._cache

    def verify_consistency(self, original_uid: str, expected_mapped: str) -> bool:
        """Verify that an original UID maps to the expected value."""
        if original_uid not in self._cache:
            return False
        return self._cache[original_uid] == expected_mapped


def generate_uid() -> str:
    """Generate a new random valid DICOM UID.

    Uses pydicom's generate_uid if available, otherwise falls back to
    a UUID-based approach.
    """
    try:
        from pydicom.uid import generate_uid as _pydicom_generate_uid
        return str(_pydicom_generate_uid())
    except ImportError:
        # Fallback: UUID-based
        numeric = str(uuid.uuid4().int)
        uid = _UID_ROOT + numeric
        if len(uid) > _MAX_UID_LEN:
            uid = uid[:_MAX_UID_LEN]
        return uid
