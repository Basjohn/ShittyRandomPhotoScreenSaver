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
HARNESS = ROOT / "native" / "core" / "python"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))


# ------------------------------------------------------------------------------------ the harness's control


class _Stand:
    """A stand-in core, scene and host for ``_clear_control``: counts per route and a frame that is the progress."""

    def __init__(self, *, known=True, by_pass_on_opengl=True, same_pixels=True, share_returns=True, route="surface",
                 stray_draws=0):
        import transition_route_check as trc

        # stray_draws: targets still cleared by the draw on OpenGL's pass route (a negative: none since 121087442).
        self.stray_draws = stray_draws
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
        self.live[f"{self.prefix}_draw_clears"] += self.stray_draws

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


def test_a_scene_target_still_cleared_by_the_draw_on_opengl_fails_the_count():
    # Since 121087442 every scene target the control variants declare clears by its pass on OpenGL (crumble_both_4x:
    # [n, 0] pass and [0, m] draw clears, run 20261128_n52h_pass_clear), so a draw clear beside the pass's on the
    # default route is a regression on either route; Vulkan still draws on both phases.
    assert not _run(_Stand(route="scene", stray_draws=1), route="scene")[1]["clear_route_counted"]
    assert not _run(_Stand(stray_draws=1))[1]["clear_route_counted"]
    record, checks = _run(_Stand(route="scene", stray_draws=1, by_pass_on_opengl=False), api="vulkan", route="scene")
    assert checks["clear_route_counted"], record


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


# ------------------------------------------------------------------------------------ the scene-pass round


class _UnitStand:
    """A stand-in for ``_scene_passes``: a record of three units (two passes, one with its nearest copies) while the
    switch is on, the whole Surface figure while it is off. ``nested``: a module that kept the whole bracket beside the
    units; ``always``: one whose units ignore the switch."""

    def __init__(self, *, known=True, nested=False, always=False, parts_known=False, parts_leak=False,
                 resolve_ns=30_000):
        self.known, self.nested, self.always = known, nested, always
        # N5.2h successor: a module with time_scene_run_parts, whose run (pass 0) is then timed in three parts summing
        # to its unit (``resolve_ns`` other than 30_000: a sum off the unit); ``parts_leak``: parts in the units block.
        self.parts_known, self.parts_leak, self.resolve_ns = parts_known, parts_leak, resolve_ns
        self.units = False
        self.parts = False
        self.edge = 0
        self.pending = []
        self.module = SimpleNamespace(stage_control=self._stage_control)
        self.layer = SimpleNamespace(tick=self._record, state=lambda: {"mode": {"program": {"passes": [
            {"name": "underlay"}, {"name": "chunks"}]}}})

    def _stage_control(self, name, on):
        if self.known and self.parts_known and name == "time_scene_run_parts":
            self.parts = bool(on)
            return True
        if not self.known or name != "time_scene_passes":
            return False
        self.units = bool(on)
        return True

    def _record(self):
        from rendering.native.gpu_timing import GpuSample

        self.edge += 1
        e = self.edge
        if (self.units or self.always) and (self.parts or (self.parts_leak and self.units)):
            self.pending += [GpuSample(5, e, e + 1, 20_000, 0, 5), GpuSample(5, e, e + 1, 50_000, 0, 6),
                             GpuSample(5, e, e + 1, self.resolve_ns, 0, 7), GpuSample(5, e, e + 1, 300_000, 1, 0),
                             GpuSample(5, e, e + 1, 50_000, 1, 1)]
        elif self.units or self.always:
            self.pending += [GpuSample(5, e, e + 1, 100_000, 0, 0), GpuSample(5, e, e + 1, 300_000, 1, 0),
                             GpuSample(5, e, e + 1, 50_000, 1, 1)]
        if not self.units or self.nested:
            self.pending.append(GpuSample(2, e, e + 1, 460_000))
        self.pending.append(GpuSample(0, -1, e + 1, 600_000))

    def frames(self, n=1):
        pass

    def set_gpu_timer(self, on):
        pass

    def gpu_samples(self):
        taken, self.pending = self.pending, []
        return taken


def _units(stand, api="opengl"):
    import transition_route_check as trc

    scene = SimpleNamespace(layer=stand.layer, frames=stand.frames)
    return trc._scene_passes(stand, scene, stand, SimpleNamespace(at=lambda run, progress: None), object(), api)


def test_the_scene_pass_round_names_each_unit_and_fails_on_its_negatives():
    record, checks = _units(_UnitStand())
    assert record["available"] and all(checks.values()), checks
    assert set(record["units"]) == {"0:underlay:unit", "1:chunks:unit", "1:chunks:nearest"}
    assert abs(record["units_sum_per_frame"]["median_ms"] - 0.45) < 1e-9
    assert abs(record["core_record_gpu_units_off"]["median_ms"] - 0.46) < 1e-9
    # Negatives: a module without the switch judges nothing; one that kept the whole bracket beside the units (nested
    # GL_TIME_ELAPSED), and one whose units ignore the switch (the control blocks timed too), each fail.
    assert _units(_UnitStand(known=False)) == ({"available": False}, {})
    assert not _units(_UnitStand(nested=True))[1]["scene_passes_replace_the_record"]
    assert not _units(_UnitStand(always=True))[1]["scene_passes_control_has_none"]


def test_the_run_parts_block_names_each_part_and_fails_on_its_negatives():
    """N5.2h successor: under ``time_scene_run_parts`` (OpenGL) a scene run is timed as its opening, each pass and its
    end-of-pass resolves; the parts sum to the run timed whole, none appears in the units block, none on Vulkan."""
    record, checks = _units(_UnitStand(parts_known=True))
    assert record["available"] and all(checks.values()), checks
    assert {"0:underlay:run_open", "0:underlay:run_draw", "0:underlay:run_resolve"} <= set(record["run_parts"])
    assert abs(record["run_parts_sum_per_frame"]["median_ms"] - 0.45) < 1e-9
    assert record["run_parts_sum_against_units"] == 1.0
    # A module without the control runs the two blocks of before and judges no part.
    assert "run_parts" not in _units(_UnitStand())[0]
    # Negatives: parts in the units block; parts whose sum is not the unit's; parts reported on Vulkan.
    assert not _units(_UnitStand(parts_known=True, parts_leak=True))[1]["run_parts_control_has_none"]
    assert not _units(_UnitStand(parts_known=True, resolve_ns=130_000))[1]["run_parts_sum_is_the_units"]
    assert not _units(_UnitStand(parts_known=True), api="vulkan")[1]["run_parts_on_opengl_only"]
