"""The operator's cursor-at-exit observer: exit edges and verdicts from synthetic samples (no Win32 reads)."""

from __future__ import annotations

from tools.cursor_exit_observer import Observer, Sample, is_saver_window

SAVER = (0x100, "Qt6111QWindowToolSaveBits", 4242, "SRPSS.exe")
DESKTOP = (0x200, "WorkerW", 900, "explorer.exe")


def _sample(t_ms: float, cursor: str, under=SAVER, *, pointer=(10, 10), buttons=()) -> Sample:
    return Sample(t_ns=int(t_ms * 1e6), cursor=cursor, flags=1, pointer=pointer, buttons=tuple(buttons),
                  capture=(), clip=None, foreground=under, under=under)


def _run(samples) -> Observer:
    observer = Observer()
    for sample in samples:
        observer.feed(sample)
    return observer


def test_saver_windows_are_qt_windows_of_a_saver_process():
    assert is_saver_window(SAVER, ("srpss",))
    assert not is_saver_window(DESKTOP, ("srpss",))
    assert not is_saver_window((1, "Qt6111QWindowIcon", 5, "OtherApp.exe"), ("srpss",))


def test_a_hand_frozen_until_a_click_is_reported_as_such():
    observer = _run([
        _sample(0, "hand"),
        _sample(10, "hand", DESKTOP),                       # the saver window left: exit edge
        _sample(800, "hand", DESKTOP),
        _sample(900, "hand", DESKTOP, buttons=("left",)),   # the operator clicks
        _sample(910, "arrow", DESKTOP),
    ])
    assert len(observer.exits) == 1
    assert observer.exits[0].cursor_at_exit == "hand"
    assert observer.exits[0].verdict().startswith("cursor after exit: hand, changed to arrow only after click")


def test_a_move_and_an_immediate_arrow_are_told_apart():
    moved = _run([
        _sample(0, "custom:0x1"),
        _sample(10, "custom:0x1", DESKTOP),
        _sample(400, "custom:0x1", DESKTOP, pointer=(11, 10)),
        _sample(410, "arrow", DESKTOP, pointer=(12, 10)),
    ])
    assert moved.exits[0].verdict() == (
        "cursor after exit: custom:0x1, changed to arrow after 400 ms (after a pointer move, no click)")
    clean = _run([_sample(0, "hand"), _sample(10, "arrow", DESKTOP)])
    assert clean.exits[0].verdict() == "cursor after exit: arrow, changed to arrow after 0 ms"


def test_the_saver_process_ending_is_an_exit_edge_too():
    observer = Observer()
    observer.feed(_sample(0, "hand"))
    observer.feed(_sample(10, "hand"), saver_alive=False)    # process gone while still the window under it
    observer.feed(_sample(20, "arrow", DESKTOP))
    assert [watch.reason for watch in observer.exits] == ["saver process ended"]
    assert observer.exits[0].arrow_ns is not None
