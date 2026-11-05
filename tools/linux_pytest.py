"""Run pytest on Linux under Xvfb with the production OpenGL 4.6 Core floor available.

Linux only, development only. Qt Quick/OpenGL tests need a display and a 4.6
Core context; this wrapper starts a private Xvfb display and gives only the
pytest child the Mesa llvmpipe 4.6 override (``tools/linux_headless.py``).
Profile isolation stays with ``tests/conftest.py``. Arguments are passed to
pytest unchanged::

    python tools/linux_pytest.py -q tests/test_platform_paths.py
    python tools/linux_pytest.py --display :95 -- -q -k quick tests/test_quick_bootstrap.py
    python tools/linux_pytest.py --chunked --isolated --jobs 3     # the whole-suite gate (tests/run_chunked.py)

Software rendering: results prove correctness, never performance.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import linux_headless as lh  # noqa: E402


def main(argv: list[str]) -> int:
    lh.require_linux()
    display = ":96"
    if argv[:1] == ["--display"]:
        display, argv = argv[1], argv[2:]
    chunked = argv[:1] == ["--chunked"]
    if chunked:
        argv = argv[1:]
    if argv[:1] == ["--"]:
        argv = argv[1:]
    env = {**os.environ, "DISPLAY": display, **lh.MESA_GL46_OVERRIDE}
    env.pop("QT_QPA_PLATFORM", None)
    xvfb = lh.start_xvfb(display)
    try:
        command = ([sys.executable, str(lh.REPO / "tests" / "run_chunked.py"), *argv] if chunked
                   else [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *argv])
        return subprocess.call(command, cwd=lh.REPO, env=env)
    finally:
        xvfb.terminate()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
