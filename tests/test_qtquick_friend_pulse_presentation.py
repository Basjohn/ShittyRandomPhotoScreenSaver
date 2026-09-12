from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QObject, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem

from core.dev_gates import force_gate, is_steam_enabled
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


def _model(
    service: _RuntimeService | None = None,
    *,
    view_mode: str = "grid",
    capacity: int | None = None,
    preferred_width: int | None = None,
) -> FriendPulsePresentationModel:
    card = {"view_mode": view_mode}
    if capacity is not None:
        card["visible_row_capacity"] = capacity
    if preferred_width is not None:
        card["preferred_width"] = preferred_width
    config = FriendPulsePresentationConfig.from_widgets_mapping(
        {"friend_pulse": card}
    )
    model = FriendPulsePresentationModel(
        config,
        FriendPulsePresentationStyle.project(config, _shadow_values()),
        runtime_generation=71,
    )
    if service is not None:
        model.set_runtime_service(service)
    return model


def test_configured_capacity_owns_authored_height_and_privacy() -> None:
    config = FriendPulsePresentationConfig.from_widgets_mapping(
        {
            "steam": {"privacy_mode": "Strict", "refresh_minutes": 17},
            "friend_pulse": {
                "view_mode": "rows",
                "visible_row_capacity": 4,
                "preferred_width": 610,
            },
        }
    )
    assert config.capacity == 4
    assert config.authored_height == 334
    assert config.authored_width == 610
    assert config.privacy_mode == "Strict"
    assert config.view_mode == "rows"
    assert config.refresh_minutes == 17


@pytest.mark.parametrize(
    ("capacity", "expected_height"),
    ((1, 222), (2, 222), (3, 334), (4, 334), (5, 334), (6, 334)),
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
    columns = 2 if capacity <= 4 else 3
    rows = (capacity + columns - 1) // columns
    required_height = rows * 102 + max(0, rows - 1) * 10
    assert grid_body_height >= required_height


def test_model_keeps_one_row_model_and_never_exposes_remote_avatar() -> None:
    service = _RuntimeService()
    model = _model(service)
    row_model = model.rowModel
    assert model.activate(object()) is True
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
                primary="Ada",
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
    online_role = next(
        role for role, name in row_model.roleNames().items() if name == b"isOnline"
    )
    assert row_model.data(row_model.index(0, 0), avatar_role) == ""
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
    assert model.friend_action_target(1) is None
    model.retire()
    assert service.stopped == service.detached == 1


def test_friend_pulse_admission_requires_dev_gate_shared_and_member_enable() -> None:
    prior = is_steam_enabled()
    try:
        adapter = FriendPulseFamilyAdapter()
        force_gate(steam=False)
        assert (
            adapter.enabled_instance_ids(
                {"steam": {"enabled": True}, "friend_pulse": {"enabled": True}}
            )
            == ()
        )
        force_gate(steam=True)
        assert (
            adapter.enabled_instance_ids(
                {"steam": {"enabled": False}, "friend_pulse": {"enabled": True}}
            )
            == ()
        )
        assert adapter.enabled_instance_ids(
            {"steam": {"enabled": True}, "friend_pulse": {"enabled": True}}
        ) == ("friend_pulse",)
    finally:
        force_gate(steam=prior)


def test_friend_pulse_registry_runtime_and_qml_are_retained_only() -> None:
    prior = is_steam_enabled()
    try:
        force_gate(steam=True)
        descriptor = get_widget_runtime_descriptor("friend_pulse")
        assert descriptor is not None
        assert descriptor.custom_layout_resize_mode == "ordinary_uniform"
        assert descriptor.service_backed is True
        assert get_runtime_service_spec("friend_pulse") is not None
    finally:
        force_gate(steam=prior)
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
    ):
        assert forbidden not in qml
    assert "uniformScaleTransform: true" in qml
    assert "signal friendActionRequested(int rowIndex)" in qml
    assert "signal gameActionRequested(int rowIndex)" in qml
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
    item.setWidth(model.authoredWidth)
    item.setHeight(model.authoredHeight)
    try:
        qt_app.processEvents()
        repeater = item.findChild(QObject, "friendPulseRepeater")
        assert repeater is not None
        assert int(repeater.property("count")) == 1
        rows = item.findChild(QObject, "friendPulseRows")
        assert rows is not None
        row = next(
            child
            for child in rows.childItems()
            if child.objectName() == "friendPulseRow_0"
        )
        assert float(row.property("height")) == 50.0
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        model.retire()
        qt_app.processEvents()


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
    item.setWidth(model.authoredWidth)
    item.setHeight(model.authoredHeight)
    try:
        qt_app.processEvents()
        grid = item.findChild(QObject, "friendPulseGrid")
        repeater = item.findChild(QObject, "friendPulseGridRepeater")
        assert grid is not None and repeater is not None
        assert int(repeater.property("count")) == 3
        tiles = {
            child.objectName(): child
            for child in grid.childItems()
            if child.objectName().startswith("friendPulseGridTile_")
        }
        assert set(tiles) == {
            "friendPulseGridTile_0",
            "friendPulseGridTile_1",
            "friendPulseGridTile_2",
        }
        assert tiles["friendPulseGridTile_0"].y() == tiles["friendPulseGridTile_1"].y()
        assert tiles["friendPulseGridTile_2"].y() > tiles["friendPulseGridTile_0"].y()
        assert tiles["friendPulseGridTile_2"].x() > tiles["friendPulseGridTile_0"].x()
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        model.retire()
        qt_app.processEvents()


@pytest.mark.parametrize("capacity", (5, 6))
@pytest.mark.qt
def test_narrow_grid_keeps_changed_friend_title_allocated(
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
        FriendPulseEntry(f"opaque-{index}", f"Friend {index}", 10 + index, f"Game {index}")
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
    item.setWidth(model.authoredWidth)
    item.setHeight(model.authoredHeight)
    try:
        qt_app.processEvents()
        grid = item.findChild(QObject, "friendPulseGrid")
        assert grid is not None
        tile = next(
            child
            for child in grid.childItems()
            if child.objectName() == "friendPulseGridTile_0"
        )
        title = tile.findChild(QObject, "friendPulseGridTitle")
        assert tile is not None and title is not None
        assert model.gridColumns == 2
        repeater = grid.findChild(QObject, "friendPulseGridRepeater")
        assert repeater is not None and int(repeater.property("count")) == capacity
        assert float(title.property("width")) >= 56.0
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        model.retire()
        qt_app.processEvents()
