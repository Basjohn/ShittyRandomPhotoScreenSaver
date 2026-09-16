"""Development feature flags for modes under active implementation.

The remaining product gate is activated via command line:
    python main.py --debug --devsteam # show the unfinished Steam Journey scaffold

``main.parse_screensaver_args`` still strips several retired/no-op CLI tokens;
that parser compatibility is cleanup debt tracked in ``Future_Cleanup.md`` and
does not control product availability. Tests can call ``force_gate()`` to enable
the remaining gate without CLI flags.

Diagnostic experiment admissions (``--abc-drive``, ``--viz-switch-telemetry``) are
**not** product feature gates and are deliberately owned elsewhere; see
``core/diagnostics/experiment_flags.py``.

See also: Spec.md § Dev Gates, Index.md § core/dev_gates.py
"""
from __future__ import annotations

import sys

_DEV_STEAM: bool = False


def _init_from_argv() -> None:
    """Read dev-gate flags from sys.argv.  Called once at import time."""
    global _DEV_STEAM
    _DEV_STEAM = "--devsteam" in sys.argv


def is_steam_enabled() -> bool:
    """True when the unfinished Steam Journey scaffold should be visible."""
    return _DEV_STEAM


def is_named_gate_enabled(name: str | None) -> bool:
    """Return a central dev-gate state by stable feature name."""
    if name == "steam":
        return is_steam_enabled()
    return False


def gate_signature() -> tuple[tuple[str, bool], ...]:
    """Return cache-key-safe gate state for descriptor activation."""
    return (("steam", _DEV_STEAM),)


def force_gate(
    *,
    steam: bool | None = None,
) -> None:
    """Override gate state programmatically (for tests)."""
    global _DEV_STEAM
    if steam is not None:
        _DEV_STEAM = steam


_init_from_argv()
