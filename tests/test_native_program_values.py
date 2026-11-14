"""N2.5 round 4, the standing port rule (``rendering/native/program_values.py``, ``native/core/src/program_blocks.h``):
a native mode's Settings- and card-derived uniforms are resolved in Python and handed to the core by name.

These hold the Python half without the module: Spectrum's settings function gives exactly the values the Python
renderer writes for the same frame (so the native item draws the renderer's own settings arithmetic), it and the
core's per-frame members cover SpectrumDraw between them with no overlap, the settings travel as plain name -> number
JSON, and every mode shader's pack is baked from its composed source (the conventions splice: the raw source does not
bake, which is the composition's negative control).
"""
from __future__ import annotations

import dataclasses
import json
import shutil
import subprocess
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from tests.test_qtquick_visualizer_spectrum import (  # noqa: F401  (the fixture is used by name)
    _logical,
    _real_spectrum_gl,
    _spectrum_capture_parameters,
)


def _snapshot():
    import tests.test_qtquick_visualizer_spectrum as base
    from core.settings.models import SpotifyVisualizerSettings
    from tests._visualizer_frozen_settings import frozen_visualizer_settings
    from widgets.spotify_visualizer.config_applier import _populate_shared_visualizer_extras

    freeze_render_fields = base.freeze_render_fields
    compose_visualizer_render_snapshot = base.compose_visualizer_render_snapshot
    VisualizerRuntimeController = base.VisualizerRuntimeController
    apply_presentation_vis_mode_kwargs = base.apply_presentation_vis_mode_kwargs
    resolve_visualizer_presentation = base.resolve_visualizer_presentation
    get_visualizer_presentation_policy = base.get_visualizer_presentation_policy

    controller = VisualizerRuntimeController(runtime_generation=2, initial_mode="spectrum")
    apply_presentation_vis_mode_kwargs(controller.presentation_state, asdict(SpotifyVisualizerSettings.from_mapping(
        frozen_visualizer_settings("spectrum"), apply_preset_overlay=False)))
    parameters: dict[str, object] = {}
    _populate_shared_visualizer_extras(parameters, SimpleNamespace(
        presentation_config_host=controller.presentation_state,
        _spectrum_ghosting_enabled=True, _spectrum_ghost_decay=0.18,
        _osc_ghosting_enabled=False, _osc_ghost_intensity=0.4, _osc_ghost_decay=0.4,
    ))
    parameters.update(_spectrum_capture_parameters(controller.presentation_state))
    count = 12
    presentation = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("spectrum"),
        display_size=(1380.0, 280.0), viewport_extent=(1380.0, 280.0), border_width=0.0, corner_radius=0.0)
    logical = _logical(playing=True, source_generation=5, source_activation_id=7,
                       bars=tuple(0.1 + 0.07 * index for index in range(count)), peaks=(0.95,) * count)
    logical = dataclasses.replace(
        logical,
        common=dataclasses.replace(logical.common, style=freeze_render_fields({
            "fill_color": (10, 220, 80, 255), "border_color": (245, 245, 255, 255),
            "single_piece": True, "border_radius": 0.0,
        })),
        mode_state=dataclasses.replace(logical.mode_state, parameters=freeze_render_fields(parameters)),
    )
    return compose_visualizer_render_snapshot(logical, presentation, logical_revision=1)


@pytest.mark.qt
def test_the_settings_function_gives_the_python_renderers_own_values(_real_spectrum_gl, monkeypatch):
    from rendering.quick.visualizer.implementations import spectrum

    seen: list = []
    original = spectrum.QuickSpectrumRenderer.render

    def recording(self, frame):
        original(self, frame)
        seen.append((dict(self._values), frame))

    monkeypatch.setattr(spectrum.QuickSpectrumRenderer, "render", recording)
    snapshot = _snapshot()
    _real_spectrum_gl(snapshot)
    values, frame = seen[-1]
    settings = spectrum.spectrum_settings_values(
        snapshot.logical, snapshot.presentation, item_size=frame.logical_size,
        oriented_size=frame.oriented_logical_size, content_rotation_quarters=frame.content_rotation_quarters,
        content_rect=frame.logical_content_rect,
        item_from_window=(*values["u_item_from_frag_x"], *values["u_item_from_frag_y"]),
        window_from_target=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0), target_px=values["u_target_px"])
    members = {name for name, _kind in spectrum.SPECTRUM_BLOCK.fields}
    # The two sides cover the block, never the same member twice.
    assert not set(settings) & set(spectrum.SPECTRUM_FRAME_MEMBERS)
    assert set(settings) | set(spectrum.SPECTRUM_FRAME_MEMBERS) == members, sorted(
        members ^ (set(settings) | set(spectrum.SPECTRUM_FRAME_MEMBERS)))
    # Every setting is the renderer's own value (uMatrix: the Python quad's, not the core's; u_time is a frame member).
    differ = {name: (settings[name], values.get(name)) for name in settings
              if name != "uMatrix" and tuple(json.loads(json.dumps(settings[name])) if isinstance(settings[name], tuple)
                                             else (settings[name],))
              != tuple(values.get(name) if isinstance(values.get(name), tuple) else (values.get(name),))}
    assert not differ, differ
    # Negative control: another frame's settings (the ghost off) are not this frame's.
    off = dict(snapshot.logical.mode_state.parameters, spectrum_ghosting_enabled=False)
    import tests.test_qtquick_visualizer_spectrum as base

    freeze_render_fields = base.freeze_render_fields
    other = dataclasses.replace(snapshot.logical, mode_state=dataclasses.replace(
        snapshot.logical.mode_state, parameters=freeze_render_fields(off)))
    changed = spectrum.spectrum_settings_values(
        other, snapshot.presentation, item_size=frame.logical_size, oriented_size=frame.oriented_logical_size,
        content_rotation_quarters=frame.content_rotation_quarters, content_rect=frame.logical_content_rect,
        item_from_window=(*values["u_item_from_frag_x"], *values["u_item_from_frag_y"]),
        window_from_target=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0), target_px=values["u_target_px"])
    assert changed["u_ghost_alpha"] == 0.0 != settings["u_ghost_alpha"]


def test_settings_travel_as_plain_name_to_number_json():
    from rendering.native.program_values import settings_json

    assert json.loads(settings_json({"b": (1.0, 2), "a": True, "c": 0.5})) == {"a": 1, "b": [1.0, 2], "c": 0.5}
    with pytest.raises(TypeError):
        settings_json({"a": "red"})
    with pytest.raises(ValueError):
        settings_json({"a": float("nan")})


def _qsb():
    from tools import regen_qrc
    import sys

    return regen_qrc.quick_shader_baker(sys.executable)


def test_a_mode_shader_bakes_from_its_composed_source_not_its_raw_text(tmp_path):
    # spectrum.frag splices the conventions include at its marker: the pack is baked from the composed text (as the
    # native core's own bake does), and the raw text does not bake (fragPixel undefined): the composition's control.
    from tools import regen_qrc

    qsb = _qsb()
    source = regen_qrc.mode_shader_dir() / "spectrum.frag"
    copy = tmp_path / "spectrum.frag"
    shutil.copyfile(source, copy)
    pack = tmp_path / "spectrum.frag.qsb"
    regen_qrc._bake_quick_shader(qsb, copy, pack, regen_qrc.quick_shader_targets(), subprocess.run)
    assert pack.is_file() and pack.read_bytes() == source.with_name("spectrum.frag.qsb").read_bytes()
    raw = subprocess.run([str(qsb), *regen_qrc.quick_shader_targets(), str(copy), "-o", str(tmp_path / "raw.qsb")],
                         capture_output=True, text=True, timeout=120)
    assert raw.returncode != 0 and "fragPixel" in (raw.stdout + raw.stderr)


def test_the_mode_pack_is_found_beside_its_source():
    from rendering.native.program_values import mode_fragment_pack, mode_fragment_pack_path

    assert mode_fragment_pack_path("spectrum").name == "spectrum.frag.qsb"
    assert mode_fragment_pack("spectrum")[:4]                 # a serialized QShader
    with pytest.raises(KeyError):
        mode_fragment_pack_path("no_such_mode")
