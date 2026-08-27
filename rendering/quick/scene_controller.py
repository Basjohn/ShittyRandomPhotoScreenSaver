"""Per-display QML and scene-item ownership for the Qt Quick presenter."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, replace
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QUrl, Signal, Qt
from PySide6.QtGui import QColor
from PySide6.QtQml import QQmlComponent, QQmlContext, QQmlEngine
from PySide6.QtQuick import QQuickItem

from core.settings.visualizer_mode_registry import VisualizerShellPolicy
from rendering.custom_layout_session import (
    CustomLayoutSession,
    CustomLayoutSessionItem,
)
from widgets.spotify_visualizer.render_bridge import (
    VisualizerRenderIdentity,
    VisualizerSnapshotBridge,
)
from widgets.spotify_visualizer.render_state import ResolvedVisualizerPresentation
from widgets.spotify_visualizer.presentation_geometry import (
    resize_visualizer_presentation_uniformly,
)

from .bootstrap import quick_qml_root
from .custom_layout_overlay import (
    CustomLayoutOverlayModel,
    GeometryResolver,
    ResizeBeginHandler,
    ResizeUpdateHandler,
    ResizeWheelHandler,
    RetainedCustomLayoutOverlay,
)
from .image_state import PresentationImage
from .media_artwork import MediaArtworkImageProvider
from .render import BackgroundRenderItem, RenderNodeTelemetry
from .state import QuickSceneReadiness
from .transitions.state import TransitionRun
from .visualizer import VisualizerRenderItem, VisualizerRenderNodeTelemetry
from .widgets.host import OrdinaryWidgetPresentationHost, OverlayWidgetGeometry
from .widgets.registry import (
    ORDINARY_WIDGET_FAMILY_COMPONENTS,
    ordinary_widget_family_component,
)
from .window import QuickDisplayWindow


class QuickSceneFactory(QObject):
    """Process-level QML engine/component cache with no display-runtime refs."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._qml_root = quick_qml_root()
        self._qml_url = QUrl.fromLocalFile(
            str(self._qml_root / "DisplayScene.qml")
        )
        self._engine = QQmlEngine(self)
        self._engine.addImportPath(str(self._qml_root))
        self._media_artwork_provider = MediaArtworkImageProvider()
        self._engine.addImageProvider(
            self._media_artwork_provider.provider_id,
            self._media_artwork_provider,
        )
        self._component = QQmlComponent(self._engine, self._qml_url)
        if self._component.status() != QQmlComponent.Status.Ready:
            raise RuntimeError(self._component_error("DisplayScene.qml failed to load"))
        # Shared retained ordinary-widget presentation primitive. Compiled once
        # as process-level QML compile state; instances are created per display
        # context and are never retained on the factory.
        self._overlay_widget_url = QUrl.fromLocalFile(
            str(self._qml_root / "OverlayWidget.qml")
        )
        self._overlay_widget_component = QQmlComponent(
            self._engine, self._overlay_widget_url
        )
        if self._overlay_widget_component.status() != QQmlComponent.Status.Ready:
            raise RuntimeError(
                self._component_error(
                    "OverlayWidget.qml failed to load",
                    self._overlay_widget_component,
                )
            )
        self._ordinary_widget_family_components: dict[str, QQmlComponent] = {}
        for descriptor in ORDINARY_WIDGET_FAMILY_COMPONENTS:
            component = QQmlComponent(
                self._engine,
                QUrl.fromLocalFile(
                    str(self._qml_root / descriptor.qml_filename)
                ),
            )
            if component.status() != QQmlComponent.Status.Ready:
                raise RuntimeError(
                    self._component_error(
                        f"{descriptor.qml_filename} failed to load",
                        component,
                    )
                )
            self._ordinary_widget_family_components[descriptor.family_id] = component

    @property
    def qml_root(self) -> Path:
        return self._qml_root

    @property
    def qml_url(self) -> QUrl:
        return QUrl(self._qml_url)

    @property
    def is_ready(self) -> bool:
        return self._component.status() == QQmlComponent.Status.Ready

    @property
    def media_artwork_provider(self) -> MediaArtworkImageProvider:
        return self._media_artwork_provider

    def create_display_root(
        self,
        *,
        owner: QObject,
        screen_index: int,
        runtime_generation: int | None,
    ) -> tuple[QQmlContext, QQuickItem]:
        """Create one context/root without retaining either on the factory."""

        if not self.is_ready:
            raise RuntimeError(self._component_error("DisplayScene.qml is not ready"))
        context = QQmlContext(self._engine.rootContext(), owner)
        root = self._component.createWithInitialProperties(
            {
                "screenIndex": int(screen_index),
                "runtimeGeneration": runtime_generation,
            },
            context,
        )
        if not isinstance(root, QQuickItem):
            context.deleteLater()
            raise RuntimeError(
                self._component_error("DisplayScene.qml did not create a QQuickItem")
            )
        QQmlEngine.setObjectOwnership(
            root,
            QQmlEngine.ObjectOwnership.CppOwnership,
        )
        return context, root

    def create_overlay_widget(
        self,
        initial_properties: dict[str, object],
        context: QQmlContext,
    ) -> QQuickItem:
        """Create one retained overlay-widget root without retaining it here."""

        component = self._overlay_widget_component
        if component.status() != QQmlComponent.Status.Ready:
            raise RuntimeError(
                self._component_error("OverlayWidget.qml is not ready", component)
            )
        item = component.createWithInitialProperties(
            dict(initial_properties), context
        )
        if not isinstance(item, QQuickItem):
            raise RuntimeError(
                self._component_error(
                    "OverlayWidget.qml did not create a QQuickItem", component
                )
            )
        QQmlEngine.setObjectOwnership(
            item,
            QQmlEngine.ObjectOwnership.CppOwnership,
        )
        return item

    def create_ordinary_widget_family(
        self,
        family_id: str,
        initial_properties: Mapping[str, object],
        context: QQmlContext,
    ) -> QQuickItem:
        """Create one statically registered retained family component."""

        descriptor = ordinary_widget_family_component(family_id)
        component = self._ordinary_widget_family_components.get(
            descriptor.family_id
        )
        if component is None or component.status() != QQmlComponent.Status.Ready:
            raise RuntimeError(
                f"ordinary-widget family component is unavailable: {family_id!r}"
            )
        item = component.createWithInitialProperties(
            dict(initial_properties), context
        )
        if not isinstance(item, QQuickItem):
            raise RuntimeError(
                self._component_error(
                    f"{descriptor.qml_filename} did not create a QQuickItem",
                    component,
                )
            )
        QQmlEngine.setObjectOwnership(
            item,
            QQmlEngine.ObjectOwnership.CppOwnership,
        )
        return item

    def _component_error(
        self, prefix: str, component: QQmlComponent | None = None
    ) -> str:
        target = component if component is not None else self._component
        details = "; ".join(error.toString() for error in target.errors())
        return f"{prefix}: {details or 'unknown QML component error'}"


class QuickSceneController(QObject):
    """The sole creator/retirement owner for one display's runtime Quick items."""

    readiness_changed = Signal(object)

    def __init__(
        self,
        *,
        window: QuickDisplayWindow,
        factory: QuickSceneFactory,
        telemetry: RenderNodeTelemetry | None = None,
    ) -> None:
        super().__init__(window)
        self._window = window
        self._factory = factory
        self._telemetry = telemetry or RenderNodeTelemetry()
        self._context: QQmlContext | None = None
        self._scene_root: QQuickItem | None = None
        self._background_item: BackgroundRenderItem | None = None
        self._ordinary_widget_host: OrdinaryWidgetPresentationHost | None = None
        self._custom_layout_overlay: RetainedCustomLayoutOverlay | None = None
        self._custom_layout_session: CustomLayoutSession | None = None
        self._custom_layout_display_identity = ""
        self._custom_layout_display_origin = QPoint()
        self._custom_layout_visualizer_baseline: ResolvedVisualizerPresentation | None = None
        self._visualizer_loader: QQuickItem | None = None
        self._visualizer_root: QQuickItem | None = None
        self._visualizer_content_host: QQuickItem | None = None
        self._visualizer_item: VisualizerRenderItem | None = None
        self._visualizer_telemetry = VisualizerRenderNodeTelemetry()
        self._last_transition_run_id = 0
        self._readiness = QuickSceneReadiness(
            screen_index=window.screen_index,
            runtime_generation=window.runtime_generation,
        )

        context, root = factory.create_display_root(
            owner=self,
            screen_index=window.screen_index,
            runtime_generation=window.runtime_generation,
        )
        content = window.contentItem()
        root.setParent(content)
        root.setParentItem(content)
        self._context = context
        self._scene_root = root
        self._visualizer_loader = root.findChild(
            QQuickItem,
            "visualizerPresentationLoader",
        )
        if self._visualizer_loader is None:
            raise RuntimeError("DisplayScene.qml has no visualizer presentation loader")
        ordinary_widget_host_item = root.findChild(
            QQuickItem,
            "ordinaryWidgetHost",
        )
        if ordinary_widget_host_item is None:
            raise RuntimeError("DisplayScene.qml has no ordinary widget host")
        self._ordinary_widget_host = OrdinaryWidgetPresentationHost(
            host_item=ordinary_widget_host_item,
            context=context,
            create_overlay_item=factory.create_overlay_widget,
            create_family_item=factory.create_ordinary_widget_family,
        )
        custom_layout_overlay_item = root.findChild(
            QQuickItem,
            "customLayoutOverlay",
        )
        if custom_layout_overlay_item is None:
            raise RuntimeError("DisplayScene.qml has no CUSTOM layout overlay")
        self._custom_layout_overlay = RetainedCustomLayoutOverlay(
            custom_layout_overlay_item
        )
        self._background_item = BackgroundRenderItem(
            root,
            telemetry=self._telemetry,
        )

        content.widthChanged.connect(self._sync_root_width)
        content.heightChanged.connect(self._sync_root_height)
        root.widthChanged.connect(self._sync_background_width)
        root.heightChanged.connect(self._sync_background_height)
        window.sceneGraphInitialized.connect(
            self._on_scene_graph_initialized,
            Qt.ConnectionType.QueuedConnection,
        )
        window.frameSwapped.connect(
            self._on_frame_swapped,
            Qt.ConnectionType.QueuedConnection,
        )
        window.sceneGraphInvalidated.connect(
            self._on_scene_graph_invalidated,
            Qt.ConnectionType.QueuedConnection,
        )

        self._sync_root_width()
        self._sync_root_height()
        self._publish_readiness(qml_root_created=True)

    @property
    def scene_root(self) -> QQuickItem:
        root = self._scene_root
        if root is None:
            raise RuntimeError("display QML root has retired")
        return root

    @property
    def background_item(self) -> BackgroundRenderItem:
        item = self._background_item
        if item is None:
            raise RuntimeError("display background item has retired")
        return item

    @property
    def ordinary_widget_host(self) -> OrdinaryWidgetPresentationHost:
        host = self._ordinary_widget_host
        if host is None:
            raise RuntimeError("ordinary widget host has retired")
        return host

    @property
    def custom_layout_overlay(self) -> RetainedCustomLayoutOverlay:
        overlay = self._custom_layout_overlay
        if overlay is None:
            raise RuntimeError("CUSTOM layout overlay has retired")
        return overlay

    def bind_custom_layout_session(
        self,
        session: CustomLayoutSession,
        *,
        display_identity: str,
        display_origin: QPoint | None = None,
        geometry_resolver: GeometryResolver | None = None,
        resize_begin_handler: ResizeBeginHandler | None = None,
        resize_update_handler: ResizeUpdateHandler | None = None,
        resize_wheel_handler: ResizeWheelHandler | None = None,
    ) -> CustomLayoutOverlayModel:
        """Bind this display's retained pixels to shared CUSTOM working state."""

        identity = str(display_identity or "").strip()
        if not identity:
            raise ValueError("display_identity must not be empty")
        self._custom_layout_display_identity = identity
        self._custom_layout_display_origin = QPoint(display_origin or QPoint())
        self._custom_layout_session = session
        current_visualizer = (
            None if self._visualizer_item is None else self._visualizer_item.presentation
        )
        self._custom_layout_visualizer_baseline = current_visualizer
        return self.custom_layout_overlay.bind_session(
            session,
            display_identity=identity,
            display_origin=self._custom_layout_display_origin,
            geometry_resolver=geometry_resolver,
            item_change_publisher=self._apply_custom_layout_item,
            resize_begin_handler=resize_begin_handler,
            resize_update_handler=resize_update_handler,
            resize_wheel_handler=resize_wheel_handler,
        )

    def refresh_custom_layout_session(self) -> None:
        """Reproject current session state onto the same retained items."""

        self.custom_layout_overlay.model.refresh()

    def clear_custom_layout_session(self) -> None:
        """Remove transient edit state without recreating family presentations."""

        host = self.ordinary_widget_host
        for model_identity in host.model_identities():
            presentation = host.presentation_for_model_identity(model_identity)
            if presentation is not None:
                presentation.set_working_visible(True)
        if self._visualizer_root is not None:
            self._visualizer_root.setProperty("customLayoutWorkingVisible", True)
        self.custom_layout_overlay.clear_session()
        self._custom_layout_session = None
        self._custom_layout_display_identity = ""
        self._custom_layout_display_origin = QPoint()
        self._custom_layout_visualizer_baseline = None

    def _apply_custom_layout_item(self, item: CustomLayoutSessionItem) -> None:
        if item.model_identity == "spotify_visualizer":
            self._sync_custom_layout_visualizer()
            return
        host = self._ordinary_widget_host
        if host is None:
            return
        presentation = host.presentation_for_model_identity(item.model_identity)
        if presentation is None:
            return
        active_item = self._active_custom_layout_item(item.model_identity)
        presentation.set_working_visible(active_item is not None)
        if active_item is None:
            return
        presentation.apply_custom_layout_size_payload(
            active_item.current_size_payload
        )
        rect = active_item.current_global_rect
        origin = self._custom_layout_display_origin
        presentation.set_geometry(
            OverlayWidgetGeometry(
                float(rect.x() - origin.x()),
                float(rect.y() - origin.y()),
                float(rect.width()),
                float(rect.height()),
            )
        )

    def _active_custom_layout_item(
        self,
        model_identity: str,
    ) -> CustomLayoutSessionItem | None:
        session = self._custom_layout_session
        if session is None:
            return None
        return next(
            (
                item
                for item in session.items()
                if item.model_identity == model_identity
                and item.current_display_identity
                == self._custom_layout_display_identity
                and item.current_enabled
                and not item.removed
            ),
            None,
        )

    def _sync_custom_layout_visualizer(self) -> None:
        root = self._visualizer_root
        loader = self._visualizer_loader
        if root is None or loader is None:
            return
        if self._custom_layout_session is None:
            root.setProperty("customLayoutWorkingVisible", True)
            return
        active_item = self._active_custom_layout_item("spotify_visualizer")
        root.setProperty("customLayoutWorkingVisible", active_item is not None)
        if active_item is None:
            return
        rect = active_item.current_global_rect
        origin = self._custom_layout_display_origin
        local_origin = (
            float(rect.x() - origin.x()),
            float(rect.y() - origin.y()),
        )
        baseline = self._custom_layout_visualizer_baseline
        if baseline is None:
            loader.setX(local_origin[0])
            loader.setY(local_origin[1])
            return
        screen = self._window.screen()
        screen_geometry = None if screen is None else screen.geometry()
        if screen_geometry is not None and screen_geometry.width() > 0 and screen_geometry.height() > 0:
            display_size = (
                float(screen_geometry.width()),
                float(screen_geometry.height()),
            )
        else:
            display_size = (
                max(1.0, float(self._window.width())),
                max(1.0, float(self._window.height())),
            )
        target_width = (
            baseline.viewport_extent[0]
            * baseline.uniform_visual_scale
            * active_item.resize_scale
        )
        target_height = (
            baseline.viewport_extent[1]
            * baseline.uniform_visual_scale
            * active_item.resize_scale
        )
        # The Python session owner has already bounded/clamped this rectangle.
        # Keep the pure presentation resolver from independently moving it.
        display_size = (
            max(display_size[0], local_origin[0] + target_width),
            max(display_size[1], local_origin[1] + target_height),
        )
        resized = resize_visualizer_presentation_uniformly(
            baseline,
            display_size=display_size,
            outer_origin=local_origin,
            relative_scale=active_item.resize_scale,
        )
        self._apply_visualizer_presentation_items(
            resized,
            active=bool(root.property("presentationActive")),
        )

    @property
    def telemetry(self) -> RenderNodeTelemetry:
        return self._telemetry

    @property
    def visualizer_telemetry(self) -> VisualizerRenderNodeTelemetry:
        return self._visualizer_telemetry

    @property
    def visualizer_item(self) -> VisualizerRenderItem:
        item = self._visualizer_item
        if item is None:
            raise RuntimeError("visualizer presentation has not been activated")
        return item

    @property
    def readiness(self) -> QuickSceneReadiness:
        return self._readiness

    def set_background_proof_progress(self, progress: float) -> None:
        """Drive the Phase A background until real image state lands in Phase C."""

        if not self._readiness.admission_open:
            raise RuntimeError("Quick scene admission is closed")
        self.background_item.setProofProgress(float(progress))

    def set_presentation_image(self, image: PresentationImage | None) -> None:
        """Admit detached image state while this scene generation is live."""

        if not self._readiness.admission_open:
            raise RuntimeError("Quick scene admission is closed")
        self.background_item.set_presentation_image(image)

    @property
    def presentation_image(self) -> PresentationImage | None:
        return self.background_item.presentation_image

    def set_transition_run(self, run: TransitionRun | None) -> bool:
        """Publish the current generation-fenced run into the Quick sync path."""

        if not self._readiness.admission_open:
            raise RuntimeError("Quick scene admission is closed")
        if (
            run is not None
            and run.request.runtime_generation != self._readiness.runtime_generation
        ):
            raise ValueError("transition run generation does not match Quick scene")
        current = self.background_item.transition_run
        if run is not None:
            if run.run_id < self._last_transition_run_id:
                return False
            if run.run_id == self._last_transition_run_id and current != run:
                return False
            self._last_transition_run_id = run.run_id
        self.background_item.set_transition_run(run)
        return True

    def set_visualizer_render_source(
        self,
        bridge: VisualizerSnapshotBridge,
        identity: VisualizerRenderIdentity,
    ) -> None:
        """Bind one exact controller-owned activation to the Quick sync item."""

        if not self._readiness.admission_open:
            raise RuntimeError("Quick scene admission is closed")
        self._ensure_visualizer_items().bind_render_source(bridge, identity)

    def apply_visualizer_presentation(
        self,
        presentation: ResolvedVisualizerPresentation,
        *,
        active: bool = True,
    ) -> None:
        """Apply one immutable geometry/style record to shell, clip, and GL."""

        if not self._readiness.admission_open:
            raise RuntimeError("Quick scene admission is closed")
        if not isinstance(presentation, ResolvedVisualizerPresentation):
            raise TypeError("visualizer presentation must already be resolved")
        if self._custom_layout_session is not None:
            # Runtime publications remain truth for style/fade/content metrics;
            # CUSTOM contributes only its relative working size and position.
            self._custom_layout_visualizer_baseline = presentation
        self._apply_visualizer_presentation_items(presentation, active=active)
        self._sync_custom_layout_visualizer()

    def _apply_visualizer_presentation_items(
        self,
        presentation: ResolvedVisualizerPresentation,
        *,
        active: bool,
    ) -> None:
        """Project one resolved record without recursively resyncing CUSTOM state."""

        item = self._ensure_visualizer_items()
        loader = self._visualizer_loader
        root = self._visualizer_root
        if loader is None or root is None:
            raise RuntimeError("visualizer presentation ownership is incomplete")

        outer_x, outer_y, outer_width, outer_height = presentation.outer_rect
        loader.setX(outer_x)
        loader.setY(outer_y)
        loader.setWidth(outer_width)
        loader.setHeight(outer_height)
        root.setX(0.0)
        root.setY(0.0)
        root.setWidth(outer_width)
        root.setHeight(outer_height)
        item.set_presentation(presentation)

        style = presentation.shell_style
        root.setOpacity(presentation.scene_fade)
        root.setProperty(
            "cardShellEnabled",
            presentation.shell_policy is VisualizerShellPolicy.CARD,
        )
        root.setProperty(
            "cardBackgroundColor",
            self._color_from_style(
                style.get("background_color", (16, 16, 16, 179))
            ),
        )
        root.setProperty(
            "cardBorderColor",
            self._color_from_style(
                style.get("border_color", (255, 255, 255, 230))
            ),
        )
        root.setProperty("cardBorderWidth", presentation.border_width)
        root.setProperty(
            "cardCornerRadius",
            float(style.get("corner_radius", 0.0)),
        )
        root.setProperty(
            "cardShadowEnabled",
            bool(style.get("shadow_enabled", False)),
        )
        root.setProperty(
            "cardShadowColor",
            self._color_from_style(
                style.get("shadow_color", (0, 0, 0, 150))
            ),
        )
        root.setProperty(
            "cardShadowBlur",
            float(style.get("shadow_blur", 0.0)),
        )
        shadow_offset = style.get("shadow_offset", (0.0, 0.0))
        root.setProperty("cardShadowOffsetX", float(shadow_offset[0]))
        root.setProperty("cardShadowOffsetY", float(shadow_offset[1]))
        root.setProperty(
            "cardShadowSpread",
            float(style.get("shadow_spread", 0.0)),
        )
        root.setProperty("presentationActive", bool(active))

    def set_visualizer_presentation_active(self, active: bool) -> None:
        """Change retained presentation visibility without rebuilding it."""

        if not self._readiness.admission_open:
            raise RuntimeError("Quick scene admission is closed")
        if self._visualizer_root is not None:
            self._visualizer_root.setProperty("presentationActive", bool(active))
            self._sync_custom_layout_visualizer()

    def quiesce_for_retirement(self) -> None:
        """Close state admission; item deletion waits for legal invalidation."""

        if not self._readiness.admission_open:
            return
        self._publish_readiness(admission_open=False)
        if self._visualizer_item is not None:
            self._visualizer_item.clear_render_source()
        if self._visualizer_root is not None:
            self._visualizer_root.setProperty("presentationActive", False)
        if (
            not self._window.isVisible()
            and not self._window.isSceneGraphInitialized()
        ):
            self._retire_qml_objects()

    def finalize_retirement(self) -> None:
        """Retire QML objects after the window has no live scene graph."""

        if self._readiness.admission_open:
            raise RuntimeError("cannot retire an admitting Quick scene")
        if self._window.isSceneGraphInitialized():
            raise RuntimeError("cannot retire QML objects before scene invalidation")
        self._retire_qml_objects()

    def describe_scene_state(self) -> dict[str, object]:
        snapshot = self._telemetry.snapshot()
        return {
            "readiness": self._readiness.as_dict(),
            "qml_url": self._factory.qml_url.toLocalFile(),
            "qml_object_name": (
                self._scene_root.objectName() if self._scene_root is not None else None
            ),
            "render_initialize_count": snapshot.initialize_count,
            "render_count": snapshot.render_count,
            "release_count": snapshot.release_count,
            "invalidation_count": snapshot.invalidation_count,
            "render_error": snapshot.error,
            "presentation_image": (
                None
                if self._background_item is None
                or self._background_item.presentation_image is None
                else self._background_item.presentation_image.describe()
            ),
            "transition_run": (
                None
                if self._background_item is None
                or self._background_item.transition_run is None
                else {
                    "run_id": self._background_item.transition_run.run_id,
                    "runtime_generation": (
                        self._background_item.transition_run.request.runtime_generation
                    ),
                    "transition_id": (
                        self._background_item.transition_run.request.transition_id
                    ),
                }
            ),
            "last_transition_run_id": self._last_transition_run_id,
            "visualizer": {
                "instantiated": self._visualizer_item is not None,
                "render_identity": (
                    None
                    if self._visualizer_item is None
                    or self._visualizer_item.render_identity is None
                    else {
                        "runtime_generation": (
                            self._visualizer_item.render_identity.runtime_generation
                        ),
                        "engine_generation": (
                            self._visualizer_item.render_identity.engine_generation
                        ),
                        "activation_id": (
                            self._visualizer_item.render_identity.activation_id
                        ),
                        "mode_id": self._visualizer_item.render_identity.mode_id,
                    }
                ),
                "telemetry": asdict(self._visualizer_telemetry.snapshot()),
            },
        }

    def _ensure_visualizer_items(self) -> VisualizerRenderItem:
        if self._visualizer_item is not None:
            return self._visualizer_item
        loader = self._visualizer_loader
        if loader is None:
            raise RuntimeError("visualizer loader has retired")
        loader.setProperty("active", True)
        root = loader.property("item")
        if not isinstance(root, QQuickItem):
            raise RuntimeError("VisualizerPresentation.qml did not create a QQuickItem")
        QQmlEngine.setObjectOwnership(
            root,
            QQmlEngine.ObjectOwnership.CppOwnership,
        )
        content_host = root.findChild(QQuickItem, "visualizerContentHost")
        if content_host is None:
            raise RuntimeError("visualizer presentation has no content host")
        item = VisualizerRenderItem(
            content_host,
            telemetry=self._visualizer_telemetry,
        )
        self._visualizer_root = root
        self._visualizer_content_host = content_host
        self._visualizer_item = item
        self._sync_custom_layout_visualizer()
        return item

    @staticmethod
    def _color_from_style(value: object) -> QColor:
        try:
            red, green, blue, alpha = value
            color = QColor(int(red), int(green), int(blue), int(alpha))
        except (TypeError, ValueError):
            color = QColor(value)
        if not color.isValid():
            raise ValueError(f"invalid visualizer shell color: {value!r}")
        return color

    def _sync_root_width(self) -> None:
        if self._scene_root is not None:
            self._scene_root.setWidth(self._window.contentItem().width())

    def _sync_root_height(self) -> None:
        if self._scene_root is not None:
            self._scene_root.setHeight(self._window.contentItem().height())

    def _sync_background_width(self) -> None:
        if self._scene_root is not None and self._background_item is not None:
            self._background_item.setWidth(self._scene_root.width())

    def _sync_background_height(self) -> None:
        if self._scene_root is not None and self._background_item is not None:
            self._background_item.setHeight(self._scene_root.height())

    def _on_scene_graph_initialized(self) -> None:
        self._publish_readiness(
            scene_graph_initialized=True,
            scene_graph_invalidated=False,
        )

    def _on_frame_swapped(self) -> None:
        snapshot = self._telemetry.snapshot()
        self._publish_readiness(
            background_renderer_ready=(
                snapshot.initialize_count > 0 and snapshot.error is None
            ),
            intentional_base_frame_ready=(
                snapshot.render_count > 0 and snapshot.error is None
            ),
            error=snapshot.error,
        )

    def _on_scene_graph_invalidated(self) -> None:
        snapshot = self._telemetry.snapshot()
        self._publish_readiness(
            scene_graph_initialized=False,
            background_renderer_ready=False,
            intentional_base_frame_ready=False,
            scene_graph_invalidated=True,
            error=snapshot.error,
        )
        if not self._readiness.admission_open:
            self._retire_qml_objects()

    def _retire_qml_objects(self) -> None:
        if self._readiness.qml_objects_retired:
            return
        # Retire retained overlay widgets first: each is detached from the host
        # and queued for deletion, so no C++-owned item outlives the display
        # generation or depends on the scene root still being attached.
        if self._ordinary_widget_host is not None:
            self._ordinary_widget_host.retire_all()
        if self._custom_layout_overlay is not None:
            self._custom_layout_overlay.retire()
        self._custom_layout_display_identity = ""
        self._custom_layout_display_origin = QPoint()
        self._custom_layout_session = None
        self._custom_layout_visualizer_baseline = None
        root = self._scene_root
        context = self._context
        # Detach and queue the C++-owned root while every Python child wrapper
        # is still retained. Dropping a Python-created child first can trigger
        # a PySide ownership cascade before the outer QML wrapper is detached.
        if root is not None:
            root.setParentItem(None)
            root.setParent(None)
            root.deleteLater()
        if context is not None:
            context.deleteLater()
        self._scene_root = None
        self._background_item = None
        self._ordinary_widget_host = None
        self._custom_layout_overlay = None
        self._visualizer_item = None
        self._visualizer_content_host = None
        self._visualizer_root = None
        self._visualizer_loader = None
        self._context = None
        self._publish_readiness(
            qml_root_created=False,
            qml_objects_retired=True,
        )

    def _publish_readiness(self, **changes: object) -> None:
        next_state = replace(self._readiness, **changes)
        if next_state == self._readiness:
            return
        self._readiness = next_state
        self.readiness_changed.emit(next_state)
