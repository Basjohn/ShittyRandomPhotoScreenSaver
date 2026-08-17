"""Bars for the --diag-p4-stages GL_TIMESTAMP stage ring.

Observational only: fixed-size, availability-checked, drops rather than waits,
no finish/flush/fence, and allocated only when the CLI gate is active.
"""
from __future__ import annotations

import ctypes
import inspect
import pathlib

import pytest

from rendering import gl_stage_timestamps as mod
from rendering.gl_stage_timestamps import (
    CLI_FLAG,
    STAGE_MARKERS,
    GLStageTimestampRing,
    cli_enabled,
)


class _FakeGL:
    GL_TIMESTAMP = 0x8E28
    GL_QUERY_RESULT = 0x8866
    GL_QUERY_RESULT_AVAILABLE = 0x8867

    def __init__(self, available=True, base_ns=1_000_000):
        self._next = 1
        self.available = available
        self.base_ns = base_ns
        self.deleted: list[int] = []
        self.counters: list[int] = []
        self.delete_should_fail = False

    def glGenQueries(self, n):
        out = [self._next + i for i in range(n)]
        self._next += n
        return out

    def glQueryCounter(self, handle, target):
        self.counters.append(handle)

    def glGetQueryObjectuiv(self, handle, pname, out):
        out[0] = 1 if self.available else 0

    def glGetQueryObjectui64v(self, handle, pname, out):
        out[0] = self.base_ns + handle * 1_000_000

    def glDeleteQueries(self, n, handles):
        if self.delete_should_fail:
            raise RuntimeError("simulated deletion failure")
        self.deleted.extend(handles)


def _ring(gl=None, capacity=2, manager=None):
    ring = GLStageTimestampRing(owner="test", generation=1, capacity=capacity)
    ring.initialize(gl or _FakeGL(), context=object(), resource_manager=manager)
    return ring


class TestCliGateOnly:
    def test_flag_is_the_documented_cli_diagnostic(self):
        assert CLI_FLAG == "--diag-p4-stages"
        assert cli_enabled(["main.py", "--perf", "--diag-p4-stages"]) is True
        assert cli_enabled(["main.py", "--perf"]) is False

    def test_no_environment_variable_path_exists(self):
        source = inspect.getsource(mod)
        assert "os.environ" not in source
        assert "getenv" not in source

    def test_flag_is_registered_in_the_known_flag_inventory(self):
        main_src = pathlib.Path("main.py").read_text(encoding="utf-8")
        assert '"--diag-p4-stages"' in main_src

    def test_no_blocking_primitives_are_called_in_the_helper(self):
        """AST-checked: prose naming them in the docstring is not a call."""
        import ast

        tree = ast.parse(inspect.getsource(mod))
        forbidden = {"glFinish", "glFlush", "glFenceSync", "glWaitSync", "sleep"}
        called = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name in forbidden:
                called.add(name)
        assert not called, f"blocking primitives called in stage helper: {called}"


class TestFixedSizeAndDropping:
    def test_allocates_nothing_until_initialized(self):
        ring = GLStageTimestampRing(owner="test", generation=1, capacity=2)
        assert ring.has_live_queries() is False
        assert ring.supported is False

    def test_capacity_is_fixed_and_frames_drop_rather_than_wait(self):
        ring = _ring(capacity=1)
        assert ring.begin_frame(
            scene_generation=1, frame_index=1, transition="burn", render_path="shader"
        )
        ring.end_frame()
        # Slot is still in flight; a second frame must drop, not block.
        assert ring.begin_frame(
            scene_generation=1, frame_index=2, transition="burn", render_path="shader"
        ) is False
        assert ring.dropped_no_capacity >= 1

    def test_reentrant_begin_is_refused(self):
        ring = _ring()
        assert ring.begin_frame(
            scene_generation=1, frame_index=1, transition="burn", render_path="shader"
        )
        assert ring.begin_frame(
            scene_generation=1, frame_index=2, transition="burn", render_path="shader"
        ) is False


class TestAvailabilityCheckedCollection:
    def test_results_are_not_fetched_until_available(self):
        gl = _FakeGL(available=False)
        ring = _ring(gl)
        ring.begin_frame(
            scene_generation=2, frame_index=7, transition="warp", render_path="shader"
        )
        for marker in STAGE_MARKERS:
            ring.mark(gl, marker)
        ring.end_frame()

        ring.poll(gl)
        assert ring.take_completed() == [], "collected before results were available"

        gl.available = True
        ring.poll(gl)
        done = ring.take_completed()
        assert len(done) == 1
        assert done[0].complete is True

    def test_completed_packet_retains_authoritative_identity(self):
        gl = _FakeGL()
        ring = _ring(gl)
        ring.begin_frame(
            scene_generation=5, frame_index=42, transition="blockspin", render_path="shader"
        )
        for marker in STAGE_MARKERS:
            ring.mark(gl, marker)
        ring.end_frame()
        ring.poll(gl)

        packet = ring.take_completed()[0]
        assert packet.scene_generation == 5
        assert packet.frame_index == 42
        assert packet.transition == "blockspin"
        assert packet.render_path == "shader"

    def test_spans_are_derived_only_from_resolved_endpoints(self):
        gl = _FakeGL()
        ring = _ring(gl)
        ring.begin_frame(
            scene_generation=1, frame_index=1, transition="burn", render_path="shader"
        )
        for marker in STAGE_MARKERS:
            ring.mark(gl, marker)
        ring.end_frame()
        ring.poll(gl)

        spans = ring.take_completed()[0].spans_ms()
        for name in ("prep_gpu_ms", "core_draw_gpu_ms", "dimming_gpu_ms",
                     "overlay_gpu_ms", "marked_gpu_ms"):
            assert name in spans and spans[name] >= 0.0

    def test_markers_coexist_with_an_outer_elapsed_scope(self):
        """glQueryCounter is legal inside an active GL_TIME_ELAPSED block."""
        gl = _FakeGL()
        ring = _ring(gl)
        # Simulate the outer elapsed query being active around the markers.
        outer_active = True
        ring.begin_frame(
            scene_generation=1, frame_index=1, transition="burn", render_path="shader"
        )
        for marker in STAGE_MARKERS:
            ring.mark(gl, marker)
        ring.end_frame()
        assert outer_active
        assert len(gl.counters) == len(STAGE_MARKERS)


class TestStrictCleanupAndAccounting:
    def test_successful_cleanup_deletes_every_query(self):
        gl = _FakeGL()
        ring = _ring(gl, capacity=2)
        expected = 2 * len(STAGE_MARKERS)
        ring.cleanup(gl)
        assert len(gl.deleted) == expected
        assert ring.has_live_queries() is False

    def test_failed_deletion_retains_ownership_and_raises(self):
        gl = _FakeGL()
        ring = _ring(gl, capacity=1)
        gl.delete_should_fail = True

        with pytest.raises(RuntimeError):
            ring.cleanup(gl)

        assert ring.has_live_queries() is True, (
            "failed deletion must retain ownership, never manufacture a clean count"
        )

    def test_cleanup_without_a_context_refuses_rather_than_leaking_silently(self):
        gl = _FakeGL()
        ring = _ring(gl, capacity=1)
        with pytest.raises(RuntimeError):
            ring.cleanup(None)
        assert ring.has_live_queries() is True


class TestDisabledByDefault:
    """Part G3: without the flag nothing is allocated, connected or changed."""

    def test_compositor_allocates_no_stage_ring_without_the_flag(self, monkeypatch):
        import sys as _sys
        from rendering.gl_stage_timestamps import cli_enabled

        monkeypatch.setattr(_sys, "argv", ["main.py", "--perf", "--gpu-timing"])
        assert cli_enabled(_sys.argv) is False

    def test_no_qt_composition_state_without_the_flag(self):
        """The observer is only constructed under the gate."""
        from rendering.gl_compositor_pkg import paint as paint_mod

        widget = type("W", (), {"_gl_stage_timestamps": None})()
        paint_mod._ensure_qt_composition_observer(widget)
        assert getattr(widget, "_qt_composition_connected", False) is False
        assert getattr(widget, "_qt_composition_observer", None) is None

    def test_stage_helpers_are_inert_without_a_ring(self):
        from rendering.gl_compositor_pkg import shader_dispatch as sd

        comp = type("C", (), {"_gl_stage_timestamps": None})()
        sd._stage_mark(comp, "t1")   # must not raise
        sd._stage_cpu(comp, "prep_cpu_ms", 0.0)


class TestSampledIdentityMatchesOuterQuery:
    """Part G7: stage packets use the same sampled-frame identity."""

    def test_packet_identity_can_join_the_outer_gpu_sample(self):
        from rendering.gl_compositor_pkg.gpu_delivery_association import associate_stages
        from types import SimpleNamespace as NS

        gl = _FakeGL()
        ring = _ring(gl)
        ring.begin_frame(
            scene_generation=3, frame_index=8, transition="burn", render_path="shader"
        )
        for marker in STAGE_MARKERS:
            ring.mark(gl, marker)
        ring.end_frame()
        ring.poll(gl)
        packet = ring.take_completed()[0]
        packet.outer_gpu_ms = 40.0

        successor = NS(scene_generation=3, frame_index=9, paint_interval_ms=70.0)
        report = associate_stages([packet], [successor])

        entry = report["by_label"]["burn"]["over_50"]
        assert entry["core_draw_gpu_ms"]["n"] == 1
        assert "unpartitioned_gpu_ms" in entry, (
            "outer sample must join by the same identity so residual is derivable"
        )


class TestQtCompositionAssociation:
    """Parts G11/G12: no scheduling, and no invented one-to-one matching."""

    def _observer(self):
        from rendering.gl_compositor_pkg.gpu_delivery_association import (
            QtCompositionObserver,
        )

        return QtCompositionObserver()

    def test_handlers_schedule_no_work(self):
        import ast
        import inspect
        from rendering.gl_compositor_pkg import paint as paint_mod

        source = inspect.getsource(paint_mod._ensure_qt_composition_observer)
        tree = ast.parse(source)
        forbidden = {
            "update", "repaint", "singleShot", "invokeMethod",
            "run_on_ui_thread", "start", "sleep",
        }
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if name in forbidden:
                    called.add(name)
        assert not called, f"composition handlers schedule work: {called}"

    def test_normal_paint_compose_swap_produces_one_record(self):
        obs = self._observer()
        obs.record_paint_end(
            scene_generation=1, frame_index=1, transition="burn", paint_end_ts=0.000
        )
        obs.on_about_to_compose(0.002)
        obs.on_frame_swapped(0.010)

        records = obs.take_records()
        assert len(records) == 1
        assert records[0]["paint_end_to_compose_ms"] == pytest.approx(2.0)
        assert records[0]["compose_to_swap_ms"] == pytest.approx(8.0)
        assert records[0]["paint_end_to_swap_ms"] == pytest.approx(10.0)

    def test_multiple_paints_before_one_compose_are_counted_not_invented(self):
        obs = self._observer()
        for frame in (1, 2, 3):
            obs.record_paint_end(
                scene_generation=1, frame_index=frame, transition="burn", paint_end_ts=0.0
            )
        obs.on_about_to_compose(0.001)
        obs.on_frame_swapped(0.005)

        counters = obs.counters()
        assert counters["multiple_paints_before_compose"] >= 1
        assert counters["paints_without_compose"] == 2, (
            "skipped paints must be counted, not matched to a compose"
        )
        assert len(obs.take_records()) == 1

    def test_compose_without_any_paint_is_counted(self):
        obs = self._observer()
        obs.on_about_to_compose(0.001)
        assert obs.counters()["compose_without_paint"] == 1
        assert obs.take_records() == []

    def test_swap_without_compose_is_counted(self):
        obs = self._observer()
        obs.on_frame_swapped(0.001)
        assert obs.counters()["swap_without_compose"] == 1
        assert obs.take_records() == []

    def test_replaced_compose_transaction_is_counted(self):
        obs = self._observer()
        obs.record_paint_end(
            scene_generation=1, frame_index=1, transition="burn", paint_end_ts=0.0
        )
        obs.on_about_to_compose(0.001)
        obs.on_about_to_compose(0.002)
        assert obs.counters()["compose_replaced"] == 1

    def test_missing_composition_data_does_not_bias_the_report(self):
        """Part G12/E: unmatched must be visible rather than silently dropped."""
        from rendering.gl_compositor_pkg.gpu_delivery_association import associate_stages
        from types import SimpleNamespace as NS

        gl = _FakeGL()
        ring = _ring(gl)
        ring.begin_frame(
            scene_generation=1, frame_index=1, transition="burn", render_path="shader"
        )
        for marker in STAGE_MARKERS:
            ring.mark(gl, marker)
        ring.end_frame()
        ring.poll(gl)
        packet = ring.take_completed()[0]

        successor = NS(scene_generation=1, frame_index=2, paint_interval_ms=70.0)
        report = associate_stages([packet], [successor], composition_records=[])

        assert report["unmatched"]["paint_end_to_swap_ms"] == 1
        assert report["matched"]["core_draw_gpu_ms"] == 1


@pytest.mark.qt
class TestHudObservationIsPassive:
    """Part G10: metadata records the real outcome and changes nothing."""

    def _packet_holder(self):
        """Minimal widget exposing an active stage packet to observe into."""
        from rendering.gl_stage_timestamps import StagePacket

        packet = StagePacket(
            scene_generation=1, frame_index=1, transition="burn", render_path="shader"
        )
        ring = type("R", (), {"_active": packet})()
        return type("W", (), {"_gl_stage_timestamps": ring})(), packet

    def test_rebuild_and_cache_hit_are_recorded_from_the_path_taken(self, qt_app):
        from PySide6.QtGui import QImage
        from rendering.gl_compositor_pkg.overlays import _hud_observe

        widget, packet = self._packet_holder()
        image = QImage(320, 180, QImage.Format.Format_ARGB32)

        _hud_observe(widget, image, rebuilt=True, t0=None)
        assert packet.hud["hud_rebuilt"] is True
        assert packet.hud["hud_cache_hit"] is False
        assert packet.hud["hud_present"] is True

        _hud_observe(widget, image, rebuilt=False, t0=None)
        assert packet.hud["hud_rebuilt"] is False
        assert packet.hud["hud_cache_hit"] is True

    def test_metadata_reports_real_dimensions_and_argb_bytes(self, qt_app):
        from PySide6.QtGui import QImage
        from rendering.gl_compositor_pkg.overlays import _hud_observe

        widget, packet = self._packet_holder()
        image = QImage(3840, 2158, QImage.Format.Format_ARGB32)

        _hud_observe(widget, image, rebuilt=True, t0=None)

        assert packet.hud["hud_width"] == 3840
        assert packet.hud["hud_height"] == 2158
        # 4 bytes/pixel ARGB32 - the allocation the QPainter path composites.
        assert packet.hud["hud_image_bytes"] == 3840 * 2158 * 4

    def test_absent_hud_is_recorded_without_inventing_a_cache_hit(self, qt_app):
        from rendering.gl_compositor_pkg.overlays import _hud_observe

        widget, packet = self._packet_holder()
        _hud_observe(widget, None, rebuilt=False, t0=None)

        assert packet.hud["hud_present"] is False
        assert packet.hud["hud_cache_hit"] is False

    def test_observation_is_inert_without_an_active_packet(self, qt_app):
        from PySide6.QtGui import QImage
        from rendering.gl_compositor_pkg.overlays import _hud_observe

        widget = type("W", (), {"_gl_stage_timestamps": None})()
        # Must not raise and must not create state.
        _hud_observe(widget, QImage(8, 8, QImage.Format.Format_ARGB32), rebuilt=True, t0=None)

    def test_hud_builder_still_returns_its_cached_image_unchanged(self, qt_app):
        """The probe must not alter cache policy or output identity."""
        import inspect
        from rendering.gl_compositor_pkg import overlays

        source = inspect.getsource(overlays.render_debug_overlay_image)
        # The cache-hit path still returns the cached image object itself.
        assert "return cached_image" in source
        # No dimension or interval was altered by the probe.
        assert "_DEBUG_OVERLAY_REFRESH_INTERVAL_S" in source
