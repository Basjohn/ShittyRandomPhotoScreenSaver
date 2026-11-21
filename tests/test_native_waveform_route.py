"""Waveform's route pieces (N5.4, unregistered): one program per backdrop holding every stage, each stage gated by its
counts; the route sends the floor's meshes and maps once per floor (again on a lost texture), and each size to its
kind (a storage image's or a target's). Test-owned frames only (``tests.test_waveform_pulse_rim``'s); no preset."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from tests.test_waveform_pulse_rim import _settled, _state


def _snapshot(**overrides):
    values, configuration, _model, snapshot = _settled(floor_give=.6, strands_enabled=True)
    state = replace(_state(values, configuration, snapshot), framed_view=(1.5, 1.0, 1.0))
    if overrides:
        state = replace(state, scene=replace(state.scene, **overrides))
    return SimpleNamespace(logical=SimpleNamespace(mode_state=state, mode_id="waveform_ribbon"), presentation=None)


class _Item:
    """A native item recording what the route hands it."""

    def __init__(self) -> None:
        self.calls: list = []
        self.composite = SimpleNamespace()
        self.lost = None

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))
        return record

    def on_textures_lost(self, callback) -> None:
        self.lost = callback


def test_one_program_holds_every_stage_with_nothing_unread():
    from rendering.native.mode import program_json
    from rendering.gl_programs.waveform_shader_files import PASS_FILES
    from rendering.quick.visualizer.native_route import waveform_program, waveform_variant

    variant = waveform_variant(_snapshot())
    assert len(variant) == 1                       # the backdrop alone: a Setting turning a stage off builds nothing
    program = waveform_program(variant)
    names = {p.name for p in program["passes"]}
    assert {pass_id for _file, _body, pass_id in PASS_FILES} - {"ribbon"} <= names
    assert {"ribbon_body", "ribbon_light", "ribbon_resolve", "waveform_bloom", "waveform_show"} <= names
    assert program["unread"] == []
    declared, _packs = program_json(program["passes"], program["targets"], program["streams"],
                                    images=program["images"])
    assert '"passes"' in declared
    # Negative control: another backdrop is another program (its clear is declared).
    other = waveform_program(((0.5, 0.0, 0.0),))
    assert program_json(other["passes"], other["targets"], other["streams"], images=other["images"])[0] != declared


def test_the_scene_is_composited_in_opengl_rows():
    """ABI 38: Waveform's scene holds OpenGL's rows (drawn unflipped, Python's SceneTarget memory), so its composite
    declares "scene_rows": "up"; the step admits it on overlay_glow alone."""
    import pytest

    from rendering.native.mode import CompositeStep
    from rendering.quick.visualizer.native_route import waveform_program, waveform_variant

    show = next(p for p in waveform_program(waveform_variant(_snapshot()))["passes"] if p.name == "waveform_show")
    assert show.declaration()["scene_rows"] == "up"
    # Negative controls: another form or another value is refused; without it nothing is declared.
    with pytest.raises(ValueError):
        CompositeStep("show", "overlay", "scene.colour", scene_rows="up")
    with pytest.raises(ValueError):
        CompositeStep("show", "overlay_glow", "scene.colour", "bloom.glow", scene_rows="down")
    assert "scene_rows" not in CompositeStep("show", "overlay_glow", "scene.colour", "bloom.glow").declaration()


def test_a_stage_off_draws_nothing_through_its_counts():
    from rendering.quick.visualizer.native_route import waveform_settings_values, waveform_stages

    on = waveform_settings_values(_snapshot(), (320, 200))
    assert waveform_stages(_snapshot(), (320, 200))[0] and on["fog_draws"] == 1.0
    assert all(on[f"medium_groups_{axis}"] > 0 for axis in "xyz") and on["floor_prepass_draws"] == 0.0
    tall = waveform_settings_values(_snapshot(), (420, 1260))
    assert tall["floor_prepass_draws"] == 1.0 and tall["floor_u_spec_mode"] == 2.0
    off = waveform_settings_values(_snapshot(fog=None), (320, 200))
    assert off["fog_draws"] == 0.0
    assert all(off[f"{name}_groups_{axis}"] == 0.0 for name in ("medium", "medium_mirror") for axis in "xyz")
    assert off["integrate_groups_x"] == 0.0 and off["integrate_mirror_groups_y"] == 0.0
    # Every pass's members are filled whichever stages are on (the program declares them all).
    assert set(off) == set(on) == set(tall)


def test_the_route_sends_the_floor_once_and_each_size_to_its_kind(monkeypatch):
    import rendering.quick.visualizer.native_route as route

    sent: list = []

    def resources(snapshot):
        floor = snapshot.logical.mode_state.scene.floor
        return (str(floor.albedo),), lambda item: sent.append(item)

    monkeypatch.setattr(route, "GENERIC_MODE_RESOURCES", {"waveform_ribbon": resources})
    content = route._ModeContent.__new__(route._ModeContent)
    content.item = _Item()
    content._resources, content._sizes, content._images = None, {}, frozenset({"fog_volume"})
    snapshot = _snapshot()
    content._resources_for("waveform_ribbon", snapshot)
    content._resources_for("waveform_ribbon", snapshot)
    assert sent == [content.item]                  # once per floor
    content.item.lost(["albedo"])
    assert sent == [content.item, content.item]    # again on a lost texture
    content._send_sizes({"fog_volume": (4, 3, 96), "reflection": (160, 100)})
    kinds = [(name, args[0]) for name, args, _kw in content.item.calls if name in ("image_size", "target_size")]
    assert kinds == [("image_size", "fog_volume"), ("target_size", "reflection")]
    content._send_sizes({"fog_volume": (4, 3, 96), "reflection": (160, 101)})
    kinds = [(name, args[0]) for name, args, _kw in content.item.calls if name in ("image_size", "target_size")]
    assert kinds[2:] == [("target_size", "reflection")]          # only what changed
    # Negative control: another floor is sent again.
    content._resources_for("waveform_ribbon", _snapshot(floor=replace(snapshot.logical.mode_state.scene.floor,
                                                                        albedo="other.png")))
    assert len(sent) == 3
