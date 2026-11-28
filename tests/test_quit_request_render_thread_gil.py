"""Quitting never makes Python wait on a Quick render thread that needs the GIL (``request_application_quit``).

``QCoreApplication.quit()`` called from Python on the GUI thread sends ``QEvent::Quit`` synchronously, and
QGuiApplication closes every open window in that call with the GIL held. A render thread running Python at that moment
(``updatePaintNode``, a direct render-phase slot) then cannot finish the render stop the close waits for, and the
process wedges (the 2026-09-25 Linux/Xvfb threaded-GL run: 3 of 3). ``request_application_quit`` queues the native
``quit()`` slot instead.

N5.2h retarget: the Python retained background node this probe once rendered is deleted, and no probe window is shown.
The probe's Python runs on a render thread through the process's kept hidden host (``bootstrap.native_hidden_host``:
the core's render control on its own render thread), on each API: an item whose ``updatePaintNode`` is Python paints
frames, then the quit is requested. The quit edge closes the hidden host (its render thread stops) and the process must
exit. ``painted_off_main`` proves the Python ran on the render thread, not the GUI thread.

Needs the built module (``release/native_module``); skips without it.
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
BUILT = os.name == "nt" and (ROOT / "release" / "native_module" / f"{loader.MODULE_NAME}.pyd").is_file()

_PROBE = r'''
import json
import sys
import threading
from pathlib import Path

from rendering.quick import bootstrap

API, state_dir = sys.argv[1], Path(sys.argv[2])
bootstrap.configure_quick_graphics(reason="quit-render-thread-gil-probe", backend=API, start_state_dir=state_dir)
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtQuick import QQuickItem, QSGSimpleRectNode
from engine.runtime_destruction import request_application_quit

app = QGuiApplication(sys.argv[:1])
bootstrap.start_quick_backend()
main_thread = threading.get_ident()
report = {"api": API}


class PythonPaintedItem(QQuickItem):
    """Python on the render thread at every frame's sync (its updatePaintNode)."""

    def __init__(self):
        super().__init__()
        self.setFlag(QQuickItem.Flag.ItemHasContents, True)
        self.painted = 0
        self.threads = set()

    def updatePaintNode(self, node, _data):
        self.threads.add(threading.get_ident())
        if node is None:
            node = QSGSimpleRectNode()
        node.setRect(self.boundingRect())
        node.setColor(QColor(20 + self.painted % 200, 60, 120))
        self.painted += 1
        return node


host = bootstrap.native_hidden_host(64, 48)
item = PythonPaintedItem()
host.set_content(item)
report["hidden_api"] = host.state().get("graphics_api")


def paint():
    item.update()
    host.frames(1)
    if item.painted < 20:
        QTimer.singleShot(0, paint)
        return
    report["painted"] = item.painted
    report["painted_off_main"] = bool(item.threads) and main_thread not in item.threads
    report["requested"] = request_application_quit("probe")
    print("REPORT " + json.dumps(report), flush=True)


QTimer.singleShot(0, paint)
app.exec()
print("EXITED", flush=True)
'''


@pytest.mark.skipif(not BUILT, reason="the native core is not built in this checkout: no release/native_module")
@pytest.mark.parametrize("api", ["opengl", "vulkan"])
def test_requested_quit_exits_while_the_render_thread_runs_python(api, tmp_path) -> None:
    env = os.environ.copy()
    env.pop("QT_QPA_PLATFORM", None)        # Qt's own platform: the offscreen one has no Vulkan; nothing is shown
    for attempt in range(3):
        completed = subprocess.run([sys.executable, "-c", _PROBE, api, str(tmp_path / str(attempt))], cwd=ROOT,
                                   env=env, text=True, capture_output=True, timeout=45, check=False)
        lines = [line for line in completed.stdout.splitlines() if line.startswith("REPORT ")]
        assert lines, completed.stdout + completed.stderr
        report = json.loads(lines[-1][len("REPORT "):])
        assert report["hidden_api"] == api and report["requested"] is True
        assert report["painted"] >= 20 and report["painted_off_main"] is True
        assert "EXITED" in completed.stdout and completed.returncode == 0, (attempt, completed.stdout + completed.stderr)
