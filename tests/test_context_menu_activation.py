"""Context-menu activation awareness + Random parity (Phase E2 §5/§9)."""
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from core.settings.capability_activation import is_transition_activated
from rendering import display_context_menu as dcm
from widgets.context_menu import ScreensaverContextMenu


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class _FakeSettings:
    def __init__(self, transitions: dict):
        self._transitions = transitions
        self.saved = 0

    def get(self, key, default=None):
        if key == "transitions":
            return self._transitions
        return default

    def set(self, key, value):
        if key == "transitions":
            self._transitions = value

    def save(self):
        self.saved += 1


def _stub_widget(transitions: dict):
    return SimpleNamespace(
        settings_manager=_FakeSettings(transitions),
        _context_menu=None,
        _transition_random_enabled=False,
        _transition_fallback_type="Crossfade",
    )


# --- Menu refresh (activation filtering) -----------------------------------


def test_refresh_shows_only_activated_transitions(qapp, qtbot):
    menu = ScreensaverContextMenu()
    qtbot.addWidget(menu)
    menu.refresh_transition_modes(["Crossfade", "Wipe"], "Wipe", False)
    names = set(menu._transition_actions) - {"Random"}
    assert names == {"Crossfade", "Wipe"}
    assert "Burn" not in menu._transition_actions


def test_random_action_disabled_when_pool_empty(qapp, qtbot):
    menu = ScreensaverContextMenu()
    qtbot.addWidget(menu)
    menu.refresh_transition_modes(["Crossfade"], "Crossfade", False, random_selectable=False)
    assert menu._transition_actions["Random"].isEnabled() is False
    menu.refresh_transition_modes(["Crossfade"], "Crossfade", False, random_selectable=True)
    assert menu._transition_actions["Random"].isEnabled() is True


def test_context_menu_save_action_emits_semantic_edit_session_request(qapp, qtbot):
    menu = ScreensaverContextMenu()
    qtbot.addWidget(menu)
    requests: list[str] = []
    menu.save_edit_mode_requested.connect(lambda: requests.append("save"))

    menu.update_edit_mode_state(True)
    assert menu._save_edit_mode_action.isVisible() is True
    menu._save_edit_mode_action.trigger()

    assert requests == ["save"]


# --- Handler persistence + admission ---------------------------------------


def test_concrete_selection_writes_type_and_disables_random(qapp):
    widget = _stub_widget({"activation": {}, "pool": {"Wipe": True}, "random_always": True})
    dcm.on_context_transition_selected(widget, "Wipe")
    cfg = widget.settings_manager.get("transitions")
    assert cfg["type"] == "Wipe"
    assert cfg["random_always"] is False


def test_random_selection_writes_random_always_never_type_random(qapp):
    widget = _stub_widget({"activation": {}, "pool": {"Wipe": True}, "type": "Wipe"})
    dcm.on_context_transition_selected(widget, "Random")
    cfg = widget.settings_manager.get("transitions")
    assert cfg["random_always"] is True
    assert cfg.get("type") != "Random"


def test_deactivated_selection_is_not_persisted(qapp):
    widget = _stub_widget({
        "type": "Crossfade",
        "random_always": False,
        "activation": {"Burn": False},
        "pool": {name: True for name in ("Crossfade", "Burn")},
    })
    dcm.on_context_transition_selected(widget, "Burn")
    cfg = widget.settings_manager.get("transitions")
    # Stale/deactivated selection rejected; type unchanged.
    assert cfg["type"] == "Crossfade"


def test_selection_never_persists_type_random_even_from_legacy(qapp):
    widget = _stub_widget({"type": "Random", "random_always": False, "pool": {"Wipe": True}})
    dcm.on_context_transition_selected(widget, "Random")
    cfg = widget.settings_manager.get("transitions")
    assert cfg.get("type") != "Random"
    assert cfg["random_always"] is True
    assert is_transition_activated(cfg, cfg["type"]) is True
