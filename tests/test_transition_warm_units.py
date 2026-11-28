"""The hitch rows under a game (Current_Plan.md N5.2f, 22 Nov): the next transition is warmed gradually, one bounded
GUI-thread unit per spaced, already-rendered frame, so its first run pays no module import or shader text build.

- A run's first start and first frames on the native background import and build nothing once the product's warm-up
  has run (a fresh interpreter each: imports are process-wide). Controls run here: with no warm-up, and with the
  module's import alone (the warm-up before this fix), the first run still imports or builds.
- Each unit is bounded: the renderer module's import builds no shader text (its texts are pieces built on first use),
  and every later unit builds at most one piece and imports at most one module.
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
#: The two N5.2f scenes (their texts split into pieces) and a fragment transition: both routes of the layer.
TRANSITIONS = ("disintegrate", "volumetric_dissolve", "burn")
SPLIT = ("disintegrate", "volumetric_dissolve")


def _first_run(transition_id: str, warm: str) -> dict:
    done = subprocess.run([sys.executable, str(CHILD), transition_id, warm], capture_output=True, text=True,
                          timeout=300, cwd=str(CHILD.parents[1]))
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("transition_id", TRANSITIONS)
def test_after_the_warm_up_a_first_run_imports_and_builds_nothing(transition_id):
    warmed = _first_run(transition_id, "product")
    assert warmed["drawn"] and len(warmed["units"]) >= 2
    assert warmed["imported"] == [] and warmed["built"] == 0


@pytest.mark.parametrize("transition_id", TRANSITIONS)
def test_without_the_warm_up_the_first_run_pays_the_import(transition_id):
    """The control: the same first run with nothing warmed imports the transition's renderer module there."""
    cold = _first_run(transition_id, "none")
    assert cold["drawn"]
    assert f"rendering.quick.transitions.implementations.{transition_id}" in cold["imported"]


@pytest.mark.parametrize("transition_id", SPLIT)
def test_the_module_import_alone_leaves_the_texts_and_scene_imports_to_the_run(transition_id):
    """The control: the warm-up before this fix (the module's import only) leaves the first run building texts or
    importing the scene frame's modules."""
    old = _first_run(transition_id, "import")
    assert old["drawn"] and len(old["units"]) == 1
    assert old["built"] or old["imported"]


@pytest.mark.parametrize("transition_id", SPLIT)
def test_each_unit_builds_at_most_one_piece(transition_id):
    """The module's import builds no shader text; each later unit builds one piece at most (a text conversion and its
    block merge) and imports at most one module of its own."""
    units = _first_run(transition_id, "product")["units"]
    module = f"rendering.quick.transitions.implementations.{transition_id}"
    importing = [unit for unit in units if module in unit["imported"]]
    assert len(importing) == 1 and importing[0]["builds"] == 0
    for unit in units:
        assert unit["builds"] <= 3, units                 # one text: its conversion and block merges
        if unit is not importing[0]:
            assert len([name for name in unit["imported"] if name.startswith("rendering.")]) <= 1, units


def _unused_shared(*names: str) -> dict:
    child = CHILD.with_name("transition_warm_shared_child.py")
    done = subprocess.run([sys.executable, str(child), *names], capture_output=True, text=True, timeout=300,
                          cwd=str(CHILD.parents[1]))
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_every_shared_warm_module_is_one_a_renderer_module_imports():
    """Fix 7 (the audit's low): a shared unit is a module some renderer module (or its resolve) imports, so the warm-up never
    spends a unit on a module no run needs from a renderer (the deleted Python GL route's leftovers). Each entry is
    checked in a fresh interpreter after the native layer's own module."""
    result = _unused_shared()
    assert result["renderers"] > 0 and result["unused"] == []


def test_the_shared_warm_module_check_names_a_module_no_renderer_imports():
    """The control: a module only the native layer's run imports (its photo environment) is reported unused."""
    assert _unused_shared("rendering.quick.scene3d.environment")["unused"] == ["rendering.quick.scene3d.environment"]


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
    left = {"value": True}

    def next_unit(tid):
        if not left["value"]:
            return None
        return lambda: (ran.append(tid), left.__setitem__("value", False))

    monkeypatch.setattr(registry, "next_quick_transition_warm_unit", next_unit)

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
    left["value"] = True
    assert item.schedule_warm_step("crumble", {}, reporter.qobject, 9) is True
    item.cancel_warm_up()
    window.afterRendering.emit()
    QCoreApplication.processEvents()
    assert ran == ["crumble"] and reporter.seen == [(7, True)]
