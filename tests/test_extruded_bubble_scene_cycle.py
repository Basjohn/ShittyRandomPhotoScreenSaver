"""N5.6 (the flickering starfish): a SCENE population never cycles over a track shorter than SCENE_CYCLE_FLOOR.

An inlet near the exit corner has a track of hundredths of a unit; a free chain's 160 beads cycled over it faster than a
frame and landed somewhere new on every frame along their own plume rays at the emission face (Preset 9's flickering
starfish while orbiting). The GPU (``sceneCycle`` in ``_SCENE_INLET_GLSL``) and its CPU twin (``scene_cycles``, the
drift paths' geometry) cycle over the track or the floor, whichever is longer; the exit fade still ends at the track.
"""
from __future__ import annotations

import numpy as np

from widgets.spotify_visualizer import extruded_bubble_material_paths as mp

BEADS_PER_CHAIN = 160
FRAME = 1.0 / 60.0
FAST_STREAM = 1.0          # world units a second, past any authored stream speed's top


def _tracks(direction):
    from widgets.spotify_visualizer.extruded_bubble_geometry import scene_source_face_weights

    ids = np.arange(mp.CHAIN_PATHS, dtype=np.uint32)
    weights = scene_source_face_weights((-1.0, 0.0, 0.0), direction)
    _start, spans = mp.scene_entries(mp.seeded_random(ids, 31),
                                     np.stack((mp.seeded_random(ids, 32), mp.seeded_random(ids, 33)), -1),
                                     direction, weights)
    return ids, np.asarray(spans)


def wraps_within_a_bead_step(cycles, ids) -> int:
    """Chains whose bead passes its neighbour's slot within one frame at a fast stream (aliased: a new place a frame)."""
    rate = mp.BEAD_CARRY * (0.7 + 0.6 * mp.seeded_random(ids, 5))
    return int((FAST_STREAM * FRAME * rate / cycles > 1.0 / BEADS_PER_CHAIN).sum())


def test_no_scene_chain_cycles_faster_than_its_beads_can_be_seen():
    rng = np.random.default_rng(250)
    shortest = []
    for _ in range(24):                               # stream directions with a falling or rising component
        d = rng.normal(size=3)
        d[0] = abs(d[0]) + 0.3
        d = tuple(d / np.linalg.norm(d))
        ids, spans = _tracks(d)
        shortest.append(float(spans.min()))
        assert wraps_within_a_bead_step(mp.scene_cycles(spans), ids) == 0
        assert (mp.scene_cycles(spans) >= mp.SCENE_CYCLE_FLOOR).all()
        assert (mp.scene_cycles(spans)[spans > mp.SCENE_CYCLE_FLOOR] == spans[spans > mp.SCENE_CYCLE_FLOOR]).all()
    # Negative control: the raw tracks (the pre-fix cycle) alias somewhere, a track of hundredths of a unit among them.
    aliased = sum(wraps_within_a_bead_step(_tracks(tuple(v))[1], _tracks(tuple(v))[0]) for v in
                  [np.array((1.0, -0.3, -0.15)) / np.linalg.norm((1.0, -0.3, -0.15))])
    assert min(shortest) < 0.5 and aliased >= 1


def test_the_gpu_and_the_cpu_cycle_alike():
    from rendering.gl_programs import extruded_bubble_program as program

    text = program._SCENE_INLET_GLSL
    assert f"const float SCENE_CYCLE_FLOOR = {mp.SCENE_CYCLE_FLOOR:.1f};" in text
    assert "float sceneCycle(float span) { return max(span, SCENE_CYCLE_FLOOR); }" in text
    beads, specks = program._BEAD_GLSL, program._SPECK_GLSL
    assert "float cycle = uSceneEmission == 1 ? sceneCycle(span) : span;" in beads            # chains
    assert "float s = progress * cycle;" in beads
    assert "float cycle = sceneCycle(sceneEntry.w);" in beads                                  # snow
    assert "progress * cycle, sceneEntry.w, 0.005)" in beads           # the exit fade still ends at the track
    assert "float cycle = uSceneEmission == 1 ? sceneCycle(sceneEntry.w) : lengthPath;" in specks
    assert "progress * cycle, sceneEntry.w," in specks
    import inspect

    assert "spans=scene_cycles(spans)" in inspect.getsource(mp.chain_geometry)
    assert "spans=scene_cycles(spans)" in inspect.getsource(mp.cloud_geometry)
