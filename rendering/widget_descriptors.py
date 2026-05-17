"""Canonical widget descriptor registry for factory-backed overlay widgets.

This module centralizes the metadata that was previously duplicated across
``rendering/widget_setup_all.py`` for monitor gating, parent attribute reuse,
factory routing, inheritance wiring, and startup-stage intent.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
import os
from typing import Any, Callable, Dict, Mapping


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


@dataclass(frozen=True)
class WidgetSettingsSectionDescriptor:
    """Descriptor for one WidgetsTab sub-section."""

    section_id: str
    button_label: str
    button_attr_name: str
    container_attr_name: str
    builder_module: str | None = None
    builder_name: str | None = None
    method_name: str | None = None
    dev_feature_env: str | None = None

    def is_enabled_in_environment(self) -> bool:
        if not self.dev_feature_env:
            return True
        return os.getenv(self.dev_feature_env, "false").lower() == "true"

    def resolve_builder(self, owner: Any) -> Callable[..., Any]:
        """Return the concrete builder callable for this section."""
        if self.method_name:
            return getattr(owner, self.method_name)
        if self.builder_module and self.builder_name:
            module = import_module(self.builder_module)
            return getattr(module, self.builder_name)
        raise ValueError(f"Descriptor {self.section_id} has no builder")


WIDGET_SETTINGS_SECTION_DESCRIPTORS: tuple[WidgetSettingsSectionDescriptor, ...] = (
    WidgetSettingsSectionDescriptor(
        section_id="clock",
        button_label="Clocks",
        button_attr_name="_btn_clocks",
        container_attr_name="_clocks_container",
        builder_module="ui.tabs.widgets_tab_clock",
        builder_name="build_clock_ui",
    ),
    WidgetSettingsSectionDescriptor(
        section_id="weather",
        button_label="Weather",
        button_attr_name="_btn_weather",
        container_attr_name="_weather_container",
        builder_module="ui.tabs.widgets_tab_weather",
        builder_name="build_weather_ui",
    ),
    WidgetSettingsSectionDescriptor(
        section_id="media",
        button_label="Media",
        button_attr_name="_btn_media",
        container_attr_name="_media_container",
        builder_module="ui.tabs.widgets_tab_media",
        builder_name="build_media_ui",
    ),
    WidgetSettingsSectionDescriptor(
        section_id="visualizers",
        button_label="Visualizers",
        button_attr_name="_btn_visualizers",
        container_attr_name="_visualizers_container",
        builder_module="ui.tabs.widgets_tab_media",
        builder_name="build_visualizers_ui",
    ),
    WidgetSettingsSectionDescriptor(
        section_id="reddit",
        button_label="Reddit",
        button_attr_name="_btn_reddit",
        container_attr_name="_reddit_container",
        builder_module="ui.tabs.widgets_tab_reddit",
        builder_name="build_reddit_ui",
    ),
    WidgetSettingsSectionDescriptor(
        section_id="gmail",
        button_label="Gmail",
        button_attr_name="_btn_gmail",
        container_attr_name="_gmail_container",
        builder_module="ui.tabs.widgets_tab_gmail",
        builder_name="build_gmail_ui",
    ),
    WidgetSettingsSectionDescriptor(
        section_id="imgur",
        button_label="Imgur",
        button_attr_name="_btn_imgur",
        container_attr_name="_imgur_container",
        builder_module="ui.tabs.widgets_tab_imgur",
        builder_name="build_imgur_ui",
        dev_feature_env="SRPSS_ENABLE_DEV",
    ),
    WidgetSettingsSectionDescriptor(
        section_id="defaults",
        button_label="Defaults",
        button_attr_name="_btn_defaults",
        container_attr_name="_defaults_container",
        method_name="_build_defaults_section",
    ),
)


def get_widget_settings_section_descriptors() -> tuple[WidgetSettingsSectionDescriptor, ...]:
    """Return the canonical WidgetsTab section registry for the current environment."""

    return tuple(
        descriptor
        for descriptor in WIDGET_SETTINGS_SECTION_DESCRIPTORS
        if descriptor.is_enabled_in_environment()
    )


@dataclass(frozen=True)
class WidgetRuntimeDescriptor:
    """Canonical runtime/capability descriptor for a widget family."""

    widget_id: str
    settings_section_id: str
    settings_prefixes: tuple[str, ...]
    startup_stage: str
    service_backed: bool = False
    anchor_dependent: bool = False
    live_refresh_handler: str | None = None
    dev_feature_env: str | None = None

    def is_enabled_in_environment(self) -> bool:
        if not self.dev_feature_env:
            return True
        return os.getenv(self.dev_feature_env, "false").lower() == "true"

    def matches_settings_key(self, setting_key: str) -> bool:
        return any(setting_key.startswith(prefix) for prefix in self.settings_prefixes)


WIDGET_RUNTIME_DESCRIPTORS: tuple[WidgetRuntimeDescriptor, ...] = (
    WidgetRuntimeDescriptor(
        widget_id="clock",
        settings_section_id="clock",
        settings_prefixes=("widgets.clock",),
        startup_stage="primary",
    ),
    WidgetRuntimeDescriptor(
        widget_id="clock2",
        settings_section_id="clock",
        settings_prefixes=("widgets.clock2",),
        startup_stage="primary",
    ),
    WidgetRuntimeDescriptor(
        widget_id="clock3",
        settings_section_id="clock",
        settings_prefixes=("widgets.clock3",),
        startup_stage="primary",
    ),
    WidgetRuntimeDescriptor(
        widget_id="weather",
        settings_section_id="weather",
        settings_prefixes=("widgets.weather",),
        startup_stage="primary",
        service_backed=True,
    ),
    WidgetRuntimeDescriptor(
        widget_id="media",
        settings_section_id="media",
        settings_prefixes=("widgets.media",),
        startup_stage="primary",
        service_backed=True,
        live_refresh_handler="_refresh_media_config",
    ),
    WidgetRuntimeDescriptor(
        widget_id="reddit",
        settings_section_id="reddit",
        settings_prefixes=("widgets.reddit",),
        startup_stage="primary",
        service_backed=True,
        live_refresh_handler="_refresh_reddit_configs",
    ),
    WidgetRuntimeDescriptor(
        widget_id="reddit2",
        settings_section_id="reddit",
        settings_prefixes=("widgets.reddit2",),
        startup_stage="primary",
        service_backed=True,
        live_refresh_handler="_refresh_reddit_configs",
    ),
    WidgetRuntimeDescriptor(
        widget_id="gmail",
        settings_section_id="gmail",
        settings_prefixes=("widgets.gmail",),
        startup_stage="primary",
        service_backed=True,
    ),
    WidgetRuntimeDescriptor(
        widget_id="imgur",
        settings_section_id="imgur",
        settings_prefixes=("widgets.imgur",),
        startup_stage="primary",
        service_backed=True,
        dev_feature_env="SRPSS_ENABLE_DEV",
    ),
    WidgetRuntimeDescriptor(
        widget_id="spotify_visualizer",
        settings_section_id="visualizers",
        settings_prefixes=("widgets.spotify_visualizer",),
        startup_stage="secondary",
        anchor_dependent=True,
        live_refresh_handler="_refresh_spotify_visualizer_config",
    ),
    WidgetRuntimeDescriptor(
        widget_id="spotify_volume",
        settings_section_id="media",
        settings_prefixes=("widgets.media",),
        startup_stage="secondary",
        anchor_dependent=True,
        service_backed=True,
        live_refresh_handler="_refresh_media_config",
    ),
    WidgetRuntimeDescriptor(
        widget_id="mute_button",
        settings_section_id="media",
        settings_prefixes=("widgets.media",),
        startup_stage="secondary",
        anchor_dependent=True,
        service_backed=True,
        live_refresh_handler="_refresh_media_config",
    ),
)


def get_widget_runtime_descriptors() -> tuple[WidgetRuntimeDescriptor, ...]:
    """Return the canonical runtime capability descriptors."""

    return tuple(
        descriptor
        for descriptor in WIDGET_RUNTIME_DESCRIPTORS
        if descriptor.is_enabled_in_environment()
    )


def get_live_refresh_handlers_for_settings_key(setting_key: str) -> tuple[str, ...]:
    """Return deduplicated live-refresh handlers for a changed settings key."""

    handlers: list[str] = []
    for descriptor in get_widget_runtime_descriptors():
        if not descriptor.live_refresh_handler:
            continue
        if not descriptor.matches_settings_key(setting_key):
            continue
        if descriptor.live_refresh_handler not in handlers:
            handlers.append(descriptor.live_refresh_handler)
    return tuple(handlers)


def get_live_refresh_handlers() -> tuple[str, ...]:
    """Return all deduplicated live-refresh handlers in canonical order."""

    handlers: list[str] = []
    for descriptor in get_widget_runtime_descriptors():
        if descriptor.live_refresh_handler and descriptor.live_refresh_handler not in handlers:
            handlers.append(descriptor.live_refresh_handler)
    return tuple(handlers)
