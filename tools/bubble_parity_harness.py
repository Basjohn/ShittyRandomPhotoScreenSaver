from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEST_APPDATA = ROOT / "tests_tmp_appdata"
os.environ["APPDATA"] = str(TEST_APPDATA)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_bubble_reactivity import BubbleSimulation, _default_settings, _energy, _warm_up


def _load_historical_bubble_module(rev: str):
    src = subprocess.check_output(
        ["git", "show", f"{rev}:widgets/spotify_visualizer/bubble_simulation.py"],
        cwd=ROOT,
        text=True,
    )
    name = f"bubble_{rev}"
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    exec(src, mod.__dict__)
    return mod


def _build_settings(payload: dict) -> dict:
    return _default_settings(
        bubble_big_count=int(payload.get("bubble_big_count", 6)),
        bubble_small_count=int(payload.get("bubble_small_count", 15)),
        bubble_surface_reach=float(payload.get("bubble_surface_reach", 0.8)),
        bubble_stream_direction=str(payload.get("bubble_stream_direction", "up")),
        bubble_stream_constant_speed=float(payload.get("bubble_stream_constant_speed", 0.5)),
        bubble_stream_speed_cap=float(payload.get("bubble_stream_speed_cap", 2.0)),
        bubble_stream_reactivity=float(payload.get("bubble_stream_reactivity", 0.5)),
        bubble_rotation_amount=float(payload.get("bubble_rotation_amount", 0.3)),
        bubble_drift_amount=float(payload.get("bubble_drift_amount", 0.3)),
        bubble_drift_speed=float(payload.get("bubble_drift_speed", 0.3)),
        bubble_drift_frequency=float(payload.get("bubble_drift_frequency", 0.5)),
        bubble_drift_direction=str(payload.get("bubble_drift_direction", "random")),
        bubble_big_size_max=float(payload.get("bubble_big_size_max", 0.038)),
        bubble_small_size_max=float(payload.get("bubble_small_size_max", 0.018)),
        bubble_trail_strength=float(payload.get("bubble_trail_strength", 0.0)),
        bubble_bounce_big_pct=float(payload.get("bubble_bounce_big_pct", 70.0)),
        bubble_bounce_small_pct=float(payload.get("bubble_bounce_small_pct", 30.0)),
        bubble_bounce_big_speed=float(payload.get("bubble_bounce_big_speed", 0.8)),
        bubble_bounce_small_speed=float(payload.get("bubble_bounce_small_speed", 0.5)),
        bubble_bounce_same_only=bool(payload.get("bubble_bounce_same_only", False)),
        bubble_collision_pop_mode=str(payload.get("bubble_collision_pop_mode", "off")),
    )


def _snapshot_metrics(sim, payload: dict) -> dict:
    pos_data, _extra, _trail = sim.snapshot(
        bass=0.0,
        mid_high=0.0,
        big_bass_pulse=float(payload.get("bubble_big_bass_pulse", 0.8)),
        small_freq_pulse=float(payload.get("bubble_small_freq_pulse", 0.5)),
        big_contraction_bias=float(payload.get("bubble_big_contraction_bias", 0.5)),
        big_size_clamp=float(payload.get("bubble_big_size_clamp", 3.0)),
    )
    big_render = []
    small_render = []
    for idx, bubble in enumerate(sim._bubbles):
        if getattr(bubble, "exiting", False):
            continue
        render_radius = float(pos_data[idx * 4 + 2])
        row = {
            "base_radius": float(getattr(bubble, "radius", 0.0) or 0.0),
            "render_radius": render_radius,
            "delta": max(0.0, render_radius - float(getattr(bubble, "radius", 0.0) or 0.0)),
            "pulse": float(getattr(bubble, "pulse_energy", 0.0) or 0.0),
        }
        if getattr(bubble, "is_big", False):
            big_render.append(row)
        else:
            small_render.append(row)
    render_diag = {}
    if hasattr(sim, "get_big_render_diagnostics"):
        try:
            render_diag = dict(sim.get_big_render_diagnostics())
        except Exception:
            render_diag = {}
    return {
        "big_count": len(big_render),
        "small_count": len(small_render),
        "big_max_render": max((r["render_radius"] for r in big_render), default=0.0),
        "big_avg_render": (sum(r["render_radius"] for r in big_render) / len(big_render)) if big_render else 0.0,
        "big_max_delta": max((r["delta"] for r in big_render), default=0.0),
        "big_avg_delta": (sum(r["delta"] for r in big_render) / len(big_render)) if big_render else 0.0,
        "big_avg_pulse": (sum(r["pulse"] for r in big_render) / len(big_render)) if big_render else 0.0,
        "small_max_render": max((r["render_radius"] for r in small_render), default=0.0),
        "small_avg_render": (sum(r["render_radius"] for r in small_render) / len(small_render)) if small_render else 0.0,
        "small_max_delta": max((r["delta"] for r in small_render), default=0.0),
        "small_avg_delta": (sum(r["delta"] for r in small_render) / len(small_render)) if small_render else 0.0,
        "small_avg_pulse": (sum(r["pulse"] for r in small_render) / len(small_render)) if small_render else 0.0,
        "render_diag": render_diag,
    }


def _run_phrase(sim_cls, payload: dict, phrase: dict, frames: int = 24) -> dict:
    sim = sim_cls()
    settings = _build_settings(payload)
    _warm_up(sim, settings, frames=80)
    for _ in range(frames):
        sim.tick(1 / 60, phrase, settings)
    return _snapshot_metrics(sim, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare current Bubble against historical revisions.")
    parser.add_argument(
        "--preset",
        default="preset_1_deep_sea.json",
        help="Bubble preset filename under presets/visualizer_modes/bubble/",
    )
    args = parser.parse_args()

    payload = json.loads((ROOT / "presets" / "visualizer_modes" / "bubble" / args.preset).read_text())
    widget_payload = payload.get("snapshot", {}).get("widgets", {}).get("spotify_visualizer", payload)

    phrases = {
        "soft_phrase": _energy(bass=0.42, mid=0.20, high=0.06),
        "hot_phrase": _energy(bass=1.55, mid=0.65, high=0.16),
        "sustained_bass_hot": _energy(bass=1.60, mid=0.15, high=0.03),
    }

    historical = {
        "current": BubbleSimulation,
        "9d4925e": _load_historical_bubble_module("9d4925e").BubbleSimulation,
        "510520e": _load_historical_bubble_module("510520e").BubbleSimulation,
    }

    report = {}
    for name, sim_cls in historical.items():
        report[name] = {label: _run_phrase(sim_cls, widget_payload, phrase) for label, phrase in phrases.items()}

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
