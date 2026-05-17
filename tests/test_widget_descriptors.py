from __future__ import annotations

from rendering.widget_descriptors import (
    build_widget_stack_preview_config,
    get_factory_widget_descriptors,
    get_service_runtime_contracts,
    get_live_refresh_handlers,
    get_live_refresh_handlers_for_settings_key,
    get_widget_ids_for_service_runtime_contract,
    get_widget_position_option_labels,
    get_widget_runtime_descriptors,
    get_widget_stack_preview_descriptors,
    get_widget_settings_section_descriptors,
)


def test_clock_descriptor_builds_expected_factory_kwargs():
    descriptor = next(
        item for item in get_factory_widget_descriptors() if item.settings_key == "clock2"
    )

    kwargs = descriptor.build_factory_kwargs(
        widgets_config={"clock": {"font_family": "Inter"}},
        shadows_config={"enabled": True},
    )

    assert kwargs["settings_key"] == "clock2"
    assert kwargs["overlay_name"] == "clock2"
    assert kwargs["base_clock_settings"] == {"font_family": "Inter"}
    assert kwargs["shadows_config"] == {"enabled": True}


def test_gmail_descriptor_injects_shadow_config_into_widget_config():
    descriptor = next(
        item for item in get_factory_widget_descriptors() if item.settings_key == "gmail"
    )

    config = descriptor.build_widget_config(
        {"enabled": True, "monitor": "ALL"},
        shadows_config={"enabled": True, "blur_radius": 18},
    )

    assert config["enabled"] is True
    assert config["_shadows_config"] == {"enabled": True, "blur_radius": 18}


def test_widget_settings_section_descriptors_default_order():
    descriptors = get_widget_settings_section_descriptors()

    assert [descriptor.section_id for descriptor in descriptors] == [
        "clock",
        "weather",
        "media",
        "visualizers",
        "reddit",
        "gmail",
        "defaults",
    ]


def test_widget_settings_section_descriptors_capture_loader_routing():
    descriptors = get_widget_settings_section_descriptors()
    media = next(item for item in descriptors if item.section_id == "media")
    gmail = next(item for item in descriptors if item.section_id == "gmail")
    defaults = next(item for item in descriptors if item.section_id == "defaults")

    assert media.loader_module == "ui.tabs.widgets_tab_media"
    assert media.loader_name == "load_media_settings"
    assert media.loader_guard_attrs == ("media_enabled", "vis_enabled_checkbox")
    assert gmail.loader_module == "ui.tabs.widgets_tab_gmail"
    assert gmail.loader_name == "load_gmail_settings"
    assert defaults.resolve_loader() is None


def test_widget_runtime_descriptors_capture_capability_and_refresh_ownership():
    descriptors = get_widget_runtime_descriptors()
    runtime_ids = [descriptor.widget_id for descriptor in descriptors]

    assert "spotify_visualizer" in runtime_ids
    assert "reddit2" in runtime_ids

    visualizer = next(item for item in descriptors if item.widget_id == "spotify_visualizer")
    reddit2 = next(item for item in descriptors if item.widget_id == "reddit2")
    gmail = next(item for item in descriptors if item.widget_id == "gmail")

    assert visualizer.startup_stage == "secondary"
    assert visualizer.anchor_dependent is True
    assert visualizer.live_refresh_handler == "_refresh_spotify_visualizer_config"
    assert reddit2.settings_section_id == "reddit"
    assert reddit2.live_refresh_handler == "_refresh_reddit_configs"
    assert gmail.service_backed is True
    assert gmail.supports_layout_edit_mode is True
    assert gmail.supports_custom_position_slot is True
    assert gmail.supports_layout_resize_edit is True
    assert gmail.requires_size_reset_affordance is True
    assert "visible_fallback" in gmail.service_runtime_contracts
    assert "manual_refresh" in reddit2.service_runtime_contracts


def test_service_runtime_contract_queries_follow_descriptor_contract():
    assert get_service_runtime_contracts("gmail") == (
        "transition_probe",
        "single_shot_timer_reuse",
        "deferred_refresh",
        "deferred_result",
        "spinner_suspend",
        "fetch_guard",
        "manual_refresh",
        "visible_fallback",
        "timer_stop_cleanup",
    )
    assert get_service_runtime_contracts("weather") == (
        "single_shot_timer_reuse",
        "timer_stop_cleanup",
    )
    assert get_service_runtime_contracts("imgur") == ()
    assert get_service_runtime_contracts("clock") == ()
    assert get_widget_ids_for_service_runtime_contract("visible_fallback") == (
        "reddit",
        "reddit2",
        "gmail",
    )


def test_widget_position_option_labels_follow_runtime_descriptor_contract():
    assert get_widget_position_option_labels("gmail") == (
        "Top Left",
        "Top Center",
        "Top Right",
        "Middle Left",
        "Center",
        "Middle Right",
        "Bottom Left",
        "Bottom Center",
        "Bottom Right",
    )
    assert get_widget_position_option_labels("unknown-widget") == (
        "Top Left",
        "Top Center",
        "Top Right",
        "Middle Left",
        "Center",
        "Middle Right",
        "Bottom Left",
        "Bottom Center",
        "Bottom Right",
    )


def test_live_refresh_handlers_follow_runtime_descriptors():
    assert get_live_refresh_handlers() == (
        "_refresh_media_config",
        "_refresh_reddit_configs",
        "_refresh_spotify_visualizer_config",
    )
    assert get_live_refresh_handlers_for_settings_key("widgets.reddit2.limit") == (
        "_refresh_reddit_configs",
    )


def test_stack_preview_descriptors_capture_live_widgets_tab_preview_contract():
    descriptors = get_widget_stack_preview_descriptors()
    clock = next(item for item in descriptors if item.widget_id == "clock")

    assert clock.position_attr_name == "clock_position"
    assert clock.monitor_attr_name == "clock_monitor_combo"
    assert {field.key for field in clock.fields} >= {
        "enabled",
        "display_mode",
        "show_timezone_label",
    }


def test_build_widget_stack_preview_config_reads_live_clock_controls(qt_app, settings_manager):
    from ui.tabs.widgets_tab import WidgetsTab

    tab = WidgetsTab(settings_manager)
    try:
        tab.clock_enabled.setChecked(True)
        tab.clock_analog_mode.setChecked(True)
        tab.clock_show_tz.setChecked(True)
        tab.clock_position.setCurrentText("Bottom Left")
        tab.clock_monitor_combo.setCurrentText("ALL")
        tab.clock_font_size.setValue(64)

        config = build_widget_stack_preview_config(tab)

        assert config["clock"]["enabled"] is True
        assert config["clock"]["display_mode"] == "analog"
        assert config["clock"]["show_timezone_label"] is True
        assert config["clock"]["position"] == "Bottom Left"
        assert config["clock"]["font_size"] == 64
    finally:
        tab.deleteLater()
