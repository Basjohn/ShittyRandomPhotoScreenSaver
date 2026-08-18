"""Production-integration bars for --diag-p4-stages.

Every test here would have FAILED on 2b62fc80c7465da4b7387d9b93e59ef296e29534,
where 30 helper tests passed while the diagnostic never armed: the ring was
constructed but ``initialize()`` was never called, the ResourceManager API was
invented, query-id normalization was missing, stage cleanup was nested inside
the timer-query branch, and the Qt observer re-attached an old sampled paint to
later unsampled compositions.
"""
from __future__ import annotations

import inspect

import pytest

from rendering.gl_stage_timestamps import STAGE_MARKERS, GLStageTimestampRing


class _GL:
    GL_TIMESTAMP = 0x8E28
    GL_QUERY_RESULT = 0x8866
    GL_QUERY_RESULT_AVAILABLE = 0x8867
    GL_TIME_ELAPSED = 0x88BF

    def __init__(self, gen_mode="sequence"):
        self._next = 1
        self.gen_mode = gen_mode
        self.deleted = []

    def glGenQueries(self, n):
        ids = [self._next + i for i in range(n)]
        self._next += n
        if self.gen_mode == "scalar" and n == 1:
            return ids[0]
        return ids

    def glQueryCounter(self, handle, target):
        pass

    def glGetQueryObjectuiv(self, handle, pname, out):
        out[0] = 1

    def glGetQueryObjectui64v(self, handle, pname, out):
        out[0] = handle * 1_000_000

    def glDeleteQueries(self, n, handles):
        self.deleted.extend(handles)


class TestInitializationIsActuallyWired:
    """Cause 1: the ring was constructed but never initialized."""

    def test_lifecycle_initializes_the_stage_ring_on_the_owner_context(self):
        from rendering.gl_compositor_pkg import gl_lifecycle

        source = inspect.getsource(gl_lifecycle)
        assert "_gl_stage_timestamps" in source
        assert "stage_ring.initialize(" in source, (
            "the stage ring must be initialized at the compositor-context seam; "
            "the first runtime emitted zero records because this was missing"
        )

    def test_initialization_emits_a_bounded_init_record(self):
        from rendering.gl_compositor_pkg import gl_lifecycle

        source = inspect.getsource(gl_lifecycle)
        assert "[PERF][P4_STAGES][INIT]" in source
        assert "timestamp_queries=" in source

    def test_failed_initialization_is_loud_not_silent(self):
        from rendering.gl_compositor_pkg import gl_lifecycle

        source = inspect.getsource(gl_lifecycle)
        assert "UNAVAILABLE" in source, (
            "a requested-but-failed diagnostic must warn, never silently produce "
            "an uninterpretable zero-record run"
        )

    def test_successful_initialization_allocates_the_full_fixed_set(self):
        gl = _GL()
        ring = GLStageTimestampRing(owner="t", generation=1, capacity=4)
        assert ring.initialize(gl, context=object()) is True
        assert ring.supported is True
        assert len(ring._handles) == 4 * len(STAGE_MARKERS) == 20


class TestQueryIdNormalization:
    """Cause 3: glGenQueries(1)[0] is not a safe PyOpenGL contract."""

    @pytest.mark.parametrize("mode", ["sequence", "scalar"])
    def test_both_pyopengl_return_forms_allocate(self, mode):
        ring = GLStageTimestampRing(owner="t", generation=1, capacity=1)
        assert ring.initialize(_GL(gen_mode=mode), context=object()) is True
        assert len(ring._handles) == len(STAGE_MARKERS)


class TestResourceManagerContract:
    """Cause 2: register_gl_resource/release_gl_resource do not exist."""

    def test_helper_uses_the_real_resource_manager_api(self):
        from rendering import gl_stage_timestamps

        source = inspect.getsource(gl_stage_timestamps)
        assert "register_gl_handle" in source
        assert "release_tracking" in source
        assert "register_gl_resource" not in source
        assert "release_gl_resource" not in source

    def test_registration_reaches_a_real_manager_shaped_object(self):
        class _RealShaped:
            def __init__(self):
                self.registered = []
                self.released = []

            def register_gl_handle(self, handle, kind, **kwargs):
                self.registered.append((handle, kind, kwargs.get("format")))
                return "res-%s" % handle

            def release_tracking(self, resource_id):
                self.released.append(resource_id)

        manager = _RealShaped()
        gl = _GL()
        ring = GLStageTimestampRing(owner="t", generation=7, capacity=1)
        ring.initialize(gl, context=object(), resource_manager=manager)

        assert len(manager.registered) == len(STAGE_MARKERS)
        assert manager.registered[0][1] == "query"
        assert manager.registered[0][2] == "GL_TIMESTAMP"

        ring.cleanup(gl)
        assert len(manager.released) == len(STAGE_MARKERS)


class TestPacketCapacityCannotWedge:
    """A fallback/partial packet must release capacity."""

    def test_abandoned_packet_releases_its_slot(self):
        gl = _GL()
        ring = GLStageTimestampRing(owner="t", generation=1, capacity=1)
        ring.initialize(gl, context=object())

        assert ring.begin_frame(
            scene_generation=1, frame_index=1, transition="burn", render_path="pending"
        )
        ring.mark(gl, "t0")
        ring.abandon_frame()

        assert ring.begin_frame(
            scene_generation=1, frame_index=2, transition="burn", render_path="pending"
        ), "abandoned packet did not release its slot"

    def test_only_issued_markers_are_awaited(self):
        gl = _GL()
        ring = GLStageTimestampRing(owner="t", generation=1, capacity=1)
        ring.initialize(gl, context=object())
        ring.begin_frame(
            scene_generation=1, frame_index=1, transition="burn", render_path="pending"
        )
        ring.mark(gl, "t0")
        ring.mark(gl, "t1")
        ring.end_frame()
        ring.poll(gl)

        done = ring.take_completed()
        assert len(done) == 1, "a never-issued marker blocked packet completion"
        assert set(done[0].results_ns) == {"t0", "t1"}


class TestCleanupIsIndependentOfTheTimerRing:
    def test_cleanup_path_is_not_nested_under_timer_queries(self):
        from rendering.gl_compositor_pkg import gl_lifecycle

        source = inspect.getsource(gl_lifecycle.cleanup_gl_pipeline)
        lines = source.splitlines()
        stage_lines = [
            line for line in lines if "stage_ring.cleanup(" in line
        ]
        assert stage_lines, "stage cleanup call missing from cleanup_gl_pipeline"
        # Structural, not positional: the call must sit at the function's own
        # try-level indentation, never nested inside the timer-query branch.
        for line in stage_lines:
            indent = len(line) - len(line.lstrip())
            assert indent <= 12, (
                "stage cleanup is nested too deeply and is therefore conditional "
                "on the timer ring existing"
            )

    def test_stage_queries_are_deleted_when_timer_ring_is_absent(self):
        gl = _GL()
        ring = GLStageTimestampRing(owner="t", generation=1, capacity=1)
        ring.initialize(gl, context=object())
        assert ring.has_live_queries() is True
        ring.cleanup(gl)
        assert ring.has_live_queries() is False
        assert len(gl.deleted) == len(STAGE_MARKERS)


class TestQtObserverConsumesPaintOnce:
    """Cause 4: an old sampled paint was reused by later unsampled composes."""

    def _observer(self):
        from rendering.gl_compositor_pkg.gpu_delivery_association import (
            QtCompositionObserver,
        )

        return QtCompositionObserver()

    def test_sampled_paint_cannot_be_reused_across_unsampled_compositions(self):
        obs = self._observer()

        obs.record_paint_end(
            scene_generation=1, frame_index=1, transition="burn", paint_end_ts=0.0
        )
        obs.on_about_to_compose(0.002)
        obs.on_frame_swapped(0.004)
        first = obs.take_records()
        assert len(first) == 1
        assert first[0]["frame_index"] == 1

        # Seven unsampled compose/swap pairs with NO new sampled paint.
        for step in range(7):
            base = 0.100 + step * 0.020
            obs.on_about_to_compose(base)
            obs.on_frame_swapped(base + 0.005)

        assert obs.take_records() == [], (
            "unsampled compositions re-attached to the consumed paint and would "
            "manufacture hundreds-of-ms ages"
        )
        assert obs.counters()["compose_without_paint"] == 7

        obs.record_paint_end(
            scene_generation=1, frame_index=9, transition="burn", paint_end_ts=0.300
        )
        obs.on_about_to_compose(0.302)
        obs.on_frame_swapped(0.304)
        second = obs.take_records()
        assert len(second) == 1
        assert second[0]["frame_index"] == 9
        assert second[0]["paint_end_to_swap_ms"] < 100.0, "manufactured age"


class TestRenderPathAttribution:
    """Cause 6: _use_shaders is not attribution authority."""

    def test_initial_path_is_unresolved_not_derived_from_use_shaders(self):
        from rendering.gl_compositor_pkg import paint as paint_mod

        widget = type("W", (), {"_use_shaders": False})()
        assert paint_mod._stage_render_path(widget) == "pending"

    def test_successful_shader_path_recorded_despite_use_shaders_false(self):
        from rendering.gl_compositor_pkg import paint as paint_mod
        from rendering.gl_stage_timestamps import StagePacket

        packet = StagePacket(
            scene_generation=1, frame_index=1, transition="burn", render_path="pending"
        )
        ring = type("R", (), {"_active": packet})()
        widget = type("W", (), {"_gl_stage_timestamps": ring, "_use_shaders": False})()

        paint_mod.stage_set_render_path(widget, "shader:burn")
        assert packet.render_path == "shader:burn"

    def test_shader_dispatch_records_the_actual_successful_path(self):
        from rendering.gl_compositor_pkg import shader_dispatch

        source = inspect.getsource(shader_dispatch)
        assert "_stage_path(comp, " in source
        assert "retained_base_shader" in source

    def test_report_exposes_render_path(self):
        from rendering.gl_compositor_pkg import gpu_delivery_association

        source = inspect.getsource(gpu_delivery_association.format_stage_report_lines)
        assert "render_path=%s" in source, (
            "render_path must be interpretable from the log, not only the packet"
        )
