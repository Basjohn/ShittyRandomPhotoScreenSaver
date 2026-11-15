"""N3.1's harness scene (Current_Plan.md item 8b, N3.1; decision D14): the scene targets as data, harness-only and never
registered (like ``probe_rings``). A still (no stream): its program, settings and card are its frame.

- ``scene``: surface-sized, two attachments (``colour`` RGBA16F, the HDR intermediate; ``emission`` RGBA16F) and a depth,
  the shape of Extruded Bubble's overlay-with-bloom target (``extruded_bubble.py``: ``depth_texture``, ``background()``,
  ``hdr``). Passes: ``planes`` (a tilted plane through ``gl_FragDepth``, colour past white), ``nearer`` (a nearer plane
  over the lower half, depth test less, emission masked), the capture ``background`` (Python's ``background()``), then
  ``after`` (depth test less_equal against the loaded depth, no depth write, straight alpha over, emission masked).
- ``ambient``: explicit size, ``coverage`` RGBA8 (premultiplied over) and ``light`` RGBA16F (added): Bubble's ambient
  target's shape (``bubble_ambient_gl.py``); ``u_glow`` 0 writes no light (the attachment holds its clear).
- ``show``: the surface's pass, sampling the captures and the ambient target (a look, not a parity record).

The fragments are product-shaped (``vUv`` y up over the pass's content, one block each at binding 18) so the Python
reference (``SceneTarget`` and a GL target with the ambient owner's states) draws the same files.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

#: (pass name, file) of every fragment.
FRAGMENTS = (("planes", "scene_planes.frag"), ("nearer", "scene_nearer.frag"), ("after", "scene_after.frag"),
             ("ambient", "ambient_light.frag"), ("show", "surface_show.frag"), ("show_colour", "show_colour.frag"),
             ("lin_planes", "lin_planes.frag"), ("lin_nearer", "lin_nearer.frag"), ("lin_show", "lin_show.frag"))

SETTINGS = {
    "u_hdr_gain": 2.5, "u_near_depth": 0.25, "u_far_depth": 0.75, "u_emission": 0.8,
    "u_nearer_colour": [0.1, 0.6, 0.9, 1.0], "u_nearer_depth": 0.4, "u_mask_band": 0.0,
    "u_after_colour": [1.0, 0.85, 0.2, 0.5], "u_after_depth": 0.5,
    "u_disc_colour": [0.9, 0.5, 0.2, 1.0], "u_glow": 1.0, "u_radius": 0.08,
    "u_depth_shade": 0.5,
}


def shader_text(filename: str) -> str:
    return (HERE / filename).read_text(encoding="utf-8")


def bake_all(folder: Path) -> dict[str, bytes]:
    """Every fragment baked by ``tools/regen_qrc.py``'s own baker (no module build): pass name -> pack."""
    import probe_rings

    return {name: probe_rings.bake(shader_text(filename), filename, folder) for name, filename in FRAGMENTS}


def targets(*, samples: int = 1, ambient_size: tuple[int, int] = (300, 170)):
    """The program's two targets (``rendering.native.mode.ModeTarget``): ``samples`` is the scene's request."""
    from rendering.native.mode import ModeTarget, TargetAttachment

    scene = ModeTarget("scene", (TargetAttachment("colour", "rgba16f"), TargetAttachment("emission", "rgba16f")),
                       depth=True, samples=int(samples))
    ambient = ModeTarget("ambient", (TargetAttachment("coverage", "rgba8"), TargetAttachment("light", "rgba16f")),
                         size=(int(ambient_size[0]), int(ambient_size[1])))
    return scene, ambient


def passes(packs: dict[str, bytes], *, with_show: bool = True):
    """The program's passes in order (``ModePass`` and ``CapturePass``)."""
    from rendering.native.mode import CapturePass, ModePass, PassOutput, PassSampler

    built = [
        ModePass("planes", packs["planes"], "replace", target="scene", depth_test="always", depth_write=True),
        ModePass("nearer", packs["nearer"], "replace", target="scene",
                 outputs=(PassOutput(True, "replace"), PassOutput(False)), depth_test="less", depth_write=True),
        CapturePass("background", "scene"),
        ModePass("after", packs["after"], "alpha", target="scene",
                 outputs=(PassOutput(True, "alpha"), PassOutput(False)), depth_test="less_equal", depth_write=False),
        ModePass("ambient", packs["ambient"], "premultiplied", target="ambient",
                 outputs=(PassOutput(True, "premultiplied"), PassOutput(True, "additive"))),
    ]
    if with_show:
        built.append(ModePass("show", packs["show"], "replace", samplers=(
            PassSampler("u_scene", "scene.capture_colour", "linear"),
            PassSampler("u_depth", "scene.capture_depth", "nearest"),
            PassSampler("u_cover", "ambient.coverage", "linear"),
            PassSampler("u_light", "ambient.light", "linear"))))
    return tuple(built)


def lin_program(packs: dict[str, bytes], *, samples: int, mask_band: float):
    """D14 point 10's means (b) (and (a) beside it): the ``lin`` target (an RGBA8 colour, an R32F ``lin`` attachment
    resolved to the nearest sample, a depth), the plane and the masked nearer plane into it, a surface pass reading
    ``lin.lin`` and ``lin.depth``: (passes, targets, settings)."""
    from rendering.native.mode import ModePass, ModeTarget, PassOutput, PassSampler, TargetAttachment

    target = ModeTarget("lin", (TargetAttachment("colour", "rgba8"),
                                TargetAttachment("lin", "r32f", (1.0, 1.0, 1.0, 1.0), resolve="nearest")),
                        depth=True, samples=int(samples))
    passes = (
        ModePass("lin_planes", packs["lin_planes"], "replace", target="lin", depth_test="always", depth_write=True),
        ModePass("lin_nearer", packs["lin_nearer"], "replace", target="lin",
                 outputs=(PassOutput(True, "replace"), PassOutput(True, "replace")), depth_test="less",
                 depth_write=True),
        ModePass("lin_show", packs["lin_show"], "replace", samplers=(
            PassSampler("u_lin", "lin.lin", "nearest"), PassSampler("u_lin_depth", "lin.depth", "nearest"))),
    )
    values = {"u_near_depth": SETTINGS["u_near_depth"], "u_far_depth": SETTINGS["u_far_depth"],
              "u_nearer_depth": SETTINGS["u_nearer_depth"], "u_mask_band": float(mask_band)}
    return passes, (target,), values


def cost_part_program(packs: dict[str, bytes], part: str, *, samples: int):
    """The cost breakdown's programs on the scene target alone (the lead's 15 Nov ask: where the four-sample time
    goes): ``clear`` (the clearing draw and the plane), ``planes2`` (the plane twice: its second draw is what one more
    full draw into every attachment costs, the clearing draw's own cost), ``draws`` (plane, nearer, after; nothing read, so nothing
    resolved), ``read`` (``draws`` and a surface pass reading the colour: one colour resolve), ``capture`` (``read``
    with the capture between nearer and after: the depth read, resolves at both runs). (passes, targets, settings)."""
    from rendering.native.mode import CapturePass, ModePass, ModeTarget, PassOutput, PassSampler, TargetAttachment

    target = ModeTarget("scene", (TargetAttachment("colour", "rgba16f"), TargetAttachment("emission", "rgba16f")),
                        depth=True, samples=int(samples))
    planes = ModePass("planes", packs["planes"], "replace", target="scene", depth_test="always", depth_write=True)
    nearer = ModePass("nearer", packs["nearer"], "replace", target="scene",
                      outputs=(PassOutput(True, "replace"), PassOutput(False)), depth_test="less", depth_write=True)
    after = ModePass("after", packs["after"], "alpha", target="scene",
                     outputs=(PassOutput(True, "alpha"), PassOutput(False)), depth_test="less_equal", depth_write=False)
    show = ModePass("show_colour", packs["show_colour"], "replace",
                    samplers=(PassSampler("u_scene", "scene.colour", "linear"),))
    again = ModePass("planes_again", packs["planes"], "replace", target="scene", depth_test="always", depth_write=True)
    passes = {"clear": (planes,), "planes2": (planes, again), "draws": (planes, nearer, after),
              "read": (planes, nearer, after, show),
              "capture": (planes, nearer, CapturePass("background", "scene"), after, show)}[part]
    names = {"clear": ("planes",), "planes2": ("planes",), "draws": ("planes", "nearer", "after"),
             "read": ("planes", "nearer", "after"), "capture": ("planes", "nearer", "after")}[part]
    values = {k: v for k, v in SETTINGS.items()
              if any(k in shader_text(dict(FRAGMENTS)[n]) for n in names)}
    return passes, (target,), values


def settings(*, ambient_size: tuple[int, int] = (300, 170), with_show: bool = True) -> dict:
    values = dict(SETTINGS)
    if with_show:
        values["u_ambient_px"] = [float(ambient_size[0]), float(ambient_size[1])]
    else:
        values.pop("u_depth_shade")
    return values
