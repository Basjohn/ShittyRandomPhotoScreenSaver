"""V4 dormancy proof: a disabled visualizer mode does no heavy work.

The retained-Quick architecture already makes mode renderers/frame-runtimes
lazy (V1) and routes selection/cycling through the effective enabled set (V3),
so a disabled mode is never activated and therefore never imported or
constructed. These tests pin that:

- resolving one mode's renderer imports only that renderer (fresh interpreter);
- the frame-runtime factory imports only the requested mode's runtime;
- each of the five modes can be the sole enabled mode (cycling/selection stay
  on it, substitution never leaves it);
- enable-state resolution introduces no timer/thread/poller.
"""
from __future__ import annotations

import ast
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    resolve_effective_enabled_modes,
    resolve_effective_mode,
)

REPO = Path(__file__).resolve().parents[1]

_ALL_RENDERER_MODULES = {
    mode_id: f"rendering.quick.visualizer.implementations.{mode_id}"
    for mode_id in VISUALIZER_MODE_IDS
}
_ALL_FRAME_RUNTIME_MODULES = {
    "spectrum": "widgets.spotify_visualizer.spectrum_frame_runtime",
    "oscilloscope": "widgets.spotify_visualizer.oscilloscope_frame_runtime",
    "sine_wave": "widgets.spotify_visualizer.sine_frame_runtime",
    "bubble": "widgets.spotify_visualizer.bubble_frame_runtime",
    "devcurve": "widgets.spotify_visualizer.devcurve_frame_runtime",
}


def _run_fresh(body: str) -> str:
    script = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(REPO)!r})
        {textwrap.indent(textwrap.dedent(body), '        ').strip()}
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_registry_import_loads_no_renderer_or_frame_runtime():
    out = _run_fresh(
        """
        import core.settings.visualizer_mode_registry  # noqa: F401
        import rendering.quick.visualizer.implementation_registry  # noqa: F401
        from widgets.spotify_visualizer import quick_display_visualizer_owner  # noqa: F401
        heavy = [m for m in sys.modules if 'implementations.' in m or m.endswith('_frame_runtime')]
        print(repr(sorted(heavy)))
        """
    )
    assert out == "[]", f"registry import eagerly loaded heavy modules: {out}"


def test_resolving_one_renderer_imports_only_that_renderer():
    out = _run_fresh(
        """
        from rendering.quick.visualizer.implementation_registry import (
            resolve_quick_visualizer_renderer,
        )
        resolve_quick_visualizer_renderer('bubble')
        loaded = sorted(m for m in sys.modules if 'implementations.' in m)
        print(repr(loaded))
        """
    )
    assert out == "['rendering.quick.visualizer.implementations.bubble']", out


def test_frame_runtime_factory_imports_only_requested_mode():
    out = _run_fresh(
        """
        from widgets.spotify_visualizer.quick_display_visualizer_owner import (
            _mode_runtime_factory,
        )
        _mode_runtime_factory('oscilloscope')
        loaded = sorted(m for m in sys.modules if m.endswith('_frame_runtime'))
        print(repr(loaded))
        """
    )
    assert out == "['widgets.spotify_visualizer.oscilloscope_frame_runtime']", out


def test_each_mode_can_be_the_sole_enabled_mode():
    from rendering.quick.visualizer.double_click_admission import (
        next_visualizer_mode_id,
    )

    for mode_id in VISUALIZER_MODE_IDS:
        enabled = [mode_id]
        assert resolve_effective_enabled_modes(enabled) == (mode_id,)
        # Cycling stays on the sole enabled mode from any current id.
        for current in VISUALIZER_MODE_IDS + ("garbage",):
            assert next_visualizer_mode_id(current, enabled) == mode_id
            resolved, _ = resolve_effective_mode(current, enabled)
            assert resolved == mode_id


def test_enable_state_resolution_introduces_no_timer_or_thread():
    # The resolver module must own no timer/poller/thread for enable-state.
    source = (REPO / "core" / "settings" / "visualizer_mode_registry.py").read_text()
    for banned in ("QTimer", "threading", "Thread(", "start_timer", "schedule_"):
        assert banned not in source, f"enable-state owner unexpectedly references {banned}"


# --- Lead-C / V4 real-runtime dormancy (the common capture module must not
#     import every mode's frame runtime, and a real sole-enabled tick must import
#     only the active mode's runtime) --------------------------------------------

_FRAME_RUNTIME_MODULES = {
    "spectrum": "widgets.spotify_visualizer.spectrum_frame_runtime",
    "oscilloscope": "widgets.spotify_visualizer.oscilloscope_frame_runtime",
    "sine_wave": "widgets.spotify_visualizer.sine_frame_runtime",
    "bubble": "widgets.spotify_visualizer.bubble_frame_runtime",
    "devcurve": "widgets.spotify_visualizer.devcurve_frame_runtime",
}


def test_warming_logical_frame_capture_imports_no_frame_runtime():
    # Lead C warms `logical_frame_capture` during activation. That common capture
    # module must not drag in any mode's frame runtime at import time.
    out = _run_fresh(
        """
        import widgets.spotify_visualizer.logical_frame_capture  # noqa: F401  (the Lead-C warm)
        heavy = sorted(m for m in sys.modules if m.endswith('_frame_runtime'))
        print(repr(heavy))
        """
    )
    assert out == "[]", f"warming logical_frame_capture loaded frame runtimes: {out}"


_REAL_RUNTIME_BODY = """
from types import SimpleNamespace

MODE = __MODE__


class _Engine:
    def get_bubble_energy_bands(self):
        return SimpleNamespace(bass=0.0, mid=0.0, high=0.0, overall=0.0)

    get_energy_bands = get_bubble_energy_bands
    get_pre_agc_energy_bands = get_bubble_energy_bands

    def get_transient_energy_bands(self):
        return SimpleNamespace(bass_transient=0.0, mid_transient=0.0,
                               high_transient=0.0, onset_detected=False,
                               onset_type="", onset_strength=0.0)

    def get_event_scheduler(self):
        return None

    def get_perf_diagnostics(self):
        return {}

    def get_generation_id(self):
        return 3

    def get_activation_id(self):
        return 4

    def get_latest_generation_with_frame(self):
        return 3

    def get_latest_generation_with_waveform(self):
        return 3

    def get_latest_authoritative_frame(self):
        return (0.0, 3, 4)

    def get_waveform(self):
        return ()

    def get_waveform_count(self):
        return 0

    def get_floor_snapshot(self):
        return None


from widgets.spotify_visualizer import tick_pipeline
from widgets.spotify_visualizer.logical_tick_state import (
    install_default_logical_tick_state,
)
from widgets.spotify_visualizer.runtime_controller import (
    VisualizerRuntimeController,
)
from widgets.spotify_visualizer.logical_frame_capture import (
    _mode_frame_runtime_type,
)

controller = VisualizerRuntimeController(
    runtime_generation=1, bar_count=32, initial_mode=MODE
)
state = controller.logical_tick_state
install_default_logical_tick_state(state, bar_count=32)
state._display_bars = [0.0] * 32
controller.enabled = True
controller.playing = True
controller.engine = _Engine()
# Resolve the active mode through the canonical descriptor seam (imports only
# the active mode's runtime, which is legitimately allowed).
controller.resolve_logical_mode_state(MODE, _mode_frame_runtime_type(MODE))
controller.begin_render_activation(engine_generation=3, activation_id=4)
state._mode_teardown_block_until_ready = False
state._mode_transition_ready = True
state._waiting_for_fresh_engine_frame = False

# Keep the heavy real engine.tick / heartbeat / perf out of the way; the mode
# dispatch + capture (which own the frame-runtime resolution) still run.
tick_pipeline.consume_engine_bars = lambda owner, now: (True, True)
tick_pipeline.process_heartbeat = lambda owner, now: None
tick_pipeline.record_tick_perf = lambda owner, now: None

for _ in range(3):
    try:
        tick_pipeline.logical_tick(state)
    except Exception:
        # The active mode's frame-runtime import happens before any capture data
        # work; a later data failure does not affect the dormancy assertion.
        pass

runtimes = {
    "spectrum": "widgets.spotify_visualizer.spectrum_frame_runtime",
    "oscilloscope": "widgets.spotify_visualizer.oscilloscope_frame_runtime",
    "sine_wave": "widgets.spotify_visualizer.sine_frame_runtime",
    "bubble": "widgets.spotify_visualizer.bubble_frame_runtime",
    "devcurve": "widgets.spotify_visualizer.devcurve_frame_runtime",
}
print(repr({m: (mod in sys.modules) for m, mod in runtimes.items()}))
"""


@pytest.mark.parametrize("mode", VISUALIZER_MODE_IDS)
def test_real_sole_enabled_tick_imports_only_active_frame_runtime(mode):
    out = _run_fresh(_REAL_RUNTIME_BODY.replace("__MODE__", repr(mode)))
    loaded = ast.literal_eval(out)
    assert loaded[mode] is True, f"{mode}: active frame runtime did not load ({out})"
    for other, present in loaded.items():
        if other != mode:
            assert present is False, (
                f"{mode} active but disabled mode {other!r} frame runtime imported "
                f"through the real logical/capture path ({out})"
            )
