"""N5.6 P: Extruded Bubble's native passes into the core's bucketed scene targets place the scene as Python's viewport
does (``extruded_bubble_shaders.PLACED``): the clip position through ``srpssTargetClip`` with the scene's pixels
(``u_scene_item.zw``) and the target's (``u_target_px``), nothing drawn in the slack. Drawn over the whole bucket, the
native scene was magnified by the bucket over the scene's pixels (640/630 by 448/420 on a 630 x 420 card, 28 Nov)."""
from __future__ import annotations

import re

import pytest

from rendering.native import extruded_bubble_shaders as shaders

_CLIP = "gl_Position = srpssTargetClip(gl_Position, u_scene_item.zw, u_target_px);"
_ITEM_ONLY = "srpssItemOnly(u_scene_item.zw, u_target_px);"


def _passes_and_targets():
    from rendering.native import extruded_bubble_program as program

    built = program.program((4,))
    return built["passes"], built["targets"]


def test_every_pass_into_a_bucketed_target_is_placed():
    passes, targets = _passes_and_targets()
    exact = {t.name for t in targets if getattr(t, "allocation", None) == "exact"}
    drawn = [p for p in passes if type(p).__name__ == "ModePass"]
    assert {p.name for p in drawn if p.target not in exact} == set(shaders.PLACED)
    assert not {p.name for p in drawn if p.target in exact} & set(shaders.PLACED)


def _main(text: str) -> str:
    return text[text.rindex("void main() {"):]


@pytest.mark.parametrize("program", shaders.PROGRAMS)
def test_placed_texts_clip_into_the_scene_pixels(program):
    files = shaders.shader_files()
    vertex, fragments = files[f"eb_{program}.vert"], [files[f"eb_{program}.frag"]]
    if program in shaders.TRANSPARENT:
        fragments.append(files[f"eb_{program}_sorted.frag"])
    placed = program in shaders.PLACED
    assert (_CLIP in _main(vertex)) is placed
    for fragment in fragments:
        assert (_main(fragment).startswith("void main() {\n    " + _ITEM_ONLY)) is placed
        assert ("#define SRPSS_SCENE_ITEM_ONLY" in fragment) is placed
    for text in (vertex, *fragments):
        own = re.search(r"uniform\s+Eb\w+\s*\{([^{}]*)\}", text).group(1)
        assert all(member in own for member in ("u_scene_item", "u_target_px")) or not placed


def test_control_without_placement_the_texts_are_unplaced(monkeypatch):
    # The texts before the fix (no program placed): the checks above tell them apart.
    monkeypatch.setattr(shaders, "PLACED", ())
    files = shaders.shader_files()
    assert _CLIP not in files["eb_specks.vert"] and _ITEM_ONLY not in files["eb_specks.frag"]
    assert "u_scene_item" not in files["eb_shells.vert"]


def _clip(clip, viewport, target_px, z_flag=1.0, w_flag=0.0):
    """``srpssTargetClip``'s arithmetic (conventions.SRPSS_TARGET_CLIP_GLSL), in Python."""
    x, y, z, w = clip
    if z_flag > 0.5:
        sx, sy = viewport[0] / target_px[0], viewport[1] / target_px[1]
        x, y = x * sx + w * (sx - 1.0), y * sy + w * (sy - 1.0)
    if w_flag > 0.5:
        z = 0.5 * (z + w)
    return x, y, z, w


def test_the_scene_takes_the_buckets_first_pixels():
    # The scene's clip corners land on the bucket's first 630 columns and 420 rows (pixel = (ndc + 1) / 2 * target).
    viewport, target = (630.0, 420.0), (640.0, 448.0)
    for ndc, pixel in (((-1.0, -1.0), (0.0, 0.0)), ((1.0, 1.0), (630.0, 420.0))):
        x, y, _z, w = _clip((ndc[0] * 2.0, ndc[1] * 2.0, 0.0, 2.0), viewport, target)
        assert ((x / w + 1.0) * 0.5 * target[0], (y / w + 1.0) * 0.5 * target[1]) == pytest.approx(pixel)


def test_control_unplaced_the_scene_is_the_buckets_size():
    # The texts as they were: the clip position unchanged, so the scene's far corner is the bucket's.
    x, y, _z, w = _clip((2.0, 2.0, 0.0, 2.0), (630.0, 420.0), (640.0, 448.0), z_flag=0.0)
    assert ((x / w + 1.0) * 320.0, (y / w + 1.0) * 224.0) == pytest.approx((640.0, 448.0))
