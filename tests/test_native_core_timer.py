"""N2.6's per-pass GPU timer (native/core: gpu_timer, load_pass, frame_driver; rendering/native/gpu_timing.py;
native/core/python/timer_check.py and timer_analysis.py), the parts that need no built module:

- the harness's judgements (scaling, the empty bracket, agreement, the two forms, off, latched reads, the stall control)
  pass on what they must pass and fail on their negative controls;
- the frame driver brackets every pass it records, and the timer's read never waits outside its negative control;
- the figures reach the frame trace and tools/frame_trace_report.py reads them back as median, p95 and p99;
- the Python face refuses what the module would refuse and decodes what it returns, on a stand-in module.
The built module's own runs are timer_check.py's (the lead's build round).
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import statistics
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "native" / "core"
sys.path.insert(0, str(CORE / "python"))

import timer_analysis as ta  # noqa: E402
import timer_check  # noqa: E402

from rendering.native import gpu_timing  # noqa: E402


# ------------------------------------------------------------------------------------------------- the judgements


def _line(a: float, b: float, draws=(1, 2, 4, 8, 16)) -> dict:
    return {n: a + b * n for n in draws}


def test_a_pass_that_scales_with_its_draws_passes_and_a_flat_or_bent_one_fails():
    good = ta.scaling_verdict(_line(0.01, 0.06))
    assert good["pass"] and abs(good["fit"]["slope"] - 0.06) < 1e-9
    # Negative controls: a timer that reads the same for every N, and one that saturates (stops scaling).
    assert ta.scaling_verdict(_line(0.3, 0.0))["pass"] is False
    bent = {1: 0.07, 2: 0.13, 4: 0.25, 8: 0.30, 16: 0.31}
    assert ta.scaling_verdict(bent)["pass"] is False


def test_the_empty_bracket_control_passes_only_when_it_does_not_scale():
    slope = 0.06
    assert ta.flat_verdict(_line(0.002, 0.0001), slope)["pass"] is True
    # A bracket that still encloses the pass grows with it: the control must fail.
    assert ta.flat_verdict(_line(0.01, slope), slope)["pass"] is False
    assert ta.flat_verdict(_line(0.002, 0.0), None)["pass"] is False


def test_a_pass_figure_agrees_with_its_frame_only_within_the_stated_tolerance():
    assert ta.agreement_verdict(1.00, 1.05)["pass"] is True
    assert ta.agreement_verdict(0.05, 0.12)["pass"] is True            # the floor: Qt Quick's own pass
    assert ta.agreement_verdict(0.5, 1.0)["pass"] is False             # half the frame unaccounted
    assert ta.agreement_verdict(None, 1.0)["pass"] is False


def test_the_two_forms_agree_within_their_bounds():
    assert ta.forms_verdict(0.060, 0.055)["pass"] is True
    assert ta.forms_verdict(0.060, 0.020)["pass"] is False
    assert ta.forms_verdict(None, 0.05)["pass"] is False


def test_off_is_judged_by_the_counts_and_each_count_can_fail_it():
    driver = {"gpu_timer": None, "gpu_timer_edges": 12}
    live = {"timers": 0, "query_pools": 0, "queries": 0}
    assert ta.off_verdict(driver, live, edges_before=12, samples=0)["pass"] is True
    assert ta.off_verdict(dict(driver, gpu_timer={}), live, edges_before=12, samples=0)["pass"] is False
    assert ta.off_verdict(dict(driver, gpu_timer_edges=13), live, edges_before=12, samples=0)["pass"] is False
    assert ta.off_verdict(driver, live, edges_before=12, samples=1)["pass"] is False
    assert ta.off_verdict(driver, dict(live, queries=64), edges_before=12, samples=0)["pass"] is False
    assert ta.off_verdict(driver, dict(live, timers=1), edges_before=12, samples=0)["pass"] is False


def test_latched_reads_pass_and_a_same_frame_or_waiting_read_fails():
    timer = {"blocking_reads": 0, "resolve_ns_max": 40_000, "not_ready_reads": 3}
    assert ta.latched_verdict(timer, [1, 1, 2], require_late_read=True)["pass"] is True
    assert ta.latched_verdict(timer, [0, 1], require_late_read=False)["pass"] is False
    assert ta.latched_verdict(dict(timer, blocking_reads=5), [1], require_late_read=False)["pass"] is False
    assert ta.latched_verdict(dict(timer, resolve_ns_max=3_000_000), [1], require_late_read=False)["pass"] is False
    # In a GPU-bound window some result must have been read later than the next frame.
    assert ta.latched_verdict(dict(timer, not_ready_reads=0), [1, 1], require_late_read=True)["pass"] is False
    assert ta.latched_verdict(timer, [], require_late_read=False)["pass"] is False


def test_a_read_cost_that_stops_being_reported_fails():
    """``reads_cost_little`` needs the module's ``resolve_ns_max``, as ``no_read_waited`` needs ``blocking_reads``
    (audit 13 Nov, low 3: a missing figure read as 0 and passed)."""
    timer = {"blocking_reads": 0, "resolve_ns_max": 40_000}
    assert ta.latched_verdict(timer, [1], require_late_read=False)["checks"]["reads_cost_little"] is True
    unreported = {key: value for key, value in timer.items() if key != "resolve_ns_max"}
    verdict = ta.latched_verdict(unreported, [1], require_late_read=False)
    assert verdict["checks"]["reads_cost_little"] is False and verdict["pass"] is False
    assert ta.latched_verdict(dict(timer, resolve_ns_max=-1), [1], require_late_read=False)["pass"] is False


def test_the_stall_control_must_show_a_stall_to_pass():
    latched = {"resolve_ns_max": 30_000}
    assert ta.stall_control_verdict({"blocking_reads": 20, "resolve_ns_max": 6_000_000}, latched)["pass"] is True
    # A waiting read that cost nothing shows nothing: the control is vacuous and fails.
    assert ta.stall_control_verdict({"blocking_reads": 20, "resolve_ns_max": 50_000}, latched)["pass"] is False
    assert ta.stall_control_verdict({"blocking_reads": 0, "resolve_ns_max": 6_000_000}, latched)["pass"] is False


def test_the_waiting_controls_pass_outlasts_the_windows_frame_interval():
    # Build round 2: the display off, the window paced at 16.7 ms, the heavy pass 11.3 ms at 223 draws: the GPU had
    # slack, every earlier frame was done by the next edge, and the wait cost nothing.
    control = ta.control_draws(16.7, 11.3, 223, 1024)
    assert control["draws"] * 11.3 / 223 >= ta.CONTROL_PASS_OVER_INTERVAL * 16.7
    # Display on (round 1): GPU-bound already at a 12.5 ms interval; the control still doubles past it.
    assert ta.control_draws(12.5, 12.4, 238, 1024)["draws"] * 12.4 / 238 >= 2 * 12.5
    # Never fewer draws than measured, never more than the pass allows; no measurement keeps the measured count.
    assert ta.control_draws(1.0, 12.4, 238, 1024)["draws"] == 238
    assert ta.control_draws(500.0, 12.4, 238, 1024)["draws"] == 1024
    assert ta.control_draws(None, 12.4, 238, 1024)["draws"] == 238


def test_the_harness_verdict_counts_a_timer_left_alive():
    record = {"rounds": ["off"], "off": {"pass": True, "checks": {"x": True}}, "live_hosts_at_end": 0,
              "module_loaded": True, "instance_created": True, "timers_at_end": {"timers": 0, "query_pools": 0,
                                                                                  "queries": 0}}
    assert timer_check.api_verdict("opengl", record, require_validation=True)[0] is True
    left = dict(record, timers_at_end={"timers": 1, "query_pools": 0, "queries": 64})
    assert timer_check.api_verdict("opengl", left, require_validation=True)[0] is False


def test_a_window_round_on_a_display_that_presents_nothing_names_the_environment():
    import host_check

    # Build round 1 (13 Nov): Qt alone presented 2 frames in 2 s on D3D11 and D3D12, 139 on OpenGL.
    record = {"rounds": ["window"], "window": {"pass": False, "checks": {"frames_arrive": False}},
              "live_hosts_at_end": 0, "module_loaded": True, "qt_alone_window_frames": 1}
    ok, reasons = host_check.api_verdict("d3d11", record, require_validation=True)
    assert ok is False and reasons[0].startswith("d3d11 environment:") and "frames_arrive" in reasons[1]
    # Negative control: a display that presents keeps the verdict on the rounds alone.
    presenting = dict(record, qt_alone_window_frames=70)
    assert not any("environment" in r for r in host_check.api_verdict("d3d11", presenting, True)[1])
    assert host_check.environment_reasons("d3d11", {"qt_alone_window_frames": None}) == []


def test_the_forms_are_compared_only_when_both_ran_the_scaling_round():
    def result(slope):
        return {"rounds": ["scaling"], "scaling": {"scaling": {"fit": {"slope": slope}}}}

    assert timer_check.forms_check({"opengl": result(0.05)}) is None
    assert timer_check.forms_check({"opengl": result(0.05), "vulkan": result(0.055)})["pass"] is True
    assert timer_check.forms_check({"opengl": result(0.05), "vulkan": result(0.2)})["pass"] is False


# ------------------------------------------------------------------------------------------------- the C++ form


def _function(source: str, name: str) -> str:
    start = source.index(f"void FrameDriver::{name}(")
    end = source.index("\n}\n", start)
    return source[start:end]


def unbracketed_passes(edge: str) -> list[str]:
    """The pass recordings on the frame edge that the timer does not bracket: every ``->record(rhi, cb`` must follow a
    ``timerBegin`` and precede a ``timerEnd`` of its own."""
    records = [m.start() for m in re.finditer(r"->record\(rhi, cb", edge)]
    begins = [m.start() for m in re.finditer(r"timerBegin\(rhi, cb, GpuPassKind::", edge)]
    ends = [m.start() for m in re.finditer(r"timerEnd\(rhi, cb, scope\)", edge)]
    missing = []
    for i, at in enumerate(records):
        before = [b for b in begins if b < at and (i == 0 or b > records[i - 1])]
        after = [e for e in ends if e > at and (i + 1 == len(records) or e < records[i + 1])]
        # The known-cost pass's negative control closes its bracket before recording ("before"); its "pass" end follows.
        if not before or (not after and "before" not in edge[before[-1]:at]):
            missing.append(edge[max(0, at - 80):at + 40])
    return missing


def test_the_frame_driver_brackets_every_pass_it_records():
    source = (CORE / "src" / "frame_driver.cpp").read_text(encoding="utf-8")
    edge = _function(source, "onBeforeRendering")
    assert len(re.findall(r"->record\(rhi, cb", edge)) == 3          # the probe, the known-cost pass, each surface
    assert unbracketed_passes(edge) == []
    # Negative control: the same reading with the surfaces' bracket taken out.
    stripped = edge.replace("const int scope = timerBegin(rhi, cb, GpuPassKind::Surface);", "const int scope = -1;")
    assert stripped != edge and unbracketed_passes(stripped)


def test_off_holds_no_timer_and_the_edge_tests_one_pointer_for_it():
    edge = _function((CORE / "src" / "frame_driver.cpp").read_text(encoding="utf-8"), "onBeforeRendering")
    # Every touch of the timer on the edge is inside `if (m_timer)` or in a helper that returns at once without one.
    block = re.search(r"if \(m_timer\) \{(.*?)\n    \}", edge, re.S)
    assert block and "beginFrame" in block.group(1)
    assert edge.count("m_timer->") == edge.count("m_timer->", block.start(), block.end())
    helpers = (CORE / "src" / "frame_driver.cpp").read_text(encoding="utf-8")
    for name in ("timerBegin", "timerEnd"):
        body = helpers[helpers.index(f"FrameDriver::{name}("):]
        assert re.match(r"FrameDriver::\w+\([^)]*\)\s*\{\s*if \(!m_timer", body), name


def test_the_timers_read_never_waits_outside_its_negative_control():
    source = (CORE / "src" / "gpu_timer.cpp").read_text(encoding="utf-8")
    code = re.sub(r"//[^\n]*", "", source)
    # The Vulkan wait flag and the OpenGL result read without availability appear only on the control's branch.
    wait_bits = [m.start() for m in re.finditer(r"VK_QUERY_RESULT_WAIT_BIT", code)]
    assert len(wait_bits) == 1
    branch = code.rfind("if (wait)", 0, wait_bits[0])
    assert branch >= 0 and code.find("} else {", branch) > wait_bits[0]
    assert "VK_QUERY_RESULT_WITH_AVAILABILITY_BIT" in code and "kGlQueryResultAvailable" in code
    # OpenGL's naive read right after the pass (the control's other half) only under the control's switch.
    assert gl_reads_outside_the_control(code) == []
    unguarded = code.replace("if (m_config.waitForResults) {", "if (true) {", 1)
    assert unguarded != code and gl_reads_outside_the_control(unguarded)


def gl_reads_outside_the_control(code: str) -> list[str]:
    """Blocking OpenGL result reads in GpuTimer::end that are not under the negative control's switch."""
    start = code.index("void GpuTimer::end(")
    body = code[start:code.index("\n}\n", start)]
    guard = body.find("if (m_config.waitForResults) {")
    return [m.group(0) for m in re.finditer(r"getQueryObjectui64v\([^;]*;", body) if guard < 0 or m.start() < guard]


def test_the_pass_kinds_are_one_list_in_cpp_python_and_the_trace_report():
    from tools import frame_trace_report

    header = (CORE / "src" / "gpu_timer.h").read_text(encoding="utf-8")
    enum = re.search(r"enum class GpuPassKind : int \{(.*?)\};", header, re.S).group(1)
    cpp = {int(v): name.lower() for name, v in re.findall(r"^\s*(\w+) = (\d+),", enum, re.M)}
    assert cpp == gpu_timing.GPU_PASS_KINDS == frame_trace_report.GPU_PASS_KIND_NAMES
    from core.performance.frame_trace import FrameTraceEvent

    assert set(frame_trace_report.GPU_EVENT_IDS) == {int(FrameTraceEvent.GPU_PASS_TIME),
                                                      int(FrameTraceEvent.GPU_FRAME_TIME)}
    for event in frame_trace_report.GPU_EVENT_IDS:
        assert frame_trace_report.EVENT_NAMES[event] == FrameTraceEvent(event).name.lower()


# ------------------------------------------------------------------------------------------------- the frame trace


def _samples():
    load = [gpu_timing.GpuSample(3, f, f + 1, 600_000 + 1_000 * (f % 7)) for f in range(1, 41)]
    frames = [gpu_timing.GpuSample(0, -1, f + 3, 700_000 + 2_000 * (f % 5)) for f in range(1, 31)]
    return load + frames


def _report(path: Path) -> str:
    from tools import frame_trace_report

    text = io.StringIO()
    with patch.object(sys, "argv", ["frame_trace_report.py", str(path)]), contextlib.redirect_stdout(text):
        frame_trace_report.main()
    return text.getvalue()


def test_the_figures_reach_the_frame_trace_and_its_report_reads_them(tmp_path):
    from core.performance.frame_trace import FrameTraceSink

    samples = _samples()
    sink = FrameTraceSink(tmp_path / "trace.bin")
    try:
        assert gpu_timing.write_to_frame_trace(sink, samples, screen_index=1) == len(samples)
    finally:
        info = sink.close()
    assert info["dropped_records"] == 0 and info["written_records"] == len(samples)
    found = timer_check._gpu_lines(_report(tmp_path / "trace.bin"))
    for name, kind in (("load", 3), ("frame", 0)):
        values = [s.nanoseconds / 1e6 for s in samples if s.kind == kind]
        assert found[name]["n"] == len(values)
        assert abs(found[name]["median_ms"] - statistics.median(values)) < 5e-4
    # Negative control: a trace without the timer's records has no GPU line.
    empty = FrameTraceSink(tmp_path / "empty.bin")
    empty.close()
    assert timer_check._gpu_lines(_report(tmp_path / "empty.bin")) == {}


class _SilentHost:
    """A hidden host whose timer never returns a figure (a backend whose offscreen frames carry none)."""

    def __init__(self, samples=()):
        self._samples = list(samples)

    def state(self):
        return {"backend": "stand-in", "driver": {"gpu_timer": {}}}

    def set_gpu_timer(self, *_a, **_k):
        pass

    def set_load(self, **_k):
        pass

    def clear_load(self):
        pass

    def frames(self, _count=1):
        pass

    def gpu_samples(self):
        samples, self._samples = self._samples, []
        return samples

    def close(self):
        return {}


class _SilentCore:
    def __init__(self, samples=()):
        self.host = _SilentHost(samples)

    def hidden_host(self, *_a, **_k):
        return self.host

    def gpu_timer_live(self):
        return {"timers": 0, "query_pools": 0, "queries": 0}


@pytest.mark.parametrize("api", ["d3d11", "opengl"])
def test_a_trace_round_with_no_figure_fails(tmp_path, api):
    """A trace of nothing passes every comparison and equals its own negative control, so it must fail on its own."""
    record = timer_check.round_trace(_SilentCore(), None, None, api, tmp_path, {})
    assert record["samples"] == 0 and record["pass"] is False and record["checks"]["figures_in_the_trace"] is False
    # Control: the same round with QRhi's frame figures (D3D's only figure) passes.
    frames = [s for s in _samples() if s.kind == 0]
    passed = timer_check.round_trace(_SilentCore(), None, None, "d3d11", tmp_path, {"samples": frames})
    assert passed["pass"] is True, passed["checks"]


def test_a_scaling_round_without_qrhis_frame_figure_fails_where_it_is_the_only_figure(tmp_path):
    record = timer_check.round_scaling(_SilentCore(), None, None, "d3d11", tmp_path, {})
    assert record["qrhi_frame_figure_in_offscreen_frames"] is False
    assert record["checks"]["qrhi_frame_figure_present"] is False and record["pass"] is False


def test_each_figure_is_one_record_in_the_traces_form():
    from core.performance.frame_trace import FrameTraceEvent

    calls = []
    sink = SimpleNamespace(record=lambda event, **fields: calls.append((event, fields)) or True)
    pass_sample = gpu_timing.GpuSample(2, 41, 42, 123_456)
    frame_sample = gpu_timing.GpuSample(0, -1, 44, 654_321)
    assert gpu_timing.write_to_frame_trace(sink, [pass_sample, frame_sample], screen_index=3) == 2
    assert calls[0] == (FrameTraceEvent.GPU_PASS_TIME, {"screen_index": 3, "revision": 41,
                                                        "logical_timestamp_ns": 2, "auxiliary": 123_456})
    assert calls[1] == (FrameTraceEvent.GPU_FRAME_TIME, {"screen_index": 3, "revision": 44,
                                                         "logical_timestamp_ns": 0, "auxiliary": 654_321})
    assert pass_sample.latency == 1 and frame_sample.latency is None
    assert pass_sample.kind_name == "surface" and abs(frame_sample.milliseconds - 0.654321) < 1e-12


# ------------------------------------------------------------------------------------------------- the Python face


def _stand_in(calls: list):
    def record(name, result=None):
        return lambda *args: (calls.append((name, args)), result)[1]

    return SimpleNamespace(
        host_attach=record("host_attach", 9), host_load=record("host_load"), host_gpu_timer=record("host_gpu_timer"),
        host_gpu_samples=record("host_gpu_samples", [(3, 5, 6, 1000), (0, -1, 7, 2000)]),
        gpu_timer_live=record("gpu_timer_live", json.dumps({"timers": 0, "query_pools": 0, "queries": 0})))


def test_the_python_face_passes_the_timer_and_the_load_through_and_refuses_what_the_module_would():
    from rendering.native import loader

    calls: list = []
    core = loader.NativeCore(_stand_in(calls), {"abi": loader.EXPECTED_ABI})
    host = core.hidden_host(64, 32, timestamps=True)
    assert calls[-1] == ("host_attach", ("hidden", 0, 64, 32, True, 1.0, True))
    host.set_gpu_timer(True)
    assert calls[-1] == ("host_gpu_timer", (9, json.dumps({"enabled": True})))
    host.set_gpu_timer(False, keep_when_off=True)
    assert json.loads(calls[-1][1][1]) == {"enabled": False, "keep_when_off": True}
    with pytest.raises(ValueError, match="unknown timer option"):
        host.set_gpu_timer(True, colour=True)
    host.set_load(draws=4, timing="before")
    assert calls[-1] == ("host_load", (9, json.dumps({"draws": 4, "timing": "before"})))
    with pytest.raises(ValueError, match="unknown load option"):
        host.set_load(passes=2)
    with pytest.raises(ValueError, match="unknown timing"):
        host.set_load(timing="after")
    host.clear_load()
    assert calls[-1] == ("host_load", (9, ""))
    samples = host.gpu_samples()
    assert samples == (gpu_timing.GpuSample(3, 5, 6, 1000), gpu_timing.GpuSample(0, -1, 7, 2000))
    assert core.gpu_timer_live() == {"timers": 0, "query_pools": 0, "queries": 0}
    # Without timestamps the call is the one N2.2 and N2.4 make (their harnesses and tests are unchanged).
    core.hidden_host(64, 32)
    assert calls[-1] == ("host_attach", ("hidden", 0, 64, 32, True))


def test_the_module_lists_what_the_face_calls():
    module = (CORE / "src" / "module.cpp").read_text(encoding="utf-8")
    for name in ("host_load", "host_gpu_timer", "host_gpu_samples", "gpu_timer_live"):
        assert f'{{ "{name}", {name}, ' in module, name
    timer = (CORE / "src" / "gpu_timer.cpp").read_text(encoding="utf-8")
    for option in gpu_timing.TIMER_OPTIONS:
        assert f'QStringLiteral("{option}")' in timer, option
    load = (CORE / "src" / "load_pass.cpp").read_text(encoding="utf-8")
    for option in gpu_timing.LOAD_OPTIONS:
        assert f'QStringLiteral("{option}")' in load, option
    for timing in gpu_timing.LOAD_TIMINGS:
        assert f'QLatin1String("{timing}")' in load, timing
