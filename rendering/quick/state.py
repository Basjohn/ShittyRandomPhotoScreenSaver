"""Immutable display-local state crossing the Qt Quick presentation boundary."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QScreen
from rendering.custom_layout_contract import get_screen_signature


RectTuple = tuple[int, int, int, int]


class QuickWindowRole(str, Enum):
    """Native top-level role selected by the product runtime."""

    SCREENSAVER = "screensaver"
    DASHBOARD_SPLASH = "dashboard-splash"
    DASHBOARD_TOOL = "dashboard-tool"


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
    widget_glow_on_hover: bool = False
    widget_glow_on_click: bool = False
    widget_glow_intensity: float = 1.0
    widget_glow_distance: float = 14.0
    widget_glow_color: tuple[int, int, int, int] = (0, 0, 0, 0)
    widget_glow_jedi_mode: bool = False
    always_show_glyphs: bool = True
    show_3d_control_hints: bool = True

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
        if self.role is QuickWindowRole.DASHBOARD_TOOL:
            flags |= Qt.WindowType.Tool
        else:
            # Standard runtime and the Dashboard splash policy both preserve the
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
class QuickDisplayBindingLoss:
    """One-shot primitive notice that a generation left its bound display."""

    screen_index: int
    runtime_generation: int | None
    expected_screen_key: str
    observed_screen_key: str | None
    observed_screen_name: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class QuickSceneReadiness:
    """Explicit generation-scoped presentation readiness and retirement facts."""

    screen_index: int
    runtime_generation: int | None
    qml_root_created: bool = False
    scene_graph_initialized: bool = False
    scene_graph_invalidated: bool = False
    admission_open: bool = True
    qml_objects_retired: bool = False
    error: str | None = None
    # A frame of this scene was presented, published once on every backend (D10, N5.2h): with the presentable scene
    # it is the reveal's one input (DisplayManager._startup_reveal_admits). The native background layer fades its first
    # photo in by itself, so no background renderer or base frame fact exists to wait for.
    frame_presented: bool = False

    @property
    def scene_presentable(self) -> bool:
        """The scene exists, renders and is admitted (the reveal adds only its presented frame)."""
        return bool(
            self.qml_root_created
            and self.scene_graph_initialized
            and self.admission_open
            and not self.scene_graph_invalidated
            and not self.qml_objects_retired
            and self.error is None
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rect_tuple(rect: QRect) -> RectTuple:
    return (
        int(rect.x()),
        int(rect.y()),
        int(rect.width()),
        int(rect.height()),
    )


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
        screen_key=get_screen_signature(screen),
        name=name,
        manufacturer=manufacturer,
        model=model,
        serial_number=serial_number,
        geometry=geometry,
        available_geometry=available_geometry,
        device_pixel_ratio=float(screen.devicePixelRatio()),
        refresh_rate_hz=float(screen.refreshRate()),
    )
