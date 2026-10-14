"""Settings-handoff signal ownership and terrain-editor source contracts.

Standalone: no Qt fixture, disk settings, env mutation or display initialization.
"""
from __future__ import annotations

import ast
import gc
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
import weakref

ROOT = Path(__file__).resolve().parents[1]


def _quick_connect_function():
    """Execute the actual unmodified method body with fake Qt signals."""
    tree = ast.parse((ROOT / 'engine/display_manager.py').read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'DisplayManager')
    node = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == '_connect_quick_runtime')
    method = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    scope = {'weakref': weakref, 'QuickDisplayUnit': object}
    exec(compile(method, '<real display manager signal method>', 'exec'), scope)
    return scope['_connect_quick_runtime']


class FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, *args):
        for callback in tuple(self.callbacks):
            callback(*args)


class FakeUnit:
    def __init__(self):
        self.screen_index = 3
        self.is_retired = False
        self.runtime = SimpleNamespace()
        runtime = self.runtime
        tree = ast.parse((ROOT / 'engine/display_manager.py').read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DisplayManager')
        node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_connect_quick_runtime')
        # Only direct .connect signal owners, including nested scene/context models.
        for call in ast.walk(node):
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and call.func.attr == 'connect'):
                continue
            signal = call.func.value
            if not isinstance(signal, ast.Attribute):
                continue
            owner = signal.value
            if isinstance(owner, ast.Name) and owner.id == 'runtime':
                setattr(runtime, signal.attr, FakeSignal())
            elif isinstance(owner, ast.Attribute) and isinstance(owner.value, ast.Name) and owner.value.id == 'runtime':
                obj = getattr(runtime, owner.attr, None)
                if obj is None:
                    obj = SimpleNamespace()
                    setattr(runtime, owner.attr, obj)
                setattr(obj, signal.attr, FakeSignal())
        runtime.input_controller = SimpleNamespace(
            set_view_orbit_enabled=lambda _admitted: None,
            set_scene_transform_enabled=lambda _admitted, **_kwargs: None,
        )
        runtime.scene_readiness = 'ready'

    def reanchor_for_current_bounds(self):
        return None


def test_quick_runtime_callbacks_do_not_retain_retired_display_unit(monkeypatch):
    registry = ModuleType('core.settings.visualizer_mode_registry')
    registry.get_visualizer_mode_descriptor = lambda _mode: SimpleNamespace(scene_transform_settings=())
    monkeypatch.setitem(sys.modules, registry.__name__, registry)
    events = []

    class Manager:
        _quick_visualizer_owner = None

        def __init__(self):
            self._quick_readiness_by_screen = {}
            self._quick_custom_layout_owner = SimpleNamespace(undo_last_change=lambda: None)

        def _quick_view_orbit_admitted(self):
            return False

        def _route_quick_media_transport(self, _display, key):
            events.append(key)

        def __getattr__(self, name):
            if name in ("previous_requested", "next_requested", "cycle_transition_requested", "jedi_mode_requested"):
                return SimpleNamespace(emit=lambda *_args: None)
            return lambda *_args, **_kwargs: None

    manager = Manager()
    unit = FakeUnit()
    runtime = unit.runtime
    _quick_connect_function()(manager, unit, startup_generation=0)
    runtime.play_pause_requested.emit()
    assert events == ['play']
    ref = weakref.ref(unit)
    del unit
    gc.collect()
    assert ref() is None, 'a connected Python signal callback strongly retained the display unit'
    runtime.play_pause_requested.emit()
    assert events == ['play'], 'an orphan runtime signal must be inert'


def test_terrain_editor_reuses_dark_glass_palette_without_changing_water_ownership():
    source = (ROOT / 'ui/tabs/media/terrain_editor.py').read_text(encoding='utf-8')
    shape = (ROOT / 'ui/tabs/media/spectrum_shape_editor.py').read_text(encoding='utf-8')
    for token in ('_BG_COLOR = QColor(18, 18, 18, 240)',
                  '_GRID_COLOR = QColor(255, 255, 255, 18)',
                  '_GRID_MAJOR_COLOR = QColor(255, 255, 255, 35)',
                  '_BORDER_COLOR = QColor(255, 255, 255, 60)'):
        assert token in source and token in shape
    assert 'value = 0.0  # water is authored zero' in source
    assert 'self.terrain_changed.emit(self.get_heightfield())' in source
    assert 'self._cancel_stroke()' in source
