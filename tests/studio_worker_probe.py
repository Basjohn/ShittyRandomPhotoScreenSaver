"""Test-only helpers for Studio clip-worker lifetime (``tests/test_studio_worker_lifetime.py``, ``tests/conftest.py``).

* ``python -m tests.studio_worker_probe clip settings output seconds``: a stand-in worker launched by the real
  ``ClipLoadJob`` (same command shape, same interpreter, same launcher). It arms ``die_with_parent`` like every Studio
  worker, writes ``<output>.ready`` and then waits far longer than any test: it only ends by being killed.
* ``python -m tests.studio_worker_probe parent <ready-file> [unbound]``: a parent process that starts one such worker
  through ``ClipLoadJob``, waits until it runs, prints its tag and then dies abruptly (``os._exit``, as on a crash: no
  cancel, no cleanup). ``unbound`` disables the job tree (the negative control).
* ``surviving_workers(tag)``: live processes whose command line carries a worker tag (``worker_tag``).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def surviving_workers(tag: str) -> list:
    """Live processes (psutil) whose command line carries ``tag``; this helper's own process excluded."""
    import psutil
    out = []
    for process in psutil.process_iter(["pid", "cmdline"]):
        try:
            line = " ".join(process.info["cmdline"] or ())
        except (psutil.Error, TypeError):
            continue
        if tag in line and process.pid != os.getpid():
            out.append(process)
    return out


def wait_gone(tag: str, seconds: float) -> list:
    """Wait (bounded) for every worker carrying ``tag`` to end; returns the ones still alive."""
    deadline = time.monotonic() + seconds
    while True:
        left = surviving_workers(tag)
        if not left or time.monotonic() > deadline:
            return left
        time.sleep(0.2)


def kill_all(processes) -> None:
    import psutil
    for process in processes:
        try:
            process.resume()                         # a suspended interpreter must run to die cleanly
        except psutil.Error:
            pass
        try:
            process.kill()
        except psutil.Error:
            pass


def _worker(argv: list[str]) -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from ui.studio.worker_lifetime import die_with_parent
    die_with_parent()
    _clip, _settings, output, *_rest = argv
    Path(output + ".ready").write_text(str(os.getpid()), encoding="utf-8")
    time.sleep(600)
    return 0


def _parent(argv: list[str]) -> int:
    ready, *flags = argv
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from PySide6.QtCore import QCoreApplication
    app = QCoreApplication.instance() or QCoreApplication([])
    from ui.studio import worker_lifetime
    from ui.studio.adapter import RECORDED, StudioFixture
    from ui.studio.waveform_recorded_inputs import ClipLoadJob, worker_tag
    if "unbound" in flags:
        worker_lifetime.WorkerTree.adopt = lambda self, pid: False
    clip = StudioFixture("clip:probe", "Probe", RECORDED, 1.0, "probe")
    job = ClipLoadJob(clip, {}, lambda *_a: None, module="tests.studio_worker_probe")
    marker = Path(job._output_path.as_posix() + ".ready")
    deadline = time.monotonic() + 120
    while not marker.exists() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.05)
    Path(ready).write_text(worker_tag() + "\n" + ("ready" if marker.exists() else "timeout"), encoding="utf-8")
    os._exit(0)                                       # an abrupt death: no cancel, no handle cleanup by Python


if __name__ == "__main__":
    args = sys.argv[1:]
    raise SystemExit(_parent(args[1:]) if args and args[0] == "parent" else _worker(args))
