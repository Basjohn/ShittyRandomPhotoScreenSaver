from __future__ import annotations

from rendering.widget_descriptors import get_factory_widget_descriptors


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
