"""R-90 on the real Windows endpoint: rebinding and retiring never double-release.

The fake-COM tests prove the probe asks for ``QueryInterface``; this proves the
real COM objects survive the default-output-device path (``rebind``) and
retirement followed by garbage collection -- where the old ``ctypes.cast``
endpoint crashed with an access violation. It runs in a subprocess so a native
fault fails the test instead of the test run.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Core Audio is Windows-only")

_REPO = Path(__file__).resolve().parents[1]

_SCRIPT = textwrap.dedent(
    """
    import gc, sys
    sys.path.insert(0, {repo!r})
    {patch}
    from core.media.core_audio_callback_probe import CoreAudioCallbackProbe

    probe = CoreAudioCallbackProbe(on_volume=lambda *_: None, on_default_device=lambda: None)
    if not probe.start():
        print("NO_ENDPOINT")
        sys.exit(0)
    for _ in range(25):          # the default-output-device switch path
        assert probe.rebind()
        gc.collect()
    probe.stop()
    del probe
    for _ in range(3):
        gc.collect()
    print("OK")
    """
)


def _run(patch: str = "") -> subprocess.CompletedProcess:
    script = _SCRIPT.format(repo=str(_REPO), patch=patch)
    return subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=120)


def test_real_endpoint_rebind_and_retirement_survive_garbage_collection() -> None:
    pytest.importorskip("pycaw")
    result = _run()
    if "NO_ENDPOINT" in result.stdout:
        pytest.skip("no default audio endpoint on this machine")
    assert result.returncode == 0 and "OK" in result.stdout, (result.returncode, result.stderr[-2000:])
