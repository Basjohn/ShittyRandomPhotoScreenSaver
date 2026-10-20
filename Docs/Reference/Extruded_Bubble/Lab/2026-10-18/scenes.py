"""S4 preset authoring harness (scratch): each lab scene as Settings values only, rendered through the production host
from a real recording and laid beside its mock and the lab's render.

usage: .venv/Scripts/python tmp/eb_s4/scenes.py [Scene,...]
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from rendering.gl_error_policy import disable_per_call_gl_error_checking  # noqa: E402

assert disable_per_call_gl_error_checking()
from PIL import Image, ImageDraw  # noqa: E402

from tools.extruded_bubble_capture import capture  # noqa: E402

OUT = ROOT / "tmp" / "eb_s4"
CLIP = ROOT / "logs" / "visualizer_recordings" / "dontyouseemetrying_mixed.jsonl"


def rgb(*c):
    return [round(max(0.0, min(1.0, v)) * 255) for v in c] + [255]


def light_from(sky, water):
    """The light colour whose derived sky tint (mix(water hue, light, 0.6)) is the lab's sky."""
    top = max(water)
    hue = [w / top for w in water]
    return rgb(*[(s - 0.4 * h) / 0.6 for s, h in zip(sky, hue)])


def direction(x, y, z):
    length = math.sqrt(x * x + y * y + z * z)
    x, y, z = x / length, y / length, z / length
    return [round(math.degrees(math.atan2(x, -z)), 1), round(math.degrees(math.asin(y)), 1)]


def view_direction(x, y, z, pitch):
    """A lab ``light_view`` (view space at the authored pitch) as the Light Direction mapper's world value."""
    p = math.radians(pitch)
    return direction(x, y * math.cos(p) - z * math.sin(p), y * math.sin(p) + z * math.cos(p))


def stream(x, y, z):
    """A lab ``travel`` (across, up the screen, into the scene) as the Stream Direction mapper's value."""
    length = math.sqrt(x * x + y * y + z * z)
    return [round(math.degrees(math.atan2(x, y)), 1), round(math.degrees(math.asin(z / length)), 1)]


def tilt(pitch):
    return round(max(-0.5, min(0.5, (pitch - 16.0) / 90.0)), 3)


P = "extruded_bubble_"
SCENES = {
    "ExBubble1": {
        "light_type": "Sunlit Surface", "water_colour": rgb(0.19, 0.26, 0.36), "depth_colour": rgb(0.1, 0.16, 0.24),
        "light_colour": light_from((0.82, 0.9, 0.98), (0.19, 0.26, 0.36)), "light_direction": direction(0.05, 0.75, -1.0),
        "light_strength": 1.0, "surface_brightness": 0.8, "rays": [0.6, 0.8], "iridescence": 0.3, "exposure": 1.0, "bead_chains": [5, 8],
        "tilt": tilt(16.0),
    },
    "ExBubble2": {
        "light_type": "Sunlit Surface", "water_colour": rgb(0.03, 0.08, 0.16), "depth_colour": rgb(0.022, 0.055, 0.12),
        "light_colour": light_from((0.6, 0.76, 0.95), (0.03, 0.08, 0.16)), "light_direction": direction(0.0, 0.7, -1.0),
        "light_strength": 1.0, "surface_brightness": 1.5, "rays": [0.6, 0.8], "iridescence": 0.35, "exposure": 0.9, "bead_chains": [5, 8],
        "tilt": tilt(16.0),
    },
    "ExBubble3": {
        "light_type": "Sunlit Surface", "water_colour": rgb(0.024, 0.046, 0.07), "depth_colour": rgb(0.016, 0.03, 0.046),
        "light_colour": light_from((0.52, 0.68, 0.85), (0.024, 0.046, 0.07)), "light_direction": direction(0.0, 0.8, -1.0),
        "light_strength": 1.0, "surface_brightness": 1.0, "rays": [0.3, 0.5], "iridescence": 0.3, "exposure": 0.82, "bead_chains": [5, 8],
        "tilt": tilt(18.0),
    },
    "ExBubble4": {
        "light_type": "Sunlit Surface", "water_colour": rgb(0.04, 0.1, 0.17), "depth_colour": rgb(0.05, 0.11, 0.2),
        "light_colour": light_from((0.48, 0.66, 0.84), (0.04, 0.1, 0.17)), "light_direction": direction(0.15, 0.65, -1.0),
        "light_strength": 1.0, "surface_brightness": 1.25, "rays": [0.35, 0.55], "ray_softness": 0.9,
        "iridescence": 0.5, "exposure": 0.82, "haze": 0.3, "bead_chains": [4, 6], "aperture": 0.33, "tilt": tilt(14.0),
    },
    "ExBubble5CameraAbyss": {
        "light_type": "Deep Light", "water_colour": rgb(0.02, 0.08, 0.13), "depth_colour": rgb(0.016, 0.05, 0.08),
        "light_colour": rgb(0.55, 0.75, 1.0), "light_direction": view_direction(0.75, 0.75, -1.0, 6.0),
        "light_strength": 1.0, "stream_direction": stream(0.4, 1.0, 0.0),
        "rays": [0.08, 0.18], "veils": 0.3, "iridescence": 0.9, "clarity": 1.0, "rim_glow": 1.0, "haze": 0.6,
        "sparkle": 1.0, "softness": 0.0, "particles": [0.3, 0.4], "particle_warmth": 0.85, "focus": 0.23,
        "aperture": 0.11, "exposure": 1.0, "bead_chains": [2, 3], "columns": 0.75, "drift": [0.1, 0.25], "sway": 0.15, "tilt": tilt(6.0),
    },
    "ExBubble5Cameradown": {
        "light_type": "Deep Light", "water_colour": rgb(0.03, 0.11, 0.2), "depth_colour": rgb(0.05, 0.12, 0.2),
        "light_colour": rgb(0.55, 0.68, 1.0), "light_direction": direction(0.3, 0.8, -1.0), "light_strength": 0.7,
        "rays": [0.3, 0.5], "iridescence": 1.0, "clarity": 0.94, "rim_glow": 1.67, "haze": 0.4, "sparkle": 0.7,
        "softness": 0.0, "particles": [0.5, 0.6], "particle_warmth": 0.85, "exposure": 1.0, "bead_chains": [4, 6],
        "tilt": tilt(-32.0),
    },
    "ExBubble6Diagonal": {
        "light_type": "Deep Light", "water_colour": rgb(0.03, 0.13, 0.17), "depth_colour": rgb(0.012, 0.05, 0.06),
        "light_colour": rgb(1.0, 0.52, 0.2), "light_direction": view_direction(1.0, 0.68, -1.0, 4.0),
        "light_strength": 0.12,
        "rays": [0.1, 0.2], "veils": 0.35, "haze": 0.6, "iridescence": 0.3, "clarity": 0.88, "rim_glow": 0.5,
        "sparkle": 1.5, "softness": 0.2, "particles": [0.85, 1.0], "particle_colour": rgb(1.0, 0.25, 0.02),
        "particle_size": 1.6, "particle_glow": 0.6, "particle_warmth": 0.9, "particle_bands": True,
        "band_contrast": 1.0, "stream_direction": stream(1.0, -0.3, 0.15), "sway": 0.25, "focus": 0.3, "aperture": 0.44,
        "exposure": 0.85, "tilt": tilt(4.0),
    },
}


def settings(scene):
    return {P + key: value for key, value in SCENES[scene].items()}


def render(scene, start=20.0):
    out = OUT / "scenes" / scene
    capture(out, CLIP, size=(1672, 941), window=None, overrides=settings(scene), start=start, duration=0.4, fps=2.5,
            gif=False)
    product = Image.open(out / "frame_0000.png").convert("RGB")
    mock = Image.open(ROOT / "tmp" / "Bubbleexamples" / f"{scene}.png").convert("RGB").resize((1672, 941))
    lab = Image.open(OUT / "lab" / f"lab_{scene}.png").convert("RGB").resize((1672, 941))
    sheet = Image.new("RGB", (1672, 980), "#111")
    for i, (label, image) in enumerate((("mock", mock), ("lab", lab), ("product", product))):
        tile = image.resize((836, 470))
        x, y = (i % 2) * 836, (i // 2) * 490
        sheet.paste(tile, (x, y))
        ImageDraw.Draw(sheet).text((x + 8, y + 474), f"{scene}: {label}", fill="white")
    sheet.save(OUT / f"cmp_{scene}.png")
    Image.fromarray(__import__("numpy").hstack([__import__("numpy").asarray(mock), __import__("numpy").asarray(product)])
                    ).save(OUT / f"pair_{scene}.png")


if __name__ == "__main__":
    names = sys.argv[1].split(",") if len(sys.argv) > 1 else list(SCENES)
    for name in names:
        render(name)
    (OUT / "scenes.json").write_text(json.dumps(SCENES, indent=2), encoding="utf-8")
