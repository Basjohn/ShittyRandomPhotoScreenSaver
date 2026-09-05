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

from PySide6.QtCore import QObject, QPointF
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
    shadow_extend_left: float = 0.0
    shadow_extend_top: float = 0.0
    shadow_extend_right: float = 0.0
    shadow_extend_bottom: float = 0.0


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
    ("cardShadowExtendLeft", "shadow_extend_left"),
    ("cardShadowExtendTop", "shadow_extend_top"),
    ("cardShadowExtendRight", "shadow_extend_right"),
    ("cardShadowExtendBottom", "shadow_extend_bottom"),
)


class RetainedOverlayWidget:
    """One retained ``OverlayWidget`` root with explicit presentation setters."""

    def __init__(
        self,
        item: QQuickItem,
        *,
        shadow_item: QQuickItem | None = None,
        model_identity: str | None = None,
    ) -> None:
        self._item: QQuickItem | None = item
        self._shadow_item: QQuickItem | None = shadow_item
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
    def shadow_item(self) -> QQuickItem | None:
        """Return the display-level shadow underlay, when production owns one."""

        return self._shadow_item

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

    def set_startup_reveal_opacity(self, opacity: float) -> None:
        """Set the independent generation-scoped startup visibility gate."""

        clamped = max(0.0, min(1.0, float(opacity)))
        self.item.setProperty("startupRevealOpacity", clamped)

    def set_working_visible(self, visible: bool) -> None:
        """Apply transient CUSTOM visibility without rewriting authored fade."""

        self.item.setProperty("workingVisible", bool(visible))

    def set_card_style(self, style: OverlayCardStyle) -> None:
        """Apply one immutable card style record to the shared shell."""

        item = self.item
        for property_name, attribute in _CARD_STYLE_BINDINGS:
            if not item.setProperty(property_name, getattr(style, attribute)):
                raise RuntimeError(
                    f"OverlayWidget.qml rejected card style property {property_name}"
                )

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
        from rendering.quick.state import QuickInputState

        # Shared visual feedback is independent of family semantic actions.
        # Only the canonical immutable input snapshot can admit it.
        if isinstance(input_state, QuickInputState) and self._item is not None:
            admitted = bool(
                input_state.admission_open
                and not input_state.exiting
                and not input_state.context_menu_active
                and (input_state.interaction_mode_enabled or input_state.ctrl_held)
            )
            item = self._item
            item.setProperty("widgetGlowOnHover", input_state.widget_glow_on_hover)
            item.setProperty("widgetGlowOnClick", input_state.widget_glow_on_click)
            item.setProperty("widgetGlowIntensity", input_state.widget_glow_intensity)
            item.setProperty("widgetGlowColor", QColor(*input_state.widget_glow_color))
            item.setProperty("widgetGlowAdmitted", admitted)
            if not admitted or not input_state.widget_glow_on_click:
                item.setProperty("widgetGlowClicked", False)
        handler = self._input_state_handler
        return bool(handler is not None and handler(input_state))

    def retire(self) -> bool:
        """Retire through the host that currently owns this retained item."""

        host = self._host
        return bool(host is not None and host.retire_widget(self))

    def _retire(self) -> None:
        item = self._item
        shadow_item = self._shadow_item
        self._item = None
        self._shadow_item = None
        self._host = None
        callbacks = self._retirement_callbacks
        self._retirement_callbacks = []
        self._custom_layout_size_payload_handler = None
        self._input_state_handler = None
        for callback in callbacks:
            callback()
        if shadow_item is not None:
            # The underlay references the widget for geometry/style bindings;
            # detach and retire it first so no binding can outlive its source.
            shadow_item.setProperty("sourceWidget", None)
            shadow_item.setParentItem(None)
            shadow_item.setParent(None)
            shadow_item.deleteLater()
        if item is not None:
            item.setProperty("widgetGlowAdmitted", False)
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
        shadow_host_item: QQuickItem | None = None,
        create_shadow_item: Callable[
            [Mapping[str, object], QQmlContext], QQuickItem
        ]
        | None = None,
        create_family_item: Callable[
            [str, Mapping[str, object], QQmlContext], QQuickItem
        ]
        | None = None,
    ) -> None:
        self._host_item: QQuickItem | None = host_item
        self._shadow_host_item: QQuickItem | None = shadow_host_item
        self._context: QQmlContext | None = context
        self._create_overlay_item = create_overlay_item
        self._create_shadow_item = create_shadow_item
        self._create_family_item = create_family_item
        if (shadow_host_item is None) != (create_shadow_item is None):
            raise RuntimeError(
                "ordinary-widget shadow underlay requires both host and factory"
            )
        self._live: list[RetainedOverlayWidget] = []
        self._by_model_identity: dict[str, RetainedOverlayWidget] = {}
        self._input_state: object | None = None
        # Generation-scoped presentation state.  Remembering this at the host
        # boundary guarantees a family root created after startup priming joins
        # the scene already closed/current, rather than flashing at QML's 1.0
        # default until the coordinator's next animation value arrives.
        self._startup_reveal_opacity = 1.0
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
        # Bind any *parentless* QObject model passed as an initial property
        # (e.g. clockModel) to the item's lifetime. The item is retired with
        # deleteLater() — its real destruction is deferred to a later event-loop
        # turn — while a Python-owned parentless model is deleted synchronously
        # the moment its Python owner drops. That left the still-live item's
        # bindings to re-evaluate against a now-null model during retirement (the
        # Clock `Cannot read property '...' of null` storm). Parenting the model
        # to the item makes it outlive the item's binding teardown and die with
        # the item, after those bindings are gone. Models that already have a
        # parent (e.g. a generation-scoped window that also carries the runtime
        # generation their neutral service reads) are left untouched.
        if isinstance(item, QQuickItem):
            for value in initial.values():
                if (
                    isinstance(value, QObject)
                    and value is not item
                    and value.parent() is None
                ):
                    try:
                        value.setParent(item)
                    except (RuntimeError, TypeError):
                        pass
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
        # Stamp both visibility authorities before the item joins the scene.
        # The generation startup gate closes cold/replacement admission, while
        # an explicit family-authored initial fade (Steam starts at 0) must also
        # be installed before parenting so no retained root can spend even one
        # synchronized frame at OverlayWidget.qml's default opacity of 1.0.
        if not item.setProperty(
            "startupRevealOpacity", float(self._startup_reveal_opacity)
        ):
            item.deleteLater()
            raise RuntimeError(
                "OverlayWidget.qml rejected startupRevealOpacity projection"
            )
        if fade_opacity is not None:
            initial_fade = max(0.0, min(1.0, float(fade_opacity)))
            if not item.setProperty("fadeOpacity", initial_fade):
                item.deleteLater()
                raise RuntimeError("OverlayWidget.qml rejected fadeOpacity projection")
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
        shadow_item: QQuickItem | None = None
        shadow_host_item = self._shadow_host_item
        shadow_creator = self._create_shadow_item
        if shadow_host_item is not None and shadow_creator is not None:
            try:
                shadow_item = shadow_creator(
                    {"sourceWidget": item},
                    self._context,
                )
                if not isinstance(shadow_item, QQuickItem):
                    raise RuntimeError(
                        "ordinary-widget shadow factory did not create a QQuickItem"
                    )
                shadow_item.setParentItem(shadow_host_item)
                shadow_item.setParent(shadow_host_item)
                if not item.setProperty("externalCardShadow", True):
                    raise RuntimeError(
                        "OverlayWidget.qml rejected externalCardShadow projection"
                    )
            except Exception:
                if shadow_item is not None:
                    shadow_item.setParentItem(None)
                    shadow_item.setParent(None)
                    shadow_item.deleteLater()
                item.setParentItem(None)
                item.setParent(None)
                item.deleteLater()
                raise

        widget = RetainedOverlayWidget(
            item,
            shadow_item=shadow_item,
            model_identity=normalized_identity or None,
        )
        if geometry is not None:
            widget.set_geometry(geometry)
        if card_style is not None:
            widget.set_card_style(card_style)
        widget._host = self
        if self._input_state is not None:
            widget._apply_input_state(self._input_state)
        self._live.append(widget)
        if normalized_identity:
            self._by_model_identity[normalized_identity] = widget
        # ``fade_opacity`` was deliberately projected before scene admission
        # above. Later lifecycle changes continue through RetainedOverlayWidget.
        return widget

    def registered_image_provider(self, provider_id: str):
        """Return the image provider registered on this host's QML engine.

        Retained families that publish images by URL (e.g. Media artwork ->
        ``image://mediaartwork/<id>``) must publish into the *same* provider
        instance the engine resolves those URLs against — the one the scene
        factory registered — not a private duplicate. Returns ``None`` when the
        engine or provider is unavailable so callers can fail closed.
        """

        context = self._context
        if context is None:
            return None
        try:
            engine = context.engine()
        except (RuntimeError, AttributeError):
            return None
        if engine is None:
            return None
        try:
            return engine.imageProvider(str(provider_id))
        except (RuntimeError, TypeError):
            return None

    def presentation_for_model_identity(
        self,
        model_identity: str,
    ) -> RetainedOverlayWidget | None:
        return self._by_model_identity.get(str(model_identity or "").strip())

    def set_startup_reveal_opacity(self, opacity: float) -> tuple[str, ...]:
        """Store/project the generation startup gate for current and future roots."""

        if self._retired:
            return ()
        clamped = max(0.0, min(1.0, float(opacity)))
        self._startup_reveal_opacity = clamped
        changed: list[str] = []
        for widget in tuple(self._live):
            try:
                widget.set_startup_reveal_opacity(clamped)
            except (RuntimeError, TypeError, ValueError):
                continue
            if widget.model_identity:
                changed.append(widget.model_identity)
        return tuple(changed)

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

        if self._retired:
            return False
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

    def set_widget_glow_click_target_at(
        self, input_state: object, scene_position: QPointF
    ) -> bool:
        """Select the last-clicked ordinary card from one discrete input edge.

        Click glow is state, not a self-decaying pulse. The top visible hit card
        becomes the sole selected target until another admitted press selects a
        different card or empty space clears the target. No timer/poller is
        introduced; QML only animates when this boolean state changes.
        """

        if self._retired or input_state != self._input_state:
            return False
        target: RetainedOverlayWidget | None = None
        # Match retained sibling stacking: higher z first, later child on ties.
        for widget in sorted(
            reversed(self._live), key=lambda w: w.item.z(), reverse=True
        ):
            item = widget.item
            if not item.isVisible() or not item.isEnabled():
                continue
            if not item.contains(item.mapFromScene(scene_position)):
                continue
            if item.property("widgetGlowAdmitted") and item.property("widgetGlowOnClick"):
                target = widget
            break

        changed = False
        for widget in tuple(self._live):
            item = widget.item
            selected = widget is target
            if bool(item.property("widgetGlowClicked")) == selected:
                continue
            item.setProperty("widgetGlowClicked", selected)
            changed = True
        return changed

    def clear_widget_glow_click_target(self, input_state: object) -> bool:
        """Clear ordinary click selection from the same admitted press state."""

        if self._retired or input_state != self._input_state:
            return False
        changed = False
        for widget in tuple(self._live):
            item = widget.item
            if not bool(item.property("widgetGlowClicked")):
                continue
            item.setProperty("widgetGlowClicked", False)
            changed = True
        return changed

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
        shadow_item = widget.shadow_item
        source_shadow_host = self._shadow_host_item
        target_shadow_host = target._shadow_host_item
        if (source_shadow_host is None) != (target_shadow_host is None):
            raise RuntimeError(
                "cannot transfer between incompatible ordinary shadow topologies"
            )
        if shadow_item is not None and (
            source_shadow_host is None or target_shadow_host is None
        ):
            raise RuntimeError("retained ordinary shadow has no transfer host")
        item.setProperty("widgetGlowAdmitted", False)
        if target._input_state is not None:
            widget._apply_input_state(target._input_state)
        try:
            item.setParentItem(target_item)
            item.setParent(target_item)
            if shadow_item is not None and target_shadow_host is not None:
                shadow_item.setParentItem(target_shadow_host)
                shadow_item.setParent(target_shadow_host)
        except Exception:
            item.setParentItem(source_item)
            item.setParent(source_item)
            if shadow_item is not None and source_shadow_host is not None:
                shadow_item.setParentItem(source_shadow_host)
                shadow_item.setParent(source_shadow_host)
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
        for widget in live:
            widget._retire()
        self._host_item = None
        self._shadow_host_item = None
        self._context = None
        self._create_overlay_item = None
        self._create_shadow_item = None
        self._create_family_item = None
