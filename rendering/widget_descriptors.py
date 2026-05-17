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


STANDARD_POSITION_OPTION_LABELS: tuple[str, ...] = (
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
    position_option_labels: tuple[str, ...] = STANDARD_POSITION_OPTION_LABELS
    supports_layout_edit_mode: bool = False
    supports_custom_position_slot: bool = False
    supports_layout_resize_edit: bool = False
    requires_size_reset_affordance: bool = False
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
        supports_layout_edit_mode=True,
        supports_custom_position_slot=True,
        supports_layout_resize_edit=True,
        requires_size_reset_affordance=True,
    ),
    WidgetRuntimeDescriptor(
        widget_id="clock2",
        settings_section_id="clock",
        settings_prefixes=("widgets.clock2",),
        startup_stage="primary",
        supports_layout_edit_mode=True,
        supports_custom_position_slot=True,
        supports_layout_resize_edit=True,
        requires_size_reset_affordance=True,
    ),
    WidgetRuntimeDescriptor(
        widget_id="clock3",
        settings_section_id="clock",
        settings_prefixes=("widgets.clock3",),
        startup_stage="primary",
        supports_layout_edit_mode=True,
        supports_custom_position_slot=True,
        supports_layout_resize_edit=True,
        requires_size_reset_affordance=True,
    ),
    WidgetRuntimeDescriptor(
        widget_id="weather",
        settings_section_id="weather",
        settings_prefixes=("widgets.weather",),
        startup_stage="primary",
        service_backed=True,
        supports_layout_edit_mode=True,
        supports_custom_position_slot=True,
        supports_layout_resize_edit=True,
        requires_size_reset_affordance=True,
    ),
    WidgetRuntimeDescriptor(
        widget_id="media",
        settings_section_id="media",
        settings_prefixes=("widgets.media",),
        startup_stage="primary",
        service_backed=True,
        live_refresh_handler="_refresh_media_config",
        supports_layout_edit_mode=True,
        supports_custom_position_slot=True,
        supports_layout_resize_edit=True,
        requires_size_reset_affordance=True,
    ),
    WidgetRuntimeDescriptor(
        widget_id="reddit",
        settings_section_id="reddit",
        settings_prefixes=("widgets.reddit",),
        startup_stage="primary",
        service_backed=True,
        live_refresh_handler="_refresh_reddit_configs",
        supports_layout_edit_mode=True,
        supports_custom_position_slot=True,
        supports_layout_resize_edit=True,
        requires_size_reset_affordance=True,
    ),
    WidgetRuntimeDescriptor(
        widget_id="reddit2",
        settings_section_id="reddit",
        settings_prefixes=("widgets.reddit2",),
        startup_stage="primary",
        service_backed=True,
        live_refresh_handler="_refresh_reddit_configs",
        supports_layout_edit_mode=True,
        supports_custom_position_slot=True,
        supports_layout_resize_edit=True,
        requires_size_reset_affordance=True,
    ),
    WidgetRuntimeDescriptor(
        widget_id="gmail",
        settings_section_id="gmail",
        settings_prefixes=("widgets.gmail",),
        startup_stage="primary",
        service_backed=True,
        supports_layout_edit_mode=True,
        supports_custom_position_slot=True,
        supports_layout_resize_edit=True,
        requires_size_reset_affordance=True,
    ),
    WidgetRuntimeDescriptor(
        widget_id="imgur",
        settings_section_id="imgur",
        settings_prefixes=("widgets.imgur",),
        startup_stage="primary",
        service_backed=True,
        supports_layout_edit_mode=True,
        supports_custom_position_slot=True,
        supports_layout_resize_edit=True,
        requires_size_reset_affordance=True,
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


def get_widget_runtime_descriptor(widget_id: str) -> WidgetRuntimeDescriptor | None:
    """Return the canonical runtime descriptor for one widget id."""

    for descriptor in get_widget_runtime_descriptors():
        if descriptor.widget_id == widget_id:
            return descriptor
    return None


def get_widget_position_option_labels(widget_id: str) -> tuple[str, ...]:
    """Return the canonical settings position labels for a widget family."""

    descriptor = get_widget_runtime_descriptor(widget_id)
    if descriptor is None:
        return STANDARD_POSITION_OPTION_LABELS
    return descriptor.position_option_labels


@dataclass(frozen=True)
class WidgetPreviewFieldDescriptor:
    """Descriptor for one settings-preview field read from WidgetsTab controls."""

    key: str
    attr_name: str
    reader: str = "raw"
    fallback: Any = None


def _read_preview_attr(owner: Any, field: WidgetPreviewFieldDescriptor) -> Any:
    widget = getattr(owner, field.attr_name, None)
    if widget is None:
        return field.fallback
    try:
        if field.reader == "checked":
            return bool(widget.isChecked())
        if field.reader == "value":
            return widget.value()
        if field.reader == "current_text":
            return widget.currentText()
        if field.reader == "current_text_int":
            return int(widget.currentText())
        if field.reader == "clock_display_mode":
            return "analog" if bool(widget.isChecked()) else "digital"
        return widget
    except Exception:
        return field.fallback


@dataclass(frozen=True)
class WidgetStackPreviewDescriptor:
    """Descriptor for stack-preview ownership in WidgetsTab."""

    widget_id: str
    widget_type_key: str
    status_attr_name: str
    position_attr_name: str
    monitor_attr_name: str
    fields: tuple[WidgetPreviewFieldDescriptor, ...]

    def build_preview_section(self, owner: Any) -> Dict[str, Any]:
        return {
            field.key: _read_preview_attr(owner, field)
            for field in self.fields
        }


WIDGET_STACK_PREVIEW_DESCRIPTORS: tuple[WidgetStackPreviewDescriptor, ...] = (
    WidgetStackPreviewDescriptor(
        widget_id="clock",
        widget_type_key="clock",
        status_attr_name="clock_stack_status",
        position_attr_name="clock_position",
        monitor_attr_name="clock_monitor_combo",
        fields=(
            WidgetPreviewFieldDescriptor("enabled", "clock_enabled", "checked", False),
            WidgetPreviewFieldDescriptor("display_mode", "clock_analog_mode", "clock_display_mode", "digital"),
            WidgetPreviewFieldDescriptor("position", "clock_position", "current_text", "Top Right"),
            WidgetPreviewFieldDescriptor("monitor", "clock_monitor_combo", "current_text", "ALL"),
            WidgetPreviewFieldDescriptor("font_size", "clock_font_size", "value", 48),
            WidgetPreviewFieldDescriptor("show_seconds", "clock_seconds", "checked", False),
            WidgetPreviewFieldDescriptor("show_timezone_label", "clock_show_tz", "checked", False),
        ),
    ),
    WidgetStackPreviewDescriptor(
        widget_id="clock2",
        widget_type_key="clock2",
        status_attr_name="clock2_stack_status",
        position_attr_name="clock_position",
        monitor_attr_name="clock2_monitor_combo",
        fields=(
            WidgetPreviewFieldDescriptor("enabled", "clock2_enabled", "checked", False),
            WidgetPreviewFieldDescriptor("position", "clock_position", "current_text", "Top Right"),
            WidgetPreviewFieldDescriptor("monitor", "clock2_monitor_combo", "current_text", "ALL"),
        ),
    ),
    WidgetStackPreviewDescriptor(
        widget_id="clock3",
        widget_type_key="clock3",
        status_attr_name="clock3_stack_status",
        position_attr_name="clock_position",
        monitor_attr_name="clock3_monitor_combo",
        fields=(
            WidgetPreviewFieldDescriptor("enabled", "clock3_enabled", "checked", False),
            WidgetPreviewFieldDescriptor("position", "clock_position", "current_text", "Top Right"),
            WidgetPreviewFieldDescriptor("monitor", "clock3_monitor_combo", "current_text", "ALL"),
        ),
    ),
    WidgetStackPreviewDescriptor(
        widget_id="weather",
        widget_type_key="weather",
        status_attr_name="weather_stack_status",
        position_attr_name="weather_position",
        monitor_attr_name="weather_monitor_combo",
        fields=(
            WidgetPreviewFieldDescriptor("enabled", "weather_enabled", "checked", False),
            WidgetPreviewFieldDescriptor("position", "weather_position", "current_text", "Top Left"),
            WidgetPreviewFieldDescriptor("monitor", "weather_monitor_combo", "current_text", "ALL"),
            WidgetPreviewFieldDescriptor("font_size", "weather_font_size", "value", 18),
            WidgetPreviewFieldDescriptor("show_forecast", "weather_show_forecast", "checked", False),
        ),
    ),
    WidgetStackPreviewDescriptor(
        widget_id="media",
        widget_type_key="media",
        status_attr_name="media_stack_status",
        position_attr_name="media_position",
        monitor_attr_name="media_monitor_combo",
        fields=(
            WidgetPreviewFieldDescriptor("enabled", "media_enabled", "checked", False),
            WidgetPreviewFieldDescriptor("position", "media_position", "current_text", "Bottom Right"),
            WidgetPreviewFieldDescriptor("monitor", "media_monitor_combo", "current_text", "ALL"),
            WidgetPreviewFieldDescriptor("font_size", "media_font_size", "value", 14),
            WidgetPreviewFieldDescriptor("artwork_size", "media_artwork_size", "value", 80),
        ),
    ),
    WidgetStackPreviewDescriptor(
        widget_id="reddit",
        widget_type_key="reddit",
        status_attr_name="reddit_stack_status",
        position_attr_name="reddit_position",
        monitor_attr_name="reddit_monitor_combo",
        fields=(
            WidgetPreviewFieldDescriptor("enabled", "reddit_enabled", "checked", False),
            WidgetPreviewFieldDescriptor("position", "reddit_position", "current_text", "Bottom Right"),
            WidgetPreviewFieldDescriptor("monitor", "reddit_monitor_combo", "current_text", "ALL"),
            WidgetPreviewFieldDescriptor("font_size", "reddit_font_size", "value", 18),
            WidgetPreviewFieldDescriptor("limit", "reddit_items", "current_text_int", 10),
        ),
    ),
    WidgetStackPreviewDescriptor(
        widget_id="reddit2",
        widget_type_key="reddit2",
        status_attr_name="reddit2_stack_status",
        position_attr_name="reddit2_position",
        monitor_attr_name="reddit2_monitor_combo",
        fields=(
            WidgetPreviewFieldDescriptor("enabled", "reddit2_enabled", "checked", False),
            WidgetPreviewFieldDescriptor("position", "reddit2_position", "current_text", "Top Left"),
            WidgetPreviewFieldDescriptor("monitor", "reddit2_monitor_combo", "current_text", "ALL"),
            WidgetPreviewFieldDescriptor("limit", "reddit2_items", "current_text_int", 4),
        ),
    ),
    WidgetStackPreviewDescriptor(
        widget_id="gmail",
        widget_type_key="gmail",
        status_attr_name="gmail_stack_status",
        position_attr_name="gmail_position",
        monitor_attr_name="gmail_monitor_combo",
        fields=(
            WidgetPreviewFieldDescriptor("enabled", "gmail_enabled", "checked", False),
            WidgetPreviewFieldDescriptor("position", "gmail_position", "current_text", "Top Left"),
            WidgetPreviewFieldDescriptor("monitor", "gmail_monitor_combo", "current_text", "ALL"),
            WidgetPreviewFieldDescriptor("limit", "gmail_limit", "value", 5),
        ),
    ),
)


def get_widget_stack_preview_descriptors() -> tuple[WidgetStackPreviewDescriptor, ...]:
    """Return canonical WidgetsTab stack-preview descriptors."""

    return WIDGET_STACK_PREVIEW_DESCRIPTORS


def build_widget_stack_preview_config(owner: Any) -> Dict[str, Dict[str, Any]]:
    """Build the descriptor-owned WidgetsTab stack-preview config mapping."""

    return {
        descriptor.widget_id: descriptor.build_preview_section(owner)
        for descriptor in get_widget_stack_preview_descriptors()
    }
