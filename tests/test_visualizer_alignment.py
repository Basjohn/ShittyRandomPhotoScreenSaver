from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout

from ui.tabs.media.spectrum_builder import build_spectrum_ui
from ui.tabs.media.oscilloscope_builder import build_oscilloscope_ui
from ui.tabs.media.bubble_builder import build_bubble_ui


@pytest.fixture(scope="session")
def qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class DummyTab:
    """Lightweight stand-in for WidgetsTab used to exercise builder wiring."""

    def __init__(self, initial_adv_state: dict[str, bool] | None = None) -> None:
        self._preset_slider_changing = False
        self._spotify_vis_fill_color = None
        self._spotify_vis_border_color = None
        self._visualizer_adv_state: dict[str, bool] = dict(initial_adv_state or {})

    # Settings helpers -------------------------------------------------
    def _save_settings(self, *args, **kwargs):
        pass

    def _auto_switch_preset_to_custom(self, *args, **kwargs):
        pass

    def _default_bool(self, _section, _key, fallback=True):
        return fallback

    def _default_int(self, _section, _key, fallback=0):
        return fallback

    def _default_float(self, _section, _key, fallback=0.0):
        return fallback

    def _default_str(self, _section, _key, fallback=""):
        return fallback

    # Widget-tab hooks referenced by builders --------------------------
    def _update_spotify_vis_sensitivity_enabled_state(self):
        pass

    def _update_spotify_vis_floor_enabled_state(self):
        pass

    def _update_spotify_vis_ghost_enabled_state(self):
        pass

    # Visualizer advanced state helpers --------------------------------
    def get_visualizer_adv_state(self, mode: str) -> bool:
        return bool(self._visualizer_adv_state.get(mode, False))

    def set_visualizer_adv_state(self, mode: str, expanded: bool) -> None:
        self._visualizer_adv_state[mode] = bool(expanded)


@pytest.mark.parametrize(
    "builder, normal_attr, adv_attr, toggle_attr, host_attr, slider_attr, helper_attr, mode_name",
    [
        (
            build_spectrum_ui,
            "_spectrum_normal",
            "_spectrum_advanced",
            "_spectrum_adv_toggle",
            "_spectrum_advanced_host",
            "_spectrum_preset_slider",
            "_spectrum_adv_helper",
            "spectrum",
        ),
        (
            build_oscilloscope_ui,
            "_osc_normal",
            "_osc_advanced",
            "_osc_adv_toggle",
            "_osc_advanced_host",
            "_osc_preset_slider",
            "_osc_adv_helper",
            "oscilloscope",
        ),
        (
            build_bubble_ui,
            "_bubble_normal",
            "_bubble_advanced",
            "_bubble_adv_toggle",
            "_bubble_advanced_host",
            "_bubble_preset_slider",
            "_bubble_adv_helper",
            "bubble",
        ),
    ],
)
def test_advanced_toggle_hides_only_advanced(
    qt_app,
    builder,
    normal_attr,
    adv_attr,
    toggle_attr,
    host_attr,
    slider_attr,
    helper_attr,
    mode_name,
):
    def _build_tab(tab):
        container = QWidget()
        layout = QVBoxLayout(container)
        builder(tab, layout)
        container.show()
        qt_app.processEvents()
        owned = getattr(tab, "_owned_containers", None)
        if owned is None:
            owned = []
            tab._owned_containers = owned
        owned.append(container)
        return (
            getattr(tab, normal_attr),
            getattr(tab, adv_attr),
            getattr(tab, toggle_attr),
            getattr(tab, host_attr),
            getattr(tab, slider_attr),
            getattr(tab, helper_attr),
        )

    # Initial tab with no remembered state should default collapsed
    tab = DummyTab()
    (
        normal_container,
        advanced_widget,
        toggle,
        host,
        slider,
        helper_label,
    ) = _build_tab(tab)

    # Preset slider should own the advanced host container
    assert slider._advanced_container is host

    # Default state now collapsed (Advanced hidden by default)
    assert not advanced_widget.isVisible()
    assert helper_label.isVisible()
    assert normal_container.isVisible()

    # Expanding via toggle should show advanced widget and hide helper text
    toggle.setChecked(True)
    qt_app.processEvents()
    assert advanced_widget.isVisible()
    assert helper_label.isHidden()
    assert normal_container.isVisible()
    assert tab._visualizer_adv_state.get(mode_name) is True

    # Collapsing again should hide only the advanced widget and persist state
    toggle.setChecked(False)
    qt_app.processEvents()
    assert not advanced_widget.isVisible()
    assert helper_label.isVisible()
    assert tab._visualizer_adv_state.get(mode_name) is False

    # A new tab with stored state should restore the expanded UI
    tab_restored = DummyTab(initial_adv_state={mode_name: True})
    (
        restored_normal,
        restored_advanced,
        restored_toggle,
        _,
        _,
        restored_helper,
    ) = _build_tab(tab_restored)
    assert restored_normal.isVisible()
    assert restored_advanced.isVisible()
    assert restored_helper.isHidden()
    assert restored_toggle.isChecked() is True
