"""The Studio's own Quick window is gone before the loop ends on any exit, on Vulkan (Current_Plan.md item 8b, N2.7
leftovers: the Studio window was not among the windows ``release_quick_windows_then`` releases).

``release_quick_windows_then`` releases the display windows only. The Studio's window needs no release of its own:
``open_mode_studio`` connects the application's ``aboutToQuit`` to ``StudioController.close_for_quit`` (the real
wiring is pinned in ``tests/test_waveform_studio_lifecycle.py``, ``app_quit``), whose retirement queues the window's
deletion, and the loop's own end processes deferred deletions after ``aboutToQuit``: whatever route ends the loop, the
window is destroyed inside ``exec()``. Each case runs in its own child process (``tests/_studio_exit_probe.py``): the
production ``StudioWindowSurface`` on Vulkan, kept off screen, exiting through a failing route's real exit.

- ``qt``: the window as the product makes it today, on Qt Quick's own Vulkan device (not the native core's). Even
  left alive at the loop's end it does not crash the process's exit.
- ``core``: the window handed to the native core before its first show, as a display window is and as a Studio
  previewing a native renderer will be. Left alive (``unwired``, the negative control) the process crashes at its
  exit as the display windows did (R-209); with the quit edge (``wired``) it is destroyed and the exit is clean.

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
PROBE = ROOT / "tests" / "_studio_exit_probe.py"
BUILT = os.name == "nt" and (ROOT / "release" / "native_module" / f"{loader.MODULE_NAME}.pyd").is_file()


def _run(variant: str, device: str, state_dir: Path) -> tuple[dict, int]:
    done = subprocess.run([sys.executable, str(PROBE), str(state_dir), variant, device], cwd=ROOT,
                          env=os.environ.copy(), text=True, capture_output=True, check=False, timeout=90)
    lines = [line for line in done.stdout.splitlines() if line.startswith("PROBE ")]
    assert lines, done.stdout + done.stderr
    return json.loads(lines[-1][len("PROBE "):]), done.returncode


@pytest.mark.skipif(not BUILT, reason="the native core is not built in this checkout: no release/native_module")
@pytest.mark.parametrize("device", ["qt", "core"])
def test_the_quit_edge_destroys_the_studio_window_before_the_loop_ends(device, tmp_path):
    report, returncode = _run("wired", device, tmp_path)
    assert report["api"] == "Vulkan" and "timeout" not in report
    assert report["hosts"] == (1 if device == "core" else 0)
    assert report["exec_code"] == 1                       # the failing route keeps its exit code
    assert report["controller_state"] == "closed"
    assert report["studio_window_alive_at_loop_end"] is False and report["hosts_left"] == 0
    assert returncode == 0


@pytest.mark.skipif(not BUILT, reason="the native core is not built in this checkout: no release/native_module")
def test_a_studio_window_on_qt_quicks_own_device_left_alive_still_exits_cleanly(tmp_path):
    report, returncode = _run("unwired", "qt", tmp_path)
    assert report["api"] == "Vulkan" and report["hosts"] == 0
    assert report["studio_window_alive_at_loop_end"] is True
    assert returncode == 0


@pytest.mark.skipif(not BUILT, reason="the native core is not built in this checkout: no release/native_module")
def test_a_studio_window_on_the_core_left_alive_crashes_the_exit_negative_control(tmp_path):
    """Without the quit edge the window on the native core's device is alive at the loop's end and the process
    crashes at its exit: the check above proves something."""
    report, returncode = _run("unwired", "core", tmp_path)
    assert report["api"] == "Vulkan" and report["hosts"] == 1
    assert report["studio_window_alive_at_loop_end"] is True and report["hosts_left"] == 1
    assert returncode != 0
