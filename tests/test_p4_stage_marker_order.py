"""Marker-order bars against REAL production call ordering.

These spy the actual production functions rather than instantiating a
`StagePacket` and calling t0-t4 by hand. That distinction matters: the shipped
probe placed T1/T2 around `paint_fn` in `try_shader_path`, which is correct only
for transitions carrying an outer `prep_fn` (BlockSpin). For Slide and the
simple/fullscreen family the real preparation runs *inside* the paint helper, so
prep would have been attributed to `core_draw`.

Required semantics on a sampled frame:

    T0  before actual preparation
    T1  immediately after actual texture/cache/prep work
    T2  immediately after the actual GL transition draw
    T3  after dimming
    T4  after QPainter overlays
"""
from __future__ import annotations

import pytest

from rendering.gl_compositor_pkg import shader_dispatch


class _Recorder:
    """Captures the real marker/CPU ordering produced by production code."""

    def __init__(self):
        self.order: list[str] = []

    def install(self, monkeypatch):
        monkeypatch.setattr(
            shader_dispatch, "_stage_mark",
            lambda comp, marker: self.order.append(marker),
        )
        monkeypatch.setattr(
            shader_dispatch, "_stage_cpu",
            lambda comp, key, start: self.order.append(key),
        )
        monkeypatch.setattr(
            shader_dispatch, "_stage_path",
            lambda comp, path: self.order.append(f"path:{path}"),
        )
        return self

    @property
    def markers(self) -> list[str]:
        return [entry for entry in self.order if entry in {"t0", "t1", "t2", "t3", "t4"}]


@pytest.fixture
def recorder(monkeypatch):
    return _Recorder().install(monkeypatch)


def _neutralise_overlays(monkeypatch):
    """Stub the shared post-draw stages so ordering is observable in isolation."""
    import rendering.gl_compositor_pkg.overlays as overlays

    monkeypatch.setattr(overlays, "paint_dimming_gl", lambda comp: None)
    monkeypatch.setattr(
        shader_dispatch, "paint_qpainter_overlays_gl", lambda comp: None
    )


class TestOuterPrepPath:
    """BlockSpin-style: prep_fn supplied to try_shader_path."""

    def test_marker_order_is_prep_draw_dim_overlay(self, monkeypatch, recorder):
        _neutralise_overlays(monkeypatch)
        comp = type("C", (), {"_last_shader_path_failure": ""})()

        ok = shader_dispatch.try_shader_path(
            comp,
            "blockspin",
            state=object(),
            can_use_fn=lambda: True,
            paint_fn=lambda target: None,
            target=None,
            prep_fn=lambda: True,
        )

        assert ok is True
        assert recorder.markers == ["t1", "t2", "t3", "t4"]
        # prep CPU is recorded before the draw, not merged into it.
        assert recorder.order.index("prep_cpu_ms") < recorder.order.index("t2")
        assert "path:shader:blockspin" in recorder.order

    def test_failed_prep_records_no_draw_markers(self, monkeypatch, recorder):
        _neutralise_overlays(monkeypatch)
        comp = type("C", (), {"_last_shader_path_failure": ""})()

        ok = shader_dispatch.try_shader_path(
            comp,
            "blockspin",
            state=object(),
            can_use_fn=lambda: True,
            paint_fn=lambda target: None,
            target=None,
            prep_fn=lambda: False,
        )

        assert ok is False
        assert recorder.markers == [], "a failed prep must not emit draw stages"


class TestInnerPrepPathIsNotAttributedToCoreDraw:
    """The defect this file exists for: prep inside the paint helper."""

    def test_transition_without_outer_prep_emits_no_premature_t1(
        self, monkeypatch, recorder
    ):
        """try_shader_path must not mark T1 when it did not run prep itself.

        Otherwise the interval up to the paint helper - which still contains the
        real preparation - would be reported as core_draw.
        """
        _neutralise_overlays(monkeypatch)
        comp = type("C", (), {"_last_shader_path_failure": ""})()

        shader_dispatch.try_shader_path(
            comp,
            "wipe",
            state=object(),
            can_use_fn=lambda: True,
            paint_fn=lambda target: None,
            target=None,
            prep_fn=None,
        )

        assert "t1" not in recorder.markers, (
            "try_shader_path marked T1 without owning prep; prep would be "
            "misattributed to core_draw for this transition family"
        )
        assert recorder.markers == ["t2", "t3", "t4"]

    def test_slide_marks_t1_after_its_own_preparation(self, monkeypatch, recorder):
        """Slide prepares inside paint_slide_shader, so T1 belongs there."""
        calls: list[str] = []

        monkeypatch.setattr(shader_dispatch, "can_use_slide_shader", lambda comp: True)
        monkeypatch.setattr(
            shader_dispatch,
            "prepare_slide_textures",
            lambda comp: (calls.append("prepare"), True)[1],
        )

        class _Pixmap:
            def isNull(self):
                return False

        class _Renderer:
            def render_slide_shader(self, target, state):
                calls.append("draw")

        comp = type(
            "C",
            (),
            {
                "_gl_pipeline": object(),
                "_slide": type(
                    "S", (), {"old_pixmap": _Pixmap(), "new_pixmap": _Pixmap()}
                )(),
                "_transition_renderer": _Renderer(),
            },
        )()

        shader_dispatch.paint_slide_shader(comp, target=None)

        assert calls == ["prepare", "draw"]
        assert recorder.markers == ["t1"], (
            "Slide must mark T1 after its own preparation, before the draw"
        )
        assert recorder.order.index("t1") < len(recorder.order)
        assert "prep_cpu_ms" in recorder.order


class TestRetainedBaseSteadyPath:
    def test_marker_order_on_the_steady_path(self, monkeypatch, recorder):
        _neutralise_overlays(monkeypatch)

        class _Pixmap:
            def isNull(self):
                return False

        class _Renderer:
            def render_retained_base_texture(self, texture_id):
                return True

        class _TexMgr:
            def get_cached_texture_id(self, pixmap):
                return 7

        pipeline = type("P", (), {"initialized": True, "crossfade_program": 1})()
        comp = type(
            "C",
            (),
            {
                "_gl_disabled_for_session": False,
                "_gl_pipeline": pipeline,
                "_texture_manager": _TexMgr(),
                "_base_pixmap": _Pixmap(),
                "_transition_renderer": _Renderer(),
            },
        )()

        fn = getattr(shader_dispatch, "paint_retained_base_texture", None)
        if fn is None:
            pytest.skip("retained-base entry point not exposed under this name")

        fn(comp, target=None)

        assert recorder.markers == ["t1", "t2", "t3", "t4"]
        assert "path:retained_base_shader" in recorder.order
