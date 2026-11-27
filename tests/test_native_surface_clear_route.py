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


def scene_clear_is_the_passes(mode_cpp: str, scene_cpp: str) -> bool:
    """Box 3: a scene target's first run begins on its clearing target (made beside its render target on OpenGL only,
    without the preserving flags, for a pass-clearable declaration) unless the control is on, and only then skips the
    clearing draw; a cube, a transparency target, a borrowed attachment and a clear value other than 0 or 1 keep it."""
    passes = _function(mode_cpp, "void ModeContent::recordPasses(", "bool ModeContent::record(")
    if "bool scenePassClearColour(" not in scene_cpp:
        return False
    helper = _function(scene_cpp, "bool scenePassClearColour(", "bool TargetDeclaration::sameLayout(")
    made = scene_cpp[scene_cpp.index("t.renderTarget.reset(rhi->newTextureRenderTarget(description, flags));"):]
    made = made[:made.index("if (t.decl.cube) {")]
    return ("const bool passClears = !cube && !cleared[runTarget] && t.clearingTarget && !sceneClearDraw();" in passes
            and "cb->beginPass(t.clearingTarget.get(), t.clearingColour, { 1.0f, 0 }, pending);" in passes
            and "} else if (!cleared[runTarget]) {" in passes
            and "rhi->backend() == QRhi::OpenGLES2 && scenePassClearColour(t.decl, t.samples, &passColour)" in made
            and "t.clearingTarget.reset(rhi->newTextureRenderTarget(description));" in made
            and "t.clearingTarget && !t.clearingTarget->create()" in made
            and "decl.cube || decl.transparency()" in helper and "if (a.borrowed)" in helper
            and "a.clear[c] != 0.0f && a.clear[c] != 1.0f" in helper
            and "known[c] && value[c] != a.clear[c]" in helper
            and "if (samples > 1 && a.format != TargetFormat::RGBA8)" in helper)


def test_scene_targets_are_cleared_by_their_pass_on_opengl_and_by_the_draw_under_the_control():
    mode_cpp, scene_cpp = _source("mode_content.cpp"), _source("scene_targets.cpp")
    assert scene_clear_is_the_passes(mode_cpp, scene_cpp)
    module = _source("module.cpp")
    assert 'control == "scene_clear_draw"' in module and "setSceneClearDraw(value)" in module
    assert '"mode_scene_pass_clears"' in module and '"mode_scene_draw_clears"' in module
    # The clearing target goes before the objects it names, on a release and on a new layout.
    release = _function(scene_cpp, "void SceneTargets::releaseTarget(", "t.depthNearest.reset();")
    assert release.index("t.clearingTarget.reset();") < release.index("t.renderTarget.reset();")
    # Negative controls: the pre-change record (the draw at every first run), a clearing target that preserved its
    # contents, one made on Vulkan too, and a helper that admitted any clear value, are each caught.
    assert not scene_clear_is_the_passes(mode_cpp.replace(
        "cb->beginPass(t.clearingTarget.get(), t.clearingColour, { 1.0f, 0 }, pending);", ""), scene_cpp)
    assert not scene_clear_is_the_passes(mode_cpp, scene_cpp.replace(
        "t.clearingTarget.reset(rhi->newTextureRenderTarget(description));",
        "t.clearingTarget.reset(rhi->newTextureRenderTarget(description, flags));"))
    assert not scene_clear_is_the_passes(mode_cpp, scene_cpp.replace(
        "rhi->backend() == QRhi::OpenGLES2 && scenePassClearColour", "scenePassClearColour"))
    assert not scene_clear_is_the_passes(mode_cpp, scene_cpp.replace(
        "a.clear[c] != 0.0f && a.clear[c] != 1.0f", "false"))
    # ... and one that pass-cleared a multisampled R16F attachment (measured slower than the draw).
    assert not scene_clear_is_the_passes(mode_cpp, scene_cpp.replace(
        "if (samples > 1 && a.format != TargetFormat::RGBA8)", "if (false)"))


# ------------------------------------------------------------------------------------ the harness's control


class _Stand:
    """A stand-in core, scene and host for ``_clear_control``: counts per route and a frame that is the progress."""

    def __init__(self, *, known=True, by_pass_on_opengl=True, same_pixels=True, share_returns=True, route="surface"):
        import transition_route_check as trc

        self.control = False
        self.known = known
        self.by_pass = by_pass_on_opengl
        self.same = same_pixels
        self.share = share_returns
        self.name, self.prefix = trc.CLEAR_ROUTES[route]
        self.live = {f"{self.prefix}_pass_clears": 0, f"{self.prefix}_draw_clears": 0}
        self.progress = 0.0
        self.module = SimpleNamespace(stage_control=self._stage_control)
        self.layer = SimpleNamespace(tick=self._record)

    def _stage_control(self, name, on):
        if not self.known or name != self.name:
            return False
        self.control = bool(on)
        return True

    def _record(self):
        route = "draw" if self.control or not self.by_pass else "pass"
        self.live[f"{self.prefix}_{route}_clears"] += 1

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
        # The record's time with the draw back (the control on) carries the draw's share when it returns.
        record = 50_000 + (16_000 if self.control and self.share else 0)
        return [SimpleNamespace(kind=2, nanoseconds=record), SimpleNamespace(kind=0, nanoseconds=80_000)]


def _run(stand, api="opengl", route="surface"):
    import transition_route_check as trc

    clock = SimpleNamespace(at=lambda run, progress: setattr(stand, "progress", progress))
    scene = SimpleNamespace(layer=stand.layer, frames=stand.frames, read=stand.read)
    return trc._clear_control(stand, api, scene, stand, clock, object(), route=route)


def test_the_scene_clear_control_judges_the_scene_route_by_its_own_control_and_counts():
    record, checks = _run(_Stand(route="scene"), route="scene")
    assert record["available"] and all(checks.values()), checks
    # The scene route asks for its own control and reads its own counts: a module with only the surface's control
    # judges nothing for scenes, and a scene still cleared by the draw on OpenGL, or a share that did not return, fails.
    assert _run(_Stand(route="surface"), route="scene") == ({"available": False}, {})
    assert not _run(_Stand(route="scene", by_pass_on_opengl=False), route="scene")[1]["clear_route_counted"]
    assert not _run(_Stand(route="scene", share_returns=False), route="scene")[1]["clear_route_share_returns"]


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
    # Both routes are timed in the control's own alternating blocks, and on OpenGL the draw's share must come back
    # with the draw (a control that timed the same route twice, or a share that did not return, fails).
    record, _checks = _run(_Stand())
    assert record["core_record_gpu_clear_draw"]["median_ms"] > record["core_record_gpu_clear_pass"]["median_ms"]
    assert not _run(_Stand(share_returns=False))[1]["clear_route_share_returns"]
    assert _run(_Stand(share_returns=False, by_pass_on_opengl=False), api="vulkan")[1]["clear_route_share_returns"]
