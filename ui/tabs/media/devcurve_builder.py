"""Dev Curve visualizer UI builder (gated by ``--devcurve``)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QButtonGroup, QCheckBox, QLabel, QPushButton, QSlider, QVBoxLayout

from ui.styled_popup import ColorSwatchButton
from ui.tabs.media.builder_scaffold import (
    add_builder_swatch_row,
    bind_setting_signal,
    build_collapsible_bucket,
    build_mode_scaffold,
)
from ui.tabs.shared_styles import add_aligned_row, add_aligned_row_widget
if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


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
_TOOLTIP_BASE_LEVEL = "Global baseline height for all Dev Curve layers."
_TOOLTIP_MOTION_POWER = "Master reactive deformation gain for all layers."
_TOOLTIP_IDLE_MOTION = "Constant low-energy wobble while idle or between beats."
_TOOLTIP_IDLE_SPEED = "Travel speed of the low-energy idle wobble."
_TOOLTIP_SMOOTHNESS = "Extra curve smoothing. Higher values reduce lumpiness while keeping spline motion reactive."
_TOOLTIP_CARD_HEIGHT = "Height multiplier for the visualizer card area."
_TOOLTIP_GHOST_ENABLED = "Enable a lightweight trail to inspect motion history."
_TOOLTIP_GHOST_OPACITY = "Opacity of the trail overlay."
_TOOLTIP_GHOST_DECAY = "How quickly the trail fades."
_TOOLTIP_FG_SHADOW_ENABLED = "Enable a dynamic full-width shadow fill tied to the current foreground layer."
_TOOLTIP_FG_SHADOW_ALPHA = "Opacity of the dynamic foreground shadow."
_TOOLTIP_FG_SHADOW_DARKEN = "How much darker the shadow is than the foreground layer color."
_TOOLTIP_FG_SHADOW_OFFSET = "Vertical offset of the foreground shadow below the foreground spline."
_TOOLTIP_FG_SPECULAR_ENABLED = "Enable a dynamic crest-following specular highlight on the foreground layer."
_TOOLTIP_FG_SPECULAR_ALPHA = "Opacity of the foreground specular highlight."
_TOOLTIP_FG_SPECULAR_WIDTH = "Thickness of the specular band around the foreground spline."
_TOOLTIP_FG_SPECULAR_OFFSET = "Vertical offset for the specular band relative to the foreground spline."
_TOOLTIP_FG_SPECULAR_CREST_BIAS = "Bias toward crest zones based on local curvature."
_LAYER_DEFAULTS = {
    "bass": {"color": [82, 167, 255, 230], "outline_color": [255, 255, 255, 255], "outline_width": 6, "alpha": 55, "power": 100, "offset": 0, "order": 1, "x": 0.15},
    "vocals": {"color": [136, 190, 255, 220], "outline_color": [255, 255, 255, 255], "outline_width": 6, "alpha": 42, "power": 100, "offset": -1, "order": 2, "x": 0.40},
    "mids": {"color": [100, 145, 255, 220], "outline_color": [255, 255, 255, 255], "outline_width": 6, "alpha": 46, "power": 100, "offset": 1, "order": 3, "x": 0.65},
    "transients": {"color": [215, 240, 255, 240], "outline_color": [255, 255, 255, 255], "outline_width": 6, "alpha": 66, "power": 115, "offset": 0, "order": 4, "x": 0.88},
}


def _row(parent_layout: QVBoxLayout, label_text: str):
    content, _ = add_aligned_row(parent_layout, label_text, label_width=LABEL_WIDTH, wrap=True)
    return content


def _row_widget(parent_layout: QVBoxLayout, label_text: str):
    row_widget, content, _ = add_aligned_row_widget(parent_layout, label_text, label_width=LABEL_WIDTH, wrap=True)
    return row_widget, content


def _add_slider(
    tab: "WidgetsTab",
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
    from ui.tabs.widgets_tab import NoWheelSlider

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


def build_devcurve_ui(tab: "WidgetsTab", parent_layout: QVBoxLayout) -> None:
    from ui.tabs.media.devcurve_shape_editor import DevCurveShapeEditor

    scaffold = build_mode_scaffold(
        tab,
        parent_layout,
        mode_key="devcurve",
        settings_container_attr="_devcurve_settings_container",
        preset_slider_attr="_devcurve_preset_slider",
        normal_attr="_devcurve_normal",
        advanced_host_attr="_devcurve_advanced_host",
        advanced_toggle_attr="_devcurve_adv_toggle",
        advanced_helper_attr="_devcurve_adv_helper",
        advanced_attr="_devcurve_advanced",
    )
    normal_layout = scaffold.normal_layout
    adv_layout = scaffold.advanced_layout

    _, shaper_bucket = build_collapsible_bucket(
        tab,
        normal_layout,
        mode_key="devcurve",
        bucket_key="shaper",
        title="Shaper",
        helper_text="Layer-first spline editor with per-layer shape and energy arrows.",
        default_expanded=True,
    )
    _, core_bucket = build_collapsible_bucket(
        tab,
        normal_layout,
        mode_key="devcurve",
        bucket_key="core",
        title="Core",
        helper_text="Global curve motion and fill styling.",
        default_expanded=True,
    )
    _, foreground_fx_bucket = build_collapsible_bucket(
        tab,
        normal_layout,
        mode_key="devcurve",
        bucket_key="foreground_fx",
        title="Foreground FX",
        helper_text="Optional dynamic shadow/specular effects for the current top layer.",
        default_expanded=False,
    )
    _, ghost_bucket = build_collapsible_bucket(
        tab,
        adv_layout,
        mode_key="devcurve",
        bucket_key="ghost",
        title="Ghost",
        helper_text="Optional trail for debug visibility.",
        default_expanded=False,
    )

    hint = QLabel(
        "Click a layer to edit its spline. Non-active layers stay visible with reduced opacity."
    )
    hint.setToolTip(_TOOLTIP_LAYER_BUTTON)
    hint.setWordWrap(True)
    shaper_bucket.addWidget(hint)

    tab.devcurve_shape_editor = DevCurveShapeEditor(parent=None)
    tab.devcurve_shape_editor.setToolTip(
        "Drag spline nodes for the active layer. Drag the top arrow for per-layer energy power."
    )

    layer_row = _row(shaper_bucket, "Edit Layer:")
    tab.devcurve_layer_buttons = {}
    tab.devcurve_layer_button_group = QButtonGroup(tab)
    tab.devcurve_layer_button_group.setExclusive(True)
    _mode_button_style = """
        QPushButton {
            background-color: #232323;
            color: #ffffff;
            border: 2px solid #f1f1f1;
            border-radius: 18px;
            padding: 10px 20px;
            font-weight: 600;
            min-height: 18px;
        }
        QPushButton:hover {
            background-color: #2a2a2a;
        }
        QPushButton:checked {
            background-color: #4a4a4a;
            border-color: #f7f7f7;
        }
        QPushButton:disabled {
            color: #7a7a7a;
            border-color: #6a6a6a;
        }
    """
    for src in _LAYER_ORDER:
        btn = QPushButton(_LAYER_LABEL[src])
        btn.setCheckable(True)
        btn.setStyleSheet(_mode_button_style)
        btn.setToolTip(_TOOLTIP_LAYER_BUTTON)
        tab.devcurve_layer_button_group.addButton(btn)
        tab.devcurve_layer_buttons[src] = btn
        layer_row.addWidget(btn)
    layer_row.addStretch()

    active_color_row = add_builder_swatch_row(shaper_bucket, "Layer Color:", label_width=LABEL_WIDTH)[1]
    tab.devcurve_active_layer_color_btn = ColorSwatchButton(title="Choose Active Dev Curve Layer Color")
    tab.devcurve_active_layer_color_btn.setToolTip(_TOOLTIP_LAYER_COLOR)
    active_color_row.addWidget(tab.devcurve_active_layer_color_btn)
    from ui.tabs.widgets_tab import NoWheelSlider
    tab.devcurve_active_layer_order = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.devcurve_active_layer_order.setMinimum(1)
    tab.devcurve_active_layer_order.setMaximum(4)
    tab.devcurve_active_layer_order.setValue(1)
    tab.devcurve_active_layer_order.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.devcurve_active_layer_order.setTickInterval(1)
    tab.devcurve_active_layer_order.setSingleStep(1)
    tab.devcurve_active_layer_order.setPageStep(1)
    tab.devcurve_active_layer_order.setFixedWidth(120)
    tab.devcurve_active_layer_order.setToolTip(_TOOLTIP_LAYER_ORDER)
    tab.devcurve_active_layer_order_label = QLabel("1/4")
    tab.devcurve_active_layer_order_label.setToolTip(_TOOLTIP_LAYER_ORDER)
    active_color_row.addSpacing(12)
    active_color_row.addWidget(QLabel("Order:"))
    active_color_row.addWidget(tab.devcurve_active_layer_order)
    active_color_row.addWidget(tab.devcurve_active_layer_order_label)
    active_color_row.addStretch()
    active_outline_row = add_builder_swatch_row(shaper_bucket, "Outline:", label_width=LABEL_WIDTH)[1]
    tab.devcurve_active_layer_outline_color_btn = ColorSwatchButton(title="Choose Active Dev Curve Layer Outline Color")
    tab.devcurve_active_layer_outline_color_btn.setToolTip(_TOOLTIP_LAYER_OUTLINE_COLOR)
    active_outline_row.addWidget(tab.devcurve_active_layer_outline_color_btn)
    tab.devcurve_active_layer_outline_width = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.devcurve_active_layer_outline_width.setMinimum(1)
    tab.devcurve_active_layer_outline_width.setMaximum(20)
    tab.devcurve_active_layer_outline_width.setValue(6)
    tab.devcurve_active_layer_outline_width.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.devcurve_active_layer_outline_width.setTickInterval(1)
    tab.devcurve_active_layer_outline_width.setSingleStep(1)
    tab.devcurve_active_layer_outline_width.setPageStep(1)
    tab.devcurve_active_layer_outline_width.setFixedWidth(120)
    tab.devcurve_active_layer_outline_width.setToolTip(_TOOLTIP_LAYER_OUTLINE_WIDTH)
    tab.devcurve_active_layer_outline_width_label = QLabel("0.006")
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
        order_default = int(tab._default_float("spotify_visualizer", f"devcurve_layer_{src}_order", _LAYER_DEFAULTS[src]["order"]))
        setattr(tab, f"_devcurve_layer_{src}_order", max(1, min(4, order_default)))
        outline_width_default = int(tab._default_float("spotify_visualizer", f"devcurve_layer_{src}_outline_width", _LAYER_DEFAULTS[src]["outline_width"] / 1000.0) * 1000.0)
        setattr(tab, f"_devcurve_layer_{src}_outline_width", max(1, min(20, outline_width_default)))
        oc = tab._color_from_default(
            "spotify_visualizer",
            f"devcurve_layer_{src}_outline_color",
            _LAYER_DEFAULTS[src]["outline_color"],
        )
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
            ranked = sorted(enabled, key=lambda s: int(getattr(tab, f"_devcurve_layer_{s}_order", _LAYER_DEFAULTS[s]["order"])))
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
                key=lambda src: int(getattr(tab, f"_devcurve_layer_{src}_order", _LAYER_DEFAULTS[src]["order"])),
            )
            if target_src in ordered_enabled and target_rank is not None:
                rank = max(1, min(len(ordered_enabled), int(target_rank)))
                ordered_enabled.remove(target_src)
                ordered_enabled.insert(rank - 1, target_src)
            for idx, src in enumerate(ordered_enabled, start=1):
                setattr(tab, f"_devcurve_layer_{src}_order", idx)
            ordered_disabled = sorted(
                disabled,
                key=lambda src: int(getattr(tab, f"_devcurve_layer_{src}_order", _LAYER_DEFAULTS[src]["order"])),
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
        defaults = _LAYER_DEFAULTS[src]
        title = _LAYER_LABEL[src]

        en_row_widget, en_row = _row_widget(shaper_bucket, f"{title}:")
        enabled = QCheckBox("Enabled")
        enabled.setProperty("circleIndicator", True)
        enabled.setChecked(tab._default_bool("spotify_visualizer", f"devcurve_layer_{src}_enabled", True))
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
            value=int(tab._default_float("spotify_visualizer", f"devcurve_layer_{src}_alpha", defaults["alpha"] / 100.0) * 100),
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
            value=int(tab._default_float("spotify_visualizer", f"devcurve_layer_{src}_offset", defaults["offset"] / 100.0) * 100),
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

    _add_slider(
        tab,
        core_bucket,
        attr="devcurve_base_level",
        label="Base Level:",
        min_v=10,
        max_v=90,
        value=int(tab._default_float("spotify_visualizer", "devcurve_base_level", 0.58) * 100),
        fmt=lambda v: f"{v}%",
        auto_switch=True,
    )
    tab.devcurve_base_level.setToolTip(_TOOLTIP_BASE_LEVEL)
    _add_slider(
        tab,
        core_bucket,
        attr="devcurve_motion_power",
        label="Motion Power:",
        min_v=0,
        max_v=300,
        value=int(tab._default_float("spotify_visualizer", "devcurve_motion_power", 1.0) * 100),
        fmt=lambda v: f"{v / 100.0:.2f}x",
        auto_switch=True,
    )
    tab.devcurve_motion_power.setToolTip(_TOOLTIP_MOTION_POWER)
    _add_slider(
        tab,
        core_bucket,
        attr="devcurve_idle_motion",
        label="Idle Motion:",
        min_v=0,
        max_v=150,
        value=int(tab._default_float("spotify_visualizer", "devcurve_idle_motion", 0.20) * 100),
        fmt=lambda v: f"{v / 100.0:.2f}",
        auto_switch=True,
    )
    tab.devcurve_idle_motion.setToolTip(_TOOLTIP_IDLE_MOTION)
    _add_slider(
        tab,
        core_bucket,
        attr="devcurve_idle_speed",
        label="Idle Speed:",
        min_v=5,
        max_v=200,
        value=int(tab._default_float("spotify_visualizer", "devcurve_idle_speed", 0.60) * 100),
        fmt=lambda v: f"{v / 100.0:.2f}x",
        auto_switch=True,
    )
    tab.devcurve_idle_speed.setToolTip(_TOOLTIP_IDLE_SPEED)
    _add_slider(
        tab,
        core_bucket,
        attr="devcurve_smoothness",
        label="Smoothness:",
        min_v=0,
        max_v=100,
        value=int(tab._default_float("spotify_visualizer", "devcurve_smoothness", 0.55) * 100),
        fmt=lambda v: f"{v}%",
        auto_switch=True,
    )
    tab.devcurve_smoothness.setToolTip(_TOOLTIP_SMOOTHNESS)
    grow = _add_slider(
        tab,
        core_bucket,
        attr="devcurve_growth",
        label="Card Height:",
        min_v=100,
        max_v=500,
        value=int(tab._default_float("spotify_visualizer", "devcurve_growth", 3.0) * 100),
        fmt=lambda v: f"{v / 100.0:.1f}x",
        auto_switch=True,
    )
    grow.setToolTip(_TOOLTIP_CARD_HEIGHT)
    grow.setTickPosition(QSlider.TickPosition.TicksBelow)
    grow.setTickInterval(50)

    fx_toggle_row = _row(foreground_fx_bucket, "")
    tab.devcurve_foreground_shadow_enabled = QCheckBox("Shadow")
    tab.devcurve_foreground_shadow_enabled.setProperty("circleIndicator", True)
    tab.devcurve_foreground_shadow_enabled.setChecked(
        tab._default_bool("spotify_visualizer", "devcurve_foreground_shadow_enabled", False)
    )
    tab.devcurve_foreground_shadow_enabled.setToolTip(_TOOLTIP_FG_SHADOW_ENABLED)
    bind_setting_signal(tab, tab.devcurve_foreground_shadow_enabled.stateChanged, auto_switch=True)
    fx_toggle_row.addWidget(tab.devcurve_foreground_shadow_enabled)
    tab.devcurve_foreground_specular_enabled = QCheckBox("Specular")
    tab.devcurve_foreground_specular_enabled.setProperty("circleIndicator", True)
    tab.devcurve_foreground_specular_enabled.setChecked(
        tab._default_bool("spotify_visualizer", "devcurve_foreground_specular_enabled", False)
    )
    tab.devcurve_foreground_specular_enabled.setToolTip(_TOOLTIP_FG_SPECULAR_ENABLED)
    bind_setting_signal(tab, tab.devcurve_foreground_specular_enabled.stateChanged, auto_switch=True)
    fx_toggle_row.addSpacing(16)
    fx_toggle_row.addWidget(tab.devcurve_foreground_specular_enabled)
    fx_toggle_row.addStretch()

    _shadow_alpha = _add_slider(
        tab,
        foreground_fx_bucket,
        attr="devcurve_foreground_shadow_alpha",
        label="Shadow Alpha:",
        min_v=0,
        max_v=100,
        value=int(tab._default_float("spotify_visualizer", "devcurve_foreground_shadow_alpha", 0.36) * 100),
        fmt=lambda v: f"{v}%",
        auto_switch=True,
    )
    _shadow_alpha.setToolTip(_TOOLTIP_FG_SHADOW_ALPHA)
    _shadow_darken = _add_slider(
        tab,
        foreground_fx_bucket,
        attr="devcurve_foreground_shadow_darken",
        label="Shadow Darken:",
        min_v=0,
        max_v=100,
        value=int(tab._default_float("spotify_visualizer", "devcurve_foreground_shadow_darken", 0.42) * 100),
        fmt=lambda v: f"{v}%",
        auto_switch=True,
    )
    _shadow_darken.setToolTip(_TOOLTIP_FG_SHADOW_DARKEN)
    _shadow_offset = _add_slider(
        tab,
        foreground_fx_bucket,
        attr="devcurve_foreground_shadow_offset",
        label="Shadow Offset:",
        min_v=0,
        max_v=45,
        value=int(tab._default_float("spotify_visualizer", "devcurve_foreground_shadow_offset", 0.10) * 100),
        fmt=lambda v: f"{v / 100.0:.2f}",
        auto_switch=True,
    )
    _shadow_offset.setToolTip(_TOOLTIP_FG_SHADOW_OFFSET)

    _spec_alpha = _add_slider(
        tab,
        foreground_fx_bucket,
        attr="devcurve_foreground_specular_alpha",
        label="Specular Alpha:",
        min_v=0,
        max_v=100,
        value=int(tab._default_float("spotify_visualizer", "devcurve_foreground_specular_alpha", 0.78) * 100),
        fmt=lambda v: f"{v}%",
        auto_switch=True,
    )
    _spec_alpha.setToolTip(_TOOLTIP_FG_SPECULAR_ALPHA)
    _spec_width = _add_slider(
        tab,
        foreground_fx_bucket,
        attr="devcurve_foreground_specular_width",
        label="Specular Width:",
        min_v=2,
        max_v=120,
        value=int(tab._default_float("spotify_visualizer", "devcurve_foreground_specular_width", 0.022) * 1000),
        fmt=lambda v: f"{v / 1000.0:.3f}",
        auto_switch=True,
    )
    _spec_width.setToolTip(_TOOLTIP_FG_SPECULAR_WIDTH)
    _spec_offset = _add_slider(
        tab,
        foreground_fx_bucket,
        attr="devcurve_foreground_specular_offset",
        label="Specular Offset:",
        min_v=-20,
        max_v=20,
        value=int(tab._default_float("spotify_visualizer", "devcurve_foreground_specular_offset", 0.028) * 100),
        fmt=lambda v: f"{v / 100.0:+.2f}",
        auto_switch=True,
    )
    _spec_offset.setToolTip(_TOOLTIP_FG_SPECULAR_OFFSET)
    _spec_crest = _add_slider(
        tab,
        foreground_fx_bucket,
        attr="devcurve_foreground_specular_crest_bias",
        label="Specular Crest Bias:",
        min_v=0,
        max_v=200,
        value=int(tab._default_float("spotify_visualizer", "devcurve_foreground_specular_crest_bias", 1.05) * 100),
        fmt=lambda v: f"{v / 100.0:.2f}x",
        auto_switch=True,
    )
    _spec_crest.setToolTip(_TOOLTIP_FG_SPECULAR_CREST_BIAS)

    tab._devcurve_foreground_shadow_rows = [
        getattr(_shadow_alpha, "_row_widget"),
        getattr(_shadow_darken, "_row_widget"),
        getattr(_shadow_offset, "_row_widget"),
    ]
    tab._devcurve_foreground_specular_rows = [
        getattr(_spec_alpha, "_row_widget"),
        getattr(_spec_width, "_row_widget"),
        getattr(_spec_offset, "_row_widget"),
        getattr(_spec_crest, "_row_widget"),
    ]

    def _update_foreground_fx_visibility() -> None:
        shadow_on = bool(tab.devcurve_foreground_shadow_enabled.isChecked())
        for row in getattr(tab, "_devcurve_foreground_shadow_rows", []):
            row.setVisible(shadow_on)
        spec_on = bool(tab.devcurve_foreground_specular_enabled.isChecked())
        for row in getattr(tab, "_devcurve_foreground_specular_rows", []):
            row.setVisible(spec_on)

    tab._devcurve_update_foreground_fx_visibility = _update_foreground_fx_visibility
    tab.devcurve_foreground_shadow_enabled.stateChanged.connect(lambda _state: _update_foreground_fx_visibility())
    tab.devcurve_foreground_specular_enabled.stateChanged.connect(lambda _state: _update_foreground_fx_visibility())
    _update_foreground_fx_visibility()

    g_row = _row(ghost_bucket, "")
    tab.devcurve_ghost_enabled = QCheckBox("Enable Ghosting")
    tab.devcurve_ghost_enabled.setProperty("circleIndicator", True)
    tab.devcurve_ghost_enabled.setChecked(tab._default_bool("spotify_visualizer", "devcurve_ghosting_enabled", False))
    tab.devcurve_ghost_enabled.setToolTip(_TOOLTIP_GHOST_ENABLED)
    bind_setting_signal(tab, tab.devcurve_ghost_enabled.stateChanged, auto_switch=True)
    g_row.addWidget(tab.devcurve_ghost_enabled)
    g_row.addStretch()
    _add_slider(
        tab,
        ghost_bucket,
        attr="devcurve_ghost_opacity",
        label="Ghost Opacity:",
        min_v=0,
        max_v=100,
        value=int(tab._default_float("spotify_visualizer", "devcurve_ghost_alpha", 0.0) * 100),
        fmt=lambda v: f"{v}%",
        auto_switch=True,
    )
    tab.devcurve_ghost_opacity.setToolTip(_TOOLTIP_GHOST_OPACITY)
    _add_slider(
        tab,
        ghost_bucket,
        attr="devcurve_ghost_decay",
        label="Ghost Decay:",
        min_v=10,
        max_v=100,
        value=int(tab._default_float("spotify_visualizer", "devcurve_ghost_decay", 0.4) * 100),
        fmt=lambda v: f"{v / 100.0:.2f}x",
        auto_switch=True,
    )
    tab.devcurve_ghost_decay.setToolTip(_TOOLTIP_GHOST_DECAY)
