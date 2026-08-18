"""P2-READY-FADE: renderer readiness, one fade authority, audio start health.

The installed startup sequence was ordered wrongly:

* the staged reveal completed and the visible fade began;
* about a second later the visualizer GL programs registered, the card texture
  was uploaded and the compositor started presenting.

So the first frame the compositor ever drew sampled a fade animation that was
already part-way through - the flash/slam. Two separate defects produced it:

1. a fade-zero publication *cleared* the compositor layer, so nothing was ever
   prepared until the fade had already started;
2. fade progress came from a ``QGraphicsOpacityEffect`` side-channel on a QWidget
   that no longer paints anything, and that side-channel reads 1.0 once the
   effect is torn down.

A third installed defect is covered here too: a just-started audio capture was
classified unhealthy because its first callback had not arrived yet, so the
immediate deferred wake restarted it.

These bars exercise the real owners, not prose about them.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRect

from rendering.gl_compositor_pkg.visualizer_layer import (
    CompositorVisualizerLayer,
    PresentationGeometry,
    VisualizerPresentationReadiness,
    VisualizerRenderState,
)
from utils.audio_capture import (
    CAPTURE_FIRST_CALLBACK_GRACE_S,
    CAPTURE_STALE_AFTER_S,
    CaptureState,
    PyAudioWPatchBackend,
    SounddeviceBackend,
)
from widgets.spotify_visualizer.presentation_fade import (
    BARS_FADE_DELAY,
    VisualizerPresentationFade,
    bars_fade_from_progress,
)


# ---------------------------------------------------------------------------
# Audio capture lifecycle
# ---------------------------------------------------------------------------


@pytest.fixture(params=[PyAudioWPatchBackend, SounddeviceBackend])
def backend(request):
    """Both backends share one health state machine; both must obey it."""
    return request.param()


class TestCaptureStartupHealth:
    def test_fresh_backend_is_stopped(self, backend):
        assert backend.capture_state() is CaptureState.STOPPED
        assert backend.is_healthy() is False
        assert backend.is_capture_stale() is False

    def test_successful_start_is_starting_not_unhealthy(self, backend):
        backend._note_capture_starting()
        assert backend.capture_state() is CaptureState.STARTING
        assert backend.is_capture_starting() is True
        # It is not yet healthy - no callback has arrived - but crucially it is
        # NOT stale, so nothing may restart it.
        assert backend.is_healthy() is False
        assert backend.is_capture_stale() is False

    def test_first_callback_promotes_to_healthy(self, backend):
        backend._note_capture_starting()
        backend._note_capture_callback()
        assert backend.capture_state() is CaptureState.HEALTHY
        assert backend.is_healthy() is True
        assert backend.is_capture_stale() is False

    def test_starting_beyond_the_first_callback_grace_becomes_stale(self, backend, monkeypatch):
        backend._note_capture_starting()
        started = backend._capture_started_ts
        monkeypatch.setattr(
            "utils.audio_capture.time.monotonic",
            lambda: started + CAPTURE_FIRST_CALLBACK_GRACE_S + 0.01,
        )
        assert backend.capture_state() is CaptureState.STALE
        assert backend.is_capture_stale() is True

    def test_late_first_callback_still_promotes_to_healthy(self, backend):
        """State derivation must be pure so a slow first callback still counts."""
        backend._note_capture_starting()
        backend._capture_started_ts -= CAPTURE_FIRST_CALLBACK_GRACE_S * 2
        assert backend.capture_state() is CaptureState.STALE
        backend._note_capture_callback()
        assert backend.capture_state() is CaptureState.HEALTHY

    def test_healthy_then_silent_capture_is_stale(self, backend, monkeypatch):
        backend._note_capture_starting()
        backend._note_capture_callback()
        last = backend._last_callback_ts
        monkeypatch.setattr(
            "utils.audio_capture.time.monotonic",
            lambda: last + CAPTURE_STALE_AFTER_S + 0.01,
        )
        assert backend.capture_state() is CaptureState.STALE
        assert backend.is_healthy() is False
        assert backend.is_capture_stale() is True

    def test_failed_start_stays_a_failure(self, backend):
        backend._note_capture_failed()
        assert backend.capture_state() is CaptureState.FAILED
        assert backend.is_healthy() is False
        # A capture that never started is not a restart candidate for wake();
        # the ordinary start path owns that.
        assert backend.is_capture_stale() is False

    def test_stop_returns_to_stopped(self, backend):
        backend._note_capture_starting()
        backend._note_capture_callback()
        backend.stop()
        assert backend.capture_state() is CaptureState.STOPPED
        assert backend.is_healthy() is False

    def test_start_marks_failure_when_the_stream_cannot_open(self, backend, monkeypatch):
        """Every failure path must land on FAILED, not a half-started state."""
        monkeypatch.setattr(backend, "_start_stream", lambda callback: False)
        assert backend.start(lambda samples: None) is False
        assert backend.capture_state() is CaptureState.FAILED


class _FakeWorker:
    """Audio worker stand-in with the real health delegation shape."""

    def __init__(self, backend):
        self._backend = backend
        self.restarts = 0

    def is_capture_healthy(self):
        return self._backend.is_healthy()

    def is_capture_starting(self):
        return self._backend.is_capture_starting()

    def is_capture_stale(self):
        return self._backend.is_capture_stale()

    def restart_capture(self):
        self.restarts += 1
        return True


def _engine_with(worker):
    """A beat engine wired only far enough to exercise wake()."""
    from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine

    engine = _SpotifyBeatEngine.__new__(_SpotifyBeatEngine)
    engine._audio_worker = worker
    engine._last_smooth_ts = 0.0
    engine.ensure_started = lambda: None
    return engine


class TestWakeDoesNotBounceAJustStartedCapture:
    def test_immediate_wake_after_start_does_not_restart(self):
        backend = PyAudioWPatchBackend()
        backend._note_capture_starting()
        worker = _FakeWorker(backend)
        _engine_with(worker).wake()
        assert worker.restarts == 0, (
            "a capture whose first callback has not arrived was restarted"
        )

    def test_warm_healthy_wake_does_not_restart(self):
        backend = PyAudioWPatchBackend()
        backend._note_capture_starting()
        backend._note_capture_callback()
        worker = _FakeWorker(backend)
        _engine_with(worker).wake()
        assert worker.restarts == 0

    def test_stale_capture_restarts_exactly_once(self, monkeypatch):
        backend = PyAudioWPatchBackend()
        backend._note_capture_starting()
        backend._note_capture_callback()
        last = backend._last_callback_ts
        monkeypatch.setattr(
            "utils.audio_capture.time.monotonic",
            lambda: last + CAPTURE_STALE_AFTER_S + 1.0,
        )
        worker = _FakeWorker(backend)
        _engine_with(worker).wake()
        assert worker.restarts == 1


# ---------------------------------------------------------------------------
# One fade authority
# ---------------------------------------------------------------------------


class TestAuthoredBarsStagger:
    def test_bars_wait_for_the_card(self):
        assert bars_fade_from_progress(0.0) == 0.0
        assert bars_fade_from_progress(BARS_FADE_DELAY) == 0.0
        assert bars_fade_from_progress(1.0) == 1.0

    def test_bars_fade_is_monotonic_in_progress(self):
        previous = -1.0
        for i in range(101):
            value = bars_fade_from_progress(i / 100.0)
            assert value >= previous
            previous = value

    def test_bars_fade_is_a_pure_function_of_the_same_progress(self):
        """Two consumers, one scalar - not two curves that can disagree."""
        for p in (0.0, 0.3, 0.7, 0.9, 1.0):
            assert bars_fade_from_progress(p) == bars_fade_from_progress(p)


@pytest.mark.qt
class TestFadeAuthority:
    def test_fade_starts_below_full_opacity(self, qt_app):
        fade = VisualizerPresentationFade()
        fade.begin_fade_in(duration_ms=1800)
        assert fade.is_running()
        assert 0.0 <= fade.progress < 1.0, "a reveal must not begin at full opacity"
        assert fade.is_complete() is False

    def test_zero_duration_jumps_exactly_once(self, qt_app):
        fade = VisualizerPresentationFade()
        fade.jump_to(1.0)
        assert fade.progress == 1.0
        assert fade.is_running() is False
        assert fade.is_complete() is True

    def test_reset_returns_to_invisible_and_cancels(self, qt_app):
        fade = VisualizerPresentationFade()
        fade.begin_fade_in(duration_ms=1800)
        fade.reset()
        assert fade.progress == 0.0
        assert fade.is_running() is False
        assert fade.has_started() is False

    def test_a_superseded_fade_cannot_finish_the_new_one(self, qt_app):
        """An interrupted fade's callbacks must not write the current progress."""
        fade = VisualizerPresentationFade()
        fade.begin_fade_in(duration_ms=1800)
        stale = fade._anim
        fade.reset()
        # Emitting the superseded animation's completion must change nothing.
        stale.finished.emit()
        stale.valueChanged.emit(1.0)
        assert fade.progress == 0.0

    def test_card_and_bars_read_the_same_progress(self, qt_app):
        fade = VisualizerPresentationFade()
        fade.jump_to(0.8)
        assert fade.card_fade() == 0.8
        assert fade.bars_fade() == bars_fade_from_progress(0.8)


@pytest.mark.qt
class TestFadeOwnershipIsNotTheQWidgetEffect:
    def _widget(self):
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

        widget = SpotifyVisualizerWidget(parent=None, bar_count=8)
        widget._shadow_config = {"enabled": False}
        widget._show_background = True
        return widget

    def test_progress_does_not_jump_when_a_widget_effect_disappears(self, qt_app):
        """The old side-channel reported 1.0 once the effect was torn down."""
        from widgets.spotify_visualizer import mode_transition

        widget = self._widget()
        try:
            widget.presentation_fade().jump_to(0.25)
            # Simulate the retired QWidget fade machinery finishing/vanishing.
            widget._shadowfade_progress = 1.0
            widget._shadowfade_completed = True
            widget._shadowfade_anim = None
            widget._shadowfade_effect = None
            widget.show()

            assert mode_transition.get_scene_fade_factor(widget, 0.0) == 0.25
            assert mode_transition.get_gpu_fade_factor(widget, 0.0) == pytest.approx(
                bars_fade_from_progress(0.25)
            )
        finally:
            widget.deleteLater()

    def test_fade_in_does_not_install_a_competing_opacity_owner(self, qt_app):
        from widgets.spotify_visualizer import mode_transition

        widget = self._widget()
        try:
            mode_transition.start_widget_fade_in(widget, duration_ms=1800)
            assert getattr(widget, "_shadowfade_anim", None) is None
            assert getattr(widget, "_shadowfade_effect", None) is None
            assert widget.presentation_fade().is_running()
        finally:
            widget.deleteLater()

    def test_hiding_the_scene_does_not_destroy_gl_resources(self, qt_app):
        """Ordinary hide/pause must not tear down the compositor generation."""
        import inspect

        from widgets.spotify_visualizer import mode_transition

        source = inspect.getsource(mode_transition.start_widget_fade_out)
        for forbidden in ("cleanup_gl", "_destroy_parent_overlay", "_clear_gl_overlay"):
            assert forbidden not in source, (
                "fading out must not free visualizer GL resources"
            )


# ---------------------------------------------------------------------------
# Renderer readiness
# ---------------------------------------------------------------------------


class _CardStub:
    def __init__(self):
        self._show_background = True
        self._painted_frame_shadow_enabled = True
        self.owned = False

    def uses_painted_frame_shadow(self):
        return bool(self._painted_frame_shadow_enabled and self._show_background)

    def set_compositor_owns_card_visual(self, owned):
        self.owned = bool(owned)

    @property
    def _compositor_owns_card_visual(self):
        return self.owned


class TestReadinessSnapshot:
    def _ready_kwargs(self, **overrides):
        base = dict(
            gl_generation=1,
            gl_resources_ready=True,
            gl_failed=False,
            geometry_committed=True,
            card_visual_owned=True,
            card_texture_ready=True,
        )
        base.update(overrides)
        return base

    def test_all_requirements_met_is_ready(self):
        assert VisualizerPresentationReadiness(**self._ready_kwargs()).is_ready

    @pytest.mark.parametrize(
        "override,missing",
        [
            ({"gl_generation": 0}, "gl_generation"),
            ({"gl_resources_ready": False}, "gl_resources"),
            ({"gl_failed": True}, "gl_failed"),
            ({"geometry_committed": False}, "geometry"),
            ({"card_visual_owned": False}, "card_visual"),
            ({"card_texture_ready": False}, "card_texture"),
        ],
    )
    def test_each_requirement_blocks_readiness(self, override, missing):
        readiness = VisualizerPresentationReadiness(**self._ready_kwargs(**override))
        assert readiness.is_ready is False
        assert missing in readiness.missing()


class TestLayerReadiness:
    def _layer(self, *, generation=1, gl_ready=True, gl_failed=False):
        card = _CardStub()
        owner = SimpleNamespace(
            _enabled=True,
            _fade=0.0,
            _bars_fade=0.0,
            _compositor_mask_origin_px=None,
            _presentation_geometry=None,
            initialize_layer_gl=lambda ctx: True,
            layer_gl_resources_ready=lambda: gl_ready,
            layer_gl_failed=lambda: gl_failed,
            paint_layer=lambda rect, fade: None,
        )
        owner.parentWidget = lambda: SimpleNamespace(spotify_visualizer_widget=card)
        comp = SimpleNamespace(
            _rhi_gl=SimpleNamespace(context=object(), generation=generation)
        )
        layer = CompositorVisualizerLayer(comp)
        layer.publish(VisualizerRenderState(owner, QRect(10, 20, 400, 200)))
        return layer, card, comp

    def test_layer_is_not_ready_before_preparation(self):
        layer, _card, _comp = self._layer()
        readiness = layer.readiness()
        assert readiness.is_ready is False
        assert "geometry" in readiness.missing()

    def test_render_at_fade_zero_prepares_instead_of_clearing(self, monkeypatch):
        """The fade-zero window is exactly when preparation must happen."""
        layer, _card, _comp = self._layer()
        prepared = []
        monkeypatch.setattr(
            CompositorVisualizerLayer,
            "prepare",
            lambda self, h, dpr: prepared.append((h, dpr)) or False,
        )
        assert layer.render(600, 1.0) is False
        assert prepared == [(600, 1.0)], "fade zero must run the preparation pass"
        assert layer.state is not None, "preparation still needs published state"

    def test_preparation_claims_card_ownership_and_commits_geometry(self, monkeypatch):
        layer, card, _comp = self._layer()
        # The texture upload needs a real pixmap/GL; the card-visual claim and
        # geometry commit are what this bar owns.
        monkeypatch.setattr(
            CompositorVisualizerLayer, "_card_texture_required", staticmethod(lambda c: False)
        )
        assert layer.prepare(600, 1.0) is True
        assert card.owned is True, (
            "card ownership must be claimed before the fade leaves zero"
        )
        assert isinstance(layer._committed_geometry, PresentationGeometry)
        assert layer._committed_generation == 1
        assert layer.is_presentation_ready() is True

    def test_readiness_does_not_survive_a_generation_change(self, monkeypatch):
        layer, _card, comp = self._layer()
        monkeypatch.setattr(
            CompositorVisualizerLayer, "_card_texture_required", staticmethod(lambda c: False)
        )
        assert layer.prepare(600, 1.0) is True
        comp._rhi_gl.generation = 2
        readiness = layer.readiness()
        assert readiness.is_ready is False
        assert "geometry" in readiness.missing()

    def test_failed_gl_initialization_is_never_ready(self, monkeypatch):
        layer, _card, _comp = self._layer(gl_ready=False, gl_failed=True)
        monkeypatch.setattr(
            CompositorVisualizerLayer, "_card_texture_required", staticmethod(lambda c: False)
        )
        layer.prepare(600, 1.0)
        readiness = layer.readiness()
        assert readiness.is_ready is False
        assert "gl_failed" in readiness.missing()

    def test_clearing_the_layer_drops_readiness(self, monkeypatch):
        layer, _card, _comp = self._layer()
        monkeypatch.setattr(
            CompositorVisualizerLayer, "_card_texture_required", staticmethod(lambda c: False)
        )
        layer.prepare(600, 1.0)
        layer.clear()
        assert layer.is_presentation_ready() is False

    def test_readiness_notification_fires_once_per_preparation(self, monkeypatch):
        layer, _card, _comp = self._layer()
        monkeypatch.setattr(
            CompositorVisualizerLayer, "_card_texture_required", staticmethod(lambda c: False)
        )
        notified = []
        monkeypatch.setattr(
            CompositorVisualizerLayer,
            "_notify_prepared",
            lambda self, owner: notified.append(owner),
        )
        layer.prepare(600, 1.0)
        layer.prepare(600, 1.0)
        layer.prepare(600, 1.0)
        assert len(notified) == 1


# ---------------------------------------------------------------------------
# Reveal ordering
# ---------------------------------------------------------------------------


class _RevealWidget:
    """The reveal-gate surface of SpotifyVisualizerWidget, nothing more."""

    def __init__(self, *, ready):
        self._enabled = True
        self._startup_reveal_pending = True
        self._startup_reveal_token = 0
        self._startup_reveal_ready_token = -1
        self._anchor_media = None
        self._startup_require_playing_before_reveal = False
        self._spotify_playing = True
        self._startup_idle_reveal_requires_authoritative_media = False
        self._startup_has_authoritative_media_update = True
        self._waiting_for_fresh_frame = False
        self._startup_reveal_not_before_ts = 0.0
        self._visible = False
        self.fades = 0
        self._compositor = SimpleNamespace(
            is_visualizer_presentation_ready=lambda: self._ready,
            visualizer_presentation_readiness=lambda: VisualizerPresentationReadiness(
                gl_generation=1
            ),
        )
        self._ready = ready

    def parent(self):
        return SimpleNamespace(_gl_compositor=self._compositor)

    def isVisible(self):
        return self._visible

    def _start_widget_fade_in(self):
        self.fades += 1
        self._visible = True


class TestRevealWaitsForRenderer:
    def test_reveal_is_refused_while_the_renderer_is_not_ready(self):
        from widgets.spotify_visualizer import startup_staging

        widget = _RevealWidget(ready=False)
        startup_staging.finish_staged_startup_reveal(widget, reason="test")
        assert widget.fades == 0, (
            "the visible fade began before the compositor could draw the visualizer"
        )
        assert widget._startup_reveal_pending is True

    def test_reveal_proceeds_once_the_renderer_is_ready(self):
        from widgets.spotify_visualizer import startup_staging

        widget = _RevealWidget(ready=False)
        startup_staging.finish_staged_startup_reveal(widget, reason="test")
        widget._ready = True
        startup_staging.finish_staged_startup_reveal(widget, reason="renderer_ready")
        assert widget.fades == 1
        assert widget._startup_reveal_pending is False

    def test_a_compositor_without_the_seam_cannot_deadlock_reveal(self):
        from widgets.spotify_visualizer import startup_staging

        widget = _RevealWidget(ready=False)
        widget._compositor = SimpleNamespace()
        startup_staging.finish_staged_startup_reveal(widget, reason="test")
        assert widget.fades == 1


@pytest.mark.qt
class TestStartupArmingResetsTheFade:
    def test_arming_returns_the_scene_fade_to_zero(self, qt_app):
        from widgets.spotify_visualizer import startup_staging
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

        widget = SpotifyVisualizerWidget(parent=None, bar_count=8)
        try:
            widget.presentation_fade().jump_to(1.0)
            widget._seed_playback_state_from_anchor = lambda **kwargs: None
            startup_staging.arm_staged_startup(widget, reason="test")
            assert widget.presentation_fade().progress == 0.0, (
                "a re-arm must not inherit a completed fade and reveal mid-curve"
            )
        finally:
            widget.deleteLater()


# ---------------------------------------------------------------------------
# Cold reactivity warmup happens behind readiness
# ---------------------------------------------------------------------------


class TestColdRampAdvancesWhileHidden:
    def test_ramp_starts_at_play_detection_not_at_reveal(self):
        """The AGC warmup is wall-clock from play detection.

        Because readiness now holds the reveal back until the renderer, card
        texture and first fresh frame exist, that warmup elapses while the
        visualizer is still invisible instead of being spent on screen.
        """
        import inspect

        from widgets.spotify_visualizer import mode_transition, startup_staging

        for module in (mode_transition, startup_staging):
            source = inspect.getsource(module)
            assert "_play_ramp_start_ts" not in source, (
                "the reveal path must never re-arm the cold reactivity ramp"
            )

    def test_warm_resume_keeps_its_fast_path(self):
        import inspect

        from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine

        source = inspect.getsource(_SpotifyBeatEngine.set_playback_state)
        assert "warm_resume" in source
        assert "self._play_ramp_start_ts = 0.0" in source, (
            "a warm capture resume must not re-enter the cold ramp"
        )


# ---------------------------------------------------------------------------
# Installed regressions from the first closure attempt
# ---------------------------------------------------------------------------


class TestNoFlashBeforeTheFade:
    """"Visualizer flashes once before the fade starts."

    The compositor layer releases the card visual whenever its published state is
    cleared. Removing the QGraphicsOpacityEffect left nothing holding the card
    QWidget at zero opacity in that window, so it self-painted one opaque frame.
    """

    def test_card_paint_is_gated_on_the_compositor_layer_existing(self, qt_app):
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

        probe = SpotifyVisualizerWidget.__new__(SpotifyVisualizerWidget)
        probe._compositor_owns_card_visual = False
        probe.parentWidget = lambda: SimpleNamespace(
            _gl_compositor=SimpleNamespace(_visualizer_layer=object())
        )
        assert probe._compositor_owns_visualizer_pixels() is True

    def test_a_released_card_visual_still_does_not_self_paint(self, qt_app):
        from rendering.gl_compositor_pkg.visualizer_layer import CompositorVisualizerLayer
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

        card = SpotifyVisualizerWidget.__new__(SpotifyVisualizerWidget)
        card._compositor_owns_card_visual = True
        compositor = SimpleNamespace(_visualizer_layer=None)
        card.parentWidget = lambda: SimpleNamespace(_gl_compositor=compositor)

        layer = CompositorVisualizerLayer(compositor)
        compositor._visualizer_layer = layer
        owner = SimpleNamespace()
        owner.parentWidget = lambda: SimpleNamespace(spotify_visualizer_widget=card)
        layer.publish(VisualizerRenderState(owner, QRect(0, 0, 400, 200)))

        layer.clear()  # mode reset / anchor hide / teardown

        assert card._compositor_owns_card_visual is False
        assert card._compositor_owns_visualizer_pixels() is True, (
            "the card must not start painting itself just because the layer cleared"
        )


class TestModeCrossfadeDoesNotStackOnTheCard:
    """"Trying to change modes leaves a dead visualizer."

    The card used to fade only on its own reveal curve while the mode crossfade
    multiplied the shader. Multiplying both stacked two 0 -> 1 ramps on the card.
    """

    def test_the_crossfade_multiplies_only_the_shader(self):
        import inspect

        from widgets.spotify_visualizer import tick_pipeline

        source = inspect.getsource(tick_pipeline.push_gpu_frame)
        assert "bars_fade *= transition_fade" in source
        assert "scene_fade *= transition_fade" not in source, (
            "the authored card fade must not be multiplied by the mode crossfade"
        )


@pytest.mark.qt
class TestRevealFollowsSceneStateNotWidgetVisibility:
    """"Final visualizer does not ever go live when music starts playing."

    ``start_widget_fade_out`` no longer hides the logical widget - the compositor
    owns the pixels - so a reveal gated on ``isVisible()`` alone did nothing
    after any fade-out and the scene stayed at zero forever.
    """

    def test_a_faded_out_but_visible_scene_still_needs_a_reveal(self, qt_app):
        fade = VisualizerPresentationFade()
        fade.jump_to(1.0)
        assert fade.needs_reveal() is False
        fade.jump_to(0.0)
        assert fade.needs_reveal() is True

    def test_an_in_flight_animation_is_never_interrupted(self, qt_app):
        fade = VisualizerPresentationFade()
        fade.jump_to(1.0)
        fade.begin_fade_out(duration_ms=1200)
        assert fade.needs_reveal() is False, "a running hide must be allowed to finish"

        fade.reset()
        fade.begin_fade_in(duration_ms=1800)
        assert fade.needs_reveal() is False, "a running reveal must not be restarted"

    def test_the_staged_reveal_consults_scene_state(self):
        import inspect

        from widgets.spotify_visualizer import startup_staging

        source = inspect.getsource(startup_staging.finish_staged_startup_reveal)
        assert "scene_needs_reveal(widget)" in source

    def test_the_anchor_sync_consults_scene_state(self):
        import inspect

        from widgets.spotify_visualizer import media_bridge

        source = inspect.getsource(media_bridge.sync_visibility_with_anchor)
        assert "_scene_needs_reveal(widget)" in source

    def test_an_anchor_sync_does_not_interrupt_a_mode_transition(self):
        from widgets.spotify_visualizer import media_bridge

        widget = SimpleNamespace(_mode_transition_phase=2, _mode_teardown_state="fading_out")
        assert media_bridge._scene_needs_reveal(widget) is False


class TestReadinessCanDelayButNeverDeadlock:
    def test_a_failed_gl_generation_still_permits_reveal(self):
        layer = CompositorVisualizerLayer(
            SimpleNamespace(_rhi_gl=SimpleNamespace(context=object(), generation=1))
        )
        card = _CardStub()
        owner = SimpleNamespace(
            _enabled=True,
            _fade=0.0,
            layer_gl_resources_ready=lambda: False,
            layer_gl_failed=lambda: True,
        )
        owner.parentWidget = lambda: SimpleNamespace(spotify_visualizer_widget=card)
        layer.publish(VisualizerRenderState(owner, QRect(0, 0, 400, 200)))

        assert layer.is_presentation_ready() is False
        assert layer.can_reveal() is True, (
            "a permanently invisible visualizer is worse than an imperfect one"
        )

    def test_an_unprepared_layer_still_waits(self):
        layer = CompositorVisualizerLayer(
            SimpleNamespace(_rhi_gl=SimpleNamespace(context=object(), generation=1))
        )
        card = _CardStub()
        owner = SimpleNamespace(
            _enabled=True,
            _fade=0.0,
            layer_gl_resources_ready=lambda: False,
            layer_gl_failed=lambda: False,
        )
        owner.parentWidget = lambda: SimpleNamespace(spotify_visualizer_widget=card)
        layer.publish(VisualizerRenderState(owner, QRect(0, 0, 400, 200)))

        assert layer.can_reveal() is False

    def test_an_unusable_card_image_does_not_hide_the_visualizer_forever(self, monkeypatch):
        layer = CompositorVisualizerLayer(
            SimpleNamespace(_rhi_gl=SimpleNamespace(context=object(), generation=1))
        )
        card = _CardStub()
        owner = SimpleNamespace(
            _enabled=True,
            _fade=0.0,
            initialize_layer_gl=lambda ctx: True,
            layer_gl_resources_ready=lambda: True,
            layer_gl_failed=lambda: False,
        )
        owner.parentWidget = lambda: SimpleNamespace(spotify_visualizer_widget=card)
        layer.publish(VisualizerRenderState(owner, QRect(0, 0, 400, 200)))

        monkeypatch.setattr(
            "widgets.spotify_visualizer.card_paint.ensure_painted_frame_shadow_pixmap",
            lambda *a, **k: None,
        )
        layer.prepare(600, 1.0)

        assert layer.is_presentation_ready() is False
        assert layer._card_preparation_failed is True
        assert layer.can_reveal() is True

    def test_preparation_that_never_completes_still_reveals(self):
        """No unforeseen readiness condition may hide the visualizer forever."""
        layer = CompositorVisualizerLayer(
            SimpleNamespace(_rhi_gl=SimpleNamespace(context=object(), generation=1))
        )
        card = _CardStub()
        owner = SimpleNamespace(
            _enabled=True,
            _fade=0.0,
            # Initialization keeps failing, so geometry is never committed.
            initialize_layer_gl=lambda ctx: False,
            layer_gl_resources_ready=lambda: False,
            layer_gl_failed=lambda: False,
        )
        owner.parentWidget = lambda: SimpleNamespace(spotify_visualizer_widget=card)
        layer.publish(VisualizerRenderState(owner, QRect(0, 0, 400, 200)))

        for _ in range(layer._PREPARE_ATTEMPT_BUDGET - 1):
            layer.prepare(600, 1.0)
        assert layer.can_reveal() is False, "the gate must still be delaying"

        layer.prepare(600, 1.0)
        assert layer.can_reveal() is True
        assert layer.is_presentation_ready() is False, "readiness stays truthful"

    def test_the_attempt_budget_resets_with_the_preparation_state(self):
        layer = CompositorVisualizerLayer(
            SimpleNamespace(_rhi_gl=SimpleNamespace(context=object(), generation=1))
        )
        owner = SimpleNamespace(
            _enabled=True,
            _fade=0.0,
            initialize_layer_gl=lambda ctx: False,
            layer_gl_resources_ready=lambda: False,
            layer_gl_failed=lambda: False,
        )
        owner.parentWidget = lambda: None
        layer.publish(VisualizerRenderState(owner, QRect(0, 0, 400, 200)))
        for _ in range(10):
            layer.prepare(600, 1.0)
        assert layer._prepare_attempts == 10
        layer.clear()
        assert layer._prepare_attempts == 0
