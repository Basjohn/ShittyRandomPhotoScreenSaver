"""Settings greys a Visualizer mode that has no renderer on the running backend, with its reason (D10 point 2;
Current_Plan.md item 8b, N2.7 leftovers).

On the diagnostic Vulkan backend a mode that is not ported is not offered by the runtime; the Visualizers page shows it
greyed (its pill and its admission checkbox), each with a one-line reason, and one line on Setup. On OpenGL every mode
has its renderer and the page is unchanged. Which modes are ported is read from the descriptors, never listed: a port
is simulated by giving one descriptor the backend. The real SettingsDialog, never shown, with ``StyledPopup.exec``
patched.
"""
from __future__ import annotations

import dataclasses
from copy import deepcopy

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QLabel

from core.animation import AnimationManager
from core.settings import visualizer_mode_registry as modes
from core.settings.capability_activation import set_widget_family_activated
from core.settings.default_contract import require_canonical_default
from core.settings.settings_manager import SettingsManager

pytestmark = pytest.mark.qt


def _active_modes() -> tuple[str, ...]:
    return tuple(d.mode_id for d in modes.iter_all_visualizer_mode_descriptors() if modes.is_mode_active(d.mode_id))


@pytest.fixture
def manager(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from ui.styled_popup import StyledPopup

    monkeypatch.setattr(StyledPopup, "exec", lambda popup: setattr(popup, "_result_value", None))
    manager = SettingsManager(application="visualizers_backend_modes", storage_base_dir=tmp_path)
    widgets = manager.get("widgets", {})
    section = deepcopy(require_canonical_default("widgets.spotify_visualizer"))
    section.update({"enabled": True, "visualizers_enabled": True,
                    "mode_activation": modes.build_visualizer_mode_activation(_active_modes())})
    widgets["spotify_visualizer"] = section
    for family in ("media", "visualizers"):
        set_widget_family_activated(widgets, family, True)
    manager.set("widgets", widgets)
    manager.set("sources.folders", [str(tmp_path)])
    yield manager
    assert manager.flush(timeout=5.0)


def _on_backend(monkeypatch, backend: str, ported: set[str]) -> None:
    from rendering.quick import bootstrap

    monkeypatch.setattr(bootstrap, "quick_backend_api", lambda: backend)
    patched = tuple(dataclasses.replace(d, renderer_backends=("opengl", "vulkan") if d.mode_id in ported
                                        else ("opengl",)) for d in modes._ALL_DESCRIPTORS)
    monkeypatch.setattr(modes, "_ALL_DESCRIPTORS", patched)


def _visualizers_tab(manager):
    from ui.settings_dialog import SettingsDialog

    dialog = SettingsDialog(manager, AnimationManager())
    QCoreApplication.processEvents()
    dialog._switch_tab(dialog._tab_index_for_key("visualizers"), animate=False)
    return dialog, dialog.visualizers_tab


def _close(dialog) -> None:
    dialog.close()
    QCoreApplication.processEvents()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()


@pytest.mark.parametrize("backend", ["vulkan", "opengl"])
def test_a_mode_without_a_renderer_on_the_running_backend_is_greyed_with_its_reason(backend, manager, monkeypatch):
    active = _active_modes()
    assert len(active) >= 2
    ported = active[0]
    _on_backend(monkeypatch, backend, {ported})
    without = {mode for mode in active if not modes.is_mode_available_on_backend(mode)}
    assert without == (set(active[1:]) if backend == "vulkan" else set())
    dialog, tab = _visualizers_tab(manager)
    try:
        assert set(tab._vis_body_host.enabled_modes) == set(active)
        for mode in active:
            pill, checkbox = tab._mode_pills[mode], tab._mode_admission_checkboxes[mode]
            greyed = mode in without
            assert not pill.isHidden()                               # still listed: the choice is persisted
            assert pill.isEnabled() is not greyed and checkbox.isEnabled() is not greyed
            assert bool(pill.toolTip()) is greyed and bool(checkbox.toolTip()) is greyed
            if greyed:
                assert "\n" not in pill.toolTip() and pill.toolTip() == checkbox.toolTip()
        line = tab.findChild(QLabel, "visualizerModesWithoutRenderer")
        assert (line is not None) is bool(without)
        if without:
            greyed_mode = sorted(without)[0]
            with pytest.raises(ValueError):
                tab._select_mode_page(greyed_mode)
            tab.restore_view_state({"page": "mode", "mode_id": greyed_mode})
            assert tab.get_view_state() == {"page": "setup"}
        tab._select_mode_page(ported)                                 # the mode with a renderer opens as before
        assert tab.get_view_state() == {"page": "mode", "mode_id": ported}
    finally:
        _close(dialog)
