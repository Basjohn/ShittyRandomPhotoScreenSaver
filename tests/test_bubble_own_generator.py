"""Bubble's spawn on its own generator (native core P2b work order 5 slice 5.6, checkpoint audit 2 A2-M2).

Every spawn, drift and bounce draw comes from the simulation's own ``random.Random``, never the process RNG: unseeded
(production) it seeds from OS entropy, as the process RNG does; gates and replays seed it per simulation, through the
runtime controller (``seed_mode_generators``), so no gate seeds the process RNG and a stray process-RNG draw in the
tick diverges (``test_visualizer_engine_live.py``). Bubble Temporal Fidelity: only the generator's source changed (the
same draws in the same order: the slice's evidence compares the pre-change simulation seeded through the process RNG
frame for frame)."""
from __future__ import annotations

import random

from tests._visualizer_presentation import neutral_bubble_settings
from widgets.spotify_visualizer.bubble_frame_runtime import BubbleFrameRuntime
from widgets.spotify_visualizer.bubble_simulation import BubbleSimulation


def _frames(sim, ticks=180):
    # Random stream and drift directions draw on every spawn and drift pick.
    settings = neutral_bubble_settings(bubble_big_count=6, bubble_small_count=24, bubble_stream_direction="random",
                                       bubble_drift_direction="random")
    frames = []
    for index in range(ticks):
        bass = 0.9 if index % 30 < 3 else 0.35
        sim.tick(1.0 / 90.0, {"bass": bass, "mid": 0.2, "high": 0.1, "overall": 0.3}, settings)
        frames.append(repr(sim.snapshot()))
    return frames


def test_bubble_never_draws_from_the_process_rng():
    saved = random.getstate()
    try:
        random.seed(4242)
        before = random.getstate()
        frames = _frames(BubbleSimulation())
        assert random.getstate() == before                    # spawning, drifting and bouncing drew nothing from it
        assert len(set(frames)) > 150                         # and the field really moved
    finally:
        random.setstate(saved)


def test_its_own_seed_decides_the_frames_and_the_process_rng_does_not():
    saved = random.getstate()
    try:
        random.seed(1)
        seeded = _frames(BubbleSimulation(seed=7))
        random.seed(2)
        assert _frames(BubbleSimulation(seed=7)) == seeded
        assert _frames(BubbleSimulation(seed=8)) != seeded
        reseeded = BubbleSimulation()
        reseeded.seed_generator(7)
        assert _frames(reseeded) == seeded
        # Unseeded, each simulation seeds from OS entropy: the process RNG seeded alike does not make them equal.
        random.seed(5)
        first = _frames(BubbleSimulation(), ticks=60)
        random.seed(5)
        assert _frames(BubbleSimulation(), ticks=60) != first
    finally:
        random.setstate(saved)


def test_the_controller_seeds_bubble_runtimes_built_before_and_after_and_none_by_default():
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController

    expected = random.Random(11).getstate()
    controller = VisualizerRuntimeController(runtime_generation=1, initial_mode="bubble")
    built = controller.resolve_logical_mode_state("bubble", BubbleFrameRuntime)
    simulation = built._ensure_simulation()                  # unseeded: OS entropy, as production
    assert simulation._rng.getstate() != expected
    controller.seed_mode_generators(11)
    assert simulation._rng.getstate() == expected             # an existing simulation: its next draw is the seed's first
    later = VisualizerRuntimeController(runtime_generation=2, initial_mode="bubble")
    later.seed_mode_generators(11)
    pending = later.resolve_logical_mode_state("bubble", BubbleFrameRuntime)
    assert pending._ensure_simulation()._rng.getstate() == expected   # built after the seed, with it
    # A mode state with no generator of its own (a test double's simulation) is left alone.
    doubled = BubbleFrameRuntime(simulation_factory=lambda: object())
    doubled._ensure_simulation()
    doubled.seed_generator(11)


def test_the_product_path_never_seeds():
    # Production passes no seed: the owner, the host binding and the owner's worker link never seed the controller (a
    # seed reaches a worker session only through the testing rig's recorded capture).
    import inspect

    from widgets.spotify_visualizer import engine_worker_link, quick_display_visualizer_owner, visualizer_host_binding

    for module in (quick_display_visualizer_owner, visualizer_host_binding, engine_worker_link):
        assert "seed_mode_generators" not in inspect.getsource(module), module.__name__
