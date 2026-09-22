from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QMetaObject, QObject, QPointF, Qt, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QSignalSpy

from core.settings.default_contract import require_canonical_default
from core.steam.friend_pulse import (
    FriendPulseEntry,
    FriendPulseProjection,
    FriendPulseRow,
    FriendPulseSnapshot,
)
from core.steam.models import SteamResultStatus
from rendering.quick.widgets.family_binder import FriendPulseFamilyAdapter
from rendering.quick.widgets.friend_pulse import (
    FriendPulsePresentationConfig,
    FriendPulsePresentationModel,
    FriendPulsePresentationStyle,
)
from rendering.quick.widgets.registry import ordinary_widget_family_component
from rendering.widget_descriptors import get_widget_runtime_descriptor
from rendering.widget_runtime_services import get_runtime_service_spec


pytestmark = pytest.mark.usefixtures("qt_app")
ROOT = Path(__file__).resolve().parents[1]
QML_ROOT = ROOT / "rendering" / "quick" / "qml"


def _shadow_values() -> dict:
    return dict(require_canonical_default("widgets.shadows"))


class _RuntimeService:
    def __init__(self) -> None:
        self.consumer = None
        self.configs = []
        self.started = 0
        self.stopped = 0
        self.detached = 0
        self.refreshes = 0
        self.visible_ranges = []
        self.friend_ids = {"opaque": "76561198000000001"}

    def configure(self, config) -> None:
        self.configs.append(config)

    def set_thread_manager(self, manager) -> None:
        self.manager = manager

    def attach_consumer(self, consumer) -> None:
        self.consumer = consumer

    def detach_consumer(self, consumer) -> None:
        assert consumer is self.consumer
        self.detached += 1

    def start(self) -> bool:
        self.started += 1
        return True

    def stop(self) -> None:
        self.stopped += 1

    def refresh(self) -> bool:
        self.refreshes += 1
        return True

    def friend_steam_id(self, identity_fingerprint: str) -> str | None:
        return self.friend_ids.get(identity_fingerprint)

    def update_visible_range(self, first_index: int, last_index: int) -> bool:
        resolved = (int(first_index), int(last_index))
        if self.visible_ranges and self.visible_ranges[-1] == resolved:
            return False
        self.visible_ranges.append(resolved)
        return True


def _model(
    service: _RuntimeService | None = None,
    *,
    view_mode: str = "grid",
    capacity: int | None = None,
    preferred_width: int | None = None,
    show_names: bool | None = None,
    name_font_size: int | None = None,
) -> FriendPulsePresentationModel:
    card = {"view_mode": view_mode}
    if capacity is not None:
        card["visible_row_capacity"] = capacity
    if preferred_width is not None:
        card["preferred_width"] = preferred_width
    if show_names is not None:
        card["show_names"] = show_names
    if name_font_size is not None:
        card["name_font_size"] = name_font_size
    config = FriendPulsePresentationConfig.from_widgets_mapping({"friend_pulse": card})
    model = FriendPulsePresentationModel(
        config,
        FriendPulsePresentationStyle.project(config, _shadow_values()),
        runtime_generation=71,
    )
    if service is not None:
        model.set_runtime_service(service)
    return model


def _show_item(item: QQuickItem, model, qt_app) -> QQuickWindow:
    window = QQuickWindow()
    window.resize(int(model.authoredWidth), int(model.authoredHeight))
    item.setParentItem(window.contentItem())
    item.setWidth(model.authoredWidth)
    item.setHeight(model.authoredHeight)
    window.show()
    qt_app.processEvents()
    return window


def _find_visual_item(root: QQuickItem, object_name: str) -> QQuickItem | None:
    if root.objectName() == object_name:
        return root
    for child in root.childItems():
        found = _find_visual_item(child, object_name)
        if found is not None:
            return found
    return None


def _visual_items(root: QQuickItem):
    yield root
    for child in root.childItems():
        yield from _visual_items(child)


def _assert_representative_matches_rendered_role(
    root: QQuickItem, representative_name: str, rendered_name: str,
) -> None:
    representative = _find_visual_item(root, representative_name)
    rendered = _find_visual_item(root, rendered_name)
    assert representative is not None and rendered is not None, (
        representative_name, rendered_name,
    )
    assert representative.isVisible() and rendered.isVisible(), rendered_name
    def mapped_bounds(item):
        corners = [item.mapToItem(root, x, y) for x, y in (
            (0.0, 0.0), (item.width(), 0.0),
            (0.0, item.height()), (item.width(), item.height()),
        )]
        return (min(p.x() for p in corners), min(p.y() for p in corners),
                max(p.x() for p in corners), max(p.y() for p in corners))
    assert mapped_bounds(representative) == pytest.approx(
        mapped_bounds(rendered), abs=0.02,
    ), rendered_name


def test_configured_capacity_owns_authored_height_and_privacy() -> None:
    config = FriendPulsePresentationConfig.from_widgets_mapping(
        {
            "steam": {"privacy_mode": "Strict", "refresh_minutes": 17},
            "friend_pulse": {
                "view_mode": "rows",
                "visible_row_capacity": 4,
                "preferred_width": 610,
                "show_names": False,
                "name_font_size": 17,
            },
        }
    )
    assert config.capacity == 4
    assert config.authored_height == 334
    assert config.authored_width == 610
    assert config.privacy_mode == "Strict"
    assert config.view_mode == "rows"
    assert config.refresh_minutes == 17
    assert config.show_names is False
    assert config.name_font_size == 17


@pytest.mark.parametrize(
    ("capacity", "expected_height"),
    ((1, 252), (2, 252), (3, 252), (4, 252), (5, 394), (6, 394), (8, 394)),
)
def test_grid_height_is_capacity_owned_and_contains_complete_tile_rows(
    capacity: int,
    expected_height: int,
) -> None:
    config = FriendPulsePresentationConfig.from_widgets_mapping(
        {
            "friend_pulse": {
                "view_mode": "grid",
                "visible_row_capacity": capacity,
            }
        }
    )

    assert config.capacity == capacity
    assert config.authored_height == expected_height
    grid_body_height = config.authored_height - 91 - 19
    columns = min(capacity, 6, max(1, int(((560 - 36) + 10) // 120)))
    rows = (capacity + columns - 1) // columns
    required_height = rows * 132 + max(0, rows - 1) * 10
    assert grid_body_height >= required_height


def test_model_keeps_one_row_model_and_never_exposes_remote_avatar() -> None:
    service = _RuntimeService()
    model = _model(service)
    row_model = model.rowModel
    assert model.activate(object()) is True
    assert service.visible_ranges == [(0, model.config.capacity - 1)]
    snapshot = FriendPulseSnapshot(
        status=SteamResultStatus.SUCCESS,
        authoritative=True,
        playing_count=1,
        online_count=2,
        entries=(FriendPulseEntry("opaque", "Ada", 10, "Game"),),
    )
    remote = FriendPulseProjection(
        "ready",
        "1 friend playing",
        (
            FriendPulseRow(
                primary="ada lovelace",
                secondary="Game",
                presence_text="Online",
                online=True,
                avatar_url="https://avatars.steamstatic.com/remote.jpg",
                game_appid=10,
                identity_fingerprint="opaque",
                friend_action_available=True,
            ),
        ),
    )
    model.on_friend_pulse_runtime_snapshot(snapshot, remote)
    assert model.rowModel is row_model
    avatar_role = next(
        role for role, name in row_model.roleNames().items() if name == b"avatarSource"
    )
    presence_role = next(
        role for role, name in row_model.roleNames().items() if name == b"presenceText"
    )
    primary_role = next(
        role for role, name in row_model.roleNames().items() if name == b"primaryText"
    )
    online_role = next(
        role for role, name in row_model.roleNames().items() if name == b"isOnline"
    )
    assert row_model.data(row_model.index(0, 0), avatar_role) == ""
    assert row_model.data(row_model.index(0, 0), primary_role) == "Ada Lovelace"
    assert row_model.data(row_model.index(0, 0), presence_role) == "Online"
    assert row_model.data(row_model.index(0, 0), online_role) is True

    local = FriendPulseProjection(
        "ready",
        "1 friend playing",
        (
            FriendPulseRow(
                primary="Ada",
                secondary="Game",
                presence_text="Away",
                online=True,
                avatar_url="file:///safe/avatar.jpg",
                game_appid=10,
                identity_fingerprint="opaque",
                friend_action_available=True,
            ),
        ),
    )
    model.on_friend_pulse_runtime_snapshot(snapshot, local)
    assert model.rowModel is row_model
    assert row_model.data(row_model.index(0, 0), avatar_role).startswith("file:")
    model.set_interaction_enabled(True)
    assert model.request_manual_refresh() is True
    assert model.friend_action_target(0) == "76561198000000001"
    assert model.game_action_target(0) == "10"
    assert model.menu_action_target("profile", 0) == (
        "friend_profile",
        "76561198000000001",
    )
    assert model.menu_action_target("chat", 0) == (
        "friend_message",
        "76561198000000001",
    )
    assert model.menu_action_target("copy_id", 0) == (
        "copy_steam_id",
        "76561198000000001",
    )
    assert model.menu_action_target("store", 0) == ("store", "10")
    assert model.menu_action_target("join", 0) is None
    assert model.report_visible_range(0, 0) is True
    assert service.visible_ranges[-1] == (0, 0)
    assert model.report_visible_range(-1, -1) is True
    assert service.visible_ranges[-1] == (-1, -1)
    assert model.friend_action_target(1) is None
    model.retire()
    assert service.stopped == service.detached == 1


def test_friend_pulse_admission_requires_shared_and_member_enable() -> None:
    adapter = FriendPulseFamilyAdapter()
    assert adapter.enabled_instance_ids({}) == ()
    assert (
        adapter.enabled_instance_ids(
            {"steam": {"enabled": False}, "friend_pulse": {"enabled": True}}
        )
        == ()
    )
    assert (
        adapter.enabled_instance_ids(
            {"steam": {"enabled": True}, "friend_pulse": {"enabled": False}}
        )
        == ()
    )
    assert adapter.enabled_instance_ids(
        {"steam": {"enabled": True}, "friend_pulse": {"enabled": True}}
    ) == ("friend_pulse",)


def test_friend_pulse_registry_runtime_and_qml_are_retained_only() -> None:
    descriptor = get_widget_runtime_descriptor("friend_pulse")
    assert descriptor is not None
    assert descriptor.custom_layout_resize_mode == "ordinary_uniform"
    assert descriptor.service_backed is True
    assert get_runtime_service_spec("friend_pulse") is not None
    component = ordinary_widget_family_component("friend_pulse")
    assert component.qml_filename == "FriendPulsePresentation.qml"
    qml = (QML_ROOT / component.qml_filename).read_text(encoding="utf-8")
    for forbidden in (
        "Timer {",
        "http://",
        "https://",
        "SteamBackend",
        "FriendPulseRuntimeService",
        "SettingsManager",
        "QWidget",
        "QPainter",
        "Qt.callLater",
    ):
        assert forbidden not in qml
    assert "uniformScaleTransform: true" in qml
    assert "function friendStrokeWidth(baseWidth)" in qml
    assert "scaleAwareHeaderStrokeWidth" in qml
    assert qml.count("fontSizeMode: Text.Fit") >= 2
    assert qml.count("maximumLineCount: 2") >= 3
    assert qml.count("elide: Text.ElideNone") >= 2
    assert "signal friendActionRequested(int rowIndex)" in qml
    assert "signal gameActionRequested(int rowIndex)" in qml
    assert "signal friendMenuActionRequested(string action, int rowIndex)" in qml
    assert "signal visibleRangeChanged(int firstIndex, int lastIndex)" in qml
    assert "ListView {" in qml
    assert "GridView {" in qml
    assert "onMovementEnded: friendRoot.reportVisibleRange()" in qml
    assert "onCountChanged:" in qml
    assert "onContentYChanged:" in qml
    assert "onMovingChanged:" in qml
    assert "onMovementStarted: friendRoot.pendingChangeRows = ({})" in qml
    assert "rowIndex < _reportedFirstVisible" in qml
    assert "pendingChangeRows = ({})" in qml
    assert "property string activeActionIdentity" in qml
    assert 'fragmentShader: "shaders/widget_glow.frag.qsb"' in qml
    assert 'property: "eventGlowLevel"' in qml
    assert "onFriendChangePulseRequested" in qml
    assert "duration: 2000" in qml
    assert "duration: 3000" in qml
    assert "model: visible ?" not in qml
    assert "antialiasing: true" in qml
    assert "import QtQuick.Effects" in qml
    assert "id: rowAvatarImage" in qml
    assert "id: gridAvatarImage" in qml
    assert "id: rowAvatarMask" in qml
    assert "id: gridAvatarMask" in qml
    assert qml.count("fillMode: Image.PreserveAspectCrop") == 2
    assert qml.count("maskEnabled: true") == 2
    assert "maskSource: rowAvatarMask" in qml
    assert "maskSource: gridAvatarMask" in qml
    assert "anchors.margins: 3.0" not in qml
    assert "anchors.margins: 4.0" not in qml
    assert 'text: "NEW"' not in qml
    assert "Behavior on" not in qml


@pytest.mark.qt
def test_friend_pulse_qml_builds_real_rows(qt_app) -> None:
    service = _RuntimeService()
    model = _model(service, view_mode="rows")
    model.activate(object())
    snapshot = FriendPulseSnapshot(
        status=SteamResultStatus.SUCCESS,
        authoritative=True,
        playing_count=1,
        online_count=1,
        entries=(FriendPulseEntry("opaque", "Ada", 10, "Half-Life"),),
    )
    model.on_friend_pulse_runtime_snapshot(
        snapshot,
        FriendPulseProjection(
            "ready",
            "1 friend playing",
            (
                FriendPulseRow(
                    primary="Ada",
                    secondary="Half-Life",
                    presence_text="Online",
                    online=True,
                    changed=True,
                    identity_fingerprint="opaque",
                ),
            ),
        ),
    )
    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(QML_ROOT / "FriendPulsePresentation.qml"))
    )
    assert component.status() == QQmlComponent.Status.Ready, [
        error.toString() for error in component.errors()
    ]
    item = component.createWithInitialProperties({"friendPulseModel": model})
    assert isinstance(item, QQuickItem), [
        error.toString() for error in component.errors()
    ]
    window = _show_item(item, model, qt_app)
    try:
        qt_app.processEvents()
        rows = item.findChild(QObject, "friendPulseRowsView")
        assert rows is not None
        QMetaObject.invokeMethod(rows, "forceLayout")
        qt_app.processEvents()
        assert int(rows.property("count")) == 1
        row = _find_visual_item(item, "friendPulseRow_0")
        assert row is not None
        row_contact = _find_visual_item(item, "friendPulseRowContactShadow_0")
        avatar_contact = _find_visual_item(item, "friendPulseRowAvatarContactShadow_0")
        avatar_frame = _find_visual_item(item, "friendPulseRowAvatar_0")
        assert all(part is not None for part in (
            row_contact, avatar_contact, avatar_frame))
        assert row_contact.width() == pytest.approx(row.width())
        assert avatar_contact.width() == pytest.approx(avatar_frame.width())
        assert float(row.property("height")) == 50.0
        baseline_row_width = float(row.property("width"))
        baseline_view_width = float(rows.property("width"))
        assert baseline_row_width == pytest.approx(baseline_view_width - 12.0)
        frame_proxy = item.findChild(QQuickItem, "friendPulseCustomFriendFrameRoleTarget")
        # Growing the parent must grow the LIVE row rather than leave a
        # baseline-width island. One shared role target must match the delegate.
        expanded_width = float(model.authoredWidth) + 260.0
        assert model.set_content_extent(expanded_width, float(model.authoredHeight))
        item.setWidth(expanded_width)
        qt_app.processEvents()
        QMetaObject.invokeMethod(rows, "forceLayout")
        qt_app.processEvents()
        assert float(row.property("width")) > baseline_row_width
        assert float(row.property("width")) == pytest.approx(
            float(rows.property("width")) - 12.0
        )
        assert frame_proxy is not None
        assert float(frame_proxy.property("width")) == pytest.approx(
            float(row.property("width"))
        )
        for representative, painted in (
            ("friendPulseCustomFriendFrameRoleTarget", "friendPulseRow_0"),
            ("friendPulseCustomAvatarRoleTarget", "friendPulseRowAvatar_0"),
            ("friendPulseCustomUsernameRoleTarget", "friendPulseRowName_0"),
        ):
            _assert_representative_matches_rendered_role(item, representative, painted)
        # One edit owner for every repeated row: X/Y and scale changes update
        # the existing representative without creating per-row Edit delegates.
        assert model.set_custom_child_geometry({
            "friend_frames": {"width_scale": 0.93, "height_scale": 1.12},
            "avatars": {"width_scale": 1.1, "x_offset": 0.015, "y_offset": -0.01},
            "usernames": {"width_scale": 0.9, "height_scale": 1.08,
                          "x_offset": -0.008, "y_offset": 0.012},
        })
        qt_app.processEvents()
        QMetaObject.invokeMethod(rows, "forceLayout")
        qt_app.processEvents()
        for representative, painted in (
            ("friendPulseCustomFriendFrameRoleTarget", "friendPulseRow_0"),
            ("friendPulseCustomAvatarRoleTarget", "friendPulseRowAvatar_0"),
            ("friendPulseCustomUsernameRoleTarget", "friendPulseRowName_0"),
        ):
            _assert_representative_matches_rendered_role(item, representative, painted)
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater()
        window.close()
        window.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        model.retire()
        qt_app.processEvents()


def test_friend_change_glow_is_emitted_once_per_accepted_game_event() -> None:
    model = _model(_RuntimeService())
    model.activate(object())
    pulse_spy = QSignalSpy(model.friendChangePulseRequested)
    snapshot = FriendPulseSnapshot(
        status=SteamResultStatus.SUCCESS,
        authoritative=True,
        playing_count=1,
        online_count=1,
        entries=(FriendPulseEntry("opaque", "Ada", 10, "Half-Life"),),
    )
    changed = FriendPulseProjection(
        "ready",
        "1 online",
        (
            FriendPulseRow(
                primary="Ada",
                secondary="Half-Life",
                online=True,
                changed=True,
                game_appid=10,
                identity_fingerprint="opaque",
            ),
        ),
    )
    initial = FriendPulseProjection(
        "ready",
        "1 online",
        (replace(changed.rows[0], changed=False),),
    )
    model.on_friend_pulse_runtime_snapshot(snapshot, initial)
    assert pulse_spy.count() == 0

    model.on_friend_pulse_runtime_snapshot(snapshot, changed)
    assert pulse_spy.count() == 1
    assert pulse_spy.at(0) == [0]

    hydrated = FriendPulseProjection(
        "ready",
        "1 online",
        (replace(changed.rows[0], avatar_url="file:///avatar.png"),),
    )
    model.on_friend_pulse_runtime_snapshot(snapshot, hydrated)
    assert pulse_spy.count() == 1

    next_snapshot = replace(
        snapshot,
        entries=(FriendPulseEntry("opaque", "Ada", 20, "Team Fortress 2"),),
    )
    next_event = FriendPulseProjection(
        "ready",
        "1 online",
        (replace(changed.rows[0], secondary="Team Fortress 2", game_appid=20),),
    )
    model.on_friend_pulse_runtime_snapshot(next_snapshot, next_event)
    assert pulse_spy.count() == 2
    assert pulse_spy.at(1) == [0]
    model.retire()


@pytest.mark.qt
def test_friend_pulse_qml_builds_centered_dynamic_avatar_grid(qt_app) -> None:
    service = _RuntimeService()
    model = _model(service, view_mode="grid")
    model.activate(object())
    entries = tuple(
        FriendPulseEntry(f"opaque-{index}", name, 10 + index, game)
        for index, (name, game) in enumerate(
            (("Ada", "Half-Life"), ("Lee", "Portal 2"), ("Sam", "Outer Wilds"))
        )
    )
    snapshot = FriendPulseSnapshot(
        status=SteamResultStatus.SUCCESS,
        authoritative=True,
        playing_count=3,
        online_count=3,
        entries=entries,
    )
    model.on_friend_pulse_runtime_snapshot(
        snapshot,
        FriendPulseProjection(
            "ready",
            "3 friends playing",
            tuple(
                FriendPulseRow(
                    primary=entry.display_name or "Friend",
                    secondary=entry.game_name or "Unknown game",
                    presence_text="Online" if index < 2 else "Away",
                    online=True,
                    identity_fingerprint=entry.identity_fingerprint,
                )
                for index, entry in enumerate(entries)
            ),
        ),
    )
    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(QML_ROOT / "FriendPulsePresentation.qml"))
    )
    assert component.status() == QQmlComponent.Status.Ready, [
        error.toString() for error in component.errors()
    ]
    item = component.createWithInitialProperties({"friendPulseModel": model})
    assert isinstance(item, QQuickItem), [
        error.toString() for error in component.errors()
    ]
    window = _show_item(item, model, qt_app)
    try:
        qt_app.processEvents()
        grid = item.findChild(QObject, "friendPulseGridView")
        assert grid is not None
        QMetaObject.invokeMethod(grid, "forceLayout")
        qt_app.processEvents()
        assert int(grid.property("count")) == 3
        tiles = {
            name: _find_visual_item(item, name)
            for name in (
                "friendPulseGridTile_0",
                "friendPulseGridTile_1",
                "friendPulseGridTile_2",
            )
        }
        grid_contact = _find_visual_item(item, "friendPulseGridContactShadow_0")
        avatar_contact = _find_visual_item(item, "friendPulseGridAvatarContactShadow_0")
        avatar_frame = _find_visual_item(item, "friendPulseGridAvatar_0")
        assert all(part is not None for part in (
            grid_contact, avatar_contact, avatar_frame))
        assert grid_contact.width() == pytest.approx(tiles["friendPulseGridTile_0"].width())
        assert avatar_contact.width() == pytest.approx(avatar_frame.width())
        assert set(tiles) == {
            "friendPulseGridTile_0",
            "friendPulseGridTile_1",
            "friendPulseGridTile_2",
        }
        assert all(tile is not None for tile in tiles.values())
        positions = [
            tiles[f"friendPulseGridTile_{index}"].mapToItem(grid, QPointF(0, 0))
            for index in range(3)
        ]
        assert positions[0].y() == positions[1].y() == positions[2].y()
        assert positions[0].x() < positions[1].x() < positions[2].x()
        left_gap = positions[0].x()
        right_gap = float(grid.property("width")) - (
            positions[-1].x() + float(tiles["friendPulseGridTile_2"].property("width"))
        )
        assert abs(left_gap - right_gap) <= 1.0
        for representative, painted in (
            ("friendPulseCustomFriendFrameRoleTarget", "friendPulseGridTile_0"),
            ("friendPulseCustomAvatarRoleTarget", "friendPulseGridAvatar_0"),
            ("friendPulseCustomUsernameRoleTarget", "friendPulseGridName_0"),
        ):
            _assert_representative_matches_rendered_role(item, representative, painted)
        assert model.set_custom_child_geometry({
            "friend_frames": {"width_scale": 0.93, "height_scale": 1.12},
            "avatars": {"width_scale": 1.1, "x_offset": 0.015, "y_offset": -0.01},
            "usernames": {"width_scale": 0.9, "height_scale": 1.08,
                          "x_offset": -0.008, "y_offset": 0.012},
        })
        qt_app.processEvents()
        QMetaObject.invokeMethod(grid, "forceLayout")
        qt_app.processEvents()
        for representative, painted in (
            ("friendPulseCustomFriendFrameRoleTarget", "friendPulseGridTile_0"),
            ("friendPulseCustomAvatarRoleTarget", "friendPulseGridAvatar_0"),
            ("friendPulseCustomUsernameRoleTarget", "friendPulseGridName_0"),
        ):
            _assert_representative_matches_rendered_role(item, representative, painted)
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater()
        window.close()
        window.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        model.retire()
        qt_app.processEvents()


@pytest.mark.qt
def test_large_roster_grid_is_virtualized_and_honors_name_and_menu_contract(
    qt_app,
) -> None:
    service = _RuntimeService()
    model = _model(
        service,
        view_mode="grid",
        capacity=8,
        show_names=False,
        name_font_size=18,
    )
    model.activate(object())
    entries = tuple(
        FriendPulseEntry(
            f"opaque-{index}",
            f"Friend {index}",
            10 if index == 0 else None,
            "Half-Life" if index == 0 else None,
            persona_state=1 if index < 12 else 0,
        )
        for index in range(100)
    )
    model.on_friend_pulse_runtime_snapshot(
        FriendPulseSnapshot(
            status=SteamResultStatus.SUCCESS,
            authoritative=True,
            playing_count=1,
            online_count=12,
            entries=entries,
        ),
        FriendPulseProjection(
            "ready",
            "12 online",
            tuple(
                FriendPulseRow(
                    primary=entry.display_name or "Friend",
                    secondary=entry.game_name or "",
                    presence_text="In game"
                    if entry.game_appid
                    else ("Online" if index < 12 else "Offline"),
                    online=index < 12,
                    game_appid=entry.game_appid,
                    identity_fingerprint=entry.identity_fingerprint,
                    friend_action_available=True,
                )
                for index, entry in enumerate(entries)
            ),
        ),
    )
    model.set_interaction_enabled(True)

    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(QML_ROOT / "FriendPulsePresentation.qml"))
    )
    assert component.status() == QQmlComponent.Status.Ready, [
        error.toString() for error in component.errors()
    ]
    item = component.createWithInitialProperties({"friendPulseModel": model})
    assert isinstance(item, QQuickItem), [
        error.toString() for error in component.errors()
    ]
    window = _show_item(item, model, qt_app)
    try:
        qt_app.processEvents()
        grid = item.findChild(QObject, "friendPulseGridView")
        assert grid is not None and int(grid.property("count")) == 100
        QMetaObject.invokeMethod(grid, "forceLayout")
        qt_app.processEvents()
        delegates = [
            candidate
            for candidate in _visual_items(item)
            if candidate.objectName().startswith("friendPulseGridTile_")
        ]
        assert 1 <= len(delegates) < 30

        name = _find_visual_item(item, "friendPulseGridName_0")
        menu = _find_visual_item(item, "friendPulseMenuButton_0")
        assert name is not None and name.property("visible") is False
        assert name.property("font").pointSizeF() == pytest.approx(18.0)
        assert menu is not None and menu.property("visible") is True

        item.setProperty("menuRowIndex", 0)
        item.setProperty("menuFriendActionAvailable", True)
        item.setProperty("menuGameActionAvailable", True)
        item.setProperty("activeActionIdentity", "friend-row-0")
        qt_app.processEvents()
        popup = _find_visual_item(item, "friendPulseActionPopup")
        assert popup is not None and popup.property("visible") is True
        assert (
            _find_visual_item(item, "friendPulseAction_profile").property("visible")
            is True
        )
        assert (
            _find_visual_item(item, "friendPulseAction_chat").property("visible")
            is True
        )
        assert (
            _find_visual_item(item, "friendPulseAction_store").property("visible")
            is True
        )
        assert (
            _find_visual_item(item, "friendPulseAction_copy_id").property("visible")
            is True
        )

        model.set_interaction_enabled(False)
        qt_app.processEvents()
        assert popup.property("visible") is False
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater()
        window.close()
        window.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        model.retire()
        qt_app.processEvents()


@pytest.mark.qt
def test_scrolled_roster_shrink_republishes_clamped_visible_range(qt_app) -> None:
    service = _RuntimeService()
    model = _model(service, view_mode="rows", capacity=4)
    model.activate(object())
    entries = tuple(
        FriendPulseEntry(
            f"opaque-{index}",
            f"Friend {index}",
            None,
            None,
            persona_state=1,
        )
        for index in range(16)
    )
    initial_rows = tuple(
        FriendPulseRow(
            primary=entry.display_name or "Friend",
            presence_text="Online",
            online=True,
            identity_fingerprint=entry.identity_fingerprint,
            friend_action_available=True,
        )
        for entry in entries
    )
    model.on_friend_pulse_runtime_snapshot(
        FriendPulseSnapshot(
            status=SteamResultStatus.SUCCESS,
            authoritative=True,
            playing_count=0,
            online_count=len(entries),
            entries=entries,
        ),
        FriendPulseProjection("ready", "16 online", initial_rows),
    )

    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(QML_ROOT / "FriendPulsePresentation.qml"))
    )
    item = component.createWithInitialProperties({"friendPulseModel": model})
    assert isinstance(item, QQuickItem), [
        error.toString() for error in component.errors()
    ]
    item.visibleRangeChanged.connect(
        model.report_visible_range,
        Qt.ConnectionType.QueuedConnection,
    )
    window = _show_item(item, model, qt_app)
    try:
        rows_view = item.findChild(QObject, "friendPulseRowsView")
        assert rows_view is not None
        QMetaObject.invokeMethod(rows_view, "forceLayout")
        qt_app.processEvents()
        maximum_content_y = max(
            0.0,
            float(rows_view.property("contentHeight"))
            - float(rows_view.property("height")),
        )
        assert maximum_content_y > 580.0
        rows_view.setProperty("contentY", 580.0)
        QMetaObject.invokeMethod(rows_view, "forceLayout")
        qt_app.processEvents()
        assert service.visible_ranges[-1][0] >= 9, (
            rows_view.property("contentY"),
            rows_view.property("moving"),
            rows_view.property("visible"),
            item.property("viewportReportingReady"),
            item.property("_reportedFirstVisible"),
            item.property("_reportedLastVisible"),
            service.visible_ranges,
        )

        retained_entries = entries[:2]
        replacement_rows = tuple(
            replace(
                initial_rows[index],
                changed=index == 1,
                game_appid=10 if index == 1 else None,
                secondary="Half-Life" if index == 1 else "",
            )
            for index in range(2)
        )
        pulse_spy = QSignalSpy(model.friendChangePulseRequested)
        model.on_friend_pulse_runtime_snapshot(
            FriendPulseSnapshot(
                status=SteamResultStatus.SUCCESS,
                authoritative=True,
                playing_count=1,
                online_count=2,
                entries=(
                    retained_entries[0],
                    replace(
                        retained_entries[1],
                        game_appid=10,
                        game_name="Half-Life",
                    ),
                ),
            ),
            FriendPulseProjection("ready", "2 online", replacement_rows),
        )
        qt_app.processEvents()

        assert service.visible_ranges[-1] == (0, 1)
        assert model._visible_row_range == (0, 1)
        assert pulse_spy.count() == 1
        assert pulse_spy.at(0) == [1]
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater()
        window.close()
        window.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        model.retire()
        qt_app.processEvents()


@pytest.mark.parametrize("capacity", (5, 6))
@pytest.mark.qt
def test_narrow_grid_keeps_event_glow_and_friend_title_allocated(
    qt_app,
    capacity: int,
) -> None:
    service = _RuntimeService()
    model = _model(
        service,
        view_mode="grid",
        capacity=capacity,
        preferred_width=420,
    )
    model.activate(object())
    entries = tuple(
        FriendPulseEntry(
            f"opaque-{index}", f"Friend {index}", 10 + index, f"Game {index}"
        )
        for index in range(capacity)
    )
    model.on_friend_pulse_runtime_snapshot(
        FriendPulseSnapshot(
            status=SteamResultStatus.SUCCESS,
            authoritative=True,
            playing_count=capacity,
            online_count=capacity,
            entries=entries,
        ),
        FriendPulseProjection(
            "ready",
            f"{capacity} friends playing",
            tuple(
                FriendPulseRow(
                    primary=entry.display_name or "Friend",
                    secondary=entry.game_name or "Unknown game",
                    presence_text="Online",
                    online=True,
                    changed=index == 0,
                    identity_fingerprint=entry.identity_fingerprint,
                )
                for index, entry in enumerate(entries)
            ),
        ),
    )

    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(QML_ROOT / "FriendPulsePresentation.qml"))
    )
    assert component.status() == QQmlComponent.Status.Ready, [
        error.toString() for error in component.errors()
    ]
    item = component.createWithInitialProperties({"friendPulseModel": model})
    assert isinstance(item, QQuickItem), [
        error.toString() for error in component.errors()
    ]
    window = _show_item(item, model, qt_app)
    try:
        qt_app.processEvents()
        grid = item.findChild(QObject, "friendPulseGridView")
        assert grid is not None
        QMetaObject.invokeMethod(grid, "forceLayout")
        qt_app.processEvents()
        tile = _find_visual_item(item, "friendPulseGridTile_0")
        name = _find_visual_item(item, "friendPulseGridName_0")
        assert tile is not None and name is not None
        assert model.gridColumns == 3
        assert int(grid.property("count")) == capacity
        assert float(name.property("width")) >= 72.0
        glow = _find_visual_item(item, "friendPulseGridEventGlow_0")
        assert glow is not None
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater()
        window.close()
        window.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        model.retire()
        qt_app.processEvents()


def test_custom_friend_roles_are_grouped_and_use_one_narrow_geometry_signal() -> None:
    model = _model(view_mode="grid", capacity=12, preferred_width=900)
    base_columns = int(model.gridColumns)
    state_spy = QSignalSpy(model.stateChanged)
    geometry_spy = QSignalSpy(model.customGeometryChanged)

    # Repeated roster geometry is one shared record per visual role, never one
    # record per friend. Intrinsic avatars canonicalize to one scalar even if
    # persisted input has mismatched axes. Applying all six roles is still one
    # geometry-only notification and does not wake provider/state bindings.
    assert model.set_custom_child_geometry(
        {
            "header": {
                "width_scale": 1.15,
                "height_scale": 0.75,
                "x_offset": 0.05,
                "alignment": "right",
                "anchor": "top_right",
            },
            "online_count": {
                "width_scale": 1.2,
                "height_scale": 1.1,
                "x_offset": -0.04,
                "alignment": "left",
            },
            "separator": {"width_scale": 0.8, "y_offset": 0.03},
            "friend_frames": {"width_scale": 1.35, "height_scale": 1.25},
            "avatars": {
                "width_scale": 1.8,
                "height_scale": 0.6,
                "x_offset": 0.02,
                "y_offset": -0.03,
            },
            "usernames": {
                "width_scale": 1.4,
                "height_scale": 1.2,
                "x_offset": -0.02,
                "y_offset": 0.04,
            },
        }
    ) is True
    assert model.customHeaderWidthScale == pytest.approx(1.15)
    # Header is intrinsic/uniform: height canonicalizes to the width scale.
    assert model.customHeaderHeightScale == pytest.approx(1.15)
    assert model.customHeaderAlignment == "right"
    assert model.customHeaderAnchor == "top_right"
    assert model.customOnlineCountWidthScale == pytest.approx(1.2)
    assert model.customOnlineCountAlignment == "left"
    assert model.customSeparatorWidthScale == pytest.approx(0.8)
    assert model.customFriendFrameWidthScale == pytest.approx(1.35)
    assert model.customFriendFrameHeightScale == pytest.approx(1.25)
    assert model.customAvatarScale == pytest.approx(1.8)
    assert model.customAvatarXOffset == pytest.approx(0.02)
    assert model.customAvatarYOffset == pytest.approx(-0.03)
    assert model.customUsernameWidthScale == pytest.approx(1.4)
    assert model.customUsernameHeightScale == pytest.approx(1.2)
    assert model.customUsernameXOffset == pytest.approx(-0.02)
    assert model.customUsernameYOffset == pytest.approx(0.04)
    assert int(model.gridColumns) <= base_columns
    assert geometry_spy.count() == 1
    assert state_spy.count() == 0

    assert model.set_custom_child_geometry({}) is True
    assert model.customAvatarScale == pytest.approx(1.0)
    assert model.customFriendFrameWidthScale == pytest.approx(1.0)
    assert model.customUsernameWidthScale == pytest.approx(1.0)


def test_content_extent_override_reflows_grid_columns() -> None:
    service = _RuntimeService()
    model = _model(service, view_mode="grid", capacity=6, preferred_width=760)
    base_columns = int(model.gridColumns)
    base_width = float(model.authoredWidth)
    base_height = float(model.authoredHeight)

    # Narrow content box -> fewer columns; wide -> as many as the caps allow.
    assert model.set_content_extent(460.0, base_height) is True
    assert int(model.gridColumns) < base_columns
    assert model.authoredWidth == pytest.approx(460.0)
    assert model.set_content_extent(900.0, base_height) is True
    assert int(model.gridColumns) >= base_columns

    # Clearing the override returns to the canonical authored size and columns.
    assert model.clear_content_extent() is True
    assert int(model.gridColumns) == base_columns
    assert model.authoredWidth == pytest.approx(base_width)
    assert model.authoredHeight == pytest.approx(base_height)


@pytest.mark.qt
def test_content_extent_vertical_grows_row_viewport(qt_app) -> None:
    service = _RuntimeService()
    model = _model(service, view_mode="rows", capacity=4)
    model.activate(object())
    base_width = float(model.authoredWidth)
    base_height = float(model.authoredHeight)

    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(QML_ROOT / "FriendPulsePresentation.qml"))
    )
    item = component.createWithInitialProperties({"friendPulseModel": model})
    assert isinstance(item, QQuickItem), [
        error.toString() for error in component.errors()
    ]
    window = _show_item(item, model, qt_app)
    try:
        rows_view = item.findChild(QObject, "friendPulseRowsView")
        assert rows_view is not None
        base_list_height = float(rows_view.property("height"))

        # A committed/live vertical extent grows the logical content box; the
        # outer item grows to match so uniform scale stays 1 and the ListView
        # gains real row room instead of letterboxing.
        taller = base_height + 232.0
        assert model.set_content_extent(base_width, taller) is True
        item.setWidth(base_width)
        item.setHeight(taller)
        qt_app.processEvents()
        assert model.authoredHeight == pytest.approx(taller)
        assert float(rows_view.property("height")) > base_list_height + 200.0

        # Clearing returns to the authored viewport height exactly.
        assert model.clear_content_extent() is True
        item.setWidth(base_width)
        item.setHeight(base_height)
        qt_app.processEvents()
        assert model.authoredHeight == pytest.approx(base_height)
        assert float(rows_view.property("height")) == pytest.approx(base_list_height)
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater()
        window.close()
        window.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        model.retire()
        qt_app.processEvents()


@pytest.mark.qt
def test_friend_pulse_header_flip_moves_summary_to_opposite_rail_without_recreating_roles(qt_app) -> None:
    """One stored header alignment drives both header and peer rail; reset is identity."""
    model = _model(view_mode="rows", preferred_width=640)
    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(QML_ROOT / "FriendPulsePresentation.qml"))
    )
    assert component.status() == QQmlComponent.Status.Ready, [
        error.toString() for error in component.errors()
    ]
    item = component.createWithInitialProperties({"friendPulseModel": model})
    assert isinstance(item, QQuickItem), [
        error.toString() for error in component.errors()
    ]
    window = _show_item(item, model, qt_app)
    try:
        header = _find_visual_item(item, "friendPulseHeaderFrame")
        summary = _find_visual_item(item, "friendPulseSummary")
        separator = _find_visual_item(item, "friendPulseHeaderSeparator")
        assert header is not None and summary is not None and separator is not None
        initial_separator_width = separator.width()
        assert initial_separator_width == pytest.approx(float(model.authoredWidth) - 36.0)
        original_header_x, original_summary_x = header.x(), summary.x()
        assert original_header_x < original_summary_x
        assert summary.x() + summary.width() == pytest.approx(
            float(model.authoredWidth) - float(item.property("headerSafeInsetX"))
        )
        # Parent X growth moves only the on-rail summary; it does not create
        # a new child edit or request an extra provider snapshot.
        expanded_width = float(model.authoredWidth) + 200.0
        assert model.set_content_extent(expanded_width, float(model.authoredHeight))
        item.setWidth(expanded_width)
        qt_app.processEvents()
        assert separator.x() == pytest.approx(18.0)
        assert separator.width() == pytest.approx(expanded_width - 36.0)
        assert separator.width() > initial_separator_width + 190.0
        assert summary.x() + summary.width() == pytest.approx(
            expanded_width - float(item.property("headerSafeInsetX"))
        )
        assert model.clear_content_extent()
        item.setWidth(float(model.authoredWidth))
        qt_app.processEvents()
        assert separator.width() == pytest.approx(initial_separator_width)
        # Explicitly customized width remains a multiplier on the live span;
        # its independent normalized x/y offsets must not be rewritten.
        assert model.set_custom_child_geometry({"separator": {"width_scale": 0.8}})
        assert model.set_content_extent(expanded_width, float(model.authoredHeight))
        item.setWidth(expanded_width)
        qt_app.processEvents()
        assert separator.width() == pytest.approx((expanded_width - 36.0) * 0.8)
        assert model.clear_content_extent()
        item.setWidth(float(model.authoredWidth))
        assert model.set_custom_child_geometry({})
        qt_app.processEvents()
        assert summary.x() == pytest.approx(original_summary_x)
        geometry_edges = QSignalSpy(model.customGeometryChanged)
        assert model.set_custom_child_geometry({"header": {"alignment": "right"}})
        qt_app.processEvents()
        assert bool(item.property("headerFlipped"))
        assert header.parentItem().x() > summary.x()
        assert summary.x() == pytest.approx(float(item.property("headerSafeInsetX")))
        assert geometry_edges.count() == 1
        assert model.set_custom_child_geometry({
            "header": {"alignment": "right"},
            "online_count": {"alignment": "left"},
        })
        qt_app.processEvents()
        assert header.parentItem().x() > summary.x()
        assert geometry_edges.count() == 2
        assert model.set_custom_child_geometry({})
        qt_app.processEvents()
        assert not bool(item.property("headerFlipped"))
        assert header.x() == pytest.approx(original_header_x)
        assert summary.x() == pytest.approx(original_summary_x)
        assert geometry_edges.count() == 3
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater()
        window.close()
        window.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        qt_app.processEvents()
