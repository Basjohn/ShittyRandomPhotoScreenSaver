"""Leaving a Studio is ONE transition: the Studio window goes and the Settings window is there (operator, 8 Nov: "we
still double flicker when leaving studios").

The double flicker: every exit revealed Settings (native show, ``BringWindowToTop``, ``SetForegroundWindow``, Qt raise
and activate) while the application-modal Studio window was still on screen, its hide only queued afterwards. Settings
jumped above the Studio, Qt handed the blocked Settings' activation straight back to the modal Studio, which jumped
back above it, and the queued hide then revealed Settings a second time. The operator's own field log shows the
hand-back: right after the reveal the native foreground and active window was still the Studio.

The exit now reveals Settings beneath the Studio window (shown without activation, z-ordered under it, re-exposed and
painted while covered) and brings it forward only once that window is gone. This test records the exit in order on the
real SettingsDialog, the real controller and ``WindowPresence``, and the production ``StudioWindowSurface`` and its
queued hide and deferred destruction: every native window call, Qt raise / activate / repaint / opacity change and
material application, and the Studio window's retirement and destruction. Nothing is shown: the native calls are
recorded instead of made, Settings is never shown and the Studio window never appears (its show is recorded). The
negative control replays the former sequence (Settings brought forward at the reveal) and the check names it.
"""
from __future__ import annotations

from copy import deepcopy

import pytest
from PySide6.QtCore import QCoreApplication, QEvent

from core.settings.default_contract import require_canonical_default
from tests.test_studio_exit_every_mode import light_adapter

MODE = "shockwave_grid"            # the operator's report; the exit path itself is mode-neutral


class ExitRecord:
    """The exit's window events, in order."""

    def __init__(self) -> None:
        self.events: list[tuple[str, ...]] = []
        self.recording = False

    def add(self, *event) -> None:
        if self.recording:
            self.events.append(tuple(event))


def single_transition_problems(events) -> list[str]:
    """What keeps an exit from being one clean transition (empty: it is one).

    One native show of Settings and no hide again; Settings painted before the Studio window goes (the swap uncovers a
    current picture); nothing brings Settings forward, raises or activates it while the Studio window is still there,
    and it comes forward exactly once after; no window opacity change and no material re-applied."""
    names = [event[0] for event in events]
    problems = []
    if "studio window gone" not in names:
        return ["the Studio window never went"]
    gone = names.index("studio window gone")
    shows = [e for e in events if e[0] in ("settings shown", "settings shown in front")]
    if len(shows) != 1:
        problems.append(f"Settings shown {len(shows)} times")
    if "settings hidden" in names:
        problems.append("Settings hidden again during the exit")
    if not any(name == "settings painted" for name in names[:gone]):
        problems.append("Settings not painted before the Studio window went")
    early = [names[i] for i in range(gone) if names[i] in ("settings shown in front", "settings brought forward",
                                                           "settings raised", "settings activated")]
    if early:
        problems.append(f"Settings came forward while the Studio window was still on screen: {early}")
    late = [name for name in names[gone:] if name in ("settings brought forward", "settings shown in front")]
    if len(late) != 1:
        problems.append(f"Settings brought forward {len(late)} times after the Studio window went")
    for name in ("settings opacity", "material applied"):
        if name in names:
            problems.append(f"{name} during the exit")
    return problems


@pytest.fixture
def no_gl_checks():
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()


@pytest.fixture
def popups(monkeypatch):
    """The real SettingsDialog is built here: any prompt it raises is recorded, never shown."""
    from ui.styled_popup import StyledPopup
    seen = []
    monkeypatch.setattr(StyledPopup, "exec", lambda popup: seen.append(popup._title) or 0)
    return seen


@pytest.fixture
def settings_dialog(qt_app, tmp_path, popups):
    """The real SettingsDialog on its Visualizers page (never shown)."""
    from core.animation import AnimationManager
    from core.settings.capability_activation import set_widget_family_activated
    from core.settings.settings_manager import SettingsManager
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from ui.settings_dialog import SettingsDialog
    from ui.studio.controller import StudioController
    manager = SettingsManager(organization="SRPSSFocusedTests", application="StudioExitTransition",
                              storage_base_dir=tmp_path / "profile")
    config = deepcopy(require_canonical_default("widgets.spotify_visualizer"))
    config.update({"enabled": True, "visualizers_enabled": True, "mode": MODE,
                   "mode_activation": build_visualizer_mode_activation([MODE])})
    widgets = manager.get("widgets", {})
    widgets["spotify_visualizer"] = config
    for family in ("media", "visualizers"):
        set_widget_family_activated(widgets, family, True)
    manager.set("widgets", widgets)
    dialog = SettingsDialog(manager, AnimationManager())
    QCoreApplication.processEvents()
    dialog._switch_tab(dialog._tab_index_for_key("visualizers"), animate=False)
    tab = dialog.visualizers_tab
    tab._select_mode_page(MODE)
    yield dialog, tab
    active = StudioController.active()
    if active is not None:
        active.close()
    dialog.close()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert manager.flush(timeout=5.0)


@pytest.fixture
def recorded(monkeypatch):
    """Native window calls and material applications recorded in order instead of made."""
    from core.windows import dwm_blur
    from ui.studio import presence
    record = ExitRecord()
    state = {"studio": None}

    def native_show(widget, command):
        record.add("settings hidden" if command == presence._SW_HIDE else "settings shown in front")
        return True

    def restore(widget):
        record.add("settings shown in front")
        return True, True

    def beneath(widget, above):
        record.add("settings shown", "beneath the Studio window" if above is state["studio"] else f"beneath {above!r}")
        return True, True

    monkeypatch.setattr(presence, "_native_show", native_show)
    monkeypatch.setattr(presence, "_native_restore", restore)
    monkeypatch.setattr(presence, "_native_show_beneath", beneath)
    monkeypatch.setattr(presence, "_native_reexpose", lambda widget: record.add("settings re-exposed"))
    monkeypatch.setattr(presence, "_native_front", lambda widget: record.add("settings brought forward"))
    monkeypatch.setattr(dwm_blur, "apply_backdrop", lambda *_a, **_k: record.add("material applied") or True)
    return record, state


def _record_settings(dialog, record: ExitRecord) -> None:
    """Settings as the presence sees a shown window, its raise / activate / repaint / opacity recorded."""
    dialog.isVisible = lambda: True                       # the presence's view: Settings is a shown window
    dialog.raise_ = lambda: record.add("settings raised")
    dialog.activateWindow = lambda: record.add("settings activated")
    dialog.repaint = lambda: record.add("settings painted")
    dialog.setWindowOpacity = lambda value: record.add("settings opacity", value)


def _surface_factory(record: ExitRecord, state: dict, made: list):
    """The production window surface; its show is recorded instead of made (the window never appears), and its
    window counts as on screen from that show until its retirement."""
    from ui.studio.surface import StudioWindowSurface

    class RecordedWindowSurface(StudioWindowSurface):
        def show(self) -> None:
            self.on_screen = True
            record.add("studio shown")

        def covering_window(self):
            return self.window if getattr(self, "on_screen", False) and not self._retired else None

        def retire(self) -> None:
            if not self._retired:
                record.add("studio retired (hide and destruction queued)")
            super().retire()

    def factory(controller):
        surface = RecordedWindowSurface(controller)
        # Connected first, so it is recorded before anything else the destruction runs.
        surface.window.destroyed.connect(lambda *_a: record.add("studio window gone"))
        state["studio"] = surface.window
        made.append(surface)
        return surface
    return factory


def _open(tab, record, state):
    from ui.studio.settings_link import open_mode_studio
    made = []
    controller = open_mode_studio(tab, MODE, adapter=light_adapter(MODE),
                                  surface_factory=_surface_factory(record, state, made))
    made[0].presented.emit()                              # the first frame reached the screen
    assert controller.state == "presented" and controller.presence.concealed
    return controller, made[0]


def _leave(controller, surface, path: str) -> None:
    if path == "close button":
        controller.bridge.requestCloseFrom("close button")
    elif path == "escape":
        controller.bridge.requestCloseFrom("escape")
    elif path == "window close":
        surface.closeRequested.emit()                      # the window X / Alt+F4
    elif path == "application quit":
        controller.close_for_quit()
    else:
        raise AssertionError(path)
    for _ in range(3):
        QCoreApplication.processEvents()                   # the queued hide
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)   # the deferred destruction
    QCoreApplication.processEvents()
    assert controller.state == "closed" and not controller.presence.concealed


@pytest.mark.parametrize("path", ["close button", "escape", "window close", "application quit"])
def test_leaving_the_studio_is_one_clean_transition(settings_dialog, recorded, no_gl_checks, popups, path):
    dialog, tab = settings_dialog
    record, state = recorded
    _record_settings(dialog, record)
    controller, surface = _open(tab, record, state)
    record.recording = True
    _leave(controller, surface, path)
    record.recording = False
    if controller.presence.watch is not None:
        controller.presence.watch.disarm()
    events = record.events
    assert single_transition_problems(events) == [], events
    names = [event[0] for event in events]
    assert ("settings shown", "beneath the Studio window") in events
    assert names.index("settings shown") < names.index("studio retired (hide and destruction queued)")
    assert popups == []


def test_the_former_exit_sequence_is_named_by_the_check_negative_control(settings_dialog, recorded, no_gl_checks,
                                                                         monkeypatch):
    """Reveal as every exit used to (Settings brought forward at once, while the Studio window is still on screen):
    the check names the early raise and activation, and Settings showing in front of the Studio window."""
    from ui.studio import presence
    dialog, tab = settings_dialog
    record, state = recorded
    _record_settings(dialog, record)
    controller, surface = _open(tab, record, state)
    reveal = presence.WindowPresence.reveal
    monkeypatch.setattr(controller.presence, "reveal", lambda **_k: reveal(controller.presence))
    record.recording = True
    _leave(controller, surface, "close button")
    record.recording = False
    if controller.presence.watch is not None:
        controller.presence.watch.disarm()
    problems = single_transition_problems(record.events)
    assert any("came forward while the Studio window was still on screen" in p for p in problems), record.events
    early = next(p for p in problems if "came forward while" in p)
    assert all(name in early for name in ("settings shown in front", "settings raised", "settings activated"))


def test_a_studio_window_that_fails_to_retire_never_leaves_settings_behind_it(settings_dialog, recorded, no_gl_checks,
                                                                              monkeypatch):
    """The restore guarantee holds with the new order: a window whose retirement fails may stay on screen, so
    Settings, revealed beneath it, comes forward at once."""
    dialog, tab = settings_dialog
    record, state = recorded
    _record_settings(dialog, record)
    controller, surface = _open(tab, record, state)

    def boom():
        raise RuntimeError("forced retire failure")
    monkeypatch.setattr(surface, "retire", boom)
    record.recording = True
    controller.close()
    record.recording = False
    if controller.presence.watch is not None:
        controller.presence.watch.disarm()
    names = [event[0] for event in record.events]
    assert "surface" in controller.close_failures and not controller.presence.concealed
    assert names.index("settings shown") < names.index("settings brought forward")
    assert names.count("settings brought forward") == 1
    surface.window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
