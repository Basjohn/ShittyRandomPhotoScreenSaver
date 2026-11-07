"""One beat-engine authority (AC-05): ``BeatEngineRegistry`` alone holds the process engine, and the logical tick
takes its engine only from its controller (the engine, or the controller's ``engine_factory``), never from a process
service.

* A module global (``_global_beat_engine``) used to keep the engine alive after ``clear()`` and was force-stopped by
  terminal stop even after ``set_engine`` replaced it.
* The tick used to bind the process engine when its controller had none, so a Studio or offline controller built
  without one would silently take the live capture engine.
"""
from __future__ import annotations

import gc
import weakref
from types import SimpleNamespace

import pytest

from widgets.spotify_visualizer import beat_engine as beat_engine_module
from widgets.spotify_visualizer.beat_engine import BeatEngineRegistry, get_shared_spotify_beat_engine


class StubEngine:
    def __init__(self):
        self.stops = 0
        self._audio_worker = SimpleNamespace(has_capture_owner_work=lambda: False)

    def reconfigure_bar_count(self, _count):
        pass

    def force_stop(self):
        self.stops += 1


@pytest.fixture
def registry():
    registry = BeatEngineRegistry.get_instance()
    previous = registry._engine
    yield registry
    registry._engine = previous


def test_a_cleared_registry_leaves_nothing_holding_the_engine(registry):
    engine = StubEngine()
    registry.set_engine(8, engine)
    assert get_shared_spotify_beat_engine(8) is engine
    ref = weakref.ref(engine)
    gc.disable()
    try:
        assert registry.clear() is True
        assert engine.stops == 1
        del engine
        assert ref() is None, "something besides the registry still holds the cleared beat engine"
    finally:
        gc.enable()


def test_terminal_stop_stops_only_the_registry_engine(registry, monkeypatch):
    """``set_engine(x)`` after an earlier shared engine: the terminal beat-engine retirement force-stops ``x`` and
    nothing else (the former global still named the replaced engine)."""
    import threading
    from engine import engine_lifecycle, runtime_destruction
    earlier, current = StubEngine(), StubEngine()
    registry.set_engine(8, earlier)
    get_shared_spotify_beat_engine(8)
    registry.set_engine(8, current)

    class TerminalEngine:
        """Only what terminal finalization reads; every other owner is absent."""
        _instance_running = True
        _usage_telemetry = _display_power = _process_supervisor = thread_manager = _image_cache = None
        _instance_lock = threading.Lock()
        stopped = SimpleNamespace(emit=lambda: None)

    quits = []
    monkeypatch.setattr(runtime_destruction, "request_application_quit", quits.append)
    engine_lifecycle._run_stop_finalization(TerminalEngine(), exit_app=True)
    assert quits == ["engine_stop"]
    assert (earlier.stops, current.stops) == (0, 1)


# ------------------------------------------------------------------------------------------------ the tick
class Reached(Exception):
    """The tick went past engine resolution."""


class TickStubEngine:
    def __init__(self):
        self.smoothing = None

    def set_smoothing(self, value):
        self.smoothing = value

    def __getattr__(self, name):
        raise Reached(name)


@pytest.fixture
def no_registry(monkeypatch):
    def refuse(*_a, **_k):
        raise AssertionError("the logical tick resolved the process beat-engine registry")
    monkeypatch.setattr(BeatEngineRegistry, "get_instance", classmethod(refuse))
    monkeypatch.setattr(beat_engine_module, "get_shared_spotify_beat_engine", refuse)


def _controller(**kwargs):
    """A controller with its logical state installed as the owner installs it (no engine bound yet)."""
    from widgets.spotify_visualizer.logical_tick_state import install_default_logical_tick_state
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    controller = VisualizerRuntimeController(runtime_generation=0, initial_mode="spectrum", **kwargs)
    install_default_logical_tick_state(controller.logical_tick_state, bar_count=controller.bar_count)
    return controller


def test_the_tick_takes_its_engine_from_the_controllers_factory(qt_app, no_registry):
    from widgets.spotify_visualizer.tick_pipeline import consume_engine_bars
    made = []
    stub = TickStubEngine()
    controller = _controller(engine_factory=lambda count: made.append(count) or stub)
    assert controller.engine is None
    with pytest.raises(Reached):
        consume_engine_bars(controller.logical_tick_state, 0.0)
    assert len(made) == 1 and controller.engine is stub and stub.smoothing is not None


def test_a_tick_without_engine_or_factory_raises(qt_app, no_registry):
    from widgets.spotify_visualizer.tick_pipeline import consume_engine_bars
    controller = _controller()
    with pytest.raises(RuntimeError, match="neither a beat engine nor an engine_factory"):
        consume_engine_bars(controller.logical_tick_state, 0.0)
    assert controller.engine is None
