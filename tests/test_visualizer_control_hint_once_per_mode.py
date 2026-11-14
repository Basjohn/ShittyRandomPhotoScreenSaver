"""The 3D control hint plays once per saver session per Visualizer mode (plan 1D.12 C).

The session's one set of modes whose hint has played lives in Python (the engine's, handed to each DisplayManager
generation and from there to every display's scene controller); the lazy QML root, which is rebuilt, only reads a
bool from it at mode and admission edges and reports the edge where the hint begins to play. The production
``DisplayScene.qml`` / ``VisualizerPresentation.qml`` and ``QuickSceneController`` run in the hidden
``QQuickRenderControl`` host (never shown); synthetic mouse moves exercise Qt Quick's own hover delivery. Mode ids
are test-owned 3D modes; nothing pins a timing, a preset or UI wording.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QMouseEvent

from tests.test_visualizer_expansion_overlays import CHROME, HEIGHT, WIDTH, _expanded_card, _run

FIRST, SECOND = "extruded_bubble", "shockwave_grid"


@pytest.fixture
def display(qt_app):
    if qt_app.platformName().strip().lower() != "windows":
        pytest.skip("the hidden production scene needs the Windows QPA GL")
    from tools.expanded_visualizer_evidence import HiddenDisplayHost

    host = HiddenDisplayHost(WIDTH, HEIGHT, dpr=1.0)
    try:
        yield host
    finally:
        host.close()


def _card(display, mode: str) -> None:
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation

    presentation = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy(mode), display_size=(WIDTH, HEIGHT), outer_origin=(120.0, 160.0),
        **CHROME)
    display.scene.apply_visualizer_presentation(presentation, active=True)


def _admit(display, mode: str, shown_modes: set[str]) -> None:
    """What DisplayManager projects at a mode or admission edge for a framed 3D mode."""
    scene = display.scene
    scene.set_visualizer_control_hints_available(True)
    scene.set_visualizer_control_hint_memory(mode, shown_modes)
    root = scene._visualizer_root
    for name, value in (("widgetGlowAdmitted", True), ("show3DControlHints", True)):
        root.setProperty(name, value)
    _run(display, 60)


def _move(display, point: QPointF) -> None:
    QGuiApplication.sendEvent(display.window, QMouseEvent(
        QEvent.Type.MouseMove, point, point, Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier))


def _card_centre(display) -> QPointF:
    root = display.scene._visualizer_root
    rect = root.mapRectToItem(display.window.contentItem(), QRectF(0.0, 0.0, root.width(), root.height()))
    return rect.center()


def _visit(display) -> float:
    """One visit: the pointer enters the card, rests, and leaves. Returns the hint's peak opacity."""
    root = display.scene._visualizer_root
    peak = [0.0]

    def sample() -> None:
        peak[0] = max(peak[0], float(root.property("controlHintOpacity")))

    _move(display, _card_centre(display))
    _run(display, 1500, sample)
    _move(display, QPointF(WIDTH - 2.0, 2.0))
    _run(display, 1500, sample)
    assert float(root.property("controlHintOpacity")) == pytest.approx(0.0, abs=0.005)   # gone before the next
    return peak[0]


@pytest.mark.qt
def test_two_visits_in_one_mode_reveal_once_and_another_mode_once_more(display):
    shown: set[str] = set()
    _card(display, FIRST)
    _admit(display, FIRST, shown)
    assert _visit(display) > 0.85                       # the first visit in a mode plays the hint
    assert shown == {FIRST}                             # recorded in the session's set, not in the QML root
    assert _visit(display) < 0.01                       # a later visit in that mode does not

    _card(display, SECOND)                              # a switch to another 3D mode
    _admit(display, SECOND, shown)
    assert _visit(display) > 0.85                       # one more reveal
    assert _visit(display) < 0.01
    _admit(display, FIRST, shown)                       # back to the first mode: still shown
    assert _visit(display) < 0.01
    assert shown == {FIRST, SECOND}


@pytest.mark.qt
def test_expanded_readmission_and_a_rebuilt_root_keep_the_set(display):
    shown: set[str] = set()
    _card(display, FIRST)
    _admit(display, FIRST, shown)
    assert _visit(display) > 0.85
    _expanded_card(display)                             # Expanded/fullscreen re-admission
    _admit(display, FIRST, shown)
    assert _visit(display) < 0.01
    _card(display, FIRST)
    # The lazy root is rebuilt (a display move binds the Visualizer to another display's scene, a new generation
    # builds a new one): a fresh root reads the session's set at its creation edge.
    display.scene._visualizer_root.setProperty("controlHintShown", False)
    _admit(display, FIRST, shown)
    assert display.scene._visualizer_root.property("controlHintShown") is True
    assert _visit(display) < 0.01


@pytest.mark.qt
def test_with_the_set_bypassed_the_second_visit_reveals_again(display, monkeypatch):
    """Negative control: nothing records the reveal, so every visit plays the hint (the behaviour before 1D.12 C)."""
    from rendering.quick.scene_controller import QuickSceneController

    monkeypatch.setattr(QuickSceneController, "_on_visualizer_control_hint_revealed", lambda self: None)
    shown: set[str] = set()
    _card(display, FIRST)
    _admit(display, FIRST, shown)
    assert _visit(display) > 0.85
    assert _visit(display) > 0.85
    assert shown == set()


def test_display_manager_hands_every_display_the_sessions_one_set():
    """Mode switches and display moves project from the one set the engine hands each generation."""
    import ast
    import weakref
    from pathlib import Path
    from types import SimpleNamespace

    from tests._display_manager_doubles import visualizer_owner_double
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController

    source = (Path(__file__).resolve().parents[1] / "engine" / "display_manager.py").read_text(encoding="utf-8")
    cls = next(node for node in ast.parse(source).body
               if isinstance(node, ast.ClassDef) and node.name == "DisplayManager")
    scope = {"QuickDisplayUnit": object, "weakref": weakref}
    for name in ("_configure_quick_visualizer_input_admission", "set_control_hint_memory"):
        node = next(item for item in cls.body if isinstance(item, ast.FunctionDef) and item.name == name)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), "<manager>", "exec"), scope)

    projected: list[tuple[str, int, object]] = []

    def unit(index: int):
        scene = SimpleNamespace(
            set_visualizer_camera_reset_available=lambda value: None,
            set_visualizer_studio_rotate_glyphs=lambda *values: None,
            set_visualizer_control_hints_available=lambda value: None,
            set_visualizer_control_hint_memory=lambda mode, memory: projected.append((mode, index, memory)))
        inputs = SimpleNamespace(set_view_orbit_enabled=lambda value: None,
                                 set_framed_flight_enabled=lambda value: None,
                                 set_scene_transform_enabled=lambda value, **kw: None)
        return SimpleNamespace(runtime=SimpleNamespace(scene_controller=scene, input_controller=inputs))

    class Manager:
        _configure_quick_visualizer_input_admission = scope["_configure_quick_visualizer_input_admission"]
        set_control_hint_memory = scope["set_control_hint_memory"]

        def __init__(self, mode):
            self._control_hint_shown_modes = set()
            self._quick_visualizer_owner = visualizer_owner_double(
                VisualizerRuntimeController(runtime_generation=0, initial_mode=mode, engine_factory=lambda _n: None))

        def _quick_view_orbit_admitted(self):
            return True

    session: set[str] = set()
    first = Manager(FIRST)
    first.set_control_hint_memory(session)
    first._configure_quick_visualizer_input_admission(unit(1), admitted=True)
    first._configure_quick_visualizer_input_admission(unit(2), admitted=True)   # the Visualizer on another display
    replacement = Manager(FIRST)                                                 # a new runtime generation
    replacement.set_control_hint_memory(session)
    replacement._configure_quick_visualizer_input_admission(unit(1), admitted=True)
    assert [(mode, index) for mode, index, _memory in projected] == [(FIRST, 1), (FIRST, 2), (FIRST, 1)]
    assert all(memory is session for _mode, _index, memory in projected)
    projected.clear()
    first._configure_quick_visualizer_input_admission(unit(1), admitted=False)  # not admitted: no mode to read
    assert projected[0][0] == ""
