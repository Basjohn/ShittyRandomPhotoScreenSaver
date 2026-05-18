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

from PySide6.QtWidgets import QButtonGroup, QPushButton


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
    loader_module: str | None = None
    loader_name: str | None = None
    loader_guard_attrs: tuple[str, ...] = ()
    saver_module: str | None = None
    saver_name: str | None = None
    saver_guard_attrs: tuple[str, ...] = ()
    persisted_widget_keys: tuple[str, ...] = ()
    signal_block_attrs: tuple[str, ...] = ()
    bootstrap_in_lazy_mode: bool = False
    lazy_dependency_section_ids: tuple[str, ...] = ()
    programmatic_dependency_section_ids: tuple[str, ...] = ()
    default_selected: bool = False
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

    def resolve_loader(self) -> Callable[..., Any] | None:
        """Return the concrete settings-loader callable for this section, if any."""
        if self.loader_module and self.loader_name:
            module = import_module(self.loader_module)
            return getattr(module, self.loader_name)
        return None

    def can_load_for_owner(self, owner: Any) -> bool:
        """Return True when the owning tab has the controls required for this section loader."""
        if not self.loader_guard_attrs:
            return False
        return all(hasattr(owner, attr_name) for attr_name in self.loader_guard_attrs)

    def resolve_saver(self) -> Callable[..., Any] | None:
        """Return the concrete settings-saver callable for this section, if any."""
        if self.saver_module and self.saver_name:
            module = import_module(self.saver_module)
            return getattr(module, self.saver_name)
        return None

    def can_save_for_owner(self, owner: Any) -> bool:
        """Return True when the owning tab has the controls required for this section saver."""
        if not self.saver_guard_attrs:
            return False
        return all(hasattr(owner, attr_name) for attr_name in self.saver_guard_attrs)


WIDGET_SETTINGS_SECTION_DESCRIPTORS: tuple[WidgetSettingsSectionDescriptor, ...] = (
    WidgetSettingsSectionDescriptor(
        section_id="clock",
        button_label="Clocks",
        button_attr_name="_btn_clocks",
        container_attr_name="_clocks_container",
        builder_module="ui.tabs.widgets_tab_clock",
        builder_name="build_clock_ui",
        loader_module="ui.tabs.widgets_tab_clock",
        loader_name="load_clock_settings",
        loader_guard_attrs=("clock_enabled",),
        saver_module="ui.tabs.widgets_tab_clock",
        saver_name="save_clock_settings",
        saver_guard_attrs=("clock_enabled",),
        persisted_widget_keys=("clock", "clock2", "clock3"),
        signal_block_attrs=(
            "clock_enabled", "clock_format", "clock_seconds", "clock_timezone",
            "clock_show_tz", "clock_position", "clock_font_combo", "clock_font_size",
            "clock_margin", "clock_show_background", "clock_bg_opacity",
            "clock_border_opacity", "clock_monitor_combo",
            "clock2_enabled", "clock2_timezone", "clock2_monitor_combo",
            "clock3_enabled", "clock3_timezone", "clock3_monitor_combo",
        ),
        default_selected=True,
    ),
    WidgetSettingsSectionDescriptor(
        section_id="weather",
        button_label="Weather",
        button_attr_name="_btn_weather",
        container_attr_name="_weather_container",
        builder_module="ui.tabs.widgets_tab_weather",
        builder_name="build_weather_ui",
        loader_module="ui.tabs.widgets_tab_weather",
        loader_name="load_weather_settings",
        loader_guard_attrs=("weather_enabled",),
        saver_module="ui.tabs.widgets_tab_weather",
        saver_name="save_weather_settings",
        saver_guard_attrs=("weather_enabled",),
        persisted_widget_keys=("weather",),
        signal_block_attrs=(
            "weather_enabled", "weather_location", "weather_position",
            "weather_font_combo", "weather_font_size", "weather_show_forecast",
            "weather_show_background", "weather_bg_opacity", "weather_border_opacity",
            "weather_margin", "weather_monitor_combo",
        ),
    ),
    WidgetSettingsSectionDescriptor(
        section_id="media",
        button_label="Media",
        button_attr_name="_btn_media",
        container_attr_name="_media_container",
        builder_module="ui.tabs.widgets_tab_media",
        builder_name="build_media_ui",
        loader_module="ui.tabs.widgets_tab_media",
        loader_name="load_media_settings",
        loader_guard_attrs=("media_enabled", "vis_enabled_checkbox"),
        saver_module="ui.tabs.widgets_tab_media",
        saver_name="save_media_settings",
        saver_guard_attrs=("media_enabled", "vis_enabled_checkbox"),
        persisted_widget_keys=("media", "spotify_visualizer"),
        signal_block_attrs=(
            "media_enabled", "media_position", "media_monitor_combo",
            "media_font_combo", "media_font_size", "media_margin",
            "media_show_background", "media_bg_opacity", "media_border_opacity",
            "media_artwork_size", "media_rounded_artwork",
            "media_show_header_frame", "media_show_controls",
            "media_spotify_volume_enabled",
        ),
        lazy_dependency_section_ids=("visualizers",),
        programmatic_dependency_section_ids=("visualizers", "defaults"),
    ),
    WidgetSettingsSectionDescriptor(
        section_id="visualizers",
        button_label="Visualizers",
        button_attr_name="_btn_visualizers",
        container_attr_name="_visualizers_container",
        builder_module="ui.tabs.widgets_tab_media",
        builder_name="build_visualizers_ui",
        lazy_dependency_section_ids=("media",),
        programmatic_dependency_section_ids=("media", "defaults"),
    ),
    WidgetSettingsSectionDescriptor(
        section_id="reddit",
        button_label="Reddit",
        button_attr_name="_btn_reddit",
        container_attr_name="_reddit_container",
        builder_module="ui.tabs.widgets_tab_reddit",
        builder_name="build_reddit_ui",
        loader_module="ui.tabs.widgets_tab_reddit",
        loader_name="load_reddit_settings",
        loader_guard_attrs=("reddit_enabled",),
        saver_module="ui.tabs.widgets_tab_reddit",
        saver_name="save_reddit_settings",
        saver_guard_attrs=("reddit_enabled",),
        persisted_widget_keys=("reddit", "reddit2"),
        signal_block_attrs=(
            "reddit_enabled", "reddit_subreddit", "reddit_items",
            "reddit_position", "reddit_monitor_combo",
            "reddit_font_combo", "reddit_font_size", "reddit_margin",
            "reddit_header_logo_px_adjust",
            "reddit_show_background", "reddit_show_separators",
            "reddit_show_refresh_spiral",
            "reddit_bg_opacity", "reddit_border_opacity",
            "reddit2_enabled", "reddit2_subreddit", "reddit2_items",
            "reddit2_position", "reddit2_monitor_combo",
            "reddit_exit_on_click",
        ),
    ),
    WidgetSettingsSectionDescriptor(
        section_id="gmail",
        button_label="Gmail",
        button_attr_name="_btn_gmail",
        container_attr_name="_gmail_container",
        builder_module="ui.tabs.widgets_tab_gmail",
        builder_name="build_gmail_ui",
        loader_module="ui.tabs.widgets_tab_gmail",
        loader_name="load_gmail_settings",
        loader_guard_attrs=("gmail_enabled",),
        saver_module="ui.tabs.widgets_tab_gmail",
        saver_name="save_gmail_settings",
        saver_guard_attrs=("gmail_enabled",),
        persisted_widget_keys=("gmail",),
    ),
    WidgetSettingsSectionDescriptor(
        section_id="imgur",
        button_label="Imgur",
        button_attr_name="_btn_imgur",
        container_attr_name="_imgur_container",
        builder_module="ui.tabs.widgets_tab_imgur",
        builder_name="build_imgur_ui",
        loader_module="ui.tabs.widgets_tab_imgur",
        loader_name="load_imgur_settings",
        loader_guard_attrs=("imgur_enabled",),
        saver_module="ui.tabs.widgets_tab_imgur",
        saver_name="save_imgur_settings",
        saver_guard_attrs=("imgur_enabled",),
        persisted_widget_keys=("imgur",),
        signal_block_attrs=(
            "imgur_enabled", "imgur_position", "imgur_monitor_combo",
            "imgur_update_interval", "imgur_grid_rows", "imgur_grid_cols",
            "imgur_show_background", "imgur_bg_opacity", "imgur_border_opacity",
            "imgur_margin",
        ),
        dev_feature_env="SRPSS_ENABLE_DEV",
    ),
    WidgetSettingsSectionDescriptor(
        section_id="defaults",
        button_label="Defaults",
        button_attr_name="_btn_defaults",
        container_attr_name="_defaults_container",
        builder_module="ui.tabs.widgets_tab_defaults",
        builder_name="build_defaults_ui",
        loader_module="ui.tabs.widgets_tab_defaults",
        loader_name="load_defaults_settings",
        loader_guard_attrs=(
            "widget_shadows_enabled",
            "widget_text_shadows_enabled",
            "widget_header_shadows_enabled",
            "card_border_width_spin",
        ),
        saver_module="ui.tabs.widgets_tab_defaults",
        saver_name="save_defaults_settings",
        saver_guard_attrs=(
            "widget_shadows_enabled",
            "widget_text_shadows_enabled",
            "widget_header_shadows_enabled",
            "card_border_width_spin",
        ),
        persisted_widget_keys=("shadows", "global"),
        signal_block_attrs=(
            "widget_shadows_enabled",
            "widget_text_shadows_enabled",
            "widget_header_shadows_enabled",
            "card_border_width_spin",
        ),
        bootstrap_in_lazy_mode=True,
    ),
)


def get_widget_settings_section_descriptors() -> tuple[WidgetSettingsSectionDescriptor, ...]:
    """Return the canonical WidgetsTab section registry for the current environment."""

    return tuple(
        descriptor
        for descriptor in WIDGET_SETTINGS_SECTION_DESCRIPTORS
        if descriptor.is_enabled_in_environment()
    )


def build_widget_section_buttons(
    owner: Any,
    button_group: QButtonGroup,
    button_style: str,
    descriptors: tuple[WidgetSettingsSectionDescriptor, ...] | None = None,
) -> tuple[QPushButton, ...]:
    """Create descriptor-owned WidgetsTab section buttons."""

    descriptor_iter = descriptors if descriptors is not None else get_widget_settings_section_descriptors()
    buttons: list[QPushButton] = []
    for idx, descriptor in enumerate(descriptor_iter):
        button = QPushButton(descriptor.button_label)
        button.setCheckable(True)
        button.setStyleSheet(button_style)
        setattr(owner, descriptor.button_attr_name, button)
        button_group.addButton(button, idx)
        buttons.append(button)
    return tuple(buttons)


def get_widget_section_index_map(
    descriptors: tuple[WidgetSettingsSectionDescriptor, ...] | None = None,
) -> dict[str, int]:
    """Return section id -> subtab index mapping for the active descriptor set."""

    descriptor_iter = descriptors if descriptors is not None else get_widget_settings_section_descriptors()
    return {
        descriptor.section_id: idx
        for idx, descriptor in enumerate(descriptor_iter)
    }


def collect_widget_section_containers(
    owner: Any,
    descriptors: tuple[WidgetSettingsSectionDescriptor, ...] | None = None,
) -> tuple[Any, ...]:
    """Collect section container widgets from an owner using descriptor metadata."""

    descriptor_iter = descriptors if descriptors is not None else get_widget_settings_section_descriptors()
    return tuple(
        getattr(owner, descriptor.container_attr_name, None)
        for descriptor in descriptor_iter
    )


def get_default_widget_section_index(
    descriptors: tuple[WidgetSettingsSectionDescriptor, ...] | None = None,
) -> int:
    """Return the descriptor-owned default WidgetsTab section index."""

    descriptor_iter = descriptors if descriptors is not None else get_widget_settings_section_descriptors()
    for idx, descriptor in enumerate(descriptor_iter):
        if descriptor.default_selected:
            return idx
    return 0


def resolve_widget_section_index_from_view_state(
    state: Mapping[str, Any] | None,
    descriptors: tuple[WidgetSettingsSectionDescriptor, ...] | None = None,
) -> int:
    """Resolve a WidgetsTab subtab index from persisted view state.

    Prefer stable descriptor-owned ``subtab_id`` when available, while still
    accepting the legacy numeric ``subtab`` field for compatibility.
    """

    descriptor_iter = descriptors if descriptors is not None else get_widget_settings_section_descriptors()
    if not descriptor_iter:
        return 0

    state_map = state if isinstance(state, Mapping) else {}
    index_map = get_widget_section_index_map(descriptor_iter)
    subtab_id = state_map.get("subtab_id")
    if isinstance(subtab_id, str) and subtab_id in index_map:
        return index_map[subtab_id]

    subtab = state_map.get("subtab", get_default_widget_section_index(descriptor_iter))
    try:
        subtab_index = int(subtab)
    except (TypeError, ValueError):
        subtab_index = 0

    if subtab_index < 0:
        subtab_index = 0
    if subtab_index >= len(descriptor_iter):
        subtab_index = len(descriptor_iter) - 1
    return subtab_index


def get_widget_lazy_bootstrap_indices(
    initial_index: int,
    descriptors: tuple[WidgetSettingsSectionDescriptor, ...] | None = None,
) -> tuple[int, ...]:
    """Return descriptor-owned lazy-build bootstrap order.

    Some sections, such as Defaults, need to exist even in lazy mode because
    shared settings load/save/state plumbing depends on their controls.
    """

    descriptor_iter = descriptors if descriptors is not None else get_widget_settings_section_descriptors()
    ordered: list[int] = [
        idx for idx, descriptor in enumerate(descriptor_iter)
        if descriptor.bootstrap_in_lazy_mode
    ]
    if 0 <= initial_index < len(descriptor_iter) and initial_index not in ordered:
        ordered.append(initial_index)
    return tuple(ordered)


def get_widget_lazy_dependency_indices(
    target_index: int,
    descriptors: tuple[WidgetSettingsSectionDescriptor, ...] | None = None,
) -> tuple[int, ...]:
    """Return descriptor-owned lazy-build dependency indices for one section."""

    descriptor_iter = descriptors if descriptors is not None else get_widget_settings_section_descriptors()
    if target_index < 0 or target_index >= len(descriptor_iter):
        return ()

    index_map = get_widget_section_index_map(descriptor_iter)
    ordered: list[int] = []
    seen: set[int] = set()

    def _visit(idx: int) -> None:
        if idx in seen or idx < 0 or idx >= len(descriptor_iter):
            return
        seen.add(idx)
        descriptor = descriptor_iter[idx]
        for section_id in descriptor.lazy_dependency_section_ids:
            dep_idx = index_map.get(section_id)
            if dep_idx is None:
                continue
            _visit(dep_idx)
            if dep_idx != target_index and dep_idx not in ordered:
                ordered.append(dep_idx)

    _visit(target_index)
    return tuple(ordered)


def get_widget_programmatic_dependency_indices(
    target_section_ids: tuple[str, ...],
    descriptors: tuple[WidgetSettingsSectionDescriptor, ...] | None = None,
) -> tuple[int, ...]:
    """Return descriptor-owned programmatic build indices for lazy WidgetsTab access.

    This is intentionally narrower than "build everything". It lets callers
    materialize only the sections they truly expect, together with any explicit
    descriptor-owned lazy/programmatic dependencies, instead of relying on
    section order or a handwritten hardcoded set.
    """

    descriptor_iter = descriptors if descriptors is not None else get_widget_settings_section_descriptors()
    index_map = get_widget_section_index_map(descriptor_iter)
    ordered: list[int] = []
    seen: set[int] = set()

    def _append(idx: int) -> None:
        if idx < 0 or idx >= len(descriptor_iter) or idx in seen:
            return
        seen.add(idx)
        ordered.append(idx)

    for section_id in target_section_ids:
        target_idx = index_map.get(section_id)
        if target_idx is None:
            continue
        descriptor = descriptor_iter[target_idx]
        dependency_ids = descriptor.programmatic_dependency_section_ids or descriptor.lazy_dependency_section_ids
        for dep_id in dependency_ids:
            dep_idx = index_map.get(dep_id)
            if dep_idx is not None:
                _append(dep_idx)
        _append(target_idx)

    return tuple(ordered)


def get_widget_section_signal_block_attrs() -> tuple[str, ...]:
    """Return canonical WidgetsTab signal-block attrs for descriptor-owned sections."""

    attrs: list[str] = []
    for descriptor in get_widget_settings_section_descriptors():
        for attr_name in descriptor.signal_block_attrs:
            if attr_name not in attrs:
                attrs.append(attr_name)
    return tuple(attrs)


def collect_widget_section_signal_block_targets(
    owner: Any,
    *,
    extra_attr_names: tuple[str, ...] = (),
) -> tuple[Any, ...]:
    """Return deduplicated signal-block-capable controls for descriptor-owned sections.

    `WidgetsTab` still owns genuinely special signal-block groups such as
    Gmail-specific control buckets, but standard section signal blocking should
    come through this descriptor-owned helper instead of repeating attribute
    scans inline at each load site.
    """

    targets: list[Any] = []
    seen_ids: set[int] = set()
    attr_names = list(get_widget_section_signal_block_attrs())
    attr_names.extend(extra_attr_names)

    for attr_name in attr_names:
        widget = getattr(owner, attr_name, None)
        if widget is None or not hasattr(widget, "blockSignals"):
            continue
        widget_id = id(widget)
        if widget_id in seen_ids:
            continue
        seen_ids.add(widget_id)
        targets.append(widget)

    return tuple(targets)


def load_widget_sections(
    owner: Any,
    widgets_config: Mapping[str, Any],
    descriptors: tuple[WidgetSettingsSectionDescriptor, ...] | None = None,
) -> None:
    """Run descriptor-owned WidgetsTab section loaders for sections present on the owner."""

    descriptor_iter = descriptors if descriptors is not None else get_widget_settings_section_descriptors()
    for descriptor in descriptor_iter:
        if not descriptor.can_load_for_owner(owner):
            continue
        loader = descriptor.resolve_loader()
        if loader is None:
            continue
        loader(owner, widgets_config)


def collect_widget_section_save_results(
    owner: Any,
    existing_widgets: Mapping[str, Any],
    descriptors: tuple[WidgetSettingsSectionDescriptor, ...] | None = None,
) -> Dict[str, Any]:
    """Collect descriptor-owned WidgetsTab section save results, preserving unbuilt sections."""

    results: Dict[str, Any] = {}
    descriptor_iter = descriptors if descriptors is not None else get_widget_settings_section_descriptors()

    for descriptor in descriptor_iter:
        keys = descriptor.persisted_widget_keys
        if not keys:
            continue

        if descriptor.can_save_for_owner(owner):
            saver = descriptor.resolve_saver()
            if saver is None:
                continue
            result = saver(owner)
            if len(keys) == 1:
                results[keys[0]] = result
            else:
                if not isinstance(result, tuple) or len(result) != len(keys):
                    raise ValueError(
                        f"Saver for section {descriptor.section_id} returned unexpected payload shape"
                    )
                for key_name, value in zip(keys, result):
                    results[key_name] = value
            continue

        for key_name in keys:
            existing_value = existing_widgets.get(key_name, {})
            if isinstance(existing_value, Mapping):
                results[key_name] = dict(existing_value)
            else:
                results[key_name] = existing_value

    return results


def apply_widget_section_save_results(
    widgets_config: Dict[str, Any],
    section_results: Mapping[str, Any],
    *,
    exclude_keys: tuple[str, ...] = (),
    descriptors: tuple[WidgetSettingsSectionDescriptor, ...] | None = None,
) -> Dict[str, Any]:
    """Apply descriptor-owned save results back into a widgets config mapping.

    This keeps standard section persistence ownership aligned with the same
    descriptor registry that already owns the build/load/save routing. Callers
    can exclude genuinely special keys, such as visualizer payloads that still
    need custom merge semantics.
    """

    exclude = set(exclude_keys)
    descriptor_iter = descriptors if descriptors is not None else get_widget_settings_section_descriptors()

    for descriptor in descriptor_iter:
        for key_name in descriptor.persisted_widget_keys:
            if key_name in exclude or key_name not in section_results:
                continue
            widgets_config[key_name] = section_results[key_name]

    return widgets_config


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
    service_runtime_contracts: tuple[str, ...] = ()
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

    def supports_service_runtime_contract(self, contract_name: str) -> bool:
        return contract_name in self.service_runtime_contracts


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
        service_runtime_contracts=(
            "single_shot_timer_reuse",
            "timer_stop_cleanup",
        ),
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
        service_runtime_contracts=(
            "transition_probe",
            "single_shot_timer_reuse",
            "deferred_refresh",
            "deferred_result",
            "spinner_suspend",
            "fetch_guard",
            "manual_refresh",
            "visible_fallback",
            "timer_stop_cleanup",
        ),
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
        service_runtime_contracts=(
            "transition_probe",
            "single_shot_timer_reuse",
            "deferred_refresh",
            "deferred_result",
            "spinner_suspend",
            "fetch_guard",
            "manual_refresh",
            "visible_fallback",
            "timer_stop_cleanup",
        ),
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
        service_runtime_contracts=(
            "transition_probe",
            "single_shot_timer_reuse",
            "deferred_refresh",
            "deferred_result",
            "spinner_suspend",
            "fetch_guard",
            "manual_refresh",
            "visible_fallback",
            "timer_stop_cleanup",
        ),
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


def get_service_runtime_contracts(widget_id: str) -> tuple[str, ...]:
    """Return the descriptor-owned shared service-runtime contracts for a widget."""

    descriptor = get_widget_runtime_descriptor(widget_id)
    if descriptor is None:
        return ()
    return descriptor.service_runtime_contracts


def get_widget_ids_for_service_runtime_contract(contract_name: str) -> tuple[str, ...]:
    """Return canonical widget ids that participate in one shared service-runtime contract."""

    return tuple(
        descriptor.widget_id
        for descriptor in get_widget_runtime_descriptors()
        if descriptor.supports_service_runtime_contract(contract_name)
    )


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


@dataclass(frozen=True)
class WidgetStackStatusTarget:
    """Resolved WidgetsTab stack-status target for one descriptor-owned widget."""

    widget_type_key: str
    status_label: Any
    position_value: str
    monitor_value: str


@dataclass(frozen=True)
class WidgetDefaultInitDescriptor:
    """Descriptor for one standard WidgetsTab default-backed attribute."""

    attr_name: str
    section: str
    key: str
    value_kind: str
    fallback: Any


WIDGET_DEFAULT_INIT_DESCRIPTORS: tuple[WidgetDefaultInitDescriptor, ...] = (
    WidgetDefaultInitDescriptor("_global_card_border_width", "global", "card_border_width_px", "int", 3),
    WidgetDefaultInitDescriptor("_clock_color", "clock", "color", "color", [255, 255, 255, 230]),
    WidgetDefaultInitDescriptor("_weather_color", "weather", "color", "color", [255, 255, 255, 230]),
    WidgetDefaultInitDescriptor("_clock_border_color", "clock", "border_color", "color", [128, 128, 128, 255]),
    WidgetDefaultInitDescriptor("_clock_bg_color", "clock", "bg_color", "color", [64, 64, 64, 255]),
    WidgetDefaultInitDescriptor("_weather_bg_color", "weather", "bg_color", "color", [64, 64, 64, 255]),
    WidgetDefaultInitDescriptor("_weather_border_color", "weather", "border_color", "color", [128, 128, 128, 255]),
    WidgetDefaultInitDescriptor("_media_color", "media", "color", "color", [255, 255, 255, 230]),
    WidgetDefaultInitDescriptor("_media_bg_color", "media", "bg_color", "color", [64, 64, 64, 255]),
    WidgetDefaultInitDescriptor("_media_border_color", "media", "border_color", "color", [128, 128, 128, 255]),
    WidgetDefaultInitDescriptor("_media_volume_fill_color", "media", "spotify_volume_fill_color", "color", [66, 66, 66, 255]),
    WidgetDefaultInitDescriptor("_spotify_vis_fill_color", "spotify_visualizer", "bar_fill_color", "color", [255, 255, 255, 230]),
    WidgetDefaultInitDescriptor("_spotify_vis_border_color", "spotify_visualizer", "bar_border_color", "color", [255, 255, 255, 230]),
    WidgetDefaultInitDescriptor("_reddit_color", "reddit", "color", "color", [255, 255, 255, 230]),
    WidgetDefaultInitDescriptor("_reddit_bg_color", "reddit", "bg_color", "color", [64, 64, 64, 255]),
    WidgetDefaultInitDescriptor("_reddit_border_color", "reddit", "border_color", "color", [128, 128, 128, 255]),
    WidgetDefaultInitDescriptor("_gmail_color", "gmail", "color", "color", [255, 255, 255, 230]),
    WidgetDefaultInitDescriptor("_gmail_bg_color", "gmail", "bg_color", "color", [35, 35, 35, 255]),
    WidgetDefaultInitDescriptor("_gmail_border_color", "gmail", "border_color", "color", [255, 255, 255, 255]),
    WidgetDefaultInitDescriptor("_gmail_separator_color", "gmail", "separator_color", "color", [200, 200, 200, 40]),
    WidgetDefaultInitDescriptor("_gmail_boundary_separator_color", "gmail", "boundary_separator_color", "color", [180, 180, 180, 80]),
    WidgetDefaultInitDescriptor("_imgur_color", "imgur", "color", "color", [255, 255, 255, 230]),
    WidgetDefaultInitDescriptor("_imgur_bg_color", "imgur", "bg_color", "color", [35, 35, 35, 255]),
    WidgetDefaultInitDescriptor("_imgur_border_color", "imgur", "border_color", "color", [255, 255, 255, 255]),
    WidgetDefaultInitDescriptor("_media_artwork_size", "media", "artwork_size", "int", 200),
)


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


def get_widget_default_init_descriptors() -> tuple[WidgetDefaultInitDescriptor, ...]:
    """Return canonical WidgetsTab default-backed attribute descriptors."""

    return WIDGET_DEFAULT_INIT_DESCRIPTORS


def build_widget_stack_preview_config(owner: Any) -> Dict[str, Dict[str, Any]]:
    """Build the descriptor-owned WidgetsTab stack-preview config mapping."""

    return {
        descriptor.widget_id: descriptor.build_preview_section(owner)
        for descriptor in get_widget_stack_preview_descriptors()
    }


def collect_widget_stack_status_targets(owner: Any) -> tuple[WidgetStackStatusTarget, ...]:
    """Return descriptor-owned stack-status targets present on the owner."""

    targets: list[WidgetStackStatusTarget] = []
    for descriptor in get_widget_stack_preview_descriptors():
        status_label = getattr(owner, descriptor.status_attr_name, None)
        pos_combo = getattr(owner, descriptor.position_attr_name, None)
        mon_combo = getattr(owner, descriptor.monitor_attr_name, None)
        if status_label is None or pos_combo is None or mon_combo is None:
            continue
        targets.append(
            WidgetStackStatusTarget(
                widget_type_key=descriptor.widget_type_key,
                status_label=status_label,
                position_value=pos_combo.currentText(),
                monitor_value=mon_combo.currentText(),
            )
        )
    return tuple(targets)
