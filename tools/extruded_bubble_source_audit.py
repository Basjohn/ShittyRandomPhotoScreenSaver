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


def _rec(*, x=1.3, y=0.4, z=-10., radius=.9, alpha=1.0, ident=1):
    return (x, y, z, radius, alpha, 0.0, float(ident), -1.0)


def audit() -> dict:
    _camera, _inverse, tan, _proj = scene.camera(0.0, 0.0, 16 / 9)
    source = _rec()
    # Packing now has no camera inputs. Actual renderer/GPU invariance is tested
    # independently; these read-only receipts are not pixel acceptance.
    opaque = scene.bubble_instances(source)[0]
    near = scene.bubble_instances(_rec(z=-4.))[0]
    far = scene.bubble_instances(_rec(z=-16., ident=2))[0]
    near_r = float(near[3] / (tan[1] * 4.))
    far_r = float(far[3] / (tan[1] * 16.))
    fading = scene.bubble_instances(_rec(alpha=.25))[0]
    # Amount owns density; per-point radiance retains its full-strength calibration.
    particle_quiet, bright_quiet = scene.speck_amount(0.2)
    particle_loud, bright_loud = scene.speck_amount(0.8)
    result = {
        'evidence_scope': 'static CPU geometry and Settings mapping; NOT actual rendered frames/audio acceptance',
        'camera_dependence': {
            'state': 'physical xyz/radius packed directly; no camera arguments or wrapping',
            'packed_world_xyz_radius': opaque[:4].tolist(),
            'owner': 'simulation physical world; rendering/gl_programs/extruded_bubble_scene.py packing',
            'requires': 'fixed world positions across camera turn and tilt; no camera-following reinstallation',
        },
        'perspective': {
            'state': 'equal physical radii retain real perspective',
            'near_depth_units': 4.,
            'far_depth_units': 16.,
            'near_projected_radius_normalized': near_r,
            'far_projected_radius_normalized': far_r,
            'requires': 'true 3D size-depth/parallax, without synthetic giant cohorts',
        },
        'fade': {
            'state': 'lifetime opacity is a separate instance attribute',
            'instance_material_opacity': float(fading[6]),
            'logical_alpha': 0.25,
            'world_radius_ratio_to_opaque': float(fading[3] / opaque[3]),
            'requires': 'separate physical size and material opacity; real birth/death transparency, including fused clusters',
        },
        'emission': {
            'problem': 'Range resolved once; squared density with constant per-point radiance is an explicit Amount semantic change; idle readability and active glare still unaccepted',
            'example_range': [0.2, 0.8],
            'simulation_quiet_and_loud': [0.2, 0.8],
            'renderer_density_share_quiet_and_loud': [particle_quiet, particle_loud],
            'renderer_brightness_quiet_and_loud': [bright_quiet, bright_loud],
            'requires': 'capture of actual quiet/music counts and pixels; do not label candidate visually accepted',
        },
        'bead_direction': {
            'state': 'procedural chains/snow/wakes inhabit the fixed world; transverse axes come from the same pure world geometry',
            'owner': 'extruded_bubble_geometry.stream_basis; renderer uniforms and production BEAD_VERTEX',
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
