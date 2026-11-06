"""Leaving any Studio always brings Settings back, and the Studio's lifecycle is always on record.

Every registered Studio mode is opened from its real Settings body, a value is committed through Settings' save,
then the *shell's own* Close button (the QML button, its deferred click) closes it: Settings is revealed, and
revealed *before* the window and models are torn down, so a failing or hanging teardown step cannot keep it
hidden (the operator's frozen exit). Forced exceptions in retirement still restore Settings. The production window
is never hidden from Python (PySide holds the GIL through ``QWindow.hide()`` while Qt's threaded render loop waits
for the render thread, which runs the viewport's Python on invalidation): the event loop hides and destroys it.
The ``--studio`` sidecar (and the main log) receive the lifecycle. Hidden windows only; negative controls included.
"""
from __future__ import annotations

import logging

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QMetaObject, QObject

from ui.studio.registry import create_adapter, studio_modes


class QuietRenderer:
    def prepare(self, card, frame):
        return True

    def render(self, card, frame):
        pass

    def release(self):
        pass


class NoJob:
    def cancel(self):
        pass


def light_adapter(mode: str):
    """The registered adapter without recorded clips, background workers or GL drawing."""
    from ui.studio.engine_answers import EngineAnswerEvaluator
    adapter = create_adapter(mode)
    adapter.recorded_clips = lambda: ()
    adapter.create_renderer = QuietRenderer
    probe = adapter.create_evaluator()
    probe.release()
    if isinstance(probe, EngineAnswerEvaluator):        # an engine-answer mode: no out-of-process worker here
        adapter.create_evaluator = lambda: type(probe)(loader=lambda *_a: NoJob())
    return adapter


@pytest.fixture
def settings_manager(qt_app, tmp_path):
    from core.settings.settings_manager import SettingsManager
    manager = SettingsManager(organization="SRPSSFocusedTests", application="StudioExit",
                              storage_base_dir=tmp_path / "profile")
    yield manager
    assert manager.flush(timeout=5.)


@pytest.fixture
def mode_dialog(qt_app, settings_manager):
    from PySide6.QtWidgets import QDialog, QVBoxLayout
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from core.settings.visualizer_presets import get_custom_preset_index
    from ui.tabs.visualizers_tab import VisualizersTab
    built = []

    def build(mode):
        settings_manager.set("widgets", {"spotify_visualizer": {
            "enabled": True, "visualizers_enabled": True, "mode": mode,
            "mode_activation": build_visualizer_mode_activation([mode]),
            f"preset_{mode}": get_custom_preset_index(mode)}})
        dialog = QDialog()
        QVBoxLayout(dialog).addWidget(tab := VisualizersTab(settings_manager))
        tab._select_mode_page(mode)
        built.append(dialog)
        return dialog, tab
    yield build
    for dialog in built:
        dialog.deleteLater()
    qt_app.processEvents()


@pytest.fixture(autouse=True)
def _no_open_studio():
    from ui.studio.controller import StudioController
    yield
    active = StudioController.active()
    if active is not None:
        active.close()


@pytest.fixture
def no_gl_checks():
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()


def _open(tab, mode):
    from ui.studio.settings_link import open_mode_studio
    from ui.studio.surface import OffscreenStudioSurface
    surfaces = []

    def factory(controller):
        surfaces.append(OffscreenStudioSurface(controller, size=(1280, 760), present_on_show=False))
        return surfaces[-1]
    controller = open_mode_studio(tab, mode, adapter=light_adapter(mode), surface_factory=factory)
    surfaces[0].pump(3)
    assert controller.state == "presented" and controller.presence.concealed
    return controller, surfaces[0]


def _commit_one_value(controller) -> None:
    """A real committed edit through Settings' save: the first shown plain scalar, moved within its range."""
    from ui.studio.schema import SCALAR
    bridge, session = controller.bridge, controller.session
    hidden = bridge.conditionHidden
    for prop in session.schema.properties:
        if prop.instrument != SCALAR or len(prop.path) != 1 or hidden.get(prop.id) or prop.view_pose:
            continue
        value = float(session.values[prop.path[0]])
        target = prop.minimum if abs(value - prop.minimum) > abs(prop.maximum - value) else prop.maximum
        saves = session.commit_count
        bridge.commitValue(prop.id, 0, target)
        if session.commit_count > saves:
            return
    raise AssertionError("no scalar could be committed")


def _click_close(surface) -> None:
    """The shell's own Close button: its click handler defers the request out of the handler."""
    button = surface.host.root.findChild(QObject, "closeButton")
    assert button is not None, "the shell has no Close button"
    QMetaObject.invokeMethod(button, "clicked")
    for _ in range(5):
        QCoreApplication.processEvents()


def _restored(controller, dialog) -> bool:
    from ui.studio.controller import StudioController
    presence = controller.presence
    return (controller.state == "closed" and StudioController.active() is None and not presence.concealed
            and presence.reveal_count >= 1 and presence.widget is dialog and dialog.isEnabled())


def _record_concealment_at_teardown(controller, surface, monkeypatch) -> list:
    """Whether Settings was still concealed when the window's retirement started."""
    seen = []
    original = surface.retire

    def retire():
        seen.append(controller.presence.concealed)
        original()
    monkeypatch.setattr(surface, "retire", retire)
    return seen


MODES = sorted(entry.mode_id for entry in studio_modes())


def test_every_visualizer_mode_has_a_studio():
    """Every registered Visualizer mode offers a Studio (Edit Preset was retired once the last one landed)."""
    from core.settings.visualizer_mode_registry import iter_visualizer_mode_descriptors
    assert {d.mode_id for d in iter_visualizer_mode_descriptors()} <= set(MODES)


@pytest.mark.parametrize("mode", MODES)
def test_the_close_button_after_a_commit_reveals_settings_before_teardown(qt_app, mode_dialog, settings_manager,
                                                                          no_gl_checks, monkeypatch, mode):
    dialog, tab = mode_dialog(mode)
    controller, surface = _open(tab, mode)
    _commit_one_value(controller)
    assert controller.session.commit_count >= 1
    assert not _restored(controller, dialog)                          # negative control: still concealed here
    seen = _record_concealment_at_teardown(controller, surface, monkeypatch)
    _click_close(surface)
    assert _restored(controller, dialog), mode
    assert seen == [False], "Settings must be revealed before the window is retired"
    assert controller.close_failures == ()


@pytest.mark.parametrize("mode", MODES)
def test_a_failing_teardown_still_reveals_settings(qt_app, mode_dialog, no_gl_checks, monkeypatch, mode):
    dialog, tab = mode_dialog(mode)
    controller, surface = _open(tab, mode)
    _commit_one_value(controller)

    def boom(*_a, **_k):
        raise RuntimeError("forced retire failure")
    monkeypatch.setattr(surface, "retire", boom)
    monkeypatch.setattr(controller.evaluator, "release", boom)
    _click_close(surface)
    assert _restored(controller, dialog), mode
    assert {"surface", "evaluator"} <= set(controller.close_failures)


def test_a_reveal_that_never_ran_is_caught_by_the_teardown_probe_negative_control(
        qt_app, mode_dialog, no_gl_checks, monkeypatch):
    """With the reveal suppressed (as when it ran only after a hanging teardown), the probe sees Settings concealed
    at teardown and the restore check fails."""
    dialog, tab = mode_dialog("spectrum")
    controller, surface = _open(tab, "spectrum")
    seen = _record_concealment_at_teardown(controller, surface, monkeypatch)
    monkeypatch.setattr(controller.presence, "reveal", lambda: None)
    _click_close(surface)
    assert seen == [True] and not _restored(controller, dialog)


# ---------------------------------------------------------------------- the production window is never hidden by Python
def _window_surface(qt_app, mode_dialog):
    from PySide6.QtCore import QRect
    from ui.studio.controller import StudioBridge, StudioController
    from ui.studio.presence import WindowPresence
    from ui.studio.session import StudioEditSession
    from ui.studio.settings_link import VisualizerSettingsStore
    from ui.studio.surface import StudioWindowSurface
    dialog, tab = mode_dialog("spectrum")
    controller = StudioController(light_adapter("spectrum"), VisualizerSettingsStore(tab, "spectrum"),
                                  WindowPresence(dialog), lambda c: None)
    controller.session = StudioEditSession(controller.adapter.schema(), controller.store)
    controller.evaluator = controller.adapter.create_evaluator()
    controller.bridge = StudioBridge(controller)
    return controller, StudioWindowSurface(controller, anchor=QRect(100, 100, 900, 700))


def test_the_production_window_is_hidden_and_destroyed_by_the_event_loop(qt_app, mode_dialog):
    """Never shown here. ``retire`` must not call ``hide()`` from Python; the event loop hides and destroys it."""
    import shiboken6
    controller, surface = _window_surface(qt_app, mode_dialog)
    window = surface.window
    python_hides = []
    window.hide = lambda: python_hides.append(True)          # what a Python-side ``window.hide()`` would call
    surface.retire()
    assert python_hides == []
    QCoreApplication.sendPostedEvents(None, 0)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qt_app.processEvents()
    assert not shiboken6.isValid(window)
    controller.evaluator.release()


def test_the_python_hide_probe_detects_a_synchronous_hide_negative_control(qt_app, mode_dialog):
    controller, surface = _window_surface(qt_app, mode_dialog)
    python_hides = []
    surface.window.hide = lambda: python_hides.append(True)
    surface.window.hide()                                     # the former retirement's synchronous call
    assert python_hides == [True]
    surface.retire()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qt_app.processEvents()
    controller.evaluator.release()


# ------------------------------------------------- a surface that was never retired is still destroyed legally
def _unretired_toy_surface(qt_app, monkeypatch):
    """A toy Studio closed with the surface's retirement forced to fail: its render tree is left alive, as after
    ``test_a_failing_teardown_still_reveals_settings`` (or a failing evidence capture)."""
    from PySide6.QtWidgets import QDialog
    from ui.studio.controller import StudioController
    from ui.studio.presence import WindowPresence
    from ui.studio.surface import OffscreenStudioSurface
    from tests.test_waveform_studio_second_mode import ToyAdapter, ToyStore
    surfaces = []
    dialog = QDialog()                                         # never shown

    def factory(controller):
        surfaces.append(OffscreenStudioSurface(controller, size=(900, 600), present_on_show=False))
        return surfaces[-1]
    controller = StudioController(ToyAdapter(), ToyStore(), WindowPresence(dialog), factory)
    assert controller.open()
    surface = surfaces[0]
    surface.pump(2)                                            # the render control's RHI exists and imported the context

    def boom():
        raise RuntimeError("forced retire failure")
    monkeypatch.setattr(surface, "retire", boom)
    controller.close()
    assert controller.state == "closed" and "surface" in controller.close_failures
    dialog.deleteLater()
    return surface


def _exit_sweep(surface) -> list:
    """What PySide's interpreter-exit sweep destroys of this surface: every live *Python-owned* native QObject, one by
    one, in an order it does not control (hash order). Arranged adversarially here: the GL context first."""
    import shiboken6
    natives = (surface.context, surface.surface, surface.control, surface.window, surface.host.engine,
               surface.host._component)
    owned = [o for o in natives if shiboken6.isValid(o) and shiboken6.ownedByPython(o)]
    return sorted(owned, key=lambda o: o is not surface.context)


def _context_freed_before_control(plan, surface) -> bool:
    return surface.context in plan and plan.index(surface.context) < plan.index(surface.control)


def test_an_unretired_surface_destroys_its_gl_context_only_after_its_render_control(qt_app, monkeypatch):
    """The render control's RHI uses the imported context until its own destructor; the context and its surface are
    the control's children, so no sweep order (exit, GC) can free the context first. The fault this pins was an
    intermittent access violation after the whole file had passed."""
    import shiboken6
    surface = _unretired_toy_surface(qt_app, monkeypatch)
    plan = _exit_sweep(surface)
    assert surface.control in plan and not _context_freed_before_control(plan, surface)
    events = []
    surface.control.destroyed.connect(lambda *_a: events.append("control"))
    surface.context.aboutToBeDestroyed.connect(lambda: events.append("context"))
    surface.surface.destroyed.connect(lambda *_a: events.append("offscreen surface"))
    for obj in plan:
        if shiboken6.isValid(obj):
            shiboken6.delete(obj)
    assert events == ["control", "context", "offscreen surface"]
    assert not shiboken6.isValid(surface.context) and not shiboken6.isValid(surface.surface)


def test_a_context_with_its_own_python_owner_is_flagged_by_the_sweep_negative_control(qt_app, monkeypatch):
    """The former structure (context and render control as two independent Python owners) puts the context ahead
    of the control in the sweep. Only the plan is checked; the illegal deletion itself is never run."""
    import shiboken6
    surface = _unretired_toy_surface(qt_app, monkeypatch)
    surface.context.setParent(None)                            # back to its own Python owner, as before the fix
    try:
        assert shiboken6.ownedByPython(surface.context)
        assert _context_freed_before_control(_exit_sweep(surface), surface)
    finally:
        surface.context.setParent(surface.control)
    assert not _context_freed_before_control(_exit_sweep(surface), surface)
    surface.control.deleteLater()
    QCoreApplication.sendPostedEvents(surface.control, QEvent.Type.DeferredDelete)


# ------------------------------------------------------------------------------------------- the --studio sidecar
@pytest.fixture
def logging_into(tmp_path, monkeypatch):
    from core.logging import logger as logger_mod

    def configure(studio: bool):
        monkeypatch.setattr(logger_mod, "_FORCED_LOG_DIR", tmp_path)
        monkeypatch.setattr(logger_mod, "_ACTIVE_LOG_DIR", None)
        monkeypatch.setattr(logger_mod, "_LOGGING_DISABLED", False)
        logger_mod.setup_logging(studio_trace=studio)
        return tmp_path
    yield configure
    logger_mod.flush_and_close_logging()
    for handler in list(logging.getLogger().handlers):
        logging.getLogger().removeHandler(handler)


def _toy_session_through_close(qt_app):
    from PySide6.QtWidgets import QDialog
    from ui.studio.controller import StudioController
    from ui.studio.presence import WindowPresence
    from ui.studio.surface import OffscreenStudioSurface
    from tests.test_waveform_studio_second_mode import ToyAdapter, ToyStore
    surfaces = []
    dialog = QDialog()                                         # never shown

    def factory(controller):
        surfaces.append(OffscreenStudioSurface(controller, size=(900, 600), present_on_show=False))
        return surfaces[-1]
    controller = StudioController(ToyAdapter(), ToyStore(), WindowPresence(dialog), factory)
    assert controller.open()
    surfaces[0].pump(2)
    controller.bridge.commitValue("toy_gain", 0, 1.5)
    _click_close(surfaces[0])
    assert controller.state == "closed" and not controller.presence.concealed
    dialog.deleteLater()


LIFECYCLE = ("[STUDIO] open mode=toy_mode", "[STUDIO] presented mode=toy_mode", "[STUDIO] Settings concealed",
             "[STUDIO] commit mode=toy_mode", "[STUDIO] close requested mode=toy_mode via close button",
             "[STUDIO] retire step settings", "[STUDIO] Settings revealed", "[STUDIO] retire step surface",
             "[STUDIO] retire reveal=True")


def test_the_studio_sidecar_and_the_main_log_receive_the_whole_lifecycle(qt_app, logging_into):
    from core.logging.logger import flush_logging, is_studio_logging_enabled, resolve_logging_bootstrap_profile
    assert resolve_logging_bootstrap_profile(("--studio",)).studio_trace is True
    assert resolve_logging_bootstrap_profile(()).studio_trace is False
    assert resolve_logging_bootstrap_profile((), diagnostic_build=True).studio_trace is True
    folder = logging_into(True)
    assert is_studio_logging_enabled()
    _toy_session_through_close(qt_app)
    assert flush_logging(5.0)
    sidecar = (folder / "screensaver_studio.log").read_text(encoding="utf-8")
    main = (folder / "screensaver.log").read_text(encoding="utf-8")
    for line in LIFECYCLE:
        assert line in sidecar, line
        assert line in main, line
    # Settings came back before the window went: the reveal precedes the surface step in the record.
    assert sidecar.index("[STUDIO] Settings revealed") < sidecar.index("[STUDIO] retire step surface")
    assert "Screensaver logging initialized" not in sidecar               # only the Studio family


def test_without_the_flag_there_is_no_sidecar_but_the_main_log_keeps_the_lifecycle_negative_control(
        qt_app, logging_into):
    from core.logging.logger import flush_logging
    folder = logging_into(False)
    _toy_session_through_close(qt_app)
    assert flush_logging(5.0)
    assert not (folder / "screensaver_studio.log").exists()
    main = (folder / "screensaver.log").read_text(encoding="utf-8")
    assert "[STUDIO] close requested mode=toy_mode via close button" in main


def test_the_studio_flag_is_an_accepted_launch_flag_everywhere():
    """Source, MC and frozen launches share main's flag filter; the run tools know the flag and its log."""
    import inspect
    import main
    from tools import run_matrix
    assert '"--studio"' in inspect.getsource(main.parse_screensaver_args)
    assert "--studio" in run_matrix.SAFE_FLAGS and "screensaver_studio.log" in run_matrix.LOG_NAMES
