from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QToolButton

from core.settings.defaults import get_default_settings
from rendering.widget_descriptors import collect_widget_section_save_result
from ui.tabs.widgets_tab import WidgetsTab
from ui.widget_stack_predictor import WidgetType, build_widget_estimates


def test_system_stats_settings_are_lazy_and_do_not_start_the_sampler(
    qt_app,
    settings_manager,
) -> None:
    sys.modules.pop("ui.tabs.widgets_tab_system_stats", None)
    sys.modules.pop("widgets.system_stats_runtime", None)
    tab = WidgetsTab(
        settings_manager,
        lazy_sections=True,
        initial_view_state={"subtab_id": "clock"},
    )
    try:
        assert not hasattr(tab, "system_stats_enabled")
        assert "ui.tabs.widgets_tab_system_stats" not in sys.modules
        assert "widgets.system_stats_runtime" not in sys.modules
    finally:
        tab.deleteLater()
        qt_app.processEvents()


def test_system_stats_settings_roundtrip_preserves_canonical_product_scope(
    qt_app,
    settings_manager,
) -> None:
    sys.modules.pop("widgets.system_stats_runtime", None)
    tab = WidgetsTab(
        settings_manager,
        lazy_sections=True,
        initial_view_state={"subtab_id": "system_stats"},
    )
    try:
        defaults = get_default_settings()["widgets"]["system_stats"]
        assert tab.system_stats_enabled.isChecked() is defaults["enabled"]
        assert tab._system_stats_controls_container.isHidden() is True
        # EXACT-VALUE INVARIANT: 10 seconds is the admitted minimum sampler
        # workload/safety bound, not merely today's mutable default.
        assert tab.system_stats_sample_interval_seconds.minimum() == 10
        assert tab.system_stats_sample_interval_seconds.value() == defaults["sample_interval_seconds"]
        assert "widgets.system_stats_runtime" not in sys.modules

        tab.system_stats_enabled.setChecked(True)
        layout_toggle = next(
            toggle
            for toggle in tab._system_stats_controls_container.findChildren(
                QToolButton
            )
            if toggle.text() == "Layout"
        )
        assert layout_toggle.isChecked() is False
        tab._set_combo_text(tab.system_stats_position, "Bottom Right")
        tab._set_combo_text(tab.system_stats_monitor_combo, "2")
        tab.system_stats_font_family.setCurrentFont(QFont("Jost"))
        tab.system_stats_font_size.setValue(19)
        tab.system_stats_sample_interval_seconds.setValue(25)
        tab.system_stats_show_cpu.setChecked(True)
        tab.system_stats_show_memory.setChecked(False)
        tab.system_stats_show_uptime.setChecked(True)
        tab.system_stats_show_network.setChecked(False)

        payload = collect_widget_section_save_result(tab, "system_stats")
        assert payload["enabled"] is True
        assert payload["position"] == "Bottom Right"
        assert payload["monitor"] == 2
        assert payload["font_family"] == "Jost"
        assert payload["font_size"] == 19
        assert payload["metric_capacity"] == defaults["metric_capacity"]
        assert payload["sample_interval_seconds"] == 25
        assert payload["show_cpu"] is True
        assert payload["show_memory"] is False
        assert payload["show_uptime"] is True
        assert payload["show_network"] is False
        assert "cadence" not in payload
        assert "gpu" not in payload
        assert "process" not in payload
        assert "widgets.system_stats_runtime" not in sys.modules
    finally:
        tab.deleteLater()
        qt_app.processEvents()


def test_system_stats_participates_in_the_shared_stack_predictor() -> None:
    defaults = get_default_settings()["widgets"]
    settings = {
        "system_stats": {
            "enabled": True,
            "position": "Middle Left",
            "monitor": "1",
        }
    }

    estimates = build_widget_estimates(settings, defaults=defaults)
    stats = next(
        estimate
        for estimate in estimates
        if estimate.widget_type is WidgetType.SYSTEM_STATS
    )

    assert stats.position == "Middle Left"
    assert stats.monitor == "1"
    system_defaults = defaults["system_stats"]
    assert stats.estimated_width == int(system_defaults["preferred_width"])
    assert stats.estimated_height == int(system_defaults["preferred_height"])
