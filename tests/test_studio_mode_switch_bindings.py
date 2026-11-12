"""Switching the Studio's mode never lets a shell evaluate its bindings against a missing ``studio`` (operator, 12 Nov).

The operator's log: switching spectrum -> sphere flooded the QML log with "Cannot read property X of null" on nearly
every binding of ``StudioShell.qml`` (``studio.theme``, ``capabilities``, ``modes``, ``values`` ...), before and after
the new window's "shown". The controller replaced its ``StudioBridge`` when the next mode opened; the retiring window,
whose hide and destruction are queued to the event loop, still had that bridge as its ``studio`` context object, so
when Python dropped the last reference the bridge was deleted under a live engine and every binding of the retiring
shell re-evaluated with ``studio`` null.

This drives the switch the way the shell does (the mode picker calls ``studio.switchMode``) through the real
controller, the real SettingsDialog and the production ``StudioWindowSurface`` with its queued hide and deferred
destruction. Nothing is shown: the surface's show is recorded instead of made. Every QML warning of every Studio
engine is captured (each engine's own ``warnings`` signal, so a warning names the window it came from) across open,
switch and retire, and none may be a TypeError.
"""
from __future__ import annotations

import gc
import weakref
from copy import deepcopy

import pytest
from PySide6.QtCore import QCoreApplication, QEvent

from core.settings.default_contract import require_canonical_default
from tests.test_studio_exit_every_mode import light_adapter

FIRST, SECOND = "spectrum", "sphere"          # the operator's switch; spectrum carries the shape (lanes) instrument


@pytest.fixture
def no_gl_checks():
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()


@pytest.fixture
def settings_tab(qt_app, tmp_path, monkeypatch):
    """The real SettingsDialog on its Visualizers page with both modes enabled (never shown)."""
    from core.animation import AnimationManager
    from core.settings.capability_activation import set_widget_family_activated
    from core.settings.settings_manager import SettingsManager
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from ui.settings_dialog import SettingsDialog
    from ui.studio import settings_link
    from ui.studio.controller import StudioController
    from ui.styled_popup import StyledPopup
    monkeypatch.setattr(StyledPopup, "exec", lambda popup: 0)
    # The next mode's adapter without recorded clips, workers or GL drawing (the switch path itself is unchanged).
    monkeypatch.setattr(settings_link, "studio_adapter", light_adapter)
    manager = SettingsManager(organization="SRPSSFocusedTests", application="StudioModeSwitchBindings",
                              storage_base_dir=tmp_path / "profile")
    config = deepcopy(require_canonical_default("widgets.spotify_visualizer"))
    config.update({"enabled": True, "visualizers_enabled": True, "mode": FIRST,
                   "mode_activation": build_visualizer_mode_activation([FIRST, SECOND])})
    widgets = manager.get("widgets", {})
    widgets["spotify_visualizer"] = config
    for family in ("media", "visualizers"):
        set_widget_family_activated(widgets, family, True)
    manager.set("widgets", widgets)
    dialog = SettingsDialog(manager, AnimationManager())
    QCoreApplication.processEvents()
    dialog._switch_tab(dialog._tab_index_for_key("visualizers"), animate=False)
    tab = dialog.visualizers_tab
    tab._select_mode_page(FIRST)
    dialog.isVisible = lambda: True                 # the presence's view of a shown Settings; never really shown
    for name in ("raise_", "activateWindow", "repaint"):
        setattr(dialog, name, lambda *_a: None)
    yield tab
    active = StudioController.active()
    if active is not None:
        active.close()
    _drain()
    dialog.close()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert manager.flush(timeout=5.0)


@pytest.fixture
def native_calls_recorded(monkeypatch):
    """Settings' native window calls and material are recorded as no-ops (nothing reaches the screen)."""
    from core.windows import dwm_blur
    from ui.studio import presence
    monkeypatch.setattr(presence, "_native_show", lambda *_a: True)
    monkeypatch.setattr(presence, "_native_restore", lambda *_a: (True, True))
    monkeypatch.setattr(presence, "_native_show_beneath", lambda *_a: (True, True))
    monkeypatch.setattr(presence, "_native_reexpose", lambda *_a: None)
    monkeypatch.setattr(presence, "_native_front", lambda *_a: None)
    monkeypatch.setattr(dwm_blur, "apply_backdrop", lambda *_a, **_k: True)


class QmlWarnings:
    """Every warning of every Studio engine, named by the window (1-based, in creation order) that raised it."""

    def __init__(self) -> None:
        self.seen: list[tuple[int, str, str]] = []
        self.windows = 0
        self.phase = "open"

    def watch(self, engine) -> None:
        self.windows += 1
        number = self.windows
        engine.warnings.connect(lambda errors, n=number: self.seen.extend((n, self.phase, e.toString())
                                                                          for e in errors))

    def type_errors(self) -> list[tuple[int, str, str]]:
        return [entry for entry in self.seen if "TypeError" in entry[2]]

    def summary(self) -> dict:
        """TypeErrors counted by (window, phase)."""
        out: dict = {}
        for window, phase, _text in self.type_errors():
            out[(window, phase)] = out.get((window, phase), 0) + 1
        return out


def _surface_factory(warnings: QmlWarnings, made: list):
    """The production window surface; its show is recorded instead of made (the window never appears)."""
    from ui.studio.surface import StudioWindowSurface

    class NeverShownWindowSurface(StudioWindowSurface):
        def show(self) -> None:
            self.on_screen = True

        def covering_window(self):
            return self.window if getattr(self, "on_screen", False) and not self._retired else None

    def factory(controller):
        surface = NeverShownWindowSurface(controller)
        warnings.watch(surface.host.engine)
        made.append(surface)
        return surface
    return factory


def _drain() -> None:
    """The event loop's turn: the queued hide, then the deferred destructions."""
    for _ in range(3):
        QCoreApplication.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()


def _open(tab, warnings):
    from ui.studio.settings_link import open_mode_studio
    made: list = []
    controller = open_mode_studio(tab, FIRST, adapter=light_adapter(FIRST), surface_factory=_surface_factory(warnings,
                                                                                                           made))
    made[0].presented.emit()                        # the first frame reached the screen
    assert controller.state == "presented" and controller.adapter.mode_id == FIRST
    return controller, made


def _switch_as_the_mode_picker_does(controller, mode_id: str) -> None:
    """The shell's mode picker calls ``studio.switchMode`` from its handler; the switch runs inside that call."""
    controller.bridge.switchMode(mode_id)
    gc.collect()                                   # whenever Python's collector runs, it must find nothing to break


def test_a_mode_switch_never_evaluates_a_shell_with_studio_missing(settings_tab, native_calls_recorded, no_gl_checks):
    warnings = QmlWarnings()
    controller, made = _open(settings_tab, warnings)
    _drain()
    assert warnings.type_errors() == [], warnings.type_errors()[:5]
    warnings.phase = "switch"
    old_bridge = weakref.ref(controller.bridge)
    _switch_as_the_mode_picker_does(controller, SECOND)
    assert controller.adapter.mode_id == SECOND and len(made) == 2 and made[0]._retired
    made[1].presented.emit()
    warnings.phase = "retiring window destroyed"
    _drain()                                       # the retiring window's hide and destruction run here
    gc.collect()
    assert old_bridge() is None, "the retiring shell's bridge must go with its engine, not stay for the process"
    warnings.phase = "close"
    controller.close()
    _drain()
    errors = warnings.type_errors()
    assert errors == [], f"{len(errors)} TypeErrors by (window, phase) {warnings.summary()}; first: {errors[:3]}"
