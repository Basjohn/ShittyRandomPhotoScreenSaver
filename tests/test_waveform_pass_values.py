"""Waveform's pass values (``waveform_pass_values``, N5.4: the native record's and settings' source) are the very blocks
the Python renderer packs, byte for byte, pass by pass, at a size without and with the floor's reduced pre-pass.
Test-owned settings and dynamics only (``tests.test_waveform_pulse_rim``'s); no preset value is read."""
from __future__ import annotations

from dataclasses import replace

import pytest

from tests.test_waveform_pulse_rim import Renders, _settled, _state

def expected_packs(passes) -> list[tuple[str, bytes]]:
    """The packs ``passes`` (``waveform_pass_values``'s) stand for, in the Python scene's order: (block, bytes)."""
    from rendering.quick.visualizer.implementations.waveform_ribbon import pass_layout, python_packs

    return [(pass_layout(name).name, block) for name, block in python_packs(passes)]


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


@pytest.mark.parametrize("size", [(320, 200), (420, 1260), (3875, 1450)], ids=["inline", "prepass", "wide"])
def test_the_routes_card_values_are_the_pass_values(size):
    """The route's settings and sizes (``waveform_settings_values``, ``waveform_sizes``: computed from the card alone,
    never per frame) are the card-decided members and sizes ``waveform_pass_values`` draws with."""
    from types import SimpleNamespace

    from core.visualizer_engine.waveform_native_schema import SETTINGS_MEMBERS
    from rendering.gl_programs.waveform_shader_files import member_name
    from rendering.quick.visualizer.implementations.waveform_ribbon import waveform_pass_values
    from rendering.quick.visualizer.native_route import waveform_settings_values, waveform_sizes

    values, configuration, _model, snapshot = _settled(floor_give=.6, strands_enabled=True)
    state = replace(_state(values, configuration, snapshot), framed_view=(1.5, 1.0, 1.0))
    drawn = SimpleNamespace(logical=SimpleNamespace(mode_state=state))
    passes, counts = waveform_pass_values(state, size)
    settings = waveform_settings_values(drawn, size)
    decided = {member_name(pass_id, member): value for pass_id, members in passes.items()
               for member, value in members.items() if member_name(pass_id, member) in SETTINGS_MEMBERS}
    assert decided and {name: settings[name] for name in decided} == {
        name: [float(v) for v in value] if isinstance(value, tuple) else float(value) for name, value in decided.items()}
    # A member the frame's passes leave out belongs to a pass the one program holds while it draws nothing (the
    # sparks before one is born, the pre-pass of a short scene, a stage turned off).
    owners = {member_name(pass_id, member): pass_id for pass_id, members in passes.items() for member in members}
    owners.update({member_name(pass_id, "uViewport"): pass_id for pass_id in
                   ("bursts", "bursts_mirror", "strays", "strays_mirror", "floor_prepass")})
    owners[member_name("floor_prepass", "uSpecMode")] = "floor_prepass"
    extra = {owners[name] for name in set(settings) - set(decided) if name in SETTINGS_MEMBERS}
    assert extra <= {"bursts", "bursts_mirror", "strays", "strays_mirror", "floor_prepass"}
    sizes = waveform_sizes(drawn, size)
    assert sizes["reflection"] == tuple(counts["reflection_size"])
    assert sizes["prepass"] == tuple(counts["prepass_size"] or (1, 1))
    assert sizes["fog_volume"] == tuple(counts["fog_grid"]) and sizes["fog_volume_mirror"] == tuple(counts["fog_grid_mirror"])
    for camera in ("", "_mirror"):
        grid = counts["fog_grid" + camera]
        assert [settings[f"medium{camera}_groups_{axis}"] for axis in "xyz"] == [float(-(-v // 4)) for v in grid]
    # Negative control: another card's values are not this one's.
    assert waveform_settings_values(drawn, (size[0] + 40, size[1])) != settings
