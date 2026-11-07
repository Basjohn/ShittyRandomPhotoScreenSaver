"""Shared scaffold helpers for visualizer mode UI builders."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from ui.tabs import shared_styles
from ui.tabs.shared_styles import add_swatch_label
from ui.widgets.continuous_border import BucketToggle
from ui.widgets.bucket_tree import BUCKET_CHILD_INDENT, BucketTreeBody

if TYPE_CHECKING:
    from ui.tabs.visualizer_settings_context import VisualizerSettingsContextMixin


@dataclass
class ModeBody:
    container: QWidget
    layout: QVBoxLayout
    preset_slider: object


def bind_setting_signal(
    tab: "VisualizerSettingsContextMixin",
    signal: Any,
    *,
    updater: Callable[..., None] | None = None,
    auto_switch: bool = False,
) -> None:
    """Wire a control signal into the shared visualizer save flow."""
    if updater is not None:
        signal.connect(updater)
    if auto_switch:
        signal.connect(lambda *_args: tab._force_visualizer_preset_to_custom())
    signal.connect(tab._save_settings)


def bind_color_button(
    tab: "VisualizerSettingsContextMixin",
    button: Any,
    attr_name: str,
    *,
    auto_switch: bool = False,
    initial_color: Any = None,
) -> None:
    """Bind a color swatch button to a tab attribute and save flow."""
    if initial_color is not None:
        button.set_color(initial_color)

    def _on_color(color: Any) -> None:
        setattr(tab, attr_name, color)
        if auto_switch:
            tab._force_visualizer_preset_to_custom()
        tab._save_settings()

    button.color_changed.connect(_on_color)


def add_builder_swatch_row(
    parent_layout: QVBoxLayout,
    label_text: str,
    *,
    label_width: int,
) -> tuple[QWidget, QHBoxLayout, QLabel]:
    """Create a standard color-swatch row with the shared visualizer spacing."""
    row_widget = QWidget()
    row_layout = QHBoxLayout(row_widget)
    row_layout.setContentsMargins(0, 8, 0, 8)
    row_layout.setSpacing(12)
    label = add_swatch_label(row_layout, label_text, label_width)
    content = QHBoxLayout()
    content.setContentsMargins(0, 0, 0, 0)
    content.setSpacing(12)
    row_layout.addLayout(content, 1)
    parent_layout.addWidget(row_widget)
    return row_widget, content, label


def _build_collapsible_bucket_core(
    tab: "VisualizerSettingsContextMixin",
    target_layout: QVBoxLayout,
    *,
    mode_provider: Callable[[], str],
    host_mode_key: str,
    bucket_key: str,
    title: str,
    helper_text: str,
    initial_expanded: bool | None = None,
) -> tuple[QWidget, QVBoxLayout, QToolButton]:
    """Create one Visualizer Custom bucket using the shared accordion contract."""

    host = QWidget()
    host.setObjectName(f"{host_mode_key}_bucket_{bucket_key}")
    host.setProperty("bucketTitle", title)

    host_layout = QVBoxLayout(host)
    host_layout.setContentsMargins(0, 0, 0, 0)
    host_layout.setSpacing(8)

    # Stable accessory buckets are constructed before any lazy mode body exists.
    # Their active mode may not own this bucket at all (for example Bubble does
    # not own Bar Appearance, and Sphere does not own Rainbow).  In that case
    # the caller supplies an inert bootstrap state; the real per-mode state is
    # applied synchronously when the accessory is placed into a compatible body.
    mode = str(mode_provider()).strip().lower()
    expanded = (
        bool(tab.get_visualizer_bucket_state(mode, bucket_key))
        if initial_expanded is None
        else bool(initial_expanded)
    )

    toggle_row = QHBoxLayout()
    toggle_row.setContentsMargins(0, 0, 0, 0)
    toggle_row.setSpacing(8)

    toggle = BucketToggle()
    toggle.setText(title)
    toggle.setCheckable(True)
    toggle.setChecked(expanded)
    toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
    toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    toggle.setAutoRaise(True)
    toggle_row.addWidget(toggle)
    toggle_row.addStretch()
    host_layout.addLayout(toggle_row)

    helper = QLabel(helper_text)
    helper.setProperty("class", "adv-helper")
    shared_styles.apply_shared_label_style(helper, "ADV_HELPER_LABEL_STYLE")
    helper.setWordWrap(True)
    host_layout.addWidget(helper)

    body = BucketTreeBody()
    toggle._srpss_bucket_body = body
    body_layout = QVBoxLayout(body)
    body_layout.setContentsMargins(BUCKET_CHILD_INDENT, 0, 0, 0)
    body_layout.setSpacing(12)
    host_layout.addWidget(body)

    def _apply_visual_state(checked: bool) -> None:
        toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        body.setVisible(checked)
        helper.setVisible(not checked)

    shared_styles.bind_bucket_accordion(
        toggle,
        scope_owner=tab,
        apply_visual_state=_apply_visual_state,
        scope_key=lambda: ("visualizer", str(mode_provider()).strip().lower()),
    )

    def _apply_state(checked: bool) -> None:
        if checked:
            shared_styles.close_bucket_accordion_peers(toggle)
            shared_styles.close_unrelated_settings_buckets(toggle)
        _apply_visual_state(checked)
        setter = getattr(tab, "set_visualizer_bucket_state", None)
        if callable(setter):
            setter(str(mode_provider()).strip().lower(), bucket_key, checked)

    toggle.toggled.connect(_apply_state)
    _apply_visual_state(expanded)

    target_layout.addWidget(host)
    return host, body_layout, toggle


def build_collapsible_bucket(
    tab: "VisualizerSettingsContextMixin",
    target_layout: QVBoxLayout,
    *,
    mode_key: str,
    bucket_key: str,
    title: str,
    helper_text: str,
) -> tuple[QWidget, QVBoxLayout]:
    """Create a persisted Visualizer Custom bucket for one canonical mode."""

    host, body_layout, _toggle = _build_collapsible_bucket_core(
        tab,
        target_layout,
        mode_provider=lambda _mode=mode_key: _mode,
        host_mode_key=mode_key,
        bucket_key=bucket_key,
        title=title,
        helper_text=helper_text,
    )
    return host, body_layout


def build_dynamic_collapsible_bucket(
    tab: "VisualizerSettingsContextMixin",
    target_layout: QVBoxLayout,
    *,
    mode_provider: Callable[[], str],
    host_mode_key: str,
    bucket_key: str,
    title: str,
    helper_text: str,
) -> tuple[QWidget, QVBoxLayout, QToolButton]:
    """Create a stable accessory bucket whose persistence follows active mode."""

    return _build_collapsible_bucket_core(
        tab,
        target_layout,
        mode_provider=mode_provider,
        host_mode_key=host_mode_key,
        bucket_key=bucket_key,
        title=title,
        helper_text=helper_text,
        # Dynamic accessories begin parked and hidden.  Do not consult the
        # currently persisted mode here: it may not own this accessory.
        # _place_custom_accessories() applies the canonical state once the
        # accessory is attached to a compatible lazy body.
        initial_expanded=False,
    )


def build_mode_body(
    tab: "VisualizerSettingsContextMixin",
    parent_layout: QVBoxLayout,
    *,
    mode_key: str,
    settings_container_attr: str,
    preset_slider_attr: str,
) -> ModeBody:
    """Build a mode's Settings body: its preset row and, where the mode has one, its 3D Detail row.

    Nothing else is built here: every mode is edited in its Studio, and the body's values live in the mode's
    section-lazy value cache (``ui/tabs/media/spec_mode_builder.py``), never in hidden QWidgets.
    """
    from ui.tabs.media.preset_slider import VisualizerPresetSlider

    body_object_name = f"visualizer_mode_body_{mode_key}"
    # A failed lazy-body construction must never leave a visible orphan behind.
    # Normal construction is cached by VisualizerModeBodyHost, so finding an
    # existing direct child with this marker means a previous factory attempt
    # failed before it could be committed. Remove that stale presentation body
    # before trying again; authored settings/presets live outside the QWidget.
    stale_bodies = []
    for index in range(parent_layout.count()):
        item = parent_layout.itemAt(index)
        candidate = item.widget() if item is not None else None
        if candidate is not None and candidate.objectName() == body_object_name:
            stale_bodies.append(candidate)
    for stale in stale_bodies:
        parent_layout.removeWidget(stale)
        stale.hide()
        stale.deleteLater()

    container = QWidget()
    container.setObjectName(body_object_name)
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    setattr(tab, settings_container_attr, container)

    preset_slider = VisualizerPresetSlider(mode_key)
    preset_slider.preset_changed.connect(lambda idx: tab._on_visualizer_preset_changed(mode_key, idx))
    setattr(tab, preset_slider_attr, preset_slider)
    layout.addWidget(preset_slider)

    from core.settings.scene3d_quality import scene3d_entry_key
    from ui.tabs.scene3d_tab import Scene3DQualityControls, scene3d_quality_rows
    quality_rows = scene3d_quality_rows()
    quality_key = scene3d_entry_key(mode_key)
    if quality_key in quality_rows:
        quality = Scene3DQualityControls(tab._settings, (quality_rows[quality_key],))
        quality.setObjectName(f"{mode_key}_quality_controls")
        layout.addWidget(quality)
        setattr(tab, f"_{mode_key}_quality_controls", quality)

    parent_layout.addWidget(container)
    return ModeBody(container=container, layout=layout, preset_slider=preset_slider)
