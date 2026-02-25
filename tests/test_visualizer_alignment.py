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

    def __init__(self) -> None:
        self._preset_slider_changing = False
        self._spotify_vis_fill_color = None
        self._spotify_vis_border_color = None

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


@pytest.mark.parametrize(
    "builder, normal_attr, adv_attr, toggle_attr, host_attr, slider_attr, helper_attr",
    [
        (
            build_spectrum_ui,
            "_spectrum_normal",
            "_spectrum_advanced",
            "_spectrum_adv_toggle",
            "_spectrum_advanced_host",
            "_spectrum_preset_slider",
            "_spectrum_adv_helper",
        ),
        (
            build_oscilloscope_ui,
            "_osc_normal",
            "_osc_advanced",
            "_osc_adv_toggle",
            "_osc_advanced_host",
            "_osc_preset_slider",
            "_osc_adv_helper",
        ),
        (
            build_bubble_ui,
            "_bubble_normal",
            "_bubble_advanced",
            "_bubble_adv_toggle",
            "_bubble_advanced_host",
            "_bubble_preset_slider",
            "_bubble_adv_helper",
        ),
    ],
)
def test_advanced_toggle_hides_only_advanced(qt_app, builder, normal_attr, adv_attr, toggle_attr, host_attr, slider_attr, helper_attr):
    tab = DummyTab()
    container = QWidget()
    layout = QVBoxLayout(container)

    builder(tab, layout)

    container.show()
    qt_app.processEvents()

    normal_container = getattr(tab, normal_attr)
    advanced_widget = getattr(tab, adv_attr)
    toggle = getattr(tab, toggle_attr)
    host = getattr(tab, host_attr)
    slider = getattr(tab, slider_attr)
    helper_label = getattr(tab, helper_attr)

    # Preset slider should own the advanced host container
    assert slider._advanced_container is host

    # Default state = expanded (Custom preset semantics)
    assert advanced_widget.isVisible()
    assert helper_label.isHidden()
    assert normal_container.isVisible()

    # Collapsing via toggle should hide only the advanced widget
    toggle.setChecked(False)
    qt_app.processEvents()
    assert not advanced_widget.isVisible()
    assert helper_label.isVisible()
    assert normal_container.isVisible()

    # Re-expanding should re-show advanced content and hide helper text
    toggle.setChecked(True)
    qt_app.processEvents()
    assert advanced_widget.isVisible()
    assert helper_label.isHidden()
