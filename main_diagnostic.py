"""Dedicated installable diagnostic entry point for SRPSS.

This is intentionally separate from both release entry points.  It runs the
ordinary screensaver runtime and settings profile, but activates bounded
per-user logging and fatal traceback capture before importing ``main``.
"""
from __future__ import annotations

import logging
import sys

from core.build_profile import activate_diagnostic_build
# Keep the locally imported crash owner visible to Nuitka's static graph even
# though ordinary runtime setup only opens it after logging is configured.
from core.logging import crash_capture as _crash_capture  # noqa: F401
from core.logging import ownership_trace as _ownership_trace  # noqa: F401


activate_diagnostic_build()

from main import main as core_main  # noqa: E402


def _inject_run_mode_arg() -> None:
    """Default a direct diagnostic launch to the ordinary RUN route.

    ``main.parse_screensaver_args`` only consumes the first non-filtered
    argument.  Diagnostic-only/unknown convenience arguments (for example
    ``-console``) must therefore not be allowed to sit in front of the injected
    ``/s`` token or a frozen build will fall back to CONFIG mode.
    """

    args = tuple(str(arg).strip().lower() for arg in sys.argv[1:])
    has_mode = any(
        arg == "/s"
        or arg.startswith("/c")
        or arg in ("/p", "-c", "-p", "-s", "--s")
        for arg in args
    )
    if not has_mode:
        # Insert immediately after argv[0], rather than appending, so the
        # screensaver parser sees RUN first even when an unknown diagnostic
        # convenience token (such as ``-console``) was supplied.
        sys.argv.insert(1, "/s")


def _install_reentrancy_safe_window_state_probe() -> None:
    """Keep diagnostic native-event logging from recursively entering Qt.

    The shared win_diag native-event path calls ``DisplayWidget._debug_window_state``
    synchronously from ``nativeEvent``.  The normal implementation queries Qt
    window state (winId/isVisible/windowState/etc.), and those queries can emit
    another native event in the compiled diagnostic runtime.  That creates the
    observed nativeEvent -> debug_window_state -> nativeEvent recursion and ends
    in a Windows access violation.

    For the diagnostic product only, replace that probe with a Python-only
    snapshot.  The native message details are already supplied in ``extra``;
    ownership/lifecycle diagnostics remain enabled and no Qt API is called from
    inside the native-event stack.
    """

    from rendering.display_widget import DisplayWidget

    win_diag_logger = logging.getLogger("win_diag")

    def _safe_debug_window_state(self, label: str, *, extra: str = "") -> None:
        if not win_diag_logger.isEnabledFor(logging.DEBUG):
            return
        try:
            win_diag_logger.debug(
                "[WIN_STATE_SAFE] %s screen=%s py_id=%#x %s",
                label,
                getattr(self, "screen_index", "?"),
                id(self),
                extra,
            )
        except Exception:
            # Diagnostic instrumentation must never be able to take down the
            # runtime it is supposed to observe.
            return

    DisplayWidget._debug_window_state = _safe_debug_window_state


def main() -> int:
    _inject_run_mode_arg()
    _install_reentrancy_safe_window_state_probe()
    return int(core_main(entrypoint="main_diagnostic"))


if __name__ == "__main__":  # pragma: no cover - thin compiled wrapper
    raise SystemExit(main())
