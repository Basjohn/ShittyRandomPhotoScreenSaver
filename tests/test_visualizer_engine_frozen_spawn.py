"""Native core P2b, work order 5 slice 5.7: the engine worker's spawn reaches ``visualizer_worker_main`` on the
production entry's spawn path.

In a Nuitka build the child is the same executable started with ``--multiprocessing-fork``; Nuitka's always-on
multiprocessing plugin runs it as ``__parents_main__`` (``main.py``'s own module code plus a freeze-support call that
hands the fork arguments to ``multiprocessing.spawn.spawn_main``), so the child executes ``main.py``'s module level and
then unpickles the supervisor's ``Process`` and calls its target by name. The source-run equivalent is a spawn whose
parent ``__main__`` is ``main.py``: the child executes ``main.py``'s module level as ``__mp_main__`` and then the
target. This test drives that path in a child interpreter (no window, no device, no app started: ``main.py``'s
``__main__`` block never runs in a child) and checks the target's own message loop answers. The frozen run itself (and
its cold spawn timed against the first configure's 6 s bound, checkpoint audit 9 A9-L2) is the operator's check: no
test builds. The package is compiled in by every build family (``--include-package=core.visualizer_engine``) and the
frozen audit requires ``core.visualizer_engine.engine_worker`` (``tests/test_build_closeout_contract.py``,
``tests/test_frozen_build_audit.py``).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_DRIVER = r'''
import json, os, sys, time
repo = sys.argv[1]
sys.path.insert(0, repo)
import multiprocessing as mp

# The production parent: its __main__ is main.py (a spawned child re-executes main.py's module level first, as the
# frozen child runs it as __parents_main__).
main_module = sys.modules["__main__"]
main_module.__file__ = os.path.join(repo, "main.py")
main_module.__spec__ = None

from core.process.types import MessageType, WorkerMessage, WorkerResponse
from core.visualizer_engine.engine_worker import visualizer_worker_main

if __name__ == "__main__":
    requests, responses = mp.Queue(), mp.Queue()
    started = time.perf_counter()
    process = mp.Process(target=visualizer_worker_main, args=(requests, responses), daemon=True)
    process.start()
    ready = WorkerResponse.from_dict(responses.get(timeout=120))
    ready_s = time.perf_counter() - started
    requests.put(WorkerMessage(msg_type=MessageType.VIS_STOP, seq_no=1, correlation_id="stop", payload={}).to_dict())
    stop = WorkerResponse.from_dict(responses.get(timeout=60))
    requests.put(WorkerMessage(msg_type=MessageType.SHUTDOWN, seq_no=2, correlation_id="bye").to_dict())
    process.join(30)
    print("RESULT " + json.dumps({
        "ready": ready.msg_type.value, "ready_s": round(ready_s, 3), "pid": process.pid,
        "stop_success": stop.success, "qt_modules": stop.payload.get("qt_modules"), "exitcode": process.exitcode,
    }))
'''


def test_the_worker_factory_is_a_module_level_function_the_child_resolves_by_name():
    from multiprocessing.reduction import ForkingPickler

    from core.visualizer_engine import engine_worker

    payload = bytes(ForkingPickler.dumps(engine_worker.visualizer_worker_main))
    assert b"core.visualizer_engine.engine_worker" in payload and b"visualizer_worker_main" in payload
    assert ForkingPickler.loads(payload) is engine_worker.visualizer_worker_main


def test_a_spawn_from_the_production_entry_reaches_visualizer_worker_main(tmp_path):
    driver = tmp_path / "spawn_driver.py"
    driver.write_text(_DRIVER, encoding="utf-8")
    completed = subprocess.run([sys.executable, str(driver), str(REPO)], cwd=str(tmp_path), capture_output=True,
                               text=True, timeout=300)
    lines = [line for line in completed.stdout.splitlines() if line.startswith("RESULT ")]
    assert completed.returncode == 0 and lines, (completed.returncode, completed.stdout[-2000:],
                                                 completed.stderr[-4000:])
    result = json.loads(lines[-1][len("RESULT "):])
    print("production-entry spawn:", result)
    # The target's own loop answered: its ready signal and a control message (the VISUALIZER worker's reply).
    assert result["ready"] == "worker_ready" and result["stop_success"] is True and result["exitcode"] == 0
    # main.py's module level ran in the child before the target (the frozen ``__parents_main__`` path): it imports Qt
    # Widgets, which the worker's own imports never load (``test_visualizer_engine_import_weight.py``).
    assert "PySide6.QtWidgets" in result["qt_modules"], result["qt_modules"]
