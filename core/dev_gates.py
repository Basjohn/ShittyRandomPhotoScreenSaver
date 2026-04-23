"""Dev-gated feature flags for modes under active development.

Gates are activated via command-line flags:
    python main.py --debug -devblob   # enable Blob mode
    python main.py --debug --devcurve # legacy no-op (kept for compatibility)

Both flags are stripped from sys.argv before screensaver mode parsing.
Tests can call ``force_gate()`` to enable gates without CLI flags.

See also: Spec.md § Dev Gates, Index.md § core/dev_gates.py
"""
from __future__ import annotations

import sys

_DEV_BLOB: bool = False


def _init_from_argv() -> None:
    """Read dev-gate flags from sys.argv.  Called once at import time."""
    global _DEV_BLOB
    _DEV_BLOB = "-devblob" in sys.argv


def is_blob_enabled() -> bool:
    """True when Blob mode should be visible in UI / preset swaps."""
    return _DEV_BLOB


def is_devcurve_enabled() -> bool:
    """Legacy compatibility helper: Dev Curve/Spline Curve is always active."""
    return True


def force_gate(*, blob: bool | None = None, devcurve: bool | None = None) -> None:
    """Override gate state programmatically (for tests)."""
    global _DEV_BLOB
    if blob is not None:
        _DEV_BLOB = blob
    # Kept for API compatibility: devcurve gate no longer controls visibility.
    _ = devcurve


_init_from_argv()
