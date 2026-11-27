"""N5.2h, the native route's cost at its owner (Current_Plan.md N5.2h), GPU-free.

- The mode surface's first run on OpenGL is cleared by its render pass's own clear (``targets.h``
  ``clearingRenderTarget``: the same texture's render target without PreserveColorContents) instead of the
  full-triangle clearing draw, the draw's share of every record (about 0.02 ms per frame at 4K). Vulkan keeps the draw
  (rule B: a non-preserving pass there loads UNDEFINED with no external dependency), and so does ``stage_control``'s
  ``surface_clear_draw`` (the negative control); the clears are counted by route in ``composite_live``.
- ``transition_route_check.py --cost`` times the Python presenter on the product route on the same frames as the native
  layer (``python_product_frame_gpu``), and Crossfade's clear-route control judges pixels and counts.

Each negative control is the pre-change form, seen failing. The drawn proof is the cost round on the built module.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "native" / "core" / "src"
HARNESS = ROOT / "native" / "core" / "python"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))


def _source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def _function(text: str, start: str, end: str) -> str:
    return text[text.index(start):text.index(end, text.index(start))]


def surface_clear_is_the_passes(mode_cpp: str, targets_cpp: str) -> bool:
    """The record asks for the clearing target unless the control is on; the surface's first run and the lone clear
    begin on it when there is one, and only then skip the clearing draw; the target is OpenGL's only and made without
    PreserveColorContents, again for every generation."""
    passes = _function(mode_cpp, "void ModeContent::recordPasses(", "bool ModeContent::record(")
    if "clearingRenderTarget(" not in targets_cpp:
        return False
    helper = _function(targets_cpp, "QRhiTextureRenderTarget *clearingRenderTarget(", "QString primeForLoad(")
    return ("surfaceClearDraw() ? nullptr : clearingRenderTarget(rhi, &target, &clearingError)" in passes
            and "cb->beginPass(passClears ? clearingTarget : target.renderTarget.get()" in passes
            and "const bool passClears = !surfaceOpened && clearingTarget;" in passes
            and "} else if (!surfaceOpened) {" in passes
            and "cb->beginPass(clearingTarget ? clearingTarget : target.renderTarget.get()" in passes
            and "rhi->backend() != QRhi::OpenGLES2" in helper
            and "rhi->newTextureRenderTarget(description))" in helper
            and "PreserveColorContents" not in helper
            and "target->clearingGeneration == target->generation" in helper)


def test_the_surface_is_cleared_by_its_pass_on_opengl_and_by_the_draw_under_the_control():
    mode_cpp, targets_cpp = _source("mode_content.cpp"), _source("targets.cpp")
    assert surface_clear_is_the_passes(mode_cpp, targets_cpp)
    # The control is the module's own (stage_control), read per record, and the clears are counted by route.
    module = _source("module.cpp")
    assert 'control == "surface_clear_draw"' in module and "setSurfaceClearDraw(value)" in module
    assert '"mode_surface_pass_clears"' in module and '"mode_surface_draw_clears"' in module
    assert "g_surfaceDrawClears.fetchAndAddRelaxed(1);" in mode_cpp
    # A reset target drops its clearing target first (it names the texture).
    reset = _function(targets_cpp, "void ColorTarget::reset()", "bool createColorTarget(")
    assert reset.index("clearingRenderTargetObject.reset();") < reset.index("texture.reset();")
    # Negative controls: the pre-N5.2h record (every first run begun on the preserving target and cleared by the
    # draw), a clearing target that preserved its contents, and one made for Vulkan too, are each caught.
    old = mode_cpp.replace("cb->beginPass(passClears ? clearingTarget : target.renderTarget.get()",
                           "cb->beginPass(target.renderTarget.get()")
    assert not surface_clear_is_the_passes(old, targets_cpp)
    assert not surface_clear_is_the_passes(mode_cpp, targets_cpp.replace(
        "rhi->newTextureRenderTarget(description))",
        "rhi->newTextureRenderTarget(description, QRhiTextureRenderTarget::PreserveColorContents))"))
    assert not surface_clear_is_the_passes(mode_cpp, targets_cpp.replace(
        "rhi->backend() != QRhi::OpenGLES2", "rhi->backend() == QRhi::Null"))


# ------------------------------------------------------------------------------------ the harness's control


class _Stand:
    """A stand-in core, scene and host for ``_clear_control``: counts per route and a frame that is the progress."""

    def __init__(self, *, known=True, by_pass_on_opengl=True, same_pixels=True):
        self.control = False
        self.known = known
        self.by_pass = by_pass_on_opengl
        self.same = same_pixels
        self.live = {"mode_surface_pass_clears": 0, "mode_surface_draw_clears": 0}
        self.progress = 0.0
        self.module = SimpleNamespace(stage_control=self._stage_control)
        self.layer = SimpleNamespace(tick=self._record)

    def _stage_control(self, name, on):
        if not self.known or name != "surface_clear_draw":
            return False
        self.control = bool(on)
        return True

    def _record(self):
        key = "mode_surface_draw_clears" if self.control or not self.by_pass else "mode_surface_pass_clears"
        self.live[key] += 1

    def composite_live(self):
        return dict(self.live)

    def frames(self, n=1):
        pass

    def read(self):
        level = int(self.progress * 200) + (0 if self.same or not self.control else 1)
        return np.full((4, 4, 4), level, dtype=np.uint8)

    def set_gpu_timer(self, on):
        pass

    def gpu_samples(self):
        return [SimpleNamespace(kind=2, nanoseconds=50_000), SimpleNamespace(kind=0, nanoseconds=80_000)]


def _run(stand, api="opengl"):
    import transition_route_check as trc

    clock = SimpleNamespace(at=lambda run, progress: setattr(stand, "progress", progress))
    scene = SimpleNamespace(layer=stand.layer, frames=stand.frames, read=stand.read)
    return trc._clear_control(stand, api, scene, stand, clock, object())


def test_the_clear_control_passes_on_the_pass_route_and_fails_on_its_negatives():
    record, checks = _run(_Stand())
    assert record["available"] and all(checks.values()), checks
    assert record["pass_clears"][1] == 0 and record["draw_clears"][0] == 0
    # Vulkan: the draw in both phases is the expected route there.
    record, checks = _run(_Stand(by_pass_on_opengl=False), api="vulkan")
    assert all(checks.values()), checks
    # Negative controls: the pre-change module (no control: nothing judged), a module still clearing by the draw on
    # OpenGL, and a pass clear that changed the pixels.
    assert _run(_Stand(known=False)) == ({"available": False}, {})
    assert not _run(_Stand(by_pass_on_opengl=False))[1]["clear_route_counted"]
    assert not _run(_Stand(same_pixels=False))[1]["clear_route_pixels_equal"]
