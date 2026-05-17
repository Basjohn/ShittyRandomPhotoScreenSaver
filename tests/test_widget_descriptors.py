from __future__ import annotations

from rendering.widget_descriptors import (
    get_factory_widget_descriptors,
    get_live_refresh_handlers,
    get_live_refresh_handlers_for_settings_key,
    get_widget_runtime_descriptors,
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


def test_live_refresh_handlers_follow_runtime_descriptors():
    assert get_live_refresh_handlers() == (
        "_refresh_media_config",
        "_refresh_reddit_configs",
        "_refresh_spotify_visualizer_config",
    )
    assert get_live_refresh_handlers_for_settings_key("widgets.reddit2.limit") == (
        "_refresh_reddit_configs",
    )
