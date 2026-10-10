"""Process-local build flavour identity.

One compile publishes two files from the same binary: ``SRPSS.scr`` and
``SRPSS_Diagnostic.scr`` (operator direction 2026-10-10: the diagnostic
artifact always comes with a Standard build, with no second compile). In a
compiled runtime the published file's own name selects the flavour, exactly
``SRPSS_Diagnostic`` and nothing looser, read from the launched binary's long
path before anything else is imported (``main.py``). Source runs select it only
through the explicit ``main_diagnostic.py`` entry point. No environment
variables or marker files.
"""
from __future__ import annotations

import os
import sys


_DIAGNOSTIC_BUILD = False
DIAGNOSTIC_ARTIFACT_STEM = "SRPSS_Diagnostic"


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


def _long_path(path: str) -> str:
    """``path`` with any 8.3 short components expanded (Windows stores screensavers by short path)."""
    if sys.platform != "win32" or not path:
        return path
    try:
        import ctypes

        absolute = os.path.abspath(path)
        size = ctypes.windll.kernel32.GetLongPathNameW(absolute, None, 0)
        if size:
            buffer = ctypes.create_unicode_buffer(size)
            if ctypes.windll.kernel32.GetLongPathNameW(absolute, buffer, size):
                return buffer.value
    except Exception:
        pass
    return path


def artifact_selects_diagnostic(argv0: str) -> bool:
    """Whether the launched binary ``argv0`` is the published diagnostic file."""
    name = os.path.basename(_long_path(str(argv0 or "")))
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return stem.casefold() == DIAGNOSTIC_ARTIFACT_STEM.casefold()


def activate_flavour_for_artifact(argv0: str) -> bool:
    """Select the diagnostic flavour when this compiled runtime was launched as
    ``SRPSS_Diagnostic``; source runs never select it by name. Returns whether it did."""
    if is_compiled_runtime() and artifact_selects_diagnostic(argv0):
        activate_diagnostic_build()
        return True
    return False


def activate_diagnostic_build() -> None:
    """Mark this process as the dedicated diagnostic build flavour."""

    global _DIAGNOSTIC_BUILD
    _DIAGNOSTIC_BUILD = True


def is_diagnostic_build() -> bool:
    """Return whether this process runs the diagnostic flavour."""

    return bool(_DIAGNOSTIC_BUILD)


def get_build_flavour() -> str:
    """Return the bounded startup identity used in logs and support evidence."""

    return "diagnostic" if is_diagnostic_build() else "release"
