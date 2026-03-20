"""Shared per-mode technical controls for Spotify visualizer modes."""
from __future__ import annotations

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

from ui.tabs.shared_styles import add_section_label, ADV_HELPER_LABEL_STYLE
from ui.widgets import StyledComboBox
from ui.tabs.widgets_tab import NoWheelSlider


_PER_MODE_TECH_ATTR = "_per_mode_technical_controls"
MANUAL_FLOOR_MIN = 0.05
MANUAL_FLOOR_MAX = 1.0

# Transient slider gating: which modes each slider is active for.
_KICK_GAIN_MODES = frozenset({"spectrum"})
_PULSE_GAIN_MODES = frozenset({"bubble"})
# transient_clamp is global — no mode restriction.


_KICK_GAIN_TIP = (
    "Spectrum kick express-lane gain (0%\u2013200%). Controls how strongly\n"
    "transient bass energy bypasses smoothing for immediate kick response.\n"
    "0% = disabled, 100% = default, 200% = double."
)
_PULSE_GAIN_TIP = (
    "Transient pulse gain (0%\u2013300%). Controls how strongly transient\n"
    "bass energy mixes into bubble/blob pulse amplitude.\n"
    "0% = disabled, 100% = default, 300% = triple."
)
_KICK_GAIN_DISABLED_TIP = "Kick lane gain is active in Spectrum mode only."
_PULSE_GAIN_DISABLED_TIP = "Transient pulse gain is active in Bubble mode only."


def _apply_transient_gating(mode_key: str, controls: Dict[str, object]) -> None:
    """Enable/disable transient sliders based on the active mode.

    - kick_lane_gain: Spectrum only
    - transient_pulse_gain: Bubble only
    - transient_clamp: all modes (global)
    """
    kick_en = mode_key in _KICK_GAIN_MODES
    pulse_en = mode_key in _PULSE_GAIN_MODES

    for key in ('kick_gain_slider', 'kick_gain_label'):
        w = controls.get(key)
        if w is not None:
            w.setEnabled(kick_en)
            if hasattr(w, 'setToolTip'):
                w.setToolTip(_KICK_GAIN_TIP if kick_en else _KICK_GAIN_DISABLED_TIP)

    for key in ('pulse_gain_slider', 'pulse_gain_label'):
        w = controls.get(key)
        if w is not None:
            w.setEnabled(pulse_en)
            if hasattr(w, 'setToolTip'):
                w.setToolTip(_PULSE_GAIN_TIP if pulse_en else _PULSE_GAIN_DISABLED_TIP)


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
    auto_switch = getattr(tab, '_auto_switch_preset_to_custom', None)
    if callable(auto_switch):
        signal.connect(auto_switch)


def _per_mode_default_bool(tab, mode_key: str, key: str, base_default: bool) -> bool:
    baseline = tab._default_bool('spotify_visualizer', key, base_default)
    return tab._default_bool('spotify_visualizer', f"{mode_key}_{key}", baseline)


def _per_mode_default_int(tab, mode_key: str, key: str, base_default: int) -> int:
    baseline = tab._default_int('spotify_visualizer', key, base_default)
    return tab._default_int('spotify_visualizer', f"{mode_key}_{key}", baseline)


def _per_mode_default_float(tab, mode_key: str, key: str, base_default: float) -> float:
    baseline = tab._default_float('spotify_visualizer', key, base_default)
    return tab._default_float('spotify_visualizer', f"{mode_key}_{key}", baseline)


def build_per_mode_technical_group(tab, parent_layout: QVBoxLayout, mode_key: str) -> QWidget:
    """Attach the per-mode Technical group to the given layout (collapsible).

    Returns the host widget so callers can register it with the preset
    slider for auto-hide when a non-Custom preset is selected.
    """
    # Host with toggle + helper (mirrors Advanced styling)
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

    # Bar count
    bar_row = _aligned_row(layout, "Bar Count:")
    bar_count = QSpinBox()
    bar_count.setRange(8, 96)
    default_bar = _per_mode_default_int(tab, mode_key, 'bar_count', 32)
    bar_count.blockSignals(True)
    bar_count.setValue(default_bar)
    bar_count.blockSignals(False)
    bar_count.setAccelerated(True)
    _connect_setting(bar_count.valueChanged, tab)
    bar_row.addWidget(bar_count)
    bar_row.addWidget(QLabel("bars"))
    bar_row.addStretch()

    # Audio block size
    block_row = _aligned_row(layout, "Audio Block Size:")
    block_size = StyledComboBox(size_variant="compact")
    block_size.setMinimumWidth(140)
    for label, value in (
        ("Auto (Driver)", 0),
        ("128 samples", 128),
        ("256 samples", 256),
        ("512 samples", 512),
        ("1024 samples", 1024),
    ):
        block_size.addItem(label, value)
    default_block = _per_mode_default_int(tab, mode_key, 'audio_block_size', 0)
    block_size.blockSignals(True)
    idx = block_size.findData(default_block)
    if idx < 0:
        idx = 0
    block_size.setCurrentIndex(idx)
    block_size.blockSignals(False)
    _connect_setting(block_size.currentIndexChanged, tab)
    block_row.addWidget(block_size)
    block_row.addStretch()

    # Adaptive sensitivity toggle
    adaptive_row = _aligned_row(layout, "")
    adaptive_checkbox = QCheckBox("Adaptive Sensitivity")
    adaptive_checkbox.setProperty("circleIndicator", True)
    adaptive_default = _per_mode_default_bool(tab, mode_key, 'adaptive_sensitivity', True)
    adaptive_checkbox.blockSignals(True)
    adaptive_checkbox.setChecked(adaptive_default)
    adaptive_checkbox.blockSignals(False)
    _connect_setting(adaptive_checkbox.stateChanged, tab)
    adaptive_row.addWidget(adaptive_checkbox)
    adaptive_row.addStretch()

    # Sensitivity slider
    sens_row = _aligned_row(layout, "Sensitivity:")
    sensitivity_slider = NoWheelSlider(Qt.Orientation.Horizontal)
    sensitivity_slider.setMinimum(25)
    sensitivity_slider.setMaximum(250)
    sensitivity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    sensitivity_slider.setTickInterval(25)
    default_sens = _per_mode_default_float(tab, mode_key, 'sensitivity', 1.0)
    sensitivity_slider.blockSignals(True)
    sensitivity_slider.setValue(int(max(0.25, min(2.5, default_sens)) * 100))
    sensitivity_slider.blockSignals(False)
    _connect_setting(sensitivity_slider.valueChanged, tab)
    sens_row.addWidget(sensitivity_slider)
    sensitivity_label = QLabel(f"{default_sens:.2f}x")
    sensitivity_slider.valueChanged.connect(lambda v: sensitivity_label.setText(f"{v / 100.0:.2f}x"))
    sens_row.addWidget(sensitivity_label)

    # Dynamic range toggle
    dyn_range_row = _aligned_row(layout, "")
    dynamic_range = QCheckBox("Dynamic Range Boost")
    dynamic_range.setProperty("circleIndicator", True)
    dynamic_range_default = _per_mode_default_bool(tab, mode_key, 'dynamic_range_enabled', False)
    dynamic_range.blockSignals(True)
    dynamic_range.setChecked(dynamic_range_default)
    dynamic_range.blockSignals(False)
    _connect_setting(dynamic_range.stateChanged, tab)
    dyn_range_row.addWidget(dynamic_range)
    dyn_range_row.addStretch()

    # Energy Boost slider — DEPRECATED (kept for preset compat, hidden from UI)
    energy_boost_slider = NoWheelSlider(Qt.Orientation.Horizontal)
    energy_boost_slider.setMinimum(50)
    energy_boost_slider.setMaximum(180)
    default_eb = _per_mode_default_float(tab, mode_key, 'energy_boost', 0.85)
    clamped_eb = max(0.5, min(1.8, default_eb))
    energy_boost_slider.blockSignals(True)
    energy_boost_slider.setValue(int(clamped_eb * 100))
    energy_boost_slider.blockSignals(False)
    _connect_setting(energy_boost_slider.valueChanged, tab)
    energy_boost_slider.setVisible(False)
    energy_boost_label = QLabel(f"{clamped_eb:.2f}x")
    energy_boost_label.setVisible(False)

    # AGC Strength slider
    agc_row = _aligned_row(layout, "AGC Strength:")
    agc_strength_slider = NoWheelSlider(Qt.Orientation.Horizontal)
    agc_strength_slider.setMinimum(0)
    agc_strength_slider.setMaximum(100)
    agc_strength_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    agc_strength_slider.setTickInterval(10)
    default_agc = _per_mode_default_float(tab, mode_key, 'agc_strength', 0.5)
    clamped_agc = max(0.0, min(1.0, default_agc))
    agc_strength_slider.blockSignals(True)
    agc_strength_slider.setValue(int(clamped_agc * 100))
    agc_strength_slider.blockSignals(False)
    agc_strength_slider.setToolTip(
        "AGC normalization aggressiveness (0%=off, 50%=default, 100%=max compression).\n"
        "Lower values preserve more dynamic range. 0% disables normalization entirely."
    )
    _connect_setting(agc_strength_slider.valueChanged, tab)
    agc_row.addWidget(agc_strength_slider)
    agc_strength_label = QLabel(f"{int(clamped_agc * 100)}%")
    agc_strength_slider.valueChanged.connect(lambda v: agc_strength_label.setText(f"{v}%"))
    agc_row.addWidget(agc_strength_label)

    # Input Gain (Virtual Volume) slider
    input_gain_row = _aligned_row(layout, "Input Gain:")
    input_gain_slider = NoWheelSlider(Qt.Orientation.Horizontal)
    input_gain_slider.setMinimum(5)
    input_gain_slider.setMaximum(200)
    input_gain_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    input_gain_slider.setTickInterval(25)
    default_ig = _per_mode_default_float(tab, mode_key, 'input_gain', 1.0)
    clamped_ig = max(0.05, min(2.0, default_ig))
    input_gain_slider.blockSignals(True)
    input_gain_slider.setValue(int(clamped_ig * 100))
    input_gain_slider.blockSignals(False)
    input_gain_slider.setToolTip(
        "Pre-FFT signal gain (5%\u2013200%). Simulates changing the mixer volume\n"
        "without actually affecting audio output. Lower = calmer visualizer,\n"
        "higher = more reactive. 100% = no change (default)."
    )
    _connect_setting(input_gain_slider.valueChanged, tab)
    input_gain_row.addWidget(input_gain_slider)
    input_gain_label = QLabel(f"{int(clamped_ig * 100)}%")
    input_gain_slider.valueChanged.connect(lambda v: input_gain_label.setText(f"{v}%"))
    input_gain_row.addWidget(input_gain_label)

    # Use Raw Energy toggle — DEPRECATED (replaced by transient bus, hidden from UI)
    raw_energy_checkbox = QCheckBox("Use Raw (Pre-AGC) Energy")
    raw_energy_checkbox.setProperty("circleIndicator", True)
    raw_energy_default = _per_mode_default_bool(tab, mode_key, 'use_raw_energy', False)
    raw_energy_checkbox.blockSignals(True)
    raw_energy_checkbox.setChecked(raw_energy_default)
    raw_energy_checkbox.blockSignals(False)
    _connect_setting(raw_energy_checkbox.stateChanged, tab)
    raw_energy_checkbox.setVisible(False)

    # ── Transient Bus Controls (Approach A dual-path) ──────────────────
    kick_gain_row = _aligned_row(layout, "Kick Lane Gain:")
    kick_gain_slider = NoWheelSlider(Qt.Orientation.Horizontal)
    kick_gain_slider.setMinimum(0)
    kick_gain_slider.setMaximum(200)
    kick_gain_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    kick_gain_slider.setTickInterval(25)
    default_kg = _per_mode_default_float(tab, mode_key, 'kick_lane_gain', 1.0)
    clamped_kg = max(0.0, min(2.0, default_kg))
    kick_gain_slider.blockSignals(True)
    kick_gain_slider.setValue(int(clamped_kg * 100))
    kick_gain_slider.blockSignals(False)
    kick_gain_slider.setToolTip(
        "Spectrum kick express-lane gain (0%\u2013200%). Controls how strongly\n"
        "transient bass energy bypasses smoothing for immediate kick response.\n"
        "0% = disabled, 100% = default, 200% = double."
    )
    _connect_setting(kick_gain_slider.valueChanged, tab)
    kick_gain_row.addWidget(kick_gain_slider)
    kick_gain_label = QLabel(f"{int(clamped_kg * 100)}%")
    kick_gain_slider.valueChanged.connect(lambda v: kick_gain_label.setText(f"{v}%"))
    kick_gain_row.addWidget(kick_gain_label)

    pulse_gain_row = _aligned_row(layout, "Transient Pulse:")
    pulse_gain_slider = NoWheelSlider(Qt.Orientation.Horizontal)
    pulse_gain_slider.setMinimum(0)
    pulse_gain_slider.setMaximum(300)
    pulse_gain_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    pulse_gain_slider.setTickInterval(50)
    default_pg = _per_mode_default_float(tab, mode_key, 'transient_pulse_gain', 1.0)
    clamped_pg = max(0.0, min(3.0, default_pg))
    pulse_gain_slider.blockSignals(True)
    pulse_gain_slider.setValue(int(clamped_pg * 100))
    pulse_gain_slider.blockSignals(False)
    pulse_gain_slider.setToolTip(
        "Transient pulse gain (0%\u2013300%). Controls how strongly transient\n"
        "bass energy mixes into bubble/blob pulse amplitude.\n"
        "0% = disabled, 100% = default, 300% = triple."
    )
    _connect_setting(pulse_gain_slider.valueChanged, tab)
    pulse_gain_row.addWidget(pulse_gain_slider)
    pulse_gain_label = QLabel(f"{int(clamped_pg * 100)}%")
    pulse_gain_slider.valueChanged.connect(lambda v: pulse_gain_label.setText(f"{v}%"))
    pulse_gain_row.addWidget(pulse_gain_label)

    clamp_row = _aligned_row(layout, "Transient Clamp:")
    clamp_slider = NoWheelSlider(Qt.Orientation.Horizontal)
    clamp_slider.setMinimum(0)
    clamp_slider.setMaximum(300)
    clamp_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    clamp_slider.setTickInterval(50)
    default_tc = _per_mode_default_float(tab, mode_key, 'transient_clamp', 1.5)
    clamped_tc = max(0.0, min(3.0, default_tc))
    clamp_slider.blockSignals(True)
    clamp_slider.setValue(int(clamped_tc * 100))
    clamp_slider.blockSignals(False)
    clamp_slider.setToolTip(
        "Maximum transient-boosted bass energy (0%\u2013300%). Prevents\n"
        "transient spikes from blowing out the visualizer. 150% = default."
    )
    _connect_setting(clamp_slider.valueChanged, tab)
    clamp_row.addWidget(clamp_slider)
    clamp_label = QLabel(f"{int(clamped_tc * 100)}%")
    clamp_slider.valueChanged.connect(lambda v: clamp_label.setText(f"{v}%"))
    clamp_row.addWidget(clamp_label)

    # Dynamic floor toggle
    dyn_floor_row = _aligned_row(layout, "")
    dynamic_floor = QCheckBox("Dynamic Noise Floor")
    dynamic_floor.setProperty("circleIndicator", True)
    dynamic_floor_default = _per_mode_default_bool(tab, mode_key, 'dynamic_floor', True)
    dynamic_floor.blockSignals(True)
    dynamic_floor.setChecked(dynamic_floor_default)
    dynamic_floor.blockSignals(False)
    _connect_setting(dynamic_floor.stateChanged, tab)
    dyn_floor_row.addWidget(dynamic_floor)
    dyn_floor_row.addStretch()

    # Manual floor slider
    manual_container = _aligned_row(layout, "Manual Floor\nBaseline:")
    manual_floor = NoWheelSlider(Qt.Orientation.Horizontal)
    manual_floor.setMinimum(int(MANUAL_FLOOR_MIN * 100))
    manual_floor.setMaximum(int(MANUAL_FLOOR_MAX * 100))
    manual_floor.setTickPosition(QSlider.TickPosition.TicksBelow)
    manual_floor.setTickInterval(10)
    default_manual = _per_mode_default_float(tab, mode_key, 'manual_floor', 0.12)
    manual_floor.blockSignals(True)
    clamped_manual = max(MANUAL_FLOOR_MIN, min(MANUAL_FLOOR_MAX, default_manual))
    manual_floor.setValue(int(clamped_manual * 100))
    manual_floor.blockSignals(False)
    manual_floor.setToolTip(
        "Sets the baseline noise floor used by both Manual and Dynamic modes."
    )
    _connect_setting(manual_floor.valueChanged, tab)
    manual_container.addWidget(manual_floor)
    manual_label = QLabel(f"{clamped_manual:.2f}")
    manual_floor.valueChanged.connect(lambda v: manual_label.setText(f"{v / 100.0:.2f}"))
    manual_container.addWidget(manual_label)

    layout.addStretch()
    parent_layout.addWidget(host)

    per_mode_controls: Dict[str, Dict[str, object]] = getattr(tab, _PER_MODE_TECH_ATTR, {})

    def _update_sensitivity_visibility() -> None:
        visible = not adaptive_checkbox.isChecked()
        for widget in (sensitivity_slider, sensitivity_label):
            widget.setEnabled(visible)

    def _update_manual_floor_visibility() -> None:
        if dynamic_floor.isChecked():
            manual_floor.setToolTip(
                "Baseline floor (0.12–1.0) feeding the dynamic algorithm. Lower = more reactive."
            )
        else:
            manual_floor.setToolTip(
                "Absolute manual floor (0.12–1.0) when Dynamic Noise Floor is disabled."
            )

    adaptive_checkbox.stateChanged.connect(lambda _: _update_sensitivity_visibility())
    dynamic_floor.stateChanged.connect(lambda _: _update_manual_floor_visibility())
    _update_sensitivity_visibility()
    _update_manual_floor_visibility()

    per_mode_controls.setdefault('modes', {})
    _controls_dict = {
        'group': group,
        'bar_count': bar_count,
        'block_size': block_size,
        'adaptive': adaptive_checkbox,
        'sensitivity_slider': sensitivity_slider,
        'sensitivity_label': sensitivity_label,
        'dynamic_floor': dynamic_floor,
        'manual_floor': manual_floor,
        'manual_label': manual_label,
        'dynamic_range': dynamic_range,
        'energy_boost_slider': energy_boost_slider,
        'energy_boost_label': energy_boost_label,
        'agc_strength_slider': agc_strength_slider,
        'agc_strength_label': agc_strength_label,
        'input_gain_slider': input_gain_slider,
        'input_gain_label': input_gain_label,
        'raw_energy': raw_energy_checkbox,
        'kick_gain_slider': kick_gain_slider,
        'kick_gain_label': kick_gain_label,
        'pulse_gain_slider': pulse_gain_slider,
        'pulse_gain_label': pulse_gain_label,
        'clamp_slider': clamp_slider,
        'clamp_label': clamp_label,
        'update_sensitivity': _update_sensitivity_visibility,
        'update_manual_floor': _update_manual_floor_visibility,
        'mode_key': mode_key,
    }
    per_mode_controls['modes'][mode_key] = _controls_dict
    setattr(tab, _PER_MODE_TECH_ATTR, per_mode_controls)

    _apply_transient_gating(mode_key, _controls_dict)

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
    per_mode_controls.setdefault('modes', {})
    stored = dict(controls)
    stored.setdefault('group', None)
    stored['update_sensitivity'] = update_sensitivity
    stored['update_manual_floor'] = update_manual_floor
    per_mode_controls['modes'][mode_key] = stored
    setattr(tab, _PER_MODE_TECH_ATTR, per_mode_controls)


def _per_mode_store(tab) -> Dict[str, Dict[str, object]]:
    store = getattr(tab, _PER_MODE_TECH_ATTR, {})
    return store.get('modes', {}) if isinstance(store, dict) else {}


def get_per_mode_controls(tab) -> Dict[str, Dict[str, object]]:
    """Return mapping of mode_key -> controls dict for the tab."""
    return _per_mode_store(tab)


def get_per_mode_controls_for_mode(tab, mode_key: str) -> Optional[Dict[str, object]]:
    return _per_mode_store(tab).get(mode_key)


def _resolve_config_entry(config: Optional[Mapping[str, Any]], mode_key: str, key: str) -> Any:
    if not isinstance(config, Mapping):
        return None
    per_mode_key = f"{mode_key}_{key}"
    if per_mode_key in config:
        return config.get(per_mode_key)
    return config.get(key)


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


def load_per_mode_technical_controls(tab, spotify_vis_config: Optional[Mapping[str, Any]]) -> None:
    """Populate per-mode technical widgets from the config mapping."""
    controls_map = get_per_mode_controls(tab)
    cache = _ensure_per_mode_cache(tab)
    for mode_key, controls in controls_map.items():
        mode_cache = cache.setdefault(mode_key, {})
        bar = controls.get('bar_count')
        if bar is not None:
            default_bar = _per_mode_default_int(tab, mode_key, 'bar_count', 32)
            bar_val = _coerce_int(_resolve_config_entry(spotify_vis_config, mode_key, 'bar_count'), default_bar)
            bar.blockSignals(True)
            bar.setValue(max(bar.minimum(), min(bar.maximum(), bar_val)))
            bar.blockSignals(False)
            mode_cache['bar_count'] = bar_val

        block_combo: Optional[StyledComboBox] = controls.get('block_size')  # type: ignore[assignment]
        if block_combo is not None:
            default_block = _per_mode_default_int(tab, mode_key, 'audio_block_size', 0)
            block_val = _coerce_int(_resolve_config_entry(spotify_vis_config, mode_key, 'audio_block_size'), default_block)
            block_combo.blockSignals(True)
            idx = block_combo.findData(block_val)
            if idx < 0:
                idx = 0
            block_combo.setCurrentIndex(idx)
            block_combo.blockSignals(False)
            mode_cache['audio_block_size'] = block_val

        adaptive = controls.get('adaptive')
        if adaptive is not None:
            default_adaptive = _per_mode_default_bool(tab, mode_key, 'adaptive_sensitivity', True)
            adaptive_val = _coerce_bool(_resolve_config_entry(spotify_vis_config, mode_key, 'adaptive_sensitivity'), default_adaptive)
            adaptive.blockSignals(True)
            adaptive.setChecked(adaptive_val)
            adaptive.blockSignals(False)
            mode_cache['adaptive_sensitivity'] = adaptive_val

        sens_slider = controls.get('sensitivity_slider')
        if sens_slider is not None:
            default_sens = _per_mode_default_float(tab, mode_key, 'sensitivity', 1.0)
            sens_val = _coerce_float(_resolve_config_entry(spotify_vis_config, mode_key, 'sensitivity'), default_sens)
            sens_slider.blockSignals(True)
            sens_slider.setValue(int(max(0.25, min(2.5, sens_val)) * 100))
            sens_slider.blockSignals(False)
            sensitivity_label = controls.get('sensitivity_label')
            if sensitivity_label is not None:
                sensitivity_label.setText(f"{max(0.25, min(2.5, sens_val)):.2f}x")
            mode_cache['sensitivity'] = max(0.25, min(2.5, sens_val))

        dyn_range = controls.get('dynamic_range')
        if dyn_range is not None:
            default_dyn_range = _per_mode_default_bool(tab, mode_key, 'dynamic_range_enabled', False)
            dyn_range_val = _coerce_bool(_resolve_config_entry(spotify_vis_config, mode_key, 'dynamic_range_enabled'), default_dyn_range)
            dyn_range.blockSignals(True)
            dyn_range.setChecked(dyn_range_val)
            dyn_range.blockSignals(False)
            mode_cache['dynamic_range_enabled'] = dyn_range_val

        eb_slider = controls.get('energy_boost_slider')
        if eb_slider is not None:
            default_eb = _per_mode_default_float(tab, mode_key, 'energy_boost', 0.85)
            eb_val = _coerce_float(_resolve_config_entry(spotify_vis_config, mode_key, 'energy_boost'), default_eb)
            clamped_eb = max(0.5, min(1.8, eb_val))
            eb_slider.blockSignals(True)
            eb_slider.setValue(int(clamped_eb * 100))
            eb_slider.blockSignals(False)
            eb_label = controls.get('energy_boost_label')
            if eb_label is not None:
                eb_label.setText(f"{clamped_eb:.2f}x")
            mode_cache['energy_boost'] = clamped_eb

        agc_slider = controls.get('agc_strength_slider')
        if agc_slider is not None:
            default_agc = _per_mode_default_float(tab, mode_key, 'agc_strength', 0.5)
            agc_val = _coerce_float(_resolve_config_entry(spotify_vis_config, mode_key, 'agc_strength'), default_agc)
            clamped_agc = max(0.0, min(1.0, agc_val))
            agc_slider.blockSignals(True)
            agc_slider.setValue(int(clamped_agc * 100))
            agc_slider.blockSignals(False)
            agc_label = controls.get('agc_strength_label')
            if agc_label is not None:
                agc_label.setText(f"{int(clamped_agc * 100)}%")
            mode_cache['agc_strength'] = clamped_agc

        ig_slider = controls.get('input_gain_slider')
        if ig_slider is not None:
            default_ig = _per_mode_default_float(tab, mode_key, 'input_gain', 1.0)
            ig_val = _coerce_float(_resolve_config_entry(spotify_vis_config, mode_key, 'input_gain'), default_ig)
            clamped_ig = max(0.05, min(2.0, ig_val))
            ig_slider.blockSignals(True)
            ig_slider.setValue(int(clamped_ig * 100))
            ig_slider.blockSignals(False)
            ig_label = controls.get('input_gain_label')
            if ig_label is not None:
                ig_label.setText(f"{int(clamped_ig * 100)}%")
            mode_cache['input_gain'] = clamped_ig

        raw_energy = controls.get('raw_energy')
        if raw_energy is not None:
            default_raw = _per_mode_default_bool(tab, mode_key, 'use_raw_energy', False)
            raw_val = _coerce_bool(_resolve_config_entry(spotify_vis_config, mode_key, 'use_raw_energy'), default_raw)
            raw_energy.blockSignals(True)
            raw_energy.setChecked(raw_val)
            raw_energy.blockSignals(False)
            mode_cache['use_raw_energy'] = raw_val

        # Transient bus controls (Approach A)
        kg_slider = controls.get('kick_gain_slider')
        if kg_slider is not None:
            default_kg = _per_mode_default_float(tab, mode_key, 'kick_lane_gain', 1.0)
            kg_val = _coerce_float(_resolve_config_entry(spotify_vis_config, mode_key, 'kick_lane_gain'), default_kg)
            clamped_kg = max(0.0, min(2.0, kg_val))
            kg_slider.blockSignals(True)
            kg_slider.setValue(int(clamped_kg * 100))
            kg_slider.blockSignals(False)
            kg_label = controls.get('kick_gain_label')
            if kg_label is not None:
                kg_label.setText(f"{int(clamped_kg * 100)}%")
            mode_cache['kick_lane_gain'] = clamped_kg

        pg_slider = controls.get('pulse_gain_slider')
        if pg_slider is not None:
            default_pg = _per_mode_default_float(tab, mode_key, 'transient_pulse_gain', 1.0)
            pg_val = _coerce_float(_resolve_config_entry(spotify_vis_config, mode_key, 'transient_pulse_gain'), default_pg)
            clamped_pg = max(0.0, min(3.0, pg_val))
            pg_slider.blockSignals(True)
            pg_slider.setValue(int(clamped_pg * 100))
            pg_slider.blockSignals(False)
            pg_label = controls.get('pulse_gain_label')
            if pg_label is not None:
                pg_label.setText(f"{int(clamped_pg * 100)}%")
            mode_cache['transient_pulse_gain'] = clamped_pg

        tc_slider = controls.get('clamp_slider')
        if tc_slider is not None:
            default_tc = _per_mode_default_float(tab, mode_key, 'transient_clamp', 1.5)
            tc_val = _coerce_float(_resolve_config_entry(spotify_vis_config, mode_key, 'transient_clamp'), default_tc)
            clamped_tc = max(0.0, min(3.0, tc_val))
            tc_slider.blockSignals(True)
            tc_slider.setValue(int(clamped_tc * 100))
            tc_slider.blockSignals(False)
            tc_label = controls.get('clamp_label')
            if tc_label is not None:
                tc_label.setText(f"{int(clamped_tc * 100)}%")
            mode_cache['transient_clamp'] = clamped_tc

        dyn_floor = controls.get('dynamic_floor')
        if dyn_floor is not None:
            default_dyn_floor = _per_mode_default_bool(tab, mode_key, 'dynamic_floor', True)
            dyn_floor_val = _coerce_bool(_resolve_config_entry(spotify_vis_config, mode_key, 'dynamic_floor'), default_dyn_floor)
            dyn_floor.blockSignals(True)
            dyn_floor.setChecked(dyn_floor_val)
            dyn_floor.blockSignals(False)
            mode_cache['dynamic_floor'] = dyn_floor_val

        manual_slider = controls.get('manual_floor')
        if manual_slider is not None:
            default_manual = _per_mode_default_float(tab, mode_key, 'manual_floor', MANUAL_FLOOR_MIN)
            manual_val = _coerce_float(_resolve_config_entry(spotify_vis_config, mode_key, 'manual_floor'), default_manual)
            clamped = max(MANUAL_FLOOR_MIN, min(MANUAL_FLOOR_MAX, manual_val))
            manual_slider.blockSignals(True)
            manual_slider.setValue(int(clamped * 100))
            manual_slider.blockSignals(False)
            manual_label = controls.get('manual_label')
            if manual_label is not None:
                manual_label.setText(f"{clamped:.2f}")
            mode_cache['manual_floor'] = clamped

        update_sensitivity = controls.get('update_sensitivity')
        if callable(update_sensitivity):
            update_sensitivity()
        update_manual_floor = controls.get('update_manual_floor')
        if callable(update_manual_floor):
            update_manual_floor()

        _apply_transient_gating(mode_key, controls)


def collect_per_mode_technical_controls(tab, spotify_vis_config: Dict[str, Any]) -> None:
    """Write per-mode technical values into the spotify_vis_config mapping."""
    controls_map = get_per_mode_controls(tab)
    cache = _ensure_per_mode_cache(tab)
    for mode_key, controls in controls_map.items():
        mode_cache = cache.setdefault(mode_key, {})

        def _set(key: str, value: Any) -> None:
            spotify_vis_config[f'{mode_key}_{key}'] = value
            mode_cache[key] = value

        bar = controls.get('bar_count')
        if bar is not None:
            _set('bar_count', bar.value())
        block_combo = controls.get('block_size')
        if block_combo is not None:
            _set('audio_block_size', int(block_combo.currentData() or 0))
        adaptive = controls.get('adaptive')
        if adaptive is not None:
            _set('adaptive_sensitivity', adaptive.isChecked())
        sens_slider = controls.get('sensitivity_slider')
        if sens_slider is not None:
            _set('sensitivity', max(0.25, min(2.5, sens_slider.value() / 100.0)))
        dyn_floor = controls.get('dynamic_floor')
        if dyn_floor is not None:
            _set('dynamic_floor', dyn_floor.isChecked())
        manual_slider = controls.get('manual_floor')
        if manual_slider is not None:
            _set('manual_floor', max(MANUAL_FLOOR_MIN, min(MANUAL_FLOOR_MAX, manual_slider.value() / 100.0)))
        dyn_range = controls.get('dynamic_range')
        if dyn_range is not None:
            _set('dynamic_range_enabled', dyn_range.isChecked())
        eb_slider = controls.get('energy_boost_slider')
        if eb_slider is not None:
            _set('energy_boost', max(0.5, min(1.8, eb_slider.value() / 100.0)))
        agc_slider = controls.get('agc_strength_slider')
        if agc_slider is not None:
            _set('agc_strength', max(0.0, min(1.0, agc_slider.value() / 100.0)))
        ig_slider = controls.get('input_gain_slider')
        if ig_slider is not None:
            _set('input_gain', max(0.05, min(2.0, ig_slider.value() / 100.0)))
        raw_energy = controls.get('raw_energy')
        if raw_energy is not None:
            _set('use_raw_energy', raw_energy.isChecked())
        # Transient bus controls (Approach A)
        kg_slider = controls.get('kick_gain_slider')
        if kg_slider is not None:
            _set('kick_lane_gain', max(0.0, min(2.0, kg_slider.value() / 100.0)))
        pg_slider = controls.get('pulse_gain_slider')
        if pg_slider is not None:
            _set('transient_pulse_gain', max(0.0, min(3.0, pg_slider.value() / 100.0)))
        tc_slider = controls.get('clamp_slider')
        if tc_slider is not None:
            _set('transient_clamp', max(0.0, min(3.0, tc_slider.value() / 100.0)))

    # Ensure cached values for all modes (including dev-gated ones without UI)
    # are flushed back into the config so custom presets can persist them.
    for mode_key, mode_cache in cache.items():
        for key, value in mode_cache.items():
            spotify_vis_config[f'{mode_key}_{key}'] = value


