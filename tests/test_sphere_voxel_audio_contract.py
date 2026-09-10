from __future__ import annotations

import ast
import re
import importlib.util
import sys
import types

import pytest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_plain_visualizer_modules():
    root_text = str(ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    for name in (
        "widgets.spotify_visualizer.sphere_frame_runtime",
        "widgets.spotify_visualizer.render_state",
        "widgets.spotify_visualizer.frame_runtime_lifecycle",
    ):
        sys.modules.pop(name, None)

    widgets_pkg = sys.modules.setdefault("widgets", types.ModuleType("widgets"))
    widgets_pkg.__path__ = [str(ROOT / "widgets")]
    vis_pkg = sys.modules.setdefault(
        "widgets.spotify_visualizer", types.ModuleType("widgets.spotify_visualizer")
    )
    vis_pkg.__path__ = [str(ROOT / "widgets/spotify_visualizer")]

    def load(name: str, relative: str):
        if name in sys.modules:
            return sys.modules[name]
        path = ROOT / relative
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    render_state = load(
        "widgets.spotify_visualizer.render_state",
        "widgets/spotify_visualizer/render_state.py",
    )
    load(
        "widgets.spotify_visualizer.frame_runtime_lifecycle",
        "widgets/spotify_visualizer/frame_runtime_lifecycle.py",
    )
    sphere_runtime = load(
        "widgets.spotify_visualizer.sphere_frame_runtime",
        "widgets/spotify_visualizer/sphere_frame_runtime.py",
    )
    return render_state, sphere_runtime


def _params(
    render_state,
    *,
    vocal_response: float = 1.0,
    reactivity: float = 1.0,
    base_rotation_speed: float = 0.026,
    rotation_speed: float = 0.32,
    size_response: float = 1.15,
    fragment_interpolation: bool = False,
    incoming_density_response: bool = False,
    incoming_transient_velocity: bool = False,
    particle_outtake: bool = False,
):
    values = {
        "sphere_vocal_response": vocal_response,
        "sphere_bump_reactivity": reactivity,
        "sphere_base_rotation_speed": base_rotation_speed,
        "sphere_rotation_speed": rotation_speed,
        "sphere_size_response": size_response,
        "sphere_light_tracer_enabled": True,
        "sphere_fragment_interpolation_enabled": fragment_interpolation,
        "sphere_incoming_density_response_enabled": incoming_density_response,
        "sphere_incoming_transient_velocity_enabled": incoming_transient_velocity,
        "sphere_particle_outtake_enabled": particle_outtake,
    }
    return render_state.FrozenFields(tuple(sorted(values.items())))


@dataclass
class _Event:
    strength: float


class _Scheduler:
    def __init__(self, **events):
        self._events = dict(events)

    def consume_next(self, name: str, *, max_age_s: float):
        _ = max_age_s
        return self._events.pop(name, None)


def _resolve(
    runtime,
    render_state,
    *,
    ts: float,
    reactive=None,
    presence=None,
    energy=None,
    transient=None,
    spectrum=None,
    source_active=True,
    scheduler=None,
    params=None,
):
    return runtime.resolve(
        now_ts=ts,
        runtime_generation=1,
        engine_generation=1,
        activation_id=1,
        source_active=source_active,
        energy=energy or render_state.VisualizerEnergyState(),
        reactive_energy=reactive or render_state.VisualizerEnergyState(),
        presence_energy=presence or reactive or render_state.VisualizerEnergyState(),
        transient=transient or render_state.VisualizerTransientState(),
        analysis_spectrum=tuple(spectrum) if spectrum is not None else tuple(0.10 for _ in range(64)),
        event_scheduler=scheduler,
        parameters=params or _params(render_state),
    )


def test_voxel_renderer_is_sectional_audio_geometry_not_time_motion() -> None:
    source = (
        ROOT / "rendering/quick/visualizer/implementations/sphere_voxel.py"
    ).read_text(encoding="utf-8")
    vertex = source.split("void main() {{", 1)[1].split("mat3 turn = rotation();", 1)[0]
    assert "uTime" not in vertex
    assert "uSectionDrives[8]" in source.split("_FRAGMENT_SOURCE", 1)[0]
    assert "sectionField(direction)" in vertex
    assert "smoothstep(0.62, 0.95" in source
    assert "0.68 * uDeformation" in vertex
    assert "uBars[64]" not in source.split("_FRAGMENT_SOURCE", 1)[0]
    assert "direction * radial" in vertex
    assert "aRadialPolarity" in vertex
    assert "uRotationPhase" in source
    assert "uRotationDrive" not in source
    assert "uRotationSpeed" not in source
    assert "uTime" not in source.split("_FRAGMENT_SOURCE", 1)[0]


def test_voxel_required_uniform_contract_matches_shader_declarations() -> None:
    source = (
        ROOT / "rendering/quick/visualizer/implementations/sphere_voxel.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    required = shadow_required = ghost_required = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
        for target_name in ("names", "shadow_names", "ghost_names"):
            if target_name in targets and isinstance(node.value, ast.Tuple):
                values = {
                    element.value
                    for element in node.value.elts
                    if isinstance(element, ast.Constant) and isinstance(element.value, str)
                }
                if target_name == "names":
                    required = values
                elif target_name == "shadow_names":
                    shadow_required = values
                else:
                    ghost_required = values
    assert required is not None and shadow_required is not None and ghost_required is not None

    vertex_shader = source.split('_VERTEX_SOURCE = f"""', 1)[1].split('_FRAGMENT_SOURCE', 1)[0]
    fragment_shader = source.split('_FRAGMENT_SOURCE = """', 1)[1].split('_SHADOW_VERTEX_SOURCE', 1)[0]
    shadow_vertex = source.split('_SHADOW_VERTEX_SOURCE = """', 1)[1].split('_SHADOW_FRAGMENT_SOURCE', 1)[0]
    shadow_fragment = source.split('_SHADOW_FRAGMENT_SOURCE = """', 1)[1].split('_GHOST_FRAGMENT_SOURCE', 1)[0]
    ghost_fragment = source.split('_GHOST_FRAGMENT_SOURCE = """', 1)[1].split('class QuickSphereVoxelRenderer', 1)[0]

    uniform_pattern = r"^\s*uniform\s+\w+\s+(u\w+)(?:\s*\[[^\]]+\])?\s*;"
    uniforms = lambda text: set(re.findall(uniform_pattern, text, flags=re.MULTILINE))
    assert required == uniforms(vertex_shader) | uniforms(fragment_shader)
    assert shadow_required == uniforms(shadow_vertex) | uniforms(shadow_fragment)
    assert ghost_required == uniforms(vertex_shader) | uniforms(ghost_fragment)


def test_audio_does_not_modulate_voxel_palette_during_reactivity_tuning() -> None:
    source = (
        ROOT / "rendering/quick/visualizer/implementations/sphere_voxel.py"
    ).read_text(encoding="utf-8")
    fragment = source.split('_FRAGMENT_SOURCE = """', 1)[1].split('_SHADOW_VERTEX_SOURCE', 1)[0]
    assert "vDrive" not in fragment
    assert "materialBase" not in fragment
    assert "uMaterial" not in fragment
    assert "uFillColor" in fragment
    assert "vec3 base = max(uFillColor.rgb, vec3(0.001))" in fragment
    assert "uEdgeColor" in fragment
    assert 'gl.glUniform1f(u["uBlockRelief"], 0.35)' in source
    assert "uMaterialFx" not in fragment


def test_sphere_capture_uses_raw_analysis_spectrum_and_live_pre_agc_energy() -> None:
    source = (ROOT / "widgets/spotify_visualizer/sphere_capture.py").read_text(encoding="utf-8")
    engine_source = (ROOT / "widgets/spotify_visualizer/beat_engine.py").read_text(encoding="utf-8")
    assert "get_bubble_energy_bands" in source  # spatial routing only
    assert "get_live_pre_agc_energy_bands" in source
    assert "get_pre_agc_analysis_spectrum" in source
    assert "get_smoothed_bars" not in source
    assert "get_pre_agc_energy_bands" not in source
    assert "analysis_spectrum = tuple" in source
    assert "_display_bars" not in source
    # Publication is lazy: accepted modes do not allocate a tuple every FFT frame.
    assert "_pre_agc_analysis_spectrum_requested" in engine_source
    assert "if not self._pre_agc_analysis_spectrum_requested" in engine_source
    assert 'raw_spectrum = getattr(worker_state, "_freq_values", None)' in engine_source
    assert "get_live_pre_agc_energy_bands" in engine_source


def test_hot_steady_audio_does_not_fragment_or_create_false_relative_swell() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    runtime = sphere_runtime.SphereFrameRuntime()
    hot = render_state.VisualizerEnergyState(bass=0.9, mid=0.9, high=0.8, overall=0.88)
    pinned_transient = render_state.VisualizerTransientState(bass=2.5, mid=2.5, high=1.0)
    _resolve(runtime, render_state, ts=1.0, reactive=hot, presence=hot, transient=pinned_transient)
    frames = []
    for step in range(1, 100):
        frames.append(_resolve(
            runtime,
            render_state,
            ts=1.0 + step * 0.04,
            reactive=hot,
            presence=hot,
            transient=pinned_transient,
        ))
    later = frames[-1]
    assert later is not None
    # A held hot source is one state: no repeated punch packets.
    assert max(later.section_drives) < 0.02
    # Adaptive sustained response is relative to local song range. Starting and
    # staying hot therefore establishes the baseline instead of pinning a swell.
    assert later.size_pulse < 0.01
    assert abs(frames[-1].size_pulse - frames[-10].size_pulse) < 0.002


def test_mid_high_spectral_flux_peak_authors_one_discrete_fragment_packet() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    runtime = sphere_runtime.SphereFrameRuntime()
    energy = render_state.VisualizerEnergyState(bass=0.20, mid=0.55, high=0.34, overall=0.42)
    quiet = [0.08] * 64
    attack = [0.08] * 64
    for index in range(16, 58):
        attack[index] = 0.68
    _resolve(runtime, render_state, ts=2.0, reactive=energy, presence=energy, spectrum=quiet)
    rise = _resolve(runtime, render_state, ts=2.02, reactive=energy, presence=energy, spectrum=attack)
    frame = _resolve(runtime, render_state, ts=2.04, reactive=energy, presence=energy, spectrum=quiet)
    assert rise is not None and frame is not None
    # Peak-picking waits for the spectral-flux crest to turn over, then authors
    # one strong patch and queues tracer travel from that same musical event.
    assert max(rise.section_drives) == 0.0
    assert max(frame.section_drives) > 0.65
    assert runtime._packet_sources_since_diag["spectral"] == 1
    assert frame.tracer_drive > 0.10

    held = frame
    for step in range(1, 16):
        held = _resolve(
            runtime, render_state, ts=2.04 + step * 0.04,
            reactive=energy, presence=energy, spectrum=quiet,
        )
    assert held is not None
    assert runtime._packet_sources_since_diag["spectral"] == 1

def test_generic_transient_crest_is_articulation_only_but_onset_can_fragment() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    vocal = render_state.VisualizerEnergyState(bass=0.20, mid=0.82, high=0.62, overall=0.58)
    low = render_state.VisualizerTransientState(mid=0.03, high=0.02)
    crest = render_state.VisualizerTransientState(mid=1.0, high=0.72)

    runtime = sphere_runtime.SphereFrameRuntime()
    _resolve(runtime, render_state, ts=2.0, reactive=vocal, presence=vocal, transient=low)
    frame = _resolve(runtime, render_state, ts=2.05, reactive=vocal, presence=vocal, transient=crest)
    assert frame is not None
    assert max(frame.section_drives) == 0.0
    assert runtime._packet_sources_since_diag.get("crest") is None
    assert frame.rotation_drive > 0.2

    onset_runtime = sphere_runtime.SphereFrameRuntime()
    _resolve(onset_runtime, render_state, ts=3.0, reactive=vocal, presence=vocal, transient=low)
    onset = render_state.VisualizerTransientState(
        mid=1.0,
        high=0.72,
        onset_detected=True,
        onset_type="vocal_swell",
        onset_strength=0.9,
    )
    onset_frame = _resolve(
        onset_runtime,
        render_state,
        ts=3.05,
        reactive=vocal,
        presence=vocal,
        transient=onset,
    )
    assert onset_frame is not None
    assert max(onset_frame.section_drives) > 0.65

def test_sustained_loud_transient_level_does_not_accumulate_packets() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    runtime = sphere_runtime.SphereFrameRuntime()
    loud = render_state.VisualizerEnergyState(bass=0.68, mid=0.82, high=0.62, overall=0.74)
    held_change = render_state.VisualizerTransientState(mid=1.0, high=0.72)
    _resolve(runtime, render_state, ts=3.0, reactive=loud, transient=held_change)

    visited: set[int] = set()
    for step in range(1, 45):
        frame = _resolve(
            runtime,
            render_state,
            ts=3.0 + step * 0.05,
            reactive=loud,
            transient=held_change,
        )
        assert frame is not None
        if max(frame.section_drives) > 0.35:
            visited.add(max(range(len(frame.section_drives)), key=frame.section_drives.__getitem__))

    # A held-hot novelty value is one change, not permission to keep filling
    # octants for as long as the passage stays loud.
    assert len(visited) <= 1



def test_separate_spectral_flux_peaks_repeat_without_continuous_level_authority() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    runtime = sphere_runtime.SphereFrameRuntime()
    energy = render_state.VisualizerEnergyState(bass=0.30, mid=0.54, high=0.32, overall=0.43)
    quiet = [0.07] * 64
    attack = [0.07] * 64
    for index in range(12, 60):
        attack[index] = 0.72
    _resolve(runtime, render_state, ts=4.0, reactive=energy, presence=energy, spectrum=quiet)

    ts = 4.0
    for _ in range(4):
        ts += 0.02
        _resolve(runtime, render_state, ts=ts, reactive=energy, presence=energy, spectrum=attack)
        ts += 0.02
        frame = _resolve(runtime, render_state, ts=ts, reactive=energy, presence=energy, spectrum=quiet)
        assert frame is not None
        assert max(frame.section_drives) > 0.55
        for _ in range(5):
            ts += 0.04
            _resolve(runtime, render_state, ts=ts, reactive=energy, presence=energy, spectrum=quiet)

    assert 3 <= runtime._packet_sources_since_diag["spectral"] <= 4
    assert "crest" not in runtime._packet_sources_since_diag

def test_shape_only_changes_without_vocal_level_rise_cannot_author_detached_packets() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    runtime = sphere_runtime.SphereFrameRuntime()
    # Keep the weighted vocal envelope approximately constant while moving energy
    # between mid/high. Shape still articulates tracer, but only a positive envelope
    # rise may use the Bubble-inspired vocal-rise packet path.
    states = (
        render_state.VisualizerEnergyState(bass=0.68, mid=0.55, high=0.45, overall=0.70),
        render_state.VisualizerEnergyState(bass=0.68, mid=0.68, high=0.20, overall=0.70),
        render_state.VisualizerEnergyState(bass=0.68, mid=0.42, high=0.70, overall=0.70),
    )
    quiet_transient = render_state.VisualizerTransientState(mid=0.01, high=0.01)
    _resolve(runtime, render_state, ts=4.0, reactive=states[0], transient=quiet_transient)
    peak_tracer = 0.0
    ts = 4.0
    for cycle in range(12):
        energy = states[cycle % len(states)]
        ts += 0.05
        frame = _resolve(runtime, render_state, ts=ts, reactive=energy, transient=quiet_transient)
        assert frame is not None
        peak_tracer = max(peak_tracer, frame.tracer_drive)
        assert max(frame.section_drives) == 0.0
    # Shape-only chatter is intentionally not tracer or fragmentation authority.
    assert peak_tracer == 0.0
    assert runtime._packets_since_diag == 0


def test_dense_weak_typed_events_are_globally_coalesced_and_stay_local() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    runtime = sphere_runtime.SphereFrameRuntime()
    loud = render_state.VisualizerEnergyState(bass=0.66, mid=0.76, high=0.44, overall=0.68)
    _resolve(runtime, render_state, ts=4.0, reactive=loud)

    frame = None
    for step in range(1, 41):
        frame = _resolve(
            runtime,
            render_state,
            ts=4.0 + step * 0.05,
            reactive=loud,
            scheduler=_Scheduler(vocal_swell=_Event(0.10)),
        )
    assert frame is not None
    # Below-threshold classifier chatter cannot become detached geometry.
    assert runtime._packets_since_diag == 0
    assert max(frame.section_drives) == 0.0
    runtime_source = (ROOT / "widgets/spotify_visualizer/sphere_frame_runtime.py").read_text(encoding="utf-8")
    assert "_PACKET_MIN_INTERVAL_S = 0.16" in runtime_source
    assert "_next_section" not in runtime_source


def test_section_attack_is_aggressive_and_fallout_is_gentle() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    runtime = sphere_runtime.SphereFrameRuntime()
    base = render_state.VisualizerEnergyState(bass=0.25, mid=0.25, high=0.20, overall=0.24)
    _resolve(runtime, render_state, ts=4.0, reactive=base)
    hit = _resolve(
        runtime,
        render_state,
        ts=4.02,
        reactive=base,
        scheduler=_Scheduler(kick=_Event(1.0)),
    )
    assert hit is not None
    peak = max(hit.section_drives)
    assert peak > 0.95

    after_250ms = hit
    for step in range(1, 6):
        after_250ms = _resolve(runtime, render_state, ts=4.02 + step * 0.05, reactive=base)
    assert after_250ms is not None
    assert max(after_250ms.section_drives) > peak * 0.45

    late = after_250ms
    for step in range(6, 70):
        late = _resolve(runtime, render_state, ts=4.02 + step * 0.05, reactive=base)
    assert late is not None
    assert max(late.section_drives) < 0.03



def test_low_band_spectral_onset_fragments_and_held_spectrum_does_not_repeat() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    energy = render_state.VisualizerEnergyState(bass=0.48, mid=0.24, high=0.12, overall=0.31)
    quiet = [0.06] * 64
    kick_spectrum = [0.06] * 64
    for index in range(0, 18):
        kick_spectrum[index] = 0.80

    runtime = sphere_runtime.SphereFrameRuntime()
    _resolve(runtime, render_state, ts=5.0, reactive=energy, presence=energy, spectrum=quiet)
    _resolve(runtime, render_state, ts=5.02, reactive=energy, presence=energy, spectrum=kick_spectrum)
    hit = _resolve(runtime, render_state, ts=5.04, reactive=energy, presence=energy, spectrum=quiet)
    assert hit is not None
    assert max(hit.section_drives) > 0.70
    assert runtime._packet_sources_since_diag["spectral"] == 1

    for step in range(1, 18):
        _resolve(
            runtime, render_state, ts=5.04 + step * 0.04,
            reactive=energy, presence=energy, spectrum=quiet,
        )
    assert runtime._packet_sources_since_diag["spectral"] == 1

    kick_runtime = sphere_runtime.SphereFrameRuntime()
    _resolve(kick_runtime, render_state, ts=6.0, reactive=energy, presence=energy)
    kick_frame = _resolve(
        kick_runtime, render_state, ts=6.04, reactive=energy, presence=energy,
        scheduler=_Scheduler(kick=_Event(1.0)),
    )
    assert kick_frame is not None
    assert max(kick_frame.section_drives) > 0.95

def test_vocal_response_scales_typed_vocal_packet_amplitude() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    vocal = render_state.VisualizerEnergyState(bass=0.17, mid=0.82, high=0.68, overall=0.60)
    low = sphere_runtime.SphereFrameRuntime()
    high = sphere_runtime.SphereFrameRuntime()
    low_params = _params(render_state, vocal_response=0.4)
    high_params = _params(render_state, vocal_response=1.3)
    _resolve(low, render_state, ts=6.0, reactive=vocal, params=low_params)
    _resolve(high, render_state, ts=6.0, reactive=vocal, params=high_params)
    low_frame = _resolve(
        low, render_state, ts=6.05, reactive=vocal,
        scheduler=_Scheduler(vocal_swell=_Event(0.8)), params=low_params,
    )
    high_frame = _resolve(
        high, render_state, ts=6.05, reactive=vocal,
        scheduler=_Scheduler(vocal_swell=_Event(0.8)), params=high_params,
    )
    assert low_frame is not None and high_frame is not None
    assert max(high_frame.section_drives) > max(low_frame.section_drives) * 1.8


def test_sustained_growth_distinguishes_soft_and_heavy_without_pulsing() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    runtime = sphere_runtime.SphereFrameRuntime()
    soft = render_state.VisualizerEnergyState(bass=0.12, mid=0.20, high=0.08, overall=0.16)
    heavy = render_state.VisualizerEnergyState(bass=0.55, mid=0.82, high=0.62, overall=0.70)
    params = _params(render_state, size_response=1.15)
    _resolve(runtime, render_state, ts=7.0, reactive=soft, presence=soft, params=params)
    soft_frame = None
    for step in range(1, 31):
        soft_frame = _resolve(runtime, render_state, ts=7.0 + step * 0.05, reactive=soft, presence=soft, params=params)
    assert soft_frame is not None

    heavy_frames = []
    for step in range(1, 31):
        heavy_frames.append(_resolve(
            runtime, render_state, ts=8.5 + step * 0.05,
            reactive=heavy, presence=heavy, params=params,
        ))
    heavy_frame = heavy_frames[-1]
    assert heavy_frame is not None
    assert heavy_frame.size_pulse > soft_frame.size_pulse + 0.08
    assert heavy_frame.size_pulse <= 0.42
    # No beat-like toggling: once the passage is held, adjacent frames move only
    # gradually toward the stable target.
    tail = [frame.size_pulse for frame in heavy_frames[-8:] if frame is not None]
    assert max(abs(b - a) for a, b in zip(tail, tail[1:])) < 0.006
    # The initial soft->heavy rise may earn one discrete packet, but held heavy
    # level cannot keep authoring; any remaining section drive is decay-only.
    assert runtime._packets_since_diag <= 2
    assert max(heavy_frame.section_drives) < 0.10


def test_interfering_experimental_controls_are_disabled_but_sustained_growth_is_live() -> None:
    source = (ROOT / "ui/tabs/media/sphere_builder.py").read_text(encoding="utf-8")
    disabled_block = source.split("for control, explanation in (", 1)[1].split("):\n        control.setEnabled(False)", 1)[0]
    for name in (
        "sphere_surface_detail",
        "sphere_bass_response",
        "sphere_mid_response",
        "sphere_high_response",
        "sphere_energy_curve",
        "sphere_idle_motion",
    ):
        assert f"tab.{name}" in disabled_block
    for name in (
        "sphere_size_response",
        "sphere_deformation",
        "sphere_base_rotation_speed",
        "sphere_rotation_speed",
        "sphere_bump_reactivity",
        "sphere_vocal_response",
    ):
        assert f"tab.{name}" not in disabled_block
    assert "sustained passage-weight growth" in source


def test_quiet_background_contour_cannot_author_packets_without_presence() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    runtime = sphere_runtime.SphereFrameRuntime()
    low_presence = render_state.VisualizerEnergyState(bass=0.01, mid=0.008, high=0.006, overall=0.009)
    states = (
        render_state.VisualizerEnergyState(bass=0.16, mid=0.13, high=0.08, overall=0.13),
        render_state.VisualizerEnergyState(bass=0.22, mid=0.18, high=0.11, overall=0.18),
        render_state.VisualizerEnergyState(bass=0.14, mid=0.12, high=0.07, overall=0.12),
    )
    _resolve(runtime, render_state, ts=8.0, reactive=states[0], presence=low_presence)
    frame = None
    for step in range(1, 120):
        frame = _resolve(
            runtime,
            render_state,
            ts=8.0 + step * 0.04,
            reactive=states[step % len(states)],
            presence=low_presence,
        )
    assert frame is not None
    assert max(frame.section_drives) < 0.01
    assert frame.size_pulse == 0.0
    assert frame.rotation_drive < 0.01


def test_source_loss_is_decay_only_and_cannot_create_false_activity_spike() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    runtime = sphere_runtime.SphereFrameRuntime()
    quiet = render_state.VisualizerEnergyState(bass=0.18, mid=0.20, high=0.09, overall=0.18)
    loud = render_state.VisualizerEnergyState(bass=0.72, mid=0.66, high=0.41, overall=0.63)

    # Establish a local quiet floor, then a real loud stage so adaptive body
    # weight is nonzero before the pause transition.
    _resolve(runtime, render_state, ts=9.0, reactive=quiet, presence=quiet)
    for step in range(1, 15):
        _resolve(runtime, render_state, ts=9.0 + step * 0.05, reactive=quiet, presence=quiet)
    pre = None
    for step in range(1, 15):
        pre = _resolve(runtime, render_state, ts=9.70 + step * 0.05, reactive=loud, presence=loud)
    assert pre is not None and pre.size_pulse > 0.01

    hit = _resolve(
        runtime,
        render_state,
        ts=10.46,
        reactive=loud,
        presence=loud,
        scheduler=_Scheduler(kick=_Event(1.0)),
    )
    assert hit is not None
    peak = max(hit.section_drives)
    paused = _resolve(
        runtime,
        render_state,
        ts=10.50,
        source_active=False,
        reactive=render_state.VisualizerEnergyState(),
        presence=render_state.VisualizerEnergyState(),
    )
    assert paused is not None
    assert max(paused.section_drives) <= peak
    assert paused.tracer_drive <= hit.tracer_drive
    later = paused
    for step in range(1, 35):
        later = _resolve(runtime, render_state, ts=10.50 + step * 0.04, source_active=False)
    assert later is not None
    assert max(later.section_drives) < max(paused.section_drives)
    assert later.size_pulse < paused.size_pulse
    assert later.rotation_drive < paused.rotation_drive

def test_rotation_integrates_one_direction_and_speed_can_fall_during_active_playback() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    runtime = sphere_runtime.SphereFrameRuntime()
    quiet = render_state.VisualizerEnergyState(bass=0.12, mid=0.10, high=0.06, overall=0.10)
    params = _params(render_state, base_rotation_speed=0.03, rotation_speed=0.40)
    _resolve(runtime, render_state, ts=10.0, reactive=quiet, presence=quiet, params=params)
    idle = _resolve(runtime, render_state, ts=10.10, reactive=quiet, presence=quiet, params=params)
    assert idle is not None
    idle_phase = idle.rotation_phase
    assert idle.rotation_drive < 0.02
    assert idle_phase > 0.0

    hit = _resolve(
        runtime, render_state, ts=10.12, reactive=quiet, presence=quiet,
        scheduler=_Scheduler(kick=_Event(1.0)), params=params,
    )
    assert hit is not None
    assert 0.30 < hit.rotation_drive < 0.65
    assert hit.rotation_phase > idle_phase

    phases = [hit.rotation_phase]
    frame = hit
    for step in range(1, 21):
        frame = _resolve(
            runtime, render_state, ts=10.12 + step * 0.05,
            reactive=quiet, presence=quiet, params=params,
        )
        assert frame is not None
        phases.append(frame.rotation_phase)
    assert all(b > a for a, b in zip(phases, phases[1:]))
    # Current-change reaction must materially return toward base within a second,
    # unlike the rejected >0.90 drive plateau seen through most active playback.
    assert frame.rotation_drive < hit.rotation_drive * 0.35

    second = _resolve(
        runtime, render_state, ts=11.17, reactive=quiet, presence=quiet,
        scheduler=_Scheduler(kick=_Event(0.9)), params=params,
    )
    assert second is not None
    assert second.rotation_drive > frame.rotation_drive * 2.0
    assert second.rotation_phase > frame.rotation_phase


def test_base_rotation_and_velocity_reaction_are_independent_without_rewriting_phase_direction() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    quiet = render_state.VisualizerEnergyState(bass=0.12, mid=0.10, high=0.06, overall=0.10)

    # Base Rotation controls continuous idle motion even with zero reactive boost.
    low_base = sphere_runtime.SphereFrameRuntime()
    high_base = sphere_runtime.SphereFrameRuntime()
    low_params = _params(render_state, base_rotation_speed=0.01, rotation_speed=0.0)
    high_params = _params(render_state, base_rotation_speed=0.08, rotation_speed=0.0)
    _resolve(low_base, render_state, ts=11.0, reactive=quiet, presence=quiet, params=low_params)
    _resolve(high_base, render_state, ts=11.0, reactive=quiet, presence=quiet, params=high_params)
    low_frame = _resolve(low_base, render_state, ts=12.0, reactive=quiet, presence=quiet, params=low_params)
    high_frame = _resolve(high_base, render_state, ts=12.0, reactive=quiet, presence=quiet, params=high_params)
    assert low_frame is not None and high_frame is not None
    assert high_frame.rotation_phase > low_frame.rotation_phase * 6.5

    # Velocity Reaction adds speed only after musical excitation while preserving
    # monotonic phase/direction and the same low base speed.
    no_reaction = sphere_runtime.SphereFrameRuntime()
    strong_reaction = sphere_runtime.SphereFrameRuntime()
    no_reaction_params = _params(render_state, base_rotation_speed=0.02, rotation_speed=0.0)
    strong_reaction_params = _params(render_state, base_rotation_speed=0.02, rotation_speed=0.60)
    _resolve(no_reaction, render_state, ts=13.0, reactive=quiet, presence=quiet, params=no_reaction_params)
    _resolve(strong_reaction, render_state, ts=13.0, reactive=quiet, presence=quiet, params=strong_reaction_params)
    for runtime, params in ((no_reaction, no_reaction_params), (strong_reaction, strong_reaction_params)):
        _resolve(
            runtime, render_state, ts=13.02, reactive=quiet, presence=quiet,
            scheduler=_Scheduler(kick=_Event(1.0)), params=params,
        )
    no_frame = _resolve(no_reaction, render_state, ts=13.30, reactive=quiet, presence=quiet, params=no_reaction_params)
    strong_frame = _resolve(strong_reaction, render_state, ts=13.30, reactive=quiet, presence=quiet, params=strong_reaction_params)
    assert no_frame is not None and strong_frame is not None
    assert no_frame.rotation_phase > 0.0
    assert strong_frame.rotation_phase > no_frame.rotation_phase * 2.0


def test_incoming_blocks_are_event_owned_and_decay_instead_of_spawning_ambiently() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    quiet = render_state.VisualizerEnergyState(bass=0.12, mid=0.10, high=0.06, overall=0.10)

    # Generic percussion may now author one event-owned sparse arrival packet too.
    kick_runtime = sphere_runtime.SphereFrameRuntime()
    _resolve(kick_runtime, render_state, ts=20.0, reactive=quiet, presence=quiet)
    kick = _resolve(
        kick_runtime, render_state, ts=20.02, reactive=quiet, presence=quiet,
        scheduler=_Scheduler(kick=_Event(1.0), snare=_Event(1.0)),
    )
    assert kick is not None
    assert max(kick.section_drives) > 0.5
    assert 0.0 < kick.incoming_drive <= 1.0

    # A vocal swell still owns a strong sparse arrival packet.
    vocal_runtime = sphere_runtime.SphereFrameRuntime()
    _resolve(vocal_runtime, render_state, ts=21.0, reactive=quiet, presence=quiet)
    vocal = _resolve(
        vocal_runtime, render_state, ts=21.02, reactive=quiet, presence=quiet,
        scheduler=_Scheduler(vocal_swell=_Event(0.8)),
    )
    assert vocal is not None
    assert vocal.incoming_drive > 0.7
    assert 0 <= vocal.incoming_section < 8

    # Arrival is event-owned with gentle fallout rather than ambient spawning.
    later = _resolve(vocal_runtime, render_state, ts=21.52, reactive=quiet, presence=quiet)
    assert later is not None
    assert 0.0 < later.incoming_drive < vocal.incoming_drive



def test_voxel_light_is_screen_anchored_and_cube_definition_is_independent() -> None:
    source = (ROOT / "rendering/quick/visualizer/implementations/sphere_voxel.py").read_text(encoding="utf-8")
    fragment = source.split('_FRAGMENT_SOURCE = """', 1)[1].split('_SHADOW_VERTEX_SOURCE', 1)[0]
    assert "vScreenCenter" in fragment
    assert "directional = dot(vScreenCenter.xy, lightXY)" in fragment
    assert "shellDiffuse = clamp(0.56 + 0.44 * directional" in fragment
    assert "dot(normal, light)" not in fragment
    assert "dot(screenNormal, light)" not in fragment
    assert "faceModel" in fragment and "edgeDefinition" in fragment
    # Accepted anti-snap seam: tracer/local rotation may never become face identity.
    assert "vLocalFaceNormal = aNormal" in source
    assert "absLocalFace = abs(normalize(vLocalFaceNormal))" in fragment
    assert "absNormal" not in fragment
    assert "edgeColor" in fragment and "sourceEdge" in fragment
    # Finish is physically tied to the fixed light source. Stable local face
    # identity still owns UV/bevel selection; rotated normals are lighting-only.
    assert "vWorldFaceNormal" in fragment
    assert "towardLight" in fragment and "sourceSide" in fragment
    assert "specExponent = mix(10.0, 96.0, gloss)" in fragment
    assert "specularStrength * specLobe * mix(0.05, 0.34, gloss)" in fragment
    # Proper Toon is intentionally hard rather than smoothstep-nearly-cel.
    assert "toonLighting" in fragment
    assert "toonLighting < 0.24 ? 0.16" in fragment
    assert "toonLighting < 0.46 ? 0.40" in fragment
    assert "toonLighting < 0.70 ? 0.68 : 1.04" in fragment
    assert "toonHighlight = step" in fragment


def test_reactive_voxel_curated_preset_exists() -> None:
    preset = ROOT / "presets/visualizer_modes/sphere/preset_6_reactive_voxel.json"
    assert preset.exists()
    text = preset.read_text(encoding="utf-8")
    assert '"sphere_finish": "Neutral"' in text
    assert '"sphere_fill_color"' in text
    assert '"sphere_material"' not in text
    assert '"preset_index": 5' in text
    assert '"sphere_light_tracer_enabled": true' in text
    assert '"sphere_fragment_interpolation_enabled": true' in text
    assert '"sphere_incoming_density_response_enabled": true' in text
    assert '"sphere_incoming_transient_velocity_enabled": true' in text
    assert '"sphere_rainbow_ghosting": false' in text
    assert '"sphere_size_response": 2.25' in text
    assert '"sphere_deformation": 2.45' in text


def test_sphere_optional_presentation_features_are_mode_owned_and_default_off() -> None:
    from core.settings.default_settings import DEFAULT_SETTINGS
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors

    config = DEFAULT_SETTINGS["widgets"]["spotify_visualizer"]
    assert config["sphere_allow_overflow"] is False
    assert config["sphere_cel_shading"] is False
    assert config["sphere_light_tracer_enabled"] is False
    assert config["sphere_fragment_interpolation_enabled"] is False
    assert config["sphere_incoming_density_response_enabled"] is False
    assert config["sphere_incoming_transient_velocity_enabled"] is False
    assert config["sphere_rainbow_ghosting"] is False
    assert config["sphere_fade_incoming_blocks"] is False
    assert config["sphere_finish"] == "Neutral"
    assert config["sphere_fill_color"] == [95, 160, 190, 255]
    assert config["sphere_edge_color"] == [190, 224, 234, 255]
    assert config["sphere_gloss"] == 0.2
    assert config["sphere_specular"] == 0.25
    assert "sphere_material" not in config
    assert "sphere_material_color" not in config
    assert "sphere_material_fx" not in config
    descriptors = {item.mode_id: item for item in iter_all_visualizer_mode_descriptors()}
    assert descriptors["sphere"].renderer_overflow_setting == "sphere_allow_overflow"
    assert all(
        not item.renderer_overflow_setting
        for mode, item in descriptors.items()
        if mode != "sphere"
    )


def test_overflow_clip_bypass_is_descriptor_gated_and_accepted_modes_stay_clipped() -> None:
    source = (ROOT / "rendering/quick/visualizer/node.py").read_text(encoding="utf-8")
    capability = (ROOT / "widgets/spotify_visualizer/mode_capabilities.py").read_text(encoding="utf-8")
    assert "requests_unclipped_renderer_overflow(snapshot)" in source
    assert "self._clip_host.begin" in source
    assert "renderer_overflow_setting" in capability
    assert "BoundedRectRendering" in source


def test_scene_shadow_cel_and_arrival_fade_are_sphere_renderer_only() -> None:
    source = (ROOT / "rendering/quick/visualizer/implementations/sphere_voxel.py").read_text(encoding="utf-8")
    presentation = (ROOT / "widgets/spotify_visualizer/presentation_geometry.py").read_text(encoding="utf-8")
    # No shared frameless-shadow escape hatch remains from the experiment.
    assert "authored_shadow_enabled" not in presentation
    assert '"shadow_enabled": bool(shadow_enabled and is_card)' in presentation
    assert "authored_shadow_enabled" not in source

    from core.settings.visualizer_mode_registry import (
        VisualizerClipPolicy,
        VisualizerModePresentationPolicy,
        VisualizerShellPolicy,
    )
    from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation

    frameless = resolve_visualizer_presentation(
        policy=VisualizerModePresentationPolicy(
            shell_policy=VisualizerShellPolicy.FRAMELESS,
            clip_policy=VisualizerClipPolicy.VIEWPORT_RECT,
            viewport_resize_capable=True,
        ),
        display_size=(2560, 1440),
        border_width=2.0,
        corner_radius=8.0,
        content_inset=0.0,
        background_color=(0, 0, 0, 255),
        border_color=(255, 255, 255, 255),
        shadow_enabled=True,
        shadow_color=(0, 0, 0, 220),
        shadow_blur=16.0,
        shadow_offset=(8.0, 8.0),
        shadow_spread=0.0,
        shadow_extensions=(0.0, 0.0, 0.0, 0.0),
    )
    assert frameless.shell_style["shadow_enabled"] is False
    assert "sphere_shadow_enabled" in source
    assert "_SHADOW_FRAGMENT_SOURCE" in source
    assert "sphere_allow_overflow" in source
    assert "sphere_fade_incoming_blocks" in source
    assert "sphere_cel_shading" in source
    assert "uCelShading" in source and "uFadeIncoming" in source
    assert "self._draw_scene_shadow(" in source
    shadow_method = source.split('    def _draw_scene_shadow(', 1)[1].split('    def _initialize', 1)[0]
    assert 'frame.quad_vao' in shadow_method
    assert 'gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)' in shadow_method
    assert 'gl.glDrawArraysInstanced' not in shadow_method
    assert 'parameters["sphere_shadow_enabled"]' in shadow_method
    assert 'radius * 1.26 * growth' in shadow_method
    assert "-light_x * radius * (0.34 + float(state.size_pulse) * 0.55)" in source
    assert "-light_y * radius * (0.34 + float(state.size_pulse) * 0.55)" in source
    assert "ground ellipse" not in source


def test_toon_finish_colors_and_rainbow_ghosting_are_explicit_sphere_owned_features() -> None:
    source = (ROOT / "rendering/quick/visualizer/implementations/sphere_voxel.py").read_text(encoding="utf-8")
    builder = (ROOT / "ui/tabs/media/sphere_builder.py").read_text(encoding="utf-8")
    binding = (ROOT / "ui/tabs/media/sphere_settings_binding.py").read_text(encoding="utf-8")
    config_applier = (ROOT / "widgets/spotify_visualizer/config_applier.py").read_text(encoding="utf-8")

    for key in ("sphere_fill_color", "sphere_edge_color", "sphere_rainbow_ghosting", "sphere_shadow_enabled"):
        assert f'"{key}"' in config_applier
    assert "ColorSwatchButton" in builder
    assert "Finish Preset:" in builder and "Fill Color:" in builder and "Edge Color:" in builder
    assert "Rainbow Ghosting:" in builder and "Drop Shadow:" in builder
    assert "Toon Shading:" in builder
    assert "sphere_finish" in binding and "sphere_fill_color" in binding and "sphere_edge_color" in binding
    assert "_GHOST_FRAGMENT_SOURCE" in source
    assert "_GHOST_MAX_SAMPLES = 6" in source
    assert "_GHOST_MAX_AGE_S = 0.62" in source
    assert "self._ghost_history.clear()" in source
    assert "blur_offsets" in source
    assert "uGhostHue" in source and "hsv2rgb" in source
    assert "gl.GL_SRC_ALPHA,\n            gl.GL_ONE_MINUS_SRC_ALPHA," in source
    # History must draw after the hero; pre-hero trails were hidden by the shell.
    hero_draw = source.index("gl.glDrawArraysInstanced(\n                gl.GL_TRIANGLES")
    ghost_call = source.index("self._draw_rainbow_ghosts(", hero_draw)
    assert ghost_call > hero_draw
    assert "uFillColor" in source and "uEdgeColor" in source
    assert "uMaterial" not in source and "materialBase" not in source
    assert "authoredAlpha = mix(uFillColor.a, uEdgeColor.a, alphaEdge)" in source
    assert "sourceEdge" in source and "specEnergy" in source
    assert "specLobe" in source



def test_light_tracer_is_optional_event_owned_and_uses_connected_ribbon() -> None:
    source = (ROOT / "rendering/quick/visualizer/implementations/sphere_voxel.py").read_text(encoding="utf-8")
    runtime_source = (ROOT / "widgets/spotify_visualizer/sphere_frame_runtime.py").read_text(encoding="utf-8")
    builder = (ROOT / "ui/tabs/media/sphere_builder.py").read_text(encoding="utf-8")
    assert "sphere_light_tracer_enabled" in runtime_source
    assert "Light Tracer:" in builder
    fragment = source.split('_FRAGMENT_SOURCE = """', 1)[1].split('_SHADOW_VERTEX_SOURCE', 1)[0]
    spec_chunk = fragment.split("float specExponent", 1)[1].split("vec3 base", 1)[0]
    assert "vScreenCenter" not in spec_chunk
    assert "sourceEdge" in source and "towardLight" in source
    assert "def _trigger_tracer" in runtime_source
    assert "self._tracer_target_phase = self._tracer_phase + queued" in runtime_source
    assert "self._tracer_phase += min(remaining, phase_speed * dt)" in runtime_source
    assert "wrappedAngle" in source
    assert "ribbonWidth" in source and "tailLength" in source
    assert "tracerHead" not in source

def test_incoming_population_rank_is_stable_and_cohorts_partition_the_population() -> None:
    source = (ROOT / "rendering/quick/visualizer/implementations/sphere_voxel.py").read_text(encoding="utf-8")
    stable = source.split("float stableFlowSelection", 1)[1].split("float incomingField", 1)[0]
    assert "float admission = 0.46 + (quadrant == (dominant & 3) ? 0.24 : 0.0)" in stable
    assert "admission *= clamp(densityScale, 0.0, 1.0)" in stable
    assert "aInstanceSeed * 19.371" in stable and "float(quadrant) * 0.271" in stable
    assert "+ float(dominant)" not in stable
    assert "uIncomingPreviousSection" not in stable
    assert "uIncomingBlend" not in stable
    assert "stableLane == (lane & 3)" in stable
    assert "aInstanceSeed * 43.117" in stable
    assert "float selected = smoothstep(threshold - 0.028, threshold + 0.028, pick)" in stable

    # The legacy aggregate fallback retains the old dominance crossfade solely
    # for bounded history compatibility. Live particle motion is cohort-owned.
    runtime_source = (ROOT / "widgets/spotify_visualizer/sphere_frame_runtime.py").read_text(encoding="utf-8")
    assert "_PARTICLE_COHORT_COUNT = 4" in runtime_source
    assert "slot.lane = slot_index & 3" in runtime_source
    assert "_INCOMING_RECYCLE_PROGRESS = 0.90" in runtime_source


def test_fragment_interpolation_is_visual_only_and_preset_enabled() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    energy = render_state.VisualizerEnergyState(bass=0.28, mid=0.48, high=0.31, overall=0.39)
    runtime = sphere_runtime.SphereFrameRuntime()
    params = _params(render_state, fragment_interpolation=True)
    _resolve(runtime, render_state, ts=40.0, reactive=energy, presence=energy, params=params)
    hit = _resolve(
        runtime, render_state, ts=40.02, reactive=energy, presence=energy, params=params,
        scheduler=_Scheduler(kick=_Event(1.0)),
    )
    assert hit is not None
    # Same-frame geometry reacts, but does not teleport to the authored unit target.
    first_peak = max(hit.section_drives)
    assert 0.05 < first_peak < 0.95

    later = _resolve(
        runtime, render_state, ts=40.05, reactive=energy, presence=energy, params=params,
    )
    assert later is not None
    assert max(later.section_drives) > first_peak

    # Turning interpolation off restores direct target->rendered geometry ownership.
    raw_runtime = sphere_runtime.SphereFrameRuntime()
    raw_params = _params(render_state, fragment_interpolation=False)
    _resolve(raw_runtime, render_state, ts=41.0, reactive=energy, presence=energy, params=raw_params)
    raw_hit = _resolve(
        raw_runtime, render_state, ts=41.02, reactive=energy, presence=energy, params=raw_params,
        scheduler=_Scheduler(kick=_Event(1.0)),
    )
    assert raw_hit is not None
    assert max(raw_hit.section_drives) > first_peak

    builder = (ROOT / "ui/tabs/media/sphere_builder.py").read_text(encoding="utf-8")
    assert "Fragment Interpolation:" in builder
    assert "visual only" in builder


def test_generic_crest_cannot_author_fragments_or_incoming_and_regions_walk() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    energy = render_state.VisualizerEnergyState(bass=0.30, mid=0.55, high=0.36, overall=0.48)
    runtime = sphere_runtime.SphereFrameRuntime()
    low = render_state.VisualizerTransientState(mid=0.01, high=0.01)
    crest = render_state.VisualizerTransientState(mid=1.0, high=0.8)
    _resolve(runtime, render_state, ts=30.0, reactive=energy, presence=energy, transient=low)
    frame = _resolve(runtime, render_state, ts=30.05, reactive=energy, presence=energy, transient=crest)
    assert frame is not None
    assert max(frame.section_drives) == 0.0
    assert frame.incoming_drive == 0.0

    # Strong typed events independently create incoming fallout, and successive
    # episodes walk visible ingress quadrants even if fragmentation admission is
    # occupied elsewhere.
    sections = []
    ts = 31.0
    runtime = sphere_runtime.SphereFrameRuntime()
    _resolve(runtime, render_state, ts=ts, reactive=energy, presence=energy)
    for _ in range(4):
        ts += 0.40
        frame = _resolve(
            runtime,
            render_state,
            ts=ts,
            reactive=energy,
            presence=energy,
            scheduler=_Scheduler(kick=_Event(1.0)),
        )
        assert frame is not None and frame.incoming_drive > 0.0
        sections.append(frame.incoming_section)
    assert all(0 <= section < 4 for section in sections)
    assert len(set(sections)) >= 3


def test_typed_vocal_incoming_survives_fragmentation_cooldown() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    energy = render_state.VisualizerEnergyState(bass=0.18, mid=0.58, high=0.34, overall=0.44)
    quiet = [0.07] * 64
    attack = [0.07] * 64
    for index in range(14, 56):
        attack[index] = 0.75
    runtime = sphere_runtime.SphereFrameRuntime()
    _resolve(runtime, render_state, ts=32.0, reactive=energy, presence=energy, spectrum=quiet)

    _resolve(runtime, render_state, ts=32.02, reactive=energy, presence=energy, spectrum=attack)
    fragment = _resolve(runtime, render_state, ts=32.04, reactive=energy, presence=energy, spectrum=quiet)
    assert fragment is not None
    assert max(fragment.section_drives) > 0.55
    assert fragment.incoming_drive == 0.0

    # A typed vocal arrives well inside the fragment cooldown. It need not author
    # another fragment packet, but the approved incoming/bounce path is independent.
    typed = _resolve(
        runtime,
        render_state,
        ts=32.08,
        reactive=energy,
        presence=energy,
        spectrum=quiet,
        scheduler=_Scheduler(vocal_swell=_Event(0.92)),
    )
    assert typed is not None
    assert typed.incoming_drive > 0.70
    assert 0 <= typed.incoming_section < 8
    assert len(typed.particle_cohorts) == 1
    assert typed.particle_cohorts[0].vocal_bounce > 0.70

def test_playing_state_silence_cannot_author_new_incoming_voxels() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    runtime = sphere_runtime.SphereFrameRuntime()
    silent = render_state.VisualizerEnergyState()
    reactive = render_state.VisualizerEnergyState(bass=0.42, mid=0.52, high=0.28, overall=0.45)
    params = _params(
        render_state,
        incoming_density_response=True,
        incoming_transient_velocity=True,
    )
    _resolve(runtime, render_state, ts=50.0, reactive=reactive, presence=silent, params=params)
    frame = _resolve(
        runtime,
        render_state,
        ts=50.04,
        reactive=reactive,
        presence=silent,
        scheduler=_Scheduler(vocal_swell=_Event(1.0), kick=_Event(1.0)),
        params=params,
    )
    assert frame is not None
    assert frame.incoming_drive == 0.0
    assert frame.particle_cohorts == ()


def test_incoming_density_response_scales_stable_four_corner_cohort_size() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    reactive = render_state.VisualizerEnergyState(bass=0.30, mid=0.46, high=0.24, overall=0.38)
    params = _params(render_state, incoming_density_response=True)

    quiet_runtime = sphere_runtime.SphereFrameRuntime()
    quiet_presence = render_state.VisualizerEnergyState(bass=0.08, mid=0.09, high=0.06, overall=0.08)
    _resolve(quiet_runtime, render_state, ts=51.0, reactive=reactive, presence=quiet_presence, params=params)
    _resolve(
        quiet_runtime,
        render_state,
        ts=51.04,
        reactive=reactive,
        presence=quiet_presence,
        scheduler=_Scheduler(vocal_swell=_Event(0.92)),
        params=params,
    )
    quiet = _resolve(
        quiet_runtime,
        render_state,
        ts=51.10,
        reactive=reactive,
        presence=quiet_presence,
        params=params,
    )
    assert quiet is not None and quiet.incoming_drive > 0.0

    loud_runtime = sphere_runtime.SphereFrameRuntime()
    loud_presence = render_state.VisualizerEnergyState(bass=1.7, mid=2.0, high=1.3, overall=1.8)
    _resolve(loud_runtime, render_state, ts=52.0, reactive=reactive, presence=loud_presence, params=params)
    _resolve(
        loud_runtime,
        render_state,
        ts=52.04,
        reactive=reactive,
        presence=loud_presence,
        scheduler=_Scheduler(vocal_swell=_Event(0.92)),
        params=params,
    )
    loud = _resolve(
        loud_runtime,
        render_state,
        ts=52.10,
        reactive=reactive,
        presence=loud_presence,
        params=params,
    )
    assert loud is not None and loud.incoming_drive > 0.0
    assert 0.28 <= quiet.incoming_density < loud.incoming_density <= 1.0


def test_incoming_intensity_calibration_requires_about_twenty_percent_more_evidence() -> None:
    _render_state, sphere_runtime = _load_plain_visualizer_modules()

    # Preserve the accepted silence/density calibration from the previous pass.
    assert sphere_runtime._INCOMING_GATE_OPEN == pytest.approx(0.090)
    assert sphere_runtime._INCOMING_GATE_CLOSE == pytest.approx(0.042)
    assert sphere_runtime._INCOMING_TYPED_FORCE_FLOOR == pytest.approx(0.030)
    assert sphere_runtime._INCOMING_DENSITY_LOW == pytest.approx(0.096)
    assert sphere_runtime._INCOMING_DENSITY_HIGH == pytest.approx(1.50)

    # Event confidence is admission evidence, not travel power. Even a shared
    # event clamped to 1.0 must remain well below maximum motion if the local
    # acoustic contrast is flat; continuous contrast then owns the rest of 0..1.
    flat = sphere_runtime._incoming_motion_intensity(1.0, 0.0)
    medium = sphere_runtime._incoming_motion_intensity(1.0, 0.50)
    peak = sphere_runtime._incoming_motion_intensity(1.0, 1.0)
    assert flat == pytest.approx(0.26)
    assert flat < medium < peak
    assert peak == pytest.approx(1.0)


def test_transient_particle_velocity_changes_real_cohort_travel_without_changing_gate() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    reactive = render_state.VisualizerEnergyState(bass=0.45, mid=0.52, high=0.28, overall=0.44)
    presence = render_state.VisualizerEnergyState(bass=1.2, mid=1.4, high=0.9, overall=1.2)

    def run(enabled: bool):
        runtime = sphere_runtime.SphereFrameRuntime()
        params = _params(render_state, incoming_transient_velocity=enabled)
        _resolve(runtime, render_state, ts=53.0, reactive=reactive, presence=presence, params=params)
        hit = _resolve(
            runtime,
            render_state,
            ts=53.04,
            reactive=reactive,
            presence=presence,
            scheduler=_Scheduler(kick=_Event(1.0)),
            params=params,
        )
        assert hit is not None and hit.incoming_drive > 0.0
        assert len(hit.particle_cohorts) == 1
        assert hit.particle_cohorts[0].progress == pytest.approx(0.0)
        later = _resolve(
            runtime,
            render_state,
            ts=53.29,
            reactive=reactive,
            presence=presence,
            params=params,
        )
        assert later is not None and len(later.particle_cohorts) == 1
        return hit, later

    fixed_hit, fixed_later = run(False)
    accented_hit, accented_later = run(True)
    assert fixed_hit.incoming_drive > 0.0 and accented_hit.incoming_drive > 0.0
    assert 0.20 < accented_hit.particle_cohorts[0].velocity_accent < 0.35
    assert fixed_hit.particle_cohorts[0].velocity_accent == 0.0
    # Identical loudness before/after the event is a flat acoustic context. With
    # Particle Velocity enabled, the admitted event intentionally travels more
    # gently than the fixed-speed fallback instead of being treated as max power.
    assert accented_later.particle_cohorts[0].progress < fixed_later.particle_cohorts[0].progress



def test_real_acoustic_jump_granularises_particle_velocity_without_changing_admission() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    params = _params(render_state, incoming_transient_velocity=True)
    reactive = render_state.VisualizerEnergyState(bass=0.30, mid=0.34, high=0.18, overall=0.28)

    def launch(initial_presence, hit_presence):
        runtime = sphere_runtime.SphereFrameRuntime()
        _resolve(runtime, render_state, ts=54.0, reactive=reactive, presence=initial_presence, params=params)
        hit = _resolve(
            runtime, render_state, ts=54.05, reactive=reactive, presence=hit_presence,
            scheduler=_Scheduler(kick=_Event(1.0)), params=params,
        )
        assert hit is not None and len(hit.particle_cohorts) == 1
        return hit.particle_cohorts[0]

    flat_presence = render_state.VisualizerEnergyState(bass=1.1, mid=1.1, high=0.7, overall=1.0)
    quiet_presence = render_state.VisualizerEnergyState(bass=0.05, mid=0.05, high=0.04, overall=0.05)
    peak_presence = render_state.VisualizerEnergyState(bass=2.2, mid=2.3, high=1.6, overall=2.1)
    flat = launch(flat_presence, flat_presence)
    peak = launch(quiet_presence, peak_presence)

    # Same clamped event confidence, radically different local acoustic contrast.
    assert flat.velocity_accent < 0.35
    assert peak.velocity_accent > 0.95
    assert peak.strength > flat.strength



def test_particle_cohorts_are_bounded_independent_and_keep_progress_when_new_events_arrive() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    reactive = render_state.VisualizerEnergyState(bass=0.38, mid=0.52, high=0.31, overall=0.43)
    presence = render_state.VisualizerEnergyState(bass=1.0, mid=1.2, high=0.8, overall=1.0)
    params = _params(render_state, incoming_transient_velocity=True)
    runtime = sphere_runtime.SphereFrameRuntime()
    _resolve(runtime, render_state, ts=60.0, reactive=reactive, presence=presence, params=params)

    frame = None
    first_progress_before_second = None
    for index in range(4):
        ts = 60.30 + index * 0.30
        if index == 1 and frame is not None:
            first_progress_before_second = frame.particle_cohorts[0].progress
        frame = _resolve(
            runtime, render_state, ts=ts, reactive=reactive, presence=presence,
            scheduler=_Scheduler(kick=_Event(0.78)), params=params,
        )
        assert frame is not None
        assert 1 <= len(frame.particle_cohorts) <= 4

    assert frame is not None
    assert len(frame.particle_cohorts) >= 2
    assert len({cohort.lane for cohort in frame.particle_cohorts}) == len(frame.particle_cohorts)
    if first_progress_before_second is not None:
        assert frame.particle_cohorts[0].progress > first_progress_before_second
    assert len(frame.particle_cohorts) <= sphere_runtime._PARTICLE_COHORT_COUNT == 4


def test_particle_outtake_direction_is_captured_at_launch_and_replacement_crossfade_is_renderer_owned() -> None:
    render_state, _sphere_runtime = _load_plain_visualizer_modules()
    from widgets.spotify_visualizer import sphere_frame_runtime

    reactive = render_state.VisualizerEnergyState(bass=0.40, mid=0.56, high=0.33, overall=0.46)
    presence = render_state.VisualizerEnergyState(bass=1.1, mid=1.3, high=0.9, overall=1.1)
    runtime = sphere_frame_runtime.SphereFrameRuntime()
    out_params = _params(render_state, incoming_transient_velocity=True, particle_outtake=True)
    in_params = _params(render_state, incoming_transient_velocity=True, particle_outtake=False)
    _resolve(runtime, render_state, ts=62.0, reactive=reactive, presence=presence, params=out_params)
    first = _resolve(
        runtime, render_state, ts=62.04, reactive=reactive, presence=presence,
        scheduler=_Scheduler(vocal_swell=_Event(0.92)), params=out_params,
    )
    assert first is not None and len(first.particle_cohorts) == 1
    assert first.particle_cohorts[0].outtake is True

    second = _resolve(
        runtime, render_state, ts=62.36, reactive=reactive, presence=presence,
        scheduler=_Scheduler(kick=_Event(0.92)), params=in_params,
    )
    assert second is not None and len(second.particle_cohorts) >= 2
    assert second.particle_cohorts[0].outtake is True
    assert any(not cohort.outtake for cohort in second.particle_cohorts[1:])

    shader = (ROOT / "rendering/quick/visualizer/implementations/sphere_voxel.py").read_text(encoding="utf-8")
    assert "float cohortTravel(float progress, float velocityAccent)" in shader
    assert "float replacementFade = smoothstep(0.08, 0.72, travel)" in shader
    assert "uRenderPass == 1" in shader
    assert "radial += outtakeRadial * flowScale" in shader
    assert "arrivalFade = outtakeAlpha" in shader
    assert "float fadeEnd = mix(0.96, 0.72, velocity)" in shader
    assert "float excursionFade = 1.0 - smoothstep(1.00, 1.18, remaining)" in shader
    assert "sphere_particle_outtake_enabled" not in shader


def test_particle_outtake_is_optional_and_only_reactive_voxel_enables_it() -> None:
    import json

    defaults = (ROOT / "core/settings/default_settings.py").read_text(encoding="utf-8")
    builder = (ROOT / "ui/tabs/media/sphere_builder.py").read_text(encoding="utf-8")
    assert "'sphere_particle_outtake_enabled': False" in defaults
    assert "Particle Outtake:" in builder
    assert "Reverse detached voxel flow outward" in builder

    preset_dir = ROOT / "presets/visualizer_modes/sphere"
    for index, filename in enumerate((
        "preset_1_neutral.json",
        "preset_2_matte.json",
        "preset_3_plastic.json",
        "preset_4_polished.json",
        "preset_5_transparent_react.json",
        "preset_6_reactive_voxel.json",
    ), start=1):
        data = json.loads((preset_dir / filename).read_text(encoding="utf-8"))
        enabled = data["snapshot"]["widgets"]["spotify_visualizer"]["sphere_particle_outtake_enabled"]
        assert enabled is (index == 6)


def test_real_particle_travel_replaces_global_decay_velocity_semantics() -> None:
    runtime_source = (ROOT / "widgets/spotify_visualizer/sphere_frame_runtime.py").read_text(encoding="utf-8")
    shader = (ROOT / "rendering/quick/visualizer/implementations/sphere_voxel.py").read_text(encoding="utf-8")
    assert "_INCOMING_TRAVEL_NORMAL_S = 1.90" in runtime_source
    assert "_INCOMING_TRAVEL_FAST_S = 0.84" in runtime_source
    assert "_OUTTAKE_TRAVEL_NORMAL_S = 1.45" in runtime_source
    assert "_OUTTAKE_TRAVEL_FAST_S = 0.82" in runtime_source
    assert "speed_mix = pow(velocity, 1.35)" in runtime_source
    assert "cohort.progress + dt / max(1.0e-6, cohort.duration)" in runtime_source
    assert "_SPHERE_INCOMING_RELEASE_S" not in runtime_source
    assert "_INCOMING_RELEASE_SLOW_S" not in runtime_source
    assert "_INCOMING_RELEASE_FAST_S" not in runtime_source
    assert "particleFlow(" in shader
    assert "uCohortProgress" in shader
    assert "uCohortVelocity" in shader


def test_preset_5_is_operator_transparent_react_ab_authority() -> None:
    import json

    data = json.loads((ROOT / "presets/visualizer_modes/sphere/preset_5_transparent_react.json").read_text(encoding="utf-8"))
    config = data["snapshot"]["widgets"]["spotify_visualizer"]
    assert data["name"] == "Preset 5 (Transparent React)"
    assert (ROOT / "presets/visualizer_modes/sphere/preset_5_transparent_react.json").exists()
    assert not (ROOT / "presets/visualizer_modes/sphere/preset_5_metallic.json").exists()
    assert config["sphere_fill_color"] == [4, 7, 8, 100]
    assert config["sphere_edge_color"] == [233, 248, 255, 255]
    assert config["sphere_finish"] == "Custom"
    assert config["sphere_shadow_enabled"] is False
    assert config["sphere_light_tracer_enabled"] is True
    assert config["sphere_fragment_interpolation_enabled"] is True
    assert config["sphere_incoming_density_response_enabled"] is True
    assert config["sphere_incoming_transient_velocity_enabled"] is True
    assert config["sphere_particle_outtake_enabled"] is False



def test_reactive_finish_presets_keep_overflow_and_incoming_fade_where_authored() -> None:
    import json
    for name in ("preset_3_plastic.json", "preset_5_transparent_react.json", "preset_6_reactive_voxel.json"):
        data = json.loads((ROOT / "presets/visualizer_modes/sphere" / name).read_text(encoding="utf-8"))
        config = data["snapshot"]["widgets"]["spotify_visualizer"]
        assert config["sphere_allow_overflow"] is True
        assert config["sphere_fade_incoming_blocks"] is True


def test_new_sphere_finish_and_ghost_controls_do_not_enter_accepted_mode_implementations() -> None:
    keys = (
        "sphere_fill_color",
        "sphere_edge_color",
        "sphere_rainbow_ghosting",
        "sphere_shadow_enabled",
        "sphere_fragment_interpolation_enabled",
        "sphere_incoming_density_response_enabled",
        "sphere_incoming_transient_velocity_enabled",
        "sphere_particle_outtake_enabled",
    )
    accepted_mode_ids = (
        "bubble",
        "spectrum",
        "oscilloscope",
        "sine",
        "devcurve",
    )

    implementation_root = ROOT / "rendering/quick/visualizer/implementations"
    runtime_root = ROOT / "widgets/spotify_visualizer"
    for mode_id in accepted_mode_ids:
        implementation = implementation_root / f"{mode_id}.py"
        if implementation.exists():
            source = implementation.read_text(encoding="utf-8")
            assert all(key not in source for key in keys), mode_id

        runtime = runtime_root / f"{mode_id}_frame_runtime.py"
        if runtime.exists():
            source = runtime.read_text(encoding="utf-8")
            assert all(key not in source for key in keys), mode_id

    shared_node = (ROOT / "rendering/quick/visualizer/node.py").read_text(encoding="utf-8")
    shared_capture = (ROOT / "widgets/spotify_visualizer/logical_frame_capture.py").read_text(encoding="utf-8")
    assert all(key not in shared_node for key in keys)
    assert all(key not in shared_capture for key in keys)


def test_renderer_overflow_capability_is_strict_and_sphere_only() -> None:
    from types import SimpleNamespace
    from widgets.spotify_visualizer import mode_capabilities
    from widgets.spotify_visualizer.render_state import FrozenFields

    sphere = SimpleNamespace(
        logical=SimpleNamespace(
            mode_id="sphere",
            mode_state=SimpleNamespace(
                parameters=FrozenFields((("sphere_allow_overflow", True),))
            ),
        )
    )
    assert mode_capabilities.requests_unclipped_renderer_overflow(sphere) is True

    clipped = SimpleNamespace(
        logical=SimpleNamespace(
            mode_id="sphere",
            mode_state=SimpleNamespace(
                parameters=FrozenFields((("sphere_allow_overflow", False),))
            ),
        )
    )
    assert mode_capabilities.requests_unclipped_renderer_overflow(clipped) is False

    bubble = SimpleNamespace(
        logical=SimpleNamespace(
            mode_id="bubble",
            mode_state=SimpleNamespace(parameters=FrozenFields()),
        )
    )
    assert mode_capabilities.requests_unclipped_renderer_overflow(bubble) is False

    missing = SimpleNamespace(
        logical=SimpleNamespace(
            mode_id="sphere",
            mode_state=SimpleNamespace(parameters=FrozenFields()),
        )
    )
    import pytest
    with pytest.raises(KeyError):
        mode_capabilities.requests_unclipped_renderer_overflow(missing)


def test_legacy_sphere_material_keys_forward_migrate_to_clean_finish_contract() -> None:
    from core.settings.visualizer_settings_contract import migrate_legacy_sphere_finish_keys

    migrated = migrate_legacy_sphere_finish_keys({
        "sphere_material": "Water",
        "sphere_material_color": [10, 20, 30, 40],
        "sphere_material_fx": 1.7,
    })
    assert migrated["sphere_finish"] == "Glassy"
    assert migrated["sphere_fill_color"] == [10, 20, 30, 40]
    assert "sphere_material" not in migrated
    assert "sphere_material_color" not in migrated
    assert "sphere_material_fx" not in migrated


def test_finish_preset_is_ui_only_and_never_reaches_voxel_renderer() -> None:
    renderer = (ROOT / "rendering/quick/visualizer/implementations/sphere_voxel.py").read_text(encoding="utf-8")
    config = (ROOT / "widgets/spotify_visualizer/config_applier.py").read_text(encoding="utf-8")
    builder = (ROOT / "ui/tabs/media/sphere_builder.py").read_text(encoding="utf-8")
    assert "sphere_finish" not in renderer
    assert '"sphere_finish"' not in config.split("_SPHERE_PARAMETER_KEYS = (", 1)[1].split(")", 1)[0]
    assert "_FINISH_PRESETS" in builder
    assert "tab.sphere_gloss.setValue" in builder
    assert "tab.sphere_specular.setValue" in builder


def test_incoming_shader_uses_four_distributed_quadrants_with_one_dominant_corner() -> None:
    source = (ROOT / "rendering/quick/visualizer/implementations/sphere_voxel.py").read_text(encoding="utf-8")
    vertex = source.split('_VERTEX_SOURCE = f"""', 1)[1].split('_FRAGMENT_SOURCE', 1)[0]
    incoming = vertex.split("float incomingField", 1)[1].split("float wrappedAngle", 1)[0]
    assert "int dominant = clamp(uIncomingSection, 0, 7) & 3" in incoming
    assert "int quadrant = (direction.x < 0.0 ? 1 : 0) | (direction.y < 0.0 ? 2 : 0)" in incoming
    assert "float admission = 0.46 + mix(previousBoost, currentBoost, dominanceBlend)" in incoming
    assert "float selected = smoothstep(threshold - 0.028, threshold + 0.028, pick)" in incoming
    assert "+ float(dominant)" not in incoming
    # Z must not choose the ingress quadrant; front/back depth therefore shares
    # each visible corner instead of re-forming a compact 3D octant fountain.
    assert "direction.z <" not in incoming



def test_sustained_growth_uses_pre_agc_local_floor_peak_stages() -> None:
    source = (ROOT / "widgets/spotify_visualizer/sphere_frame_runtime.py").read_text(encoding="utf-8")
    assert "sustained_target = fullness" in source
    assert "live_bass * 0.18 + live_mid * 0.58 + live_high * 0.24" in source
    assert "_fullness_floor" in source and "_fullness_peak" in source
    assert "_FULLNESS_FLOOR_RISE_S = 120.0" in source
    assert "relative_fullness" in source
    for pair in (("0.12", "0.30"), ("0.30", "0.48"), ("0.48", "0.68"), ("0.76", "0.94")):
        assert f"_smooth_gate(relative_fullness, {pair[0]}, {pair[1]})" in source


def test_tracer_has_no_free_running_or_shape_sustained_floor() -> None:
    runtime_source = (ROOT / "widgets/spotify_visualizer/sphere_frame_runtime.py").read_text(encoding="utf-8")
    renderer = (ROOT / "rendering/quick/visualizer/implementations/sphere_voxel.py").read_text(encoding="utf-8")
    assert "max(0.10 * sustained_target" not in runtime_source
    assert "self._tracer_phase += (0.055 +" not in runtime_source
    assert "self._tracer_target_phase = self._tracer_phase + queued" in runtime_source
    assert "def _trigger_tracer" in runtime_source
    trigger_chunk = runtime_source.split("def _trigger_tracer", 1)[1].split("@retirement_fenced", 1)[0]
    assert "shape_change" not in trigger_chunk
    assert "crest_score" not in trigger_chunk
    assert "ribbonWidth" in renderer
    assert "tailLength" in renderer
    assert "smoothstep(0.05, 0.18, drive)" in renderer


def test_small_spectrum_chatter_does_not_peak_pick_false_fragment_events() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    runtime = sphere_runtime.SphereFrameRuntime()
    energy = render_state.VisualizerEnergyState(bass=0.40, mid=0.40, high=0.25, overall=0.35)
    ts = 40.0
    _resolve(runtime, render_state, ts=ts, reactive=energy, presence=energy, spectrum=[0.10] * 64)
    for step in range(1, 180):
        ts += 0.02
        spectrum = [
            0.10 + (((index * 13 + step * 7) % 11) - 5) * 0.0007
            for index in range(64)
        ]
        frame = _resolve(
            runtime,
            render_state,
            ts=ts,
            reactive=energy,
            presence=energy,
            spectrum=spectrum,
        )
        assert frame is not None
    assert runtime._packet_sources_since_diag["spectral"] == 0


def test_spectral_events_queue_tracer_distance_instead_of_free_running_phase() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    runtime = sphere_runtime.SphereFrameRuntime()
    energy = render_state.VisualizerEnergyState(bass=0.24, mid=0.50, high=0.30, overall=0.40)
    quiet = [0.07] * 64
    attack = [0.07] * 64
    for index in range(18, 58):
        attack[index] = 0.72
    _resolve(runtime, render_state, ts=41.0, reactive=energy, presence=energy, spectrum=quiet)
    idle = _resolve(runtime, render_state, ts=41.10, reactive=energy, presence=energy, spectrum=quiet)
    assert idle is not None
    idle_phase = idle.tracer_phase
    assert runtime._tracer_target_phase == idle_phase

    _resolve(runtime, render_state, ts=41.12, reactive=energy, presence=energy, spectrum=attack)
    event = _resolve(runtime, render_state, ts=41.14, reactive=energy, presence=energy, spectrum=quiet)
    assert event is not None
    assert runtime._tracer_target_phase > event.tracer_phase > idle_phase
    queued_target = runtime._tracer_target_phase

    later = event
    for step in range(1, 12):
        later = _resolve(
            runtime,
            render_state,
            ts=41.14 + step * 0.04,
            reactive=energy,
            presence=energy,
            spectrum=quiet,
        )
    assert later is not None
    assert idle_phase < later.tracer_phase <= queued_target
    assert runtime._tracer_target_phase == queued_target

def test_tracer_moves_at_bounded_speed_stays_visible_then_settles_cleanly() -> None:
    render_state, sphere_runtime = _load_plain_visualizer_modules()
    runtime = sphere_runtime.SphereFrameRuntime()
    energy = render_state.VisualizerEnergyState(bass=0.24, mid=0.50, high=0.30, overall=0.40)
    quiet = [0.05] * 64
    attack = [0.05] * 64
    for index in range(18, 58):
        attack[index] = 0.90
    params = _params(render_state)
    _resolve(runtime, render_state, ts=50.0, reactive=energy, presence=energy, spectrum=quiet, params=params)
    _resolve(runtime, render_state, ts=50.02, reactive=energy, presence=energy, spectrum=attack, params=params)
    event = _resolve(runtime, render_state, ts=50.04, reactive=energy, presence=energy, spectrum=quiet, params=params)
    assert event is not None
    start = event.tracer_phase
    target = runtime._tracer_target_phase
    assert target - start > 0.20

    moving_drives = []
    previous = start
    frame = event
    for step in range(1, 35):
        frame = _resolve(
            runtime, render_state, ts=50.04 + step * 0.04,
            reactive=energy, presence=energy, spectrum=quiet, params=params,
        )
        assert frame is not None
        assert frame.tracer_phase >= previous
        assert frame.tracer_phase - previous <= 0.04  # bounded below 1 rad/s
        previous = frame.tracer_phase
        if runtime._tracer_target_phase - frame.tracer_phase > sphere_runtime._TRACER_SETTLE_EPS:
            moving_drives.append(frame.tracer_drive)
    assert moving_drives and min(moving_drives) > 0.45
    assert abs(frame.tracer_phase - runtime._tracer_target_phase) < 0.02

    settled_drive = frame.tracer_drive
    for step in range(35, 70):
        frame = _resolve(
            runtime, render_state, ts=50.04 + step * 0.04,
            reactive=energy, presence=energy, spectrum=quiet, params=params,
        )
    assert frame is not None
    assert frame.tracer_drive < settled_drive


def test_rejected_three_band_rise_packet_authority_is_absent_from_sphere_runtime() -> None:
    source = (ROOT / "widgets/spotify_visualizer/sphere_frame_runtime.py").read_text(encoding="utf-8")
    assert "vocal_rise" not in source
    assert "bass_rise" not in source
    assert '"spectral": 0' in source
    assert "def _spectral_onset" in source
    assert "analysis_spectrum" in source
    assert "get_smoothed_bars" not in source
