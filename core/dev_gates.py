"""Dev-gated feature flags for modes under active development.

Gates are activated via command-line flags:
    python main.py --debug -devblob   # enable Blob mode
    python main.py --debug --devcurve # legacy no-op (kept for compatibility)
    python main.py --debug --devsteam # show unfinished Steam card prototypes

These flags are stripped from sys.argv before screensaver mode parsing.
Tests can call ``force_gate()`` to enable gates without CLI flags.

See also: Spec.md § Dev Gates, Index.md § core/dev_gates.py
"""
from __future__ import annotations

import sys

_DEV_BLOB: bool = False
_DEV_STEAM: bool = False


def _init_from_argv() -> None:
    """Read dev-gate flags from sys.argv.  Called once at import time."""
    global _DEV_BLOB, _DEV_STEAM
    _DEV_BLOB = "-devblob" in sys.argv
    _DEV_STEAM = "--devsteam" in sys.argv


def is_blob_enabled() -> bool:
    """True when Blob mode should be visible in UI / preset swaps."""
    return _DEV_BLOB


def is_steam_enabled() -> bool:
    """True when unfinished Steam cards should be visible in UI/runtime."""
    return _DEV_STEAM


def is_named_gate_enabled(name: str | None) -> bool:
    """Return a central dev-gate state by stable feature name."""
    if name == "steam":
        return is_steam_enabled()
    if name == "blob":
        return is_blob_enabled()
    return False


def gate_signature() -> tuple[tuple[str, bool], ...]:
    """Return cache-key-safe gate state for descriptor activation."""
    return (
        ("blob", _DEV_BLOB),
        ("steam", _DEV_STEAM),
    )


def force_gate(*, blob: bool | None = None, steam: bool | None = None) -> None:
    """Override gate state programmatically (for tests)."""
    global _DEV_BLOB, _DEV_STEAM
    if blob is not None:
        _DEV_BLOB = blob
    if steam is not None:
        _DEV_STEAM = steam


_init_from_argv()
