"""Shared command-line runtime flag helpers.

Keep lightweight process-wide feature flags here so startup/runtime code does
not drift into repeated handwritten ``'--flag' in sys.argv`` checks.
"""
from __future__ import annotations

import sys


def has_cli_flag(*names: str) -> bool:
    """Return True when any of *names* appears in ``sys.argv``."""

    argv = tuple(str(arg) for arg in getattr(sys, "argv", ()) or ())
    return any(name in argv for name in names)


def automatic_service_updates_enabled() -> bool:
    """Return False when CLI explicitly disables automatic service retrievals."""

    return not has_cli_flag("--noupdates")
