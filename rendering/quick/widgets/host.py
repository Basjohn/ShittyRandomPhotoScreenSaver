"""Per-display retained ordinary-widget presentation host.

The host owns creation and retirement of retained Quick presentation items for
one display generation. It is deliberately presentation-only: it imports no
model, service, settings, or QWidget code, and it retains no reference to the
runtime generation beyond the QQuickItems it currently presents. E1 closed the
provider/model/runtime ownership boundary; E3 presentation must not route that
lifetime back through the display scene.

The scene itself stays free of per-widget ``if/elif`` dispatch: the host creates
generic ``OverlayWidget`` roots (an assigned display rectangle, a whole-widget
fade, and a shared card shell) and later family ports compose shell primitives
into each item's content area.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor
from PySide6.QtQml import QQmlContext
from PySide6.QtQuick import QQuickItem


# Deliberate destination policy established by F1 Clock and reused by ordinary
# families unless a family owns a real visual distinction.
ORDINARY_CARD_SHADOW_BASE = (4.0, 4.0)
ORDINARY_TEXT_SHADOW_BASE = (2.0, 2.0)


@dataclass(frozen=True)
class OverlayWidgetGeometry:
    """One resolved display-space rectangle for a retained overlay widget."""

    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class OverlayCardStyle:
    """Explicit presentation-only card style for the shared shell.

    Content/background alpha, border alpha and shadow alpha are independent of
    one another and of the whole-widget fade opacity, so each ``QColor`` carries
    its own alpha channel. Shadow offsets are signed so E4 can later orient them
    without changing magnitude.
    """

    shell_enabled: bool = True
    background_color: QColor = field(
        default_factory=lambda: QColor(16, 16, 16, 179)
    )
    border_color: QColor = field(
        default_factory=lambda: QColor(255, 255, 255, 230)
    )
    border_width: float = 2.0
    corner_radius: float = 8.0
    padding: float = 8.0
    shadow_enabled: bool = True
    shadow_color: QColor = field(default_factory=lambda: QColor(0, 0, 0, 150))
    shadow_blur: float = 18.0
    shadow_offset_x: float = 0.0
    shadow_offset_y: float = 4.0
    shadow_spread: float = 0.0


_CARD_STYLE_BINDINGS: tuple[tuple[str, str], ...] = (
    ("cardShellEnabled", "shell_enabled"),
    ("cardBackgroundColor", "background_color"),
    ("cardBorderColor", "border_color"),
    ("cardBorderWidth", "border_width"),
    ("cardCornerRadius", "corner_radius"),
    ("cardPadding", "padding"),
    ("cardShadowEnabled", "shadow_enabled"),
    ("cardShadowColor", "shadow_color"),
    ("cardShadowBlur", "shadow_blur"),
    ("cardShadowOffsetX", "shadow_offset_x"),
    ("cardShadowOffsetY", "shadow_offset_y"),
    ("cardShadowSpread", "shadow_spread"),
)


class RetainedOverlayWidget:
    """One retained ``OverlayWidget`` root with explicit presentation setters."""

    def __init__(self, item: QQuickItem, *, model_identity: str | None = None) -> None:
        self._item: QQuickItem | None = item
        self._model_identity = str(model_identity or "").strip()
        self._host: OrdinaryWidgetPresentationHost | None = None
        self._retirement_callbacks: list[Callable[[], None]] = []
        self._custom_layout_size_payload_handler: Callable[
            [Mapping[str, object]], None
        ] | None = None
        self._input_state_handler: Callable[[object], bool] | None = None

    @property
    def item(self) -> QQuickItem:
        item = self._item
        if item is None:
            raise RuntimeError("retained overlay widget has retired")
        return item

    @property
    def is_retired(self) -> bool:
        return self._item is None

    @property
    def model_identity(self) -> str:
        return self._model_identity

    def set_geometry(self, geometry: OverlayWidgetGeometry) -> None:
        """Assign this widget's display-space rectangle."""

        item = self.item
        item.setX(float(geometry.x))
        item.setY(float(geometry.y))
        item.setWidth(float(geometry.width))
        item.setHeight(float(geometry.height))

    def set_fade_opacity(self, opacity: float) -> None:
        """Set the whole-widget authored fade (root opacity), clamped to [0, 1]."""

        clamped = max(0.0, min(1.0, float(opacity)))
        self.item.setProperty("fadeOpacity", clamped)

    def set_working_visible(self, visible: bool) -> None:
        """Apply transient CUSTOM visibility without rewriting authored fade."""

        self.item.setProperty("workingVisible", bool(visible))

    def set_card_style(self, style: OverlayCardStyle) -> None:
        """Apply one immutable card style record to the shared shell."""

        item = self.item
        for property_name, attribute in _CARD_STYLE_BINDINGS:
            item.setProperty(property_name, getattr(style, attribute))

    def set_custom_layout_size_payload_handler(
        self,
        handler: Callable[[Mapping[str, object]], None] | None,
    ) -> None:
        """Register a presentation-only family payload projector for CUSTOM preview."""

        self._custom_layout_size_payload_handler = handler

    def apply_custom_layout_size_payload(
        self,
        payload: Mapping[str, object],
    ) -> None:
        """Project Python-owned working size values onto the retained family model."""

        handler = self._custom_layout_size_payload_handler
        if handler is not None:
            handler(dict(payload))

    def add_retirement_callback(self, callback: Callable[[], None]) -> None:
        """Run ``callback`` exactly once before the retained item is detached."""

        if self._item is None:
            callback()
            return
        if callback not in self._retirement_callbacks:
            self._retirement_callbacks.append(callback)

    def _set_input_state_handler(
        self,
        handler: Callable[[object], bool] | None,
    ) -> None:
        self._input_state_handler = handler

    def _apply_input_state(self, input_state: object) -> bool:
        handler = self._input_state_handler
        return bool(handler is not None and handler(input_state))

    def retire(self) -> bool:
        """Retire through the host that currently owns this retained item."""

        host = self._host
        return bool(host is not None and host.retire_widget(self))

    def _retire(self) -> None:
        item = self._item
        self._item = None
        self._host = None
        callbacks = self._retirement_callbacks
        self._retirement_callbacks = []
        self._custom_layout_size_payload_handler = None
        self._input_state_handler = None
        for callback in callbacks:
            callback()
        if item is not None:
            # Detach from the scene graph before queuing deletion so retiring one
            # widget never depends on the display generation still being live.
            item.setParentItem(None)
            item.setParent(None)
            item.deleteLater()


class OrdinaryWidgetPresentationHost:
    """Creates/retires retained overlay widgets under one display's scene host."""

    def __init__(
        self,
        *,
        host_item: QQuickItem,
        context: QQmlContext,
        create_overlay_item: Callable[
            [Mapping[str, object], QQmlContext], QQuickItem
        ],
        create_family_item: Callable[
            [str, Mapping[str, object], QQmlContext], QQuickItem
        ]
        | None = None,
    ) -> None:
        self._host_item: QQuickItem | None = host_item
        self._context: QQmlContext | None = context
        self._create_overlay_item = create_overlay_item
        self._create_family_item = create_family_item
        self._live: list[RetainedOverlayWidget] = []
        self._by_model_identity: dict[str, RetainedOverlayWidget] = {}
        self._input_state: object | None = None
        self._retired = False

    @property
    def is_retired(self) -> bool:
        return self._retired

    @property
    def live_count(self) -> int:
        return len(self._live)

    def create_widget(
        self,
        *,
        object_name: str | None = None,
        model_identity: str | None = None,
        geometry: OverlayWidgetGeometry | None = None,
        fade_opacity: float | None = None,
        card_style: OverlayCardStyle | None = None,
    ) -> RetainedOverlayWidget:
        """Create one retained overlay widget under this display's host item."""

        if self._retired:
            raise RuntimeError("ordinary-widget presentation host has retired")
        host_item = self._host_item
        context = self._context
        if host_item is None or context is None:
            raise RuntimeError("ordinary-widget presentation host is incomplete")

        initial: dict[str, object] = {}
        if object_name is not None:
            initial["objectName"] = str(object_name)
        item = self._create_overlay_item(initial, context)
        return self._adopt_item(
            item,
            host_item=host_item,
            model_identity=model_identity,
            geometry=geometry,
            fade_opacity=fade_opacity,
            card_style=card_style,
        )

    def create_family_widget(
        self,
        family_id: str,
        *,
        initial_properties: Mapping[str, object] | None = None,
        object_name: str | None = None,
        model_identity: str | None = None,
        geometry: OverlayWidgetGeometry | None = None,
        fade_opacity: float | None = None,
        card_style: OverlayCardStyle | None = None,
    ) -> RetainedOverlayWidget:
        """Create one registered family component under this display host."""

        if self._retired:
            raise RuntimeError("ordinary-widget presentation host has retired")
        host_item = self._host_item
        context = self._context
        creator = self._create_family_item
        if host_item is None or context is None:
            raise RuntimeError("ordinary-widget presentation host is incomplete")
        if creator is None:
            raise RuntimeError("ordinary-widget family factory is unavailable")

        initial = dict(initial_properties or {})
        if object_name is not None:
            initial["objectName"] = str(object_name)
        item = creator(str(family_id), initial, context)
        return self._adopt_item(
            item,
            host_item=host_item,
            model_identity=model_identity,
            geometry=geometry,
            fade_opacity=fade_opacity,
            card_style=card_style,
        )

    def _adopt_item(
        self,
        item: QQuickItem,
        *,
        host_item: QQuickItem,
        model_identity: str | None,
        geometry: OverlayWidgetGeometry | None,
        fade_opacity: float | None,
        card_style: OverlayCardStyle | None,
    ) -> RetainedOverlayWidget:
        """Adopt one factory-created item into this display generation."""

        if not isinstance(item, QQuickItem):
            raise RuntimeError("overlay widget factory did not create a QQuickItem")
        item.setParentItem(host_item)
        item.setParent(host_item)

        normalized_identity = str(model_identity or "").strip()
        if normalized_identity and normalized_identity in self._by_model_identity:
            item.setParentItem(None)
            item.setParent(None)
            item.deleteLater()
            raise ValueError(
                f"duplicate retained model identity: {normalized_identity!r}"
            )
        widget = RetainedOverlayWidget(
            item,
            model_identity=normalized_identity or None,
        )
        widget._host = self
        self._live.append(widget)
        if normalized_identity:
            self._by_model_identity[normalized_identity] = widget
        if geometry is not None:
            widget.set_geometry(geometry)
        if fade_opacity is not None:
            widget.set_fade_opacity(fade_opacity)
        if card_style is not None:
            widget.set_card_style(card_style)
        return widget

    def presentation_for_model_identity(
        self,
        model_identity: str,
    ) -> RetainedOverlayWidget | None:
        return self._by_model_identity.get(str(model_identity or "").strip())

    def model_identities(self) -> tuple[str, ...]:
        return tuple(self._by_model_identity)

    def handles_semantic_double_click_at(self, scene_position: QPointF) -> bool:
        """Return whether the topmost retained item owns this double click."""

        point = QPointF(scene_position)
        for widget in reversed(self._live):
            item = widget.item
            if (
                not item.isVisible()
                or not item.isEnabled()
                or not bool(item.property("semanticDoubleClickEnabled"))
            ):
                continue
            if item.contains(item.mapFromScene(point)):
                return True
        return False

    def set_widget_input_state_handler(
        self,
        widget: RetainedOverlayWidget,
        handler: Callable[[object], bool] | None,
    ) -> None:
        """Register one family admission projector and seed current state."""

        if widget not in self._live:
            raise ValueError("input-state target is not owned by this host")
        widget._set_input_state_handler(handler)
        if handler is not None and self._input_state is not None:
            handler(self._input_state)

    def apply_input_state(self, input_state: object) -> bool:
        """Project one display-local input state onto all interactive families."""

        self._input_state = input_state
        changed = False
        for widget in tuple(self._live):
            changed = widget._apply_input_state(input_state) or changed
        return changed

    def retire_widget(self, widget: RetainedOverlayWidget) -> bool:
        """Retire one live widget mid-generation without retiring the host."""

        for index, live in enumerate(self._live):
            if live is widget:
                del self._live[index]
                if live.model_identity:
                    self._by_model_identity.pop(live.model_identity, None)
                live._retire()
                return True
        return False

    def transfer_widget_to(
        self,
        widget: RetainedOverlayWidget,
        target: "OrdinaryWidgetPresentationHost",
    ) -> bool:
        """Move one retained presentation to another live host without cloning it.

        The target becomes the presentation's scene/lifecycle host. The family
        model and any neutral runtime-service owner remain unchanged; CUSTOM
        Save rebuilds the generation on the newly persisted monitor route.
        """

        if target is self:
            return widget in self._live
        if self._retired or target._retired:
            raise RuntimeError("cannot transfer through a retired presentation host")
        if widget not in self._live or widget._host is not self:
            raise ValueError("ordinary presentation is not owned by the source host")
        source_item = self._host_item
        target_item = target._host_item
        if source_item is None:
            raise RuntimeError("source ordinary presentation host is incomplete")
        if target_item is None:
            raise RuntimeError("target ordinary presentation host is incomplete")
        identity = widget.model_identity
        if identity and identity in target._by_model_identity:
            raise ValueError(f"target already owns model identity: {identity!r}")

        item = widget.item
        if target._input_state is not None:
            widget._apply_input_state(target._input_state)
        try:
            item.setParentItem(target_item)
            item.setParent(target_item)
        except Exception:
            item.setParentItem(source_item)
            item.setParent(source_item)
            raise
        self._live.remove(widget)
        if identity:
            self._by_model_identity.pop(identity, None)
        target._live.append(widget)
        if identity:
            target._by_model_identity[identity] = widget
        widget._host = target
        return True

    def retire_all(self) -> None:
        """Terminally retire every live widget for this display generation."""

        live = self._live
        self._live = []
        self._by_model_identity = {}
        self._input_state = None
        self._retired = True
        self._host_item = None
        self._context = None
        self._create_family_item = None
        for widget in live:
            widget._retire()
