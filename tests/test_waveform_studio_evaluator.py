"""Studio evaluator: same inputs + same times -> byte-identical packets to the production path."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from core.settings.default_contract import require_canonical_default
from ui.studio.waveform_adapter import (
    REFERENCE, SYNTHETIC, SyntheticInputs, WaveformStudioAdapter, WaveformStudioEvaluator, advance_options,
    build_frame, _logical_values,
)


def canonical_section():
    """Test-owned inputs: the code-owned canonical defaults, never an authored preset."""
    return dict(require_canonical_default("widgets.spotify_visualizer"))


def production_packets(fixture_id, values, times):
    """Drive a fresh production frame runtime directly with the fixture's inputs."""
    from widgets.spotify_visualizer.waveform_ribbon_frame_runtime import WaveformRibbonFrameRuntime
    runtime = WaveformRibbonFrameRuntime()
    configuration = runtime.configure(_logical_values(values))
    options = advance_options(runtime, values)
    wanted = sorted(times)
    out = {}
    snapshot = None
    for step in SyntheticInputs(fixture_id).steps(max(wanted)):
        snapshot = runtime.advance(onsets=step.onsets, now_ts=step.now, playing=step.playing,
            identity=step.identity, source_identity=step.source_identity, controls=configuration.controls,
            body_bands=step.body_bands, intensity=step.intensity, loudness=step.loudness,
            presence=step.presence, **options)
        for t in wanted:
            if t not in out and step.now >= t - 1e-9:
                out[t] = (snapshot.packet.payload, build_frame(configuration, snapshot, values))
    return out


@pytest.mark.parametrize("fixture_id", ["mid", "transient", "decay"])
def test_evaluator_packets_are_byte_identical_to_the_production_runtime(fixture_id):
    values = canonical_section()
    times = (0.5, 3.0, 6.75)
    expected = production_packets(fixture_id, values, times)
    evaluator = WaveformStudioEvaluator()
    evaluator.select(fixture_id)
    for t in times:
        frame = evaluator.evaluate(t, values)
        payload, production_frame = expected[t]
        assert frame.packet.payload == payload
        assert frame.particles == production_frame.particles and frame.strands == production_frame.strands
        assert dict(frame.drives) == dict(production_frame.drives)
    evaluator.release()


def test_scrub_backwards_replays_deterministically():
    values = canonical_section()
    evaluator = WaveformStudioEvaluator()
    evaluator.select("bass")
    late = evaluator.evaluate(7.0, values).packet.payload
    early = evaluator.evaluate(2.0, values).packet.payload          # earlier time: replay from the start
    assert evaluator.evaluate(7.0, values).packet.payload == late
    assert early != late
    fresh = WaveformStudioEvaluator()
    fresh.select("bass")
    assert fresh.evaluate(2.0, values).packet.payload == early


def test_fixtures_vary_bands_independently_not_one_monotonic_sweep():
    table = {f.id: f for f in WaveformStudioEvaluator().fixtures()}
    assert {f.kind for f in table.values()} >= {REFERENCE, SYNTHETIC}

    def profile(fixture_id):
        steps = [s for s in SyntheticInputs(fixture_id).steps(table[fixture_id].duration) if s.now >= 0]
        bands = [s.body_bands for s in steps]
        kinds = {o.kind for s in steps for o in s.onsets}
        dominant = max(range(3), key=lambda i: sum(b[i] for b in bands))
        return dominant, kinds, [s.loudness for s in steps]

    assert profile("bass")[0] == 0 and profile("mids")[0] == 1 and profile("highs")[0] == 2
    assert profile("bass")[1] == {"kick"} and profile("mids")[1] == {"snare"}
    _d, kinds, loudness = profile("transient")
    assert len({round(v, 3) for v in loudness}) == 1 and kinds            # hits over a constant loud bed
    _d, _k, loudness = profile("decay")
    assert loudness[0] > 10 * max(loudness[-1], 1e-3)                    # releases to silence
    _d, kinds, loudness = profile("sustained")
    assert not kinds and loudness[-1] == loudness[len(loudness) // 2]   # held, no hits


def test_evaluator_owns_its_runtime_and_reconfigures_from_session_values():
    values = canonical_section()
    evaluator = WaveformStudioEvaluator()
    evaluator.select("peak")
    before = evaluator.evaluate(4.0, values)
    edited = dict(values)
    cards = [dict(card) for card in values["waveform_ribbon_ribbons"]]
    cards[0]["height"] = min(2.0, cards[0]["height"] * 1.5)
    edited["waveform_ribbon_ribbons"] = cards
    after = evaluator.evaluate(4.0, edited)       # same time, new values: replayed with the edit
    assert after.packet.payload != before.packet.payload
    assert evaluator.evaluate(4.0, values).packet.payload == before.packet.payload
    fresh = WaveformStudioEvaluator()
    fresh.select("peak")
    assert fresh.evaluate(4.0, edited).packet.payload == after.packet.payload      # exact = full replay


def test_live_gesture_path_republishes_the_instant_without_moving_time():
    values = canonical_section()
    evaluator = WaveformStudioEvaluator()
    evaluator.select("peak")
    before = evaluator.evaluate(4.0, values)
    edited = dict(values)
    edited["waveform_ribbon_height"] = [values["waveform_ribbon_height"][0], values["waveform_ribbon_height"][1] * .5]
    steps = evaluator.steps_run
    live = evaluator.evaluate(4.0, edited, exact=False)
    assert evaluator.steps_run == steps + 1 and live.time == before.time
    assert live.packet.payload != before.packet.payload
    # The gesture's end asks for the exact frame: the approximate history is replayed away.
    exact = evaluator.evaluate(4.0, edited)
    fresh = WaveformStudioEvaluator()
    fresh.select("peak")
    assert exact.packet.payload == fresh.evaluate(4.0, edited).packet.payload


def _native_clip():
    from ui.studio.waveform_recorded_inputs import has_native_history
    directory = Path(__file__).resolve().parents[1] / "logs" / "visualizer_recordings"
    clips = sorted(directory.glob("*.jsonl"), key=lambda p: p.stat().st_size) if directory.is_dir() else []
    return next((clip for clip in clips if has_native_history(clip)), None)


def test_recorded_clip_replay_matches_production_logical_capture_byte_for_byte(qt_app):
    clip = _native_clip()
    if clip is None:
        pytest.skip("No native-PCM visualizer recording in logs/visualizer_recordings")
    from ui.studio.adapter import RECORDED, StudioFixture
    from ui.studio.waveform_recorded_inputs import extract, to_inputs
    values = canonical_section()
    data = extract(clip, values, seconds=3.0)
    fixture = StudioFixture("clip:test", "Test Clip", RECORDED, float(data["duration"]), str(clip))
    evaluator = WaveformStudioEvaluator()
    evaluator.add_recorded(to_inputs(data, fixture))
    evaluator.select("clip:test")
    origin = data["origin"]
    ready = [step for step in data["steps"] if step["ready"]]
    checked = 0
    for step in ready[:: max(1, len(ready) // 12)]:
        frame = evaluator.evaluate(step["now_ts"] - origin, values)
        assert hashlib.sha256(frame.packet.payload).hexdigest() == step["packet_sha256"]
        checked += 1
    assert checked >= 6


def test_adapter_schema_is_derived_from_the_canonical_registry():
    from core.settings.visualizer_mode_settings import Range, require_mode_settings
    schema = WaveformStudioAdapter().schema()
    spec = require_mode_settings("waveform_ribbon")
    ranges = {c.key for c in spec.controls if isinstance(c, Range)}
    by_id = {p.id: p for p in schema.properties}
    assert ranges <= set(by_id)
    assert all(by_id[key].instrument == "quiet_peak" for key in ranges)     # A/B endpoints, not range sliders
    assert {w.id for w in schema.workspaces} == {"composition", "reactivity", "appearance", "world"}
    assert not [p.id for p in schema.properties if p.instrument == "scalar" and p.path[0] in ranges]


def test_every_registry_control_is_reachable_in_the_studio():
    """Coverage gate: the Studio replaces the builder, so no canonical Waveform control may be unreachable.

    Schema-driven: a key added to the registry must appear without Studio code changes (or this fails)."""
    from core.settings.visualizer_mode_settings import require_mode_settings
    schema = WaveformStudioAdapter().schema()
    spec = require_mode_settings("waveform_ribbon")
    by_key: dict[str, list] = {}
    for prop in schema.properties:
        by_key.setdefault(prop.path[0], []).append(prop)
    missing = [c.key for c in spec.controls if c.key not in by_key]
    assert missing == [], f"Registry controls unreachable in the Studio: {missing}"
    tuned = {pid for t in schema.response.targets for c in t.cells for pid in (c.gain, c.power)}
    for key, props in by_key.items():
        visible = [p for p in props if not p.instrument_only]
        assert visible or all(p.id in tuned or p.group == "Routing Details" for p in props), key
    groups = {(w.id, g) for w in schema.workspaces for g in w.groups}
    assert all((p.workspace, p.group) in groups for p in schema.properties)


def test_retired_stretch_is_advanced_only_and_pulse_is_first_class():
    schema = WaveformStudioAdapter().schema()
    stretch = [p for p in schema.properties if p.path[0] == "waveform_ribbon_stretch"]
    assert stretch and all(p.group == "Advanced (Retired)" for p in stretch)
    assert "stretch" not in {t.id for t in schema.response.targets}
    reactivity = next(w for w in schema.workspaces if w.id == "reactivity")
    assert reactivity.groups[0] == "Energy Pulse"
    from core.settings.visualizer_mode_settings import require_mode_settings
    pulse_keys = {c.key for c in require_mode_settings("waveform_ribbon").controls if c.bucket == "pulse"}
    assert pulse_keys and all(p.group == "Energy Pulse" for p in schema.properties if p.path[0] in pulse_keys)


def test_world_and_reaction_headline_controls_lead_open_groups():
    """Mist density, floor brightness/reflection/tint and the reaction mode are first and visible."""
    schema = WaveformStudioAdapter().schema()
    by_id = {p.id: p for p in schema.properties}

    def first_rows(group, count):
        rows = sorted((p for p in schema.properties if p.group == group and not p.instrument_only),
                      key=lambda p: p.priority)
        return [p.id for p in rows[:count]]

    world = next(w for w in schema.workspaces if w.id == "world")
    assert {"Mist", "Floor"} <= set(world.open_groups)
    assert "waveform_ribbon_fog_density" in first_rows("Mist", 2)
    from ui.studio.waveform_adapter import HEADLINE_FLOOR
    headline = [f"waveform_ribbon_{key}" for key in HEADLINE_FLOOR if f"waveform_ribbon_{key}" in by_id]
    assert len(headline) >= 4 and first_rows("Floor", len(headline)) == headline
    assert by_id["waveform_ribbon_fog_density"].instrument == "quiet_peak"
    mode = by_id.get("waveform_ribbon_reaction_mode")
    if mode is None:
        pytest.skip("reaction mode not in this registry revision")
    reactivity = next(w for w in schema.workspaces if w.id == "reactivity")
    assert reactivity.groups[0] == "Energy Pulse" and "Energy Pulse" in reactivity.open_groups
    assert first_rows("Energy Pulse", 1) == [mode.id]
    assert len(mode.choice_notes) == len(mode.choices) and all(mode.choice_notes)


@pytest.mark.parametrize("extent", [(420.0, 280.0), (1282.5, 1005.0), (2284.7, 408.7)])
def test_studio_view_and_projection_equal_production_for_the_same_card(extent):
    """The Studio's lens is production's: same presentation rule, aperture and physical_view result."""
    import numpy as np
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from rendering.quick.visualizer.implementations.waveform_ribbon import physical_view
    from ui.studio.adapter import RenderCard
    from ui.studio.waveform_adapter import WaveformStudioRenderer, camera_parameters
    from widgets.spotify_visualizer.presentation_geometry import (framed_aperture_scale,
                                                                 resolve_visualizer_presentation)
    values = canonical_section()
    values["waveform_ribbon_camera_projection"] = "Perspective"
    border = 4.0
    width = 900.0
    height = width * extent[1] / extent[0]
    # Production display owner (planar card): the live card committed at its CUSTOM extent (uniform scale 1),
    # card chrome in display pixels. The Studio shows that card scaled down to its frame, chrome included.
    production = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("waveform_ribbon"), display_size=(4000.0, 4000.0),
        viewport_extent=extent, uniform_visual_scale=1.0, border_width=border, corner_radius=8.0,
        content_inset=0.0, background_color=(0, 0, 0, 0), border_color=(0, 0, 0, 0), shadow_enabled=False,
        shadow_color=(0, 0, 0, 0), shadow_blur=0.0, shadow_offset=(0.0, 0.0), shadow_spread=0.0,
        shadow_extensions=(0.0, 0.0, 0.0, 0.0))
    renderer = object.__new__(WaveformStudioRenderer)
    renderer._presentation_key = None
    card = RenderCard((0, 0, int(width), int(height)), (width, height), (0.0,) * 16, 1, extent,
                      (("border_width", border), ("content_inset", 0.0)))
    studio = renderer._resolved_presentation(card)
    aperture_p = framed_aperture_scale(production, content=True)
    aperture_s = framed_aperture_scale(studio, content=True)
    assert aperture_s == pytest.approx(aperture_p, rel=1e-9)
    camera = camera_parameters(values)
    for a, b in zip(physical_view(camera, width / height, aperture_s), physical_view(camera, width / height, aperture_p)):
        np.testing.assert_allclose(np.asarray(a, float), np.asarray(b, float), rtol=1e-9, atol=1e-12)
    if extent[1] > 280.0:
        assert aperture_s > 0.9 * extent[1] / 280.0   # a taller live card reveals more world (no magnification)
