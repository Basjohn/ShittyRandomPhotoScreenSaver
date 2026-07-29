from __future__ import annotations

import threading
from types import SimpleNamespace

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize
from PySide6.QtGui import QColor, QImage, QPixmap

from core.media.media_controller import MediaPlaybackState, MediaTrackInfo
from core.threading.manager import ThreadManager
from widgets.media.artwork_layout import compute_artwork_frame_size
from widgets.media_widget import MediaWidget, PreparedArtwork


def _image_bytes(width: int, height: int) -> bytes:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("#cc5500"))
    payload = QByteArray()
    buffer = QBuffer(payload)
    assert buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    buffer.close()
    return bytes(payload)


def test_compute_artwork_frame_size_uses_cover_frame_for_landscape_video(qt_app) -> None:
    pixmap = QPixmap.fromImage(QImage(640, 360, QImage.Format.Format_ARGB32))

    frame = compute_artwork_frame_size(pixmap, 200)

    assert frame == QSize(200, 200)


def test_compute_artwork_frame_size_keeps_square_art_square(qt_app) -> None:
    pixmap = QPixmap.fromImage(QImage(512, 512, QImage.Format.Format_ARGB32))

    frame = compute_artwork_frame_size(pixmap, 200)

    assert frame == QSize(200, 200)


def test_decode_artwork_pixmap_uses_reader_and_normalizes_dpr(qt_app) -> None:
    payload = _image_bytes(640, 360)

    pixmap = MediaWidget._decode_artwork_pixmap(SimpleNamespace(), payload)

    assert pixmap is not None
    assert pixmap.width() == 640
    assert pixmap.height() == 360
    assert pixmap.devicePixelRatioF() == 1.0


def test_unique_artwork_key_decodes_once(monkeypatch) -> None:
    payload = b"unique-artwork"
    key = MediaWidget._compute_artwork_payload_key(payload)
    decode_calls = []
    image = QImage(8, 8, QImage.Format.Format_ARGB32)

    monkeypatch.setattr(
        MediaWidget,
        "_decode_artwork_image",
        staticmethod(lambda _payload: decode_calls.append(_payload) or image),
    )

    first = MediaWidget._prepare_artwork_payload(
        payload,
        key,
        known_artwork_keys=frozenset(),
    )
    second = MediaWidget._prepare_artwork_payload(
        payload,
        key,
        known_artwork_keys=frozenset({key}),
    )

    assert isinstance(first, PreparedArtwork)
    assert first.image is image
    assert second.image is None
    assert decode_calls == [payload]


def test_applied_and_pending_artwork_keys_are_both_treated_as_decoded(
    monkeypatch,
) -> None:
    payload = b"already-applied"
    applied_key = MediaWidget._compute_artwork_payload_key(payload)
    pending_key = (99, "pending")
    decode_calls = []

    monkeypatch.setattr(
        MediaWidget,
        "_decode_artwork_image",
        staticmethod(lambda data: decode_calls.append(data)),
    )

    prepared = MediaWidget._prepare_artwork_payload(
        payload,
        applied_key,
        known_artwork_keys=frozenset({applied_key, pending_key}),
    )

    assert prepared.image is None
    assert decode_calls == []


def test_refresh_async_decodes_qimage_in_existing_worker_job(
    qt_app,
    monkeypatch,
) -> None:
    payload = _image_bytes(48, 48)
    info = MediaTrackInfo(
        title="Track",
        artist="Artist",
        album="Album",
        state=MediaPlaybackState.PLAYING,
        artwork=payload,
    )
    worker_thread_ids: list[int] = []
    ui_callbacks = []
    display_thread_ids: list[int] = []
    original_decode = MediaWidget._decode_artwork_image

    monkeypatch.setattr(
        MediaWidget,
        "_decode_artwork_image",
        staticmethod(
            lambda data: (
                worker_thread_ids.append(threading.get_ident()),
                original_decode(data),
            )[1]
        ),
    )
    monkeypatch.setattr(
        ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda callback: ui_callbacks.append(callback)),
    )

    class _Controller:
        def get_current_track(self):
            return info

    class _TaskResult:
        success = True

        def __init__(self, result):
            self.result = result

    class _ThreadManager:
        def submit_io_task(self, worker, callback):
            def _run():
                callback(_TaskResult(worker()))

            thread = threading.Thread(target=_run)
            thread.start()
            thread.join()

    widget = MediaWidget(
        controller=_Controller(),
        thread_manager=_ThreadManager(),
    )
    try:
        widget._update_display = lambda *_args, **_kwargs: display_thread_ids.append(
            threading.get_ident()
        )
        widget._refresh_async()

        assert len(ui_callbacks) == 1
        ui_callbacks.pop()()

        assert worker_thread_ids
        assert worker_thread_ids[0] != threading.get_ident()
        assert display_thread_ids == [threading.get_ident()]
    finally:
        widget.cleanup()
        widget.close()
