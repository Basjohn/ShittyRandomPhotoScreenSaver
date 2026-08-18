"""P2-ACTIVATION-FINAL: one activation, one final engine generation.

The installed BUBBLE -> DEVCURVE switch advanced the engine three times:

    starting                       generation=1 activation=1
    bar-count reconfigure 48 -> 35 generation=2 activation=2
    smoothing reset                generation=3 activation=3

and then replayed an identical technical configuration under
``settings_refresh:activation_payload`` immediately after the fresh frame.

The prior transaction-stamp work did not catch this because its test double's
``reset_smoothing_state`` did not increment anything, so the fake could not
reproduce the production boundary. These bars use the REAL engine.
"""

from __future__ import annotations

import pytest

from widgets.spotify_visualizer.activation_runtime import (
    activation_payload_identity,
    engine_activation_transaction,
)


@pytest.fixture
def engine(qt_app):
    from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine

    instance = _SpotifyBeatEngine(48)
    yield instance
    instance.deleteLater()


def _stamp(engine) -> tuple[int, int]:
    return (engine.get_generation_id(), engine.get_activation_id())


# ---------------------------------------------------------------------------
# Real engine generation semantics
# ---------------------------------------------------------------------------


class TestPublicEngineSemanticsAreUnchanged:
    def test_bar_count_reconfigure_still_advances_once_on_its_own(self, engine):
        before = _stamp(engine)
        engine.reconfigure_bar_count(35)
        after = _stamp(engine)
        assert after == (before[0] + 1, before[1] + 1)

    def test_smoothing_reset_still_advances_once_on_its_own(self, engine):
        before = _stamp(engine)
        engine.reset_smoothing_state()
        after = _stamp(engine)
        assert after == (before[0] + 1, before[1] + 1)

    def test_a_no_op_bar_count_still_advances_nothing(self, engine):
        before = _stamp(engine)
        engine.reconfigure_bar_count(engine._bar_count)
        assert _stamp(engine) == before


class TestOneActivationOneGeneration:
    def test_cross_mode_bar_count_switch_advances_exactly_once(self, engine):
        """BUBBLE 48 -> DEVCURVE 35: resize AND reset, one final generation."""
        before = _stamp(engine)
        engine.begin_activation_transaction()
        engine.reconfigure_bar_count(35)
        engine.reset_smoothing_state()
        engine.reset_floor_state()
        assert _stamp(engine) == before, (
            "an intermediate target generation became observable mid-transaction"
        )
        engine.end_activation_transaction(reason="mode_switch")
        after = _stamp(engine)
        assert after == (before[0] + 1, before[1] + 1)
        assert engine._bar_count == 35

    def test_same_bar_count_switch_advances_exactly_once(self, engine):
        before = _stamp(engine)
        engine.begin_activation_transaction()
        engine.reconfigure_bar_count(48)  # unchanged: prepares nothing
        engine.reset_smoothing_state()
        engine.end_activation_transaction(reason="mode_switch")
        after = _stamp(engine)
        assert after == (before[0] + 1, before[1] + 1)

    def test_a_transaction_that_prepares_nothing_commits_nothing(self, engine):
        before = _stamp(engine)
        engine.begin_activation_transaction()
        engine.reconfigure_bar_count(48)
        engine.end_activation_transaction(reason="inert")
        assert _stamp(engine) == before

    def test_nested_transactions_commit_once(self, engine):
        before = _stamp(engine)
        engine.begin_activation_transaction()
        engine.begin_activation_transaction()
        engine.reconfigure_bar_count(35)
        engine.end_activation_transaction(reason="inner")
        assert _stamp(engine) == before, "an inner scope committed early"
        engine.reset_smoothing_state()
        engine.end_activation_transaction(reason="outer")
        assert _stamp(engine) == (before[0] + 1, before[1] + 1)

    def test_commit_republishes_the_activation_id_to_the_audio_worker(self, engine):
        engine.begin_activation_transaction()
        engine.reconfigure_bar_count(35)
        engine.end_activation_transaction(reason="mode_switch")
        assert engine._audio_worker._activation_id == engine.get_activation_id()

    def test_fresh_frame_gating_waits_for_the_final_generation(self, engine):
        """Nothing produced before the commit may satisfy the fresh-frame gate."""
        engine.begin_activation_transaction()
        engine.reconfigure_bar_count(35)
        engine.reset_smoothing_state()
        engine.end_activation_transaction(reason="mode_switch")
        assert engine.get_latest_generation_with_frame() == engine.get_generation_id() - 1
        assert engine.get_latest_generation_with_waveform() == engine.get_generation_id() - 1

    def test_the_context_manager_commits_once(self, engine):
        widget = type("W", (), {"_engine": engine})()
        before = _stamp(engine)
        with engine_activation_transaction(widget, reason="mode_switch"):
            engine.reconfigure_bar_count(35)
            engine.reset_smoothing_state()
        assert _stamp(engine) == (before[0] + 1, before[1] + 1)

    def test_the_context_manager_commits_even_when_the_body_raises(self, engine):
        widget = type("W", (), {"_engine": engine})()
        before = _stamp(engine)
        with pytest.raises(RuntimeError):
            with engine_activation_transaction(widget, reason="mode_switch"):
                engine.reconfigure_bar_count(35)
                raise RuntimeError("boom")
        assert engine.in_activation_transaction() is False, (
            "a failed activation must not leave the transaction open forever"
        )
        assert _stamp(engine) == (before[0] + 1, before[1] + 1)

    def test_a_widget_without_an_engine_is_a_safe_no_op(self):
        widget = type("W", (), {"_engine": None})()
        with engine_activation_transaction(widget, reason="mode_switch") as engine:
            assert engine is None


# ---------------------------------------------------------------------------
# Activation payload identity
# ---------------------------------------------------------------------------


class _Payload:
    def __init__(self, *, mode="bubble", preset_index=0, is_custom=False,
                 preset_name="Default", preset_path=None, resolved_config=None):
        self.mode = mode
        self.preset_index = preset_index
        self.is_custom = is_custom
        self.preset_name = preset_name
        self.preset_path = preset_path
        self.resolved_config = resolved_config if resolved_config is not None else {}


def _config(**overrides):
    base = {
        "mode": "bubble",
        "bar_count": 48,
        "sensitivity": 1.0,
        "audio_block_size": 512,
        "nested": {"a": [1, 2, 3], "b": True},
    }
    base.update(overrides)
    return base


class TestActivationPayloadIdentity:
    def test_structurally_identical_payloads_match(self):
        """Distinct dict instances with equal values are the same activation."""
        a = _Payload(resolved_config=_config())
        b = _Payload(resolved_config=_config())
        assert a.resolved_config is not b.resolved_config
        assert activation_payload_identity(a) == activation_payload_identity(b)

    def test_key_order_does_not_change_identity(self):
        a = _Payload(resolved_config={"x": 1, "y": 2})
        b = _Payload(resolved_config={"y": 2, "x": 1})
        assert activation_payload_identity(a) == activation_payload_identity(b)

    def test_a_genuine_value_change_changes_identity(self):
        a = _Payload(resolved_config=_config())
        b = _Payload(resolved_config=_config(sensitivity=1.4))
        assert activation_payload_identity(a) != activation_payload_identity(b)

    def test_a_nested_value_change_changes_identity(self):
        a = _Payload(resolved_config=_config())
        b = _Payload(resolved_config=_config(nested={"a": [1, 2, 4], "b": True}))
        assert activation_payload_identity(a) != activation_payload_identity(b)

    def test_a_same_mode_preset_change_changes_identity(self):
        """The rejected per-mode cache failed exactly here."""
        a = _Payload(mode="bubble", preset_index=0, preset_name="Deep Sea",
                     resolved_config=_config())
        b = _Payload(mode="bubble", preset_index=1, preset_name="Organs",
                     resolved_config=_config(sensitivity=2.0))
        assert activation_payload_identity(a) != activation_payload_identity(b)

    def test_a_mode_change_changes_identity(self):
        a = _Payload(mode="bubble", resolved_config=_config())
        b = _Payload(mode="devcurve", resolved_config=_config(mode="devcurve"))
        assert activation_payload_identity(a) != activation_payload_identity(b)

    def test_identity_is_stable_across_repeated_resolution(self):
        payload = _Payload(resolved_config=_config())
        assert activation_payload_identity(payload) == activation_payload_identity(payload)

    def test_identity_does_not_use_object_identity(self):
        class _Thing:
            def __init__(self, value):
                self.value = value

            def __repr__(self):
                return f"_Thing({self.value})"

        a = _Payload(resolved_config={"obj": _Thing(1)})
        b = _Payload(resolved_config={"obj": _Thing(1)})
        assert activation_payload_identity(a) == activation_payload_identity(b)


# ---------------------------------------------------------------------------
# Identical post-activation refresh is a no-op
# ---------------------------------------------------------------------------


class _ApplyWidget:
    """Only the surface ``apply_resolved_activation_payload`` actually touches."""

    def __init__(self, engine, mode):
        self._engine = engine
        self._vis_mode = mode
        self._settings_model = None
        self._technical_config_cache: dict = {}
        self._last_gpu_geom = None
        self._last_gpu_fade_sent = -1.0
        self._has_pushed_first_frame = False
        self._mode_transition_phase = 0
        self._mode_transition_apply_height_on_resume = True
        self._waiting_for_fresh_engine_frame = False
        self._waiting_for_fresh_frame = False
        self._committed_activation_identity = None
        self.technical_applies: list[str] = []

    # -- authority the function consults --------------------------------
    def _build_technical_cache(self, model):
        return {}

    def _map_mode_key_to_enum(self, key):
        from widgets.spotify_visualizer.audio_worker import VisualizerMode

        return getattr(VisualizerMode, str(key).upper())

    def _get_mode_technical_config(self, mode):
        return {"present": True}

    def _apply_technical_config_for_mode(self, mode, *, reason):
        self.technical_applies.append(reason)

    def _replay_engine_config(self, engine):
        pass

    def _sync_active_mode_legacy_ghost_bridge(self, vm):
        pass

    def _is_custom_layout_route_selected(self):
        return False

    def _is_custom_layout_active(self):
        return False

    def _apply_pending_mode_transition_layout(self):
        pass

    def _reset_mode_owned_runtime_state(self, *, reason):
        pass

    def _clear_gl_overlay(self):
        pass

    def _prepare_engine_for_mode_reset(self):
        # Production resets smoothing here; that must be inside the transaction.
        self._engine.reset_smoothing_state()

    def _clear_runtime_bar_state(self):
        pass

    def parent(self):
        return None


@pytest.fixture
def apply_env(engine, monkeypatch):
    from widgets.spotify_visualizer import activation_runtime
    from widgets.spotify_visualizer.audio_worker import VisualizerMode

    monkeypatch.setattr(
        activation_runtime, "_store_authoritative_settings_model", lambda w, m: m
    )
    monkeypatch.setattr(activation_runtime, "log_live_activation_state",
                        lambda *a, **k: None)
    import rendering.spotify_widget_creators as creators

    monkeypatch.setattr(creators, "apply_spotify_vis_model_config",
                        lambda *a, **k: None)
    widget = _ApplyWidget(engine, VisualizerMode.BUBBLE)
    return activation_runtime, widget


class TestIdenticalRefreshIsANoOp:
    def _apply(self, activation_runtime, widget, payload, *, reason, force=False):
        activation_runtime.apply_resolved_activation_payload(
            widget, object(), payload, reason=reason, force_runtime_reset=force
        )

    def test_identical_refresh_after_activation_does_not_reapply(self, apply_env):
        activation_runtime, widget = apply_env
        payload = _Payload(resolved_config=_config())

        self._apply(activation_runtime, widget, payload, reason="mode_switch")
        applied_once = len(widget.technical_applies)
        assert applied_once == 1

        # The exact replay the installed run performed after the fresh frame.
        self._apply(
            activation_runtime,
            widget,
            _Payload(resolved_config=_config()),
            reason="settings_refresh",
        )
        assert len(widget.technical_applies) == applied_once, (
            "an identical activation payload was applied twice"
        )

    def test_a_genuine_same_mode_preset_change_still_applies(self, apply_env):
        activation_runtime, widget = apply_env
        self._apply(
            activation_runtime, widget,
            _Payload(preset_index=0, resolved_config=_config()),
            reason="mode_switch",
        )
        self._apply(
            activation_runtime, widget,
            _Payload(preset_index=1, resolved_config=_config(sensitivity=2.0)),
            reason="preset_cycle",
        )
        assert len(widget.technical_applies) == 2

    def test_a_genuine_settings_mutation_still_applies(self, apply_env):
        activation_runtime, widget = apply_env
        self._apply(activation_runtime, widget,
                    _Payload(resolved_config=_config()), reason="mode_switch")
        self._apply(activation_runtime, widget,
                    _Payload(resolved_config=_config(audio_block_size=256)),
                    reason="settings_refresh")
        assert len(widget.technical_applies) == 2

    def test_a_changed_engine_generation_defeats_suppression(self, apply_env):
        activation_runtime, widget = apply_env
        payload = _Payload(resolved_config=_config())
        self._apply(activation_runtime, widget, payload, reason="mode_switch")
        widget._engine.reset_smoothing_state()  # something else reset the runtime
        self._apply(activation_runtime, widget,
                    _Payload(resolved_config=_config()), reason="settings_refresh")
        assert len(widget.technical_applies) == 2

    def test_a_forced_runtime_reset_is_never_suppressed(self, apply_env):
        activation_runtime, widget = apply_env
        payload = _Payload(resolved_config=_config())
        self._apply(activation_runtime, widget, payload, reason="mode_switch")
        self._apply(activation_runtime, widget,
                    _Payload(resolved_config=_config()),
                    reason="settings_refresh", force=True)
        assert len(widget.technical_applies) == 2

    def test_a_mode_change_is_never_suppressed(self, apply_env):
        activation_runtime, widget = apply_env
        self._apply(activation_runtime, widget,
                    _Payload(mode="bubble", resolved_config=_config()),
                    reason="mode_switch")
        self._apply(activation_runtime, widget,
                    _Payload(mode="devcurve", resolved_config=_config(mode="devcurve")),
                    reason="mode_switch")
        assert len(widget.technical_applies) == 2

    def test_a_real_mode_switch_advances_the_engine_exactly_once(self, apply_env):
        """The end-to-end shape of the installed BUBBLE -> DEVCURVE defect."""
        activation_runtime, widget = apply_env
        engine = widget._engine
        engine.reconfigure_bar_count(48)
        before = _stamp(engine)

        def _resize_then_reset(mode, *, reason):
            widget.technical_applies.append(reason)
            engine.reconfigure_bar_count(35)  # the bar_buffer_resize pass

        widget._apply_technical_config_for_mode = _resize_then_reset

        self._apply(
            activation_runtime, widget,
            _Payload(mode="devcurve", resolved_config=_config(mode="devcurve")),
            reason="mode_switch",
        )
        after = _stamp(engine)
        assert after == (before[0] + 1, before[1] + 1), (
            "bar-count resize and smoothing reset each advanced the generation"
        )
        assert engine._bar_count == 35

    def test_the_identical_refresh_after_that_switch_is_a_no_op(self, apply_env):
        activation_runtime, widget = apply_env
        payload = _Payload(mode="devcurve", resolved_config=_config(mode="devcurve"))
        self._apply(activation_runtime, widget, payload, reason="mode_switch")
        applies = len(widget.technical_applies)
        self._apply(
            activation_runtime, widget,
            _Payload(mode="devcurve", resolved_config=_config(mode="devcurve")),
            reason="settings_refresh",
        )
        assert len(widget.technical_applies) == applies
