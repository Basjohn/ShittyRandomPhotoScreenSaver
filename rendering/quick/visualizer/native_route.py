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
"""
from __future__ import annotations

import uuid
from typing import Any

from core.logging.logger import get_logger

logger = get_logger(__name__)

#: The modes the native core draws (D10: a mode offers ``vulkan`` once its port passes; see
#: ``visualizer_mode_registry`` ``renderer_backends``).
NATIVE_MODE_IDS = frozenset({"spectrum"})

#: One slot of Spectrum's stream (the record is 1488 bytes; the slot shape rounds it).
_SLOT_BYTES = 4096


def native_route_wanted(backend: str | None = None) -> bool:
    """Whether the Visualizer draws through the native route on ``backend`` (the process's when None): Vulkan."""
    if backend is None:
        from rendering.quick.bootstrap import quick_backend_api

        backend = quick_backend_api()
    return str(backend) == "vulkan"


class NativeVisualizerRoute:
    """One Visualizer item's native drawing: a native item in ``content_host`` and the frame stream it reads."""

    def __init__(self, core: Any, content_host: Any) -> None:
        self._core = core
        self._content_host = content_host
        self._spectrum: Any = None
        self._memory: Any = None
        self._writer: Any = None
        self._identity: Any = None
        self._code = 0
        self._card: dict | None = None
        self._placed: tuple | None = None
        self._snapshot: Any = None
        self.published = 0
        self.closed = False

    # ------------------------------------------------------------------------------------------------ binding

    @property
    def identity(self) -> Any:
        return self._identity

    @property
    def spectrum(self) -> Any:
        return self._spectrum

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

        code = mode_code(mode_id)
        values = {"runtime_generation": int(identity.runtime_generation),
                  "engine_generation": int(identity.engine_generation),
                  "activation_id": int(identity.activation_id)}
        self._memory = create_frame_mapping(generation=values["runtime_generation"], slot_bytes=_SLOT_BYTES,
                                            engine_generation=values["engine_generation"],
                                            activation_id=values["activation_id"], mode_code=code,
                                            token=f"route{uuid.uuid4().hex[:10]}")
        self._writer = FramePacketWriter(self._memory.buf)
        if self._spectrum is None:
            self._spectrum = self._core.spectrum(self._content_host)
        self._spectrum.bind(self._memory.name, expect={**values, "mode_code": code})
        self._identity = identity
        self._code = code
        self._card = self._placed = None
        self._snapshot = None

    def unbind(self) -> None:
        """The bound stream retires (never waits, D1) and the native item shows nothing."""
        if self._identity is None:
            return
        self._identity = None
        self._snapshot = None
        self._card = self._placed = None
        spectrum = self._spectrum
        if spectrum is not None:
            spectrum.unbind()
            spectrum.composite.set(visible=False)
        writer, self._writer = self._writer, None
        memory, self._memory = self._memory, None
        if writer is not None:
            writer.release()
        if memory is not None:
            memory.close()
            try:
                memory.unlink()
            except FileNotFoundError:
                pass

    def close(self) -> None:
        """Unbind and destroy the native item (before its content host retires). Idempotent."""
        if self.closed:
            return
        self.unbind()
        self.closed = True
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
        the stream, and the native item asked for a frame. Returns whether a frame was published."""
        if self.closed:
            return False
        if identity is None:
            self.unbind()
            return False
        if presentation is None:
            self._hide()
            return False
        if identity != self._identity:
            self.bind(identity)
        if bridge is None:
            return False
        from core.visualizer_engine import spectrum_native_schema
        from core.visualizer_engine.packet_mailbox import publication_flags
        from rendering.native.composite import composite_geometry

        if not authority:
            bridge.admit_at_sync()
        snapshot = bridge.take_for_render(
            runtime_generation=identity.runtime_generation, engine_generation=identity.engine_generation,
            activation_id=identity.activation_id, mode_id=identity.mode_id, required_presentation=presentation,
            allow_presentation_rebase=authority)
        geometry = composite_geometry(presentation)
        # The content host's top-left is the record's outer rect (the Python item sits at its origin with the outer
        # rect's size, ``VisualizerRenderItem.set_presentation``), whenever QML lays the host out.
        origin = (float(presentation.outer_rect[0]), float(presentation.outer_rect[1]))
        placed = (geometry, origin)
        spectrum = self._spectrum
        if placed != self._placed:
            spectrum.composite.place(geometry, origin, visible=True)
            self._placed = placed
        if snapshot is None:
            return False
        card = self.card(presentation, snapshot, geometry)
        if card != self._card:
            spectrum.present_raw(card)
            self._card = card
        logical = snapshot.logical
        self._writer.publish(spectrum_native_schema.encode(logical),
                             payload_schema=spectrum_native_schema.SCHEMA_ID,
                             logical_timestamp=float(logical.logical_timestamp or 0.0),
                             flags=publication_flags(logical), mode_code=self._code,
                             runtime_generation=int(identity.runtime_generation),
                             engine_generation=int(identity.engine_generation),
                             activation_id=int(identity.activation_id))
        self._snapshot = snapshot
        self.published += 1
        spectrum.update()
        return True

    def card(self, presentation: Any, snapshot: Any, geometry: Any) -> dict:
        """The card handed to the native item: the item's own size from the committed record, the drawn inputs from
        the snapshot's (the Python node's split: its item is the record's outer rect, its renderer draws the
        snapshot's presentation)."""
        from rendering.native.spectrum import spectrum_presentation, window_metrics

        window_size, window_pixels = window_metrics(self._content_host, float(presentation.dpr))
        card = spectrum_presentation(presentation, geometry, window_size=window_size, window_pixels=window_pixels)
        drawn = spectrum_presentation(snapshot.presentation, geometry, window_size=window_size,
                                      window_pixels=window_pixels)
        for key in ("content_rect", "viewport_extent", "visual_scale", "dpr", "content_fade", "expanded"):
            card[key] = drawn[key]
        return card

    def _hide(self) -> None:
        if self._spectrum is not None and self._placed is not None:
            self._spectrum.composite.set(visible=False)
            self._placed = None


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
    item.attach_native_route(route)
    return route


__all__ = ["NATIVE_MODE_IDS", "NativeVisualizerRoute", "attach_native_route", "native_route_wanted"]
