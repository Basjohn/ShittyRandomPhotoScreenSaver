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

import subprocess
import sys
import textwrap
from pathlib import Path

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
