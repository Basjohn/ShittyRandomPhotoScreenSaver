"""Per-display QML and scene-item ownership for the Qt Quick presenter."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal, Qt
from PySide6.QtQml import QQmlComponent, QQmlContext, QQmlEngine
from PySide6.QtQuick import QQuickItem

from .bootstrap import quick_qml_root
from .image_state import PresentationImage
from .render import BackgroundRenderItem, RenderNodeTelemetry
from .state import QuickSceneReadiness
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
        self._component = QQmlComponent(self._engine, self._qml_url)
        if self._component.status() != QQmlComponent.Status.Ready:
            raise RuntimeError(self._component_error("DisplayScene.qml failed to load"))

    @property
    def qml_root(self) -> Path:
        return self._qml_root

    @property
    def qml_url(self) -> QUrl:
        return QUrl(self._qml_url)

    @property
    def is_ready(self) -> bool:
        return self._component.status() == QQmlComponent.Status.Ready

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

    def _component_error(self, prefix: str) -> str:
        details = "; ".join(error.toString() for error in self._component.errors())
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
    def telemetry(self) -> RenderNodeTelemetry:
        return self._telemetry

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

    def quiesce_for_retirement(self) -> None:
        """Close state admission; item deletion waits for legal invalidation."""

        if not self._readiness.admission_open:
            return
        self._publish_readiness(admission_open=False)
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
        }

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
        root, self._scene_root = self._scene_root, None
        self._background_item = None
        context, self._context = self._context, None
        if root is not None:
            root.setParentItem(None)
            root.deleteLater()
        if context is not None:
            context.deleteLater()
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
