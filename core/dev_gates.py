"""Dev-gated feature flags for modes under active development.

Gates are activated via command-line flags:
    python main.py --debug --devcurve # legacy no-op (kept for compatibility)
    python main.py --debug --devsteam # show unfinished Steam card prototypes

These flags are stripped from sys.argv before screensaver mode parsing.
Tests can call ``force_gate()`` to enable gates without CLI flags.

See also: Spec.md § Dev Gates, Index.md § core/dev_gates.py
"""
from __future__ import annotations

import sys

_DEV_STEAM: bool = False
_ABC_DRIVE: str | None = None


def _parse_abc_drive(argv: list[str]) -> str | None:
    """Return the requested A/B/C condition, or None.

    Accepts ``--abc-drive=B`` or ``--abc-drive B``; the condition is one of
    A/B/C (case-insensitive). Opt-in and dev-only; never active in production.
    """
    for index, arg in enumerate(argv):
        value: str | None = None
        if arg.startswith("--abc-drive="):
            value = arg.split("=", 1)[1]
        elif arg == "--abc-drive" and index + 1 < len(argv):
            value = argv[index + 1]
        if value is not None:
            condition = value.strip().upper()
            return condition if condition in {"A", "B", "C"} else None
    return None


def _init_from_argv() -> None:
    """Read dev-gate flags from sys.argv.  Called once at import time."""
    global _DEV_STEAM, _ABC_DRIVE
    _DEV_STEAM = "--devsteam" in sys.argv
    _ABC_DRIVE = _parse_abc_drive(sys.argv)


def abc_drive_condition() -> str | None:
    """Return the opt-in visualizer-switch A/B/C experiment condition, if any."""
    return _ABC_DRIVE


def is_steam_enabled() -> bool:
    """True when unfinished Steam cards should be visible in UI/runtime."""
    return _DEV_STEAM


def is_named_gate_enabled(name: str | None) -> bool:
    """Return a central dev-gate state by stable feature name."""
    if name == "steam":
        return is_steam_enabled()
    return False


def gate_signature() -> tuple[tuple[str, bool], ...]:
    """Return cache-key-safe gate state for descriptor activation."""
    return (("steam", _DEV_STEAM),)


def force_gate(*, steam: bool | None = None, abc_drive: str | None = None) -> None:
    """Override gate state programmatically (for tests)."""
    global _DEV_STEAM, _ABC_DRIVE
    if steam is not None:
        _DEV_STEAM = steam
    if abc_drive is not None:
        _ABC_DRIVE = abc_drive.strip().upper() or None


_init_from_argv()
