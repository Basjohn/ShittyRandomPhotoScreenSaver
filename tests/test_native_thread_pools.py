"""numpy's OpenBLAS starts with one thread in the app and in spawned workers.

With its default pool, OpenBLAS starts one worker thread per logical CPU at
numpy import, and on Windows each thread commits a ~32 MB buffer: about 700 MB
of private commit per process on a 24-thread CPU (R-99). The pool size is
read only at library load, so these probes import ``main`` in a fresh process
(as the entry points do) and ask the loaded OpenBLAS directly.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

_PROBE = r'''
import ctypes, glob, multiprocessing, os, sys


def openblas_threads():
    import numpy
    base = os.path.dirname(numpy.__file__)
    for pattern in ("../numpy.libs/*openblas*", ".libs/*openblas*", "../numpy.libs/*.dll"):
        for path in glob.glob(os.path.join(base, pattern)):
            try:
                lib = ctypes.CDLL(path)
            except OSError:
                continue
            for name in ("openblas_get_num_threads64_", "openblas_get_num_threads"):
                fn = getattr(lib, name, None)
                if fn is not None:
                    return int(fn())
    return None


def child(queue):
    queue.put(openblas_threads())


if __name__ == "__main__":
    sys.path.insert(0, os.getcwd())
    import main  # noqa: F401  - the entry point sizes the pool before numpy loads
    print("PARENT", openblas_threads(), flush=True)
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    process = context.Process(target=child, args=(queue,))
    process.start()
    print("CHILD", queue.get(timeout=60), flush=True)
    process.join(30)
'''


def test_openblas_runs_single_threaded_in_the_app_and_its_spawned_workers(tmp_path) -> None:
    probe = tmp_path / "blas_probe.py"
    probe.write_text(_PROBE)
    env = {key: value for key, value in os.environ.items() if key != "OPENBLAS_NUM_THREADS"}
    completed = subprocess.run(
        [sys.executable, str(probe)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    out = completed.stdout + completed.stderr
    assert "PARENT 1" in completed.stdout, out
    assert "CHILD 1" in completed.stdout, out


import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Qt's private image pool is resolved through MSVC exports")
def test_qt_image_pool_keeps_its_threads_instead_of_recreating_them(qt_app):
    """R-97: Qt's private image pool must not recreate threads for every image.

    With the default 30 s idle expiry and a 40 s rotation, each wallpaper made
    the pool start its threads again; the NVIDIA GL driver keeps ~70 KB per
    thread ever created. The probe shortens the expiry to show the churn, then
    applies the production setting and shows the same threads are reused.
    """
    import ctypes

    import psutil
    from PySide6.QtCore import QEventLoop, Qt, QTimer
    from PySide6.QtGui import QImage

    from core.native_threads import (
        _qt_gui_pool_expiry_functions,
        qt_gui_pool_expiry_ms,
        retain_qt_gui_pool_threads,
    )

    resolved = _qt_gui_pool_expiry_functions()
    assert resolved is not None, "Qt6Gui no longer exports qtGuiThreadPool; R-97 fix is inert"
    pool, _get_expiry, set_expiry = resolved
    source = QImage(4096, 2400, QImage.Format.Format_RGB32)
    source.fill(0x336699)

    def burst() -> None:
        source.scaled(3000, 1700, Qt.AspectRatioMode.IgnoreAspectRatio,
                      Qt.TransformationMode.SmoothTransformation)

    def idle(ms: int) -> None:
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    def thread_ids() -> set[int]:
        return {t.id for t in psutil.Process().threads()}

    # Short expiry: threads created for one image are gone before the next.
    set_expiry(pool, 100)
    burst()
    idle(600)
    before = thread_ids()
    burst()
    churned = thread_ids() - before
    assert churned, "the probe no longer exercises Qt's multithreaded scaling"

    # Production setting: the threads persist and the next image reuses them.
    assert retain_qt_gui_pool_threads() is True
    assert qt_gui_pool_expiry_ms() == -1
    burst()
    idle(600)
    before = thread_ids()
    burst()
    assert thread_ids() - before == set()
