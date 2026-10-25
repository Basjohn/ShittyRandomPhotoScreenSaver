"""SCENE face distribution checks; tests do not constitute native pixel acceptance."""
from __future__ import annotations

from pathlib import Path
import random

from widgets.spotify_visualizer.extruded_bubble_geometry import (
    WORLD_HALF, scene_source_face_weights, upstream_source,
)


SHADER = Path(__file__).resolve().parents[1] / 'rendering/gl_programs/extruded_bubble_program.py'


def test_scene_floor_and_corner_cpu_inlet_samples_cover_two_independent_face_axes():
    rng = random.Random(451)
    up = (0.0, 1.0, 0.0)
    samples = [upstream_source(rng, up, scene_source_face_weights((0, -1, 0), up))
               for _ in range(1024)]
    assert all(y == -WORLD_HALF[1] for _, y, _ in samples)
    assert min(p[0] for p in samples) < -17.0 and max(p[0] for p in samples) > 17.0
    assert min(p[2] for p in samples) < -17.0 and max(p[2] for p in samples) > 17.0
    # Face-wide coverage, not one screen-space column; production GLSL must
    # retain the corresponding *independent* 2-axis mapping below.
    quadrants = {(p[0] > 0, p[2] > 0) for p in samples}
    assert len(quadrants) == 4


def test_scene_gpu_inlet_uses_independent_face_uv_not_correlated_fraction():
    shader = SHADER.read_text(encoding='utf-8')
    inlet = shader.split('vec4 sceneInlet(', 1)[1].split('return vec4(p,', 1)[0]
    assert 'fract(uv.x * 0.75487767 + uv.y * 0.5698403)' not in inlet
    # On Y-face, each of the two free transverse axes comes from a distinct UV.
    assert 'p.x += (uv.x * 2.0 - 1.0) * halfExt.x;' in inlet
    assert 'p.z += (uv.y * 2.0 - 1.0) * halfExt.z;' in inlet
    assert 'p.y -= sign(d.y) * halfExt.y;' in inlet
    assert shader.count('sceneInlet(') == 4  # no new source/simulation shader owner


def test_scene_speck_band_mask_can_no_longer_drop_entire_face_patches():
    shader = SHADER.read_text(encoding='utf-8')
    # SCENE keeps whole-face admission unless Band Gathering asks for the banded patches (dark water between bands).
    assert 'uSceneEmission == 1 ? mix(sceneKeep, uClouds.y + 0.88 * clouds, uBandGather)' in shader
    assert 'uSceneEmission == 1 ?\n        (0.35 + uClouds.z' in shader
    assert 'bool kept = speckRandom(i, 6u)' in shader
    # BEAM keeps the original cloud-shaped admission; only SCENE reinterprets
    # banding as glow variation, keeping the operator's band control useful.
