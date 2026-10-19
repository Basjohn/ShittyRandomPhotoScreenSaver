"""Read-only Extruded Bubble source/geometry diagnostic, NOT a visual acceptance test.

Run on the supplied working tree without changing Settings, presets, environment variables, runtime or GPU state:
    .venv/Scripts/python.exe tools/extruded_bubble_source_audit.py --output tmp/eb_source_audit.json

This deliberately reports current failure mechanisms instead of declaring synthetic numeric results a PASS.
The rendering agent must separately prove changes with actual captured, annotated frames and GPU pass timings.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np

from rendering.gl_programs import extruded_bubble_scene as scene


def _rec(*, x=0.13, y=0.04, z=0.5, radius=0.10, alpha=1.0, ident=1):
    return (x, y, z, radius, alpha, 0.0, float(ident), -1.0)


def audit() -> dict:
    _camera, _inverse, tan, _proj = scene.camera(0.0, 0.0, 16 / 9)
    source = _rec()
    # A physical point's WORLD position must not depend on the camera's yaw. This one does.
    sample_turns = tuple(float(x) for x in np.linspace(0.0, 2.0, 361))
    world = np.array([scene.bubble_instances(source, tan, (yaw, 0.0))[0, :3] for yaw in sample_turns])
    steps = np.linalg.norm(np.diff(world, axis=0), axis=1)
    moved = np.linalg.norm(world - world[0], axis=1)
    # Depth-space scaling cancels perspective (r_world = r_normalized * depth * tanY).
    near = scene.bubble_instances(_rec(z=0.0), tan)[0]
    far = scene.bubble_instances(_rec(z=1.0, ident=2), tan)[0]
    projected = lambda row, depth: float(row[3] / (tan[1] * depth))
    near_r = projected(near, scene.DEPTH_NEAR)
    far_r = projected(far, scene.DEPTH_NEAR + scene.DEPTH_SPAN)
    # The logical alpha is not transported as a material-opacity attribute: fade scales radius by sqrt(alpha).
    opaque = scene.bubble_instances(_rec(alpha=1.0), tan)[0]
    fading = scene.bubble_instances(_rec(alpha=0.25), tan)[0]
    # The old second use of the Particles Range has a source candidate fix; the caller already gives ranged values.
    params = {'extruded_bubble_particles': (0.2, 0.8)}
    particle_quiet, bright_quiet = scene.speck_amount(params, 0.2)
    particle_loud, bright_loud = scene.speck_amount(params, 0.8)
    result = {
        'evidence_scope': 'static CPU geometry and Settings mapping; NOT actual rendered frames/audio acceptance',
        'camera_dependence': {
            'problem': 'world-space position changes with camera yaw due to angle-period wrap',
            'max_displacement_world_units': float(moved.max()),
            'largest_one_step_displacement_world_units': float(steps.max()),
            'offending_source': 'rendering/gl_programs/extruded_bubble_scene.py: _wrapped_turn, bubble_instances, wake_instances, cluster_instances',
            'requires': 'fixed world positions across camera turn and tilt; no camera-following reinstallation',
        },
        'perspective': {
            'problem': 'pixel radius cancels depth: same normalized radius near/far',
            'near_depth_units': scene.DEPTH_NEAR,
            'far_depth_units': scene.DEPTH_NEAR + scene.DEPTH_SPAN,
            'near_projected_radius_normalized': near_r,
            'far_projected_radius_normalized': far_r,
            'requires': 'true 3D size-depth/parallax, without synthetic giant cohorts',
        },
        'fade': {
            'problem': 'bubble alpha alters geometric radius, is not sent to regular shell material',
            'logical_alpha': 0.25,
            'world_radius_ratio_to_opaque': float(fading[3] / opaque[3]),
            'requires': 'separate physical size and material opacity; real birth/death transparency, including fused clusters',
        },
        'emission': {
            'problem': 'previous double Particles Range mapping removed in source candidate; squared density and visible response still unaccepted',
            'example_range': [0.2, 0.8],
            'simulation_quiet_and_loud': [0.2, 0.8],
            'renderer_density_share_quiet_and_loud': [particle_quiet, particle_loud],
            'renderer_brightness_quiet_and_loud': [bright_quiet, bright_loud],
            'requires': 'capture of actual quiet/music counts and pixels; do not label candidate visually accepted',
        },
        'bead_direction': {
            'problem': 'each chain gets a camera-relative wrapping rotation independent of fixed stream orientation',
            'offending_source': 'rendering/gl_programs/extruded_bubble_program.py: _BEAD_GLSL.wrapTurn / turnAbout',
            'requires': 'coherent stream vector in world coordinates and stable chain positions during orbit',
        },
        'acceptance': 'Every item remains [~]. Need operator OR visual-capable agent with offscreen render/capture; GLSL compilation and synthetic output are not visual proof.',
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='write the read-only JSON diagnostic; no file written if omitted')
    args = parser.parse_args()
    result = audit()
    payload = json.dumps(result, indent=2) + '\n'
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding='utf-8')
    print(payload, end='')


if __name__ == '__main__':
    main()
