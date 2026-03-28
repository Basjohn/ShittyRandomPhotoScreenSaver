"""Shared per-mode technical controls for Spotify visualizer modes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui.tabs.shared_styles import ADV_HELPER_LABEL_STYLE, add_section_label
from ui.tabs.widgets_tab import NoWheelSlider
from ui.widgets import StyledComboBox


_PER_MODE_TECH_ATTR = "_per_mode_technical_controls"
MANUAL_FLOOR_MIN = 0.05
MANUAL_FLOOR_MAX = 1.0

_KICK_GAIN_MODES = frozenset({"spectrum", "blob"})
_PULSE_GAIN_MODES = frozenset({"bubble"})

_TRANSIENT_MIX_META: Dict[str, tuple] = {
    "spectrum": (
        "spectrum_lane_transient_mix",
        "Kick Lane Mix:",
        "How much transient energy feeds the kick express lane (0%–100%).\n"
        "Higher = snappier kick response. 65% = default.",
        0.65, 0.0, 1.0,
    ),
    "bubble": (
        "bubble_transient_mix_bass",
        "Transient Bass Mix:",
        "Transient bass energy weight for bubble pulse (0%–100%).\n"
        "Higher = stronger kick punch. 75% = default.",
        0.75, 0.0, 1.0,
    ),
    "blob": (
        "blob_transient_mix_bass",
        "Transient Bass Mix:",
        "Transient bass energy weight for blob deformation (0%–100%).\n"
        "Higher = stronger kick response. 50% = default.",
        0.5, 0.0, 1.0,
    ),
    "sine_wave": (
        "sine_wave_transient_width_mix",
        "Transient Width Mix:",
        "How much transient energy widens the sine wave (0%–100%).\n"
        "Higher = more width reaction on kicks. 40% = default.",
        0.4, 0.0, 1.0,
    ),
    "oscilloscope": (
        "oscilloscope_transient_width_mix",
        "Transient Width Mix:",
        "How much transient energy widens the oscilloscope line (0%–100%).\n"
        "Higher = more width reaction on kicks. 35% = default.",
        0.35, 0.0, 1.0,
    ),
}

_KICK_GAIN_TIP = (
    "Kick event gain (0%–200%). Controls how strongly discrete kick help\n"
    "pushes the mode's fast-react path. 0% = disabled, 100% = default.\n"
    "Spectrum spends this in the kick lane; Blob spends it in stage/kick assist.\n"
    "0% = disabled, 100% = default, 200% = double."
)
_PULSE_GAIN_TIP = (
    "Transient pulse gain (0%–300%). Controls how strongly transient\n"
    "bass energy mixes into bubble/blob pulse amplitude.\n"
    "0% = disabled, 100% = default, 300% = triple."
)


@dataclass(frozen=True)
class _ControlDef:
    control_key: str
    config_key: str
    default_key: str
    widget_kind: str
    default_type: str
    base_default: Any
    label_text: str = ""
    checkbox_text: str = ""
    section: str = "root"
    label_key: Optional[str] = None
    tooltip: str = ""
    minimum: float = 0.0
    maximum: float = 100.0
    tick_interval: int = 0
    scale: float = 1.0
    options: tuple[tuple[str, int], ...] = ()
    suffix_text: str = ""
    storage_kind: str = "prefixed"
    hidden: bool = False
    modes: Optional[frozenset[str]] = None
    display: Optional[Callable[[Any], str]] = None
    min_width: Optional[int] = None
    circle_indicator: bool = False


@dataclass(frozen=True)
class _BucketDef:
    key: str
    label: str
    default_visible: bool
    helper_text: str


def _format_percent(value: float) -> str:
    return f"{int(round(value * 100.0))}%"


def _format_multiplier(value: float) -> str:
    return f"{value:.2f}x"


def _format_floor(value: float) -> str:
    return f"{value:.2f}"


_BUCKET_DEFS: tuple[_BucketDef, ...] = (
    _BucketDef(
        key="agc",
        label="Show AGC Controls",
        default_visible=False,
        helper_text="Visibility only. Hidden AGC controls still keep their saved values and remain active.",
    ),
    _BucketDef(
        key="transient",
        label="Show Transient Controls",
        default_visible=True,
        helper_text="Visibility only. Hidden transient controls still keep their saved values and remain active.",
    ),
)

_BASE_CONTROL_DEFS: tuple[_ControlDef, ...] = (
    _ControlDef(
        control_key="bar_count",
        config_key="bar_count",
        default_key="bar_count",
        widget_kind="spinbox",
        default_type="int",
        base_default=32,
        label_text="Bar Count:",
        minimum=8,
        maximum=96,
        suffix_text="bars",
    ),
    _ControlDef(
        control_key="block_size",
        config_key="audio_block_size",
        default_key="audio_block_size",
        widget_kind="combo",
        default_type="int",
        base_default=0,
        label_text="Audio Block Size:",
        options=(
            ("Auto (Driver)", 0),
            ("128 samples", 128),
            ("256 samples", 256),
            ("512 samples", 512),
            ("1024 samples", 1024),
        ),
        min_width=140,
    ),
    _ControlDef(
        control_key="adaptive",
        config_key="adaptive_sensitivity",
        default_key="adaptive_sensitivity",
        widget_kind="checkbox",
        default_type="bool",
        base_default=True,
        checkbox_text="Adaptive Sensitivity",
        circle_indicator=True,
    ),
    _ControlDef(
        control_key="sensitivity_slider",
        config_key="sensitivity",
        default_key="sensitivity",
        widget_kind="slider",
        default_type="float",
        base_default=1.0,
        label_text="Sensitivity:",
        label_key="sensitivity_label",
        minimum=0.25,
        maximum=2.5,
        tick_interval=25,
        scale=100.0,
        display=_format_multiplier,
    ),
    _ControlDef(
        control_key="dynamic_range",
        config_key="dynamic_range_enabled",
        default_key="dynamic_range_enabled",
        widget_kind="checkbox",
        default_type="bool",
        base_default=False,
        checkbox_text="Dynamic Range Boost",
        circle_indicator=True,
    ),
    _ControlDef(
        control_key="agc_strength_slider",
        config_key="agc_strength",
        default_key="agc_strength",
        widget_kind="slider",
        default_type="float",
        base_default=0.5,
        label_text="AGC Strength:",
        label_key="agc_strength_label",
        section="agc",
        tooltip=(
            "AGC normalization aggressiveness (0%=off, 50%=default, 100%=max compression).\n"
            "Lower values preserve more dynamic range. 0% disables normalization entirely."
        ),
        minimum=0.0,
        maximum=1.0,
        tick_interval=10,
        scale=100.0,
        display=_format_percent,
    ),
    _ControlDef(
        control_key="input_gain_slider",
        config_key="input_gain",
        default_key="input_gain",
        widget_kind="slider",
        default_type="float",
        base_default=1.0,
        label_text="Input Gain:",
        label_key="input_gain_label",
        section="agc",
        tooltip=(
            "Pre-FFT signal gain (5%–200%). Simulates changing the mixer volume\n"
            "without actually affecting audio output. Lower = calmer visualizer,\n"
            "higher = more reactive. 100% = no change (default)."
        ),
        minimum=0.05,
        maximum=2.0,
        tick_interval=25,
        scale=100.0,
        display=_format_percent,
    ),
    _ControlDef(
        control_key="kick_gain_slider",
        config_key="kick_lane_gain",
        default_key="kick_lane_gain",
        widget_kind="slider",
        default_type="float",
        base_default=1.0,
        label_text="Kick Lane Gain:",
        label_key="kick_gain_label",
        section="transient",
        tooltip=_KICK_GAIN_TIP,
        minimum=0.0,
        maximum=2.0,
        tick_interval=25,
        scale=100.0,
        display=_format_percent,
        modes=_KICK_GAIN_MODES,
    ),
    _ControlDef(
        control_key="pulse_gain_slider",
        config_key="transient_pulse_gain",
        default_key="transient_pulse_gain",
        widget_kind="slider",
        default_type="float",
        base_default=1.0,
        label_text="Transient Pulse:",
        label_key="pulse_gain_label",
        section="transient",
        tooltip=_PULSE_GAIN_TIP,
        minimum=0.0,
        maximum=3.0,
        tick_interval=50,
        scale=100.0,
        display=_format_percent,
        modes=_PULSE_GAIN_MODES,
    ),
    _ControlDef(
        control_key="clamp_slider",
        config_key="transient_clamp",
        default_key="transient_clamp",
        widget_kind="slider",
        default_type="float",
        base_default=1.5,
        label_text="Transient Clamp:",
        label_key="clamp_label",
        section="transient",
        tooltip=(
            "Maximum transient-boosted bass energy (0%–300%). Prevents\n"
            "transient spikes from blowing out the visualizer. 150% = default."
        ),
        minimum=0.0,
        maximum=3.0,
        tick_interval=50,
        scale=100.0,
        display=_format_percent,
    ),
    _ControlDef(
        control_key="dynamic_floor",
        config_key="dynamic_floor",
        default_key="dynamic_floor",
        widget_kind="checkbox",
        default_type="bool",
        base_default=True,
        checkbox_text="Dynamic Noise Floor",
        circle_indicator=True,
    ),
    _ControlDef(
        control_key="manual_floor",
        config_key="manual_floor",
        default_key="manual_floor",
        widget_kind="slider",
        default_type="float",
        base_default=0.12,
        label_text="Manual Floor\nBaseline:",
        label_key="manual_label",
        tooltip="Sets the baseline noise floor used by both Manual and Dynamic modes.",
        minimum=MANUAL_FLOOR_MIN,
        maximum=MANUAL_FLOOR_MAX,
        tick_interval=10,
        scale=100.0,
        display=_format_floor,
    ),
)


def _control_defs_for_mode(mode_key: str) -> tuple[_ControlDef, ...]:
    defs = [defn for defn in _BASE_CONTROL_DEFS if defn.modes is None or mode_key in defn.modes]
    mix_meta = _TRANSIENT_MIX_META.get(mode_key)
    if mix_meta is not None:
        mix_key, mix_label, mix_tip, mix_default, mix_lo, mix_hi = mix_meta
        defs.append(
            _ControlDef(
                control_key="mix_slider",
                config_key=mix_key,
                default_key=mix_key.split("_", 1)[-1] if "_" in mix_key else mix_key,
                widget_kind="slider",
                default_type="float",
                base_default=mix_default,
                label_text=mix_label,
                label_key="mix_label",
                section="transient",
                tooltip=mix_tip,
                minimum=mix_lo,
                maximum=mix_hi,
                tick_interval=10,
                scale=100.0,
                storage_kind="direct",
                display=_format_percent,
            )
        )
    if mode_key == "bubble":
        defs.append(
            _ControlDef(
                control_key="mix_vocal_slider",
                config_key="bubble_transient_mix_vocal",
                default_key="transient_mix_vocal",
                widget_kind="slider",
                default_type="float",
                base_default=0.25,
                label_text="Transient Vocal Mix:",
                label_key="mix_vocal_label",
                section="transient",
                tooltip=(
                    "Transient vocal/mid energy weight for bubble pulse (0%–100%).\n"
                    "Higher = more mid-range response. 25% = default."
                ),
                minimum=0.0,
                maximum=1.0,
                tick_interval=10,
                scale=100.0,
                storage_kind="direct",
                display=_format_percent,
            )
        )
    if mode_key == "blob":
        defs.append(
            _ControlDef(
                control_key="blob_vocal_slider",
                config_key="blob_transient_mix_vocal",
                default_key="transient_mix_vocal",
                widget_kind="slider",
                default_type="float",
                base_default=0.35,
                label_text="Transient Vocal Mix:",
                label_key="blob_vocal_label",
                section="transient",
                tooltip=(
                    "Transient vocal/mid energy weight for blob deformation (0%–100%).\n"
                    "Higher = more mid-range response. 35% = default."
                ),
                minimum=0.0,
                maximum=1.0,
                tick_interval=10,
                scale=100.0,
                storage_kind="direct",
                display=_format_percent,
            )
        )
    return tuple(defs)


def _ensure_per_mode_cache(tab) -> Dict[str, Dict[str, Any]]:
    cache = getattr(tab, "_per_mode_technical_config", None)
    if not isinstance(cache, dict):
        cache = {}
        setattr(tab, "_per_mode_technical_config", cache)
    return cache


def _aligned_row(parent_layout: QVBoxLayout, label_text: str) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setContentsMargins(0, 6, 0, 6)
    row.setSpacing(12)
    add_section_label(row, label_text, 150)
    content = QHBoxLayout()
    content.setContentsMargins(0, 0, 0, 0)
    content.setSpacing(12)
    row.addLayout(content, 1)
    parent_layout.addLayout(row)
    return content


def _build_visibility_toggle(
    tab,
    parent_layout: QVBoxLayout,
    *,
    mode_key: str,
    bucket_key: str,
    label: str,
    default_visible: bool,
    helper_text: str,
) -> tuple[QCheckBox, QWidget]:
    toggle = QCheckBox(label)
    toggle.setProperty("circleIndicator", True)
    toggle.setToolTip(helper_text)
    getter = getattr(tab, "get_visualizer_tech_bucket_state", None)
    visible = default_visible
    if callable(getter):
        try:
            visible = bool(getter(mode_key, bucket_key, default_visible))
        except Exception:
            visible = default_visible
    toggle.blockSignals(True)
    toggle.setChecked(visible)
    toggle.blockSignals(False)

    toggle_row = _aligned_row(parent_layout, "")
    toggle_row.addWidget(toggle)
    toggle_row.addStretch()

    section = QWidget()
    section_layout = QVBoxLayout(section)
    section_layout.setContentsMargins(0, 0, 0, 0)
    section_layout.setSpacing(12)
    parent_layout.addWidget(section)

    def _apply_visibility(checked: bool) -> None:
        section.setVisible(checked)
        setter = getattr(tab, "set_visualizer_tech_bucket_state", None)
        if callable(setter):
            try:
                setter(mode_key, bucket_key, checked)
            except Exception:
                pass

    toggle.toggled.connect(_apply_visibility)
    _apply_visibility(visible)
    return toggle, section


def _aligned_row_widget(parent_layout: QVBoxLayout, label_text: str):
    container = QHBoxLayout()
    container.setContentsMargins(0, 6, 0, 6)
    container.setSpacing(12)
    add_section_label(container, label_text, 150)
    placeholder = QHBoxLayout()
    placeholder.setContentsMargins(0, 0, 0, 0)
    placeholder.setSpacing(12)
    container.addLayout(placeholder, 1)
    parent_layout.addLayout(container)
    return placeholder


def _connect_setting(signal, tab) -> None:
    signal.connect(tab._save_settings)
    auto_switch = getattr(tab, "_auto_switch_preset_to_custom", None)
    if callable(auto_switch):
        signal.connect(auto_switch)


def _per_mode_default_bool(tab, mode_key: str, key: str, base_default: bool) -> bool:
    baseline = tab._default_bool("spotify_visualizer", key, base_default)
    return tab._default_bool("spotify_visualizer", f"{mode_key}_{key}", baseline)


def _per_mode_default_int(tab, mode_key: str, key: str, base_default: int) -> int:
    baseline = tab._default_int("spotify_visualizer", key, base_default)
    return tab._default_int("spotify_visualizer", f"{mode_key}_{key}", baseline)


def _per_mode_default_float(tab, mode_key: str, key: str, base_default: float) -> float:
    baseline = tab._default_float("spotify_visualizer", key, base_default)
    return tab._default_float("spotify_visualizer", f"{mode_key}_{key}", baseline)


def _resolve_default(tab, mode_key: str, defn: _ControlDef) -> Any:
    if defn.default_type == "bool":
        return _per_mode_default_bool(tab, mode_key, defn.default_key, bool(defn.base_default))
    if defn.default_type == "int":
        return _per_mode_default_int(tab, mode_key, defn.default_key, int(defn.base_default))
    return _per_mode_default_float(tab, mode_key, defn.default_key, float(defn.base_default))


def _resolve_config_entry(config: Optional[Mapping[str, Any]], mode_key: str, key: str) -> Any:
    if not isinstance(config, Mapping):
        return None
    per_mode_key = f"{mode_key}_{key}"
    if per_mode_key in config:
        return config.get(per_mode_key)
    return config.get(key)


def _resolve_loaded_value(config: Optional[Mapping[str, Any]], mode_key: str, defn: _ControlDef) -> Any:
    if defn.storage_kind == "direct":
        if not isinstance(config, Mapping):
            return None
        return config.get(defn.config_key)
    return _resolve_config_entry(config, mode_key, defn.config_key)


def _storage_key(mode_key: str, defn: _ControlDef) -> str:
    if defn.storage_kind == "direct":
        return defn.config_key
    return f"{mode_key}_{defn.config_key}"


def _coerce_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return fallback if value is None else bool(value)


def _coerce_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _coerce_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _clamp_numeric(value: float, defn: _ControlDef) -> float:
    return max(defn.minimum, min(defn.maximum, value))


def _coerce_value(value: Any, defn: _ControlDef, fallback: Any) -> Any:
    if defn.default_type == "bool":
        return _coerce_bool(value, bool(fallback))
    if defn.default_type == "int":
        coerced = _coerce_int(value, int(fallback))
        if defn.widget_kind == "combo":
            return coerced
        return int(_clamp_numeric(coerced, defn))
    coerced = _coerce_float(value, float(fallback))
    return float(_clamp_numeric(coerced, defn))


def _slider_value_from_actual(value: float, defn: _ControlDef) -> int:
    return int(round(_clamp_numeric(value, defn) * defn.scale))


def _slider_actual_from_widget(widget: QSlider, defn: _ControlDef) -> float:
    return _clamp_numeric(widget.value() / defn.scale, defn)


def _set_label_text(controls: Dict[str, object], defn: _ControlDef, value: Any) -> None:
    if not defn.label_key or defn.display is None:
        return
    label = controls.get(defn.label_key)
    if label is not None:
        label.setText(defn.display(value))


def _create_hidden_control(tab, mode_key: str, defn: _ControlDef) -> Dict[str, object]:
    controls: Dict[str, object] = {}
    default_value = _resolve_default(tab, mode_key, defn)

    if defn.widget_kind == "slider":
        widget = NoWheelSlider(Qt.Orientation.Horizontal)
        widget.setMinimum(_slider_value_from_actual(defn.minimum, defn))
        widget.setMaximum(_slider_value_from_actual(defn.maximum, defn))
        if defn.tick_interval:
            widget.setTickPosition(QSlider.TickPosition.TicksBelow)
            widget.setTickInterval(defn.tick_interval)
        widget.blockSignals(True)
        widget.setValue(_slider_value_from_actual(default_value, defn))
        widget.blockSignals(False)
        widget.setVisible(False)
        controls[defn.control_key] = widget
        if defn.label_key:
            label = QLabel(defn.display(default_value) if defn.display else "")
            label.setVisible(False)
            controls[defn.label_key] = label
        _connect_setting(widget.valueChanged, tab)
        return controls

    if defn.widget_kind == "checkbox":
        widget = QCheckBox(defn.checkbox_text)
        widget.setVisible(False)
        if defn.circle_indicator:
            widget.setProperty("circleIndicator", True)
        widget.blockSignals(True)
        widget.setChecked(bool(default_value))
        widget.blockSignals(False)
        controls[defn.control_key] = widget
        _connect_setting(widget.stateChanged, tab)
        return controls

    raise ValueError(f"Unsupported hidden control kind: {defn.widget_kind}")


def _build_control(tab, parent_layout: QVBoxLayout, mode_key: str, defn: _ControlDef) -> Dict[str, object]:
    if defn.hidden:
        return _create_hidden_control(tab, mode_key, defn)

    controls: Dict[str, object] = {}
    default_value = _resolve_default(tab, mode_key, defn)

    if defn.widget_kind == "spinbox":
        row = _aligned_row(parent_layout, defn.label_text)
        widget = QSpinBox()
        widget.setRange(int(defn.minimum), int(defn.maximum))
        widget.setAccelerated(True)
        widget.blockSignals(True)
        widget.setValue(int(default_value))
        widget.blockSignals(False)
        row.addWidget(widget)
        if defn.suffix_text:
            row.addWidget(QLabel(defn.suffix_text))
        row.addStretch()
        _connect_setting(widget.valueChanged, tab)
        controls[defn.control_key] = widget
        return controls

    if defn.widget_kind == "combo":
        row = _aligned_row(parent_layout, defn.label_text)
        widget = StyledComboBox(size_variant="compact")
        if defn.min_width:
            widget.setMinimumWidth(defn.min_width)
        for label, value in defn.options:
            widget.addItem(label, value)
        idx = widget.findData(int(default_value))
        if idx < 0:
            idx = 0
        widget.blockSignals(True)
        widget.setCurrentIndex(idx)
        widget.blockSignals(False)
        row.addWidget(widget)
        row.addStretch()
        _connect_setting(widget.currentIndexChanged, tab)
        controls[defn.control_key] = widget
        return controls

    if defn.widget_kind == "checkbox":
        row = _aligned_row(parent_layout, defn.label_text)
        widget = QCheckBox(defn.checkbox_text)
        if defn.circle_indicator:
            widget.setProperty("circleIndicator", True)
        if defn.tooltip:
            widget.setToolTip(defn.tooltip)
        widget.blockSignals(True)
        widget.setChecked(bool(default_value))
        widget.blockSignals(False)
        row.addWidget(widget)
        row.addStretch()
        _connect_setting(widget.stateChanged, tab)
        controls[defn.control_key] = widget
        return controls

    if defn.widget_kind == "slider":
        row = _aligned_row(parent_layout, defn.label_text)
        widget = NoWheelSlider(Qt.Orientation.Horizontal)
        widget.setMinimum(_slider_value_from_actual(defn.minimum, defn))
        widget.setMaximum(_slider_value_from_actual(defn.maximum, defn))
        widget.setTickPosition(QSlider.TickPosition.TicksBelow)
        if defn.tick_interval:
            widget.setTickInterval(defn.tick_interval)
        if defn.tooltip:
            widget.setToolTip(defn.tooltip)
        widget.blockSignals(True)
        widget.setValue(_slider_value_from_actual(default_value, defn))
        widget.blockSignals(False)
        row.addWidget(widget)
        controls[defn.control_key] = widget
        if defn.label_key:
            label = QLabel(defn.display(default_value) if defn.display else "")
            row.addWidget(label)
            controls[defn.label_key] = label
            widget.valueChanged.connect(
                lambda _value, _controls=controls, _defn=defn, _widget=widget: _set_label_text(
                    _controls,
                    _defn,
                    _slider_actual_from_widget(_widget, _defn),
                )
            )
        _connect_setting(widget.valueChanged, tab)
        return controls

    raise ValueError(f"Unsupported control kind: {defn.widget_kind}")


def _build_bucket_sections(tab, layout: QVBoxLayout, mode_key: str) -> tuple[Dict[str, QWidget], Dict[str, QCheckBox]]:
    sections: Dict[str, QWidget] = {}
    toggles: Dict[str, QCheckBox] = {}
    for bucket in _BUCKET_DEFS:
        toggle, section = _build_visibility_toggle(
            tab,
            layout,
            mode_key=mode_key,
            bucket_key=bucket.key,
            label=bucket.label,
            default_visible=bucket.default_visible,
            helper_text=bucket.helper_text,
        )
        section_layout = section.layout()
        if section_layout is None:
            section_layout = QVBoxLayout()
            section.setLayout(section_layout)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(12)
        sections[bucket.key] = section
        toggles[bucket.key] = toggle
    return sections, toggles


def build_per_mode_technical_group(tab, parent_layout: QVBoxLayout, mode_key: str) -> QWidget:
    """Attach the per-mode Technical group to the given layout (collapsible)."""
    host = QWidget()
    host_layout = QVBoxLayout(host)
    host_layout.setContentsMargins(0, 0, 0, 0)
    host_layout.setSpacing(8)

    toggle_row = QHBoxLayout()
    toggle_row.setContentsMargins(0, 0, 0, 0)
    toggle_row.setSpacing(8)
    toggle = QToolButton()
    toggle.setText("Technical")
    toggle.setCheckable(True)
    default_expanded = True
    getter = getattr(tab, "get_visualizer_tech_state", None)
    if callable(getter):
        try:
            default_expanded = bool(getter(mode_key))
        except Exception:
            default_expanded = True
    toggle.setChecked(default_expanded)
    toggle.setArrowType(Qt.DownArrow if default_expanded else Qt.RightArrow)
    toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    toggle.setAutoRaise(True)
    toggle_row.addWidget(toggle)
    toggle_row.addStretch()
    host_layout.addLayout(toggle_row)

    helper = QLabel("Technical controls still apply when hidden.")
    helper.setProperty("class", "adv-helper")
    helper.setStyleSheet(ADV_HELPER_LABEL_STYLE)
    host_layout.addWidget(helper)

    group = QWidget()
    layout = QVBoxLayout(group)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    host_layout.addWidget(group)

    def _apply_toggle_state(checked: bool) -> None:
        toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        group.setVisible(checked)
        helper.setVisible(not checked)
        setter = getattr(tab, "set_visualizer_tech_state", None)
        if callable(setter):
            try:
                setter(mode_key, checked)
            except Exception:
                pass

    toggle.toggled.connect(_apply_toggle_state)
    _apply_toggle_state(default_expanded)

    sections, toggles = _build_bucket_sections(tab, layout, mode_key)
    section_layouts: Dict[str, QVBoxLayout] = {
        "root": layout,
        "agc": sections["agc"].layout(),
        "transient": sections["transient"].layout(),
    }

    per_mode_controls: Dict[str, Dict[str, object]] = getattr(tab, _PER_MODE_TECH_ATTR, {})
    per_mode_controls.setdefault("modes", {})

    controls: Dict[str, object] = {
        "group": group,
        "agc_visibility_toggle": toggles["agc"],
        "transient_visibility_toggle": toggles["transient"],
        "mode_key": mode_key,
    }
    defs = _control_defs_for_mode(mode_key)
    for defn in defs:
        controls.update(_build_control(tab, section_layouts[defn.section], mode_key, defn))

    def _update_sensitivity_visibility() -> None:
        adaptive_checkbox = controls.get("adaptive")
        sensitivity_slider = controls.get("sensitivity_slider")
        sensitivity_label = controls.get("sensitivity_label")
        if adaptive_checkbox is None or sensitivity_slider is None:
            return
        visible = not adaptive_checkbox.isChecked()
        sensitivity_slider.setEnabled(visible)
        if sensitivity_label is not None:
            sensitivity_label.setEnabled(visible)

    def _update_manual_floor_visibility() -> None:
        dynamic_floor = controls.get("dynamic_floor")
        manual_floor = controls.get("manual_floor")
        if dynamic_floor is None or manual_floor is None:
            return
        if dynamic_floor.isChecked():
            manual_floor.setToolTip(
                "Baseline floor (0.12–1.0) feeding the dynamic algorithm. Lower = more reactive."
            )
        else:
            manual_floor.setToolTip(
                "Absolute manual floor (0.12–1.0) when Dynamic Noise Floor is disabled."
            )

    adaptive_checkbox = controls.get("adaptive")
    if adaptive_checkbox is not None:
        adaptive_checkbox.stateChanged.connect(lambda _state: _update_sensitivity_visibility())
    dynamic_floor = controls.get("dynamic_floor")
    if dynamic_floor is not None:
        dynamic_floor.stateChanged.connect(lambda _state: _update_manual_floor_visibility())

    _update_sensitivity_visibility()
    _update_manual_floor_visibility()

    controls["update_sensitivity"] = _update_sensitivity_visibility
    controls["update_manual_floor"] = _update_manual_floor_visibility
    if "mix_slider" in controls:
        controls["mix_config_key"] = next(
            (defn.config_key for defn in defs if defn.control_key == "mix_slider"),
            None,
        )

    layout.addStretch()
    parent_layout.addWidget(host)

    per_mode_controls["modes"][mode_key] = controls
    setattr(tab, _PER_MODE_TECH_ATTR, per_mode_controls)
    return host


def register_per_mode_technical_controls(
    tab,
    mode_key: str,
    *,
    controls: Dict[str, object],
    update_sensitivity: Callable[[], None],
    update_manual_floor: Callable[[], None],
) -> None:
    """Register existing widgets as the per-mode technical control set."""
    per_mode_controls: Dict[str, Dict[str, object]] = getattr(tab, _PER_MODE_TECH_ATTR, {})
    per_mode_controls.setdefault("modes", {})
    stored = dict(controls)
    stored.setdefault("group", None)
    stored["update_sensitivity"] = update_sensitivity
    stored["update_manual_floor"] = update_manual_floor
    per_mode_controls["modes"][mode_key] = stored
    setattr(tab, _PER_MODE_TECH_ATTR, per_mode_controls)


def _per_mode_store(tab) -> Dict[str, Dict[str, object]]:
    store = getattr(tab, _PER_MODE_TECH_ATTR, {})
    return store.get("modes", {}) if isinstance(store, dict) else {}


def get_per_mode_controls(tab) -> Dict[str, Dict[str, object]]:
    """Return mapping of mode_key -> controls dict for the tab."""
    return _per_mode_store(tab)


def get_per_mode_controls_for_mode(tab, mode_key: str) -> Optional[Dict[str, object]]:
    return _per_mode_store(tab).get(mode_key)


def _apply_control_value(controls: Dict[str, object], defn: _ControlDef, value: Any) -> None:
    widget = controls.get(defn.control_key)
    if widget is None:
        return
    if defn.widget_kind == "spinbox":
        widget.blockSignals(True)
        widget.setValue(int(value))
        widget.blockSignals(False)
        return
    if defn.widget_kind == "combo":
        widget.blockSignals(True)
        idx = widget.findData(int(value))
        if idx < 0:
            idx = 0
        widget.setCurrentIndex(idx)
        widget.blockSignals(False)
        return
    if defn.widget_kind == "checkbox":
        widget.blockSignals(True)
        widget.setChecked(bool(value))
        widget.blockSignals(False)
        return
    if defn.widget_kind == "slider":
        widget.blockSignals(True)
        widget.setValue(_slider_value_from_actual(float(value), defn))
        widget.blockSignals(False)
        _set_label_text(controls, defn, float(value))
        return
    raise ValueError(f"Unsupported control kind: {defn.widget_kind}")


def _collect_control_value(controls: Dict[str, object], defn: _ControlDef) -> Any:
    widget = controls.get(defn.control_key)
    if widget is None:
        return None
    if defn.widget_kind == "spinbox":
        return int(widget.value())
    if defn.widget_kind == "combo":
        return int(widget.currentData() or 0)
    if defn.widget_kind == "checkbox":
        return bool(widget.isChecked())
    if defn.widget_kind == "slider":
        return _slider_actual_from_widget(widget, defn)
    raise ValueError(f"Unsupported control kind: {defn.widget_kind}")


def load_per_mode_technical_controls(tab, spotify_vis_config: Optional[Mapping[str, Any]]) -> None:
    """Populate per-mode technical widgets from the config mapping."""
    controls_map = get_per_mode_controls(tab)
    cache = _ensure_per_mode_cache(tab)

    for mode_key, controls in controls_map.items():
        mode_cache: Dict[str, Any] = {}
        for defn in _control_defs_for_mode(mode_key):
            if controls.get(defn.control_key) is None:
                continue
            default_value = _resolve_default(tab, mode_key, defn)
            loaded_value = _resolve_loaded_value(spotify_vis_config, mode_key, defn)
            resolved_value = _coerce_value(loaded_value, defn, default_value)
            _apply_control_value(controls, defn, resolved_value)
            mode_cache[_storage_key(mode_key, defn)] = resolved_value

        update_sensitivity = controls.get("update_sensitivity")
        if callable(update_sensitivity):
            update_sensitivity()
        update_manual_floor = controls.get("update_manual_floor")
        if callable(update_manual_floor):
            update_manual_floor()
        cache[mode_key] = mode_cache


def collect_per_mode_technical_controls(tab, spotify_vis_config: Dict[str, Any]) -> None:
    """Write per-mode technical values into the spotify_vis_config mapping."""
    controls_map = get_per_mode_controls(tab)
    cache = _ensure_per_mode_cache(tab)

    for mode_key, controls in controls_map.items():
        mode_cache: Dict[str, Any] = {}
        for defn in _control_defs_for_mode(mode_key):
            if controls.get(defn.control_key) is None:
                continue
            value = _collect_control_value(controls, defn)
            if value is None:
                continue
            storage_key = _storage_key(mode_key, defn)
            spotify_vis_config[storage_key] = value
            mode_cache[storage_key] = value
        cache[mode_key] = mode_cache

    for mode_cache in cache.values():
        for key, value in mode_cache.items():
            spotify_vis_config[key] = value
