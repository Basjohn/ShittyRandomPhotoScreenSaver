"""The host adapter's Python face (D5.1, D5.2; Current_Plan.md item 8b, N2.2).

A host gives the native core a device, a place to record each frame's commands and the frame edge. The core's frame
driver is connected to the host window's ``beforeRendering`` in C++ (``native/core/src/frame_driver.h``), so nothing
here ever runs on a render thread: these objects only create, attach, detach, read and close hosts from the GUI thread.

- :class:`WindowHost`: a Qt Quick window the product shows, rendered by Qt's render loop. On Vulkan it is hosted before
  it is first shown (the window then renders on the module's device, D6) and needs the process's Vulkan instance
  (:meth:`rendering.native.NativeCore.vulkan_instance`).
- :class:`HiddenHost`: a Qt Quick window the core drives itself with a ``QQuickRenderControl`` on its own render thread,
  never shown; the caller hands it the Qt Quick item to render and asks for frames.

The probe pass (``probe_pass.h``) is the harness's trivial core pass: switched on per host, it proves the frame edge,
the upload correction and the readback orientation; nothing creates it otherwise. Nothing in the product uses any of
this yet (N2.7 adds the backend owner).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any, Mapping

#: The probe pass's options (``ProbeConfig`` in ``probe_pass.h``); anything but the defaults is a negative control.
PROBE_OPTIONS = ("width", "height", "correction", "front_face", "fragment_flip", "ndc_flip")


@dataclass(frozen=True)
class ProbeReadback:
    """One completed readback of the probe's target: the raw rows as the target's memory holds them (row 0 first, never
    flipped: N0.3 rule 2), with the facts of the recording that produced it."""

    facts: Mapping[str, Any]
    rgba: bytes = field(repr=False)
    width: int
    height: int
    frame: int


def _address(obj: Any) -> int:
    import shiboken6

    if not shiboken6.isValid(obj):
        raise TypeError(f"{type(obj).__name__} is no longer valid")
    return int(shiboken6.getCppPointer(obj)[0])


class Host:
    """One host on the native core's side; closed explicitly (:meth:`close`)."""

    kind = ""

    def __init__(self, module: ModuleType, handle: int) -> None:
        self._module = module
        self._handle = int(handle)
        self._closed: dict | None = None

    @property
    def handle(self) -> int:
        return self._handle

    @property
    def closed(self) -> bool:
        return self._closed is not None

    def _live(self) -> int:
        if self._closed is not None:
            raise RuntimeError(f"the {self.kind} host {self._handle} is closed")
        return self._handle

    def state(self) -> dict:
        """The host and its frame drivers (the current one and the one detached last): edges, recorded passes, the
        thread probe (edges with a Python thread state: zero on the render thread), releases."""
        return json.loads(self._module.host_state(self._live()))

    def attach(self) -> None:
        """A new frame driver on the host's window (after :meth:`detach`)."""
        self._module.host_reattach(self._live())

    def detach(self) -> None:
        """The frame driver stops recording now and releases its resources on the render thread."""
        self._module.host_detach(self._live())

    def set_probe(self, **config: Any) -> None:
        """The probe pass from the next frame, with these options (``PROBE_OPTIONS``; the defaults are the decided
        conventions)."""
        unknown = sorted(set(config) - set(PROBE_OPTIONS))
        if unknown:
            raise ValueError(f"unknown probe option(s) {', '.join(unknown)} (the options are {', '.join(PROBE_OPTIONS)})")
        self._module.host_probe(self._live(), json.dumps(config))

    def clear_probe(self) -> None:
        self._module.host_probe(self._live(), "")

    def request_readback(self) -> None:
        """The next recorded probe pass reads its target back."""
        self._module.host_probe_readback(self._live())

    def probe_result(self) -> ProbeReadback | None:
        """The last completed probe readback, once (None until one completes)."""
        raw = self._module.host_probe_result(self._live())
        if raw is None:
            return None
        return ProbeReadback(json.loads(raw["facts"]), raw["rgba"], int(raw["width"]), int(raw["height"]),
                             int(raw["frame"]))

    def close(self) -> dict:
        """Detaches (a hidden host also tears down its window and device); returns what was done. Idempotent."""
        if self._closed is None:
            self._closed = json.loads(self._module.host_close(self._handle))
        return self._closed


class WindowHost(Host):
    """A Qt Quick window the product shows. Closing the host leaves the window alone; the module's device (Vulkan) goes
    when the window object is destroyed."""

    kind = "window"


class HiddenHost(Host):
    """A Qt Quick window the core drives with a render control on its own render thread; never shown."""

    kind = "hidden"

    def set_content(self, item: Any | None) -> None:
        """The Qt Quick item it renders (parented to its window and sized to it; never owned). None removes it."""
        from PySide6.QtQuick import QQuickItem

        if item is not None and not isinstance(item, QQuickItem):
            raise TypeError(f"the content is a QQuickItem, not {type(item).__name__}")
        self._module.host_set_content(self._live(), 0 if item is None else _address(item))

    def frames(self, count: int = 1) -> None:
        """Renders ``count`` frames (the GIL is released while the render thread works)."""
        self._module.host_frames(self._live(), int(count))


__all__ = ["HiddenHost", "Host", "PROBE_OPTIONS", "ProbeReadback", "WindowHost"]
