"""Compatibility alias for medctl."""
from __future__ import annotations

import sys
import medctl

sys.modules["medimg"] = medctl
