from __future__ import annotations

import logging
import weakref
from types import SimpleNamespace

from PySide6.QtGui import QImage

from core.media.media_controller import MediaPlaybackState, MediaTrackInfo
import rendering.display_image_ops as display_image_ops
from rendering.display_widget import DisplayWidget
from widgets.media import display_update
from widgets.media_widget import MediaWidget, PreparedArtwork


def _prepared(key: tuple[int, str]) -> PreparedArtwork:
    image = QImage(24, 24, QImage.Format.Format_ARGB32)
    return PreparedArtwork(key=key, image=image, decode_ms=0.75)


def _set_transition_probe(monkeypatch, busy):
    monkeypatch.setattr(
        MediaWidget,
        "_has_transition_work_on_any_display",
        classmethod(lambda cls: bool(busy[0])),
    )


def test_artwork_is_stored_not_applied_during_transition(qt_app, monkeypatch):
    busy = [True]
    _set_transition_probe(monkeypatch, busy)
    widget = MediaWidget()
    pixmap_calls = []
    widget._create_artwork_pixmap = lambda image: pixmap_calls.append(image)

    try:
        widget._artwork_update_generation = 1
        applied = widget._accept_prepared_artwork(
            _prepared((100, "a")),
            1,
            refresh_layout_after_apply=False,
        )

        assert applied is False
        assert widget._pending_artwork is not None
        assert widget._pending_artwork.key == (100, "a")
        assert widget._artwork_pixmap is None
        assert pixmap_calls == []
    finally:
        widget.cleanup()
        widget.close()


def test_transition_coalesces_to_newest_artwork(qt_app, monkeypatch):
    busy = [True]
    _set_transition_probe(monkeypatch, busy)
    widget = MediaWidget()

    try:
        for generation, key in enumerate(
            ((100, "a"), (200, "b"), (300, "c")),
            start=1,
        ):
            widget._artwork_update_generation = generation
            widget._accept_prepared_artwork(
                _prepared(key),
                generation,
                refresh_layout_after_apply=False,
            )

        assert widget._pending_artwork is not None
        assert widget._pending_artwork.key == (300, "c")
        assert widget._pending_artwork_generation == 3
        assert widget._artwork_coalesced_count == 2
    finally:
        widget.cleanup()
        widget.close()


def test_unchanged_poll_promotes_pending_artwork_before_diff_gate(
    qt_app,
    monkeypatch,
):
    busy = [True]
    _set_transition_probe(monkeypatch, busy)
    widget = MediaWidget()
    monkeypatch.setattr(MediaWidget, "_instances", weakref.WeakSet([widget]))

    old_info = MediaTrackInfo(
        title="Track",
        artist="Artist",
        album="Album",
        state=MediaPlaybackState.PLAYING,
        artwork=b"old-art",
    )
    new_info = MediaTrackInfo(
        title="Track",
        artist="Artist",
        album="Album",
        state=MediaPlaybackState.PLAYING,
        artwork=b"new-art",
    )
    old_key = widget._compute_artwork_key(old_info)
    new_key = widget._compute_artwork_key(new_info)

    try:
        widget._fade_in_completed = True
        widget._applied_artwork_key = old_key
        widget._last_track_identity = widget._compute_track_identity(old_info)
        widget._last_metadata_identity = widget._compute_metadata_identity(old_info)

        widget._artwork_update_generation = 1
        display_update.update_display(
            widget,
            new_info,
            prepared_artwork=_prepared(new_key),
            artwork_generation=1,
        )
        assert widget._pending_artwork is not None
        assert widget._pending_artwork_generation == 1
        decoded_image = widget._pending_artwork.image
        assert decoded_image is not None

        # The next same-track poll correctly skips another decode. It must still
        # promote the retained decoded image before metadata diff-gating returns.
        widget._artwork_update_generation = 2
        display_update.update_display(
            widget,
            new_info,
            prepared_artwork=PreparedArtwork(new_key, None, 0.0),
            artwork_generation=2,
        )
        assert widget._pending_artwork is not None
        assert widget._pending_artwork_generation == 2
        assert widget._pending_artwork.image is decoded_image

        busy[0] = False
        MediaWidget._flush_pending_artwork_when_all_displays_idle()

        assert widget._pending_artwork is None
        assert widget._applied_artwork_key == new_key
        assert widget._artwork_pixmap is not None
    finally:
        widget.cleanup()
        widget.close()


def test_artwork_lifecycle_telemetry_is_material_event_only(
    qt_app,
    monkeypatch,
    caplog,
):
    busy = [True]
    _set_transition_probe(monkeypatch, busy)
    monkeypatch.setattr("widgets.media_widget.is_perf_metrics_enabled", lambda: True)
    widget = MediaWidget()
    monkeypatch.setattr(MediaWidget, "_instances", weakref.WeakSet([widget]))

    try:
        with caplog.at_level(logging.INFO):
            widget._artwork_update_generation = 1
            widget._accept_prepared_artwork(
                _prepared((100, "a")),
                1,
                refresh_layout_after_apply=False,
            )

            # Same-key polling promotes ownership but intentionally emits no
            # additional lifecycle record.
            widget._artwork_update_generation = 2
            widget._accept_prepared_artwork(
                PreparedArtwork((100, "a"), None, 0.0),
                2,
                refresh_layout_after_apply=False,
            )

            widget._artwork_update_generation = 3
            widget._accept_prepared_artwork(
                _prepared((200, "b")),
                3,
                refresh_layout_after_apply=False,
            )

            busy[0] = False
            MediaWidget._flush_pending_artwork_when_all_displays_idle()

        messages = [
            record.getMessage()
            for record in caplog.records
            if "[PERF][MEDIA_ARTWORK]" in record.getMessage()
        ]
        assert sum("event=queued" in message for message in messages) == 1
        assert sum("event=replaced" in message for message in messages) == 1
        assert sum("event=flushing" in message for message in messages) == 1
        assert sum("event=applied" in message for message in messages) == 1
        assert any("key_id=b" in message for message in messages)
    finally:
        widget.cleanup()
        widget.close()


def test_transition_reversal_discards_stale_pending_artwork(qt_app, monkeypatch):
    busy = [False]
    _set_transition_probe(monkeypatch, busy)
    widget = MediaWidget()

    try:
        applied = _prepared((100, "applied"))
        widget._artwork_update_generation = 1
        assert widget._accept_prepared_artwork(
            applied,
            1,
            refresh_layout_after_apply=False,
        )
        original_pixmap = widget._artwork_pixmap

        busy[0] = True
        widget._artwork_update_generation = 2
        widget._accept_prepared_artwork(
            _prepared((200, "pending")),
            2,
            refresh_layout_after_apply=False,
        )
        assert widget._pending_artwork is not None

        # The newest media snapshot returned to the artwork that is already
        # displayed. It must cancel the pending replacement rather than let
        # the stale intermediate key flush after the transition.
        widget._artwork_update_generation = 3
        widget._accept_prepared_artwork(
            PreparedArtwork((100, "applied"), None, 0.0),
            3,
            refresh_layout_after_apply=False,
        )

        assert widget._pending_artwork is None
        assert widget._artwork_pixmap is original_pixmap

        busy[0] = False
        MediaWidget._flush_pending_artwork_when_all_displays_idle()
        assert widget._artwork_pixmap is original_pixmap
        assert widget._applied_artwork_key == (100, "applied")
    finally:
        widget.cleanup()
        widget.close()


def test_no_artwork_fade_starts_until_all_displays_idle(qt_app, monkeypatch):
    busy = [True]
    _set_transition_probe(monkeypatch, busy)
    widget = MediaWidget()
    widget._has_seen_first_track = True
    fades = []
    widget._start_artwork_fade_in = lambda: fades.append("fade")
    monkeypatch.setattr(MediaWidget, "_instances", weakref.WeakSet([widget]))

    try:
        widget._artwork_update_generation = 1
        widget._accept_prepared_artwork(
            _prepared((100, "a")),
            1,
            refresh_layout_after_apply=False,
        )

        MediaWidget._flush_pending_artwork_when_all_displays_idle()
        assert fades == []
        assert widget._pending_artwork is not None

        busy[0] = False
        MediaWidget._flush_pending_artwork_when_all_displays_idle()
        assert fades == ["fade"]
        assert widget._pending_artwork is None
        assert widget._artwork_pixmap is not None
    finally:
        widget.cleanup()
        widget.close()


def test_no_media_artwork_clear_waits_for_transition_idle(qt_app, monkeypatch):
    busy = [False]
    _set_transition_probe(monkeypatch, busy)
    widget = MediaWidget()
    monkeypatch.setattr(MediaWidget, "_instances", weakref.WeakSet([widget]))

    try:
        widget._artwork_update_generation = 1
        widget._accept_prepared_artwork(
            _prepared((100, "a")),
            1,
            refresh_layout_after_apply=False,
        )
        assert widget._artwork_pixmap is not None

        busy[0] = True
        widget._clear_artwork_for_missing_media()

        assert widget._artwork_pixmap is not None
        assert widget._pending_artwork is not None
        assert widget._pending_artwork.key == (0, "")

        busy[0] = False
        MediaWidget._flush_pending_artwork_when_all_displays_idle()

        assert widget._artwork_pixmap is None
        assert widget._applied_artwork_key == (0, "")
    finally:
        widget.cleanup()
        widget.close()


def test_final_display_transition_completion_flushes_all_media_artwork(
    qt_app,
    monkeypatch,
):
    media0 = MediaWidget()
    media1 = MediaWidget()
    media0._has_seen_first_track = True
    media1._has_seen_first_track = True
    media0._start_artwork_fade_in = lambda: None
    media1._start_artwork_fade_in = lambda: None
    monkeypatch.setattr(
        MediaWidget,
        "_instances",
        weakref.WeakSet([media0, media1]),
    )

    display0 = SimpleNamespace(media_widget=media0, busy=True)
    display1 = SimpleNamespace(media_widget=media1, busy=True)
    display0.has_transition_work_pending = lambda: display0.busy
    display1.has_transition_work_pending = lambda: display1.busy

    monkeypatch.setattr(
        DisplayWidget,
        "get_all_instances",
        classmethod(lambda cls: [display0, display1]),
    )
    monkeypatch.setattr(
        "widgets.media_widget.Shiboken.isValid",
        lambda _obj: True,
    )
    monkeypatch.setattr(
        display_image_ops,
        "_on_transition_finished",
        lambda display, *_args, **_kwargs: setattr(display, "busy", False),
    )

    try:
        for widget, key in ((media0, (100, "a")), (media1, (200, "b"))):
            widget._artwork_update_generation = 1
            widget._pending_artwork = _prepared(key)
            widget._pending_artwork_generation = 1
            widget._pending_artwork_deferred = True

        DisplayWidget._on_transition_finished(display0)
        assert media0._pending_artwork is not None
        assert media1._pending_artwork is not None

        DisplayWidget._on_transition_finished(display1)
        assert media0._pending_artwork is None
        assert media1._pending_artwork is None
        assert media0._artwork_pixmap is not None
        assert media1._artwork_pixmap is not None
    finally:
        media0.cleanup()
        media1.cleanup()
        media0.close()
        media1.close()


def test_destroyed_media_widget_discards_pending_qimage_once(
    qt_app,
    monkeypatch,
    caplog,
):
    widget = MediaWidget()
    widget._artwork_update_generation = 1
    widget._pending_artwork = _prepared((100, "a"))
    widget._pending_artwork_generation = 1
    instances = weakref.WeakSet([widget])
    monkeypatch.setattr(MediaWidget, "_instances", instances)
    monkeypatch.setattr("widgets.media_widget.is_perf_metrics_enabled", lambda: True)
    monkeypatch.setattr(
        MediaWidget,
        "_has_transition_work_on_any_display",
        classmethod(lambda cls: False),
    )
    monkeypatch.setattr(
        "widgets.media_widget.Shiboken.isValid",
        lambda candidate: candidate is not widget,
    )

    with caplog.at_level(logging.INFO):
        MediaWidget._flush_pending_artwork_when_all_displays_idle()
        MediaWidget._flush_pending_artwork_when_all_displays_idle()

    assert widget._pending_artwork is None
    assert widget not in instances
    discarded = [
        record.getMessage()
        for record in caplog.records
        if "[PERF][MEDIA_ARTWORK] event=discarded" in record.getMessage()
        and "reason=widget_destroyed" in record.getMessage()
    ]
    assert len(discarded) == 1
    widget.close()
