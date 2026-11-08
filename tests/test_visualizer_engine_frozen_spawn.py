"""Native core P2b, work order 5 slice 5.7: the engine worker's spawn reaches ``visualizer_worker_main`` on the
production entry's spawn path; checkpoint audit 10 (A10-M1): and that spawn, like every worker role's, no longer loads
the application's GUI stack first.

In a Nuitka build the child is the same executable started with ``--multiprocessing-fork``; Nuitka's always-on
multiprocessing plugin runs it as ``__parents_main__`` (``main.py``'s own module code plus a freeze-support call that
hands the fork arguments to ``multiprocessing.spawn.spawn_main``), so the child executes ``main.py``'s module level and
then unpickles the supervisor's ``Process`` and calls its target by name. The source-run equivalent is a spawn whose
parent ``__main__`` is ``main.py``: the child executes ``main.py``'s module level as ``__mp_main__`` and then the
target. These tests drive that path in a child interpreter (no window, no device, no app started: ``main.py``'s
``__main__`` block never runs in a child) and check the target's own message loop answers, and what the child loaded.

Until A10-M1 that module level imported the Qt GUI, Quick and Widgets stack, the engine and Settings in every worker
(measured 8 Nov from a ``main.py`` parent: 1.6 s to ready, 112 MB RSS, 83 MB USS per worker, against 0.3 s / 31 MB /
18 MB for the target alone); ``main.py`` (and ``main_mc.py``) now skip their application imports in a worker
(``core.spawn_child``). The frozen run itself (and its cold spawn timed against the first configure's 6 s bound,
checkpoint audit 9 A9-L2) is the operator's check: no test builds. The package is compiled in by every build family
(``--include-package=core.visualizer_engine``) and the frozen audit requires ``core.visualizer_engine.engine_worker``
(``tests/test_build_closeout_contract.py``, ``tests/test_frozen_build_audit.py``).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: What a worker must never load before its target: the GUI stack the application's own process uses.
GUI_STACK = ("PySide6.QtGui", "PySide6.QtWidgets", "PySide6.QtQuick", "PySide6.QtQml")
GUI_DLLS = ("qt6gui.dll", "qt6widgets.dll", "qt6quick.dll", "qt6qml.dll")

_DRIVER = r'''
import json, os, sys, time
repo, entry, target = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, repo)
import multiprocessing as mp

# The production parent: its __main__ is main.py (or the MC build's main_mc.py). A spawned child re-executes that
# module level first, as the frozen child runs it as __parents_main__.
main_module = sys.modules["__main__"]
main_module.__file__ = os.path.join(repo, entry)
main_module.__spec__ = None

from core.process.types import MessageType, WorkerMessage, WorkerResponse
if target == "engine":
    from core.visualizer_engine.engine_worker import visualizer_worker_main as factory
else:
    from core.process.workers.image_worker import image_worker_main as factory


def mapped_qt_dlls(pid):
    import psutil

    return sorted({os.path.basename(m.path).lower() for m in psutil.Process(pid).memory_maps(grouped=True)
                   if os.path.basename(m.path).lower().startswith("qt6")})


if __name__ == "__main__":
    requests, responses = mp.Queue(), mp.Queue()
    started = time.perf_counter()
    process = mp.Process(target=factory, args=(requests, responses), daemon=True)
    process.start()
    ready = WorkerResponse.from_dict(responses.get(timeout=120))
    ready_s = time.perf_counter() - started
    result = {"ready": ready.msg_type.value, "ready_s": round(ready_s, 3), "pid": process.pid,
              "qt_dlls": mapped_qt_dlls(process.pid)}
    seq = 1
    if target == "engine":
        requests.put(WorkerMessage(msg_type=MessageType.VIS_STOP, seq_no=seq, correlation_id="stop",
                                   payload={}).to_dict())
        seq += 1
        stop = WorkerResponse.from_dict(responses.get(timeout=60))
        result.update(stop_success=stop.success, qt_modules=stop.payload.get("qt_modules"))
    requests.put(WorkerMessage(msg_type=MessageType.SHUTDOWN, seq_no=seq, correlation_id="bye").to_dict())
    process.join(30)
    result["exitcode"] = process.exitcode
    print("RESULT " + json.dumps(result))
'''


def _spawn(tmp_path, entry: str, target: str) -> dict:
    driver = tmp_path / "spawn_driver.py"
    driver.write_text(_DRIVER, encoding="utf-8")
    completed = subprocess.run([sys.executable, str(driver), str(REPO), entry, target], cwd=str(tmp_path),
                               capture_output=True, text=True, timeout=300)
    lines = [line for line in completed.stdout.splitlines() if line.startswith("RESULT ")]
    assert completed.returncode == 0 and lines, (completed.returncode, completed.stdout[-2000:],
                                                 completed.stderr[-4000:])
    return json.loads(lines[-1][len("RESULT "):])


def test_the_worker_factory_is_a_module_level_function_the_child_resolves_by_name():
    from multiprocessing.reduction import ForkingPickler

    from core.visualizer_engine import engine_worker

    payload = bytes(ForkingPickler.dumps(engine_worker.visualizer_worker_main))
    assert b"core.visualizer_engine.engine_worker" in payload and b"visualizer_worker_main" in payload
    assert ForkingPickler.loads(payload) is engine_worker.visualizer_worker_main


def test_a_spawn_from_the_production_entry_reaches_visualizer_worker_main_without_the_gui_stack(tmp_path):
    result = _spawn(tmp_path, "main.py", "engine")
    print("production-entry spawn:", result)
    # The target's own loop answered: its ready signal and a control message (the VISUALIZER worker's reply).
    assert result["ready"] == "worker_ready" and result["stop_success"] is True and result["exitcode"] == 0
    # A10-M1: main.py's module level ran in the child before the target and loaded none of the application's GUI
    # stack (before the fix: QtGui, QtWidgets, QtQuick, QtQml, QtNetwork and QtOpenGL, here and in every image worker).
    assert not set(GUI_STACK) & set(result["qt_modules"]), result["qt_modules"]
    assert not set(GUI_DLLS) & set(result["qt_dlls"]), result["qt_dlls"]


@pytest.mark.parametrize("entry", ("main.py", "main_mc.py"))
def test_an_image_worker_spawned_from_a_production_entry_loads_no_qt_gui_stack(tmp_path, entry):
    # Every worker role runs the parent's main module first: the image workers (which predate 5.7) carried the same
    # ~65 MB for the whole run. The MC build's entry imports main.py from its own module level.
    result = _spawn(tmp_path, entry, "image")
    print(f"{entry} image-worker spawn:", result)
    assert result["ready"] == "worker_ready" and result["exitcode"] == 0
    assert not set(GUI_DLLS) & set(result["qt_dlls"]), result["qt_dlls"]


_FROZEN_CHILD = r'''
import json, runpy, sys
repo, entry, run_name = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, repo)
# What Nuitka's multiprocessing plugin does in a frozen child: the root module's code runs as __parents_main__ before
# the fork arguments reach multiprocessing.spawn.spawn_main. Another run name stands for an ordinary import.
namespace = runpy.run_path(repo + "/" + entry, run_name=run_name)
print("RESULT " + json.dumps({
    "gui": sorted(name for name in sys.modules if name.startswith("PySide6.Qt")),
    "engine": "engine.screensaver_engine" in sys.modules,
    "settings": "core.settings.settings_manager" in sys.modules,
    "main_defined": "main" in namespace or "core_main" in namespace,
}))
'''


@pytest.mark.parametrize("entry", ("main.py", "main_mc.py"))
@pytest.mark.parametrize("run_name", ("__parents_main__", "srpss_entry_import"))
def test_a_frozen_child_runs_the_entry_module_without_the_application_imports(tmp_path, entry, run_name):
    # The frozen path, without a build: the entry module executed as ``__parents_main__`` (directly, or main.py
    # imported from the MC entry while ``__parents_main__`` is being imported) defines its functions but imports no
    # Qt, engine or Settings. Control: the same module under any other name (the parent, a test, a tool) imports
    # all of it, exactly as before.
    script = tmp_path / "frozen_child.py"
    script.write_text(_FROZEN_CHILD, encoding="utf-8")
    completed = subprocess.run([sys.executable, str(script), str(REPO), entry, run_name], cwd=str(tmp_path),
                               capture_output=True, text=True, timeout=300)
    lines = [line for line in completed.stdout.splitlines() if line.startswith("RESULT ")]
    assert completed.returncode == 0 and lines, (completed.stdout[-2000:], completed.stderr[-4000:])
    result = json.loads(lines[-1][len("RESULT "):])
    assert result["main_defined"]
    if run_name == "__parents_main__":
        assert result == {"gui": [], "engine": False, "settings": False, "main_defined": True}, result
    else:
        assert set(GUI_STACK) <= set(result["gui"]) and result["engine"] and result["settings"], result
