"""Process-local build flavour identity.

Release entry points leave the default flavour untouched.  The dedicated
diagnostic entry point activates its flavour before importing the ordinary
runtime so logging and crash capture can be enabled without environment
variables, marker files, or release-build heuristics.
"""
from __future__ import annotations


_DIAGNOSTIC_BUILD = False


def activate_diagnostic_build() -> None:
    """Mark this process as the dedicated diagnostic build flavour."""

    global _DIAGNOSTIC_BUILD
    _DIAGNOSTIC_BUILD = True


def is_diagnostic_build() -> bool:
    """Return whether the dedicated diagnostic entry point owns this process."""

    return bool(_DIAGNOSTIC_BUILD)


def get_build_flavour() -> str:
    """Return the bounded startup identity used in logs and support evidence."""

    return "diagnostic" if is_diagnostic_build() else "release"
