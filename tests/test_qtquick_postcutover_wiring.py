"""Focused post-cutover wiring regressions from the 2026-08-30 operator audit.

These tests intentionally target two composition facts that are broken on audited
pushed main ``4f33981e``. They are expected to be RED before the corresponding
source fixes land. They do not prescribe where the dependency is threaded; they
only assert the production retained presentation receives a usable destination
owner/action.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject
from PySide6.QtQuick import QQuickItem

from core.reddit_preparation import RedditPost
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.widgets.family_binder import (
    MediaFamilyAdapter,
    default_ordinary_family_adapters,
)
from rendering.quick.widgets.host import OrdinaryWidgetPresentationHost, OverlayWidgetGeometry


class _NoServiceRuntimeManager:
    """Keep these tests on presentation composition rather than provider lifetime."""

    @staticmethod
    def has_runtime_service(_widget_id: str) -> bool:
        return False

    @staticmethod
    def retire_widget_service(_widget_id: str) -> bool:
        return False


class _ProductUrlOpener:
    """Minimal semantic product opener used only to prove the family route exists."""

    def __init__(self) -> None:
        self.urls: list[str] = []

    def __call__(self, url: str) -> bool:
        self.urls.append(str(url))
        return True


def _host(factory: QuickSceneFactory, owner: QObject):
    context, root = factory.create_display_root(
        owner=owner,
        screen_index=0,
        runtime_generation=1701,
    )
    host_item = root.findChild(QQuickItem, "ordinaryWidgetHost")
    assert host_item is not None
    host = OrdinaryWidgetPresentationHost(
        host_item=host_item,
        context=context,
        create_overlay_item=factory.create_overlay_widget,
        create_family_item=factory.create_ordinary_widget_family,
    )
    return context, root, host


def _retire_fixture(context, root, host, owner, factory, qt_app) -> None:
    host.retire_all()
    root.setParentItem(None)
    root.setParent(None)
    root.deleteLater()
    context.deleteLater()
    owner.deleteLater()
    factory.deleteLater()
    qt_app.processEvents()


@pytest.mark.qt
def test_media_family_uses_the_qml_engines_registered_artwork_provider(qt_app) -> None:
    """``image://mediaartwork`` must publish into the provider registered on QQmlEngine.

    Audited main creates one provider in ``QuickSceneFactory`` and a second private
    provider in ``MediaFamilyAdapter``. A decoded image published into the private
    provider can therefore never be resolved by the QML engine. The exact
    dependency-threading mechanism is deliberately not asserted here; only owner
    identity is.
    """

    owner = QObject()
    factory = QuickSceneFactory(owner)
    context, root, host = _host(factory, owner)
    presentation = None
    try:
        adapter = MediaFamilyAdapter()
        presentation = adapter.build(
            widget_id="media",
            widgets_config={"media": {"enabled": True}},
            host=host,
            geometry=OverlayWidgetGeometry(20.0, 20.0, 600.0, 310.0),
            display_bounds=OverlayWidgetGeometry(0.0, 0.0, 1920.0, 1080.0),
            display_identity="audit-display",
            shadow_values={},
            runtime_manager=_NoServiceRuntimeManager(),
            runtime_generation=1701,
        )
        assert presentation is not None
        assert (
            presentation.model._artwork_provider is factory.media_artwork_provider
        ), "Media publishes artwork into a provider the QML engine does not own"
    finally:
        _retire_fixture(context, root, host, owner, factory, qt_app)


@pytest.mark.qt
def test_reddit_family_has_a_product_url_opener_and_routes_admitted_click(qt_app) -> None:
    """A retained Reddit click must leave the family through a real product action seam.

    ``RetainedRedditPresentation`` already owns URL admission and an
    ``on_open_requested`` callback seam. The bar exercises the exact production
    composition path — ``default_ordinary_family_adapters`` threading the
    destination-owner callback that ``DisplayManager`` supplies — rather than a
    bare adapter, because the adapter must NOT self-synthesize a URL launcher (a
    duplicate opener authority). It does not assert MC vs SCR implementation
    details; the injected callback remains responsible for choosing direct
    desktop open vs the established helper queue.
    """

    owner = QObject()
    factory = QuickSceneFactory(owner)
    context, root, host = _host(factory, owner)
    presentation = None
    fake_opener = _ProductUrlOpener()
    try:
        adapters = default_ordinary_family_adapters(
            reddit_open_requested=lambda _widget_id, url: fake_opener(url),
        )
        adapter = next(a for a in adapters if a.family_id == "reddit")
        presentation = adapter.build(
            widget_id="reddit",
            widgets_config={
                "reddit": {
                    "enabled": True,
                    "subreddit": "games",
                    "limit": 3,
                }
            },
            host=host,
            geometry=OverlayWidgetGeometry(20.0, 20.0, 640.0, 320.0),
            display_bounds=OverlayWidgetGeometry(0.0, 0.0, 1920.0, 1080.0),
            display_identity="audit-display",
            shadow_values={},
            runtime_manager=_NoServiceRuntimeManager(),
            runtime_generation=1701,
        )
        assert presentation is not None

        # Production composition must thread a usable product opener all the way
        # into the retained presentation. The adapter itself never fabricates one.
        opener = presentation._on_open_requested
        assert callable(opener), "Production Reddit family composition supplied no product URL opener"

        presentation.activate()
        presentation.apply_input_state(
            {
                "admission_open": True,
                "exiting": False,
                "interaction_mode_enabled": True,
                "ctrl_held": False,
            }
        )
        url = "https://www.reddit.com/r/games/comments/audit"
        presentation.model.publish_posts(
            (
                RedditPost(
                    title="Audit post",
                    url=url,
                    score=1,
                    created_utc=1.0,
                ),
            ),
            now_ts=2.0,
        )
        assert presentation._handle_open_requested(url) is True
        assert fake_opener.urls == [url]
    finally:
        _retire_fixture(context, root, host, owner, factory, qt_app)
