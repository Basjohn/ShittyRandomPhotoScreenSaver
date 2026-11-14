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

The route's stream is created at bind (the identity's mapping), retired at unbind (the reader stores Retiring at once
and is released on the render thread at the item's next sync, D1; the name is unlinked at once, the reader's own
view stays mapped until then) and the composite goes with the route's close (before the content host retires).
GUI thread only; nothing runs at rest (a frame is published only when the bridge hands a new one).

Fade, never vanish (audit N29 M1, round 2 M2 to M5, L3): the native item fades out on any failure (the route's own,
or the core's: a content build that failed or a run of refused frames, read from the item's status) and fades back in
when it draws again; an activation whose first frame comes late (after a failure or a wait for the window) fades in; an
unbind fades the item out over its last frame (the core keeps it). The route waits on the window's own edges, never a
timer: ``afterSynchronizing`` once the native item has read the window's framebuffer (before the first frame, after a
resize), ``afterRendering`` once the core has recorded what the route just changed (so a failed build is seen with no
new frame). Each is armed for one firing and re-runs the item's update.
"""
from __future__ import annotations

import uuid
import weakref
from typing import Any, Callable

from core.logging.logger import get_logger
from widgets.spotify_visualizer.quick_display_visualizer_owner import ACTIVATION_SCENE_FADE_DURATION_S

logger = get_logger(__name__)

#: The modes the native core draws (D10: a mode offers ``vulkan`` once its port passes; see
#: ``visualizer_mode_registry`` ``renderer_backends``).
NATIVE_MODE_IDS = frozenset({"spectrum"})

#: One slot of Spectrum's stream (the record is 1488 bytes; the slot shape rounds it).
_SLOT_BYTES = 4096
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
        self._spectrum: Any = None
        self._memory: Any = None
        self._writer: Any = None
        self._identity: Any = None
        self._code = 0
        self._card: dict | None = None
        self._settings: dict | None = None
        self._placed: tuple | None = None
        self._snapshot: Any = None
        self._programmed = False      # the mode's pack is loaded into the native item
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
        return self._spectrum

    def prepare(self) -> None:
        """At attach (long before an activation): the native item made and its synchronisation asked for, so it has read
        its window's framebuffer by the first activation (round 2, L1: only its own synchronisation reads it). Never
        raises; a failure is retried at the first sync."""
        if self.closed:
            return

        def make() -> None:
            if self._spectrum is None:
                self._spectrum = self._core.spectrum(self._content_host)
                self._spectrum.composite.set(surface_format=self.surface_format)
            self._spectrum.composite.update()

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
        if self._spectrum is None:
            self._spectrum = self._core.spectrum(self._content_host)
            self._spectrum.composite.set(surface_format=self.surface_format)
        if not self._programmed:
            from rendering.native.program_values import mode_fragment_pack

            # The product's own pack (tools/regen_qrc.py --shaders), loaded at run time: no module build for a shader
            # change (N2.5's standing port rule).
            self._spectrum.program(mode_fragment_pack(mode_id))
            self._programmed = True
        code = mode_code(mode_id)
        values = {"runtime_generation": int(identity.runtime_generation),
                  "engine_generation": int(identity.engine_generation),
                  "activation_id": int(identity.activation_id)}
        memory = create_frame_mapping(generation=values["runtime_generation"], slot_bytes=_SLOT_BYTES,
                                      engine_generation=values["engine_generation"],
                                      activation_id=values["activation_id"], mode_code=code,
                                      token=f"route{uuid.uuid4().hex[:10]}")
        writer = None
        try:
            writer = FramePacketWriter(memory.buf)
            self._spectrum.bind(memory.name, expect={**values, "mode_code": code})
        except BaseException:
            # Nothing of the failed bind stays: the mapping is released, closed and unlinked here.
            if writer is not None:
                writer.release()
            _close_mapping(memory)
            raise
        self._memory, self._writer = memory, writer
        self._identity = identity
        self._code = code
        self._card = self._placed = self._settings = None
        self._snapshot = None
        self._faded_out = False       # a new activation: its card's content fade brings it in

    def unbind(self) -> None:
        """The bound stream retires (never waits, D1) and the native item fades out over its last frame (the core keeps
        it while no stream is bound: round 2, L3)."""
        if self._identity is None:
            return
        self._identity = None
        self._snapshot = None
        self._card = self._placed = self._settings = None
        self._core_failure = None
        self._disarm_edges()
        spectrum = self._spectrum
        writer, self._writer = self._writer, None
        memory, self._memory = self._memory, None
        try:
            if spectrum is not None:
                # The fade first, on its own (L3): a stream that cannot retire never leaves the card shown.
                self._guarded(lambda: spectrum.composite.set(visible=False, fade_ms=FAILURE_FADE_MS))
                spectrum.unbind()
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
        spectrum, self._spectrum = self._spectrum, None
        if spectrum is not None:
            spectrum.composite.destroy()

    # ---------------------------------------------------------------------------------------------- the edges

    def drop(self) -> None:
        """The retained frame is no longer drawn; the stream stays bound (the item's drop edge)."""
        self._snapshot = None
        if self._spectrum is not None and self._identity is not None:
            self._spectrum.drop_retained_frame()

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
            metrics = self._window_metrics(presentation)
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

    def _window_metrics(self, presentation: Any) -> tuple:
        from rendering.native.spectrum import window_metrics

        if self._spectrum is None:
            self._spectrum = self._core.spectrum(self._content_host)
            self._spectrum.composite.set(surface_format=self.surface_format)
        return window_metrics(self._content_host, self._spectrum.composite)

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
        if self._spectrum is not None:
            self._guarded(self._spectrum.composite.update)
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
        from core.visualizer_engine import spectrum_native_schema
        from core.visualizer_engine.packet_mailbox import publication_flags
        from rendering.native.composite import composite_geometry, window_pixel_ratio

        # On the window's own 2x2 quads (every edge on an even device pixel): the shader's fine derivatives then pair
        # the pixels the Python renderer's did (N2.5 rule (a): an odd target origin moved them at the cap arcs). The
        # device pixels are the window's own (its framebuffer over its logical size, audit 14 Nov H1), never dpr's.
        window_size, window_pixels = metrics
        geometry = composite_geometry(presentation, quad_aligned=True,
                                      pixel_ratio=window_pixel_ratio(window_size, window_pixels))
        # The content host's top-left is the record's outer rect (the Python item sits at its origin with the outer
        # rect's size, ``VisualizerRenderItem.set_presentation``), whenever QML lays the host out.
        origin = (float(presentation.outer_rect[0]), float(presentation.outer_rect[1]))
        placed = (geometry, origin)
        spectrum = self._spectrum
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
            card = self.card(presentation, drawn, geometry, metrics)
            if snapshot is None and card == self._card and placed == self._placed and not recheck:
                return False
            if card != self._card:
                spectrum.present_raw(card)
                self._card = card
                sent = True
            settings = self.settings(drawn, card)
            if settings != self._settings:
                spectrum.settings(settings)          # by name; re-packed by the core only when they change
                self._settings = settings
                sent = True
            if snapshot is not None:
                logical = snapshot.logical
                self._writer.publish(spectrum_native_schema.encode(logical),
                                     payload_schema=spectrum_native_schema.SCHEMA_ID,
                                     logical_timestamp=float(logical.logical_timestamp or 0.0),
                                     flags=publication_flags(logical), mode_code=self._code,
                                     runtime_generation=int(identity.runtime_generation),
                                     engine_generation=int(identity.engine_generation),
                                     activation_id=int(identity.activation_id))
            healthy = self._core_verdict(spectrum.composite.content_status())
        except Exception as exc:
            raise _FrameFailure(exc) from exc
        if healthy and placed != self._placed:
            # Shown once a frame of its own is published for it, never before. After a fade-out (a failure, a hide) it
            # fades back in, and so does an activation whose first frame came late (M2); a new activation's first
            # frame shows at once, its fade-in the card's own content fade (the Python renderer's: rule (a) holds
            # from the first frame).
            fade = FAILURE_FADE_MS if self._faded_out or self._late == identity else 0
            spectrum.composite.place(geometry, origin, visible=True, fade_ms=fade)
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
        spectrum.update()
        return snapshot is not None

    def card(self, presentation: Any, snapshot: Any, geometry: Any, metrics: tuple | None = None) -> dict:
        """The card handed to the native item: the item's own size from the committed record, the drawn inputs from
        the snapshot's (the Python node's split: its item is the record's outer rect, its renderer draws the
        snapshot's presentation). ``metrics``: the window's (logical size, framebuffer pixels)."""
        from rendering.native.spectrum import spectrum_presentation

        window_size, window_pixels = metrics if metrics is not None else self._window_metrics(presentation)
        card = spectrum_presentation(presentation, geometry, window_size=window_size, window_pixels=window_pixels)
        drawn = spectrum_presentation(snapshot.presentation, geometry, window_size=window_size,
                                      window_pixels=window_pixels)
        for key in ("content_rect", "viewport_extent", "visual_scale", "dpr", "content_fade", "expanded"):
            card[key] = drawn[key]
        return card

    def settings(self, snapshot: Any, card: dict) -> dict:
        """The Settings- and card-derived members of the drawn frame, by name (the Python renderer's own arithmetic,
        ``spectrum_settings_values``)."""
        from rendering.quick.visualizer.implementations.spectrum import spectrum_settings_values

        return spectrum_settings_values(snapshot.logical, snapshot.presentation, item_size=card["item_size"],
                                        oriented_size=card["oriented_size"],
                                        content_rotation_quarters=card["quarters"],
                                        content_rect=card["content_rect"], item_from_window=card["item_from_window"],
                                        window_from_target=card["window_from_target"],
                                        target_px=card["target_size"])

    def _hide(self, *, fade_back_in: bool = True) -> None:
        if self._spectrum is not None and self._placed is not None:
            self._placed = None
            if fade_back_in:
                self._faded_out = True
            self._spectrum.composite.set(visible=False, fade_ms=FAILURE_FADE_MS)   # fade, never vanish (N29 M1)


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


def _close_mapping(memory: Any) -> None:
    memory.close()
    try:
        memory.unlink()
    except FileNotFoundError:
        pass


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


__all__ = ["NATIVE_MODE_IDS", "NativeVisualizerRoute", "attach_native_route", "native_route_wanted"]
