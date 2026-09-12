"""Dev-gated feature flags for modes under active development.

Gates are activated via command-line flags:
    python main.py --debug --devcurve # legacy no-op (kept for compatibility)
    python main.py --debug --devsteam # show unfinished Steam card prototypes
    python main.py --debug --devstats # show the experimental System Stats card

These flags are stripped from sys.argv before screensaver mode parsing.
Tests can call ``force_gate()`` to enable gates without CLI flags.

Diagnostic experiment admissions (``--abc-drive``, ``--viz-switch-telemetry``) are
**not** product feature gates and are deliberately owned elsewhere; see
``core/diagnostics/experiment_flags.py``.

See also: Spec.md § Dev Gates, Index.md § core/dev_gates.py
"""
from __future__ import annotations

import sys

_DEV_STEAM: bool = False
_DEV_SYSTEM_STATS: bool = False


def _init_from_argv() -> None:
    """Read dev-gate flags from sys.argv.  Called once at import time."""
    global _DEV_STEAM, _DEV_SYSTEM_STATS
    _DEV_STEAM = "--devsteam" in sys.argv
    _DEV_SYSTEM_STATS = "--devstats" in sys.argv


def is_steam_enabled() -> bool:
    """True when unfinished Steam cards should be visible in UI/runtime."""
    return _DEV_STEAM


def is_system_stats_enabled() -> bool:
    """True when the experimental System Stats family is available."""
    return _DEV_SYSTEM_STATS


def is_named_gate_enabled(name: str | None) -> bool:
    """Return a central dev-gate state by stable feature name."""
    if name == "steam":
        return is_steam_enabled()
    if name == "system_stats":
        return is_system_stats_enabled()
    return False


def gate_signature() -> tuple[tuple[str, bool], ...]:
    """Return cache-key-safe gate state for descriptor activation."""
    return (
        ("steam", _DEV_STEAM),
        ("system_stats", _DEV_SYSTEM_STATS),
    )


def force_gate(
    *,
    steam: bool | None = None,
    system_stats: bool | None = None,
) -> None:
    """Override gate state programmatically (for tests)."""
    global _DEV_STEAM, _DEV_SYSTEM_STATS
    if steam is not None:
        _DEV_STEAM = steam
    if system_stats is not None:
        _DEV_SYSTEM_STATS = system_stats


_init_from_argv()
