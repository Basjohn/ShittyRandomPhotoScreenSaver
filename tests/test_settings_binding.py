"""Tests for declarative settings binding utility.

Tests cover:
- SliderBinding load/save with scaling, labels, clamping
- CheckBinding load/save
- ComboDataBinding load/save with compat_map
- ComboIndexBinding load/save
- ColorBinding load/save
- RawBinding load/save
- apply_bindings_load / collect_bindings_save batch operations
- Error resilience (missing widgets, bad config values)
"""
import pytest
from unittest.mock import MagicMock

from ui.tabs.settings_binding import (
    SliderBinding,
    CheckBinding,
    ComboDataBinding,
    ComboIndexBinding,
    ColorBinding,
    RawBinding,
    apply_bindings_load,
    collect_bindings_save,
)


class _FakeSlider:
    """Minimal QSlider/QSpinBox mock."""
    def __init__(self, value=0):
        self._value = value
    def value(self):
        return self._value
    def setValue(self, v):
        self._value = v


class _FakeCheckBox:
    """Minimal QCheckBox mock."""
    def __init__(self, checked=False):
        self._checked = checked
    def isChecked(self):
        return self._checked
    def setChecked(self, v):
        self._checked = v


class _FakeComboBox:
    """Minimal QComboBox mock."""
    def __init__(self, items=None):
        self._items = items or []  # list of (data, text)
        self._index = 0
    def findData(self, data):
        for i, (d, _) in enumerate(self._items):
            if str(d) == str(data):
                return i
        return -1
    def currentData(self):
        if 0 <= self._index < len(self._items):
            return self._items[self._index][0]
        return None
    def currentIndex(self):
        return self._index
    def setCurrentIndex(self, idx):
        self._index = idx
    def count(self):
        return len(self._items)


class _FakeLabel:
    def __init__(self):
        self._text = ''
    def setText(self, t):
        self._text = t


class TestSliderBinding:
    def test_load_basic(self):
        tab = MagicMock()
        tab.osc_speed = _FakeSlider()
        tab.osc_speed_label = _FakeLabel()
        
        b = SliderBinding('osc_speed', scale=100, default=1.0, label_fmt='{}%')
        b.load(tab, {'osc_speed': 0.75})
        
        assert tab.osc_speed.value() == 75
        assert tab.osc_speed_label._text == '75%'

    def test_load_default(self):
        tab = MagicMock()
        tab.osc_speed = _FakeSlider()
        
        b = SliderBinding('osc_speed', scale=100, default=1.0)
        b.load(tab, {})
        
        assert tab.osc_speed.value() == 100

    def test_load_clamped(self):
        tab = MagicMock()
        tab.osc_speed = _FakeSlider()
        
        b = SliderBinding('osc_speed', scale=100, default=1.0, min_val=0.1, max_val=1.0)
        b.load(tab, {'osc_speed': 5.0})
        
        assert tab.osc_speed.value() == 100  # clamped to max_val * scale

    def test_load_missing_widget(self):
        tab = MagicMock(spec=[])  # no attributes
        b = SliderBinding('osc_speed', scale=100, default=1.0)
        b.load(tab, {'osc_speed': 0.5})  # should not raise

    def test_save_basic(self):
        tab = MagicMock()
        tab.osc_speed = _FakeSlider(75)
        
        b = SliderBinding('osc_speed', scale=100, default=1.0)
        key, val = b.save(tab)
        
        assert key == 'osc_speed'
        assert val == 0.75

    def test_save_missing_widget(self):
        tab = MagicMock(spec=[])
        b = SliderBinding('osc_speed', scale=100, default=1.0)
        key, val = b.save(tab)
        assert val == 1.0

    def test_save_clamped(self):
        tab = MagicMock()
        tab.osc_speed = _FakeSlider(500)
        
        b = SliderBinding('osc_speed', scale=100, default=1.0, min_val=0.1, max_val=1.0)
        key, val = b.save(tab)
        assert val == 1.0

    def test_custom_widget_attr(self):
        tab = MagicMock()
        tab.my_slider = _FakeSlider(50)
        
        b = SliderBinding('config_key', scale=100, default=0.5, widget_attr='my_slider')
        key, val = b.save(tab)
        assert key == 'config_key'
        assert val == 0.5

    def test_label_with_x_format(self):
        tab = MagicMock()
        tab.growth = _FakeSlider()
        tab.growth_label = _FakeLabel()
        
        b = SliderBinding('growth', scale=100, default=1.0, label_fmt='{x}x')
        b.load(tab, {'growth': 2.5})
        assert tab.growth_label._text == '2.5x'

    def test_bool_config_value(self):
        """Bool values in config should be converted to float."""
        tab = MagicMock()
        tab.shift = _FakeSlider()
        
        b = SliderBinding('shift', scale=1, default=0)
        b.load(tab, {'shift': True})
        assert tab.shift.value() == 1


class TestCheckBinding:
    def test_load_true(self):
        tab = MagicMock()
        tab.glow_enabled = _FakeCheckBox()
        
        b = CheckBinding('glow_enabled', default=False)
        b.load(tab, {'glow_enabled': True})
        assert tab.glow_enabled.isChecked() is True

    def test_load_default(self):
        tab = MagicMock()
        tab.glow_enabled = _FakeCheckBox()
        
        b = CheckBinding('glow_enabled', default=False)
        b.load(tab, {})
        assert tab.glow_enabled.isChecked() is False

    def test_save(self):
        tab = MagicMock()
        tab.glow_enabled = _FakeCheckBox(True)
        
        b = CheckBinding('glow_enabled')
        key, val = b.save(tab)
        assert key == 'glow_enabled'
        assert val is True


class TestComboDataBinding:
    def test_load(self):
        tab = MagicMock()
        tab.profile = _FakeComboBox([('legacy', 'Legacy'), ('curved', 'Curved')])
        
        b = ComboDataBinding('profile', default='legacy', widget_attr='profile')
        b.load(tab, {'profile': 'curved'})
        assert tab.profile.currentIndex() == 1

    def test_load_compat_map(self):
        tab = MagicMock()
        tab.profile = _FakeComboBox([('legacy', 'Legacy'), ('curved', 'Curved')])
        
        b = ComboDataBinding('profile', default='legacy', widget_attr='profile',
                            compat_map={True: 'curved', False: 'legacy'})
        b.load(tab, {'profile': True})
        assert tab.profile.currentIndex() == 1

    def test_save(self):
        tab = MagicMock()
        tab.profile = _FakeComboBox([('legacy', 'Legacy'), ('curved', 'Curved')])
        tab.profile.setCurrentIndex(1)
        
        b = ComboDataBinding('profile', widget_attr='profile')
        key, val = b.save(tab)
        assert val == 'curved'


class TestComboIndexBinding:
    def test_load(self):
        tab = MagicMock()
        tab.travel = _FakeComboBox([('none', 'None'), ('left', 'Left'), ('right', 'Right')])
        
        b = ComboIndexBinding('travel', default=0, widget_attr='travel')
        b.load(tab, {'travel': 2})
        assert tab.travel.currentIndex() == 2

    def test_save(self):
        tab = MagicMock()
        tab.travel = _FakeComboBox([('none', 'None'), ('left', 'Left'), ('right', 'Right')])
        tab.travel.setCurrentIndex(1)
        
        b = ComboIndexBinding('travel', widget_attr='travel')
        key, val = b.save(tab)
        assert val == 1


class TestColorBinding:
    def test_load(self):
        tab = MagicMock(spec=[])
        tab._line_color = None
        
        b = ColorBinding('line_color', attr='_line_color', default=[255, 255, 255, 255])
        b.load(tab, {'line_color': [255, 0, 0, 200]})
        
        c = tab._line_color
        assert c.red() == 255
        assert c.green() == 0
        assert c.blue() == 0
        assert c.alpha() == 200

    def test_load_default(self):
        tab = MagicMock(spec=[])
        tab._line_color = None
        
        b = ColorBinding('line_color', attr='_line_color', default=[0, 200, 255, 180])
        b.load(tab, {})
        # No key in config → default applied
        c = tab._line_color
        assert c.red() == 0
        assert c.green() == 200

    def test_save(self):
        from PySide6.QtGui import QColor
        tab = MagicMock(spec=[])
        tab._line_color = QColor(100, 150, 200, 230)
        
        b = ColorBinding('line_color', attr='_line_color')
        key, val = b.save(tab)
        assert val == [100, 150, 200, 230]

    def test_save_missing(self):
        tab = MagicMock(spec=[])
        
        b = ColorBinding('line_color', attr='_line_color', default=[255, 255, 255, 255])
        key, val = b.save(tab)
        assert val == [255, 255, 255, 255]


class TestRawBinding:
    def test_load_save(self):
        loaded = {}
        def my_load(tab, config, key, default):
            loaded['val'] = config.get(key, default)
        def my_save(tab):
            return 42
        
        tab = MagicMock()
        b = RawBinding('custom', load_fn=my_load, save_fn=my_save)
        b.load(tab, {'custom': 'hello'})
        assert loaded['val'] == 'hello'
        
        key, val = b.save(tab)
        assert val == 42


class TestBatchOperations:
    def test_apply_bindings_load(self):
        tab = MagicMock()
        tab.speed = _FakeSlider()
        tab.enabled = _FakeCheckBox()
        
        bindings = [
            SliderBinding('speed', scale=100, default=1.0),
            CheckBinding('enabled', default=False),
        ]
        
        apply_bindings_load(tab, {'speed': 0.5, 'enabled': True}, bindings)
        assert tab.speed.value() == 50
        assert tab.enabled.isChecked() is True

    def test_collect_bindings_save(self):
        tab = MagicMock()
        tab.speed = _FakeSlider(75)
        tab.enabled = _FakeCheckBox(True)
        
        bindings = [
            SliderBinding('speed', scale=100, default=1.0),
            CheckBinding('enabled', default=False),
        ]
        
        result = collect_bindings_save(tab, bindings)
        assert result['speed'] == 0.75
        assert result['enabled'] is True

    def test_error_resilience(self):
        """Bindings should not crash on bad data."""
        tab = MagicMock()
        tab.speed = _FakeSlider()
        
        bindings = [
            SliderBinding('speed', scale=100, default=1.0),
        ]
        
        # Bad config value
        apply_bindings_load(tab, {'speed': 'not_a_number'}, bindings)
        assert tab.speed.value() == 100  # falls back to default


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
