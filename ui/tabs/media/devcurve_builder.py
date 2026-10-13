"""Spline Curve visualizer UI builder."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QButtonGroup, QCheckBox, QLabel, QPushButton, QSlider, QVBoxLayout

from ui.styled_popup import ColorSwatchButton
from ui.tabs.media.builder_scaffold import (
    add_builder_swatch_row,
    bind_setting_signal,
)
from ui.tabs import shared_styles
from ui.tabs.shared_styles import add_aligned_row, add_aligned_row_widget
if TYPE_CHECKING:
    from ui.tabs.visualizer_settings_context import VisualizerSettingsContextMixin


LABEL_WIDTH = 150
_LAYER_ORDER = ("bass", "vocals", "mids", "transients")
_LAYER_LABEL = {"bass": "Bass", "vocals": "Vocals", "mids": "Mids", "transients": "Transients"}
_TOOLTIP_LAYER_BUTTON = "Pick the active layer to edit its spline shape, color, and per-layer controls."
_TOOLTIP_LAYER_COLOR = "Color for the currently selected active layer."
_TOOLTIP_LAYER_OUTLINE_COLOR = "Outline color for the active layer. Outline alpha is always fully opaque."
_TOOLTIP_LAYER_OUTLINE_WIDTH = "Outline thickness for the active layer."
_TOOLTIP_LAYER_ENABLED = "Enable/disable this layer's rendering and audio response."
_TOOLTIP_LAYER_ALPHA = "Fill opacity for this layer only."
_TOOLTIP_LAYER_OFFSET = "Vertical lane offset for this layer before audio deformation."
_TOOLTIP_LAYER_ORDER = "Layer stack order. Higher numbers render on top of lower numbers."

def _row(parent_layout: QVBoxLayout, label_text: str):
    content, _ = add_aligned_row(parent_layout, label_text, label_width=LABEL_WIDTH, wrap=True)
    return content


def _row_widget(parent_layout: QVBoxLayout, label_text: str):
    row_widget, content, _ = add_aligned_row_widget(parent_layout, label_text, label_width=LABEL_WIDTH, wrap=True)
    return row_widget, content


def _add_slider(
    tab: "VisualizerSettingsContextMixin",
    parent_layout: QVBoxLayout,
    *,
    attr: str,
    label: str,
    min_v: int,
    max_v: int,
    value: int,
    fmt,
    auto_switch: bool = True,
):
    from ui.tabs.shared_styles import NoWheelSlider

    row_widget, r = _row_widget(parent_layout, label)
    slider = NoWheelSlider(Qt.Orientation.Horizontal)
    slider.setMinimum(min_v)
    slider.setMaximum(max_v)
    slider.setValue(max(min_v, min(max_v, value)))
    lbl = QLabel(fmt(slider.value()))
    setattr(tab, attr, slider)
    setattr(tab, f"{attr}_label", lbl)
    bind_setting_signal(tab, slider.valueChanged, updater=lambda v: lbl.setText(fmt(v)), auto_switch=auto_switch)
    r.addWidget(slider)
    r.addWidget(lbl)
    setattr(slider, "_row_widget", row_widget)
    return slider


def build_devcurve_ui(tab: "VisualizerSettingsContextMixin", parent_layout: QVBoxLayout) -> None:
    from ui.tabs.media.spec_mode_builder import build_spec_mode_ui

    build_spec_mode_ui(tab, parent_layout, "devcurve")


def build_devcurve_layers(tab: "VisualizerSettingsContextMixin", shaper_bucket: QVBoxLayout) -> None:
    from ui.tabs.media.devcurve_shape_editor import DevCurveShapeEditor

    hint = QLabel(
        "Click a layer to edit its spline. Non-active layers stay visible with reduced opacity."
    )
    hint.setToolTip(_TOOLTIP_LAYER_BUTTON)
    hint.setWordWrap(True)
    shaper_bucket.addWidget(hint)

    tab.devcurve_shape_editor = DevCurveShapeEditor(
        parent=None,
        default_layer_nodes={
            src: tab._widget_default(
                'spotify_visualizer', f'devcurve_layer_{src}_shape_nodes'
            )
            for src in _LAYER_ORDER
        },
        default_layer_strengths={
            src: tab._default_float(
                'spotify_visualizer', f'devcurve_layer_{src}_power'
            ) / 3.0
            for src in _LAYER_ORDER
        },
    )
    tab.devcurve_shape_editor.setToolTip(
        "Drag spline nodes for the active layer. Drag the top arrow for per-layer energy power."
    )

    layer_row = _row(shaper_bucket, "Edit Layer:")
    tab.devcurve_layer_buttons = {}
    tab.devcurve_layer_button_group = QButtonGroup(tab)
    tab.devcurve_layer_button_group.setExclusive(True)

    for src in _LAYER_ORDER:
        btn = QPushButton(_LAYER_LABEL[src])
        btn.setCheckable(True)
        shared_styles.bind_shared_styles(
            btn, "MODE_TOGGLE_BUTTON_STYLE", base_style=""
        )
        btn.setToolTip(_TOOLTIP_LAYER_BUTTON)
        tab.devcurve_layer_button_group.addButton(btn)
        tab.devcurve_layer_buttons[src] = btn
        layer_row.addWidget(btn)
    layer_row.addStretch()

    active_color_row = add_builder_swatch_row(shaper_bucket, "Layer Color:", label_width=LABEL_WIDTH)[1]
    tab.devcurve_active_layer_color_btn = ColorSwatchButton(title="Choose Active Spline Curve Layer Color")
    tab.devcurve_active_layer_color_btn.setToolTip(_TOOLTIP_LAYER_COLOR)
    active_color_row.addWidget(tab.devcurve_active_layer_color_btn)
    from ui.tabs.shared_styles import NoWheelSlider
    tab.devcurve_active_layer_order = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.devcurve_active_layer_order.setMinimum(1)
    tab.devcurve_active_layer_order.setMaximum(4)
    active_layer_default = str(
        tab._default_str("spotify_visualizer", "devcurve_active_layer")
    ).strip().lower()
    active_order_default = tab._default_int(
        "spotify_visualizer", f"devcurve_layer_{active_layer_default}_order"
    )
    tab.devcurve_active_layer_order.setValue(
        max(1, min(4, active_order_default))
    )
    tab.devcurve_active_layer_order.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.devcurve_active_layer_order.setTickInterval(1)
    tab.devcurve_active_layer_order.setSingleStep(1)
    tab.devcurve_active_layer_order.setPageStep(1)
    tab.devcurve_active_layer_order.setFixedWidth(120)
    tab.devcurve_active_layer_order.setToolTip(_TOOLTIP_LAYER_ORDER)
    tab.devcurve_active_layer_order_label = QLabel(
        f"{tab.devcurve_active_layer_order.value()}/4"
    )
    tab.devcurve_active_layer_order_label.setToolTip(_TOOLTIP_LAYER_ORDER)
    active_color_row.addSpacing(12)
    active_color_row.addWidget(QLabel("Order:"))
    active_color_row.addWidget(tab.devcurve_active_layer_order)
    active_color_row.addWidget(tab.devcurve_active_layer_order_label)
    active_color_row.addStretch()
    active_outline_row = add_builder_swatch_row(shaper_bucket, "Outline:", label_width=LABEL_WIDTH)[1]
    tab.devcurve_active_layer_outline_color_btn = ColorSwatchButton(title="Choose Active Spline Curve Layer Outline Color")
    tab.devcurve_active_layer_outline_color_btn.setToolTip(_TOOLTIP_LAYER_OUTLINE_COLOR)
    active_outline_row.addWidget(tab.devcurve_active_layer_outline_color_btn)
    tab.devcurve_active_layer_outline_width = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.devcurve_active_layer_outline_width.setMinimum(1)
    tab.devcurve_active_layer_outline_width.setMaximum(20)
    tab.devcurve_active_layer_outline_width.setValue(
        max(1, min(20, int(tab._default_float('spotify_visualizer', 'devcurve_layer_bass_outline_width') * 1000.0)))
    )
    tab.devcurve_active_layer_outline_width.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.devcurve_active_layer_outline_width.setTickInterval(1)
    tab.devcurve_active_layer_outline_width.setSingleStep(1)
    tab.devcurve_active_layer_outline_width.setPageStep(1)
    tab.devcurve_active_layer_outline_width.setFixedWidth(120)
    tab.devcurve_active_layer_outline_width.setToolTip(_TOOLTIP_LAYER_OUTLINE_WIDTH)
    tab.devcurve_active_layer_outline_width_label = QLabel(
        f"{tab.devcurve_active_layer_outline_width.value() / 1000.0:.3f}"
    )
    tab.devcurve_active_layer_outline_width_label.setToolTip(_TOOLTIP_LAYER_OUTLINE_WIDTH)
    active_outline_row.addSpacing(12)
    active_outline_row.addWidget(QLabel("Width:"))
    active_outline_row.addWidget(tab.devcurve_active_layer_outline_width)
    active_outline_row.addWidget(tab.devcurve_active_layer_outline_width_label)
    active_outline_row.addStretch()

    def _on_shape_change(_value=None):
        tab._force_visualizer_preset_to_custom("devcurve")
        tab._save_settings()

    tab.devcurve_shape_editor.nodes_changed.connect(_on_shape_change)
    tab.devcurve_shape_editor.layer_nodes_changed.connect(_on_shape_change)
    tab.devcurve_shape_editor.lane_strengths_changed.connect(_on_shape_change)
    tab.devcurve_shape_editor.notch_positions_changed.connect(_on_shape_change)
    shaper_bucket.addWidget(tab.devcurve_shape_editor)
    tab._devcurve_layer_rows = {}
    tab._devcurve_order_syncing = False
    for src in _LAYER_ORDER:
        order_default = int(tab._default_float("spotify_visualizer", f"devcurve_layer_{src}_order"))
        setattr(tab, f"_devcurve_layer_{src}_order", max(1, min(4, order_default)))
        outline_width_default = int(tab._default_float("spotify_visualizer", f"devcurve_layer_{src}_outline_width") * 1000.0)
        setattr(tab, f"_devcurve_layer_{src}_outline_width", max(1, min(20, outline_width_default)))
        oc = tab._color_from_default(
            "spotify_visualizer",
            f"devcurve_layer_{src}_outline_color")
        oc.setAlpha(255)
        setattr(tab, f"_devcurve_layer_{src}_outline_color", oc)

    def _enabled_layers() -> list[str]:
        enabled: list[str] = []
        for src in _LAYER_ORDER:
            chk = getattr(tab, f"devcurve_layer_{src}_enabled", None)
            if chk is not None and hasattr(chk, "isChecked") and chk.isChecked():
                enabled.append(src)
        return enabled

    def _sync_active_layer_order_ui() -> None:
        src = str(getattr(tab, "_devcurve_active_layer", "bass")).lower()
        if src not in _LAYER_ORDER:
            src = "bass"
        enabled = _enabled_layers()
        max_rank = max(1, len(enabled))
        is_ranked = src in enabled
        if is_ranked:
            ranked = sorted(enabled, key=lambda s: int(getattr(tab, f"_devcurve_layer_{s}_order", tab._default_int("spotify_visualizer", f"devcurve_layer_{s}_order"))))
            rank = ranked.index(src) + 1
        else:
            rank = 1
        slider = tab.devcurve_active_layer_order
        label = tab.devcurve_active_layer_order_label
        slider.blockSignals(True)
        slider.setMinimum(1)
        slider.setMaximum(max_rank)
        slider.setTickInterval(1)
        slider.setValue(max(1, min(max_rank, rank)))
        slider.blockSignals(False)
        slider.setEnabled(is_ranked)
        label.setText(f"{rank}/{max_rank}" if is_ranked else f"-/{max_rank}")

    def _normalize_layer_orders(*, target_src: str | None = None, target_rank: int | None = None, save: bool = True) -> None:
        if getattr(tab, "_devcurve_order_syncing", False):
            return
        tab._devcurve_order_syncing = True
        try:
            enabled = _enabled_layers()
            disabled = [src for src in _LAYER_ORDER if src not in enabled]
            ordered_enabled = sorted(
                enabled,
                key=lambda src: int(getattr(tab, f"_devcurve_layer_{src}_order", tab._default_int("spotify_visualizer", f"devcurve_layer_{src}_order"))),
            )
            if target_src in ordered_enabled and target_rank is not None:
                rank = max(1, min(len(ordered_enabled), int(target_rank)))
                ordered_enabled.remove(target_src)
                ordered_enabled.insert(rank - 1, target_src)
            for idx, src in enumerate(ordered_enabled, start=1):
                setattr(tab, f"_devcurve_layer_{src}_order", idx)
            ordered_disabled = sorted(
                disabled,
                key=lambda src: int(getattr(tab, f"_devcurve_layer_{src}_order", tab._default_int("spotify_visualizer", f"devcurve_layer_{src}_order"))),
            )
            for idx, src in enumerate(ordered_disabled, start=len(ordered_enabled) + 1):
                setattr(tab, f"_devcurve_layer_{src}_order", idx)
            _sync_active_layer_order_ui()
        finally:
            tab._devcurve_order_syncing = False
        if save:
            tab._force_visualizer_preset_to_custom("devcurve")
            tab._save_settings()

    tab._devcurve_normalize_layer_orders = _normalize_layer_orders

    def _apply_active_layer_ui(src: str) -> None:
        src = str(src or "bass").lower()
        if src not in _LAYER_ORDER:
            src = "bass"
        tab._devcurve_active_layer = src
        for key, btn in tab.devcurve_layer_buttons.items():
            btn.blockSignals(True)
            btn.setChecked(key == src)
            btn.blockSignals(False)
        tab.devcurve_shape_editor.set_active_layer(src)
        for key, rows in getattr(tab, "_devcurve_layer_rows", {}).items():
            visible = key == src
            for row in rows:
                row.setVisible(visible)
        sync = getattr(tab, f"_devcurve_layer_{src}_color", None)
        if sync is not None:
            tab.devcurve_active_layer_color_btn.set_color(sync)
        outline_sync = getattr(tab, f"_devcurve_layer_{src}_outline_color", None)
        if outline_sync is not None:
            tab.devcurve_active_layer_outline_color_btn.set_color(outline_sync)
        outline_w = int(getattr(tab, f"_devcurve_layer_{src}_outline_width", 6))
        tab.devcurve_active_layer_outline_width.blockSignals(True)
        tab.devcurve_active_layer_outline_width.setValue(max(1, min(20, outline_w)))
        tab.devcurve_active_layer_outline_width.blockSignals(False)
        tab.devcurve_active_layer_outline_width_label.setText(f"{outline_w / 1000.0:.3f}")
        _sync_active_layer_order_ui()

    def _on_active_layer_color(color) -> None:
        src = str(getattr(tab, "_devcurve_active_layer", "bass")).lower()
        if src not in _LAYER_ORDER:
            src = "bass"
        setattr(tab, f"_devcurve_layer_{src}_color", color)
        tab._force_visualizer_preset_to_custom("devcurve")
        tab._save_settings()

    def _on_active_layer_outline_color(color) -> None:
        src = str(getattr(tab, "_devcurve_active_layer", "bass")).lower()
        if src not in _LAYER_ORDER:
            src = "bass"
        color.setAlpha(255)
        setattr(tab, f"_devcurve_layer_{src}_outline_color", color)
        tab._force_visualizer_preset_to_custom("devcurve")
        tab._save_settings()

    def _on_active_layer_outline_width_change(value: int) -> None:
        src = str(getattr(tab, "_devcurve_active_layer", "bass")).lower()
        if src not in _LAYER_ORDER:
            src = "bass"
        v = max(1, min(20, int(value)))
        setattr(tab, f"_devcurve_layer_{src}_outline_width", v)
        tab.devcurve_active_layer_outline_width_label.setText(f"{v / 1000.0:.3f}")
        tab._force_visualizer_preset_to_custom("devcurve")
        tab._save_settings()

    def _on_active_layer_order_change(value: int) -> None:
        src = str(getattr(tab, "_devcurve_active_layer", "bass")).lower()
        if src not in _LAYER_ORDER:
            src = "bass"
        _normalize_layer_orders(target_src=src, target_rank=int(value), save=True)

    tab.devcurve_active_layer_color_btn.color_changed.connect(_on_active_layer_color)
    tab.devcurve_active_layer_outline_color_btn.color_changed.connect(_on_active_layer_outline_color)
    tab.devcurve_active_layer_outline_width.valueChanged.connect(_on_active_layer_outline_width_change)
    tab.devcurve_active_layer_order.valueChanged.connect(_on_active_layer_order_change)

    for src, btn in tab.devcurve_layer_buttons.items():
        btn.clicked.connect(lambda _checked=False, s=src: _apply_active_layer_ui(s))

    tab._devcurve_apply_active_layer_ui = _apply_active_layer_ui

    for src in _LAYER_ORDER:
        title = _LAYER_LABEL[src]

        en_row_widget, en_row = _row_widget(shaper_bucket, f"{title}:")
        enabled = QCheckBox("Enabled")
        enabled.setProperty("circleIndicator", True)
        enabled.setChecked(tab._default_bool("spotify_visualizer", f"devcurve_layer_{src}_enabled"))
        enabled.setToolTip(_TOOLTIP_LAYER_ENABLED)
        setattr(tab, f"devcurve_layer_{src}_enabled", enabled)
        bind_setting_signal(tab, enabled.stateChanged, auto_switch=True)
        enabled.stateChanged.connect(lambda _state, _src=src: _normalize_layer_orders(target_src=_src, save=True))
        en_row.addWidget(enabled)

        alpha_slider = _add_slider(
            tab,
            shaper_bucket,
            attr=f"devcurve_layer_{src}_alpha",
            label=f"{title} Alpha:",
            min_v=0,
            max_v=100,
            value=int(tab._default_float("spotify_visualizer", f"devcurve_layer_{src}_alpha") * 100),
            fmt=lambda v: f"{v}%",
            auto_switch=True,
        )
        alpha_slider.setToolTip(_TOOLTIP_LAYER_ALPHA)
        offset_slider = _add_slider(
            tab,
            shaper_bucket,
            attr=f"devcurve_layer_{src}_offset",
            label=f"{title} Offset:",
            min_v=-45,
            max_v=45,
            value=int(tab._default_float("spotify_visualizer", f"devcurve_layer_{src}_offset") * 100),
            fmt=lambda v: f"{v / 100.0:+.2f}",
            auto_switch=True,
        )
        offset_slider.setToolTip(_TOOLTIP_LAYER_OFFSET)
        tab._devcurve_layer_rows[src] = [
            en_row_widget,
            getattr(alpha_slider, "_row_widget"),
            getattr(offset_slider, "_row_widget"),
        ]
    _normalize_layer_orders(save=False)
    _apply_active_layer_ui(str(getattr(tab, "_devcurve_active_layer", "bass")))

