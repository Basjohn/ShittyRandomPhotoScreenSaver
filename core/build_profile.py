"""Process-local build flavour identity.

Release entry points leave the default flavour untouched.  The dedicated
diagnostic entry point activates its flavour before importing the ordinary
runtime so logging and crash capture can be enabled without environment
variables, marker files, or release-build heuristics.
"""
from __future__ import annotations

import sys


_DIAGNOSTIC_BUILD = False


def is_compiled_runtime() -> bool:
    """Return whether this process is running from compiled application code.

    Runtime packaging and product flavour are deliberately separate concepts:
    a standard, Media Center, or diagnostic executable is compiled, while only
    the dedicated diagnostic entry point activates ``_DIAGNOSTIC_BUILD``.
    """

    if bool(getattr(sys, "frozen", False)):
        return True
    if bool(globals().get("__compiled__", False)):
        return True

    try:
        import builtins

        if bool(getattr(builtins, "__compiled__", False)):
            return True
    except Exception:
        pass

    main_mod = sys.modules.get("__main__")
    return bool(main_mod is not None and getattr(main_mod, "__compiled__", False))


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
