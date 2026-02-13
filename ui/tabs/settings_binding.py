"""Declarative settings binding for UI tabs.

Reduces save/load boilerplate by defining widget↔config key mappings
as data descriptors. Each binding knows how to:
- Load a value from config dict → set on widget
- Save a value from widget → config dict
- Update an optional label

Usage:
    BINDINGS = [
        SliderBinding('osc_speed', scale=100, default=1.0, label_fmt='{}%'),
        CheckBinding('osc_glow_enabled', default=False),
        ComboDataBinding('spectrum_bar_profile', default='legacy'),
        ColorBinding('osc_line_color', attr='_osc_line_color', default=[255, 255, 255, 255]),
    ]

    # Load:
    apply_bindings_load(tab, config, BINDINGS)

    # Save:
    result = collect_bindings_save(tab, BINDINGS)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Union

from core.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SliderBinding:
    """Bind a QSlider/QSpinBox to a config key with scaling.

    - On load: config_value * scale → widget.setValue(), optional label update
    - On save: widget.value() / scale → config_value
    """
    key: str
    scale: float = 1.0
    default: float = 0.0
    label_fmt: str = ''
    label_suffix: str = '_label'
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    widget_attr: str = ''  # defaults to key if empty

    def _widget_name(self) -> str:
        return self.widget_attr or self.key

    def load(self, tab: Any, config: dict) -> None:
        wname = self._widget_name()
        if not hasattr(tab, wname):
            return
        widget = getattr(tab, wname)
        raw = config.get(self.key, self.default)
        if isinstance(raw, bool):
            raw = (1.0 if raw else 0.0)
        try:
            val = int(float(raw) * self.scale)
        except (TypeError, ValueError):
            val = int(float(self.default) * self.scale)
        if self.min_val is not None:
            val = max(int(self.min_val * self.scale), val)
        if self.max_val is not None:
            val = min(int(self.max_val * self.scale), val)
        widget.setValue(val)
        if self.label_fmt:
            lbl_name = wname + self.label_suffix
            if hasattr(tab, lbl_name):
                if '{x}' in self.label_fmt:
                    getattr(tab, lbl_name).setText(self.label_fmt.replace('{x}', str(val / self.scale)))
                else:
                    getattr(tab, lbl_name).setText(self.label_fmt.format(val))

    def save(self, tab: Any) -> Optional[tuple]:
        wname = self._widget_name()
        if not hasattr(tab, wname):
            return (self.key, self.default)
        widget = getattr(tab, wname)
        raw = widget.value() / self.scale
        if self.min_val is not None:
            raw = max(self.min_val, raw)
        if self.max_val is not None:
            raw = min(self.max_val, raw)
        return (self.key, raw)


@dataclass
class CheckBinding:
    """Bind a QCheckBox to a config key."""
    key: str
    default: bool = False
    widget_attr: str = ''

    def _widget_name(self) -> str:
        return self.widget_attr or self.key

    def load(self, tab: Any, config: dict) -> None:
        wname = self._widget_name()
        if not hasattr(tab, wname):
            return
        widget = getattr(tab, wname)
        widget.setChecked(bool(config.get(self.key, self.default)))

    def save(self, tab: Any) -> Optional[tuple]:
        wname = self._widget_name()
        if not hasattr(tab, wname):
            return (self.key, self.default)
        return (self.key, getattr(tab, wname).isChecked())


@dataclass
class ComboDataBinding:
    """Bind a QComboBox (using currentData/findData) to a config key."""
    key: str
    default: Any = None
    widget_attr: str = ''
    compat_map: dict = field(default_factory=dict)

    def _widget_name(self) -> str:
        return self.widget_attr or self.key

    def load(self, tab: Any, config: dict) -> None:
        wname = self._widget_name()
        if not hasattr(tab, wname):
            return
        widget = getattr(tab, wname)
        val = config.get(self.key, self.default)
        if val in self.compat_map:
            val = self.compat_map[val]
        idx = widget.findData(str(val))
        if idx >= 0:
            widget.setCurrentIndex(idx)

    def save(self, tab: Any) -> Optional[tuple]:
        wname = self._widget_name()
        if not hasattr(tab, wname):
            return (self.key, self.default)
        return (self.key, getattr(tab, wname).currentData())


@dataclass
class ComboIndexBinding:
    """Bind a QComboBox (using currentIndex) to a config key."""
    key: str
    default: int = 0
    widget_attr: str = ''

    def _widget_name(self) -> str:
        return self.widget_attr or self.key

    def load(self, tab: Any, config: dict) -> None:
        wname = self._widget_name()
        if not hasattr(tab, wname):
            return
        widget = getattr(tab, wname)
        val = int(config.get(self.key, self.default))
        if 0 <= val < widget.count():
            widget.setCurrentIndex(val)

    def save(self, tab: Any) -> Optional[tuple]:
        wname = self._widget_name()
        if not hasattr(tab, wname):
            return (self.key, self.default)
        return (self.key, getattr(tab, wname).currentIndex())


@dataclass
class ColorBinding:
    """Bind a QColor attribute on the tab to a config key (as RGBA list)."""
    key: str
    attr: str  # e.g. '_osc_line_color'
    default: list = field(default_factory=lambda: [255, 255, 255, 255])

    def load(self, tab: Any, config: dict) -> None:
        from PySide6.QtGui import QColor
        val = config.get(self.key, self.default)
        if isinstance(val, list) and len(val) >= 3:
            try:
                setattr(tab, self.attr, QColor(*val))
            except Exception:
                setattr(tab, self.attr, QColor(*self.default))

    def save(self, tab: Any) -> Optional[tuple]:
        color = getattr(tab, self.attr, None)
        if color is None or not hasattr(color, 'red'):
            return (self.key, self.default)
        return (self.key, [color.red(), color.green(), color.blue(), color.alpha()])


@dataclass
class RawBinding:
    """Bind an arbitrary value with custom load/save callables.

    Use for one-off bindings that don't fit the standard patterns.
    """
    key: str
    default: Any = None
    load_fn: Optional[Callable] = None  # (tab, config, key, default) -> None
    save_fn: Optional[Callable] = None  # (tab) -> value

    def load(self, tab: Any, config: dict) -> None:
        if self.load_fn:
            self.load_fn(tab, config, self.key, self.default)

    def save(self, tab: Any) -> Optional[tuple]:
        if self.save_fn:
            return (self.key, self.save_fn(tab))
        return (self.key, self.default)


# Type alias for any binding
Binding = Union[SliderBinding, CheckBinding, ComboDataBinding, ComboIndexBinding, ColorBinding, RawBinding]


def apply_bindings_load(tab: Any, config: dict, bindings: List[Binding]) -> None:
    """Load all bindings from config dict onto tab widgets."""
    for binding in bindings:
        try:
            binding.load(tab, config)
        except Exception as e:
            logger.debug("[SETTINGS_BINDING] Failed to load '%s': %s", 
                        getattr(binding, 'key', '?'), e)


def collect_bindings_save(tab: Any, bindings: List[Binding]) -> dict:
    """Collect all binding values from tab widgets into a config dict."""
    result = {}
    for binding in bindings:
        try:
            pair = binding.save(tab)
            if pair is not None:
                result[pair[0]] = pair[1]
        except Exception as e:
            logger.debug("[SETTINGS_BINDING] Failed to save '%s': %s",
                        getattr(binding, 'key', '?'), e)
    return result
