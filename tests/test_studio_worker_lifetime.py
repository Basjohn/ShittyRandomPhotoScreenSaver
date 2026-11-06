"""Studio clip workers fail fast and never outlive what started them (``ui/studio/worker_lifetime.py``).

Proven on the real ``ClipLoadJob`` and the real worker modules, with the same interpreter (a venv's ``python.exe``
is a launcher that starts the real interpreter suspended): a missing or unreadable clip makes every worker exit
non-zero within a bound; a cancel right after start leaves no process (the orphaned, suspended interpreters seen
5-6 Nov); a parent that dies abruptly takes its worker with it; and the Studio test modules leave no worker behind
(``tests/conftest.py``). Each with a negative control. Nothing shows a window.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from tests.studio_worker_probe import kill_all, surviving_workers, wait_gone

ROOT = Path(__file__).resolve().parents[1]
BOUND_S = 90.0                     # a worker must have failed by then (they fail in a few seconds)


def _worker_modules() -> list[str]:
    """Every Studio clip worker: the modules ``run_frozen_worker`` admits (``ui.studio.*_recorded_inputs``)."""
    return sorted(f"ui.studio.{path.stem}" for path in (ROOT / "ui" / "studio").glob("*_recorded_inputs.py"))


def _run_bounded(commands: dict, bound: float) -> dict:
    """Start every command at once; (return code or None when still running at ``bound``, output tail) each."""
    started = {key: subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
               for key, cmd in commands.items()}
    deadline = time.monotonic() + bound
    results = {}
    for key, process in started.items():
        try:
            out, _ = process.communicate(timeout=max(0.1, deadline - time.monotonic()))
            results[key] = (process.returncode, out.decode("utf-8", "replace").strip().splitlines()[-1:])
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            results[key] = (None, ["still running at the bound"])
    return results


def test_every_worker_fails_fast_on_a_missing_or_unreadable_clip(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text("{}", encoding="utf-8")
    garbage = tmp_path / "garbage.srclip"
    garbage.write_bytes(b"not a clip" * 64)
    commands = {}
    modules = _worker_modules()
    assert {"ui.studio.waveform_recorded_inputs", "ui.studio.spectrum_recorded_inputs",
            "ui.studio.extruded_spectrum_recorded_inputs", "ui.studio.shockwave_grid_recorded_inputs"} <= set(modules)
    for module in modules:
        for kind, clip in (("missing", tmp_path / "no_such_clip.srclip"), ("unreadable", garbage)):
            commands[(module, kind)] = [sys.executable, "-m", module, str(clip), str(settings),
                                        str(tmp_path / f"{module}.{kind}.json"), "30.0"]
    results = _run_bounded(commands, BOUND_S)
    for key, (code, tail) in results.items():
        assert code not in (None, 0), (key, code, tail)              # failed, promptly, as an error
        assert tail and tail[0].strip(), key                         # the job has a message to show
        assert not (tmp_path / f"{key[0]}.{key[1]}.json").exists(), key


def test_the_bound_check_catches_a_worker_that_never_ends_negative_control(tmp_path):
    output = tmp_path / "probe.json"
    results = _run_bounded({"probe": [sys.executable, "-m", "tests.studio_worker_probe", "clip", "settings",
                                      str(output), "30.0"]}, 3.0)
    assert results["probe"][0] is None


# --------------------------------------------------------------------------------------- cancel and parent death
def _fresh_tag() -> str:
    from ui.studio.waveform_recorded_inputs import worker_tag
    return worker_tag()


@pytest.fixture
def no_leftovers():
    """After the test: nothing carrying this process's worker tag survives (killed for hygiene either way)."""
    tag = _fresh_tag()
    yield tag
    kill_all(surviving_workers(tag))


# Cancel delays after start (s): they sweep the window in which a venv launcher has created the real interpreter
# suspended and not yet resumed it (where a cancel that killed only the launcher orphaned it).
CANCEL_DELAYS = (0.0, 0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.2)


def _cancel_soon_after_start(qt_app, delay: float) -> None:
    from PySide6.QtCore import QCoreApplication
    from ui.studio.adapter import RECORDED, StudioFixture
    from ui.studio.waveform_recorded_inputs import ClipLoadJob
    clip = StudioFixture("clip:missing", "Missing", RECORDED, 1.0, str(ROOT / "no_such_clip.srclip"))
    job = ClipLoadJob(clip, {}, lambda *_a: None, module="ui.studio.spectrum_recorded_inputs")
    time.sleep(delay)
    job.cancel()                                   # as the retry test's release did
    for _ in range(20):
        QCoreApplication.processEvents()


def test_a_cancel_soon_after_start_leaves_no_process(qt_app, no_leftovers):
    for delay in CANCEL_DELAYS:
        _cancel_soon_after_start(qt_app, delay)
    assert wait_gone(no_leftovers, 15.0) == []


def test_without_the_job_tree_the_cancelled_launchers_child_is_orphaned_negative_control(
        qt_app, no_leftovers, monkeypatch):
    """The 5-6 Nov defect: killing only the venv launcher leaves the interpreter it started suspended."""
    from ui.studio import worker_lifetime
    if sys.platform != "win32":
        pytest.skip("the venv launcher and its suspended child are Windows-only")
    import psutil
    if Path(psutil.Process().exe()).resolve() == Path(sys.executable).resolve():
        pytest.skip("this interpreter is not started through a venv launcher")
    monkeypatch.setattr(worker_lifetime.WorkerTree, "adopt", lambda self, pid: False)
    for delay in CANCEL_DELAYS:
        _cancel_soon_after_start(qt_app, delay)
    time.sleep(3.0)                                # every un-suspended worker has failed on the missing clip by now
    left = surviving_workers(no_leftovers)
    assert left, "an unbound cancel inside the launcher's setup window should orphan its child"
    assert all(p.status() == psutil.STATUS_STOPPED for p in left)       # suspended, as found in the field


def _orphan_after_parent_death(tmp_path, *flags) -> tuple[str, list]:
    ready, log = tmp_path / "ready.txt", tmp_path / "parent.log"
    with log.open("wb") as sink:            # a file, not a pipe: a surviving worker would hold a pipe open
        done = subprocess.run([sys.executable, "-m", "tests.studio_worker_probe", "parent", str(ready), *flags],
                              cwd=ROOT, stdout=sink, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=180)
    assert done.returncode == 0, log.read_text(encoding="utf-8", errors="replace")[-2000:]
    tag, state = ready.read_text(encoding="utf-8").splitlines()
    assert state == "ready"                                          # the worker was running when the parent died
    return tag, wait_gone(tag, 15.0)


def _remove_folders(tag: str) -> None:
    for folder in Path(tempfile.gettempdir()).glob(tag + "*"):
        shutil.rmtree(folder, ignore_errors=True)


def test_a_worker_dies_with_its_parent(tmp_path):
    tag, left = _orphan_after_parent_death(tmp_path)
    try:
        assert left == []
    finally:
        kill_all(left)
        _remove_folders(tag)


def test_without_the_binding_a_worker_outlives_its_parent_negative_control(tmp_path):
    tag, left = _orphan_after_parent_death(tmp_path, "unbound")
    try:
        if sys.platform != "win32":
            pytest.skip("the unbound control disables the Windows job; Linux arms the death signal in the worker")
        assert left, "an unbound worker should survive its parent"
    finally:
        kill_all(left)
        _remove_folders(tag)


# --------------------------------------------------------------------------------------- the conftest guard
def test_the_module_guard_reports_a_surviving_worker_negative_control(qt_app, no_leftovers):
    """The check ``tests/conftest.py`` runs after every module that started a worker sees a live one."""
    from PySide6.QtCore import QCoreApplication
    from ui.studio.adapter import RECORDED, StudioFixture
    from ui.studio.waveform_recorded_inputs import ClipLoadJob
    clip = StudioFixture("clip:probe", "Probe", RECORDED, 1.0, "probe")
    job = ClipLoadJob(clip, {}, lambda *_a: None, module="tests.studio_worker_probe")
    marker = Path(job._output_path.as_posix() + ".ready")
    deadline = time.monotonic() + 120
    while not marker.exists() and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.05)
    assert surviving_workers(no_leftovers)
    job.cancel()
    assert wait_gone(no_leftovers, 15.0) == []                        # and a cancel ends it
