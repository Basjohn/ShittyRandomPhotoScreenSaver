#!/usr/bin/env python3
"""Bounded, Qt-free EB camera/near-layer discontinuity probe on the real authored presets.

    py -3.14 tools/visualizer_replay/extruded_bubble_projection_gate_probe.py
    py -3.14 tools/visualizer_replay/extruded_bubble_projection_gate_probe.py --json

Mirrors the declared pinhole projection, tangent-cone silhouette and sceneNearCircle
primitive; checks their source signatures before reporting. It does NOT render the full
scene, establish cause of a particular live judder, or accept any visual behavior.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def silhouette_aspect(angle_deg: float, *, fov_y_degrees=45.0, sphere_radius=0.4, distance=10.0, frame=(1600, 900), samples=1440):
    """Sample tangent rays to a physical sphere, project through production's FOV and convert to pixels."""
    assert 0 < sphere_radius < distance
    angle = math.radians(angle_deg)
    alpha = math.asin(sphere_radius / distance)
    axis = (math.sin(angle), 0.0, -math.cos(angle))
    sideways = (math.cos(angle), 0.0, math.sin(angle))
    tan_y = math.tan(math.radians(fov_y_degrees) / 2.0)
    tan_x = tan_y * frame[0] / frame[1]
    bounds = [float('inf'), float('-inf'), float('inf'), float('-inf')]
    for i in range(samples):
        p = 2.0 * math.pi * i / samples
        ray = [axis[k] * math.cos(alpha) + math.sin(alpha) * (sideways[k] * math.cos(p)
               + (1.0 if k == 1 else 0.0) * math.sin(p)) for k in range(3)]
        xx = (ray[0] / -ray[2] / tan_x + 1.0) * frame[0] * 0.5
        yy = (ray[1] / -ray[2] / tan_y + 1.0) * frame[1] * 0.5
        bounds = [min(bounds[0], xx), max(bounds[1], xx), min(bounds[2], yy), max(bounds[3], yy)]
    return {"off_axis_degrees": angle_deg,
            "pixel_width": round(bounds[1]-bounds[0], 4),
            "pixel_height": round(bounds[3]-bounds[2], 4),
            "width_to_height": round((bounds[1]-bounds[0]) / (bounds[3]-bounds[2]), 5)}


def near_circle(front_depth: float, focus: float, aperture: float, pixel_scale: float):
    """Exact scalar algebra of sceneNearCircle in scene3d_spheres.py."""
    return pixel_scale * (aperture / 3.0) * max(focus-front_depth, 0.0) / max(front_depth, 2.5)


def parameters(slot: int):
    basename = {1: "preset_1_sunlit_surface.json", 7: "preset_7_ember_drift.json"}[slot]
    p = ROOT / "presets/visualizer_modes/extruded_bubble" / basename
    return json.loads(p.read_text(encoding="utf-8"))["snapshot"]["widgets"]["spotify_visualizer"]


def check_owners():
    scene = (ROOT / "rendering/gl_programs/extruded_bubble_scene.py").read_text(encoding="utf-8")
    spheres = (ROOT / "rendering/gl_programs/scene3d_spheres.py").read_text(encoding="utf-8")
    shaders = (ROOT / "rendering/gl_programs/extruded_bubble_program.py").read_text(encoding="utf-8")
    renderer = (ROOT / "rendering/quick/visualizer/implementations/extruded_bubble.py").read_text(encoding="utf-8")
    assert "FOV_Y_DEGREES = 45.0" in scene
    assert 'fov_y_degrees=fov_y)' in renderer
    assert 'physical_camera(' in renderer
    assert 'camera_look_pan(' not in renderer
    assert 'uEye' in shaders and 'aSphere.xyz - uEye' in shaders
    assert 'shift = (0.0, 0.0)' in renderer
    assert "float sceneNearCircle(float frontDepth, float focus, float aperture, float pixelScale)" in spheres
    assert "float coc = sceneNearCircle(frontDepth, uFocus, uAperture, uNearCoc);" in shaders
    assert "bool near_ = aExtra.y < 0.5 && coc > 1.5;" in shaders
    assert "(coc > 1.5) != (uNearLayer > 0.5)" in shaders  # clusters too
    assert '"uNearCoc": 22.0 * height / 941.0' in renderer


def inspect():
    check_owners()
    projection = [silhouette_aspect(a) for a in (0, 15, 30, 40)]
    # Compare the same pixel position with the narrower DEFAULT FOV and the
    # previous wide FOV: the off-axis ray angles are different. At the same
    # FIXED angle a rectilinear projection's elongation is independent of FOV.
    fov_comparison = {}
    for fov in (62.0, 45.0):
        xy = 0.75  # 75% of the positive half-width from centre
        angle = math.degrees(math.atan(xy * (1600 / 900) * math.tan(math.radians(fov) / 2.0)))
        result = silhouette_aspect(angle, fov_y_degrees=fov)
        fov_comparison[f"FOV{int(fov)}"] = {"screen_half_width_fraction": xy,
                                            "off_axis_degrees": round(angle, 4),
                                            "width_to_height": result["width_to_height"]}
    gates = {}
    for slot in (1, 7):
        p = parameters(slot)
        focus = 2.5+3*float(p['extruded_bubble_focus'])
        aperture = 0.3+2.7*float(p['extruded_bubble_aperture'])
        # 941px tall, scene camera scale=1; threshold invert when front depth >=2.5.
        scale = 22.0
        factor = scale * aperture / 3.0
        critical = focus * factor/(factor+1.5)
        assert critical >= 2.5 and abs(near_circle(critical, focus, aperture, scale) - 1.5) < 1e-9
        # Physical centre held fixed, changing true bubble size +/- 2% about r=1.
        depth = critical + 1.0
        states = [{"physical_radius": round(r, 3),
                   "circle_px": round(near_circle(depth-r, focus, aperture, scale), 4),
                   "near_layer": near_circle(depth-r, focus, aperture, scale) > 1.5}
                  for r in (0.98, 1.0, 1.02)]
        gates[f'P{slot}'] = {"focus": round(focus, 4), "aperture": round(aperture, 4),
                            "critical_front_depth": round(critical, 5),
                            "held_centre_depth": round(depth, 5), "states": states}
    return {"claim_scope": "analytic owner-checked geometry; not native full-GL frame or observed judder causation",
            "projection": projection, "fov_comparison": fov_comparison, "near_layer_gate": gates}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    result = inspect()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print('Physical sphere under 45-degree default rectilinear EB camera, 1600x900:')
        for item in result['projection']:
            print(f" off-axis {item['off_axis_degrees']:2d} deg: {item['width_to_height']:.4f} horizontal:vertical pixel span")
        for key, value in result['fov_comparison'].items():
            print(f" screen x=75% of half-width: {key} at {value['off_axis_degrees']:.2f}° from centre -> "
                  f"{value['width_to_height']:.3f}:1 aspect")
        for slot, item in result['near_layer_gate'].items():
            print(f" {slot}: CoC 1.5px boundary at front depth {item['critical_front_depth']:.4f},"
                  f" focus {item['focus']:.3f}, aperture {item['aperture']:.3f}")
            for state in item['states']:
                print(f"  radius {state['physical_radius']:.2f} -> CoC {state['circle_px']:.4f} px"
                      f" -> {'defocus' if state['near_layer'] else 'normal'} pass")
    return 0


if __name__ == '__main__':
    sys.exit(main())
