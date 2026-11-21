"""Waveform's pass values (``waveform_pass_values``, N5.4: the native record's and settings' source) are the very blocks
the Python renderer packs, byte for byte, pass by pass, at a size without and with the floor's reduced pre-pass.
Test-owned settings and dynamics only (``tests.test_waveform_pulse_rim``'s); no preset value is read."""
from __future__ import annotations

from dataclasses import replace

import pytest

from tests.test_waveform_pulse_rim import Renders, _settled, _state

#: The Python scene's pack order of a frame (``WaveformScene._render_packet``): the yielding floor, the field, each
#: camera's medium and volume, the reflection's sky, light, strays and sparks, then the scene's sky, floor (pre-pass
#: first), ribbon body and light, strays and sparks.
ORDER = ("give_section", "give_blur", "field", "medium", "integrate", "medium_mirror", "integrate_mirror", "sky_mirror",
         "ribbon_mirror", "strays_mirror", "bursts_mirror", "sky", "floor_prepass", "floor", "ribbon_body", "ribbon",
         "strays", "bursts")


def _layouts():
    from rendering.gl_programs.fog_volume import FOG_VOLUME_BLOCK
    from rendering.gl_programs.ribbon import RIBBON_BLOCK, RIBBON_COHORT_STRAY_BLOCK
    from rendering.gl_programs.ribbon_bursts import BURSTS_BLOCK
    from rendering.gl_programs.waveform_atmosphere import FIELD_BLOCK, MEDIUM_BLOCK, SKY_BLOCK
    from rendering.gl_programs.waveform_floor_give import FLOOR_GIVE_BLUR_BLOCK, FLOOR_GIVE_SECTION_BLOCK
    from rendering.gl_programs.waveform_ribbon import FLOOR_BLOCK

    return {"give_section": FLOOR_GIVE_SECTION_BLOCK, "give_blur": FLOOR_GIVE_BLUR_BLOCK, "field": FIELD_BLOCK,
            "medium": MEDIUM_BLOCK, "integrate": FOG_VOLUME_BLOCK, "sky": SKY_BLOCK, "ribbon": RIBBON_BLOCK,
            "strays": RIBBON_COHORT_STRAY_BLOCK, "bursts": BURSTS_BLOCK, "floor": FLOOR_BLOCK}


def expected_packs(passes) -> list[tuple[str, bytes]]:
    """The packs ``passes`` (``waveform_pass_values``'s) stand for, in the Python scene's order: (block, bytes)."""
    from rendering.gl_programs.portable import pack_block

    layouts, packs = _layouts(), []
    for name in ORDER:
        key = "ribbon" if name == "ribbon_body" else name
        if key not in passes:
            continue
        values = passes[key]
        if name == "ribbon_body":   # the body pass leaves the light's Pulse Rim members unset (it reads none)
            values = {**values, "uPulseRim": (0., 0., 0., 0.), "uPulseRimShape": (0., 0.)}
        layout = layouts[key.replace("_mirror", "").replace("_prepass", "")]
        packs.append((layout.name, pack_block(layout, values)))
    return packs


def _python_packs(renders, state):
    """The Python renderer's own packs of one frame of ``state`` (its scene target's steps aside)."""
    from rendering.gl_programs import scene3d

    recorded = []
    original = scene3d.Scene3DBlockLayout.pack

    def recording(self, values):
        packed = original(self, values)
        recorded.append((self.name, bytes(packed)))
        return packed
    renders.rgb(state, state.scene.pulse_rim)          # the renderer prepared and warm first
    scene3d.Scene3DBlockLayout.pack = recording
    try:
        renders.rgb(state, state.scene.pulse_rim)
    finally:
        scene3d.Scene3DBlockLayout.pack = original
    return [pack for pack in recorded if not pack[0].startswith("Scene")]


@pytest.mark.qt
@pytest.mark.parametrize("size", [(320, 200), (420, 1260)], ids=["inline", "prepass"])
def test_the_pass_values_are_the_python_renderers_packs(qt_app, size):
    from rendering.quick.visualizer.framed_view import framed_view_of_frame
    from rendering.quick.visualizer.implementations.waveform_ribbon import waveform_pass_values

    values, configuration, _model, snapshot = _settled(floor_give=.6, strands_enabled=True)
    state = _state(values, configuration, snapshot)
    renders = Renders(*size)
    try:
        renders.rgb(state, 0.)
        state = replace(state, framed_view=tuple(framed_view_of_frame(renders.frame)))
        python = _python_packs(renders, state)
    finally:
        renders.close()
    passes, counts = waveform_pass_values(state, size)
    assert ("floor_prepass" in passes) == (size[1] > 1080)
    assert "give_section" in passes and "field" in passes and "medium_mirror" in passes
    assert expected_packs(passes) == python
    # Negative control: the values of another size (another camera aspect and viewport) are not the frame's.
    other, _ = waveform_pass_values(replace(state, framed_view=(state.framed_view[0] * 1.1, *state.framed_view[1:])),
                                    (size[0] + 40, size[1]))
    assert expected_packs(other) != python
