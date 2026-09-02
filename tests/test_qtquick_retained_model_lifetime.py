"""Retained family model lifetime is bound to its QML item (H1b §F).

The Clock retirement storm (`ClockAnalogueFace.qml: TypeError: Cannot read
property '...' of null`) was an ownership-order defect: the retained item is
retired with `deleteLater()` (deferred), while a Python-owned parentless model
(e.g. `clockModel`) is destroyed synchronously the instant its Python owner
drops. The still-live item's bindings then re-evaluated against a null model.

`OrdinaryWidgetPresentationHost.create_family_widget` now parents any QObject
model passed as an initial property to the item, so the model outlives the
item's binding teardown and is destroyed together with the item. This bar pins
that ownership: dropping the external model reference must not invalidate the
model while the item is alive, and retiring the item destroys both.
"""
from __future__ import annotations

import gc

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem

import shiboken6


# Minimal family item that declares the visibility authorities the host stamps
# (startupRevealOpacity, fadeOpacity) before scene admission, so a bare QQuickItem
# dynamic property does not make the host's real projection check fail.
_FAMILY_ITEM_QML = (
    b"import QtQuick\n"
    b"Item {\n"
    b"    property real startupRevealOpacity: 1.0\n"
    b"    property real fadeOpacity: 1.0\n"
    b"    property bool externalCardShadow: false\n"
    b"}\n"
)

from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.widgets.host import (
    OrdinaryWidgetPresentationHost,
    OverlayWidgetGeometry,
)


def _make_host(qt_app):
    owner = QObject()
    factory = QuickSceneFactory()
    context, root = factory.create_display_root(
        owner=owner,
        screen_index=0,
        runtime_generation=41,
    )
    host_item = root.findChild(QQuickItem, "ordinaryWidgetHost")
    assert host_item is not None

    created: list[QQuickItem] = []

    def _create_family_item(family_id, initial, ctx) -> QQuickItem:
        # Parent the component to the long-lived owner so it is not GC'd at
        # return (which would take the item it created with it).
        component = QQmlComponent(ctx.engine(), owner)
        component.setData(_FAMILY_ITEM_QML, QUrl())
        item = component.create(ctx)
        assert isinstance(item, QQuickItem), component.errorString()
        # The real factory hands the host C++-owned items; without this the
        # engine's JS GC can delete this item the moment Python drops its ref.
        QQmlEngine.setObjectOwnership(item, QQmlEngine.ObjectOwnership.CppOwnership)
        for key, value in initial.items():
            item.setProperty(str(key), value)
        created.append(item)
        return item

    host = OrdinaryWidgetPresentationHost(
        host_item=host_item,
        context=context,
        create_overlay_item=factory.create_overlay_widget,
        create_family_item=_create_family_item,
    )
    # Keep owner/root/factory alive for the test's duration.
    return host, owner, root, factory


def test_family_model_is_parented_to_item_and_outlives_dropped_python_ref(qt_app) -> None:
    host, _owner, _root, _factory = _make_host(qt_app)

    model = QObject()
    widget = host.create_family_widget(
        "clocks",
        initial_properties={"clockModel": model},
        object_name="clock",
        model_identity="clock",
        geometry=OverlayWidgetGeometry(120.0, 80.0, 300.0, 200.0),
    )
    item = widget.item

    # The model's lifetime is bound to the item: it cannot be deleted first.
    assert model.parent() is item

    # Drop the only external strong Python reference. Because the item now owns
    # the model (C++ parent), the model must remain valid while the item lives —
    # this is exactly what prevents the retirement-time null-model bindings.
    del model
    gc.collect()
    qt_app.processEvents()

    recovered = item.property("clockModel")
    assert recovered is not None
    assert shiboken6.isValid(recovered)
    assert shiboken6.isValid(item)


def test_retiring_item_destroys_both_item_and_bound_model(qt_app) -> None:
    host, _owner, _root, _factory = _make_host(qt_app)

    model = QObject()
    widget = host.create_family_widget(
        "clocks",
        initial_properties={"clockModel": model},
        object_name="clock",
        model_identity="clock",
    )
    item = widget.item
    assert model.parent() is item

    assert widget.retire() is True
    # deleteLater() posts a DeferredDelete event; flush it explicitly (plain
    # processEvents does not drain DeferredDelete at the top event-loop level).
    qt_app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qt_app.processEvents()
    gc.collect()

    assert not shiboken6.isValid(item)
    # The model was a child of the item, so it is destroyed with it.
    assert not shiboken6.isValid(model)


def test_non_qobject_initial_properties_are_untouched(qt_app) -> None:
    host, _owner, _root, _factory = _make_host(qt_app)

    # objectName is a plain string initial property; parenting logic must ignore
    # non-QObject values and still build the widget.
    widget = host.create_family_widget(
        "clocks",
        initial_properties={"someScalar": 7},
        object_name="clock",
        model_identity="clock",
    )
    assert widget.item.property("someScalar") == 7
