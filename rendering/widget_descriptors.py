"""Canonical widget descriptor registry for factory-backed overlay widgets.

This module centralizes the metadata that was previously duplicated across
``rendering/widget_setup_all.py`` for monitor gating, parent attribute reuse,
factory routing, inheritance wiring, and startup-stage intent.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Dict, Mapping


@dataclass(frozen=True)
class FactoryWidgetDescriptor:
    """Descriptor for a factory-backed overlay widget family."""

    settings_key: str
    attr_name: str
    factory_name: str
    startup_stage: str = "primary"
    settings_key_kwarg: bool = False
    overlay_name: str | None = None
    default_position: str | None = None
    default_font_size: int | None = None
    base_settings_key: str | None = None
    base_settings_kwarg: str | None = None
    factory_shadows_kwarg: bool = False
    inject_shadows_into_config: bool = False
    dev_feature_env: str | None = None

    def is_enabled_in_environment(self) -> bool:
        """Return whether this descriptor is active in the current environment."""
        if not self.dev_feature_env:
            return True
        return os.getenv(self.dev_feature_env, "false").lower() == "true"

    def build_widget_config(
        self,
        widget_config: Mapping[str, Any] | None,
        *,
        shadows_config: Mapping[str, Any] | None,
    ) -> Dict[str, Any]:
        """Build the concrete config mapping passed into the factory."""
        config: Dict[str, Any] = dict(widget_config) if isinstance(widget_config, Mapping) else {}
        if self.default_position is not None:
            config["_default_position"] = self.default_position
        if self.default_font_size is not None:
            config["_default_font_size"] = self.default_font_size
        if self.inject_shadows_into_config:
            config["_shadows_config"] = dict(shadows_config) if isinstance(shadows_config, Mapping) else {}
        return config

    def build_factory_kwargs(
        self,
        *,
        widgets_config: Mapping[str, Any] | None,
        shadows_config: Mapping[str, Any] | None,
    ) -> Dict[str, Any]:
        """Build extra kwargs for the target factory."""
        kwargs: Dict[str, Any] = {}
        if self.settings_key_kwarg:
            kwargs["settings_key"] = self.settings_key
        if self.overlay_name is not None:
            kwargs["overlay_name"] = self.overlay_name
        if self.base_settings_key and self.base_settings_kwarg:
            base_settings: Any = {}
            if isinstance(widgets_config, Mapping):
                candidate = widgets_config.get(self.base_settings_key, {})
                if isinstance(candidate, Mapping):
                    base_settings = candidate
            kwargs[self.base_settings_kwarg] = base_settings
        if self.factory_shadows_kwarg:
            kwargs["shadows_config"] = shadows_config if isinstance(shadows_config, Mapping) else {}
        return kwargs


FACTORY_WIDGET_DESCRIPTORS: tuple[FactoryWidgetDescriptor, ...] = (
    FactoryWidgetDescriptor(
        settings_key="clock",
        attr_name="clock_widget",
        factory_name="clock",
        settings_key_kwarg=True,
        overlay_name="clock",
        default_position="Top Right",
        default_font_size=48,
        factory_shadows_kwarg=True,
    ),
    FactoryWidgetDescriptor(
        settings_key="clock2",
        attr_name="clock2_widget",
        factory_name="clock",
        settings_key_kwarg=True,
        overlay_name="clock2",
        default_position="Bottom Right",
        default_font_size=32,
        base_settings_key="clock",
        base_settings_kwarg="base_clock_settings",
        factory_shadows_kwarg=True,
    ),
    FactoryWidgetDescriptor(
        settings_key="clock3",
        attr_name="clock3_widget",
        factory_name="clock",
        settings_key_kwarg=True,
        overlay_name="clock3",
        default_position="Bottom Left",
        default_font_size=32,
        base_settings_key="clock",
        base_settings_kwarg="base_clock_settings",
        factory_shadows_kwarg=True,
    ),
    FactoryWidgetDescriptor(
        settings_key="weather",
        attr_name="weather_widget",
        factory_name="weather",
        factory_shadows_kwarg=True,
    ),
    FactoryWidgetDescriptor(
        settings_key="media",
        attr_name="media_widget",
        factory_name="media",
        factory_shadows_kwarg=True,
    ),
    FactoryWidgetDescriptor(
        settings_key="reddit",
        attr_name="reddit_widget",
        factory_name="reddit",
        settings_key_kwarg=True,
        factory_shadows_kwarg=True,
    ),
    FactoryWidgetDescriptor(
        settings_key="reddit2",
        attr_name="reddit2_widget",
        factory_name="reddit",
        settings_key_kwarg=True,
        base_settings_key="reddit",
        base_settings_kwarg="base_reddit_settings",
        factory_shadows_kwarg=True,
    ),
    FactoryWidgetDescriptor(
        settings_key="imgur",
        attr_name="imgur_widget",
        factory_name="imgur",
        dev_feature_env="SRPSS_ENABLE_DEV",
    ),
    FactoryWidgetDescriptor(
        settings_key="gmail",
        attr_name="gmail_widget",
        factory_name="gmail",
        inject_shadows_into_config=True,
    ),
)


def get_factory_widget_descriptors() -> tuple[FactoryWidgetDescriptor, ...]:
    """Return the canonical registry for factory-backed overlay widgets."""

    return FACTORY_WIDGET_DESCRIPTORS
