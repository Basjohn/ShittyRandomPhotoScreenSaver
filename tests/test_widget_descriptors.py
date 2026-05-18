from __future__ import annotations

from rendering.widget_descriptors import (
    apply_widget_section_save_results,
    build_widget_section_buttons,
    build_widget_stack_preview_config,
    collect_widget_section_containers,
    collect_widget_section_save_results,
    collect_widget_section_signal_block_targets,
    collect_widget_stack_status_targets,
    get_factory_widget_descriptors,
    get_default_widget_section_index,
    get_widget_default_init_descriptors,
    get_widget_lazy_dependency_indices,
    get_widget_lazy_bootstrap_indices,
    get_widget_programmatic_dependency_indices,
    get_service_runtime_contracts,
    get_live_refresh_handlers,
    get_live_refresh_handlers_for_settings_key,
    get_widget_section_index_map,
    get_widget_section_signal_block_attrs,
    get_widget_ids_for_service_runtime_contract,
    get_widget_position_option_labels,
    get_widget_runtime_descriptors,
    get_widget_stack_preview_descriptors,
    get_widget_settings_section_descriptors,
    load_widget_sections,
    resolve_widget_section_index_from_view_state,
)
from PySide6.QtWidgets import QButtonGroup


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
    assert defaults.loader_module == "ui.tabs.widgets_tab_defaults"
    assert defaults.loader_name == "load_defaults_settings"
    assert defaults.loader_guard_attrs == (
        "widget_shadows_enabled",
        "widget_text_shadows_enabled",
        "widget_header_shadows_enabled",
        "card_border_width_spin",
    )


def test_widget_settings_section_descriptors_capture_saver_routing():
    descriptors = get_widget_settings_section_descriptors()
    clock = next(item for item in descriptors if item.section_id == "clock")
    reddit = next(item for item in descriptors if item.section_id == "reddit")
    defaults = next(item for item in descriptors if item.section_id == "defaults")

    assert clock.saver_module == "ui.tabs.widgets_tab_clock"
    assert clock.saver_name == "save_clock_settings"
    assert clock.persisted_widget_keys == ("clock", "clock2", "clock3")
    assert reddit.saver_module == "ui.tabs.widgets_tab_reddit"
    assert reddit.saver_name == "save_reddit_settings"
    assert reddit.persisted_widget_keys == ("reddit", "reddit2")
    assert defaults.saver_module == "ui.tabs.widgets_tab_defaults"
    assert defaults.saver_name == "save_defaults_settings"
    assert defaults.persisted_widget_keys == ("shadows", "global")
    assert defaults.bootstrap_in_lazy_mode is True


def test_widget_settings_section_descriptors_expose_default_selected_section():
    descriptors = get_widget_settings_section_descriptors()
    default_idx = get_default_widget_section_index(descriptors)

    assert descriptors[default_idx].section_id == "clock"


def test_widget_section_index_resolution_prefers_stable_section_id():
    descriptors = get_widget_settings_section_descriptors()
    index_map = get_widget_section_index_map(descriptors)

    assert resolve_widget_section_index_from_view_state(
        {"subtab_id": "reddit", "subtab": 0},
        descriptors,
    ) == index_map["reddit"]


def test_widget_lazy_bootstrap_indices_include_defaults_and_requested_subtab():
    descriptors = get_widget_settings_section_descriptors()
    index_map = get_widget_section_index_map(descriptors)

    bootstrap = get_widget_lazy_bootstrap_indices(index_map["weather"], descriptors)

    assert index_map["defaults"] in bootstrap
    assert index_map["weather"] in bootstrap


def test_widget_lazy_dependency_indices_capture_media_visualizer_contract():
    descriptors = get_widget_settings_section_descriptors()
    index_map = get_widget_section_index_map(descriptors)

    assert get_widget_lazy_dependency_indices(index_map["media"], descriptors) == (
        index_map["visualizers"],
    )
    assert get_widget_lazy_dependency_indices(index_map["visualizers"], descriptors) == (
        index_map["media"],
    )


def test_widget_programmatic_dependency_indices_capture_media_visualizer_defaults_contract():
    descriptors = get_widget_settings_section_descriptors()
    index_map = get_widget_section_index_map(descriptors)

    assert get_widget_programmatic_dependency_indices(("media",), descriptors) == (
        index_map["visualizers"],
        index_map["defaults"],
        index_map["media"],
    )
    assert get_widget_programmatic_dependency_indices(("visualizers",), descriptors) == (
        index_map["media"],
        index_map["defaults"],
        index_map["visualizers"],
    )


def test_widget_section_signal_block_attrs_follow_descriptor_registry():
    attrs = get_widget_section_signal_block_attrs()

    assert isinstance(attrs, tuple)
    assert "clock_enabled" in attrs
    assert "weather_enabled" in attrs
    assert "media_enabled" in attrs
    assert "reddit_enabled" in attrs


def test_build_widget_section_buttons_uses_descriptor_metadata(qt_app):
    class _Owner:
        pass

    owner = _Owner()
    group = QButtonGroup()
    descriptors = (
        type(
            "_D",
            (),
            {
                "button_label": "Clock",
                "button_attr_name": "_btn_clock",
            },
        )(),
        type(
            "_D",
            (),
            {
                "button_label": "Weather",
                "button_attr_name": "_btn_weather",
            },
        )(),
    )

    buttons = build_widget_section_buttons(owner, group, "QPushButton {}", descriptors)

    assert len(buttons) == 2
    assert owner._btn_clock is buttons[0]
    assert owner._btn_weather is buttons[1]
    assert group.button(0) is buttons[0]
    assert group.button(1) is buttons[1]


def test_collect_widget_section_containers_uses_descriptor_metadata():
    class _Owner:
        _clock_container = "clock"
        _weather_container = "weather"

    descriptors = (
        type("_D", (), {"container_attr_name": "_clock_container"})(),
        type("_D", (), {"container_attr_name": "_weather_container"})(),
    )

    containers = collect_widget_section_containers(_Owner(), descriptors)

    assert containers == ("clock", "weather")


def test_collect_widget_section_signal_block_targets_uses_descriptor_attrs_and_dedupes():
    class _Owner:
        pass

    owner = _Owner()

    class _Blockable:
        def __init__(self, name: str):
            self.name = name

        def blockSignals(self, _blocked: bool) -> None:
            return None

    shared = _Blockable("shared")
    owner.clock_enabled = shared
    owner.weather_enabled = _Blockable("weather")
    owner.extra = shared
    owner.not_blockable = object()

    targets = collect_widget_section_signal_block_targets(
        owner,
        extra_attr_names=("extra", "not_blockable"),
    )

    assert shared in targets
    assert owner.weather_enabled in targets
    assert owner.not_blockable not in targets
    assert len(targets) == len({id(item) for item in targets})


def test_load_widget_sections_runs_descriptor_owned_loaders():
    calls: list[str] = []
    owner = object()

    descriptors = (
        type(
            "_D",
            (),
            {
                "can_load_for_owner": lambda self, current_owner: current_owner is owner,
                "resolve_loader": lambda self: lambda current_owner, widgets: calls.append(f"a:{widgets['x']}"),
            },
        )(),
        type(
            "_D",
            (),
            {
                "can_load_for_owner": lambda self, current_owner: False,
                "resolve_loader": lambda self: lambda current_owner, widgets: calls.append("b"),
            },
        )(),
    )

    from rendering import widget_descriptors as module

    original = module.get_widget_settings_section_descriptors
    module.get_widget_settings_section_descriptors = lambda: descriptors  # type: ignore[assignment]
    try:
        load_widget_sections(owner, {"x": 7})
    finally:
        module.get_widget_settings_section_descriptors = original  # type: ignore[assignment]

    assert calls == ["a:7"]


def test_collect_widget_section_save_results_runs_savers_and_preserves_unbuilt_sections():
    owner = object()
    descriptors = (
        type(
            "_D",
            (),
            {
                "section_id": "clock",
                "persisted_widget_keys": ("clock", "clock2"),
                "can_save_for_owner": lambda self, current_owner: current_owner is owner,
                "resolve_saver": lambda self: lambda current_owner: ({"enabled": True}, {"enabled": False}),
            },
        )(),
        type(
            "_D",
            (),
            {
                "section_id": "weather",
                "persisted_widget_keys": ("weather",),
                "can_save_for_owner": lambda self, current_owner: False,
                "resolve_saver": lambda self: None,
            },
        )(),
    )

    results = collect_widget_section_save_results(
        owner,
        {"weather": {"location": "Johannesburg"}},
        descriptors,
    )

    assert results == {
        "clock": {"enabled": True},
        "clock2": {"enabled": False},
        "weather": {"location": "Johannesburg"},
    }


def test_apply_widget_section_save_results_uses_descriptor_owned_persisted_keys():
    widgets_config = {
        "clock": {"enabled": True},
        "spotify_visualizer": {"mode": "bubble"},
        "weather": {"location": "Cape Town"},
    }
    results = {
        "clock": {"enabled": False},
        "clock2": {"enabled": True},
        "spotify_visualizer": {"mode": "spectrum"},
        "weather": {"location": "Johannesburg"},
    }
    descriptors = (
        type(
            "_D",
            (),
            {"persisted_widget_keys": ("clock", "clock2")},
        )(),
        type(
            "_D",
            (),
            {"persisted_widget_keys": ("weather", "spotify_visualizer")},
        )(),
    )

    merged = apply_widget_section_save_results(
        widgets_config,
        results,
        exclude_keys=("spotify_visualizer",),
        descriptors=descriptors,
    )

    assert merged is widgets_config
    assert widgets_config["clock"] == {"enabled": False}
    assert widgets_config["clock2"] == {"enabled": True}
    assert widgets_config["weather"] == {"location": "Johannesburg"}
    assert widgets_config["spotify_visualizer"] == {"mode": "bubble"}


def test_widget_default_init_descriptors_cover_standard_widgets_tab_attrs():
    descriptors = get_widget_default_init_descriptors()
    attr_names = {item.attr_name for item in descriptors}

    assert "_global_card_border_width" in attr_names
    assert "_clock_color" in attr_names
    assert "_weather_color" in attr_names
    assert "_media_color" in attr_names
    assert "_reddit_color" in attr_names
    assert "_gmail_color" in attr_names
    assert "_imgur_color" in attr_names


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


def test_collect_widget_stack_status_targets_reads_live_owner_values():
    class _Combo:
        def __init__(self, value: str):
            self._value = value

        def currentText(self) -> str:
            return self._value

    class _Owner:
        pass

    owner = _Owner()
    owner.clock_stack_status = object()
    owner.clock_position = _Combo("Bottom Left")
    owner.clock_monitor_combo = _Combo("ALL")

    targets = collect_widget_stack_status_targets(owner)

    clock = next(item for item in targets if item.widget_type_key == "clock")
    assert clock.status_label is owner.clock_stack_status
    assert clock.position_value == "Bottom Left"
    assert clock.monitor_value == "ALL"


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
