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
MANUAL_FLOOR_MAX = 4.0


def _ensure_per_mode_cache(tab) -> Dict[str, Dict[str, Any]]:
    cache = getattr(tab, "_per_mode_technical_config", None)
    if not isinstance(cache, dict):
        cache = {}
        setattr(tab, "_per_mode_technical_config", cache)
    return cache


def _aligned_row(parent_layout: QVBoxLayout, label_text: str) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    add_section_label(row, label_text, 150)
    content = QHBoxLayout()
    content.setContentsMargins(0, 0, 0, 0)
    content.setSpacing(6)
    row.addLayout(content, 1)
    parent_layout.addLayout(row)
    return content


def _aligned_row_widget(parent_layout: QVBoxLayout, label_text: str):
    container = QHBoxLayout()
    container.setContentsMargins(0, 0, 0, 0)
    container.setSpacing(6)
    add_section_label(container, label_text, 150)
    placeholder = QHBoxLayout()
    placeholder.setContentsMargins(0, 0, 0, 0)
    placeholder.setSpacing(6)
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
    host_layout.setSpacing(4)

    toggle_row = QHBoxLayout()
    toggle_row.setContentsMargins(0, 0, 0, 0)
    toggle_row.setSpacing(6)
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
    layout.setSpacing(6)
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
    default_manual = _per_mode_default_float(tab, mode_key, 'manual_floor', 2.1)
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
                "Baseline floor feeding the dynamic algorithm. Lower = more reactive."
            )
        else:
            manual_floor.setToolTip(
                "Absolute manual floor when Dynamic Noise Floor is disabled."
            )

    adaptive_checkbox.stateChanged.connect(lambda _: _update_sensitivity_visibility())
    dynamic_floor.stateChanged.connect(lambda _: _update_manual_floor_visibility())
    _update_sensitivity_visibility()
    _update_manual_floor_visibility()

    per_mode_controls.setdefault('modes', {})
    per_mode_controls['modes'][mode_key] = {
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
        'update_sensitivity': _update_sensitivity_visibility,
        'update_manual_floor': _update_manual_floor_visibility,
        'mode_key': mode_key,
    }
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
            default_manual = _per_mode_default_float(tab, mode_key, 'manual_floor', 2.1)
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

    # Ensure cached values for all modes (including dev-gated ones without UI)
    # are flushed back into the config so custom presets can persist them.
    for mode_key, mode_cache in cache.items():
        for key, value in mode_cache.items():
            spotify_vis_config[f'{mode_key}_{key}'] = value


