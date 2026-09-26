"""Retained Reddit/Reddit2 child Save -> committed read -> fresh family scene.

The production CUSTOM writer and committed reader supply the persisted state;
the real family model/QML and selected Edit mapper must consume the same child
records after retirement and reconstruction.  This is NOT a synthetic target
standing in for the family, a GPU-pixel test, or a full settings/app restart.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtQuick import QQuickItem, QQuickWindow
from shiboken6 import isValid as is_valid_qobject

from core.settings.default_contract import require_canonical_default
from core.reddit_preparation import RedditPost
from rendering.custom_child_geometry import (
    CustomChildSize, normalize_child_geometry, update_child_geometry_payload,
)
from rendering.custom_layout_contract import load_custom_layout_map, write_custom_layout_map
from rendering.custom_layout_session import CustomLayoutKey, CustomLayoutSession, CustomLayoutSessionItem
from rendering.quick.custom_layout_hydration import resolve_quick_committed_variant_state
from rendering.quick.custom_layout_overlay import RetainedCustomLayoutOverlay
from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner, _DisplayBinding
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.widgets.host import OrdinaryWidgetPresentationHost, OverlayWidgetGeometry
from rendering.quick.widgets.reddit import (
    RedditPresentationConfig, RedditPresentationModel, RedditPresentationStyle,
    RetainedRedditPresentation,
)
from rendering.widget_descriptors import get_widget_runtime_descriptor


def _walk(root: QQuickItem):
    yield root
    for child in root.childItems():
        yield from _walk(child)


def _one(root: QQuickItem, name: str) -> QQuickItem:
    found = [item for item in _walk(root) if item.objectName() == name]
    assert len(found) == 1, (name, len(found))
    return found[0]


def _mapped_rect(item: QQuickItem, frame: QQuickItem) -> tuple[float, float, float, float]:
    corners = [item.mapToItem(frame, x, y) for x, y in (
        (0.0, 0.0), (item.width(), 0.0),
        (0.0, item.height()), (item.width(), item.height()),
    )]
    left = min(point.x() for point in corners)
    top = min(point.y() for point in corners)
    return left, top, max(point.x() for point in corners) - left, max(point.y() for point in corners) - top


def _presentation(host: OrdinaryWidgetPresentationHost, family: str, rect: QRect):
    config = RedditPresentationConfig.from_mapping({
        "subreddit": "wallpapers", "limit": 3, "font_family": "Inter",
        "font_size": 18, "show_background": True,
        "show_refresh_spiral": True,
    }, widget_id=family)
    # The retained style projector requires the complete resolved shadow contract.
    # Use the canonical settings snapshot rather than an incomplete test shorthand.
    shadows = require_canonical_default("widgets.shadows")
    shadows.update(enabled=False, text_enabled=False, header_enabled=False)
    style = RedditPresentationStyle.project(config, shadows)
    model = RedditPresentationModel(config, style)
    model.publish_posts((RedditPost(
        title="Example timestamp post", url="https://reddit.com/r/test/comments/example",
        score=3, created_utc=16400.0,
    ),), from_cache=True, now_ts=20000.0)
    presentation = RetainedRedditPresentation(
        host=host, model=model,
        geometry=OverlayWidgetGeometry(*map(float, rect.getRect())),
    )
    return presentation


@pytest.mark.qt
@pytest.mark.parametrize("family", ("reddit", "reddit2"))
def test_committed_child_header_and_refresh_reopen_in_real_retained_family_and_edit_proxy(
    qt_app, family: str,
) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    display = screen.geometry()
    width = min(650, max(180, display.width() - 45))
    height = min(315, max(100, display.height() - 45))
    rect = QRect(display.x() + 20, display.y() + 15, width, height)
    descriptor = get_widget_runtime_descriptor(family)
    assert descriptor is not None
    roles = descriptor.custom_child_roles
    assert {"header", "refresh"} <= {role.role_id for role in roles}
    sizes = normalize_child_geometry({
        "header": {"width_scale": 0.90, "alignment": "right", "x_offset": 0.02},
        "refresh": {"width_scale": 1.20, "x_offset": -0.02},
    }, roles)
    payload = update_child_geometry_payload({}, roles, sizes)
    item = CustomLayoutSessionItem(
        source_key=CustomLayoutKey(family, "display:reopen"),
        model_identity=family, baseline_global_rect=rect, current_global_rect=rect,
        baseline_size_payload=payload, current_size_payload=payload,
        baseline_enabled=True, current_enabled=True, custom_child_roles=roles,
        baseline_child_sizes=dict(sizes), current_child_sizes=dict(sizes),
    )
    owner = QuickCustomLayoutOwner(
        settings_manager=SimpleNamespace(), participants_provider=lambda: (),
        visualizer_provider=lambda: (None, None), reload_request=lambda _reason: None,
    )
    owner._bindings = {"display:reopen": _DisplayBinding(
        identity="display:reopen", monitor_route="1", unit=SimpleNamespace(),
        screen=screen, geometry=QRect(display),
    )}
    owner._descriptors = {item.source_key: descriptor}
    widgets = {family: {"enabled": True, "position": "Custom", "monitor": "1"}}
    custom = load_custom_layout_map(widgets)
    owner._write_item(widgets, custom, item, descriptor, "1")
    write_custom_layout_map(widgets, custom)
    persisted = deepcopy(widgets)
    resolved = resolve_quick_committed_variant_state(
        widgets, screen, family, geometry_variant="default",
    )
    assert resolved is not None
    geometry, restored_payload = resolved
    assert restored_payload["child_geometry"] == payload["child_geometry"]
    assert widgets == persisted, "Committed read must not write Settings"

    factory = QuickSceneFactory()
    window = QQuickWindow()
    context = None
    root = None
    host = None
    overlay = None
    try:
        window.setGeometry(0, 0, display.width(), display.height())
        context, root = factory.create_display_root(
            owner=window, screen_index=0, runtime_generation=2195,
        )
        root.setParent(window.contentItem())
        root.setParentItem(window.contentItem())
        root.setWidth(float(display.width()))
        root.setHeight(float(display.height()))
        host = OrdinaryWidgetPresentationHost(
            host_item=_one(root, "ordinaryWidgetHost"),
            shadow_host_item=_one(root, "ordinaryWidgetShadowHost"),
            context=context, create_overlay_item=factory.create_overlay_widget,
            create_family_item=factory.create_ordinary_widget_family,
            create_shadow_item=factory.create_overlay_card_shadow,
        )
        # Start with default child settings. Retire the real family item, then
        # construct a replacement from committed rect and payload rather than
        # reusing the same QML item or presentation model. The host stays live.
        initial = _presentation(host, family, rect)
        original_root = initial.item
        assert _one(original_root, "redditHeaderFrame") is not None
        assert host.retire_widget(initial._retained)
        qt_app.processEvents()
        assert initial._retained.is_retired

        local = QRect(
            round(geometry.x), round(geometry.y),
            round(geometry.width), round(geometry.height),
        )
        reopened = _presentation(host, family, local)
        reopened._retained.apply_custom_layout_size_payload(restored_payload)
        window.show()
        qt_app.processEvents()
        assert reopened.item is not original_root
        assert reopened.model.customChildGeometry == restored_payload["child_geometry"]
        header = _one(reopened.item, "redditHeaderFrame")
        refresh = _one(reopened.item, "redditRefreshTarget")
        # redditHeaderFrame names BrandedHeader's *inner* painted Rectangle,
        # whose local scale is correctly 1.0.  The saved child scale belongs to
        # the enclosing brandedHeader QQuickItem (the actual Edit role target).
        # Check that scale AND the inner frame's transformed painted footprint,
        # rather than testing a local scale property on the wrong item.
        branded_header = header.parentItem()
        assert branded_header is not None
        assert branded_header.objectName() == "brandedHeader"
        assert branded_header.scale() == pytest.approx(0.90)
        header_area = _one(reopened.item, "redditHeaderArea")
        mapped_header = _mapped_rect(header, header_area)
        assert mapped_header[2:] == pytest.approx(
            (header.width() * 0.90, header.height() * 0.90), abs=0.03,
        )
        assert bool(branded_header.property("contentReversed")), "saved right-aligned header must remain flipped"
        # The saved offset and flipped, right-edge placement must reach paint.
        assert mapped_header[0] == pytest.approx(
            header_area.width() - header.width() * 0.90
            + 0.02 * float(reopened.item.property("childNormalizationWidth")),
            abs=0.03,
        )
        assert refresh.width() == pytest.approx(
            float(refresh.property("implicitWidth")) * 1.20, abs=0.03,
        )
        age_rail = _one(reopened.item, "redditPostAge_0")
        age_value = _one(reopened.item, "redditPostAgeValue_0")
        age_ago = _one(reopened.item, "redditPostAgeAgo_0")
        assert age_value.property("text") == "01HR"
        assert age_ago.property("text") == "AGO"
        assert age_rail.width() == pytest.approx(
            age_value.width() + 2.0 + age_ago.width(), abs=0.02,
        )
        assert age_ago.x() - age_value.width() == pytest.approx(2.0, abs=0.02)
        # The 01HR/AGO compact rail is independent of the title clearance.
        # In flipped layout the title ends exactly the root-level titleAgeGap
        # before the age rail (the same gap is used unflipped). That gap is at
        # least 8 logical pixels and grows as the card scales down, so the
        # painted clearance never shrinks below ~9 device pixels.
        post_title = _one(reopened.item, "redditPostTitle_0")
        title_age_gap = float(reopened.item.property("titleAgeGap"))
        assert title_age_gap >= 8.0
        assert age_rail.x() - (post_title.x() + post_title.width()) == pytest.approx(
            title_age_gap, abs=0.03,
        )
        assert reopened.item.x() == pytest.approx(geometry.x, abs=1.0)
        assert reopened.item.y() == pytest.approx(geometry.y, abs=1.0)

        session = CustomLayoutSession()
        session.add_item(CustomLayoutSessionItem(
            source_key=CustomLayoutKey(family, "display:reopen"),
            model_identity=family, baseline_global_rect=QRect(local),
            current_global_rect=QRect(local),
            baseline_size_payload=restored_payload,
            current_size_payload=restored_payload,
            baseline_enabled=True, current_enabled=True,
            custom_child_roles=roles,
            baseline_child_sizes=dict(sizes), current_child_sizes=dict(sizes),
        ))
        edit_root = _one(root, "customLayoutOverlay")
        overlay = RetainedCustomLayoutOverlay(edit_root)
        overlay.bind_session(
            session, display_identity="display:reopen", display_origin=QPoint(0, 0),
            presentation_item_resolver=lambda _item: reopened.item,
        )
        assert overlay.model.selectItem(0)
        qt_app.processEvents()
        frame = _one(edit_root, f"customLayoutEditFrame-{family}")
        assert frame.setProperty("childEditingLocked", False)
        qt_app.processEvents()
        for role_id, target in (("header", header), ("refresh", refresh)):
            role = _one(edit_root, f"customLayoutChildRole-{family}-{role_id}")
            assert role.property("targetReady") is True
            assert (role.x(), role.y(), role.width(), role.height()) == pytest.approx(
                _mapped_rect(target, frame), abs=0.03,
            )
        overlay.clear_session()
        qt_app.processEvents()
        assert header.isVisible() and refresh.isVisible()
        assert not any(
            child.objectName().startswith(f"customLayoutChildRole-{family}-")
            for child in _walk(edit_root)
        )
        assert widgets == persisted, "Reopening and Edit mapping must not rewrite Settings"
    finally:
        if overlay is not None:
            overlay.clear_session()
        window.hide()
        if host is not None:
            host.retire_all()
        if root is not None:
            root.setParentItem(None)
            root.setParent(None)
            root.deleteLater()
        if context is not None:
            context.deleteLater()
        factory.deleteLater()
        window.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
@pytest.mark.parametrize("family", ("reddit", "reddit2"))
def test_owner_save_live_promotion_and_fresh_reddit_generation_preserves_painted_children(
    qt_app, family: str,
) -> None:
    """Use the real CUSTOM owner Save and real Quick display generations.

    The offline adapter substitutes only the external Reddit provider. Both
    generations still use the production family, presenter, committed-geometry
    resolver, persistence writer, payload hydration, and retained QML item.
    """
    from rendering.quick.ctrl_coordinator import SharedCtrlCoordinator
    from rendering.quick.custom_layout_hydration import (
        apply_quick_committed_payloads, resolve_quick_committed_geometry,
    )
    from rendering.quick.display_unit import create_quick_display_unit
    from rendering.quick.state import QuickWindowPolicy
    from rendering.quick.widgets.family_binder import RedditFamilyAdapter

    class _OfflineRedditAdapter(RedditFamilyAdapter):
        def enabled_instance_ids(self, widgets_config):
            section = widgets_config.get(family, {})
            return (family,) if section.get("enabled", False) else ()

        def build(self, *, widget_id, host, geometry, **_kwargs):
            # Keep the real retained Reddit model/QML, replacing only the
            # provider-backed builder with the already-proven offline builder.
            return _presentation(
                host, widget_id,
                QRect(round(geometry.x), round(geometry.y),
                      round(geometry.width), round(geometry.height)),
            )

    class _Settings:
        def __init__(self, widgets):
            self.widgets = deepcopy(widgets)
            self.save_calls = 0

        def get_widgets_map(self):
            return deepcopy(self.widgets)

        def set_widgets_map(self, widgets, *, emit_change=True):
            self.widgets = deepcopy(widgets)

        def save(self):
            self.save_calls += 1

    # Production RUN keeps QApplication alive across its last-window-closed
    # replacement barrier; test the same policy rather than Qt's default
    # top-level-window-count exit policy.
    previous_quit_on_last_window = qt_app.quitOnLastWindowClosed()
    qt_app.setQuitOnLastWindowClosed(False)
    screen = qt_app.primaryScreen()
    assert screen is not None and is_valid_qobject(screen)
    initial_widgets = {
        "family_activation": {"reddit": True},
        family: {"enabled": True, "position": "Top Left", "monitor": "ALL",
                 "subreddit": "wallpapers", "font_size": 18, "limit": 3},
    }
    settings = _Settings(initial_widgets)
    reloads: list[str] = []
    owners = []
    generations = []
    factories = []

    def new_generation(config, generation):
        # A QScreen is Qt/application-owned, never owned by a retired runtime.
        # Resolve it for each new generation instead of carrying a wrapper
        # across the old QQuickWindow's asynchronous teardown.
        live_screen = qt_app.primaryScreen()
        assert live_screen is not None and is_valid_qobject(live_screen), (
            "QApplication lost its physical screen while replacing a Qt Quick "
            "display; inspect screen ownership/teardown, not the widget payload"
        )
        factory = QuickSceneFactory()
        unit = create_quick_display_unit(
            screen=live_screen, screen_index=0, runtime_generation=generation,
            scene_factory=factory,
            window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
            ctrl_coordinator=SharedCtrlCoordinator(),
            adapters=(_OfflineRedditAdapter(),),
        )
        factories.append(factory)
        generations.append(unit)
        unit.bind_families(
            widgets_config=config,
            shadow_values=require_canonical_default("widgets.shadows"),
            committed_rect_resolver=lambda widget_id: resolve_quick_committed_geometry(
                config, live_screen, widget_id,
            ),
        )
        apply_quick_committed_payloads(unit, config)
        result = unit.presenter.presentation_for_widget_id(family)
        assert result is not None
        return unit, result

    try:
        unit, initial = new_generation(settings.widgets, 2197)
        initial_root = initial.item
        owner = QuickCustomLayoutOwner(
            settings_manager=settings, participants_provider=lambda: (unit,),
            visualizer_provider=lambda: (None, None), reload_request=reloads.append,
            live_config_commit=lambda _widgets: None,
        )
        owners.append(owner)
        assert owner.start()
        session = owner.session
        assert session is not None
        item = next(value for value in session.items() if value.model_identity == family)
        roles = get_widget_runtime_descriptor(family).custom_child_roles
        sizes = normalize_child_geometry({
            "header": {"width_scale": 0.90, "alignment": "right", "x_offset": 0.02},
            "refresh": {"width_scale": 1.20, "x_offset": -0.02},
        }, roles)
        payload = update_child_geometry_payload(item.current_size_payload, roles, sizes)
        item.current_child_sizes = dict(sizes)
        # Persist a parent movement as well as child edits: a correct child
        # payload with an old parent rectangle would still be a broken reopen.
        edited_parent = QRect(item.current_global_rect)
        edited_parent.translate(17, 11)
        item.set_geometry(edited_parent, size_payload=payload)
        session.notify_item_changed(item)
        qt_app.processEvents()
        # Save persists the current session then *promotes the same retained item*
        # before retiring the edit overlay. No generation replacement is valid.
        assert owner.save()
        assert settings.save_calls == 1
        assert reloads == []
        assert not owner.is_active
        assert unit.presenter.presentation_for_widget_id(family) is initial
        assert initial.item is initial_root
        committed = resolve_quick_committed_variant_state(
            settings.widgets, screen, family, geometry_variant="default",
        )
        assert committed is not None
        committed_rect, committed_payload = committed
        assert committed_payload["child_geometry"] == payload["child_geometry"]
        assert initial.model.customChildGeometry == payload["child_geometry"]
        assert initial.item.x() == pytest.approx(
            edited_parent.x() - screen.geometry().x(), abs=1.0,
        )
        assert initial.item.y() == pytest.approx(
            edited_parent.y() - screen.geometry().y(), abs=1.0,
        )
        painted_before = _mapped_rect(
            _one(initial.item, "redditHeaderFrame"), initial.item,
        )
        committed_snapshot = deepcopy(settings.widgets)

        # Full family + display-generation retirement, not same-host rebind.
        owner.retire()
        unit.retire()
        qt_app.processEvents()
        # The old generation's screen wrapper must not be used by the new
        # generation. Detect a real Qt screen loss here instead of allowing a
        # stale-wrapper RuntimeError to obscure the failing lifecycle phase.
        assert qt_app.primaryScreen() is not None
        fresh_unit, reopened = new_generation(settings.widgets, 2198)
        assert reopened.item is not initial_root
        assert reopened.model is not initial.model
        assert reopened.model.customChildGeometry == payload["child_geometry"]
        assert settings.widgets == committed_snapshot, "Fresh hydration must remain read-only"
        assert settings.save_calls == 1
        painted_after = _mapped_rect(
            _one(reopened.item, "redditHeaderFrame"), reopened.item,
        )
        assert painted_after == pytest.approx(painted_before, abs=1.0)
        assert reopened.item.x() == pytest.approx(committed_rect.x, abs=1.0)
        assert reopened.item.y() == pytest.approx(committed_rect.y, abs=1.0)
        header = _one(reopened.item, "redditHeaderFrame").parentItem()
        assert header is not None
        assert header.scale() == pytest.approx(0.9)
        assert bool(header.property("contentReversed"))
        assert _one(reopened.item, "redditRefreshTarget").width() > 0
        # A new Edit session must read the committed geometry and child roles
        # without writing Settings, then relinquish those transient state
        # holders on Cancel. This is the same production owner used for Save.
        fresh_owner = QuickCustomLayoutOwner(
            settings_manager=settings,
            participants_provider=lambda: (fresh_unit,),
            visualizer_provider=lambda: (None, None),
            reload_request=reloads.append,
            live_config_commit=lambda _widgets: None,
        )
        owners.append(fresh_owner)
        assert fresh_owner.start()
        fresh_session = fresh_owner.session
        assert fresh_session is not None
        reopened_item = next(
            value for value in fresh_session.items() if value.model_identity == family
        )
        assert reopened_item.current_global_rect == edited_parent
        assert reopened_item.current_size_payload["child_geometry"] == payload["child_geometry"]
        assert reopened_item.current_child_sizes == sizes
        assert _mapped_rect(
            _one(reopened.item, "redditHeaderFrame"), reopened.item,
        ) == pytest.approx(painted_before, abs=1.0)
        assert settings.widgets == committed_snapshot
        assert settings.save_calls == 1
        assert fresh_owner.cancel()
        assert not fresh_owner.is_active
        assert _mapped_rect(
            _one(reopened.item, "redditHeaderFrame"), reopened.item,
        ) == pytest.approx(painted_before, abs=1.0)
        assert fresh_unit.presenter.presentation_for_widget_id(family) is reopened
        assert settings.widgets == committed_snapshot
        assert settings.save_calls == 1
        assert reloads == []
    finally:
        for owner in reversed(owners):
            owner.retire()
        for unit in reversed(generations):
            unit.retire()
        for factory in reversed(factories):
            factory.deleteLater()
        qt_app.processEvents()
        qt_app.setQuitOnLastWindowClosed(previous_quit_on_last_window)
