"""Bounded, tool-only production replay observations and paired GPU interventions.

Never writes Settings/presets or installs product instrumentation. Recorded post-DSP
bands are immutable: technical sensitivity/floor overrides cannot reanalyse them.
Use --capture for native production-host pixels and same-frame zero-swell controls.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

import numpy as np

from core.settings.visualizer_presets import resolve_visualizer_activation_payload
from core.settings.models import SpotifyVisualizerSettings
from rendering.gl_programs import extruded_bubble_scene as scene
from tools.visualizer_replay.driver import replay_clip
from tools.visualizer_replay.engine import ReplayBeatEngine
from widgets.spotify_visualizer.extruded_bubble_frame_runtime import ExtrudedBubbleFrameRuntime
from widgets.spotify_visualizer.feature_frame import FeatureClip, FeatureFrame
from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine


def distribution(values):
    data = np.asarray(values, dtype=float)
    return dict(zip(('min', 'p05', 'median', 'p95', 'max'),
                    map(float, np.quantile(data, (0, .05, .5, .95, 1))))) if len(data) else {}


def load_clip(path, stop):
    frames = []
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            frame = FeatureFrame.from_dict(json.loads(line))
            if frames and (frame.timestamp_us - frames[0].timestamp_us) / 1e6 > stop:
                break
            frames.append(frame)
    if not frames:
        raise ValueError('empty recording')
    return FeatureClip(path.stem, tuple(frames))


def run(args):
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[2]
    paths = [root / p for p in (
        'widgets/spotify_visualizer/extruded_bubble_simulation.py',
        'widgets/spotify_visualizer/extruded_bubble_geometry.py',
        'widgets/spotify_visualizer/extruded_bubble_frame_runtime.py',
        'widgets/spotify_visualizer/logical_frame_capture.py',
        'widgets/spotify_visualizer/render_state.py',
        'core/settings/visualizer_mode_settings.py',
        'rendering/gl_programs/extruded_bubble_scene.py',
        'rendering/gl_programs/scene3d_spheres.py',
        'rendering/gl_programs/scene3d_optics.py',
        'rendering/quick/scene3d/defocus.py',
        'rendering/quick/visualizer/implementations/extruded_bubble.py',
        'tools/extruded_bubble_capture.py',
        'tools/visualizer_replay/driver.py',
        'tools/visualizer_replay/extruded_bubble_forensics.py')]
    paths.extend((root / 'rendering/gl_programs').glob('extruded_bubble*.py'))
    hashes = lambda: {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in sorted(set(paths))}
    source_hashes = hashes()
    receipt = dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                   tracked_diff_sha256=hashlib.sha256(subprocess.check_output(['git', 'diff', 'HEAD'])).hexdigest(),
                   source_hashes=source_hashes)
    (output / 'source_receipt.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    # A hash alone cannot reproduce a rejected uncommitted attempt after the next
    # iteration. Retain exact bounded producer bytes with its ignored evidence.
    for relative, digest in source_hashes.items():
        data = (root / relative).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise RuntimeError('source changed while preserving producer bytes; reject this run')
        destination = output / 'source' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    size = tuple(map(int, args.size.split('x')))
    clip = load_clip(args.clip, args.start + args.duration)
    activation = resolve_visualizer_activation_payload(
        {'mode': 'extruded_bubble', 'preset_extruded_bubble': args.preset - 1}, mode='extruded_bubble')
    settings = dict(activation.resolved_config)
    overrides = {}
    for item in args.set:
        key, separator, value = item.partition('=')
        if not separator:
            raise ValueError('--set requires KEY=JSON')
        overrides[key] = json.loads(value)
    settings.update(overrides)
    settings = asdict(SpotifyVisualizerSettings.from_mapping(
        settings, apply_preset_overlay=False, resolve_preset_indices=False))
    if args.probe_controls:
        off = FeatureClip(clip.name + '_playback_off', tuple(replace(frame, playing=False) for frame in clip.frames))

        def states(source, **changes):
            return replay_clip(source, 'extruded_bubble', settings={**settings, **changes})['logical_series']

        a, b = states(clip, extruded_bubble_sustained=0.), states(clip, extruded_bubble_sustained=1.)
        quiet_a, quiet_b = states(off, extruded_bubble_idle=0.), states(off, extruded_bubble_idle=1.)
        result = dict(clip=str(args.clip.resolve()), frames=len(a),
                      scope='production logical capture, real recorded features, explicit in-memory control interventions',
                      sustained_0_vs_1_evolved_state_identical=all(
                          x.mode_state == replace(y.mode_state, parameters=x.mode_state.parameters)
                          for x, y in zip(a, b)),
                      idle_0_vs_1_bubbles_identical=all(x.mode_state.bubbles == y.mode_state.bubbles
                                                     for x, y in zip(quiet_a, quiet_b)),
                      idle_max_swell=max(value for frame in quiet_b for value in frame.mode_state.bubbles[5::8]),
                      idle_motion_phase_endpoints=[quiet_a[-1].mode_state.motion_phase, quiet_b[-1].mode_state.motion_phase])
        (output / 'control_probe.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        if hashes() != source_hashes:
            raise RuntimeError('source changed during replay; reject this evidence directory')
        print(json.dumps(result, indent=2))
        return
    observed = {}
    rows = []
    bases_at_time = {}
    original_accept = ReplayBeatEngine.accept_feature_frame
    original_advance = ExtrudedBubbleFrameRuntime.advance
    origin = clip.frames[0].timestamp_us / 1e6

    def accept(engine, feature):
        result = original_accept(engine, feature)
        if args.reanalyze_pcm:
            from widgets.spotify_visualizer.bar_computation import compute_bars_from_samples
            history = feature.capture_history
            if history is None:
                raise ValueError('--reanalyze-pcm requires native capture history on every frame')
            if observed.get('capture_serial') != history.capture_serial:
                if 'compute_state' not in observed:
                    observed['compute_state'] = engine._audio_worker.make_compute_snapshot()
                    observed['compute_state']._np = np
                state = observed['compute_state']
                block = int(engine._audio_worker._preferred_block_size or 0) or history.sample_rate // 100
                samples = np.frombuffer(history.pcm_f32le, dtype='<f4')[-block:]
                bars = compute_bars_from_samples(state, samples)
                if bars is None:
                    raise RuntimeError('production PCM analysis failed')
                engine._audio_worker.commit_compute_snapshot(state)
                observed['capture_serial'] = history.capture_serial
        observed['feature'] = feature
        observed['intensity'] = engine.get_musical_intensity()
        if args.reanalyze_pcm:
            worker = engine._audio_worker
            observed['dsp'] = {name: getattr(worker, name) for name in (
                '_last_raw_bass', '_last_raw_mid', '_last_raw_treble', '_raw_bass_avg',
                '_pre_agc_control_bass', '_pre_agc_control_mid', '_pre_agc_control_treble',
                '_gate_floor', '_preferred_block_size')}
        return result

    def advance(runtime, **kwargs):
        snapshot = original_advance(runtime, **kwargs)
        feature = observed['feature']
        parameters = settings
        pose = (float(parameters['extruded_bubble_turn']), float(parameters['extruded_bubble_tilt']))
        _, world_to_view, tan, _ = scene.camera(*pose, size[0] / size[1],
                                               float(parameters['extruded_bubble_scene_scale']))
        records = np.asarray(snapshot.bubbles).reshape(-1, 8)
        shells = scene.bubble_instances(snapshot.bubbles)
        eligible = records[(records[:, 7] < 0) & (records[:, 4] > 0.)]
        mapped = {int(rec[6]): shell for rec, shell in zip(eligible, shells)}
        bases = {bubble.ident: bubble for bubble in runtime._simulation._bubbles}
        bases_at_time[snapshot.time] = {ident: bubble.radius for ident, bubble in bases.items()}
        objects = []
        view_matrix = np.asarray(world_to_view).reshape(3, 3).T
        for rec in records:
            ident = int(rec[6])
            base = bases[ident]
            item = dict(id=ident, large=base.large, base_radius=base.radius,
                        record=list(map(float, rec)), popping=base.popping, leaving=base.leaving)
            if ident in mapped:
                shell = mapped[ident]
                view = view_matrix @ shell[:3]
                depth = -float(view[2])
                item.update(instance=list(map(float,shell)),view_depth=depth,
                            projection_regime='fully_in_front_first_order' if depth>float(shell[3])+.05 else 'near_plane_or_behind_no_radius_estimate')
                if depth > float(shell[3]) + .05:
                    px = float(shell[3]) / (tan[1] * depth) * size[1] / 2
                    candidate=(abs(float(view[0])) < tan[0]*depth+float(shell[3])
                               and abs(float(view[1])) < tan[1]*depth+float(shell[3]))
                    item.update(projected_radius_px=px,frustum_candidate=candidate,
                                musical_radius_delta_px=px * float(rec[5]) / (1 + float(rec[5])),
                                screen_xy=[(float(view[0]) / (tan[0] * depth) + 1) * size[0] / 2,
                                           (1 - float(view[1]) / (tan[1] * depth)) * size[1] / 2])
            objects.append(item)
        sim = runtime._simulation
        rows.append(dict(time_s=feature.timestamp_us / 1e6 - origin,
                         timestamp_us=feature.timestamp_us, playing=kwargs['playing'],
                         identity=kwargs['identity'], source_identity=kwargs['source_identity'],
                         bands=kwargs['body_bands'], scalar=kwargs['intensity'],
                         onsets=[asdict(onset) for onset in kwargs['onsets']],
                         controls=asdict(kwargs['controls']),
                         dsp=observed.get('dsp'),
                         followers={name: getattr(sim, name) for name in (
                             '_body_big_envelope', '_body_small_envelope', '_big_body_reference', '_small_body_reference')},
                         state={name: getattr(snapshot, name) for name in (
                             'level', 'flash', 'sustain', 'stream_speed', 'drift',
                             'emission', 'rays', 'shimmer', 'travel', 'motion_phase')},
                         ray_uniform=scene.ray_strength(parameters, snapshot.rays),
                         speck_density_brightness=scene.speck_amount(snapshot.emission),
                         objects=objects))
        return snapshot

    pixel_records = []
    # Explicit PCM mode recomputes the production body-band DSP only. Recorded onsets,
    # loudness and cadence remain unchanged; this is a controlled hybrid, not a live run.
    band_getter = (_SpotifyBeatEngine.get_bubble_energy_bands if args.reanalyze_pcm
                   else ReplayBeatEngine.get_bubble_energy_bands)
    with patch.object(ReplayBeatEngine, 'accept_feature_frame', accept), \
            patch.object(ReplayBeatEngine, 'get_bubble_energy_bands', band_getter), \
            patch.object(ExtrudedBubbleFrameRuntime, 'advance', advance):
        if args.capture:
            from tools import extruded_bubble_capture as capture_tool
            from PIL import Image
            original_draw = capture_tool._draw

            def paired_draw(host, target, snapshot, size, window, passes=None):
                rgba, gpu_ms = original_draw(host, target, snapshot, size, window, passes)
                state = snapshot.logical.mode_state
                recs = np.asarray(state.bubbles).reshape(-1, 8).copy()
                # Same world, camera, lighting, time, population and alpha; remove only musical swell.
                recs[:, 3] -= np.array([bases_at_time[state.time][int(rec[6])] for rec in recs]) * recs[:, 5]
                recs[:, 5] = 0
                neutral_state = replace(state, bubbles=tuple(map(float, recs.ravel())))
                neutral = replace(snapshot, logical=replace(snapshot.logical, mode_state=neutral_state))
                # Keep the normal-frame pass ledger separate from counterfactual costs.
                before = dict(passes.frame) if passes else None
                plain, _ = original_draw(host, target, neutral, size, window, passes)
                if passes:
                    passes.frame = before
                index = len(pixel_records)
                Image.fromarray(plain).save(output / f'zero_swell_{index:04d}.png')
                diff = np.abs(rgba[..., :3].astype(float) - plain[..., :3].astype(float))
                heat = np.clip(diff * 6, 0, 255).astype('uint8')
                Image.fromarray(heat).save(output / f'swell_difference_{index:04d}.png')
                pixel_records.append(dict(frame=index, logical_time=state.time,
                                          mean_abs_rgb=float(diff.mean()),
                                          pixels_rgb_delta_gt3=int((diff.max(axis=2) > 3).sum()),
                                          scope='same-frame all-bubble swell intervention; not musical correlation or a segmented radius measurement'))
                return rgba, gpu_ms

            with patch.object(capture_tool, '_draw', paired_draw):
                capture_tool.capture(output, args.clip, size=size, window=size, overrides=overrides,
                                     start=args.start, duration=args.duration, fps=args.fps,
                                     gif=args.gif, passes=args.passes, preset=args.preset)
        else:
            replay_clip(clip, 'extruded_bubble', settings=settings)
    selected = [row for row in rows if row['time_s'] >= args.start]
    if not selected:
        raise ValueError('requested interval contains no recorded frames')
    # Stable-ID full-alpha, unclustered, nonpop records exclude births/deaths/collisions as size explanations.
    mature = [obj for row in selected for obj in row['objects']
              if obj['record'][4] > .999 and obj['record'][7] < 0 and obj['popping'] < 0
              and 'projected_radius_px' in obj and obj['frustum_candidate']]
    by_id = {}
    for row in selected:
        for obj in row['objects']:
            if obj['record'][4] > .999 and obj['record'][7] < 0 and obj['popping'] < 0:
                by_id.setdefault(obj['id'], []).append((row['time_s'], obj))
    stable = []
    for ident, samples in by_id.items():
        if len(samples) < 30 or samples[-1][0] - samples[0][0] < 1:
            continue
        swell = [obj['record'][5] for _, obj in samples]
        stable.append(dict(id=ident, large=samples[0][1]['large'], samples=len(samples),
                           duration_s=samples[-1][0] - samples[0][0], swell=distribution(swell),
                           radius_excursion_share=(max(swell) - min(swell)) / (1 + min(swell))))
    summary = dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                   clip=str(args.clip.resolve()), clip_sha256=hashlib.sha256(args.clip.read_bytes()).hexdigest(),
                   preset_path=activation.preset_path, settings=settings, overrides=overrides,
                   scope=('hybrid: production body-band DSP from requested-size PCM tails; recorded onsets/loudness and sampled capture cadence retained; not exact native callback replay'
                          if args.reanalyze_pcm else 'recorded post-DSP features through production logical capture; fixed prerecorded bands, not new live DSP'),
                   pcm_reanalysis=args.reanalyze_pcm,
                   projection_scope='first-order estimates only for fully forward spheres; mature aggregate uses conservative frustum candidates. Near-plane/inside cases retain world instances without a radius estimate. Paired PNG differences are native pixels, not segmented silhouettes',
                   frames=len(selected), size=size,
                   bands={name: distribution([row['bands'][i] for row in selected])
                          for i, name in enumerate(('bass', 'mid', 'high'))},
                   scalars={name: distribution([row['state'][name] for row in selected])
                            for name in selected[0]['state']},
                   stable_ids=stable,
                   mature_large_swell=distribution([o['record'][5] for o in mature if o['large']]),
                   mature_small_swell=distribution([o['record'][5] for o in mature if not o['large']]),
                   musical_radius_delta_px=distribution([o['musical_radius_delta_px'] for o in mature]),
                   pixels=pixel_records)
    with (output / 'custody.jsonl').open('w', encoding='utf-8') as stream:
        for row in rows:
            stream.write(json.dumps(row, separators=(',', ':')) + '\n')
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    if hashes() != source_hashes:
        raise RuntimeError('source changed during replay; reject this evidence directory')
    print(json.dumps({k: summary[k] for k in ('frames', 'bands', 'mature_large_swell',
                                             'mature_small_swell', 'musical_radius_delta_px')}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clip', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--preset', type=int, default=1)
    parser.add_argument('--start', type=float, default=0)
    parser.add_argument('--duration', type=float, default=60)
    parser.add_argument('--size', default='1672x941')
    parser.add_argument('--set', action='append', default=[])
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--probe-controls', action='store_true', help='paired sustained/idle interventions; no GPU')
    parser.add_argument('--reanalyze-pcm', action='store_true',
                        help='production body-band DSP from native PCM; recorded onsets/loudness/cadence retained')
    parser.add_argument('--passes', action='store_true')
    parser.add_argument('--gif', action='store_true')
    parser.add_argument('--fps', type=float, default=6)
    args = parser.parse_args()
    if args.duration <= 0 or args.start < 0 or args.fps <= 0 or not 1 <= args.preset <= 7:
        parser.error('duration/fps must be positive, start nonnegative, preset 1..7')
    if args.probe_controls and (args.capture or args.reanalyze_pcm):
        parser.error('--probe-controls is separate from --capture/--reanalyze-pcm')
    if args.capture:
        from rendering.gl_error_policy import disable_per_call_gl_error_checking
        if not disable_per_call_gl_error_checking():
            raise RuntimeError('GL imported before production policy')
    run(args)


if __name__ == '__main__':
    main()
