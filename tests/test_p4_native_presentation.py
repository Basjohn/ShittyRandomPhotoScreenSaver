"""Bars for the native-presentation P4 diagnostics.

Covers the DWM composition-timing probe, the present-context state probe, and
the --diag-p4-no-perf-hud control. All are observational: nothing here may
block, flush, or alter presentation.
"""
from __future__ import annotations

import ctypes
import inspect
import sys

import pytest

from rendering import dwm_timing
from rendering.dwm_timing import (
    DELTA_FIELDS,
    DWM_TIMING_INFO,
    QPC_DELTA_FIELDS,
    DwmSnapshot,
    DwmTimingProbe,
    associate_dwm,
    qpc_delta_ms,
)


class TestDwmStructLayout:
    def test_struct_matches_the_documented_field_set(self):
        names = {name for name, _ in DWM_TIMING_INFO._fields_}
        for required in (
            "cbSize", "rateRefresh", "qpcRefreshPeriod", "qpcVBlank", "qpcCompose",
            "cRefresh", "cFrame", "cFrameSubmitted", "cFrameConfirmed",
            "cFrameDisplayed", "cFramesLate", "cFramesDropped", "cFramesMissed",
            "cRefreshesDisplayed", "cRefreshesPresented",
        ):
            assert required in names, f"missing DWM_TIMING_INFO field: {required}"

    def test_cbsize_is_settable_and_struct_is_non_trivial(self):
        info = DWM_TIMING_INFO()
        info.cbSize = ctypes.sizeof(DWM_TIMING_INFO)
        assert info.cbSize == ctypes.sizeof(DWM_TIMING_INFO)
        # Mixed 32/64-bit fields under natural alignment; a trivially small size
        # would mean the layout collapsed.
        assert ctypes.sizeof(DWM_TIMING_INFO) > 200

    def test_ratio_subfields_are_addressable(self):
        info = DWM_TIMING_INFO()
        info.rateRefresh.uiNumerator = 60
        info.rateRefresh.uiDenominator = 1
        assert info.rateRefresh.uiNumerator == 60
        assert info.rateRefresh.uiDenominator == 1


class TestNoBlockingCalls:
    def test_dwmflush_is_never_called(self):
        source = inspect.getsource(dwm_timing)
        tree = __import__("ast").parse(source)
        for node in __import__("ast").walk(tree):
            if isinstance(node, __import__("ast").Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                assert name != "DwmFlush", "DwmFlush blocks until composition"

    def test_no_sleeps_or_waits(self):
        source = inspect.getsource(dwm_timing)
        for forbidden in ("sleep(", "WaitFor", "glFinish", "glFlush"):
            assert forbidden not in source

    def test_hwnd_is_null_per_windows_81_requirement(self):
        source = inspect.getsource(dwm_timing.DwmTimingProbe.capture)
        assert "DwmGetCompositionTimingInfo(None" in source


class TestUnsupportedPath:
    def test_non_windows_reports_unsupported_without_raising(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        probe = DwmTimingProbe()
        assert probe.supported is False
        assert probe.reason == "not_windows"

    def test_capture_on_unsupported_records_an_explicit_snapshot(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        probe = DwmTimingProbe()
        assert probe.capture(scene_generation=1, frame_index=1) is False

        snapshots = probe.take_snapshots()
        assert len(snapshots) == 1
        assert snapshots[0].supported is False
        assert snapshots[0].values == {}, "unsupported must not invent zero fields"

    def test_unsupported_snapshots_are_counted_not_silently_dropped(self):
        snaps = [
            DwmSnapshot(1, 1, {}, supported=False, reason="not_windows"),
            DwmSnapshot(1, 2, {}, supported=False, reason="not_windows"),
        ]
        report = associate_dwm(snaps, frequency=10_000_000)
        assert report["unsupported"] == 2
        assert report["rows"] == []


class TestIdentityJoin:
    def _snap(self, frame, **values):
        base = {name: 0 for name in DELTA_FIELDS}
        base.update({name: 0 for name in QPC_DELTA_FIELDS})
        base["qpcRefreshPeriod"] = 166_666
        base["rateRefreshNumerator"] = 60
        base["rateRefreshDenominator"] = 1
        base.update(values)
        return DwmSnapshot(1, frame, base, supported=True, reason="supported")

    def test_n_to_n_plus_one_join_reports_refresh_advancement(self):
        snaps = [
            self._snap(1, cRefresh=100, cFramesDisplayed=10),
            self._snap(2, cRefresh=103, cFramesDisplayed=11),
        ]
        report = associate_dwm(snaps, frequency=10_000_000)

        assert len(report["rows"]) == 1
        row = report["rows"][0]
        assert row["frame_index"] == 1
        assert row["cRefresh"] == 3, "a severe gap should span multiple refreshes"

    def test_generation_is_part_of_the_identity(self):
        a = DwmSnapshot(1, 1, {name: 0 for name in DELTA_FIELDS}, True, "supported")
        b = DwmSnapshot(2, 2, {name: 0 for name in DELTA_FIELDS}, True, "supported")
        report = associate_dwm([a, b], frequency=10_000_000)
        assert report["rows"] == []
        assert report["unmatched"] == 2

    def test_qpc_conversion_uses_the_reported_frequency(self):
        snaps = [
            self._snap(1, qpcCompose=0),
            self._snap(2, qpcCompose=10_000_000),  # exactly 1 s at 10 MHz
        ]
        row = associate_dwm(snaps, frequency=10_000_000)["rows"][0]
        assert row["qpcCompose_ms"] == pytest.approx(1000.0)

    def test_missing_frequency_yields_none_not_zero(self):
        assert qpc_delta_ms(0, 1000, None) is None
        assert qpc_delta_ms(0, 1000, 0) is None


class TestNoPerfHudControl:
    def test_flag_is_registered_in_the_cli_inventory(self):
        import pathlib

        main_src = pathlib.Path("main.py").read_text(encoding="utf-8")
        assert '"--diag-p4-no-perf-hud"' in main_src

    def test_no_environment_variable_path(self):
        from rendering.gl_compositor_pkg import overlays

        import ast

        tree = ast.parse(inspect.getsource(overlays._no_perf_hud_requested))
        # AST, not substring: the docstring legitimately contains the word
        # "environment-variable" while the code must never read one.
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "environ":
                pytest.fail("HUD control reads an environment variable")
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                assert name != "getenv", "HUD control reads an environment variable"
        assert "sys.argv" in inspect.getsource(overlays._no_perf_hud_requested)

    def test_flag_absent_by_default(self, monkeypatch):
        from rendering.gl_compositor_pkg import overlays

        monkeypatch.setattr(sys, "argv", ["main.py", "--perf", "--gpu-timing"])
        assert overlays._no_perf_hud_requested() is False

    def test_flag_suppresses_only_the_hud_build(self, monkeypatch):
        from rendering.gl_compositor_pkg import overlays

        monkeypatch.setattr(
            sys, "argv", ["main.py", "--perf", "--diag-p4-no-perf-hud"]
        )
        assert overlays._no_perf_hud_requested() is True

        built = []
        monkeypatch.setattr(
            overlays, "_build_debug_overlay_payload",
            lambda *a, **k: built.append(1),
        )

        widget = type("W", (), {"_gl_stage_timestamps": None})()
        assert overlays.render_debug_overlay_image(widget) is None
        assert built == [], "HUD payload must not be built under the control flag"

    def test_flag_does_not_disable_perf_telemetry(self):
        """It suppresses drawing only; PERF gating is untouched."""
        from rendering.gl_compositor_pkg import overlays

        source = inspect.getsource(overlays.render_debug_overlay_image)
        # The PERF gate remains a separate, later check.
        assert "is_perf_metrics_enabled()" in source
        suppression = source.index("_no_perf_hud_requested()")
        perf_gate = source.index("is_perf_metrics_enabled()")
        assert suppression < perf_gate

    def test_flag_state_is_recorded_in_the_init_record(self):
        from rendering.gl_compositor_pkg import gl_lifecycle

        source = inspect.getsource(gl_lifecycle)
        assert "no_perf_hud=%d" in source


class TestPresentContextProbe:
    def test_probe_runs_once_and_is_bounded(self):
        from rendering.gl_compositor_pkg import paint as paint_mod

        widget = type("W", (), {})()
        paint_mod._probe_present_context_once(widget)
        assert widget._p4_present_context_probed is True

        # A second call must be inert - this is a state probe, not a per-frame log.
        paint_mod._probe_present_context_once(widget)
        assert widget._p4_present_context_probed is True

    def test_probe_mutates_no_presentation_state(self):
        import ast

        from rendering.gl_compositor_pkg import paint as paint_mod

        tree = ast.parse(inspect.getsource(paint_mod._probe_present_context_once))
        forbidden = {"wglSwapIntervalEXT", "setSwapInterval", "setFormat", "update",
                     "repaint", "makeCurrent", "doneCurrent", "swapBuffers"}
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if name in forbidden:
                    called.add(name)
        assert not called, f"present-context probe mutates state: {called}"

    def test_probe_is_used_as_state_not_duration(self):
        from rendering.gl_compositor_pkg import paint as paint_mod

        source = inspect.getsource(paint_mod._probe_present_context_once)
        assert "perf_counter" not in source, (
            "the present-context probe must not be a duration source"
        )
