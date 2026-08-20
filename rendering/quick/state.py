"""Immutable display-local state crossing the Qt Quick presentation boundary."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QScreen


RectTuple = tuple[int, int, int, int]


class QuickWindowRole(str, Enum):
    """Native top-level role selected by the product runtime."""

    SCREENSAVER = "screensaver"
    MEDIA_CENTER_SPLASH = "media-center-splash"
    MEDIA_CENTER_TOOL = "media-center-tool"


class QuickRuntimePhase(str, Enum):
    """Lifecycle phase for one generation-scoped physical-display runtime."""

    CONSTRUCTED = "constructed"
    VISIBLE = "visible"
    PAUSED = "paused"
    RETIRING = "retiring"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class QuickInputState:
    """Primitive generation-scoped input admission and interaction facts."""

    screen_index: int
    runtime_generation: int | None
    admission_open: bool = True
    interaction_mode_enabled: bool = False
    ctrl_held: bool = False
    context_menu_active: bool = False
    exiting: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class QuickWindowPolicy:
    """Explicit top-level policy; cross-display focus selection lives elsewhere."""

    role: QuickWindowRole = QuickWindowRole.SCREENSAVER
    always_on_top: bool = True
    accepts_focus: bool = True
    blank_cursor: bool = True

    def flags(self) -> Qt.WindowType:
        flags = Qt.WindowType.FramelessWindowHint
        if self.role is QuickWindowRole.MEDIA_CENTER_TOOL:
            flags |= Qt.WindowType.Tool
        else:
            # Standard runtime and the MC splash policy both preserve the
            # current WM_APPCOMMAND-capable native role.
            flags |= Qt.WindowType.SplashScreen
        if self.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        if not self.accepts_focus:
            flags |= Qt.WindowType.WindowDoesNotAcceptFocus
        return flags


@dataclass(frozen=True, slots=True)
class QuickDisplayIdentity:
    """Primitive-only snapshot of one physical display and runtime generation."""

    screen_index: int
    runtime_generation: int | None
    screen_key: str
    name: str
    manufacturer: str
    model: str
    serial_number: str
    geometry: RectTuple
    available_geometry: RectTuple
    device_pixel_ratio: float
    refresh_rate_hz: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class QuickSceneReadiness:
    """Explicit generation-scoped presentation readiness and retirement facts."""

    screen_index: int
    runtime_generation: int | None
    qml_root_created: bool = False
    scene_graph_initialized: bool = False
    background_renderer_ready: bool = False
    intentional_base_frame_ready: bool = False
    scene_graph_invalidated: bool = False
    admission_open: bool = True
    qml_objects_retired: bool = False
    error: str | None = None

    @property
    def ready_for_reveal(self) -> bool:
        return bool(
            self.qml_root_created
            and self.scene_graph_initialized
            and self.background_renderer_ready
            and self.intentional_base_frame_ready
            and self.admission_open
            and not self.scene_graph_invalidated
            and not self.qml_objects_retired
            and self.error is None
        )

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ready_for_reveal"] = self.ready_for_reveal
        return payload


def _rect_tuple(rect: QRect) -> RectTuple:
    return (
        int(rect.x()),
        int(rect.y()),
        int(rect.width()),
        int(rect.height()),
    )


def _screen_key(
    *,
    name: str,
    manufacturer: str,
    model: str,
    serial_number: str,
    geometry: RectTuple,
) -> str:
    identity = [
        part
        for part in (
            f"serial:{serial_number}" if serial_number else "",
            f"manufacturer:{manufacturer}" if manufacturer else "",
            f"model:{model}" if model else "",
            f"name:{name}" if name else "",
        )
        if part
    ]
    if serial_number and identity:
        return "|".join(identity)
    return "|".join((*identity, f"geometry:{geometry}"))


def capture_display_identity(
    *,
    screen_index: int,
    runtime_generation: int | None,
    screen: QScreen,
) -> QuickDisplayIdentity:
    """Capture current QScreen facts without retaining the live QScreen object."""

    index = int(screen_index)
    if index < 0:
        raise ValueError("screen_index must be non-negative")
    if screen is None:
        raise ValueError("screen is required")

    geometry = _rect_tuple(screen.geometry())
    available_geometry = _rect_tuple(screen.availableGeometry())
    if geometry[2] <= 0 or geometry[3] <= 0:
        raise RuntimeError(f"screen {index} has invalid geometry: {geometry}")

    name = str(screen.name() or "")
    manufacturer = str(screen.manufacturer() or "")
    model = str(screen.model() or "")
    serial_number = str(screen.serialNumber() or "")
    generation = (
        None if runtime_generation is None else int(runtime_generation)
    )
    return QuickDisplayIdentity(
        screen_index=index,
        runtime_generation=generation,
        screen_key=_screen_key(
            name=name,
            manufacturer=manufacturer,
            model=model,
            serial_number=serial_number,
            geometry=geometry,
        ),
        name=name,
        manufacturer=manufacturer,
        model=model,
        serial_number=serial_number,
        geometry=geometry,
        available_geometry=available_geometry,
        device_pixel_ratio=float(screen.devicePixelRatio()),
        refresh_rate_hz=float(screen.refreshRate()),
    )
