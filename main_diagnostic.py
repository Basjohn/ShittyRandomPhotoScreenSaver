"""Source-run diagnostic entry point for SRPSS.

``python main_diagnostic.py`` runs the ordinary screensaver runtime and settings
profile with the diagnostic flavour: bounded per-user logging and fatal traceback
capture are activated before ``main`` is imported. Compiled builds have no
separate diagnostic compile: the Standard build publishes the same binary a
second time as ``SRPSS_Diagnostic.scr`` and ``main`` selects the flavour from
that name (``core/build_profile.py``). A direct launch runs the screensaver, and
``--debug`` opens a terminal.
"""
from __future__ import annotations

from core.build_profile import activate_diagnostic_build


activate_diagnostic_build()

from main import main as core_main  # noqa: E402


def main() -> int:
    return int(core_main(entrypoint="main_diagnostic"))


if __name__ == "__main__":  # pragma: no cover - thin wrapper
    raise SystemExit(main())
