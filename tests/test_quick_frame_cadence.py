"""tools/quick_frame_cadence.py: layer T's frame-cycle measure and late-frame attribution, on synthetic frames."""

from tools.quick_frame_cadence import cadence, phases, requests, split

MS = 1_000_000


def _frame(begin_ms, render_ms=0.2):
    b = int(begin_ms * MS)
    return {"begin": b, "quick_before_synchronizing": b + int(0.05 * MS),
            "quick_after_synchronizing": b + int(0.1 * MS), "quick_before_rendering": b + int(0.1 * MS),
            "quick_after_rendering": b + int((0.1 + render_ms) * MS)}


def _frames():
    # 11 ms cadence with one 20 ms gap after the frame at 33 ms.
    return [_frame(t) for t in (0, 11, 22, 33, 53, 64)]


def test_cadence_counts_the_late_interval():
    figures = cadence([f["begin"] for f in _frames()])
    assert figures["frames"] == 6
    assert figures["over_16_7"] == 1
    assert figures["over_25"] == 0
    assert abs(figures["max"] - 20.0) < 1e-6


def test_split_puts_the_late_time_after_rendering():
    figures = split(_frames(), 16.7)
    assert figures["late"] == 1
    assert figures["after_render_to_next_median"] > 19.0
    assert figures["begin_to_sync_median"] < 0.1


def test_phases_report_render_duration_for_late_frames():
    figures = phases(_frames(), 16.7)
    assert figures["late"] == 1
    assert abs(figures["late_render_median"] - 0.2) < 1e-6


def test_requests_classify_a_waiting_present_request_and_a_missing_publish():
    frames = _frames()
    events = [(int(35 * MS), "logical_publish"), (int(36 * MS), "gui_present_request_ready")]
    assert requests(events, frames, 16.7) == {"late": 1, "no_publish_in_gap": 0,
                                              "request_ready_over_8ms_before_begin": 1}
    assert requests([], frames, 16.7)["no_publish_in_gap"] == 1
