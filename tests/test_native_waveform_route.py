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


def test_a_frame_is_published_only_for_its_drawn_cards_view(monkeypatch):
    """Item 2's design (D5.5): the route publishes a Waveform frame only when its framed view is the drawn card's;
    before the scene's first view and across a resize edge the frame is held."""
    from rendering.quick.visualizer import framed_view
    from rendering.quick.visualizer import native_route as route

    snapshot = _snapshot()                                         # its framed view (1.5, 1.0, 1.0)
    monkeypatch.setattr(framed_view, "resolve_framed_view", lambda _presentation: (1.5, 1.0, 1.0))
    assert route.waveform_frame_ready(snapshot)
    assert route.GENERIC_MODE_FRAME_GATES["waveform_ribbon"] is route.waveform_frame_ready
    # Negative controls: another card's view, no view yet, and a card covering no pixel all hold the frame.
    monkeypatch.setattr(framed_view, "resolve_framed_view", lambda _presentation: (1.6, 1.0, 1.0))
    assert not route.waveform_frame_ready(snapshot)
    monkeypatch.setattr(framed_view, "resolve_framed_view", lambda _presentation: None)
    assert not route.waveform_frame_ready(snapshot)
    monkeypatch.setattr(framed_view, "resolve_framed_view", lambda _presentation: (1.5, 1.0, 1.0))
    state = replace(snapshot.logical.mode_state, framed_view=())
    assert not route.waveform_frame_ready(SimpleNamespace(logical=SimpleNamespace(mode_state=state),
                                                          presentation=None))


def test_a_frame_whose_ribbon_is_not_ready_is_held(monkeypatch):
    """The Python renderer draws nothing while the ribbon's history primes (``state.ready`` false), so the route holds
    those frames: a new model's route shows nothing until its first ready frame (layer L's first run)."""
    from rendering.quick.visualizer import framed_view
    from rendering.quick.visualizer import native_route as route

    snapshot = _snapshot()
    monkeypatch.setattr(framed_view, "resolve_framed_view", lambda _presentation: (1.5, 1.0, 1.0))
    assert snapshot.logical.mode_state.ready and route.waveform_frame_ready(snapshot)
    priming = replace(snapshot.logical.mode_state, ready=False)
    held = SimpleNamespace(logical=SimpleNamespace(mode_state=priming), presentation=snapshot.presentation)
    assert not route.waveform_frame_ready(held)
    # Negative control: the same frame ready again is published.
    ready = SimpleNamespace(logical=SimpleNamespace(mode_state=replace(priming, ready=True)),
                            presentation=snapshot.presentation)
    assert route.waveform_frame_ready(ready)


def test_rule_a_single_samples_the_routes_scene_as_pythons():
    """Rule (a) judges a multisampled scene by its single-sampled form (D8 point 1): inside the owner's
    ``single_sample_scene_targets`` the route's Waveform program declares one sample, as the Python scene target then
    takes; outside it, and after it, the product's four (P's first run compared a 4x route scene with Python's one)."""
    from rendering.quick.scene3d import waveform
    from rendering.quick.visualizer import native_route as route
    from tools.visualizer_replay import owner_render_parity as parity

    def scene_samples():
        program = route.waveform_program(((0.0, 0.0, 0.0),))
        scene = next(t for t in program["targets"] if t.name == route.WAVEFORM_SCENE)
        return scene.samples

    product = waveform.SCENE_SAMPLES
    assert product > 1 and scene_samples() == product
    with parity.single_sample_scene_targets():
        assert scene_samples() == 1
    # Negative control: after the block the product's count is back, so the product never draws single-sampled.
    assert waveform.SCENE_SAMPLES == product and scene_samples() == product


def test_a_variant_program_mode_loads_without_a_fragment_pack(monkeypatch):
    """Waveform builds every pass from its variant's packs: loading it reads no single fragment pack (it has none)."""
    import pytest

    from rendering.quick.visualizer import native_route as route

    content = route._ModeContent.__new__(route._ModeContent)
    content._pack = None
    content.load("waveform_ribbon")
    assert content._pack == ("waveform_ribbon", b"")
    # Negative control: without its program variants, the mode is a single-fragment mode, and it has no such pack.
    content._pack = None
    variants = dict(route.GENERIC_MODE_PROGRAM_VARIANTS)
    del variants["waveform_ribbon"]
    monkeypatch.setattr(route, "GENERIC_MODE_PROGRAM_VARIANTS", variants)
    with pytest.raises(KeyError):
        content.load("waveform_ribbon")


def test_the_scene_is_composited_in_opengl_rows():
    """ABI 40: Waveform's scene holds OpenGL's rows (drawn unflipped, Python's SceneTarget memory), so its composite
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
