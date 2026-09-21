from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    path = ROOT / "rendering" / "gl_programs" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_srpss_{name}_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exploding_tiles_owns_one_deterministic_solid_mesh() -> None:
    effect = _load("exploding_tiles_program")
    first = effect.exploding_tiles_box_vertices()
    assert first == effect.exploding_tiles_box_vertices()
    assert len(first) == effect.EXPLODING_TILES_VERTEX_COUNT * effect.EXPLODING_TILES_VERTEX_STRIDE_FLOATS
    positions = [first[index:index + 3] for index in range(0, len(first), 8)]
    assert {round(position[2], 5) for position in positions} == {-0.5, -0.38, 0.38, 0.5}


@pytest.mark.parametrize("parameters", (
    {"seed": 0, "columns": 12, "depth": .8},
    {"seed": 7, "columns": 5, "depth": .8},
    {"seed": 7, "columns": 12, "depth": 1.6},
))
def test_exploding_tiles_rejects_outside_resolved_contract(parameters) -> None:
    effect = _load("exploding_tiles_program")
    with pytest.raises(ValueError):
        effect.exploding_tiles_parameters(parameters)


def test_exploding_tiles_grid_is_aspect_aware_and_bounded() -> None:
    effect = _load("exploding_tiles_program")
    assert effect.exploding_tiles_grid(24, 1920, 1080) == (24, 14)
    assert effect.exploding_tiles_grid(48, 400, 4000) == (48, 48)


def test_exploding_tiles_remain_full_size_and_depart_geometrically() -> None:
    effect = _load("exploding_tiles_program")
    assert effect.exploding_tile_state(.04, .10) == 0.0
    assert effect.exploding_tile_state(.98, .10) == 1.0
    # Actual departure/retirement is checked against driver pixels across
    # directions/aspects in test_qtquick_future_transition_gl.


def test_pixel_accretion_adapts_high_resolution_grid_to_hard_instance_cap() -> None:
    effect = _load("pixel_accretion_program")
    cols, rows, actual = effect.pixel_accretion_grid(7680, 4320, 4)
    assert cols * rows <= effect.PIXEL_ACCRETION_MAX_INSTANCES
    assert actual > 4
    assert effect.pixel_accretion_grid(2560, 1440, 8) == (320, 180, 8)


def test_pixel_accretion_tiles_are_absent_before_their_wave_and_settle_exactly() -> None:
    effect = _load("pixel_accretion_program")
    assert effect.pixel_accretion_tile_state(.1, .2) == (0.0, 0.0)
    local, appearance = effect.pixel_accretion_tile_state(.96, .2)
    assert local == 1.0
    assert appearance == 1.0
    # A coherent moving front contains both already-landed and unstarted tiles.
    assert effect.pixel_accretion_tile_state(.40, .025)[0] == 1.0
    assert effect.pixel_accretion_tile_state(.40, .60) == (0.0, 0.0)


@pytest.mark.parametrize("parameters", (
    {"seed": 65536, "tile_size": 8, "travel": .5},
    {"seed": 1, "tile_size": 3, "travel": .5},
    {"seed": 1, "tile_size": 8, "travel": 1.1},
))
def test_pixel_accretion_rejects_outside_resolved_contract(parameters) -> None:
    effect = _load("pixel_accretion_program")
    with pytest.raises(ValueError):
        effect.pixel_accretion_parameters(parameters)


def test_pixel_accretion_shader_translates_microquads_toward_one_event_vector() -> None:
    effect = _load("pixel_accretion_program")
    source = effect.PIXEL_ACCRETION_VERTEX_SOURCE
    assert "gl_InstanceID" in source
    assert "translation = -direction * uTravel * (1. - local)" in source
    assert "if (raw <= 0.)" in source
    assert "gl_Position = vec4(2., 2., 2., 1.)" in source
    assert "landing = 1. + (1. - local)" in source
    assert "abs(direction.x) + abs(direction.y)" in source
    assert "(uProgress - start) / .28" in source
    assert "projected *= cameraW" in source
    assert "vUv = (cell + aUv) / uGrid" in source
    renderer = (ROOT / "rendering/quick/transitions/implementations/pixel_accretion.py").read_text(encoding="utf-8")
    assert "glDrawArraysInstanced" in renderer
    assert "PIXEL_ACCRETION_MAX_INSTANCES" not in renderer
    assert "draw_image(frame, frame.source_texture_id)" in renderer
    assert "draw_image(frame, frame.destination_texture_id)" in renderer
    assert "glBufferData" not in renderer
