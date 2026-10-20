"""Accepted original Bubble as a real-recording positive response comparator.

Tool-only stable identities, immutable snapshots and native production-host pixels.
No simulation/Settings/preset changes. Run as a module; --clip and --output required.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import subprocess
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clip', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--duration', type=float, default=12)
    parser.add_argument('--fps', type=float, default=12)
    parser.add_argument('--size', default='1672x941')
    parser.add_argument('--preset', type=int, default=1)
    args = parser.parse_args()
    if args.duration <= 0 or args.fps <= 0 or args.preset < 1:
        parser.error('duration/fps and preset must be positive')
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    if not disable_per_call_gl_error_checking():
        raise RuntimeError('GL imported before production policy')
    from PIL import Image, ImageDraw
    import numpy as np
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.extruded_bubble_capture import _draw
    from tools.transition_contact_sheet import TransitionCapture
    from tools.visualizer_replay.driver import replay_clip
    from tools.visualizer_replay import driver
    from tools.visualizer_replay.extruded_bubble_forensics import distribution, load_clip
    from widgets.spotify_visualizer.bubble_simulation import BubbleSimulation
    from widgets.spotify_visualizer.presentation_geometry import resize_visualizer_presentation
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    activation = resolve_visualizer_activation_payload({'mode': 'bubble', 'preset_bubble': args.preset-1}, mode='bubble')
    clip = load_clip(args.clip, args.duration)
    size = tuple(map(int, args.size.split('x')))
    args.output.mkdir(parents=True, exist_ok=False)
    times = [(frame.timestamp_us - clip.frames[0].timestamp_us) / 1e6 for frame in clip.frames]
    wanted = sorted({min(len(times)-1, bisect_left(times, index/args.fps))
                     for index in range(math.ceil(times[-1]*args.fps))})
    identities, retained, rows = {}, [], []
    original_snapshot = BubbleSimulation.snapshot
    scale = math.sqrt(size[0] * size[1] / 1.5)

    def observe(simulation, **kwargs):
        result = original_snapshot(simulation, **kwargs)
        positions = np.asarray(result[0]).reshape(-1, 4)
        objects = []
        for bubble, record in zip(simulation._bubbles, positions):
            token = id(bubble)
            if token not in identities:
                identities[token] = len(identities) + 1
                retained.append(bubble)  # prevent Python id reuse; does not reinsert into the simulation
            objects.append(dict(id=identities[token], large=bubble.is_big, popping=bubble.popping,
                                exiting=bubble.exiting, record=list(map(float, record)),
                                radius_px=float(record[2])*scale, base_radius=bubble.radius))
        rows.append(dict(time_s=times[len(rows)], objects=objects))
        return result

    original_configure = driver._configure

    def configure(controller, *positional, **kwargs):
        original_configure(controller, *positional, **kwargs)
        controller.set_custom_viewport_override(tuple(map(float, size)))

    with patch.object(BubbleSimulation, 'snapshot', observe), patch.object(driver, '_configure', configure):
        result = replay_clip(clip, 'bubble', preset=args.preset-1, snapshots_at=wanted)
    target = TransitionCapture(*size)
    host = QuickVisualizerRenderHost()
    animation, contacts, gpu = [], [], []
    try:
        for ordinal, index in enumerate(wanted):
            snapshot = result['snapshots'][index]
            presentation = resize_visualizer_presentation(
                snapshot.presentation, display_size=size, outer_origin=(0, 0),
                relative_scale=1., viewport_extent=size, committed_outer_size=size)
            snapshot = replace(snapshot, presentation=presentation)
            rgba, ms = _draw(host, target, snapshot, size, size)
            gpu.append(ms)
            image = Image.fromarray(rgba).convert('RGB')
            image.save(args.output / f'frame_{ordinal:04d}.png')
            if ordinal % max(1, round(args.fps)) == 0:
                tile = image.copy()
                tile.thumbnail((400, 250))
                label = Image.new('RGB', (400, 275), '#111827')
                label.paste(tile, (0, 0))
                ImageDraw.Draw(label).text((8, 255), f'{times[index]:.2f}s original Bubble', fill='white')
                contacts.append(label)
            image.thumbnail((960, 540))
            animation.append(image)
        sheet = Image.new('RGB', (1200, 275*math.ceil(len(contacts)/3)), '#111827')
        for i, tile in enumerate(contacts):
            sheet.paste(tile, ((i % 3)*400, (i // 3)*275))
        sheet.save(args.output / 'contact.png')
        animation[0].save(args.output / 'motion.gif', save_all=True, append_images=animation[1:],
                          duration=round(1000/args.fps), loop=0)
        objects = {}
        for row in rows:
            for obj in row['objects']:
                if obj['record'][3] < .999 or obj['popping'] or obj['exiting']:
                    continue
                objects.setdefault(obj['id'], []).append((row['time_s'], obj))
        stable = []
        for ident, samples in objects.items():
            if len(samples) < 100 or samples[-1][0] - samples[0][0] < 1:
                continue
            radii = [obj['radius_px'] for _, obj in samples]
            stable.append(dict(id=ident, large=samples[0][1]['large'], time_span=[samples[0][0], samples[-1][0]],
                               radius_px=distribution(radii), excursion_share=(max(radii)-min(radii))/min(radii)))
        summary = dict(clip=str(args.clip.resolve()), preset=args.preset, size=size, renderer=target.driver,
                       commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                       clip_sha256=hashlib.sha256(args.clip.read_bytes()).hexdigest(),
                       preset_path=activation.preset_path, settings=activation.resolved_config,
                       source_indices=wanted,
                       stable_ids=stable, gpu_ms=distribution(gpu[1:]),
                       scope='accepted 2D Bubble, same recorded post-DSP features/cadence; distinct authored art, no parameters retuned')
        (args.output / 'summary.json').write_text(json.dumps(summary, indent=2))
        with (args.output / 'custody.jsonl').open('w') as stream:
            for row in rows:
                stream.write(json.dumps(row, separators=(',', ':'))+'\n')
        print('saved', len(wanted), 'frames;', len(stable), 'tracked IDs;', target.driver)
    finally:
        host.release_resources()
        target.close()


if __name__ == '__main__':
    main()
