"""Visualizer capability runtime + context-menu admission (Phase E2 §6/§7/§14)."""
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from rendering.widget_setup_all import _setup_spotify_visualizer
from rendering import display_context_menu as dcm
from widgets.context_menu import ScreensaverContextMenu


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class _StubVisMgr:
    def __init__(self):
        self._parent = SimpleNamespace()
        self.create_calls = 0

    def create_spotify_visualizer_widget(self, *a, **k):
        self.create_calls += 1
        return SimpleNamespace()

    def register_widget(self, *a, **k):
        pass

    def _bind_parent_attribute(self, *a, **k):
        pass

    def _register_spotify_secondary_fade(self, w):
        pass


def _run_local_setup(widgets_config, media=SimpleNamespace()):
    mgr = _StubVisMgr()
    _setup_spotify_visualizer(mgr, {}, widgets_config, {}, 0, None, media)
    return mgr


# --- Runtime admission -----------------------------------------------------


def test_visualizer_not_created_when_visualizers_deactivated():
    cfg = {"family_activation": {"media": True, "visualizers": False}}
    assert _run_local_setup(cfg).create_calls == 0


def test_visualizer_not_created_when_media_deactivated():
    cfg = {"family_activation": {"media": False, "visualizers": True}}
    assert _run_local_setup(cfg).create_calls == 0


def test_stale_media_object_cannot_bypass_capability_gate():
    # A live/stale Media object is present, but the capability is deactivated.
    cfg = {"family_activation": {"media": False, "visualizers": False}}
    assert _run_local_setup(cfg, media=SimpleNamespace(alive=True)).create_calls == 0


def test_visualizer_created_when_both_capabilities_active():
    cfg = {"family_activation": {"media": True, "visualizers": True}}
    assert _run_local_setup(cfg).create_calls == 1


# --- Context-menu admission ------------------------------------------------


def test_menu_set_visualizer_available_toggles_submenu(qapp, qtbot):
    menu = ScreensaverContextMenu()
    qtbot.addWidget(menu)
    menu.set_visualizer_available(False)
    assert menu.is_visualizer_available() is False
    assert menu._visualizer_menu_action.isVisible() is False
    menu.set_visualizer_available(True)
    assert menu._visualizer_menu_action.isVisible() is True


def _stub_widget_for_vis(widgets: dict):
    switched = []
    vis = SimpleNamespace(switch_to_mode=lambda m: switched.append(m))
    widget = SimpleNamespace(
        settings_manager=SimpleNamespace(get=lambda k, d=None: widgets if k == "widgets" else d),
        spotify_visualizer_widget=vis,
    )
    return widget, switched


def test_context_visualizer_selection_rejected_when_capability_inactive(qapp):
    widget, switched = _stub_widget_for_vis({"family_activation": {"media": False, "visualizers": True}})
    dcm.on_context_visualizer_selected(widget, "bubble")
    assert switched == []  # capability inactive -> no mode switch


def test_context_visualizer_selection_allowed_when_active(qapp):
    widget, switched = _stub_widget_for_vis({"family_activation": {"media": True, "visualizers": True}})
    dcm.on_context_visualizer_selected(widget, "bubble")
    assert switched == ["bubble"]


# --- Unresolvable-state fail-closed: mode-switch boundary -------------------
#
# The blocker: callers coerced an unresolvable state to ``{}``, which — because a
# valid mapping with absent activation keys means active for compatibility — read
# as permission. These prove the mode-switch boundary now fails closed on an
# unresolvable state while keeping the valid-empty-map compatibility semantics.


def _switch_target():
    switched = []
    vis = SimpleNamespace(switch_to_mode=lambda m: switched.append(m))
    return vis, switched


def test_mode_switch_rejected_when_settings_manager_missing(qapp):
    vis, switched = _switch_target()
    widget = SimpleNamespace(settings_manager=None, spotify_visualizer_widget=vis)
    dcm.on_context_visualizer_selected(widget, "bubble")
    assert switched == []  # missing manager -> fail closed


def test_mode_switch_rejected_when_widgets_read_raises(qapp):
    vis, switched = _switch_target()

    def _boom(key, default=None):
        if key == "widgets":
            raise RuntimeError("read failure")
        return default

    widget = SimpleNamespace(
        settings_manager=SimpleNamespace(get=_boom),
        spotify_visualizer_widget=vis,
    )
    dcm.on_context_visualizer_selected(widget, "bubble")
    assert switched == []  # failed read -> fail closed


def test_mode_switch_rejected_when_widgets_root_malformed(qapp):
    vis, switched = _switch_target()
    # A non-mapping widgets root (list) is unresolvable, not a valid empty config.
    widget = SimpleNamespace(
        settings_manager=SimpleNamespace(get=lambda k, d=None: ["nope"] if k == "widgets" else d),
        spotify_visualizer_widget=vis,
    )
    dcm.on_context_visualizer_selected(widget, "bubble")
    assert switched == []  # malformed root -> fail closed


def test_mode_switch_allowed_with_valid_empty_widgets_map(qapp):
    # NEGATIVE CONTROL: a genuine empty mapping is valid; absent activation keys
    # mean active for backwards compatibility, so the switch proceeds.
    vis, switched = _switch_target()
    widget = SimpleNamespace(
        settings_manager=SimpleNamespace(get=lambda k, d=None: {} if k == "widgets" else d),
        spotify_visualizer_widget=vis,
    )
    dcm.on_context_visualizer_selected(widget, "bubble")
    assert switched == ["bubble"]


# --- Unresolvable-state fail-closed: show-menu boundary ---------------------


class _ShowSettings:
    """Settings stand-in for driving show_context_menu; only 'widgets' varies."""

    def __init__(self, widgets_result=None, *, raise_on_widgets=False):
        self._widgets = widgets_result
        self._raise = raise_on_widgets

    def get(self, key, default=None):
        if key == "widgets":
            if self._raise:
                raise RuntimeError("read failure")
            return self._widgets
        if key == "transitions":
            return {}
        return default


def _make_show_widget(settings_manager, qtbot):
    menu = ScreensaverContextMenu()
    qtbot.addWidget(menu)
    menu.set_visualizer_available(True)  # start available so a fail-closed flip is real
    menu.popup = lambda *a, **k: None  # never actually show a window during the test
    widget = SimpleNamespace(
        settings_manager=settings_manager,
        _context_menu=menu,
        _context_menu_hooks_connected=True,
        _context_menu_hide_connected=True,
        _context_menu_active=False,
        _is_mc_build=False,
        _always_on_top=False,
        screen_index=0,
        _input_handler=None,
        spotify_visualizer_widget=None,
        _refresh_transition_state_from_settings=lambda: ("Crossfade", False),
        _is_interaction_mode_enabled=lambda: False,
        _hide_ctrl_cursor_hint=lambda **k: None,
    )
    return widget, menu


def test_show_menu_submenu_unavailable_when_settings_manager_missing(qapp, qtbot):
    widget, menu = _make_show_widget(None, qtbot)
    dcm.show_context_menu(widget, QPoint(0, 0))
    assert menu.is_visualizer_available() is False


def test_show_menu_submenu_unavailable_when_widgets_read_raises(qapp, qtbot):
    widget, menu = _make_show_widget(_ShowSettings(raise_on_widgets=True), qtbot)
    dcm.show_context_menu(widget, QPoint(0, 0))
    assert menu.is_visualizer_available() is False


def test_show_menu_submenu_unavailable_when_widgets_root_malformed(qapp, qtbot):
    widget, menu = _make_show_widget(_ShowSettings("not-a-mapping"), qtbot)
    dcm.show_context_menu(widget, QPoint(0, 0))
    assert menu.is_visualizer_available() is False


def test_show_menu_submenu_unavailable_when_media_off(qapp, qtbot):
    widget, menu = _make_show_widget(
        _ShowSettings({"family_activation": {"media": False, "visualizers": True}}), qtbot
    )
    dcm.show_context_menu(widget, QPoint(0, 0))
    assert menu.is_visualizer_available() is False


def test_show_menu_submenu_available_with_valid_empty_widgets_map(qapp, qtbot):
    # NEGATIVE CONTROL: valid empty mapping -> compatibility semantics -> available.
    widget, menu = _make_show_widget(_ShowSettings({}), qtbot)
    dcm.show_context_menu(widget, QPoint(0, 0))
    assert menu.is_visualizer_available() is True


def test_show_menu_submenu_available_when_active(qapp, qtbot):
    widget, menu = _make_show_widget(
        _ShowSettings({"family_activation": {"media": True, "visualizers": True}}), qtbot
    )
    dcm.show_context_menu(widget, QPoint(0, 0))
    assert menu.is_visualizer_available() is True
