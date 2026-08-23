"""Visualizer capability runtime + context-menu admission (Phase E2 §6/§7/§14)."""
from types import SimpleNamespace

import pytest
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
