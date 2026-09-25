"""Artwork stays inside its rounded frame and under its outline (real render).

Qt Quick ``clip`` is rectangular and ignores ``radius``, and an outline painted
under an inset image is covered by it. Each case renders the production QML at
2x card scale with a pure-red image, then measures every red pixel against the
frame's ideal rounded rectangle: none may lie outside it, and none may lie in
the outline's stroke band (the artwork-frame contract: image inset by the
stroke on a concentric mask, outline on top).
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest
from PySide6.QtCore import QEventLoop, QPointF, QTimer, QUrl
from PySide6.QtGui import QColor, QImage
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlProperty
from PySide6.QtQuick import QQuickItem, QQuickWindow

from core.settings.default_contract import require_canonical_default

pytestmark = pytest.mark.usefixtures("qt_app")


def _wait_releasing_gil(ms: int) -> None:
    # QTest.qWait keeps the GIL while it processes events (PySide 6.9.1). The
    # first expose then waits for the render thread, which needs the GIL for
    # the Python window's connectNotify override lookup during
    # ShaderEffectSource sync: a deadlock. QEventLoop.exec releases the GIL.
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
QML_ROOT = Path(__file__).resolve().parents[1] / "rendering" / "quick" / "qml"
SCALE = 2.0


def _red_png(path: Path) -> Path:
    image = QImage(64, 64, QImage.Format.Format_ARGB32)
    image.fill(QColor(255, 0, 0))
    assert image.save(str(path))
    return path


def _visual(root: QQuickItem, name: str) -> QQuickItem | None:
    if root.objectName() == name:
        return root
    for child in root.childItems():
        found = _visual(child, name)
        if found is not None:
            return found
    return None


class _Scene:
    def __init__(self, qml: str, properties: dict, preferred: tuple[float, float]) -> None:
        self.engine = QQmlEngine()
        self.engine.addImportPath(str(QML_ROOT))
        self.component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(QML_ROOT / qml)))
        assert self.component.status() == QQmlComponent.Status.Ready, [
            error.toString() for error in self.component.errors()]
        self.root = self.component.createWithInitialProperties(properties)
        assert isinstance(self.root, QQuickItem), [e.toString() for e in self.component.errors()]
        width, height = preferred[0] * SCALE, preferred[1] * SCALE
        self.window = QQuickWindow()
        self.window.setColor(QColor(0, 0, 0))
        self.window.resize(int(width) + 2, int(height) + 2)
        self.root.setParentItem(self.window.contentItem())
        self.root.setWidth(width)
        self.root.setHeight(height)
        self.window.show()

    def grab(self) -> QImage:
        _wait_releasing_gil(1400)  # asynchronous decode + ArtworkFadeImage's fade-in
        return self.window.grabWindow()

    def close(self) -> None:
        self.window.close()
        self.root.deleteLater()
        self.window.deleteLater()


def _pen_width(item: QQuickItem) -> float:
    prop = QQmlProperty(item, "border.width")
    return float(prop.read() or 0.0) if prop.isValid() else 0.0


def _outline_width(frame: QQuickItem) -> float:
    """The frame's painted stroke, wherever it is drawn (frame or an overlay child)."""
    return max([_pen_width(frame)] + [_pen_width(child) for child in frame.childItems()])


def _red(color: QColor) -> bool:
    return color.red() >= 200 and color.green() <= 60 and color.blue() <= 60


def _assert_contained(grab: QImage, frame: QQuickItem, label: str) -> None:
    assert frame.isVisible() and frame.width() > 0.0, label
    dpr = grab.devicePixelRatio()
    top_left = frame.mapToScene(QPointF(0.0, 0.0))
    bottom_right = frame.mapToScene(QPointF(frame.width(), frame.height()))
    scene_scale = (bottom_right.x() - top_left.x()) / frame.width()
    x0, y0 = top_left.x() * dpr, top_left.y() * dpr
    x1, y1 = bottom_right.x() * dpr, bottom_right.y() * dpr
    radius = min(float(frame.property("radius")) * scene_scale * dpr, (x1 - x0) / 2.0, (y1 - y0) / 2.0)
    stroke = _outline_width(frame) * scene_scale * dpr
    assert radius >= 6.0, f"{label}: radius {radius:.1f} device px is too small to measure"
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    hx, hy = (x1 - x0) / 2.0 - radius, (y1 - y0) / 2.0 - radius
    escaped, covered, image = [], [], 0
    for py in range(max(0, int(y0) - 2), min(grab.height(), int(y1) + 3)):
        for px in range(max(0, int(x0) - 2), min(grab.width(), int(x1) + 3)):
            if not _red(grab.pixelColor(px, py)):
                continue
            image += 1
            qx, qy = abs(px + 0.5 - cx) - hx, abs(py + 0.5 - cy) - hy
            distance = (math.hypot(max(qx, 0.0), max(qy, 0.0))
                        + min(max(qx, qy), 0.0) - radius)  # signed, device px
            if distance > 1.0:
                escaped.append((px, py))
            elif -distance < stroke - 1.5:
                covered.append((px, py))
    assert image > 0, f"{label}: the test image never rendered"
    assert not escaped, f"{label}: {len(escaped)} image pixels outside the rounded frame, e.g. {escaped[:4]}"
    assert not covered, f"{label}: {len(covered)} image pixels over the outline, e.g. {covered[:4]}"


@pytest.mark.parametrize("view_mode", ["grid", "rows"])
def test_friend_pulse_avatar_stays_inside_its_frame(qt_app, tmp_path, view_mode) -> None:
    from core.steam.friend_pulse import (
        FriendPulseEntry, FriendPulseProjection, FriendPulseRow, FriendPulseSnapshot)
    from core.steam.models import SteamResultStatus
    from rendering.quick.widgets.friend_pulse import (
        FriendPulsePresentationConfig, FriendPulsePresentationModel, FriendPulsePresentationStyle)
    from tests.test_qtquick_friend_pulse_presentation import _RuntimeService

    avatar = _red_png(tmp_path / "avatar.png").as_uri()
    config = FriendPulsePresentationConfig.from_widgets_mapping({"friend_pulse": {"view_mode": view_mode}})
    model = FriendPulsePresentationModel(
        config, FriendPulsePresentationStyle.project(config, dict(require_canonical_default("widgets.shadows"))),
        runtime_generation=71)
    model.set_runtime_service(_RuntimeService())
    model.activate(object())
    entry = FriendPulseEntry("opaque-0", "Ada", 10, "Half-Life")
    snapshot = FriendPulseSnapshot(status=SteamResultStatus.SUCCESS, authoritative=True,
                                   playing_count=1, online_count=1, entries=(entry,))
    model.on_friend_pulse_runtime_snapshot(snapshot, FriendPulseProjection("ready", "1 friend playing", (
        FriendPulseRow(primary="Ada", secondary="Half-Life", presence_text="Online", online=True,
                       identity_fingerprint="opaque-0", avatar_url=avatar),)))
    scene = _Scene("FriendPulsePresentation.qml", {"friendPulseModel": model},
                   (model.authoredWidth, model.authoredHeight))
    try:
        grab = scene.grab()
        name = "friendPulseGridAvatar_0" if view_mode == "grid" else "friendPulseRowAvatar_0"
        frame = _visual(scene.root, name)
        assert frame is not None
        _assert_contained(grab, frame, f"Friend Pulse {view_mode} avatar")
    finally:
        scene.close()


def test_games_you_follow_artwork_stays_inside_its_frames(qt_app, tmp_path) -> None:
    from dataclasses import replace

    from core.steam.games_followed_source import FollowedNewsSnapshot, FollowedNewsStory
    from rendering.quick.widgets.games_you_follow import GamesYouFollowPresentationModel

    red = str(_red_png(tmp_path / "art.png"))
    story = FollowedNewsStory(appid=10000, gid="90000", title="Update", published_at=1700000000,
                              feed_name="News", action_available=True,
                              article_url="https://store.steampowered.com/news/app/10000/view/80000",
                              game_name="Limbus Company", preview="Preview text")
    snapshot = FollowedNewsSnapshot("available", (story,), followed_count=1, checked_count=1)
    snapshot = replace(snapshot, artwork_paths=(red,), inline_image_paths=((red, red),))
    model = GamesYouFollowPresentationModel()
    assert model.accept_snapshot(snapshot)
    model.set_content_extent(730.0, 440.0)
    scene = _Scene("GamesYouFollowPresentation.qml", {"followedModel": model},
                   (model.authoredWidth, model.authoredHeight))
    try:
        grab = scene.grab()
        outline = _visual(scene.root, "followedStoryArtworkOutline0")
        inline = _visual(scene.root, "followedStoryInlineImageFrame10")
        assert outline is not None and inline is not None
        _assert_contained(grab, outline, "Games You Follow story artwork")
        _assert_contained(grab, inline, "Games You Follow inline image")
    finally:
        scene.close()


@pytest.mark.parametrize("view_mode", ["grid", "list"])
def test_feeds_artwork_stays_inside_its_frame(qt_app, tmp_path, view_mode) -> None:
    from time import time

    from core.feeds.models import (FeedDocument, FeedHealth, FeedImageCandidate, FeedItem,
                                   FeedRefreshResult, FeedSnapshot)
    from rendering.quick.widgets.feeds import (FeedPresentationConfig, FeedPresentationModel,
                                               FeedPresentationStyle)

    red = _red_png(tmp_path / "art.png").as_uri()
    config = FeedPresentationConfig.from_widgets_mapping({"feeds_custom_1": {
        "enabled": True, "feed_url": "https://example.test/feed.xml",
        "view_mode": view_mode, "show_images": True, "item_limit": 1,
    }}, widget_id="feeds_custom_1")
    model = FeedPresentationModel(
        config, FeedPresentationStyle.project(config, dict(require_canonical_default("widgets.shadows"))))
    model._active = True  # Test-only consumer admission; no runtime/network owner.
    now = time()
    item = FeedItem("0", "Photo", "https://example.test/0",
                    images=(FeedImageCandidate("https://cdn.example.test/0.png"),))
    model.on_feed_runtime_result(FeedRefreshResult(
        "available", FeedSnapshot(FeedDocument("Photos", "https://example.test", "rss20", (item,)), now),
        FeedHealth(last_success_at=now), local_artwork_by_item=(("0", red),)), from_cache=False)
    scene = _Scene("FeedPresentation.qml", {"feedModel": model},
                   (model.preferredWidth, model.preferredHeight))
    try:
        grab = scene.grab()
        frame = _visual(scene.root, f"feed{view_mode.capitalize()}ArtworkFrame0")
        assert frame is not None
        _assert_contained(grab, frame, f"FEEDS {view_mode} artwork")
    finally:
        scene.close()
