"""Every exit that bypasses the terminal stop releases its Quick windows before the loop ends (Current_Plan.md item
8b, N2.7 leftovers, "Exits that bypass the stop"; R-207 fixed the exiting stops themselves).

The bare ``QCoreApplication.exit(1)`` routes (the replacement barrier's timeout, a failed Settings, CUSTOM or
monitor teardown, a failed replacement), the terminal barrier's timeout and a second exiting stop during the
terminal drain each ended the loop with the generation's Quick window still alive; on Vulkan the process then
crashed at interpreter exit (0xC0000005). Each route runs in its own child process
(``tests/_quick_exit_route_probe.py``) on one real ``QuickDisplayRuntime`` hosted on the native core, kept off
screen. ``bare`` is the code before the fix in the same process shape: it must crash, or the test proves nothing.

Needs the built module (``release/native_module``, a GitHub build); skips without it.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from rendering.native import loader

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tests" / "_quick_exit_route_probe.py"
BUILT = os.name == "nt" and (ROOT / "release" / "native_module" / f"{loader.MODULE_NAME}.pyd").is_file()

ROUTES = [
    "replacement_barrier_timeout",
    "terminal_barrier_timeout",
    "settings_teardown_failed",
    "custom_teardown_failed",
    "monitor_teardown_failed",
    "replacement_continuation_failed",
    "second_exiting_stop",
]
# The code each route's loop must end with: the failing routes keep their exit(1); the stops quit cleanly.
EXIT_CODE = {"terminal_barrier_timeout": 0, "second_exiting_stop": 0}


def _run(route: str, variant: str, state_dir: Path) -> tuple[dict, int]:
    done = subprocess.run([sys.executable, str(PROBE), str(state_dir), route, variant], cwd=ROOT,
                          env=os.environ.copy(), text=True, capture_output=True, check=False, timeout=90)
    lines = [line for line in done.stdout.splitlines() if line.startswith("PROBE ")]
    assert lines, done.stdout + done.stderr
    return json.loads(lines[-1][len("PROBE "):]), done.returncode


@pytest.mark.skipif(not BUILT, reason="the native core is not built in this checkout: no release/native_module")
@pytest.mark.parametrize("variant", ["fixed", "bare"])
@pytest.mark.parametrize("route", ROUTES)
def test_the_route_releases_its_vulkan_window_before_the_loop_ends(route, variant, tmp_path):
    report, returncode = _run(route, variant, tmp_path)
    assert report["api"] == "Vulkan" and "timeout" not in report
    assert report["exec_code"] == EXIT_CODE.get(route, 1)
    if variant == "fixed":
        assert report["window_alive_at_loop_end"] is False and report["hosts_left"] == 0
        assert returncode == 0
    else:
        # The negative control: the loop ended with the window alive and the process crashed at its exit.
        assert report["window_alive_at_loop_end"] is True and report["hosts_left"] == 1
        assert returncode != 0
