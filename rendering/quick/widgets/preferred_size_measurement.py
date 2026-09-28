"""On-demand ordinary-family preferred-size measurement for Settings Arrange.

The Quick runtime sizes every ordinary card from its family QML's
``preferredContentWidth/Height``; that is the one size authority. Settings
Arrange reads the same authority here instead of predicting sizes: the family
adapter's own ``presentation_model`` builds a detached model, the family's
registered component is instantiated in a private engine, given its preferred
size and laid out by Qt's own polish pass until both preferred properties
settle, and the item is then destroyed. Fonts, DPR and text metrics are this
machine's, exactly as the saver will see them.

The polish pass matters: Column/Row positioners size themselves only when
polished, which a window never shown does not do. A ``QQuickRenderControl``
runs that pass without any platform window, rendering or GL. A family whose
size follows its data (Weather) is measured in the state its data brings.

Nothing here attaches a runtime service, activates a model, shows a window or
owns a timer. A meter exists only while an Arrange editor does, so
Settings pays nothing unless Arrange is opened. Results are memoized per
size-relevant draft fingerprint: layout-only edits (moves, resets, CUSTOM
entries, slots, routes) reuse them and a real settings change re-measures once.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict
import json
from typing import Any

from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem, QQuickRenderControl, QQuickWindow
from core.logging.logger import get_logger
from core.settings.layout_slots import LAYOUT_SLOTS_SETTINGS_KEY
from rendering.custom_layout_contract import (
    CUSTOM_LAYOUT_RESTORE_SETTINGS_KEY,
    CUSTOM_LAYOUT_SETTINGS_KEY,
)

from .host import apply_overlay_card_style
from .registry import OrdinaryWidgetFamilyComponent, ordinary_widget_family_component

logger = get_logger(__name__)

# Layout converges in one or two passes; the bound only guards a family bug.
_SETTLE_PASSES = 6

# Keys that place a card without changing its content size.
_LAYOUT_ONLY_KEYS = frozenset(
    {CUSTOM_LAYOUT_SETTINGS_KEY, CUSTOM_LAYOUT_RESTORE_SETTINGS_KEY, LAYOUT_SLOTS_SETTINGS_KEY}
)
_PLACEMENT_FIELDS = frozenset({"position", "monitor", "margin"})


def size_fingerprint(widgets: Mapping[str, Any]) -> str:
    """Stable key of every widgets-map value that can change a preferred size."""

    projected = {
        key: (
            {field: value for field, value in section.items() if field not in _PLACEMENT_FIELDS}
            if isinstance(section, Mapping)
            else section
        )
        for key, section in widgets.items()
        if key not in _LAYOUT_ONLY_KEYS
    }
    return json.dumps(projected, sort_keys=True, default=str)


def ordinary_instance_order(
    widgets: Mapping[str, Any], adapters: Sequence[Any]
) -> tuple[str, ...]:
    """Enabled ordinary instances in the saver's build (and stacking) order.

    Family effectiveness and monitor routes stay with the caller, as in the
    display binder; this is only the adapters' own admission and order.
    """

    return tuple(
        widget_id
        for adapter in adapters
        for widget_id in adapter.enabled_instance_ids(widgets)
    )


class OrdinaryPreferredSizeMeter:
    """Measure ordinary widgets' preferred content sizes through their own QML."""

    def __init__(self, adapters: Sequence[Any] | None = None) -> None:
        if adapters is None:
            from .family_binder import default_ordinary_family_adapters

            adapters = default_ordinary_family_adapters()
        self.adapters: tuple[Any, ...] = tuple(adapters)
        self._engine: QQmlEngine | None = None
        # Polish only: this window is bound to a render control, never shown.
        self._render_control: QQuickRenderControl | None = None
        self._layout_window: QQuickWindow | None = None
        self._components: dict[str, QQmlComponent] = {}
        self._fingerprint: str | None = None
        self._memo: dict[tuple[str, str | None, str | None], tuple[float, float]] = {}

    def presents(self, widget_id: str) -> bool:
        """Whether an ordinary family (not the Visualizer) presents ``widget_id``."""

        return self._family_for(widget_id) is not None

    def _family_for(
        self, widget_id: str
    ) -> tuple[Any, OrdinaryWidgetFamilyComponent] | None:
        for adapter in self.adapters:
            component_id = adapter.presentation_component(widget_id)
            if component_id is not None:
                return adapter, ordinary_widget_family_component(component_id)
        return None

    def measure(
        self,
        widget_id: str,
        widgets: Mapping[str, Any],
        *,
        display_identity: str | None = None,
        size_payload: Mapping[str, Any] | None = None,
    ) -> tuple[float, float]:
        """Return the saver's ``(width, height)`` for one widget.

        ``display_identity`` matters only to families with per-display content
        (Clock's per-display face); pass it only for those. ``size_payload`` is a
        committed content-sized CUSTOM payload: a family whose content follows it
        (Clock's font) is measured as the saver presents that entry.
        """

        fingerprint = size_fingerprint(widgets)
        if fingerprint != self._fingerprint:
            self._fingerprint = fingerprint
            self._memo.clear()
        payload_key = json.dumps(dict(size_payload), sort_keys=True, default=str) if size_payload else None
        key = (str(widget_id), display_identity, payload_key)
        size = self._memo.get(key)
        if size is None:
            size = self._measure(str(widget_id), widgets, display_identity, size_payload)
            self._memo[key] = size
        return size

    def presentation_config(
        self,
        widget_id: str,
        widgets: Mapping[str, Any],
        *,
        display_identity: str | None = None,
    ) -> Any:
        """The family's resolved presentation config (plain Python, no QML)."""

        adapter, _descriptor = self._require_family(widget_id)
        return adapter.presentation_model(
            widget_id=widget_id,
            widgets_config=widgets,
            shadow_values=self._shadow_values(widgets),
            display_identity=display_identity,
        ).config

    def close(self) -> None:
        """Release the private engine; a later measure lazily recreates it."""

        self._components = {}
        engine, self._engine = self._engine, None
        window, self._layout_window = self._layout_window, None
        control, self._render_control = self._render_control, None
        if engine is not None:
            engine.deleteLater()
        if window is not None:
            window.deleteLater()
        if control is not None:
            control.deleteLater()
        self._fingerprint = None
        self._memo.clear()

    def _require_family(self, widget_id: str) -> tuple[Any, OrdinaryWidgetFamilyComponent]:
        family = self._family_for(widget_id)
        if family is None:
            raise KeyError(f"no ordinary family presents {widget_id!r}")
        return family

    @staticmethod
    def _shadow_values(widgets: Mapping[str, Any]) -> dict[str, Any]:
        from core.settings.models import ShadowSettings

        # The saver's shadow projection, read from the draft map.
        return asdict(ShadowSettings.from_widgets_map(widgets))

    def _measure(
        self,
        widget_id: str,
        widgets: Mapping[str, Any],
        display_identity: str | None,
        size_payload: Mapping[str, Any] | None = None,
    ) -> tuple[float, float]:
        adapter, descriptor = self._require_family(widget_id)
        model = adapter.presentation_model(
            widget_id=widget_id,
            widgets_config=widgets,
            shadow_values=self._shadow_values(widgets),
            display_identity=display_identity,
        )
        apply_payload = getattr(adapter, "apply_committed_size_payload", None)
        if size_payload and callable(apply_payload):
            apply_payload(model, size_payload)
        prepare = getattr(adapter, "prepare_measurement", None)
        if callable(prepare):
            prepare(model)
        component = self._component(descriptor)
        item = component.createWithInitialProperties({descriptor.model_property: model})
        if not isinstance(item, QQuickItem):
            details = "; ".join(error.toString() for error in component.errors())
            raise RuntimeError(f"{descriptor.qml_filename} did not create an item: {details}")
        # Qt owns the whole chain: component and item die with the engine at the
        # latest, the model with its item (after the item's bindings, as the
        # retained host arranges). A synchronous item delete corrupts later
        # engine teardown, so the item leaves through the event loop.
        QQmlEngine.setObjectOwnership(item, QQmlEngine.ObjectOwnership.CppOwnership)
        item.setParent(self._engine)
        model.setParent(item)
        try:
            # Card padding is part of the preferred size; the host applies the
            # family's card style the same way when it adopts the item.
            apply_overlay_card_style(item, adapter.presentation_card_style(model))
            item.setParentItem(self._layout_window.contentItem())
            width = height = 0.0
            for _ in range(_SETTLE_PASSES):
                # As the saver does: give the item its preferred size, lay it out.
                width = float(item.property("preferredContentWidth") or 0.0)
                height = float(item.property("preferredContentHeight") or 0.0)
                item.setWidth(width)
                item.setHeight(height)
                self._render_control.polishItems()
                if (float(item.property("preferredContentWidth") or 0.0), float(item.property("preferredContentHeight") or 0.0)) == (width, height):
                    break
            width = float(item.property("preferredContentWidth") or 0.0)
            height = float(item.property("preferredContentHeight") or 0.0)
        finally:
            item.setParentItem(None)
            item.deleteLater()
        if not (width > 0.0 and height > 0.0):
            raise RuntimeError(f"{widget_id} reported no preferred size ({width}x{height})")
        return width, height

    def _component(self, descriptor: OrdinaryWidgetFamilyComponent) -> QQmlComponent:
        component = self._components.get(descriptor.family_id)
        if component is not None:
            return component
        from rendering.quick.bootstrap import quick_qml_root

        if self._engine is None:
            from PySide6.QtGui import QGuiApplication

            from ui.font_registration import ensure_custom_fonts

            if QGuiApplication.instance() is None:
                # A QML engine without one aborts the whole process.
                raise RuntimeError("preferred-size measurement needs a QGuiApplication")

            # The saver registers its bundled fonts at startup; text metrics
            # must come from the same faces.
            ensure_custom_fonts()
            self._engine = QQmlEngine()
            self._engine.addImportPath(str(quick_qml_root()))
            self._render_control = QQuickRenderControl()
            self._layout_window = QQuickWindow(self._render_control)
        component = QQmlComponent(
            self._engine, QUrl.fromLocalFile(str(quick_qml_root() / descriptor.qml_filename))
        )
        component.setParent(self._engine)
        if component.status() != QQmlComponent.Status.Ready:
            details = "; ".join(error.toString() for error in component.errors())
            raise RuntimeError(f"{descriptor.qml_filename} failed to load: {details}")
        self._components[descriptor.family_id] = component
        return component


__all__ = [
    "OrdinaryPreferredSizeMeter",
    "ordinary_instance_order",
    "size_fingerprint",
]
