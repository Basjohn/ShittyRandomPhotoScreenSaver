"""The Visualizer's native route (Current_Plan.md item 8b, N2.5 box 7; D10 point 4): on the Vulkan backend the
Visualizer item draws nothing itself; a native mode's frames are drawn by the native core's item in its content host.

Route (N2.5 box 1): ``VisualizerRenderItem`` keeps everything the scene and its owner read from it (the bound
identity, the committed presentation record, the prewarm and drop edges); with a route attached it never creates a
render node, and each of its GUI-thread update requests becomes the route's ``sync``: the same take the Python item
makes at its sync (``admit_at_sync``, ``take_for_render`` under the committed record), published as the mode's
fixed-layout record (``spectrum_native_schema``) into a frame stream the route owns, which the native item's packet
reader reads at its own sync on the render thread (N2.3: one consuming reader at the accept edge, D2). The owner's
engine worker path reaches the same bridge, so both paths draw through one stream (the worker's own native stream,
read with no Python copy, is a later step: the owner's presentation and reveal decisions would then read the slot
head instead of the bridge).

Two kinds of native item (N5.1): Spectrum's hand-written one (N2.5) and one generic item (D12) on which every generic
mode (Spline Curve first) is drawn from its own fragment pack, its settings function (``GENERIC_MODE_SETTINGS``) and
its runtime schema's record; the route makes both at attach and retargets the generic item's program between modes.

The route's stream is created at bind (the identity's mapping), retired at unbind (the reader stores Retiring at once
and is released on the render thread at the item's next sync, D1; the name is unlinked at once, the reader's own
view stays mapped until then) and the composite goes with the route's close (before the content host retires).
GUI thread only; nothing runs at rest (a frame is published only when the bridge hands a new one).

Fade, never vanish (audit N29 M1, round 2 M2 to M5): the native item fades out on any failure (the route's own, or
the core's: a content build that failed or a run of refused frames, read from the item's status) and fades back in
when it draws again; an activation whose first frame comes late (after a failure or a wait for the window) fades in.
An activation's end is the owner's to fade (its scene and content fades): the unbind hides the item at that edge, as
the Python item stops drawing there (rule (a)). The route waits on the window's own edges, never a
timer: ``afterSynchronizing`` once the native item has read the window's framebuffer (before the first frame, after a
resize), ``afterRendering`` once the core has recorded what the route just changed (so a failed build is seen with no
new frame). Each is armed for one firing and re-runs the item's update.
"""
from __future__ import annotations

import uuid
import weakref
from pathlib import Path
from typing import Any, Callable

from core.logging.logger import get_logger
from widgets.spotify_visualizer.quick_display_visualizer_owner import ACTIVATION_SCENE_FADE_DURATION_S

logger = get_logger(__name__)

def _devcurve_settings(snapshot: Any, card: dict) -> dict:
    """Spline Curve's Settings- and card-derived members of the drawn frame (N5.1): the Python renderer's own
    ``devcurve_settings_values`` under the card's content rect (its ``frame.logical_content_rect``)."""
    from rendering.quick.visualizer.implementations.devcurve import (
        devcurve_presentation_layout,
        devcurve_settings_values,
    )

    layout = devcurve_presentation_layout(snapshot.presentation, card["content_rect"])
    return devcurve_settings_values(snapshot.logical, layout)


def _bubble_settings(snapshot: Any, card: dict) -> dict:
    """Bubble's Settings- and card-derived members of every pass (N5.1): the Python renderer's own
    ``bubble_settings_values`` (BubbleDraw) and ``bubble_ambient_settings_values`` (the ambient points' block) under the
    card's content rect, the drawn dpr and the frame's capacity zoom."""
    from rendering.quick.visualizer.implementations.bubble import (
        bubble_ambient_settings_values,
        bubble_presentation_layout,
        bubble_settings_values,
    )

    presentation = snapshot.presentation
    layout = bubble_presentation_layout(presentation, card["content_rect"], snapshot.logical.mode_state.world_scale)
    values = bubble_settings_values(snapshot.logical, layout, presentation.dpr)
    values.update(bubble_ambient_settings_values(snapshot.logical, layout, presentation.dpr))
    return values


def _oscilloscope_settings(snapshot: Any, card: dict) -> dict:
    """The Oscilloscope's Settings- and card-derived members of both its passes (N5.1): the Python renderer's own
    ``oscilloscope_settings_values`` under the card's content rect and oriented size, the drawn dpr and visual scale."""
    from rendering.quick.visualizer.implementations.oscilloscope import oscilloscope_settings_values

    presentation = snapshot.presentation
    return oscilloscope_settings_values(snapshot.logical, card["content_rect"], card["oriented_size"],
                                        presentation.dpr, presentation.uniform_visual_scale)


#: The Oscilloscope's settings function by name (its harness and tests call it directly).
OSCILLOSCOPE_SETTINGS = _oscilloscope_settings


def _shader_pack(filename: str) -> bytes:
    """A pack of the Visualizer modes' shader folder (``tools/regen_qrc.py --shaders`` bakes it beside its source)."""
    from widgets.spotify_visualizer import shaders

    path = Path(shaders.__file__).resolve().parent / f"{filename}.qsb"
    if not path.is_file():
        raise FileNotFoundError(f"{path.name} is missing: run tools/regen_qrc.py --shaders")
    return path.read_bytes()


#: Bubble's ambient target (D14 point 6): coverage premultiplied over, light added, at the size of its content.
BUBBLE_AMBIENT_TARGET = "ambient"
#: The size the ambient target holds while the ambience's Settings are off: the smallest (one 64-pixel bucket); its two
#: passes then draw no instance (one program, never an ambience-off variant: lead, 15 Nov; D12 "As built: Bubble").
_AMBIENT_IDLE_SIZE = (1, 1)


def _bubble_target_sizes(snapshot: Any, settings: dict) -> dict:
    """The ambient target's size: its content's (``u_ambient_px``) while the drawn frame carries ambient points (the
    simulation publishes them only while the ambience's Settings are on; its enable switches are read from the runtime's
    own settings, whose keys the frame's parameters do not share)."""
    if not snapshot.logical.mode_state.ambient_points:
        return {BUBBLE_AMBIENT_TARGET: _AMBIENT_IDLE_SIZE}
    width, height = settings["u_ambient_px"]
    return {BUBBLE_AMBIENT_TARGET: (int(width), int(height))}


def bubble_program(pack: bytes, sizes: dict) -> dict:
    """Bubble's program (N5.1): the ambient points and the hero-circle mask as instanced quads into the ambient target
    (two attachments), then the card's pass sampling both (``bubble.frag``, straight alpha over as the Python render
    host blends). ``pack``: ``bubble.frag``'s; ``sizes``: ``_bubble_target_sizes``."""
    from rendering.native.mode import (
        BlendState,
        MeshAttribute,
        ModePass,
        ModeStream,
        ModeTarget,
        PassGeometry,
        PassOutput,
        PassSampler,
        RecordLayout,
        TargetAttachment,
    )

    ambient = ModeTarget(BUBBLE_AMBIENT_TARGET, (TargetAttachment("coverage", "rgba8"),
                                                 TargetAttachment("light", "rgba16f")),
                         size=tuple(sizes[BUBBLE_AMBIENT_TARGET]))
    points = RecordLayout(24, (MeshAttribute("aPoint", 4, 0), MeshAttribute("aOther", 2, 16)))
    occluders = RecordLayout(16, (MeshAttribute("aOccluder", 4, 0),))
    erase = BlendState(("add", "zero", "one_minus_src_alpha"), ("add", "zero", "one_minus_src_alpha"))
    passes = [
        ModePass("bubble_ambient_points", _shader_pack("bubble_ambient_points.frag"), "premultiplied",
                 target=BUBBLE_AMBIENT_TARGET,
                 outputs=(PassOutput(True, "premultiplied"), PassOutput(True, "additive")),
                 geometry=PassGeometry(_shader_pack("bubble_ambient_points.vert"), topology="triangle_strip",
                                       vertices=4, instance_from="ambient_points")),
        ModePass("bubble_ambient_mask", _shader_pack("bubble_ambient_mask.frag"), erase,
                 target=BUBBLE_AMBIENT_TARGET, outputs=(PassOutput(True, erase), PassOutput(True, erase)),
                 geometry=PassGeometry(_shader_pack("bubble_ambient_mask.vert"), topology="triangle_strip",
                                       vertices=4, instance_from="ambient_occluders")),
        ModePass("bubble", pack, "alpha", samplers=(
            PassSampler("u_ambient_texture", f"{BUBBLE_AMBIENT_TARGET}.coverage", "linear"),
            PassSampler("u_ambient_light", f"{BUBBLE_AMBIENT_TARGET}.light", "linear"))),
    ]
    streams = [ModeStream("ambient_points", "ambient_points", "instance", points, used="ambient_point_floats"),
               ModeStream("ambient_occluders", "ambient_occluders", "instance", occluders,
                          used="ambient_occluder_floats")]
    return {"passes": passes, "targets": [ambient], "streams": streams}


#: The Oscilloscope's overlay target (D14, D17): the beam's colour (RGBA8, its alpha coverage) and, under Glow, its light
#: (RGBA16F) that the bloom spreads; single-sampled, the surface's size.
OSCILLOSCOPE_TARGET = "scope"


def oscilloscope_glow(snapshot: Any) -> bool:
    """Whether the Oscilloscope's program carries the glow (its Glow Setting above 0): the program the route draws,
    chosen at the Settings edge (D17 choice E), never per frame."""
    from rendering.quick.visualizer.implementation_values import parameter

    return float(parameter(snapshot.logical.mode_state.parameters, "osc_glow")) > 0.0


def oscilloscope_program(glow: bool) -> dict:
    """The Oscilloscope's program (N5.1): the graticule (one quad, its vertex count the record's: 0 when its style draws
    none) and the beam (one instanced quad a segment, its endpoints read from the record's points as a storage stream)
    into the overlay target, both blended MAX on every attachment as the Python renderer blends them; with ``glow`` the
    target's emission spread by the bloom and the overlay composite with the glow (``u_bloom_strength`` the record's,
    ``u_hdr_exposure`` 0), else the target's colour alone and the plain overlay composite (no emission, no bloom: D17
    point 1), whose program leaves the record's bloom strength unread."""
    from rendering.native.mode import (
        BlendState,
        BloomStep,
        CompositeStep,
        ModePass,
        ModeStream,
        ModeTarget,
        PassGeometry,
        PassOutput,
        TargetAttachment,
    )

    maximum = BlendState(("max", "one", "one"), ("max", "one", "one"))
    attachments = (TargetAttachment("colour", "rgba8"),) + ((TargetAttachment("emission", "rgba16f"),) if glow else ())
    outputs = tuple(PassOutput(True, maximum) for _ in attachments)
    plain = "" if glow else "_plain"
    passes: list = [
        ModePass("oscilloscope_graticule", _shader_pack(f"oscilloscope_graticule{plain}.frag"), maximum,
                 target=OSCILLOSCOPE_TARGET, outputs=outputs,
                 geometry=PassGeometry(_shader_pack("oscilloscope_graticule.vert"), topology="triangle_strip",
                                       vertices="osc_graticule_vertices")),
        ModePass("oscilloscope_beam", _shader_pack(f"oscilloscope_beam{plain}.frag"), maximum,
                 target=OSCILLOSCOPE_TARGET, outputs=outputs,
                 geometry=PassGeometry(_shader_pack("oscilloscope_beam.vert"), topology="triangle_strip", vertices=4,
                                       instances="osc_segments", storage=(("OscPoints", "osc_points"),))),
    ]
    if glow:
        passes += [BloomStep("oscilloscope_bloom", f"{OSCILLOSCOPE_TARGET}.emission"),
                   CompositeStep("oscilloscope_show", "overlay_glow", f"{OSCILLOSCOPE_TARGET}.colour",
                                 "oscilloscope_bloom.glow")]
    else:
        passes.append(CompositeStep("oscilloscope_show", "overlay", f"{OSCILLOSCOPE_TARGET}.colour"))
    streams = [ModeStream("osc_points", "osc_points", "storage", used="osc_point_floats")]
    program = {"passes": passes, "targets": [ModeTarget(OSCILLOSCOPE_TARGET, attachments)], "streams": streams}
    if not glow:
        program["unread"] = ["u_bloom_strength"]
    return program


#: The generic modes the core draws from data alone (D12, ``rendering.native.mode``): mode id -> its settings function
#: ``(snapshot, card) -> members by name``. Its program is its own fragment pack (one pass, straight alpha over, as the
#: Python render host blends), its record its runtime schema (``native_schema.schema_for_mode``).
GENERIC_MODE_SETTINGS: dict[str, Callable[[Any, dict], dict]] = {
    "devcurve": _devcurve_settings,
    "bubble": _bubble_settings,
}
#: Bubble's settings function by name (its diagnostics and tests call it directly).
BUBBLE_SETTINGS = _bubble_settings
#: A generic mode with more than its one fragment pass (N5.1, Bubble): mode id -> ``(fragment pack, target sizes) ->
#: {"passes", "targets", "streams"}``, and its explicit-size targets' sizes ``(snapshot, settings) -> {target: size}``,
#: sent when they change (``NativeMode.target_size``) and again after a new program.
GENERIC_MODE_PROGRAMS: dict[str, Callable[[bytes, dict], dict]] = {
    "bubble": bubble_program,
}
GENERIC_MODE_TARGET_SIZES: dict[str, Callable[[Any, dict], dict]] = {
    "bubble": _bubble_target_sizes,
}
#: The modes the native core draws (D10: a mode offers ``vulkan`` once its port passes; see
#: ``visualizer_mode_registry`` ``renderer_backends``): Spectrum's hand-written item (N2.5) and the generic modes.
NATIVE_MODE_IDS = frozenset({"spectrum", *GENERIC_MODE_SETTINGS})

#: One slot of a native mode's stream (Spectrum's record is 1488 bytes, Spline Curve's 3200; the slot shape rounds it);
#: a larger record (Bubble's) takes whole multiples of it (``_slot_bytes``).
_SLOT_BYTES = 4096


def _slot_bytes(mode_id: str) -> int:
    """The slot size of ``mode_id``'s stream: its record and the slot's own words, in whole 4096-byte steps."""
    from core.visualizer_engine.native_schema import schema_for_mode
    from core.visualizer_engine.packet_abi import SLOT_OVERHEAD

    needed = schema_for_mode(mode_id).layout.size + SLOT_OVERHEAD
    return max(_SLOT_BYTES, -(-needed // _SLOT_BYTES) * _SLOT_BYTES)
#: How long the native item fades in and out (fade, never vanish: audit N29 M1): the Visualizer's own activation fade,
#: read from its owner (round 2, L5).
FAILURE_FADE_MS = round(ACTIVATION_SCENE_FADE_DURATION_S * 1000.0)
#: Frames the core may refuse in a row (each keeps the last drawn one) before the native item fades out (round 2, M5):
#: half a second at 60 frames, so a lasting refusal never stands as a frozen card.
REFUSED_RUN_FADE = 30


def native_route_wanted(backend: str | None = None) -> bool:
    """Whether the Visualizer draws through the native route on ``backend`` (the process's when None): Vulkan."""
    if backend is None:
        from rendering.quick.bootstrap import quick_backend_api

        backend = quick_backend_api()
    return str(backend) == "vulkan"


class NativeVisualizerRoute:
    """One Visualizer item's native drawing: a native item in ``content_host`` and the frame stream it reads."""

    #: The item's surface texels: RGBA8 (lead's decision, N2.5 round 5). RGBA16F gave rule (a) nothing (52,238 steady
    #: pixels over one level against RGBA8's 52,213 before the quad alignment that fixed it) at twice the memory; the
    #: composite keeps ``surface_format`` as a harness switch only (``spectrum_check`` / ``owner_render_parity``
    #: ``--surface-format``).
    surface_format = "rgba8"

    def __init__(self, core: Any, content_host: Any) -> None:
        self._core = core
        self._content_host = content_host
        # One native item per kind (``_content_kind``): Spectrum's own, and one generic item every generic mode is
        # drawn on (its program retargeted, never a new item). ``_content`` is the bound identity's.
        self._contents: dict[str, Any] = {}
        self._content: Any = None
        self._memory: Any = None
        self._writer: Any = None
        self._identity: Any = None
        self._code = 0
        self._card: dict | None = None
        self._settings: dict | None = None
        self._placed: tuple | None = None
        self._snapshot: Any = None
        self._faded_out = False       # faded out within an activation: its next showing fades back in
        self._late: Any = None        # the identity whose first frame comes late (a failure, a wait): it fades in (M2)
        self._failure: tuple | None = None   # the inputs a failed sync had (nothing is retried until they change)
        self._core_failure: str | None = None   # the core's content failing (M4, M5): the item faded out until it draws
        self._core_draws = 0          # the core's draws when it failed: recovered once they move
        self._recheck = False         # an edge fired: the next sync reads the core's status even at rest
        self._request_update: Callable[[], Any] | None = None
        self._edges: dict[str, _WindowEdge] = {}
        self.failures = 0
        self.waits = 0
        self.published = 0
        self.closed = False

    # ------------------------------------------------------------------------------------------------ binding

    @property
    def identity(self) -> Any:
        return self._identity

    @property
    def spectrum(self) -> Any:
        """The native Spectrum item (None until made)."""
        content = self._contents.get("spectrum")
        return None if content is None else content.item

    @property
    def native_item(self) -> Any:
        """The bound identity's native item (None while nothing is bound)."""
        return None if self._content is None else self._content.item

    def prepare(self) -> None:
        """At attach (long before an activation): each kind's native item made and its synchronisation asked for, so it
        has read its window's framebuffer by the first activation of any native mode (round 2, L1: only its own
        synchronisation reads it). Never raises; a failure is retried at the first sync."""
        if self.closed:
            return
        for kind in _CONTENT_KINDS:
            def make(kind=kind) -> None:
                self._content_of(kind).composite.update()

            self._guarded(make)

    def set_update_request(self, request: Callable[[], Any] | None) -> None:
        """The item's update (a bound method, held weakly): what a window edge re-runs (round 2, M3, M4)."""
        if request is None:
            self._request_update = None
        elif hasattr(request, "__self__"):
            method = weakref.WeakMethod(request)
            self._request_update = lambda: (method() or (lambda: None))()
        else:
            self._request_update = request

    def bind(self, identity: Any) -> None:
        """Draw ``identity``'s frames (a native mode's activation); the previous stream retires."""
        if self.closed:
            raise RuntimeError("the native Visualizer route is closed")
        mode_id = str(identity.mode_id)
        if mode_id not in NATIVE_MODE_IDS:
            raise ValueError(f"the native Visualizer route draws {sorted(NATIVE_MODE_IDS)}, not {mode_id!r} "
                             "(D10: a mode without a renderer on this backend is never offered)")
        if identity == self._identity:
            return
        self.unbind()
        from core.visualizer_engine.packet_abi import FramePacketWriter, create_frame_mapping, mode_code

        # The native item and its program first: a failure there leaves no mapping behind (audit 14 Nov, M1), and a
        # program that did not load is loaded again at the next bind rather than drawn without.
        content = self._content_of(_content_kind(mode_id))
        content.load(mode_id)
        code = mode_code(mode_id)
        values = {"runtime_generation": int(identity.runtime_generation),
                  "engine_generation": int(identity.engine_generation),
                  "activation_id": int(identity.activation_id)}
        memory = create_frame_mapping(generation=values["runtime_generation"], slot_bytes=_slot_bytes(mode_id),
                                      engine_generation=values["engine_generation"],
                                      activation_id=values["activation_id"], mode_code=code,
                                      token=f"route{uuid.uuid4().hex[:10]}")
        writer = None
        try:
            writer = FramePacketWriter(memory.buf)
            content.bind(mode_id, memory.name, {**values, "mode_code": code})
        except BaseException:
            # Nothing of the failed bind stays: the mapping is released, closed and unlinked here.
            if writer is not None:
                writer.release()
            _close_mapping(memory)
            raise
        self._memory, self._writer = memory, writer
        self._identity = identity
        self._content = content
        self._code = code
        self._card = self._placed = self._settings = None
        self._snapshot = None
        self._faded_out = False       # a new activation: its card's content fade brings it in

    def unbind(self) -> None:
        """The bound stream retires (never waits, D1) and the native item is hidden at this edge, as the Python item
        stops drawing the activation at it: the owner's own fades (the scene's, the card's content fade) have run
        before an activation ends, so a fade of the route's own on top would draw the last frame on past the
        Python renderer's (rule (a), ABI 12 build round: 1.3 s of the last frame after a mode switch, up to 9 levels).
        The hide is its own guarded step before the stream retires (round 2, L3): a stream that cannot retire never
        leaves the card shown. The core keeps the frame while no stream is bound."""
        if self._identity is None:
            return
        self._identity = None
        self._snapshot = None
        self._card = self._placed = self._settings = None
        self._core_failure = None
        self._disarm_edges()
        content, self._content = self._content, None
        writer, self._writer = self._writer, None
        memory, self._memory = self._memory, None
        try:
            if content is not None:
                # The hide first, on its own (L3); at once, as the Python item (rule (a)).
                self._guarded(lambda: content.composite.set(visible=False, fade_ms=0))
                content.unbind()
        finally:
            # The route's own mapping goes whatever the native item said (N29 L2): nothing of it outlives the unbind.
            try:
                if writer is not None:
                    writer.release()
            finally:
                if memory is not None:
                    _close_mapping(memory)

    def close(self) -> None:
        """Unbind and destroy the native item (before its content host retires). Idempotent."""
        if self.closed:
            return
        self.unbind()
        self.closed = True
        self._disarm_edges()
        contents, self._contents = list(self._contents.values()), {}
        for content in contents:
            content.composite.destroy()

    # ---------------------------------------------------------------------------------------------- the edges

    def drop(self) -> None:
        """The retained frame is no longer drawn; the stream stays bound (the item's drop edge)."""
        self._snapshot = None
        if self._content is not None and self._identity is not None:
            self._content.drop()

    def retained_snapshot(self, identity: Any) -> Any:
        """The snapshot last published for ``identity`` (the Python node's ``retained_snapshot``)."""
        return self._snapshot if identity is not None and identity == self._identity else None

    def sync(self, *, bridge: Any, identity: Any, presentation: Any, authority: bool) -> bool:
        """GUI thread, at an update request of the item: the take the Python item makes at its sync, published into
        the stream, and the native item asked for a frame. Returns whether a frame was published.

        Never raises (audit 14 Nov, M1; N29 L2). A failure is logged once per run of failures and the native item fades
        out (never vanishes: N29 M1). What is tried again (N29 M1): a failure of the setup (the bind, the program, the
        window's map) when one of its inputs changes (the identity, the window's size or framebuffer, the record's
        placement); a failure of a frame (the admission, the take, its card, settings or publish: round 2, M1) at the
        next update. A window that is not there yet is an ordinary state, logged at debug; a window whose framebuffer
        the native item has not read yet (before its first frame, after a resize) is waited for on its own edge (M3).
        The core's own failures (round 2, M4, M5) fade the item out too, and it fades back in once the core draws."""
        if self.closed:
            return False
        if identity is None:
            self._failure = None
            self._guarded(self.unbind)
            return False
        if presentation is None:
            # The owner hides the Visualizer (and fades it back in itself): no composite fade on its return (L5).
            self._guarded(lambda: self._hide(fade_back_in=False))
            return False
        from rendering.native.spectrum import FramebufferNotReady

        try:
            metrics = self._window_metrics(presentation, str(identity.mode_id))
        except FramebufferNotReady as exc:
            return self._wait_for_framebuffer(identity, exc)
        except Exception as exc:  # no window yet, or none any more
            return self._fail((identity, None, None), exc, stage="setup")
        inputs = (identity, metrics, _placement_key(presentation))
        if self._failure is not None:
            failed_inputs, stage = self._failure
            if stage == "setup" and inputs == failed_inputs:
                return False                              # failed closed: nothing per update until an input changes
        try:
            published = self._sync(bridge=bridge, identity=identity, presentation=presentation, authority=authority,
                                   metrics=metrics)
        except _FrameFailure as failure:
            return self._fail(inputs, failure.cause, stage="frame")
        except Exception as exc:
            return self._fail(inputs, exc, stage="setup")
        if published and self._failure is not None:
            self._failure = None                          # recovered: the next failure is logged again
        return published

    def _window_metrics(self, presentation: Any, mode_id: str = "spectrum") -> tuple:
        """The window's metrics as ``mode_id``'s native item read them at its own synchronisation."""
        from rendering.native.spectrum import window_metrics

        return window_metrics(self._content_host, self._content_of(_content_kind(mode_id)).composite)

    def _content_of(self, kind: str) -> Any:
        """``kind``'s native item, made on first use, hidden until its first frame is placed: a placement that fades in
        (a late first frame, M2) then fades from nothing (an item made shown would pop in, its fade a no-op: ABI 12
        build round, --unprimed)."""
        content = self._contents.get(kind)
        if content is None:
            content = _SpectrumContent(self._core, self._content_host) if kind == "spectrum" else \
                _ModeContent(self._core, self._content_host)
            self._contents[kind] = content
            content.composite.set(surface_format=self.surface_format, visible=False)
        return content

    def _guarded(self, step) -> None:
        """A teardown step that must not raise into the item's update (N29 L2): logged instead."""
        try:
            step()
        except Exception:
            logger.debug("[VISUALIZER][NATIVE] A native route teardown step failed", exc_info=True)

    def _fail(self, inputs: tuple, exc: BaseException, *, stage: str) -> bool:
        """The fail-closed state: logged once per run of failures (a window not there yet at debug), the native item
        faded out, the frame not drawn. The identity's next first showing fades in (M2)."""
        from rendering.native.spectrum import WindowNotReady

        if self._failure is None or self._failure[0] != inputs:
            self.failures += 1
            if isinstance(exc, WindowNotReady):
                logger.debug("[VISUALIZER][NATIVE] The native route waits for its window: %s", exc)
            elif self._failure is None:
                logger.error("[VISUALIZER][NATIVE] The native route failed (%s); the native item fades out until it "
                             "draws again", exc, exc_info=exc)
        self._failure = (inputs, stage)
        self._late = inputs[0]
        self._guarded(self._hide)
        return False

    def _wait_for_framebuffer(self, identity: Any, exc: BaseException) -> bool:
        """The native item has not read its window's framebuffer as it is now (M3): the item keeps what it shows (a
        resize does not fade it), asks Qt for its synchronisation, and the window's next ``afterSynchronizing`` re-runs
        the update, which then cards the frame for the framebuffer as it is (the retained one when no new frame comes).
        An unshown identity's first frame fades in (M2)."""
        if not self._edges.get("afterSynchronizing"):
            self.waits += 1
            logger.debug("[VISUALIZER][NATIVE] The native route waits for its window's framebuffer: %s", exc)
        if self._placed is None:
            self._late = identity
        self._arm("afterSynchronizing")
        content = self._contents.get(_content_kind(str(identity.mode_id)))
        if content is not None:
            self._guarded(content.composite.update)
        return False

    @property
    def failed(self) -> bool:
        """Whether the route is in its fail-closed state (its own failure, or the core's)."""
        return self._failure is not None or self._core_failure is not None

    # ---------------------------------------------------------------------------------------- the window's edges

    def _arm(self, signal: str) -> None:
        """One firing of the window's ``signal`` (queued to the GUI thread) re-runs the item's update."""
        window = self._content_host.window() if self._content_host is not None else None
        if window is None or self._request_update is None:
            return
        edge = self._edges.get(signal)
        if edge is None:
            edge = self._edges[signal] = _WindowEdge(signal, self._edge_fired)
        edge.arm(window)

    def _disarm_edges(self) -> None:
        for edge in self._edges.values():
            self._guarded(edge.disarm)

    def _edge_fired(self) -> None:
        if self.closed:
            return
        self._recheck = True
        request = self._request_update
        if request is not None:
            try:
                request()
            except Exception:
                logger.debug("[VISUALIZER][NATIVE] The native route's update after a window edge failed", exc_info=True)

    # ------------------------------------------------------------------------------------------ the core's health

    def _core_verdict(self, status: Any) -> bool:
        """The core's content health at this sync (M4, M5): a failing build, or a run of refused frames past
        ``REFUSED_RUN_FADE``, fades the item out (logged once per run); it is healthy again once the core draws."""
        if status is None:
            return self._core_failure is None
        problem = None
        if status.failing:
            problem = f"the native content's build failed ({status.failures} failure(s))"
        elif status.refused_run >= REFUSED_RUN_FADE:
            problem = f"the native content refused {status.refused_run} frames in a row"
        if problem is not None:
            if self._core_failure is None:
                self.failures += 1
                self._core_draws = status.draws
                logger.error("[VISUALIZER][NATIVE] %s; the native item fades out until it draws again", problem)
            self._core_failure = problem
            self._late = self._identity
            self._guarded(self._hide)
            return False
        if self._core_failure is not None and status.draws > self._core_draws:
            logger.info("[VISUALIZER][NATIVE] The native content draws again; the native item fades back in")
            self._core_failure = None
        return self._core_failure is None

    def _sync(self, *, bridge: Any, identity: Any, presentation: Any, authority: bool, metrics: tuple) -> bool:
        if identity != self._identity:
            self.bind(identity)
        if bridge is None:
            return False
        from rendering.native.composite import composite_geometry, window_pixel_ratio

        # On the window's own 2x2 quads (every edge on an even device pixel): the shader's fine derivatives then pair
        # the pixels the Python renderer's did (N2.5 rule (a): an odd target origin moved them at the cap arcs). The
        # device pixels are the window's own (its framebuffer over its logical size, audit 14 Nov H1), never dpr's.
        window_size, window_pixels = metrics
        geometry = composite_geometry(presentation, quad_aligned=True,
                                      pixel_ratio=window_pixel_ratio(window_size, window_pixels))
        # The native item is placed in its content host, which lies where the scene draws the card (R-NEW: never the
        # record's exact outer origin, half a device pixel away from it at most).
        origin = content_host_origin(presentation)
        placed = (geometry, origin)
        content = self._content
        recheck, self._recheck = self._recheck, False
        sent = False
        try:
            # The frame's own stage (N29 M1; round 2 M1: the admission and the take too): a failure here is tried
            # again at the next update, never latched for the activation.
            if not authority:
                bridge.admit_at_sync()
            snapshot = bridge.take_for_render(
                runtime_generation=identity.runtime_generation, engine_generation=identity.engine_generation,
                activation_id=identity.activation_id, mode_id=identity.mode_id, required_presentation=presentation,
                allow_presentation_rebase=authority)
            # With no new frame the retained one is carded again when the window or the placement moved (M3: a resize
            # is corrected at rest), and nothing is sent at rest.
            drawn = snapshot if snapshot is not None else self._snapshot
            if drawn is None:
                return False
            full = self.card(presentation, drawn, geometry, metrics)
            card = content.shown_card(full, drawn)
            if snapshot is None and card == self._card and placed == self._placed and not recheck:
                return False
            if card != self._card:
                content.present(card)
                self._card = card
                sent = True
            settings = self.settings(drawn, full)
            if settings != self._settings:
                content.settings(settings, drawn)    # by name; re-packed by the core only when they change
                self._settings = settings
                sent = True
            sent = content.target_sizes(drawn, settings) or sent
            if snapshot is not None:
                logical = snapshot.logical
                payload, payload_schema = content.encode(logical)
                self._writer.publish(payload, payload_schema=payload_schema,
                                     logical_timestamp=float(logical.logical_timestamp or 0.0),
                                     flags=_admission_flags(logical), mode_code=self._code,
                                     runtime_generation=int(identity.runtime_generation),
                                     engine_generation=int(identity.engine_generation),
                                     activation_id=int(identity.activation_id))
            healthy = self._core_verdict(content.composite.content_status())
        except _ProgramRefused as refused:
            raise refused.cause from None             # the setup stage's: latched until an input changes
        except Exception as exc:
            raise _FrameFailure(exc) from exc
        if healthy and placed != self._placed:
            # Shown once a frame of its own is published for it, never before. After a fade-out (a failure, a hide) it
            # fades back in, and so does an activation whose first frame came late (M2); a new activation's first
            # frame shows at once, its fade-in the card's own content fade (the Python renderer's: rule (a) holds
            # from the first frame).
            fade = FAILURE_FADE_MS if self._faded_out or self._late == identity else 0
            content.composite.place(geometry, origin, visible=True, fade_ms=fade)
            self._placed = placed
            self._faded_out = False
            self._late = None
            self._failure = None                          # shown again: the next failure is logged again
            sent = True
        if snapshot is not None:
            self._snapshot = snapshot
            self.published += 1
        if sent:
            # What the core builds from (the card, the settings, a new target) is recorded at the next frame: its
            # verdict is read once that frame has rendered, with no new frame needed (M4).
            self._arm("afterRendering")
        content.update()
        return snapshot is not None

    def card(self, presentation: Any, snapshot: Any, geometry: Any, metrics: tuple | None = None) -> dict:
        """The card handed to the native item: the item's own size from the committed record, the drawn inputs from
        the snapshot's (the Python node's split: its item is the record's outer rect, its renderer draws the
        snapshot's presentation). ``metrics``: the window's (logical size, framebuffer pixels)."""
        from rendering.native.spectrum import spectrum_presentation

        window_size, window_pixels = metrics if metrics is not None else self._window_metrics(presentation)
        # The Python renderer's item lies in the content host (R-NEW): at the drawn card on the display, and wherever
        # the display lies in the window (an R-63 overscan above it).
        placement = {"host_origin": content_host_origin(presentation), "item_origin": self._host_window_origin()}
        card = spectrum_presentation(presentation, geometry, window_size=window_size, window_pixels=window_pixels,
                                     **placement)
        drawn = spectrum_presentation(snapshot.presentation, geometry, window_size=window_size,
                                      window_pixels=window_pixels, **placement)
        for key in ("content_rect", "viewport_extent", "visual_scale", "dpr", "content_fade", "expanded"):
            card[key] = drawn[key]
        return card

    def _host_window_origin(self) -> tuple[float, float] | None:
        """The content host's top-left in its window, logical (Qt's own scene mapping); None for a host that is not a
        Qt Quick item (the card then takes the display at the window's origin)."""
        map_to_scene = getattr(self._content_host, "mapToScene", None)
        if map_to_scene is None:
            return None
        from PySide6.QtCore import QPointF

        point = map_to_scene(QPointF(0.0, 0.0))
        return (float(point.x()), float(point.y()))

    def settings(self, snapshot: Any, card: dict) -> dict:
        """The Settings- and card-derived members of the drawn frame, by name (the Python renderer's own arithmetic:
        ``spectrum_settings_values``, or the generic mode's ``GENERIC_MODE_SETTINGS`` function). ``card``: the route's
        whole card (``card``)."""
        generic = None if self._identity is None else GENERIC_MODE_SETTINGS.get(str(self._identity.mode_id))
        if generic is not None:
            return generic(snapshot, card)
        from rendering.quick.visualizer.implementations.spectrum import spectrum_settings_values

        return spectrum_settings_values(snapshot.logical, snapshot.presentation, item_size=card["item_size"],
                                        oriented_size=card["oriented_size"],
                                        content_rotation_quarters=card["quarters"],
                                        content_rect=card["content_rect"], item_from_window=card["item_from_window"],
                                        window_from_target=card["window_from_target"],
                                        target_px=card["target_size"])

    def _hide(self, *, fade_back_in: bool = True) -> None:
        if self._content is not None and self._placed is not None:
            self._placed = None
            if fade_back_in:
                self._faded_out = True
            self._content.composite.set(visible=False, fade_ms=FAILURE_FADE_MS)   # fade, never vanish (N29 M1)


#: The native items a route holds, one per kind: Spectrum's hand-written item and the generic modes' item.
_CONTENT_KINDS = ("spectrum", "mode")


def _admission_flags(logical: Any) -> int:
    """The slot flags of ``logical``'s publication (``publication_flags``), as the core's admission reads them. The
    core admits a playing frame only with ``FLAG_SOURCE_CURRENT`` (``stream_source.cpp``): the Python node's rule
    (``render_contract.snapshot_is_render_admissible``) for a mode whose first reactive output must come from its
    tracked source. A mode that animates by itself (Spline Curve) is admitted by the Python node without a current
    source, so its frames carry the bit as admitted: the native item then draws every frame the Python renderer draws
    (rule (a); without it the first frames of an activation were refused, N5.1)."""
    from core.visualizer_engine.packet_abi import FLAG_SOURCE_CURRENT
    from core.visualizer_engine.packet_mailbox import publication_flags
    from widgets.spotify_visualizer import mode_capabilities

    flags = publication_flags(logical)
    if not mode_capabilities.requires_authoritative_first_source(getattr(logical, "mode_id", "")):
        flags |= FLAG_SOURCE_CURRENT
    return flags


def _content_kind(mode_id: str) -> str:
    """The kind of native item that draws ``mode_id``; a mode the route does not draw is refused (ValueError)."""
    if mode_id == "spectrum":
        return "spectrum"
    if mode_id in GENERIC_MODE_SETTINGS:
        return "mode"
    raise ValueError(f"the native Visualizer route draws {sorted(NATIVE_MODE_IDS)}, not {mode_id!r} "
                     "(D10: a mode without a renderer on this backend is never offered)")


class _SpectrumContent:
    """The native Spectrum (N2.5, ``rendering.native.spectrum.NativeSpectrum``): its program loaded once, its stream
    bound at the route's bind, the route's whole card handed over."""

    def __init__(self, core: Any, host: Any) -> None:
        self.item = core.spectrum(host)
        self.composite = self.item.composite
        self._programmed = False      # the mode's pack is loaded into the native item

    def load(self, mode_id: str) -> None:
        if not self._programmed:
            from rendering.native.program_values import mode_fragment_pack

            # The product's own pack (tools/regen_qrc.py --shaders), loaded at run time: no module build for a shader
            # change (N2.5's standing port rule).
            self.item.program(mode_fragment_pack(mode_id))
            self._programmed = True

    def bind(self, mode_id: str, mapping_name: str, expect: dict) -> None:
        self.item.bind(mapping_name, expect=expect)

    def unbind(self) -> None:
        self.item.unbind()

    def shown_card(self, card: dict, snapshot: Any) -> dict:
        return card

    def present(self, card: dict) -> None:
        self.item.present_raw(card)

    def settings(self, values: dict, snapshot: Any = None) -> None:
        self.item.settings(values)

    def target_sizes(self, snapshot: Any, settings: dict) -> bool:
        return False

    def encode(self, logical: Any) -> tuple[bytes, int]:
        from core.visualizer_engine import spectrum_native_schema

        return spectrum_native_schema.encode(logical), spectrum_native_schema.SCHEMA_ID

    def drop(self) -> None:
        self.item.drop_retained_frame()

    def update(self) -> None:
        self.item.update()


class _ModeContent:
    """The generic modes' native item (D12, ``rendering.native.mode.NativeMode``), retargeted between them by its
    program. Its program is the mode's own fragment pack, one pass blended as the Python render host blends (straight
    alpha over the transparent target). A program is admitted against its settings, so the stream is bound with the
    first settings of an activation: the program first when the item draws another mode (with those settings), else
    the settings; then the stream with its runtime schema (``native_schema.schema_for_mode``)."""

    def __init__(self, core: Any, host: Any) -> None:
        self.item = core.mode(host)
        self.composite = self.item.composite
        self._pack: tuple[str, bytes] | None = None       # the bound mode's fragment pack, read at its bind
        self._program_mode: str | None = None             # the mode whose program the item holds
        self._pending: tuple[str, str, dict] | None = None   # (mode, mapping name, expect): bound at its first settings
        self._bound = False
        self._sizes: dict | None = None                     # the explicit targets' sizes sent since the program

    def load(self, mode_id: str) -> None:
        if self._pack is None or self._pack[0] != mode_id:
            from rendering.native.program_values import mode_fragment_pack

            self._pack = (mode_id, mode_fragment_pack(mode_id))

    def bind(self, mode_id: str, mapping_name: str, expect: dict) -> None:
        self._pending = (mode_id, mapping_name, dict(expect))

    def unbind(self) -> None:
        self._pending = None
        if self._bound:
            self._bound = False
            self.item.unbind()

    def shown_card(self, card: dict, snapshot: Any) -> dict:
        """The core members' card (``MODE_CARD_KEYS``): the route's card with the drawn border width (the Python
        renderer's ``presentation.border_width``)."""
        from rendering.native.mode import MODE_CARD_KEYS

        shown = {key: card[key] for key in MODE_CARD_KEYS if key in card}
        shown["border_width"] = float(getattr(snapshot.presentation, "border_width", 0.0) or 0.0)
        return shown

    def present(self, card: dict) -> None:
        self.item.card(card)

    def settings(self, values: dict, snapshot: Any = None) -> None:
        pending = self._pending
        if pending is None:
            self.item.settings(values)
            return
        mode_id, mapping_name, expect = pending
        if self._program_mode != mode_id:
            from rendering.native.mode import ModePass

            if self._pack is None or self._pack[0] != mode_id:
                self.load(mode_id)
            try:
                build = GENERIC_MODE_PROGRAMS.get(mode_id)
                if build is None:
                    self.item.program([ModePass(mode_id, self._pack[1], "alpha")], values)
                else:
                    sizes = GENERIC_MODE_TARGET_SIZES[mode_id](snapshot, values)
                    program = build(self._pack[1], sizes)
                    self.item.program(program["passes"], values, targets=program["targets"],
                                      streams=program["streams"])
                    self._sizes = dict(sizes)                  # the program's declarations hold them
            except Exception as exc:
                # A setup input (checkpoint audit 3 L2): latched by the route until one of its inputs changes, as
                # Spectrum's program at its bind, never tried again at every update.
                raise _ProgramRefused(exc) from exc
            self._program_mode = mode_id
        else:
            self.item.settings(values)
        from core.visualizer_engine.native_schema import schema_for_mode

        self.item.bind(mapping_name, schema_for_mode(mode_id), expect=expect)
        self._bound = True
        self._pending = None

    def target_sizes(self, snapshot: Any, settings: dict) -> bool:
        """The bound mode's explicit-size targets follow its card and Settings (Bubble's ambient target, N5.1): sent
        when they change, never per frame. True when something was sent."""
        sizer = GENERIC_MODE_TARGET_SIZES.get(str(self._program_mode))
        if sizer is None or self._pending is not None:
            return False
        sizes = sizer(snapshot, settings)
        if sizes == self._sizes:
            return False
        for name, size in sizes.items():
            self.item.target_size(name, size)
        self._sizes = dict(sizes)
        return True

    def encode(self, logical: Any) -> tuple[bytes, int]:
        from core.visualizer_engine.native_schema import schema_for_mode

        schema = schema_for_mode(getattr(logical, "mode_id", None))
        return schema.encode(logical), schema.schema_id

    def drop(self) -> None:
        self.item.drop_retained_frame()

    def update(self) -> None:
        self.item.update()


class _WindowEdge:
    """One firing of a window signal, queued to the GUI thread (round 2, M3, M4): connected when armed, disconnected
    when it fires or is disarmed. An event edge, never a timer or a poll."""

    def __init__(self, signal: str, fired: Callable[[], None]) -> None:
        self._signal = signal
        self._fired = fired
        self._window: Any = None
        self._receiver: Any = None

    def __bool__(self) -> bool:
        return self._window is not None

    def arm(self, window: Any) -> None:
        if self._window is window:
            return
        self.disarm()
        from PySide6.QtCore import Qt

        if self._receiver is None:
            self._receiver = _edge_receiver(self._fire)
        getattr(window, self._signal).connect(self._receiver.fired, Qt.ConnectionType.QueuedConnection)
        self._window = window

    def disarm(self) -> None:
        window, self._window = self._window, None
        if window is not None:
            try:
                getattr(window, self._signal).disconnect(self._receiver.fired)
            except (RuntimeError, TypeError):
                pass                                # the window went first

    def _fire(self) -> None:
        if self._window is None:
            return
        self.disarm()
        self._fired()


def _edge_receiver(fire: Callable[[], None]) -> Any:
    """A GUI-thread QObject whose plain method takes the queued signal (a QML-free C++ signal: no @Slot with a result,
    memory note on PySide's slot crash)."""
    from PySide6.QtCore import QObject

    class _Receiver(QObject):
        def fired(self) -> None:
            fire()

    return _Receiver()


class _FrameFailure(Exception):
    """A failure of one frame's own inputs (its card, settings or publish): tried again at the next new snapshot."""

    def __init__(self, cause: BaseException) -> None:
        super().__init__(str(cause))
        self.cause = cause


class _ProgramRefused(Exception):
    """The core refused a generic mode's program (its settings do not fit, D12 point 4): a setup failure, latched until
    an input of the setup changes (checkpoint audit 3 L2), raised past the frame stage."""

    def __init__(self, cause: BaseException) -> None:
        super().__init__(str(cause))
        self.cause = cause


def _close_mapping(memory: Any) -> None:
    memory.close()
    try:
        memory.unlink()
    except FileNotFoundError:
        pass


def content_host_origin(presentation: Any) -> tuple[float, float]:
    """The content host's top-left, display-logical: where the scene places the Visualizer's loader, the drawn card
    (``resolve_card_drawn_rect``, 1C.4: the record's outer rect on whole device pixels; a frameless shell's is its outer
    rect). The composite's rect is on whole device pixels in display coordinates, so relative to this origin the native
    item lies on whole device pixels too. Relative to the record's exact outer origin instead (R-NEW) the item sat up
    to half a device pixel off them, and at a half pixel the composite's pixel lookup fell on its texel thresholds: the
    two triangles of the item's quad rounded apart and the bars broke along its diagonal (Vulkan, Display 1)."""
    from widgets.spotify_visualizer.presentation_geometry import resolve_card_drawn_rect

    x, y, _width, _height = resolve_card_drawn_rect(presentation)
    return (float(x), float(y))


def _placement_key(presentation: Any) -> tuple:
    """What places the card in its window (a failure is retried once any of it changes)."""
    return tuple(getattr(presentation, name, None) for name in (
        "outer_rect", "content_rect", "content_rotation_quarters", "dpr"))


def attach_native_route(item: Any, content_host: Any, backend: str | None = None) -> NativeVisualizerRoute | None:
    """On the native route's backend: the route of ``item`` (a ``VisualizerRenderItem``) in ``content_host``, from the
    process's native core (``rendering.quick.bootstrap.native_core``). Elsewhere None, and nothing is created."""
    if not native_route_wanted(backend):
        return None
    from rendering.quick.bootstrap import native_core

    core = native_core()
    if core is None:
        raise RuntimeError("the Visualizer's native route needs the native core (start_quick_backend on Vulkan)")
    route = NativeVisualizerRoute(core, content_host)
    item.attach_native_route(route)                # the item hands the route its update (round 2, M3, M4)
    route.prepare()
    return route


__all__ = ["GENERIC_MODE_SETTINGS", "NATIVE_MODE_IDS", "NativeVisualizerRoute", "attach_native_route", "content_host_origin",
           "native_route_wanted"]
