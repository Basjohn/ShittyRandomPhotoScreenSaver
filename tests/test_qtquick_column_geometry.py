"""Column width/start edits cross real retained QML and the existing CUSTOM owners, without a shown window."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, QPoint, QPointF, QRect
from PySide6.QtQml import QQmlContext, QQmlEngine, QQmlExpression
from PySide6.QtQuick import QQuickItem

from rendering.custom_layout_session import CustomLayoutKey, CustomLayoutSession, CustomLayoutSessionItem
from rendering.quick.custom_layout_overlay import RetainedCustomLayoutOverlay
from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.widgets.host import OrdinaryWidgetPresentationHost, OverlayWidgetGeometry
from rendering.widget_descriptors import get_widget_runtime_descriptor
from tests.test_qtquick_gmail_presentation import _config, _style, _email, _snapshot
from tests.test_qtquick_reddit_presentation import _model as reddit_model, _post
from tests.test_qtquick_custom_layout_owner import _Settings


ROLES = {"gmail": ("timestamp", "sender", "subject"), "reddit": ("age", "ago", "title"),
         "reddit2": ("age", "ago", "title")}
NAMES = {"timestamp": "gmailTimestamp_", "sender": "gmailSender_", "subject": "gmailSubject_",
         "age": "redditPostAgeValue_", "ago": "redditPostAgeAgo_", "title": "redditPostTitle_"}


def walk(item):
    yield item
    for child in item.childItems():
        yield from walk(child)


def one(root, name):
    found = [item for item in walk(root) if item.objectName() == name]
    assert len(found) == 1, (name, len(found))
    return found[0]


def assert_rects_equal(actual, expected, *, tolerance=.02):
    for row, baseline in zip(actual, expected):
        assert row.keys() == baseline.keys()
        for role in row:
            assert row[role][:2] == pytest.approx(baseline[role][:2], abs=tolerance)
            assert row[role][2] == baseline[role][2]


class Scene:
    def __init__(self, qt_app, family, payload=None, collision=True):
        self.app, self.family = qt_app, family
        self.qt_owner = QObject()
        self.factory = QuickSceneFactory(self.qt_owner)
        self.context, self.root = self.factory.create_display_root(
            owner=self.qt_owner, screen_index=0, runtime_generation=1980)
        self.root.setWidth(1000); self.root.setHeight(700)
        self.host = OrdinaryWidgetPresentationHost(
            host_item=one(self.root, "ordinaryWidgetHost"), context=self.context,
            create_overlay_item=self.factory.create_overlay_widget,
            create_family_item=self.factory.create_ordinary_widget_family)
        if family == "gmail":
            from rendering.quick.widgets.gmail import GmailPresentationModel, RetainedGmailPresentation
            config = _config(group_threads=False, limit=3, max_sender_words=20, max_subject_words=30)
            self.model = GmailPresentationModel(config, _style(config))
            self.presentation = RetainedGmailPresentation(host=self.host, model=self.model,
                geometry=OverlayWidgetGeometry(80, 90, 620, 300))
        else:
            from rendering.quick.widgets.reddit import RetainedRedditPresentation
            self.model = reddit_model(widget_id=family, limit=3)
            self.presentation = RetainedRedditPresentation(host=self.host, model=self.model,
                geometry=OverlayWidgetGeometry(80, 90, 620, 300))
        self.presentation.activate()
        self.publish(1)
        self.payload = deepcopy(payload or {})
        self.presentation._apply_custom_layout_size_payload(self.payload)
        self.app.processEvents()
        descriptor = get_widget_runtime_descriptor(family)
        rect = QRect(80, 90, 620, 300)
        self.item = CustomLayoutSessionItem(
            source_key=CustomLayoutKey(family, "display:columns"), model_identity=family,
            baseline_global_rect=rect, current_global_rect=rect,
            baseline_size_payload=deepcopy(self.payload), current_size_payload=deepcopy(self.payload),
            baseline_enabled=True, current_enabled=True, custom_child_roles=descriptor.custom_child_roles,
            child_collision_enabled=collision)
        self.session = CustomLayoutSession(); self.session.add_item(self.item)
        self.settings = _Settings({family: {"enabled": True, "position": "Custom", "monitor": "ALL"}})
        self.owner = QuickCustomLayoutOwner(settings_manager=self.settings, participants_provider=lambda: (),
            visualizer_provider=lambda: (None, None), reload_request=lambda reason: None)
        self.owner._active = True; self.owner._session = self.session
        self.owner._descriptors[self.item.source_key] = descriptor
        self.edit = one(self.root, "customLayoutOverlay")
        self.overlay = RetainedCustomLayoutOverlay(self.edit)
        self.app.processEvents()

    def publish(self, revision):
        if self.family == "gmail":
            self.model.on_gmail_runtime_snapshot(_snapshot(revision, tuple(
                _email(str(i), sender="Retained Sender Name", subject="Retained column text", minute=i)
                for i in range(3))))
        else:
            self.model.publish_posts(tuple(_post(i + 1, title="Retained column text") for i in range(3)), now_ts=20_000.)

    def enter(self):
        self.presentation.item.setProperty("customLayoutInputBlocked", True)
        self.overlay.bind_session(self.session, display_identity="display:columns", display_origin=QPoint(0, 0),
            item_change_publisher=lambda item: self.presentation._apply_custom_layout_size_payload(item.current_size_payload),
            presentation_item_resolver=lambda item: self.presentation.item,
            child_resize_begin_handler=self.owner.begin_child_resize,
            child_resize_preview_handler=self.owner.preview_child_resize,
            child_resize_update_handler=self.owner.update_child_resize,
            child_gesture_cancel_handler=self.owner.cancel_child_gesture,
            column_rail_swap_handler=self.owner.swap_column_rail_roles)
        assert self.overlay.model.selectItem(0)
        self.app.processEvents()
        one(self.edit, "customLayoutEditFrame-" + self.family).setProperty("childEditingLocked", False)
        self.settle()

    def settle(self):
        def polish(item):
            for child in item.childItems(): polish(child)
            item.ensurePolished()
        for _ in range(3):
            polish(self.root); self.app.processEvents()

    def call(self, expression, **objects):
        layer = one(self.edit, "customLayoutChildRoleLayer-" + self.family)
        context = QQmlContext(QQmlEngine.contextForObject(layer))
        for name, value in objects.items(): context.setContextProperty(name, value)
        query = QQmlExpression(context, layer, expression)
        result, undefined = query.evaluate()
        assert not query.hasError(), query.error()
        assert not undefined
        context.deleteLater()
        return result

    def resize(self, role, side, dx):
        frame = one(self.edit, f"customLayoutChildRole-{self.family}-{role}")
        area = one(self.edit, f"customLayoutChildResizeEdge-{self.family}-{role}-{side}")
        gesture = area.parentItem()
        press = area.mapToItem(self.edit, area.width() / 2, area.height() / 2)
        params = dict(testFrame=frame, testGesture=gesture)
        assert self.call(f"beginChildResizeGesture(testFrame, testGesture, '{side}', Qt.point({press.x()}, {press.y()}))", **params)
        assert self.call(f"updateChildResizeGesture(testFrame, testGesture, '{side}', Qt.point({press.x()+dx}, {press.y()}), true)", **params)
        self.settle()

    def rects(self):
        rows = []
        for i in range(3):
            row = one(self.presentation.item, ("gmailMessageRow_" if self.family == "gmail" else "redditPostRow_") + str(i))
            cells = {}
            for role in ROLES[self.family]:
                text = one(self.presentation.item, NAMES[role] + str(i))
                origin = text.mapToItem(row, QPointF(0, 0))
                cells[role] = (origin.x(), text.width(), text.property("text"))
            rows.append(cells)
        return rows

    def close(self):
        self.overlay.clear_session()
        self.owner._active = False; self.owner._session = None
        self.presentation.retire(); self.host.retire_all()
        self.root.setParentItem(None); self.root.deleteLater()
        self.context.deleteLater(); self.factory.deleteLater(); self.qt_owner.deleteLater()
        self.app.processEvents()


@pytest.fixture
def scene(qt_app):
    scenes = []
    def create(family, **kwargs):
        result = Scene(qt_app, family, **kwargs); scenes.append(result); return result
    yield create
    for result in reversed(scenes): result.close()


def test_retained_gmail_admits_every_column_rail_before_and_during_edit(scene):
    live = scene("gmail")
    def admitted():
        roles = live.presentation.item.property("customEditableChildRoles").toVariant()
        rails = {role["roleId"]: role for role in roles if role.get("horizontalRail")}
        assert set(rails) == set(ROLES["gmail"])
        for role_id, role in rails.items():
            assert role["targetColumn"] == role_id
            assert role["normalizationTarget"] is live.presentation.item
            assert role["targetSource"].property("count") == 3
        return rails
    before = admitted()
    live.enter()
    assert admitted() == before
    live.publish(2); live.settle()
    assert admitted() == before


@pytest.mark.parametrize("family", ROLES)
def test_column_span_left_endpoint_changes_start_truncation_and_keeps_opposite_edge(scene, family):
    live = scene(family)
    before = live.rects()
    live.enter()
    assert live.rects() == before                  # entering Edit itself changes no paint
    role = "subject" if family == "gmail" else "title"
    frame = one(live.edit, f"customLayoutChildRole-{family}-{role}")
    original_frame = frame
    text = one(live.presentation.item, NAMES[role] + "0")
    main = one(text, "shadowedTextMain")
    assert not main.property("truncated")
    width = before[0][role][1]
    live.resize(role, "left", width * .65)
    after = live.rects()
    assert one(live.edit, f"customLayoutChildRole-{family}-{role}") is original_frame
    for first, changed in zip(before, after):
        assert changed[role][0] > first[role][0]
        assert sum(changed[role][:2]) == pytest.approx(sum(first[role][:2]), abs=1.1)
        assert changed[role][2] == first[role][2]
    assert main.property("truncated")
    assert live.item.current_global_rect == live.item.baseline_global_rect
    assert len(live.owner._undo_history) == 1
    live.publish(2); live.settle()
    assert live.rects() == after                   # provider update retains shared column geometry
    assert live.owner.undo_last_change()
    live.session.notify_item_changed(live.item); live.settle()
    assert live.rects() == before


@pytest.mark.parametrize("family", ROLES)
def test_column_width_start_order_save_cancel_slot_and_profile_reload(scene, family, tmp_path):
    from rendering.custom_layout_commit import commit_custom_session
    from rendering.custom_layout_contract import load_custom_layout_map, get_widget_layout_variant_payload
    from core.settings.layout_slots import save_layout_slot, apply_layout_slot
    from core.settings.settings_manager import SettingsManager
    unknown = {"future_column_role": {"width_scale": 1.7, "note": "preserve"}}
    live = scene(family, payload={"child_geometry": unknown})
    original = live.rects()
    live.enter()
    role, first = ROLES[family][-1], ROLES[family][0]
    live.resize(role, "left", original[0][role][1] * .4)
    assert live.call(f"admitColumnSwap('{role}', '{first}')")
    assert live.overlay.model.swapColumnRails(0, role, first)
    live.settle()
    edited, payload = live.rects(), deepcopy(live.item.current_size_payload)
    assert payload["child_geometry"]["future_column_role"] == unknown["future_column_role"]
    # Cancel's existing session boundary restores paint and every payload field, without settings I/O.
    live.session.restore_baseline(); live.settle()
    assert live.rects() == original and live.settings.save_calls == 0
    assert live.item.current_size_payload == {"child_geometry": unknown}
    # Reapply the captured draft through the same retained replay seam, then exercise canonical CUSTOM Save.
    live.item.current_size_payload = deepcopy(payload)
    live.session.notify_item_changed(live.item); live.settle()
    assert live.rects() == edited
    widgets = deepcopy(live.settings.widgets)
    commit_custom_session(widgets, live.session, live.owner._descriptors,
                          {"display:columns": (("screen:columns",), QRect(0, 0, 1000, 700), "ALL")})
    assert save_layout_slot(widgets, "1")
    expected_layout = deepcopy(widgets["custom_layout"])
    widgets["custom_layout"] = {}
    assert apply_layout_slot(widgets, "1")
    assert widgets["custom_layout"] == expected_layout
    profile = tmp_path / "profile"
    manager = SettingsManager(application="ColumnGeometryRoundTrip", storage_base_dir=profile)
    manager.set("widgets", widgets); assert manager.flush(timeout=5.)
    reopened = SettingsManager(application="ColumnGeometryRoundTrip", storage_base_dir=profile)
    restored = reopened.get("widgets")
    custom = load_custom_layout_map(restored)
    entry = get_widget_layout_variant_payload(custom["displays"]["screen:columns"], family, "default")
    assert entry is not None
    saved = entry["size_payload"]
    assert saved["column_rails"] == payload["column_rails"]
    assert saved["child_geometry"] == payload["child_geometry"]
    fresh = scene(family, payload=saved)
    assert fresh.rects() == edited                 # fresh hydration, before Edit has ever been entered
    fresh.enter()
    assert fresh.rects() == edited
    assert reopened.flush(timeout=5.)


@pytest.mark.parametrize("family", ROLES)
def test_reorder_uses_optional_collision_policy_for_expanded_column_geometry(scene, family):
    live = scene(family, collision=True)
    live.enter()
    first, middle, last = ROLES[family]
    before = live.rects()
    # Make a gap at the last column's start, then expand its predecessor into that gap.
    live.resize(last, "left", before[0][last][1] * .5)
    live.resize(middle, "right", before[0][last][1] * .3)
    after = live.rects()[0]
    assert after[middle][1] > before[0][middle][1] + 5
    assert after[middle][0] + after[middle][1] <= after[last][0] + 1.1
    # Moving that expanded middle column before the first would overlap a newly adjacent column.
    saved = deepcopy(live.item.current_size_payload)
    assert not live.call(f"admitColumnSwap('{middle}', '{first}')")
    assert live.item.current_size_payload == saved
    live.item.child_collision_enabled = False
    live.session.notify_item_changed(live.item); live.settle()
    assert live.call(f"admitColumnSwap('{middle}', '{first}')")
    assert live.overlay.model.swapColumnRails(0, middle, first)
    live.settle()
    assert live.item.current_size_payload["child_geometry"] == saved["child_geometry"]
    # Re-enabling collision must still allow a swap that reduces an already-overlapping input.
    live.item.child_collision_enabled = True
    live.session.notify_item_changed(live.item); live.settle()
    assert live.call(f"admitColumnSwap('{middle}', '{first}')")


@pytest.mark.parametrize("family", ROLES)
def test_endpoint_chrome_does_not_share_reorder_or_generic_move_hit_regions(scene, family):
    live = scene(family); live.enter()
    for role in ROLES[family]:
        grip = one(live.edit, f"customLayoutColumnGrip-{family}-{role}")
        span = one(live.edit, f"customLayoutColumnSpan-{family}-{role}")
        move = one(live.edit, f"customLayoutChildMoveArea-{family}-{role}")
        assert span.isVisible() and not move.property("enabled")
        grip_bottom = grip.mapToItem(live.edit, 0, grip.height()).y()
        for side in ("left", "right"):
            edge = one(live.edit, f"customLayoutChildResizeEdge-{family}-{role}-{side}")
            assert edge.mapToItem(live.edit, 0, 0).y() >= grip_bottom
    retained = [item for item in walk(live.presentation.item)]
    changes = []
    live.model.customGeometryChanged.connect(lambda: changes.append(True))
    for _ in range(3): live.publish(2); live.settle()
    assert changes == []
    assert list(walk(live.presentation.item)) == retained
    live.overlay.clear_session()
    live.presentation.item.setProperty("customLayoutInputBlocked", False)
    live.settle()
    assert not [item for item in walk(live.edit) if item.objectName().startswith("customLayoutColumnSpan-")]


@pytest.mark.parametrize("malformed", ("null", "function() { return [] }"))
def test_malformed_column_projection_is_logged_and_reorder_is_refused(scene, malformed):
    from PySide6.QtCore import qInstallMessageHandler
    live = scene("gmail"); live.enter()
    query = QQmlExpression(QQmlEngine.contextForObject(live.presentation.item), live.presentation.item,
                          "customColumnRailSwapRects = " + malformed)
    query.evaluate(); assert not query.hasError(), query.error()
    before = deepcopy(live.item.current_size_payload)
    messages = []
    previous = qInstallMessageHandler(lambda kind, context, message: messages.append(message))
    try:
        assert not live.call("admitColumnSwap('sender', 'subject')")
    finally:
        qInstallMessageHandler(previous)
    assert live.item.current_size_payload == before
    assert any("Semantic column reorder refused" in message for message in messages)


@pytest.mark.parametrize("family", ROLES)
def test_column_geometry_survives_flip_and_outer_resize_then_restore_clears_known_roles(scene, family):
    live = scene(family, payload={"child_geometry": {"future_role": {"keep": True}}})
    before = live.rects(); live.enter()
    role = ROLES[family][-1]
    live.resize(role, "left", before[0][role][1] * .4)
    edited = live.rects()
    payload = deepcopy(live.item.current_size_payload)
    flipped = deepcopy(payload)
    flipped["child_geometry"]["header"] = {"alignment": "right"}
    live.presentation._apply_custom_layout_size_payload(flipped); live.settle()
    after_flip = live.rects()
    assert after_flip != edited
    for row, old in zip(after_flip, edited):
        assert all(row[k][2] == old[k][2] for k in row)
    live.presentation.set_geometry(OverlayWidgetGeometry(80, 90, 800, 450)); live.settle()
    # Reddit's existing scale-aware text gap may vary below one local pixel as the outer uniform scale changes.
    assert_rects_equal(live.rects(), after_flip, tolerance=1.0)
    assert live.item.current_size_payload == payload
    live.presentation.set_geometry(OverlayWidgetGeometry(80, 90, 620, 300))
    live.presentation._apply_custom_layout_size_payload(payload); live.settle()
    assert_rects_equal(live.rects(), edited)
    live.item.size_reset_capable = True
    live.item.authored_reference_size = (620, 300)
    live.owner._bindings["display:columns"] = SimpleNamespace(geometry=QRect(0, 0, 1000, 700))
    assert live.owner.restore_item_size(live.item)
    live.settle()
    assert_rects_equal(live.rects(), before)
    # Explicit Restore Size intentionally clears unknown/retired records too (the existing reset contract).
    assert "child_geometry" not in live.item.current_size_payload


@pytest.mark.parametrize("family", ROLES)
def test_column_start_resize_keeps_middle_column_opposite_edge_without_parent_clipping(scene, family):
    live = scene(family); live.enter()
    role = ROLES[family][1]
    before = live.rects()[0][role]
    live.resize(role, "left", before[1] * .3)
    after = live.rects()[0][role]
    assert after[0] > before[0]
    assert sum(after[:2]) == pytest.approx(sum(before[:2]), abs=1.1)
