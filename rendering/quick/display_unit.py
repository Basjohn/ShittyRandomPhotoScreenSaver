"""Per-display Quick destination-chain assembly (H).

One ``QuickDisplayUnit`` is the destination chain for one selected display:

```text
selected display
    -> one QuickDisplayRuntime (window / scene / input / auxiliary / context /
       transition / one WidgetRuntimeManager)
    -> one QuickDisplayPresenter (families + option-A geometry)
    -> shared cross-display Ctrl coordination
```

The display orchestrator (``DisplayManager``) constructs one unit per selected
``QScreen`` and drives it through **clean** operations - it does not emulate the
legacy widget surface. Image, transition and visualizer routing use the
runtime's own explicit APIs; families and their content-driven geometry use the
presenter; Ctrl state is coordinated through the shared coordinator.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from PySide6.QtCore import QSize
from PySide6.QtGui import QPixmap, QScreen

from core.logging.logger import get_logger
from rendering.display_modes import DisplayMode

from .ctrl_coordinator import SharedCtrlCoordinator
from .display_image_route import present_processed_pixmap
from .display_processing import DisplayProcessingDescriptor
from .display_presenter import QuickDisplayPresenter
from .render import RenderNodeTelemetry
from .runtime import QuickDisplayRuntime
from .scene_controller import QuickSceneFactory
from .state import QuickWindowPolicy
from .widgets.family_binder import OrdinaryFamilyAdapter
from .widgets.host import OverlayWidgetGeometry

logger = get_logger(__name__)


class QuickDisplayUnit:
    """One selected display's full Quick destination chain."""

    def __init__(
        self,
        *,
        runtime: QuickDisplayRuntime,
        presenter: QuickDisplayPresenter,
        ctrl_coordinator: SharedCtrlCoordinator,
        ctrl_key: object,
    ) -> None:
        self._runtime = runtime
        self._presenter = presenter
        self._ctrl_coordinator = ctrl_coordinator
        self._ctrl_key = ctrl_key
        self._retired = False

    @property
    def runtime(self) -> QuickDisplayRuntime:
        return self._runtime

    @property
    def presenter(self) -> QuickDisplayPresenter:
        return self._presenter

    @property
    def screen_index(self) -> int:
        return self._runtime.screen_index

    @property
    def is_retired(self) -> bool:
        return self._retired

    def display_bounds(self) -> OverlayWidgetGeometry:
        """Return this display's logical host rectangle (origin-relative)."""

        _x, _y, width, height = self._runtime.display_identity.geometry
        return OverlayWidgetGeometry(0.0, 0.0, float(width), float(height))

    def bind_families(
        self,
        *,
        widgets_config: Mapping[str, object] | None,
        shadow_values: Mapping[str, object] | None = None,
        thread_manager: Any | None = None,
        committed_rect_resolver: Callable[[str], OverlayWidgetGeometry | None]
        | None = None,
    ) -> tuple[str, ...]:
        """Bind + place this display generation's ordinary families (option A)."""

        return self._presenter.bind_families(
            widgets_config=widgets_config,
            display_bounds=self.display_bounds(),
            shadow_values=shadow_values,
            thread_manager=thread_manager,
            committed_rect_resolver=committed_rect_resolver,
        )

    def reanchor_for_current_bounds(self) -> None:
        """Re-anchor content-anchored families to this display's current bounds."""

        self._presenter.set_display_bounds(self.display_bounds())

    # -- base image / transition (runtime's own explicit APIs) -------------- #
    def present_image(self, processed_pixmap: QPixmap, *, image_path: str = "") -> None:
        """Publish one processed pipeline pixmap as the base image."""

        present_processed_pixmap(self._runtime, processed_pixmap, image_path=image_path)

    def clear(self) -> None:
        self._runtime.clear()

    def target_size(self) -> QSize:
        return self._runtime.get_target_size()

    def processing_descriptor(
        self,
        display_mode: DisplayMode,
    ) -> DisplayProcessingDescriptor:
        """Snapshot immutable image-processing inputs for engine orchestration."""

        identity = self._runtime.display_identity
        _x, _y, logical_width, logical_height = identity.geometry
        pixel_size = self.target_size()
        return DisplayProcessingDescriptor(
            screen_index=self.screen_index,
            target_size=QSize(pixel_size),
            logical_size=QSize(int(logical_width), int(logical_height)),
            display_mode=display_mode,
            device_pixel_ratio=float(identity.device_pixel_ratio),
        )

    def has_running_transition(self) -> bool:
        return bool(self._runtime.transition_controller.is_active)

    # -- visibility / lifecycle -------------------------------------------- #
    def show_on_screen(self) -> None:
        self._runtime.show_on_screen()

    def hide(self) -> None:
        self._runtime.hide()

    def quiesce(self) -> None:
        self._runtime.quiesce_for_runtime_pause()

    def retire(self) -> bool:
        """Retire this display generation exactly once, clean owner order.

        Families and their geometry bindings retire first, then the runtime
        closes its window/scene/input on the legal render-safe path, and finally
        this display's Ctrl contribution is dropped so it cannot pin Ctrl held.
        """

        if self._retired:
            return False
        self._retired = True
        self._presenter.retire()
        closed = self._runtime.close_runtime()
        self._ctrl_coordinator.forget(self._ctrl_key)
        return closed


def create_quick_display_unit(
    *,
    screen: QScreen,
    screen_index: int,
    runtime_generation: int,
    scene_factory: QuickSceneFactory,
    window_policy: QuickWindowPolicy,
    ctrl_coordinator: SharedCtrlCoordinator,
    interaction_mode_provider: Callable[[], bool] | None = None,
    telemetry: RenderNodeTelemetry | None = None,
    adapters: Sequence[OrdinaryFamilyAdapter] | None = None,
) -> QuickDisplayUnit:
    """Construct one display's full Quick destination chain.

    The runtime's cross-display Ctrl seam is bound to ``ctrl_coordinator`` so this
    display publishes only its own Ctrl state while reading the authoritative
    global-held truth. The Ctrl key is the screen index.
    """

    runtime = QuickDisplayRuntime(
        screen_index=screen_index,
        runtime_generation=runtime_generation,
        screen=screen,
        scene_factory=scene_factory,
        window_policy=window_policy,
        telemetry=telemetry,
        interaction_mode_provider=interaction_mode_provider,
        global_ctrl_held_provider=ctrl_coordinator.held_provider(),
        ctrl_state_publisher=ctrl_coordinator.publisher_for(screen_index),
    )
    presenter = QuickDisplayPresenter(runtime, adapters=adapters)
    return QuickDisplayUnit(
        runtime=runtime,
        presenter=presenter,
        ctrl_coordinator=ctrl_coordinator,
        ctrl_key=screen_index,
    )


__all__ = ["QuickDisplayUnit", "create_quick_display_unit"]
