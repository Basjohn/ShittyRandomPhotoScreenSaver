"""Expanded Visualizer M3b: the full-display overlays (plan 01 §G, §H Milestone 3b).

Operator, 8 Nov: the preset's name in Title Case fading in and out gently when it changes; Artist, Song and Artwork
fading in and out very gently when the track changes; the artwork with the themed border, the text white with a
customizable font; any corner, Always Show, Media Controls and a Card as options.

These bars run the production ``DisplayScene.qml`` / ``VisualizerPresentation.qml`` and ``QuickSceneController`` in a
hidden ``QQuickRenderControl`` host (``tools/expanded_visualizer_evidence.HiddenDisplayHost``; no window is shown):

* dormant: nothing of the overlays exists (no item, no Media subscription) unless the display-wide card is drawn,
  and undrawing removes it all again;
* event-only: they appear on entering, on a preset announcement and on a track's identity change, run one bounded
  fade and retire (invisible, nothing left in the frame, nothing running) until the next event; latest wins;
* identity-fenced: a track's artwork is never shown under another track's text;
* Always Show keeps an overlay up and swaps its content by fading the content only (never a pop);
* every corner places both overlays inside the safe area, clear of the card's controls, stacked without overlap
  with the newer nearer the edge; the OSD keeps priority;
* Media Controls reach the one Media route; the overlays add no Media consumer.

The owner's edge (the overlays exist exactly while the display-wide card is drawn and the displays are on) is checked
with the production owner. Timings are shortened on the live items for speed (they are the items' own properties);
every value a test writes is test-owned.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy
import pytest
from PySide6.QtCore import (
    QElapsedTimer,
    QEvent,
    QObject,
    QPointF,
    QRectF,
    Property,
    Qt,
    SIGNAL,
    Signal,
    QCoreApplication,
)
from PySide6.QtGui import QMouseEvent
from PySide6.QtQuick import QQuickItem

WIDTH, HEIGHT = 1280, 720
CHROME = {"border_width": 4.0, "corner_radius": 8.0, "content_inset": 0.0,
          "background_color": (20, 22, 26, 200), "border_color": (230, 234, 240, 255),
          "shadow_enabled": True, "shadow_color": (0, 0, 0, 150), "shadow_blur": 18.0,
          "shadow_offset": (4.0, 4.0), "shadow_spread": 0.0, "shadow_extensions": (0.0, 0.0, 4.0, 4.0)}
FAST = {"fadeInMs": 120, "holdMs": 260, "fadeOutMs": 160, "swapOutMs": 90, "swapInMs": 90,
        "resizeMs": 60, "stackGlideMs": 80}
SLOTS = ("expandedOverlayPreset", "expandedOverlayNowPlaying")


class _Media(QObject):
    """A test-owned stand-in carrying exactly the Media model properties the overlays read (checked against the real
    ``MediaPresentationModel`` below), so tests can drive track identity and artwork directly."""

    stateChanged = Signal()

    def __init__(self, **values) -> None:
        super().__init__()
        self.values = dict(hasTrack=True, title="Track One", artist="Artist One", artworkSource="",
                           playbackState="playing", canPrevious=True, canNext=True, canPlayPause=True)
        self.values.update(values)

    def update(self, **values) -> None:
        self.values.update(values)
        self.stateChanged.emit()

    def _value(name, kind, notify=stateChanged):
        return Property(kind, lambda self: self.values[name], notify=notify)

    hasTrack = _value("hasTrack", bool)
    title = _value("title", str)
    artist = _value("artist", str)
    artworkSource = _value("artworkSource", str)
    playbackState = _value("playbackState", str)
    canPrevious = _value("canPrevious", bool)
    canNext = _value("canNext", bool)
    canPlayPause = _value("canPlayPause", bool)


@pytest.fixture
def display(qt_app):
    if qt_app.platformName().strip().lower() != "windows":
        pytest.skip("the hidden production scene needs the Windows QPA GL")
    from tools.expanded_visualizer_evidence import HiddenDisplayHost

    host = HiddenDisplayHost(WIDTH, HEIGHT, dpr=1.0)
    try:
        yield host
    finally:
        host.close()


def _render(display) -> None:
    """One frame, finished on the GPU before the next: an unthrottled loop queues frames, and the next texture upload
    (a glyph, a layer) then waits for the whole queue, jumping the time-based animations past what is sampled."""
    display.render()
    display._current()
    display._gl.glFinish()


def _settle(display, until, timeout_ms: int = 6000) -> None:
    clock = QElapsedTimer()
    clock.start()
    while not until():
        _render(display)
        if clock.elapsed() > timeout_ms:
            raise AssertionError("the overlays did not reach the expected state before the deadline")


def _run(display, ms: int, sample=None) -> None:
    clock = QElapsedTimer()
    clock.start()
    while clock.elapsed() < ms:
        _render(display)
        if sample is not None:
            sample()


def _frame(display) -> numpy.ndarray:
    """The settled frame (unchanged over 150 ms of animation time)."""
    clock = QElapsedTimer()
    clock.start()
    display.render()
    previous, since = display.read(), clock.elapsed()
    while clock.elapsed() < 6000:
        display.render()
        current = display.read()
        if not numpy.array_equal(current, previous):
            previous, since = current, clock.elapsed()
        elif clock.elapsed() - since >= 150:
            return current
    raise AssertionError("the hidden scene did not settle")


def _expanded_card(display) -> None:
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from widgets.spotify_visualizer.presentation_geometry import (
        resolve_expanded_visualizer_presentation,
        resolve_visualizer_presentation,
    )

    ordinary = resolve_visualizer_presentation(policy=get_visualizer_presentation_policy("extruded_bubble"),
                                               display_size=(WIDTH, HEIGHT), outer_origin=(30.0, 400.0), **CHROME)
    display.scene.apply_visualizer_presentation(
        resolve_expanded_visualizer_presentation(ordinary, display_size=(WIDTH, HEIGHT)), active=True)


def _config(**overrides) -> dict:
    """The QML projection of a test-owned ``fullscreen_overlays`` value (canonical, with ``overrides`` per overlay)."""
    from core.settings.fullscreen_overlays import canonical_fullscreen_overlays
    from widgets.spotify_visualizer.expanded_overlays import resolve_expanded_overlay_config

    value = canonical_fullscreen_overlays()
    for overlay, options in overrides.items():
        value[overlay].update(options)
    return resolve_expanded_overlay_config({"fullscreen_overlays": value})


def _root(display):
    return display.scene._visualizer_root


def _layer(display):
    return _root(display).findChild(QQuickItem, "expandedVisualizerOverlays")


def _slot(display, name: str):
    return _root(display).findChild(QQuickItem, name)


def _prop(item, name):
    return item.property(name)


def _visual(item):
    """Every item under ``item`` in the visual tree (Repeater delegates are not its QObject children)."""
    found, queue = [], list(item.childItems())
    while queue:
        child = queue.pop()
        found.append(child)
        queue.extend(child.childItems())
    return found


def _named(item, name):
    return next((child for child in _visual(item) if child.objectName() == name), None)


def _shown(display, name) -> bool:
    slot = _slot(display, name)
    return slot is not None and slot.isVisible() and float(slot.opacity()) > 0.0


def _draw(display, *, media=None, preset="Preset Alpha", config=None, gate_closed=True, fast=True):
    """Publish the overlays' inputs as the display manager does, then draw the display-wide card. With the startup
    gate closed first the overlays wait; the test shortens their timings and opens it (``_open``)."""
    scene = display.scene
    _expanded_card(display)
    scene.set_visualizer_expanded_overlay_config(config if config is not None else _config())
    scene.announce_visualizer_preset(preset, reveal=False)
    scene.set_visualizer_overlay_media_model(media)
    if gate_closed:
        scene.set_visualizer_startup_reveal_opacity(0.0)
    scene.set_visualizer_expanded_overlays_drawn(True)
    display.render()
    if fast:
        for name in SLOTS:
            slot = _slot(display, name)
            for key, value in FAST.items():
                slot.setProperty(key, value)


def _open(display) -> None:
    display.scene.set_visualizer_startup_reveal_opacity(1.0)


def _rect(item, root) -> QRectF:
    return item.mapRectToItem(root, QRectF(0.0, 0.0, item.width(), item.height()))


# ----------------------------------------------------------------------------------------------- dormancy


@pytest.mark.qt
def test_the_stand_in_reads_only_properties_the_real_media_model_has():
    from rendering.quick.widgets.media import MediaPresentationModel

    meta = MediaPresentationModel.staticMetaObject
    real = {meta.property(i).name() for i in range(meta.propertyCount())}
    stand_in = _Media.staticMetaObject
    names = {stand_in.property(i).name() for i in range(stand_in.propertyOffset(), stand_in.propertyCount())}
    assert names and names <= real


@pytest.mark.qt
def test_nothing_exists_until_the_display_wide_card_is_drawn_and_undrawing_removes_it(display):
    scene = display.scene
    media = _Media()
    signal = SIGNAL("stateChanged()")
    _expanded_card(display)
    scene.set_visualizer_expanded_overlay_config(_config())
    scene.announce_visualizer_preset("Preset Alpha", reveal=False)
    scene.set_visualizer_overlay_media_model(media)
    scene.announce_visualizer_preset("Preset Beta")          # an announcement while not drawn is not an event
    _run(display, 200)
    loader = _root(display).findChild(QQuickItem, "visualizerExpandedOverlays")
    assert loader is not None and loader.property("active") is False
    assert _layer(display) is None and media.receivers(signal) == 0      # no item, no Media subscription
    before = len(_root(display).findChildren(QObject))

    scene.set_visualizer_expanded_overlays_drawn(True)
    display.render()
    assert _layer(display) is not None and media.receivers(signal) > 0
    scene.set_visualizer_expanded_overlays_drawn(False)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    display.render()
    assert _layer(display) is None and media.receivers(signal) == 0
    assert len(_root(display).findChildren(QObject)) == before


@pytest.mark.qt
def test_a_restore_before_the_reveal_waits_for_it(display):
    _draw(display, media=_Media())
    _run(display, 300)
    assert not any(_shown(display, name) for name in SLOTS)
    _open(display)
    _settle(display, lambda: all(_shown(display, name) for name in SLOTS))


# ------------------------------------------------------------------------------------ event-only visibility


@pytest.mark.qt
def test_entering_reveals_once_then_the_overlays_retire_and_nothing_runs(display):
    _expanded_card(display)
    reference = _frame(display)                       # the drawn card with no overlay
    _draw(display, media=_Media())
    _open(display)
    _settle(display, lambda: all(_shown(display, name) for name in SLOTS))
    assert _prop(_slot(display, "expandedOverlayPreset"), "contentText") == "Preset Alpha"
    assert _prop(_slot(display, "expandedOverlayNowPlaying"), "contentTitle") == "Track One"
    # Each fades out within its bounded window and retires: invisible, its place released, the frame untouched.
    _settle(display, lambda: not any(_shown(display, name) for name in SLOTS))
    _run(display, 200)
    for name in SLOTS:
        slot = _slot(display, name)
        assert _prop(slot, "presence") == 0.0 and _prop(slot, "shown") is False and not slot.isVisible()
    assert numpy.array_equal(_frame(display), reference)
    # No timer brings anything back: only an event does.
    _run(display, 600)
    assert not any(_shown(display, name) for name in SLOTS)


@pytest.mark.qt
def test_a_preset_announcement_reveals_the_toast_and_the_latest_wins(display):
    _draw(display, media=None)
    _open(display)
    preset = "expandedOverlayPreset"
    _settle(display, lambda: _shown(display, preset))
    _settle(display, lambda: not _shown(display, preset))
    slot = _slot(display, preset)
    seen = []
    display.scene.announce_visualizer_preset("Preset Bravo")
    display.scene.announce_visualizer_preset("Preset Charlie")       # before the first frame: latest wins
    _settle(display, lambda: _shown(display, preset) and _prop(slot, "presence") >= 1.0,
            )
    assert _prop(slot, "contentText") == "Preset Charlie"

    # A change while it shows swaps the content behind a content fade; the toast itself stays up.
    lowest = [1.0, 1.0]

    def sample():
        lowest[0] = min(lowest[0], _prop(slot, "presence"))
        lowest[1] = min(lowest[1], _prop(slot, "contentOpacity"))
        seen.append((_prop(slot, "contentText"), _prop(slot, "contentOpacity")))

    display.scene.announce_visualizer_preset("Preset Delta")
    _run(display, 260, sample)
    assert _prop(slot, "contentText") == "Preset Delta"
    assert lowest[0] >= 0.999 and lowest[1] < 0.2
    first_delta = next(opacity for text, opacity in seen if text == "Preset Delta")
    assert first_delta < 0.5                       # swapped while invisible, then faded in
    _settle(display, lambda: not _shown(display, preset))


@pytest.mark.qt
def test_a_track_change_reveals_now_playing_and_its_artwork_is_identity_fenced(display, tmp_path):
    from PySide6.QtGui import QColor, QImage

    art_one, art_two = tmp_path / "one.png", tmp_path / "two.png"
    for path, colour in ((art_one, "#d03030"), (art_two, "#3060d0")):
        image = QImage(64, 64, QImage.Format.Format_ARGB32)
        image.fill(QColor(colour))
        image.save(str(path))
    media = _Media(artworkSource=art_one.as_uri())
    _draw(display, media=media)
    for key, value in {"holdMs": 2500}.items():
        _slot(display, "expandedOverlayNowPlaying").setProperty(key, value)
    _open(display)
    name = "expandedOverlayNowPlaying"
    slot = _slot(display, name)
    _settle(display, lambda: _prop(slot, "presence") >= 1.0)
    assert _prop(slot, "artSource") == art_one.as_uri()

    # One coherent publication: new title and new art. Until the content swaps, the old text keeps no art at all.
    media.update(title="Track Two", artist="Artist Two", artworkSource=art_two.as_uri())
    assert _prop(slot, "contentTitle") == "Track One" and _prop(slot, "artSource") == ""
    pairs = []
    _run(display, 400, lambda: pairs.append((_prop(slot, "contentTitle"), _prop(slot, "artSource"))))
    assert all(art in ("", art_two.as_uri()) for title, art in pairs if title == "Track One")
    assert all(art in ("", art_two.as_uri()) for title, art in pairs if title == "Track Two")
    assert _prop(slot, "contentTitle") == "Track Two" and _prop(slot, "artSource") == art_two.as_uri()
    assert ("Track One", art_two.as_uri()) not in pairs

    # Missing art falls back to the theme's geometry (the card surface under the empty image).
    media.update(artworkSource="")
    _run(display, 200)
    fallback = _root(display).findChild(QQuickItem, "expandedOverlayArtworkFallback")
    assert _prop(slot, "artSource") == "" and fallback is not None and fallback.isVisible()
    # No track: Now Playing fades out (it has nothing to show).
    media.update(hasTrack=False, title="No Media Playing", artist="")
    _settle(display, lambda: not _shown(display, name))


@pytest.mark.qt
def test_playback_resuming_reveals_now_playing_like_a_track_change(display):
    """Operator, 8 Nov: "we're not fading in the fullscreen visualizer overlay on pause -> play and we really
    should." Paused -> playing is an event (Now Playing fades in and out in its bounded window); a pause, or a playing
    state published again, is not; the same track's content is kept (never swapped)."""
    media = _Media(playbackState="playing")
    _draw(display, media=media)
    _open(display)
    name = "expandedOverlayNowPlaying"
    _settle(display, lambda: _shown(display, name))
    _settle(display, lambda: not _shown(display, name))          # the entering reveal retired

    media.update(playbackState="paused")                          # pausing is not an event
    _run(display, 300)
    assert not _shown(display, name)
    media.update(playbackState="playing")                         # resuming is
    _settle(display, lambda: float(_slot(display, name).property("presence")) >= 1.0)
    assert _slot(display, name).property("contentTitle") == "Track One"
    _settle(display, lambda: not _shown(display, name))          # within the same bounded window

    media.update(playbackState="playing", canNext=False)          # playing -> playing: no event
    _run(display, 300)
    assert not _shown(display, name)


@pytest.mark.qt
def test_playback_resuming_leaves_always_show_as_it_is(display):
    media = _Media(playbackState="paused")
    _draw(display, media=media, config=_config(now_playing={"always_show": True}))
    _open(display)
    name = "expandedOverlayNowPlaying"
    _settle(display, lambda: float(_slot(display, name).property("presence")) >= 1.0)
    _run(display, 200)
    lowest = [1.0, 1.0]

    def sample():
        slot = _slot(display, name)
        lowest[0] = min(lowest[0], float(slot.property("presence")))
        lowest[1] = min(lowest[1], float(slot.property("contentOpacity")))

    media.update(playbackState="playing")
    _run(display, 500, sample)
    assert lowest == [1.0, 1.0]                                    # no dip, no content crossfade


# --------------------------------------------------------------------------------------------- Always Show


@pytest.mark.qt
def test_always_show_keeps_both_up_and_a_change_fades_only_the_content(display):
    media = _Media()
    _draw(display, media=media, config=_config(preset={"always_show": True, "card": True},
                                               now_playing={"always_show": True}))
    _open(display)
    _settle(display, lambda: all(_prop(_slot(display, name), "presence") >= 1.0 for name in SLOTS))
    _run(display, 900)                               # well past every hold: still up
    assert all(_prop(_slot(display, name), "presence") >= 1.0 for name in SLOTS)
    card = _slot(display, "expandedOverlayPreset").findChild(QQuickItem, "expandedOverlayCard")
    assert card is not None and card.isVisible()
    lowest = {name: [1.0, 1.0] for name in SLOTS}

    def sample():
        for name in SLOTS:
            slot = _slot(display, name)
            lowest[name][0] = min(lowest[name][0], _prop(slot, "presence"))
            lowest[name][1] = min(lowest[name][1], _prop(slot, "contentOpacity"))

    display.scene.announce_visualizer_preset("Preset Echo")
    media.update(title="Track Two")
    _run(display, 700, sample)
    for name in SLOTS:
        assert lowest[name][0] >= 0.999, name        # never pops (nor even dips)
        assert lowest[name][1] < 0.2, name           # the content crossfades through
        assert _prop(_slot(display, name), "presence") >= 1.0
    assert _prop(_slot(display, "expandedOverlayPreset"), "contentText") == "Preset Echo"
    assert _prop(_slot(display, "expandedOverlayNowPlaying"), "contentTitle") == "Track Two"


# --------------------------------------------------------------------------- placement, stacking, priority


def _controls(root) -> dict[str, QRectF]:
    """The card's own controls where they show (the bottom tip at each of the three places a hover puts it)."""
    names = ("visualizerExpandGlyph", "visualizerExpandTooltip", "visualizerControlHint",
             "visualizerCameraResetGlyph", "visualizerPresetControls")
    found = {name: root.findChild(QQuickItem, name) for name in names}
    assert all(item is not None for item in found.values())
    rects = {name: _rect(item, root) for name, item in found.items() if item.width() > 0 and item.height() > 0}
    tip = root.findChild(QQuickItem, "visualizerPresetTooltip")
    reset, steps = found["visualizerCameraResetGlyph"], found["visualizerPresetControls"]
    for label, right in (("reset", reset.x() + reset.width()), ("previous", steps.x() + reset.width()),
                         ("next", steps.x() + steps.width())):
        root.setProperty("cameraActionTipX", right)
        rects[f"visualizerPresetTooltip@{label}"] = _rect(tip, root)
    root.setProperty("cameraActionTipX", 0.0)
    return rects


@pytest.mark.qt
@pytest.mark.parametrize("corner", ["top_left", "top_right", "bottom_left", "bottom_right"])
def test_every_corner_places_both_inside_the_safe_area_stacked_clear_of_the_controls(display, corner):
    options = {"corner": corner, "always_show": True, "card": True}
    _draw(display, media=_Media(), config=_config(preset=options,
                                                  now_playing={**options, "media_controls": True}))
    root = _root(display)
    root.setProperty("controlHintsAvailable", True)    # reserve the 3D hint's corner too
    _open(display)
    _settle(display, lambda: all(_prop(_slot(display, name), "presence") >= 1.0 for name in SLOTS))
    _run(display, 300)                                 # stack glides settle
    layer = _layer(display)
    inset = float(layer.property("safeInset"))
    preset, now_playing = (_rect(_slot(display, name), root) for name in SLOTS)
    controls = _controls(root)
    assert "visualizerControlHint" in controls          # the 3D hint image is loaded and measured
    for rect in (preset, now_playing):
        assert rect.left() >= inset - 0.5 and rect.right() <= root.width() - inset + 0.5
        assert rect.top() >= inset - 0.5 and rect.bottom() <= root.height() - inset + 0.5
        for name, control in controls.items():
            assert not rect.intersects(control), (corner, name)
    assert not preset.intersects(now_playing)          # stacked, never overlapping
    # The newer (Now Playing appeared second on entering) sits nearer the corner's edge.
    if corner.startswith("bottom"):
        assert now_playing.bottom() > preset.bottom()
    else:
        assert now_playing.top() < preset.top()
    right = corner.endswith("right")
    assert (preset.center().x() > root.width() / 2.0) is right


@pytest.mark.qt
def test_the_older_overlay_returns_to_the_edge_when_the_newer_retires(display):
    _draw(display, media=_Media(), config=_config(preset={"corner": "bottom_left", "always_show": True}))
    _open(display)
    preset = _slot(display, "expandedOverlayPreset")
    _settle(display, lambda: _shown(display, "expandedOverlayNowPlaying")
            and float(preset.property("stackShift")) > 0.0)
    _settle(display, lambda: not _shown(display, "expandedOverlayNowPlaying")
            and float(preset.property("stackShift")) == 0.0)


@pytest.mark.qt
def test_the_overlays_sit_below_the_cards_controls_the_osd_lane_and_the_menu(display):
    _draw(display, media=_Media(), config=_config(now_playing={"media_controls": True}))
    root = _root(display)
    loader = root.findChild(QQuickItem, "visualizerExpandedOverlays")
    for name in ("visualizerExpandGlyph", "visualizerCameraResetGlyph", "visualizerPresetControls"):
        control = root.findChild(QQuickItem, name)
        assert control.parentItem() is loader.parentItem() and control.z() > loader.z(), name
    scene_root = display.scene.scene_root
    visualizer_lane = scene_root.findChild(QQuickItem, "visualizerPresentationLoader")
    osd_lane = scene_root.findChild(QQuickItem, "systemAudioOSDForegroundHost")
    assert osd_lane.parentItem() is visualizer_lane.parentItem() and osd_lane.z() > visualizer_lane.z()
    # Only the Media Controls take input: no text or artwork handler can swallow the card's own gestures.
    layer = _layer(display)
    takers = [item for item in _visual(layer) if item.metaObject().className().startswith("QQuickMouseArea")]
    handlers = [child for item in _visual(layer) for child in item.children()
                if child.metaObject().className().startswith(("QQuickTapHandler", "QQuickHoverHandler",
                                                              "QQuickWheelHandler", "QQuickDragHandler"))]
    assert len(takers) == 3 and handlers == []
    # Each press area is its segment's (the shared bar loads it into the segment).
    assert all(item.parentItem().parentItem().objectName().startswith("expandedOverlayTransport_") for item in takers)
    assert all(item.property("consumesDoubleClick") is True for item in takers)


@pytest.mark.qt
def test_a_showing_osd_keeps_priority_over_an_overlay_beneath_it(display):
    from rendering.quick.widgets.host import OverlayWidgetGeometry
    from rendering.quick.widgets.system_audio_osd import (
        RetainedSystemAudioOSDPresentation,
        SystemAudioOSDConfig,
        SystemAudioOSDPresentationModel,
    )

    _draw(display, media=None, config=_config(preset={"always_show": True}))
    _open(display)
    slot = _slot(display, "expandedOverlayPreset")
    _settle(display, lambda: _prop(slot, "presence") >= 1.0)
    toast = _rect(slot, display.scene.scene_root)
    model = SystemAudioOSDPresentationModel(SystemAudioOSDConfig.from_widgets_mapping({"system_audio_osd": {}}),
                                            runtime_generation=1)
    osd = RetainedSystemAudioOSDPresentation(
        host=display.scene.ordinary_widget_host, model=model,
        geometry=OverlayWidgetGeometry(toast.x(), toast.y(), 320.0, 60.0))
    # The OSD root's own first fade (from QML's default) passes; then it rests hidden, the toast showing.
    _settle(display, lambda: osd.item.opacity() == 0.0 and _prop(slot, "osdYield") == 1.0)
    assert _prop(slot, "osdBlocked") is False and slot.isVisible()
    model._set_revealed(True)
    _settle(display, lambda: _prop(slot, "osdYield") == 0.0 and not slot.isVisible())
    assert _prop(slot, "interactive") is False
    model._set_revealed(False)
    _settle(display, lambda: _prop(slot, "osdYield") == 1.0 and slot.isVisible())
    osd.retire()


# ------------------------------------------------------------------------------------------- Media Controls


def _click(display, item) -> None:
    centre = item.mapToScene(QPointF(item.width() / 2.0, item.height() / 2.0))
    for kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
        event = QMouseEvent(kind, centre, centre, Qt.MouseButton.LeftButton,
                            Qt.MouseButton.LeftButton if kind == QEvent.Type.MouseButtonPress
                            else Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        QCoreApplication.sendEvent(display.window, event)
    display.render()


@pytest.mark.qt
def test_media_controls_emit_one_semantic_request_only_while_admitted(display):
    media = _Media()
    _draw(display, media=media, config=_config(now_playing={"media_controls": True, "always_show": True}))
    _open(display)
    slot = _slot(display, "expandedOverlayNowPlaying")
    _settle(display, lambda: _prop(slot, "presence") >= 1.0)
    requests = []
    display.scene.visualizer_overlay_transport_requested.connect(requests.append)
    root = _root(display)
    controls = {key: _named(root, f"expandedOverlayTransport_{key}") for key in ("previous", "play", "next")}
    assert all(control is not None for control in controls.values())
    root.setProperty("widgetGlowAdmitted", False)      # not admitted: no Interaction Mode / Ctrl
    _click(display, controls["next"])
    assert requests == []
    root.setProperty("widgetGlowAdmitted", True)
    for key in ("previous", "play", "next"):
        _click(display, controls[key])
    assert requests == ["previous", "play", "next"]
    media.update(canNext=False)                        # the model says it cannot: nothing is asked
    _click(display, controls["next"])
    assert requests == ["previous", "play", "next"]


def _qml_type(item) -> str:
    """The QML component an item instantiates (``Name_QMLTYPE_n`` -> ``Name``)."""
    return item.metaObject().className().split("_QMLTYPE_", 1)[0]


@pytest.mark.qt
def test_media_controls_are_the_media_cards_own_transport_bar_small(display):
    """Operator, 8 Nov: "it should have the media control bar just a small version". Now Playing's Media Controls are
    the one MediaTransportBar the Media card draws (shared, never a copy), below the card's size, and Fullscreen Edit's
    narrowest text box still holds the whole bar."""
    from core.settings.defaults import get_default_settings
    from rendering.quick.widgets.host import OverlayWidgetGeometry
    from rendering.quick.widgets.media import (
        MediaPresentationConfig,
        MediaPresentationModel,
        MediaPresentationStyle,
        RetainedMediaPresentation,
    )

    widgets = get_default_settings()["widgets"]
    config = MediaPresentationConfig.from_widgets_mapping(widgets)
    model = MediaPresentationModel(config, MediaPresentationStyle.project(config, widgets.get("shadows", {})),
                                   display.factory.media_artwork_provider)
    card = RetainedMediaPresentation(host=display.scene.ordinary_widget_host, model=model,
                                     geometry=OverlayWidgetGeometry(20.0, 20.0, 600.0, 300.0))
    try:
        display.render()
        card_bar = card.item.findChild(QQuickItem, "mediaControlsRow")
        assert card_bar is not None and _qml_type(card_bar) == "MediaTransportBar"

        # A text box narrower than anything (Fullscreen Edit's side handle) is floored at the bar's width.
        from dataclasses import replace

        model._replace_snapshot(replace(model._snapshot, has_track=True, title="Track One", artist="Artist One",
                                        playback_state="playing"))
        _draw(display, media=model, config=_config(now_playing={"media_controls": True, "always_show": True,
                                                                "text_width": 0.01}))
        _open(display)
        slot = _slot(display, "expandedOverlayNowPlaying")
        _settle(display, lambda: _prop(slot, "presence") >= 1.0)
        layer = _layer(display)
        bar = _named(layer, "expandedOverlayMediaControls")
        assert bar is not None and _qml_type(bar) == _qml_type(card_bar)
        # The card's bar parts (three segments of the one bar), each pressing with the overlay's own keys.
        segments = [_named(bar, f"expandedOverlayTransport_{key}") for key in ("previous", "play", "next")]
        assert all(segment is not None and segment.parentItem().parentItem() is bar for segment in segments)
        # The card's own look, from the one Media model.
        for name in ("surfaceColor", "iconColor", "separatorColor", "shadowEnabled", "shadowColor"):
            assert bar.property(name) == card_bar.property(name), name
        assert bar.property("playing") is card_bar.property("playing") is True
        # Small: shorter and much narrower than the card's bar.
        assert 0.0 < bar.height() < card_bar.height() and bar.width() < card_bar.width() / 2.0
        text_block = _named(layer, "expandedOverlayNowPlayingText")
        assert text_block.width() >= bar.width() - 0.5
        assert _rect(bar, layer).left() >= _rect(text_block, layer).left() - 0.5
    finally:
        display.scene.set_visualizer_overlay_media_model(None)
        card.retire()
        model.deleteLater()


def _manager_route(unit, *, menu=False, admission=True):
    from engine.display_manager import DisplayManager

    calls = []
    unit.runtime = SimpleNamespace(input_controller=SimpleNamespace(input_state=SimpleNamespace(
        admission_open=admission, context_menu_active=menu)))
    host = SimpleNamespace(_quick_visualizer_unit=unit,
                           _route_quick_media_transport=lambda source, key: calls.append((source, key)) or True)
    return (lambda target, key: DisplayManager._route_expanded_overlay_transport(host, target, key)), calls


def test_the_display_manager_sends_a_press_to_the_one_media_transport_route():
    unit = SimpleNamespace(is_retired=False)
    route, calls = _manager_route(unit)
    for key in ("previous", "play", "next"):
        assert route(unit, key) is True
    assert calls == [(unit, "previous"), (unit, "play"), (unit, "next")]
    # Never another display's press, an unknown action, a retired unit, under the menu or with admission closed.
    assert route(unit, "volume_up") is False and route(SimpleNamespace(is_retired=False), "next") is False
    unit.is_retired = True
    assert route(unit, "next") is False
    menu_unit, closed_unit = SimpleNamespace(is_retired=False), SimpleNamespace(is_retired=False)
    menu_route, menu_calls = _manager_route(menu_unit, menu=True)
    closed_route, closed_calls = _manager_route(closed_unit, admission=False)
    assert menu_route(menu_unit, "next") is False and closed_route(closed_unit, "next") is False
    assert menu_calls == [] and closed_calls == [] and len(calls) == 3


# ------------------------------------------------------------------------------------ the one Media source


@pytest.mark.qt
def test_the_overlays_add_no_media_consumer_and_leave_no_subscription(display):
    """The real Media model with a recording runtime service: drawing, every event and undrawing call nothing on it
    (no second Media query, lease or refresh) and leave its signal exactly as subscribed as before."""
    from dataclasses import replace

    from core.settings.defaults import get_default_settings
    from rendering.quick.widgets.media import (
        MediaPresentationConfig,
        MediaPresentationModel,
        MediaPresentationStyle,
    )

    class _Service:
        def __init__(self) -> None:
            self.calls = []

        def __getattr__(self, name):
            def record(*args, **kwargs):
                self.calls.append(name)
                return True
            return record

    service = _Service()
    widgets = get_default_settings()["widgets"]
    config = MediaPresentationConfig.from_widgets_mapping(widgets)
    style = MediaPresentationStyle.project(config, get_default_settings()["widgets"].get("shadows", {}))
    model = MediaPresentationModel(config, style, display.factory.media_artwork_provider, runtime_service=service)
    model._replace_snapshot(replace(model._snapshot, has_track=True, title="Track One", artist="Artist One",
                                    playback_state="playing"))
    signal = SIGNAL("stateChanged()")
    baseline = model.receivers(signal)
    _draw(display, media=model)
    _open(display)
    for cycle in range(3):
        display.scene.announce_visualizer_preset(f"Preset {cycle}")
        model._replace_snapshot(replace(model._snapshot, title=f"Track {cycle + 2}"))
        _run(display, 150)
        display.scene.set_visualizer_expanded_overlays_drawn(False)
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        display.render()
        assert model.receivers(signal) == baseline
        display.scene.set_visualizer_expanded_overlays_drawn(True)
        display.render()
    assert service.calls == []
    display.scene.set_visualizer_overlay_media_model(None)
    display.scene.set_visualizer_expanded_overlays_drawn(False)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    display.render()
    assert model.receivers(signal) == baseline
    model.deleteLater()


# ------------------------------------------------------------------------------------ the owner's edges


@pytest.mark.qt
def test_the_owner_admits_the_overlays_exactly_while_drawn_display_wide_and_on(qt_app):
    from PySide6.QtWidgets import QApplication

    from rendering.quick.runtime import QuickDisplayRuntime
    from rendering.quick.scene_controller import QuickSceneFactory
    from rendering.quick.state import QuickWindowPolicy
    from tests._visualizer_presentation import make_visualizer_owner

    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(screen_index=0, runtime_generation=778, screen=QApplication.primaryScreen(),
                                  scene_factory=factory,
                                  window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False))
    owner = make_visualizer_owner(runtime, bar_count=32, initial_mode="extruded_bubble")
    scene = runtime.scene_controller
    try:
        owner.bind(engine_generation=1, activation_id=1)
        assert scene.visualizer_expanded_overlays_drawn is False
        owner.set_expanded_display(True)
        assert scene.visualizer_expanded_overlays_drawn is True
        owner.set_display_power(False)                    # parked displays hold no overlay
        assert scene.visualizer_expanded_overlays_drawn is False
        owner.set_display_power(True)
        assert scene.visualizer_expanded_overlays_drawn is True
        owner.set_expanded_display(False)
        assert scene.visualizer_expanded_overlays_drawn is False
        owner.set_expanded_display(True)
    finally:
        owner.retire()
        assert scene.visualizer_expanded_overlays_drawn is False   # they leave with the owner
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_the_owner_flips_the_overlays_at_the_fade_through_midpoint(qt_app):
    """Animated, the overlays appear with the first display-wide record (the card at the bottom of its fade) and
    leave with the first ordinary one on the way back: never while the other side is drawn."""
    from unittest.mock import patch

    from rendering.quick.scene_controller import QuickSceneController
    from tools.expanded_visualizer_evidence import looped_fixture, owner_replay

    edges = []
    original = QuickSceneController.set_visualizer_expanded_overlays_drawn

    def recording(self, drawn):
        presentation = self.visualizer_item.presentation
        edges.append((bool(drawn), tuple(presentation.outer_rect), float(presentation.scene_fade)))
        original(self, drawn)

    with patch.object(QuickSceneController, "set_visualizer_expanded_overlays_drawn", recording):
        result = owner_replay(looped_fixture(loops=6), "extruded_bubble", expand_at=30, collapse_at=250,
                              animate=True)
    width, height = result["display"][2:]
    assert [drawn for drawn, _rect_, _fade in edges] == [True, False]
    (_on, entered_rect, entered_fade), (_off, left_rect, left_fade) = edges
    assert entered_rect[2] > width * 0.9 and entered_rect[3] > height * 0.9      # the display-wide card...
    assert left_rect[2] < width * 0.5                                            # ...and the ordinary one
    assert entered_fade < 0.5 and left_fade < 0.5                               # both at the fade's bottom
