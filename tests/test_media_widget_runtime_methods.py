from __future__ import annotations

from types import SimpleNamespace

from widgets.media_widget import MediaWidget


class _PollStageStub:
    def __init__(self) -> None:
        self._current_poll_stage = 0
        self._polls_at_current_stage = 0
        self._poll_intervals = [1000, 2000, 2500]
        self.ensure_timer_calls = []

    def _ensure_timer(self, *, force: bool = False) -> None:
        self.ensure_timer_calls.append(bool(force))


def test_media_widget_advance_poll_stage_restarts_timer() -> None:
    stub = _PollStageStub()

    MediaWidget._advance_poll_stage(stub)

    assert stub._current_poll_stage == 1
    assert stub._polls_at_current_stage == 0
    assert stub.ensure_timer_calls == [True]


def test_media_widget_reset_poll_stage_restarts_timer_only_when_needed() -> None:
    stub = _PollStageStub()
    stub._current_poll_stage = 2

    MediaWidget._reset_poll_stage(stub)

    assert stub._current_poll_stage == 0
    assert stub._polls_at_current_stage == 0
    assert stub.ensure_timer_calls == [True]

    MediaWidget._reset_poll_stage(stub)

    assert stub.ensure_timer_calls == [True]


def test_media_widget_track_identity_includes_artwork_key() -> None:
    stub = SimpleNamespace(
        _compute_artwork_key=lambda info: ("artwork", len(info.artwork or b"")),
    )
    info = SimpleNamespace(
        title=" Track ",
        artist=" Artist ",
        album=" Album ",
        state=SimpleNamespace(value="playing"),
        artwork=b"frame-bytes",
    )

    identity = MediaWidget._compute_track_identity(stub, info)

    assert identity == ("track", "artist", "album", "playing", ("artwork", 11))
