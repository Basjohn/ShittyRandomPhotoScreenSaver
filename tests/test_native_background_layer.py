"""N5.7a, the display's background layer on the native core (D7 point 1): GPU-free.

- The presenter's fit and crop has one owner (``rendering.quick.background_placement``), read by the Python presenter's
  retained ``QSGImageNode`` and by the native layer's pass settings: a change of the owner moves both (the negative
  control: neither path keeps a copy of the rule).
- The layer (``rendering.quick.render.native_background``) over a stand-in core: a still, opaque, background-layer
  composite with the product pack's one pass sampling the photo; each new image sent once, the same image never again;
  the first photo fades in, the item's image going fades it out; a lost texture is sent again from the item's image; the
  close retires and destroys it.
- ``BackgroundRenderItem`` makes the layer only on the native background's backend, and only at its first image; on
  OpenGL nothing native is made (production keeps the Python presenter).

The drawn proof is ``native/core/python/background_layer_check.py`` (the hidden host, both backends, real photos).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from rendering.quick import background_placement as placement_module
from rendering.quick.background_placement import background_placement
from rendering.quick.image_state import PresentationImage


def _image(identity: str, size: tuple[int, int] = (8, 4), value: int = 40) -> PresentationImage:
    width, height = size
    return PresentationImage(identity=identity, source_path="", logical_size=(float(width), float(height)),
                             device_pixel_ratio=1.0, pixel_size=size, row_stride=width * 4,
                             rgba8=bytes((value, value, value, 255)) * (width * height))


# --------------------------------------------------------------------------------------------- the one owner


def test_the_placement_is_the_whole_photo_over_the_whole_item():
    placement = background_placement((2560, 1440), (1706.6666667, 960.0))
    assert placement.source_rect == (0.0, 0.0, 2560.0, 1440.0)
    assert placement.target_rect == (0.0, 0.0, 1706.6666667, 960.0)
    assert placement.source_uv == (0.0, 0.0, 1.0, 1.0)
    with pytest.raises(ValueError):
        background_placement((0, 10), (10.0, 10.0))


def test_the_python_presenter_and_the_native_layer_read_the_one_owner(qt_app, monkeypatch):
    from PySide6.QtQuick import QSGNode

    from rendering.quick.render import background_image_node
    from rendering.quick.render.background_image_node import RetainedBackgroundSceneNode
    from rendering.quick.render.native_background import background_layer_settings
    from rendering.quick.render.telemetry import RenderNodeTelemetry

    rects: dict = {}

    class _FakeImageNode(QSGNode):
        def setOwnsTexture(self, _owns) -> None:  # noqa: N802
            pass

        def setFiltering(self, _filtering) -> None:  # noqa: N802
            pass

        def setTexture(self, _texture) -> None:  # noqa: N802
            pass

        def setSourceRect(self, rect) -> None:  # noqa: N802
            rects["source"] = (rect.x(), rect.y(), rect.width(), rect.height())

        def setRect(self, rect) -> None:  # noqa: N802
            rects["target"] = (rect.x(), rect.y(), rect.width(), rect.height())

    class _Window:
        def createImageNode(self):  # noqa: N802
            return _FakeImageNode()

        def createTextureFromImage(self, _image, _options):  # noqa: N802
            return object()

    monkeypatch.setattr(background_image_node, "validate_or_quit_current_opengl_context", lambda **_kwargs: None)
    node = RetainedBackgroundSceneNode(window=_Window(), telemetry=RenderNodeTelemetry(gui_thread_id=1),
                                       screen_index=0, frame_trace=None)
    node._synchronize_native_image(_image("a"), logical_size=(8.0, 4.0))
    assert rects == {"source": (0.0, 0.0, 8.0, 4.0), "target": (0.0, 0.0, 8.0, 4.0)}
    assert background_layer_settings((8, 4), (8.0, 4.0)) == {"u_source_uv": [0.0, 0.0, 1.0, 1.0]}

    # Negative control: another rule in the owner moves both paths (neither keeps a copy of it).
    def cropped(pixel_size, logical_size):
        return placement_module.BackgroundPlacement(pixel_size=tuple(pixel_size), source_rect=(2.0, 1.0, 4.0, 2.0),
                                                    target_rect=(0.0, 0.0, float(logical_size[0]),
                                                                 float(logical_size[1])))

    monkeypatch.setattr(background_image_node, "background_placement", cropped)
    monkeypatch.setattr(placement_module, "background_placement", cropped)
    node._synchronize_native_image(_image("b"), logical_size=(8.0, 4.0))
    assert rects["source"] == (2.0, 1.0, 4.0, 2.0)
    assert background_layer_settings((8, 4), (8.0, 4.0)) == {"u_source_uv": [0.25, 0.25, 0.5, 0.5]}


# --------------------------------------------------------------------------------------------- the layer


class _Composite:
    def __init__(self, calls: list) -> None:
        self.calls = calls
        self.destroyed = False

    def set(self, **config) -> None:
        self.calls.append(("set", config))

    def window_pixels(self):
        return (16, 8)

    def content_status(self):
        return SimpleNamespace(draws=1, failures=0, refused_run=0, failing=False)

    def state(self) -> dict:
        return {}

    def destroy(self) -> bool:
        self.destroyed = True
        self.calls.append(("destroy",))
        return True


class _Mode:
    def __init__(self, calls: list) -> None:
        self.calls = calls
        self.composite = _Composite(calls)
        self.lost = None
        self.meshes_lost = None

    def still(self, still=True) -> None:
        self.calls.append(("still", still))

    def program(self, passes, settings=None, **declared) -> None:
        self.calls.append(("program", passes, settings) + ((declared,) if declared else ()))

    def mesh(self, name, vertices, layout, **instances) -> None:
        self.calls.append(("mesh", name, len(vertices), layout, instances))

    def remove_mesh(self, name) -> None:
        self.calls.append(("remove_mesh", name))

    def on_textures_lost(self, callback) -> None:
        self.lost = callback

    def on_meshes_lost(self, callback) -> None:
        self.meshes_lost = callback

    def texture(self, name, pixels, size, **_kwargs) -> None:
        self.calls.append(("texture", name, tuple(size), len(pixels)))

    def remove_texture(self, name) -> None:
        self.calls.append(("remove_texture", name))

    def card(self, card) -> None:
        self.calls.append(("card", card))

    def settings(self, values) -> None:
        self.calls.append(("settings", values))

    def update(self) -> None:
        self.calls.append(("update",))

    def retire(self) -> None:
        self.calls.append(("retire",))

    def state(self) -> dict:
        return {}


class _Window:
    def size(self):
        return SimpleNamespace(width=lambda: 8, height=lambda: 4)


class _Item:
    def __init__(self) -> None:
        self.w, self.h = 8.0, 4.0

    def width(self) -> float:
        return self.w

    def height(self) -> float:
        return self.h

    def window(self):
        return None                      # no window edges in a GPU-free test


@pytest.fixture
def layer(monkeypatch):
    from rendering.quick.render import native_background

    calls: list = []
    mode = _Mode(calls)
    core = SimpleNamespace(mode=lambda _item: mode)
    monkeypatch.setattr(native_background, "_fade_ms", lambda: 250)
    made = native_background.NativeBackgroundLayer(core, _Item())
    return made, mode, calls


def test_the_layer_is_an_opaque_still_background_with_the_product_pass(layer):
    from rendering.quick.render.native_background import PASS_NAME, SAMPLER, TEXTURE, background_layer_pack_path

    made, mode, calls = layer
    made.present(_image("a"))
    composite_config = next(c[1] for c in calls if c[0] == "set")
    assert composite_config["layer"] == "background" and composite_config["opaque"] is True
    assert composite_config["coverage"] is None and composite_config["visible"] is False
    assert ("still", True) in calls
    passes = next(c[1] for c in calls if c[0] == "program")
    assert [p.name for p in passes] == [PASS_NAME] and passes[0].blend == "replace"
    assert passes[0].pack == background_layer_pack_path().read_bytes()
    assert [(s.name, s.texture, s.filter, s.wrap, s.mips) for s in passes[0].samplers] == [
        (SAMPLER, TEXTURE, "linear", "clamp", "none")]
    # The first photo: its texture once, its placement's settings, and the layer fades in.
    assert [c for c in calls if c[0] == "texture"] == [("texture", TEXTURE, (8, 4), 8 * 4 * 4)]
    assert ("settings", {"u_source_uv": [0.0, 0.0, 1.0, 1.0]}) in calls
    shown = [c[1] for c in calls if c[0] == "set" and c[1].get("visible") is True]
    assert len(shown) == 1 and shown[0]["fade_ms"] == 250 and shown[0]["rect"] == [0.0, 0.0, 8.0, 4.0]


def test_an_image_is_sent_once_and_its_going_fades_the_layer_out(layer):
    made, _mode, calls = layer
    first = _image("a")
    made.present(first)
    made.present(first)                                       # the same image: nothing sent again
    assert len([c for c in calls if c[0] == "texture"]) == 1
    made.present(_image("b", value=90))
    assert len([c for c in calls if c[0] == "texture"]) == 2
    made.present(None)
    assert calls[-1] == ("set", {"visible": False, "fade_ms": 250})   # fade, never vanish
    # A size change places it again, with no image sent.
    sent = len([c for c in calls if c[0] == "texture"])
    made.present(_image("c"))
    made._item.w = 10.0
    made.geometry_changed()
    assert len([c for c in calls if c[0] == "texture"]) == sent + 1
    assert any(c[0] == "set" and c[1].get("rect") == [0.0, 0.0, 10.0, 4.0] for c in calls)


def test_a_lost_photo_is_sent_again_from_the_items_image_and_the_close_retires(layer):
    from rendering.quick.render.native_background import TEXTURE

    made, mode, calls = layer
    made.present(_image("a"))
    mode.lost(["other"])                                      # not the layer's texture: nothing
    assert len([c for c in calls if c[0] == "texture"]) == 1
    mode.lost([TEXTURE])
    assert len([c for c in calls if c[0] == "texture"]) == 2 and made.resent == 1
    made.close()
    assert calls[-2:] == [("retire",), ("destroy",)]
    made.present(_image("b"))                                 # closed: nothing more
    assert len([c for c in calls if c[0] == "texture"]) == 2


# --------------------------------------------------------------------------------------------- the transitions (N5.2a)


class _Signal:
    def __init__(self) -> None:
        self.slots: list = []

    def connect(self, slot) -> None:
        self.slots.append(slot)

    def disconnect(self, slot) -> None:
        self.slots.remove(slot)


class _ClockWindow:
    def __init__(self) -> None:
        self.afterAnimating = _Signal()

    def effectiveDevicePixelRatio(self) -> float:  # noqa: N802
        return 1.0

    def size(self):
        return SimpleNamespace(width=lambda: 8, height=lambda: 4)


def _run(transition_id: str, source, destination, run_id: int = 1):
    from tools.transition_contact_sheet import production_transition_spec
    from rendering.quick.transitions.state import TransitionRun

    spec = production_transition_spec(transition_id, 1000)
    request = spec.build_request(runtime_generation=0, source_image=source, destination_image=destination)
    return TransitionRun.start(run_id=run_id, request=request, start_ns=1_000)


@pytest.fixture
def clocked_layer(monkeypatch):
    from rendering.quick.render import native_background

    calls: list = []
    mode = _Mode(calls)
    core = SimpleNamespace(mode=lambda _item: mode)
    monkeypatch.setattr(native_background, "_fade_ms", lambda: 250)
    window = _ClockWindow()
    item = _Item()
    item.window = lambda: window
    monkeypatch.setattr(native_background.NativeBackgroundLayer, "_arm", lambda self, signal: None)
    now = {"ns": 0}
    made = native_background.NativeBackgroundLayer(core, item, clock_ns=lambda: now["ns"])
    return made, mode, calls, window, now


def test_a_run_is_drawn_by_the_core_from_its_own_pack_and_the_python_renderers_values(clocked_layer):
    from rendering.native.mode import MODE_CORE_MEMBERS
    from rendering.quick.render import native_background as nb

    made, _mode, calls, window, now = clocked_layer
    source, destination = _image("a", value=40), _image("b", value=200)
    made.present(source)
    run = _run("burn", source, destination)
    now["ns"] = run.start_ns + (run.end_ns - run.start_ns) // 2
    del calls[:]
    made.transition(run)
    # The destination into the other slot, once; the source (already drawn) not again.
    assert [c for c in calls if c[0] == "texture"] == [("texture", nb.NEXT_TEXTURE, (8, 4), 8 * 4 * 4)]
    (program,) = [c for c in calls if c[0] == "program"]
    (one_pass,) = program[1]
    assert one_pass.name == "burn" and one_pass.blend == "replace"
    assert one_pass.pack == nb.transition_pack_path("burn").read_bytes()
    assert [(s.name, s.texture) for s in one_pass.samplers] == [(nb.OLD_SAMPLER, nb.TEXTURE),
                                                                (nb.NEW_SAMPLER, nb.NEXT_TEXTURE)]
    # Its settings: the Python renderer's own block values at the clock's progress, less the core's members.
    renderer = nb.native_transition_renderer("burn")
    expected = renderer.run_values(run, run.sample(now["ns"]), (8.0, 4.0), 1.0)
    settings = program[2]
    assert settings == {k: v for k, v in expected.items() if k not in MODE_CORE_MEMBERS}
    assert settings["u_progress"] == pytest.approx(0.5) and "u_target_px" not in settings
    # The clock: one connection while the run lasts; each tick gives the frame's progress.
    assert window.afterAnimating.slots == [made.tick]
    now["ns"] = run.start_ns + (run.end_ns - run.start_ns) * 3 // 4
    window.afterAnimating.slots[0]()
    assert calls[-2][0] == "settings" and calls[-2][1]["u_progress"] == pytest.approx(0.75) and made.ticks == 1
    # The end: the slots swap (no upload), the background's pass samples the destination, the source goes, the clock
    # is disconnected; the destination handed over afterwards uploads nothing.
    del calls[:]
    made.transition(None)
    made.present(destination)
    assert [c for c in calls if c[0] == "texture"] == []
    (program,) = [c for c in calls if c[0] == "program"]
    assert program[1][0].name == nb.PASS_NAME and program[1][0].samplers[0].texture == nb.NEXT_TEXTURE
    assert ("remove_texture", nb.TEXTURE) in calls and window.afterAnimating.slots == []
    # Negative control: a tick after the end gives nothing.
    made.tick()
    assert made.ticks == 1


def test_a_run_writes_its_window_to_the_frame_trace_only_when_a_trace_is_admitted(clocked_layer):
    """The live check's transition session cuts a native run's window from these records (the Python background node's
    never carry it): a tick at the run's start and at each frame, and one end record, each with the run's id."""
    from core.performance.frame_trace import FrameTraceEvent
    from rendering.quick.render import native_background as nb

    assert (nb._TRACE_TICK, nb._TRACE_END) == (FrameTraceEvent.NATIVE_TRANSITION_TICK,
                                              FrameTraceEvent.NATIVE_TRANSITION_END)
    made, _mode, _calls, window, now = clocked_layer
    records: list = []
    made._trace = SimpleNamespace(record=lambda event, **kw: records.append((int(event), kw["auxiliary"])))
    source, destination = _image("a"), _image("b")
    made.present(source)
    run = _run("burn", source, destination, run_id=7)
    now["ns"] = run.start_ns
    made.transition(run)
    window.afterAnimating.slots[0]()
    window.afterAnimating.slots[0]()
    made.transition(None)
    assert records == [(nb._TRACE_TICK, 7)] * 3 + [(nb._TRACE_END, 7)]
    # Control: without an admitted trace (the product's default) nothing is recorded and the run is drawn the same.
    made._trace = None
    made.present(destination)
    second = _run("burn", destination, source, run_id=8)
    made.transition(second)
    window.afterAnimating.slots[0]()
    made.transition(None)
    assert len(records) == 4 and made.runs == 2


def test_a_transition_without_a_pass_on_the_core_is_drawn_as_crossfade(clocked_layer, monkeypatch):
    from rendering.quick.render import native_background as nb

    made, _mode, calls, _window, _now = clocked_layer
    source = _image("a")
    made.present(source)
    monkeypatch.setattr(nb, "transition_pack_path",
                        lambda tid, real=nb.transition_pack_path: real(tid) if tid == "crossfade" else real("none"))
    made.transition(_run("burn", source, _image("b")))
    (program,) = [c for c in calls if c[0] == "program" and c[1][0].name != nb.PASS_NAME]
    assert program[1][0].name == nb.FALLBACK_TRANSITION


def test_a_scene_run_shows_its_photographs_by_the_background_program_and_its_effect_as_its_scene(clocked_layer):
    """N5.2c: a 3D transition (Cube Turn) sends its meshes once, keeps the old picture's program while the Python
    renderer draws the old picture, draws its scene (the environment, its passes into the scene target, the opaque
    composite) with the renderer's own values from the first moving frame, only its settings after that, the new
    picture's program where the renderer draws the new picture, and at its end removes its meshes."""
    from rendering.native.mode import MODE_CORE_MEMBERS, CompositeStep, EnvironmentStep, ModePass
    from rendering.quick.render import native_background as nb

    made, _mode, calls, window, now = clocked_layer
    source, destination = _image("a", value=40), _image("b", value=200)
    made.present(source)
    run = _run("cube_turn", source, destination)
    now["ns"] = run.start_ns
    del calls[:]
    made.transition(run)
    assert [c[1] for c in calls if c[0] == "mesh"] == ["box"]
    assert not [c for c in calls if c[0] == "program"]          # progress 0: the old picture's program stays
    now["ns"] = run.start_ns + (run.end_ns - run.start_ns) // 2
    window.afterAnimating.slots[0]()
    (program,) = [c for c in calls if c[0] == "program"]
    passes, settings, declared = program[1], program[2], program[3]
    assert isinstance(passes[0], EnvironmentStep) and passes[0].source == nb.NEXT_TEXTURE
    assert [p.name for p in passes if isinstance(p, ModePass)] == ["backdrop", "box"]
    assert isinstance(passes[-1], CompositeStep) and passes[-1].form == "opaque"
    assert [t.name for t in declared["targets"]] == [nb.SCENE_TARGET]
    renderer = nb.native_transition_renderer("cube_turn")
    expected = renderer.scene_values(run, run.sample(now["ns"]), (8.0, 4.0))
    assert settings == {k: v for k, v in expected.items() if k not in MODE_CORE_MEMBERS}
    # The next frame gives its settings only (no new program).
    now["ns"] = run.start_ns + (run.end_ns - run.start_ns) * 3 // 5
    window.afterAnimating.slots[0]()
    assert calls[-2][0] == "settings" and len([c for c in calls if c[0] == "program"]) == 1
    # The run's last instant: the new picture by the background's program on the other slot.
    now["ns"] = run.end_ns
    window.afterAnimating.slots[0]()
    last = [c for c in calls if c[0] == "program"][-1]
    assert last[1][0].name == nb.PASS_NAME and last[1][0].samplers[0].texture == nb.NEXT_TEXTURE
    del calls[:]
    made.transition(None)
    assert ("remove_mesh", "box") in calls and ("remove_texture", nb.TEXTURE) in calls
    assert calls.index(("remove_mesh", "box")) > max(i for i, c in enumerate(calls) if c[0] == "program")


def test_a_content_made_again_mid_run_gets_the_scenes_meshes_and_photographs_again(clocked_layer):
    """N5.2c (playbook checklist 13): a content made again mid-run reports the scene's meshes and its photographs lost;
    the layer sends each again from what it holds and the run goes on (its clock connected, its program kept), so the
    scene never waits for the run's end. A name the run does not hold is ignored; after the run nothing is sent."""
    from rendering.quick.render import native_background as nb

    made, mode, calls, window, now = clocked_layer
    source, destination = _image("a", value=40), _image("b", value=200)
    made.present(source)
    run = _run("depth_cascade", source, destination)
    now["ns"] = run.start_ns + (run.end_ns - run.start_ns) // 2
    made.transition(run)
    window.afterAnimating.slots[0]()
    (sent,) = [c for c in calls if c[0] == "mesh"]
    del calls[:]
    mode.meshes_lost(["cards", "other"])                     # the content made again
    mode.lost([nb.TEXTURE, nb.NEXT_TEXTURE])
    again = [c for c in calls if c[0] == "mesh"]
    assert again == [sent] and calls[-1] == ("update",)
    assert sorted(c[1] for c in calls if c[0] == "texture") == sorted([nb.TEXTURE, nb.NEXT_TEXTURE])
    assert made.state()["run"] == run.run_id and window.afterAnimating.slots == [made.tick]
    assert not [c for c in calls if c[0] == "program"]       # the scene's program goes on
    made.transition(None)
    del calls[:]
    mode.meshes_lost(["cards"])                              # after the run: nothing to send
    assert not [c for c in calls if c[0] == "mesh"]


def test_the_ported_transitions_are_exactly_those_the_core_draws():
    """D10: a transition is offered on Vulkan (its ``renderer_backends``) only where the core draws it: a one-fragment
    pass whose pack is shipped and current (``tests/test_quick_shader_packs.py``)."""
    from rendering.quick.render.native_background import native_transition_renderer, transition_pack_path
    from rendering.transition_registry import iter_transition_descriptors
    from tools import regen_qrc

    on_vulkan = {d.stable_id for d in iter_transition_descriptors() if "vulkan" in d.renderer_backends}
    drawn = {d.stable_id for d in iter_transition_descriptors() if native_transition_renderer(d.stable_id) is not None}
    # N5.2c: the scene transitions (``NativeScenePasses``) are drawn and offered too, their packs one per pass. N5.2d:
    # a scene transition is drawn before it is offered on Vulkan (its registration follows its proof, the lead's).
    scenes = {cls.transition_id for cls in regen_qrc._native_scene_classes()}
    assert on_vulkan and on_vulkan <= drawn and drawn - on_vulkan <= scenes and scenes <= drawn
    assert set(regen_qrc.transition_fragment_sources()) == drawn - scenes
    assert all(transition_pack_path(tid) == regen_qrc.transition_pack_path(tid) for tid in drawn - scenes)
    # Negative control: a transition with no shipped pack is not drawn.
    assert native_transition_renderer("no_such_transition") is None


def test_an_item_quad_transition_gives_the_core_its_own_values_arrays_flat_and_its_plain_picture_frames():
    """N5.2b: Surface Tension (an item-quad program, one fragment between two pictures) is drawn by the core from the
    Python renderer's own block values: its pool arrays flat (the core packs them at the reflected stride), and the
    frames the Python renderer draws as a plain picture (``uShow``) are the fragment's to draw the same way."""
    from rendering.gl_programs.surface_tension_program import SURFACE_TENSION_BLOCK, TENSION_MAX_POOLS
    from rendering.native.mode import MODE_CORE_MEMBERS
    from rendering.quick.render import native_background as nb
    from rendering.quick.transitions.fullscreen_pass import SHOW_EFFECT, SHOW_NEW, SHOW_OLD

    renderer = nb.native_transition_renderer("surface_tension")
    assert renderer is not None
    run = _run("surface_tension", _image("a"), _image("b"))
    members = {name for name, _kind in SURFACE_TENSION_BLOCK.fields}

    def settings_at(fraction: float) -> dict:
        sample = run.sample(run.start_ns + round(fraction * (run.end_ns - run.start_ns)))
        return nb.transition_settings(renderer, run, sample, (8.0, 4.0), 1.0)

    middle = settings_at(0.5)
    # Every member the block holds is filled by the core or by these settings, and nothing else is given.
    assert set(middle) | (members & set(MODE_CORE_MEMBERS)) == members
    assert not set(middle) & set(MODE_CORE_MEMBERS)
    assert len(middle["uPools"]) == 4 * TENSION_MAX_POOLS and len(middle["uDrift"]) == 2 * TENSION_MAX_POOLS
    assert all(isinstance(v, (int, float)) for v in middle["uPools"] + middle["uDrift"])
    assert [settings_at(f)["uShow"] for f in (0.0, 0.5, 1.0)] == [SHOW_OLD, SHOW_EFFECT, SHOW_NEW]


def _beam_run(source, destination, sparks: bool):
    from rendering.quick.transitions.state import TransitionRequest, TransitionRun

    r = _run("beam", source, destination).request
    request = TransitionRequest(r.runtime_generation, r.transition_id, r.requested_name, r.selected_from_random,
                                r.duration_ms, r.direction, {**r.parameter_dict(), "sparks": sparks},
                                r.source_image, r.destination_image)
    return TransitionRun.start(run_id=1, request=request, start_ns=1_000)


@pytest.mark.parametrize("sparks", [True, False])
def test_beams_sparks_follow_its_fragment_as_instanced_quads_while_sparks_is_on(clocked_layer, sparks):
    """N5.2b's leftover: Beam is drawn by the core as its fragment between the two pictures and, while Sparks is on, its
    sparks after it: the built-in item quad drawn once a spark from the sparks' own vertex stage, light added (the
    Python renderer's ONE, ONE), both packs baked from the Python renderer's texts. Every member of the drawn passes'
    blocks is the core's or one of the settings, which are the Python renderer's own block values; with Sparks off the
    program and the settings hold nothing of the sparks."""
    from rendering.gl_programs.beam_program import BEAM_BLOCK, BEAM_SPARK_BLOCK
    from rendering.native.mode import BUILTIN_QUAD_MESH, MODE_CORE_MEMBERS
    from rendering.quick.render import native_background as nb

    made, _mode, calls, _window, now = clocked_layer
    source = _image("a")
    made.present(source)
    run = _beam_run(source, _image("b"), sparks)
    now["ns"] = run.start_ns + (run.end_ns - run.start_ns) // 2
    del calls[:]
    made.transition(run)
    (program,) = [c for c in calls if c[0] == "program"]
    passes, settings = program[1], program[2]
    renderer = nb.native_transition_renderer("beam")
    assert renderer is not None and passes[0].name == "beam" and passes[0].blend == "replace"
    assert passes[0].pack == nb.transition_pack_path("beam").read_bytes() and passes[0].geometry is None
    drawn = renderer.native_instanced_passes(run.request.parameter_dict())
    assert [p.name for p in passes[1:]] == [p.name for p in drawn] and len(drawn) == int(sparks)
    for declared, extra in zip(passes[1:], drawn):
        vertex, fragment = nb.instanced_pack_paths(extra.name)
        geometry = declared.geometry
        assert declared.pack == fragment.read_bytes() and geometry.vertex_pack == vertex.read_bytes()
        assert declared.blend == extra.blend == "additive" and not declared.samplers
        assert (geometry.topology, geometry.mesh, geometry.vertices, geometry.instances) == (
            "triangle_strip", BUILTIN_QUAD_MESH, "mesh", extra.instances)
    expected = renderer.run_values(run, run.sample(now["ns"]), (8.0, 4.0), 1.0)
    assert settings == {k: v for k, v in expected.items() if k not in MODE_CORE_MEMBERS}
    members = {name for block in ((BEAM_BLOCK, BEAM_SPARK_BLOCK) if sparks else (BEAM_BLOCK,))
               for name, _kind in block.fields}
    assert set(settings) | (members & set(MODE_CORE_MEMBERS)) == members


def test_the_item_hands_its_runs_to_the_layer(qt_app, monkeypatch):
    from rendering.quick.render import background_item, native_background

    runs: list = []

    class _Layer:
        def present(self, image) -> None:
            pass

        def transition(self, run) -> None:
            runs.append(run)

        def geometry_changed(self) -> None:
            pass

        def close(self) -> None:
            pass

    monkeypatch.setattr(native_background, "attach_native_background", lambda _item, backend=None: _Layer())
    monkeypatch.setattr(background_item, "background_family_available_on_backend", lambda: False)
    monkeypatch.setattr(background_item, "_native_background_wanted", lambda: True)
    item = background_item.BackgroundRenderItem()
    source, destination = _image("a"), _image("b")
    run = _run("crossfade", source, destination)
    item.set_transition_run(run)                      # before any image: no layer, nothing handed
    assert runs == []
    item.set_presentation_image(source)
    item.set_transition_run(None)
    item.set_transition_run(run)
    item.set_transition_run(None)
    assert runs == [None, run, None]
    item.close_native_layer()


# --------------------------------------------------------------------------------------------- the item's route


def test_the_item_makes_the_layer_only_on_the_native_backend_at_its_first_image(qt_app, monkeypatch):
    from rendering.quick.render import background_item, native_background

    made: list = []

    class _Layer:
        def __init__(self) -> None:
            self.images: list = []
            self.closed = False

        def present(self, image) -> None:
            self.images.append(image)

        def geometry_changed(self) -> None:
            pass

        def close(self) -> None:
            self.closed = True

    def attach(_item, backend=None):
        made.append(_Layer())
        return made[-1]

    monkeypatch.setattr(native_background, "attach_native_background", attach)

    # OpenGL (production): the Python presenter only.
    monkeypatch.setattr(background_item, "_native_background_wanted", lambda: False)
    item = background_item.BackgroundRenderItem()
    item.set_presentation_image(_image("a"))
    assert made == [] and item.native_layer is None

    # The native background's backend (no Python renderer there): the layer at the first image, and every change.
    monkeypatch.setattr(background_item, "background_family_available_on_backend", lambda: False)
    monkeypatch.setattr(background_item, "_native_background_wanted", lambda: True)
    item = background_item.BackgroundRenderItem()
    assert made == []                                         # nothing before an image
    first, second = _image("a"), _image("b")
    item.set_presentation_image(first)
    item.set_presentation_image(second)
    item.set_presentation_image(None)
    assert len(made) == 1 and made[0].images == [first, second, None]
    item.close_native_layer()
    assert made[0].closed and item.native_layer is None
