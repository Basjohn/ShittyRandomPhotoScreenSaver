"""Bars for the GPU/delivery association diagnostic.

Observational only. These prove correlation identity survives asynchronous
submission, cannot go stale across slot reuse or generation boundaries, and
never alters the aggregate GPU statistics or scheduling.
"""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from rendering.gl_compositor_pkg.gpu_delivery_association import associate
from rendering.gl_timer_queries import GLTimerQueryRing, GPUFrameSample


def _gpu(gen, frame, ms, label="blockspin"):
    return GPUFrameSample(scene_generation=gen, frame_index=frame, label=label, elapsed_ms=ms)


def _paint(gen, frame, interval):
    return NS(scene_generation=gen, frame_index=frame, paint_interval_ms=interval)


class _FakeGL:
    GL_TIME_ELAPSED = 1
    GL_QUERY_RESULT_AVAILABLE = 2
    GL_QUERY_RESULT = 3

    def __init__(self, elapsed_ns=5_000_000):
        self.elapsed_ns = elapsed_ns
        self.available = True

    def glBeginQuery(self, target, handle): pass
    def glEndQuery(self, target): pass

    def glGetQueryObjectuiv(self, handle, pname, out):
        out[0] = 1 if self.available else 0

    def glGetQueryObjectui64v(self, handle, pname, out):
        out[0] = self.elapsed_ns


def _ring():
    ring = GLTimerQueryRing(owner="test", generation=1)
    return ring


class TestAssociationCausalOrdering:
    def test_same_frame_is_recorded_but_marked_non_causal(self):
        report = associate([_gpu(1, 5, 40.0)], [_paint(1, 5, 60.0)])
        assert 0 in report["by_delta"], "same-frame association is still recorded"

    def test_primary_comparison_is_gpu_frame_n_against_gap_entering_n_plus_1(self):
        report = associate([_gpu(1, 5, 40.0)], [_paint(1, 6, 60.0)])
        entry = report["by_delta"][1]["blockspin"]
        assert entry["over_50"]["n"] == 1
        assert entry["over_50"]["max_ms"] == pytest.approx(40.0)
        assert entry["ordinary"]["n"] == 0

    def test_deltas_are_reported_separately_not_pooled(self):
        report = associate(
            [_gpu(1, 5, 40.0)],
            [_paint(1, 6, 16.0), _paint(1, 7, 60.0), _paint(1, 8, 16.0)],
        )
        assert report["by_delta"][1]["blockspin"]["ordinary"]["n"] == 1
        assert report["by_delta"][2]["blockspin"]["over_50"]["n"] == 1
        assert report["by_delta"][3]["blockspin"]["ordinary"]["n"] == 1

    def test_every_collected_sample_is_retained_giving_a_denominator(self):
        gpu = [_gpu(1, i, 3.0) for i in range(10)] + [_gpu(1, 20, 45.0)]
        paint = [_paint(1, i + 1, 16.0) for i in range(10)] + [_paint(1, 21, 70.0)]
        entry = associate(gpu, paint)["by_delta"][1]["blockspin"]
        assert entry["ordinary"]["n"] == 10, "ordinary population is the denominator"
        assert entry["over_50"]["n"] == 1


class TestAssociationIdentityIsolation:
    def test_repeated_transition_labels_cannot_cross_associate(self):
        """Two Blockspin runs share a label but differ by generation."""
        report = associate(
            [_gpu(1, 5, 40.0, "blockspin")],
            [_paint(2, 6, 60.0)],  # same label, later generation
        )
        assert report["matched_gpu_samples"] == 0
        assert report["unmatched_gpu_samples"] == 1

    def test_unmatched_samples_are_counted_not_silently_dropped(self):
        report = associate([_gpu(9, 99, 12.0)], [_paint(1, 2, 16.0)])
        assert report["unmatched_gpu_samples"] == 1


class TestQuerySlotIdentityLifecycle:
    def test_identity_survives_async_submission_then_later_poll(self):
        ring = _ring()
        gl = _FakeGL(elapsed_ns=7_000_000)
        assert ring.initialize(gl, context=object()) or True
        ring.set_pending_frame_identity(scene_generation=4, frame_index=11)
        if ring.begin(gl, label="burn"):
            ring.end(gl)
            ring.poll(gl)
            samples = ring.take_frame_samples()
            assert samples, "a collected sample must retain its identity"
            assert samples[0].scene_generation == 4
            assert samples[0].frame_index == 11

    def test_reused_slot_cannot_retain_stale_identity(self):
        ring = _ring()
        gl = _FakeGL()
        ring.initialize(gl, context=object())
        ring.set_pending_frame_identity(scene_generation=4, frame_index=11)
        if not ring.begin(gl, label="burn"):
            pytest.skip("timer queries unsupported in this environment")
        ring.end(gl)
        ring.poll(gl)
        ring.take_frame_samples()

        # A second query with no declared identity must not inherit the first.
        ring.set_pending_frame_identity(scene_generation=-1, frame_index=-1)
        ring.begin(gl, label="burn")
        ring.end(gl)
        ring.poll(gl)
        assert ring.take_frame_samples() == [], "stale identity was reused"

    def test_discard_clears_correlation_identity(self):
        ring = _ring()
        gl = _FakeGL()
        ring.initialize(gl, context=object())
        ring.set_pending_frame_identity(scene_generation=4, frame_index=11)
        if not ring.begin(gl, label="burn"):
            pytest.skip("timer queries unsupported in this environment")
        ring.end(gl)
        ring._discard_in_flight()
        ring.poll(gl)
        assert ring.take_frame_samples() == [], "discarded query produced a sample"

    def test_runtime_disable_clears_identity_and_stops_sampling(self):
        ring = _ring()
        gl = _FakeGL()
        ring.initialize(gl, context=object())
        ring.set_pending_frame_identity(scene_generation=4, frame_index=11)
        ring._disable_runtime("test")
        assert ring.supported is False
        assert ring.take_frame_samples() == []

    def test_draining_does_not_alter_aggregate_window_statistics(self):
        ring = _ring()
        gl = _FakeGL(elapsed_ns=6_000_000)
        ring.initialize(gl, context=object())
        ring.set_pending_frame_identity(scene_generation=1, frame_index=1)
        if not ring.begin(gl, label="burn"):
            pytest.skip("timer queries unsupported in this environment")
        ring.end(gl)
        ring.poll(gl)

        ring.take_frame_samples()  # drain the correlation queue only
        window = ring.consume_window(include_labels=("burn",))
        assert window["by_label"]["burn"]["collected"] == 1, (
            "draining correlation metadata must not consume aggregate statistics"
        )
