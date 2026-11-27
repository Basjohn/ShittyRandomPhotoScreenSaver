"""The hitch rows under a game (Current_Plan.md N5.2f, 22 Nov): the next transition is warmed gradually, one bounded
GUI-thread unit per spaced, already-rendered frame, so its first run pays no module import or shader text build.

- A run's first start and first frames on the native background import nothing once the product's warm-up has run
  (a fresh interpreter each: imports are process-wide). Controls run here: with no warm-up, and with the module's
  import alone (the warm-up before this fix), the first run still imports.
- The idle owner's edge imports nothing itself; the item runs one unit only when the window has rendered a frame (the
  queued ``afterRendering``), never on its own, and tells the owner whether more is left.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

CHILD = Path(__file__).with_name("transition_warm_first_run_child.py")
#: A scene transition (N5.2f's population) and a fragment one: both routes of the layer.
TRANSITIONS = ("disintegrate", "burn")


def _first_run(transition_id: str, warm: str) -> dict:
    done = subprocess.run([sys.executable, str(CHILD), transition_id, warm], capture_output=True, text=True,
                          timeout=300, cwd=str(CHILD.parents[1]))
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("transition_id", TRANSITIONS)
def test_after_the_warm_up_a_first_run_imports_nothing(transition_id):
    warmed = _first_run(transition_id, "product")
    assert warmed["drawn"] and warmed["units"] >= 2
    assert warmed["imported"] == []


@pytest.mark.parametrize("transition_id", TRANSITIONS)
def test_without_the_warm_up_the_first_run_pays_the_import(transition_id):
    """The control: the same first run with nothing warmed imports the transition's renderer module there."""
    cold = _first_run(transition_id, "none")
    assert cold["drawn"]
    assert f"rendering.quick.transitions.implementations.{transition_id}" in cold["imported"]


def test_the_module_import_alone_leaves_the_scene_frames_imports():
    """The control: the warm-up before this fix (the module's import only) leaves the first scene frame's imports."""
    old = _first_run("disintegrate", "product_without_layer_units")
    assert old["drawn"] and old["units"] == 1
    assert old["imported"]
    assert not any(name.endswith(".disintegrate") for name in old["imported"])


class _Reporter:
    def __init__(self) -> None:
        from PySide6.QtCore import QObject, Signal

        class _R(QObject):
            finished = Signal(int, bool)

        self.qobject = _R()
        self.seen: list[tuple[int, bool]] = []
        self.qobject.finished.connect(lambda ticket, done: self.seen.append((ticket, done)))


def test_one_unit_runs_only_after_a_rendered_frame_and_reports(qt_app, monkeypatch):
    from PySide6.QtCore import QCoreApplication, QObject, Signal

    from rendering.quick.render.background_item import BackgroundRenderItem
    from rendering.quick.transitions import implementation_registry as registry

    ran: list[str] = []
    loaded = {"value": False}
    monkeypatch.setattr(registry, "quick_transition_implementation_loaded", lambda _tid: loaded["value"])
    monkeypatch.setattr(registry, "preload_quick_transition_implementation",
                        lambda tid: (ran.append(tid), loaded.__setitem__("value", True)))

    class _Window(QObject):
        afterRendering = Signal()

        def isExposed(self) -> bool:  # noqa: N802
            return True

    window = _Window()
    item = BackgroundRenderItem()
    monkeypatch.setattr(item, "window", lambda: window)
    item._renderers_on_backend = False                    # the native background's backend
    reporter = _Reporter()
    assert item.schedule_warm_step("crumble", {}, reporter.qobject, 7) is True
    QCoreApplication.processEvents()
    assert ran == [] and reporter.seen == []              # nothing until the window renders a frame
    window.afterRendering.emit()
    QCoreApplication.processEvents()
    assert ran == ["crumble"] and reporter.seen == [(7, True)]
    window.afterRendering.emit()                          # one unit per armed step: a later frame runs nothing
    QCoreApplication.processEvents()
    assert ran == ["crumble"] and reporter.seen == [(7, True)]
    # Nothing left: no step is armed; a cancelled step runs nothing.
    assert item.schedule_warm_step("crumble", {}, reporter.qobject, 8) is False
    loaded["value"] = False
    assert item.schedule_warm_step("crumble", {}, reporter.qobject, 9) is True
    item.cancel_warm_up()
    window.afterRendering.emit()
    QCoreApplication.processEvents()
    assert ran == ["crumble"] and reporter.seen == [(7, True)]
