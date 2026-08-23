from __future__ import annotations

import random
import threading
from collections import Counter
from types import SimpleNamespace

from engine.screensaver_engine import ScreensaverEngine
from rendering.transition_registry import get_transition_setting_names


class _FakeSettingsManager:
    def __init__(self, *, transitions: dict, hw_accel: bool = True) -> None:
        self._transitions = dict(transitions)
        self._display = {"hw_accel": hw_accel}

    def get(self, key: str, default=None):
        if key == "transitions":
            return self._transitions
        if key == "display.hw_accel":
            return self._display.get("hw_accel", default)

        current = None
        if key.startswith("transitions."):
            current = self._transitions
            parts = key.split(".")[1:]
        elif key.startswith("display."):
            current = self._display
            parts = key.split(".")[1:]
        else:
            return default

        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        return current

    def set(self, key: str, value) -> None:
        if key.startswith("transitions."):
            current = self._transitions
            parts = key.split(".")[1:]
        elif key.startswith("display."):
            current = self._display
            parts = key.split(".")[1:]
        else:
            return

        for part in parts[:-1]:
            next_node = current.get(part)
            if not isinstance(next_node, dict):
                next_node = {}
                current[part] = next_node
            current = next_node
        current[parts[-1]] = value

    def save(self) -> None:
        return


def _run_random_transition_prepare(settings: _FakeSettingsManager) -> str:
    engine = type("EngineStub", (), {"settings_manager": settings})()
    ScreensaverEngine._prepare_random_transition_if_needed(engine)
    return settings.get("transitions.random_choice")


def test_random_transition_pool_can_select_burn_when_hw_accel_enabled() -> None:
    transitions = {
        "type": "Random",
        "random_always": True,
        "pool": {
            "Crossfade": False,
            "Slide": False,
            "Wipe": False,
            "Diffuse": False,
            "Block Puzzle Flip": False,
            "Blinds": False,
            "3D Block Spins": False,
            "Ripple": False,
            "Warp Dissolve": False,
            "Crumble": False,
            "Particle": False,
            "Burn": True,
        },
    }
    settings = _FakeSettingsManager(transitions=transitions, hw_accel=True)

    choice = _run_random_transition_prepare(settings)

    assert choice == "Burn"
    assert settings.get("transitions.last_random_choice") == "Burn"


def test_random_transition_distribution_is_approximately_uniform_for_enabled_pool() -> None:
    transitions = {
        "type": "Random",
        "random_always": True,
        "pool": {
            "Crossfade": True,
            "Slide": True,
            "Wipe": True,
            "Diffuse": True,
            "Block Puzzle Flip": True,
            "Blinds": True,
            "3D Block Spins": True,
            "Ripple": True,
            "Warp Dissolve": True,
            "Crumble": True,
            "Particle": True,
            "Burn": True,
        },
    }
    settings = _FakeSettingsManager(transitions=transitions, hw_accel=True)

    rng_state = random.getstate()
    random.seed(1337)
    try:
        draws = 12000
        counts: Counter[str] = Counter()
        for _ in range(draws):
            choice = _run_random_transition_prepare(settings)
            counts[choice] += 1
    finally:
        random.setstate(rng_state)

    expected_types = {
        "Crossfade",
        "Slide",
        "Wipe",
        "Diffuse",
        "Block Puzzle Flip",
        "Blinds",
        "3D Block Spins",
        "Ripple",
        "Warp Dissolve",
        "Crumble",
        "Particle",
        "Burn",
    }
    assert set(counts) == expected_types

    expected = draws / len(expected_types)
    lower = expected * 0.88
    upper = expected * 1.12
    for transition_name in expected_types:
        assert lower <= counts[transition_name] <= upper, (
            transition_name,
            counts[transition_name],
            lower,
            upper,
        )


def test_deactivated_transition_is_excluded_from_random_pool() -> None:
    # Every transition is a pool member, but Burn is deactivated, so it must
    # never be chosen while every other activated transition still can be.
    transitions = {
        "type": "Random",
        "random_always": True,
        "pool": {name: True for name in (
            "Crossfade", "Slide", "Wipe", "Diffuse", "Block Puzzle Flip",
            "Blinds", "3D Block Spins", "Ripple", "Warp Dissolve", "Crumble",
            "Particle", "Burn",
        )},
        "activation": {"Burn": False},
    }
    settings = _FakeSettingsManager(transitions=transitions, hw_accel=True)

    rng_state = random.getstate()
    random.seed(2024)
    try:
        choices = {_run_random_transition_prepare(settings) for _ in range(4000)}
    finally:
        random.setstate(rng_state)

    assert "Burn" not in choices
    # Other activated transitions are still reachable.
    assert "Crossfade" in choices
    assert "Particle" in choices


def test_empty_effective_pool_resolves_to_activated_transition() -> None:
    # The only pooled transition (Burn) is deactivated -> empty effective pool.
    # The engine must resolve to an activated transition, never the deactivated
    # Burn, rather than silently running it.
    transitions = {
        "type": "Random",
        "random_always": True,
        "pool": {"Burn": True},
        "activation": {"Burn": False},
    }
    settings = _FakeSettingsManager(transitions=transitions, hw_accel=True)

    rng_state = random.getstate()
    random.seed(4242)
    try:
        for _ in range(50):
            choice = _run_random_transition_prepare(settings)
            assert choice != "Burn"
    finally:
        random.setstate(rng_state)


def test_engine_random_fails_closed_when_pool_hw_unavailable() -> None:
    # Random on; the only activated pool member (Burn) is hw-required and hw is
    # off; Crossfade is activated + hw-safe but NOT a pool member. Random must
    # fail closed — never escape the saved pool into the out-of-pool Crossfade.
    pool = {name: False for name in get_transition_setting_names()}
    pool["Burn"] = True
    transitions = {
        "type": "Crossfade",
        "random_always": True,
        "pool": pool,
        "activation": {},
    }
    settings = _FakeSettingsManager(transitions=transitions, hw_accel=False)
    choice = _run_random_transition_prepare(settings)
    assert choice is None  # no out-of-pool substitution; fail closed
    # Saved pool membership is unchanged.
    assert settings.get("transitions.pool")["Burn"] is True
    assert settings.get("transitions.pool")["Crossfade"] is False


def test_rotation_timer_does_not_prepare_random_choice_twice() -> None:
    calls = {"show": 0, "prepare": 0}

    def _show_next_image():
        calls["show"] += 1
        return True

    def _prepare_random_transition_if_needed():
        calls["prepare"] += 1

    engine = SimpleNamespace(
        _show_next_image=_show_next_image,
        _has_active_image_change_work=lambda: False,
        _prepare_random_transition_if_needed=_prepare_random_transition_if_needed,
    )

    ScreensaverEngine._on_rotation_timer(engine)

    assert calls == {"show": 1, "prepare": 0}


def test_rotation_timer_coalesces_before_image_acquisition_when_transition_busy() -> None:
    calls = {"show": 0}
    engine = SimpleNamespace(
        _has_active_image_change_work=lambda: True,
        _show_next_image=lambda: calls.__setitem__("show", calls["show"] + 1),
    )

    ScreensaverEngine._on_rotation_timer(engine)

    assert calls["show"] == 0


def test_manual_next_rebases_only_after_request_is_accepted() -> None:
    calls = {"show": 0, "rebase": []}
    accepted = [False, True]
    engine = SimpleNamespace(
        _show_next_image=lambda: (
            calls.__setitem__("show", calls["show"] + 1),
            accepted.pop(0),
        )[1],
        _rebase_rotation_timer=lambda *, reason: calls["rebase"].append(reason),
    )

    ScreensaverEngine._on_next_requested(engine)
    ScreensaverEngine._on_next_requested(engine)

    assert calls["show"] == 2
    assert calls["rebase"] == ["manual_next"]


def test_manual_previous_rebases_after_fallback_request_is_accepted() -> None:
    calls = {"previous": 0, "rebase": [], "clear": 0}

    class _Queue:
        def previous(self):
            calls["previous"] += 1

    engine = SimpleNamespace(
        image_queue=_Queue(),
        _display_image_history=[],
        _try_begin_image_change_work=lambda: True,
        _show_current_image=lambda: True,
        _rebase_rotation_timer=lambda *, reason: calls["rebase"].append(reason),
        _clear_unaccepted_image_change_work=lambda: calls.__setitem__(
            "clear",
            calls["clear"] + 1,
        ),
    )

    ScreensaverEngine._on_previous_requested(engine)

    assert calls["previous"] == 1
    assert calls["rebase"] == ["manual_previous"]
    assert calls["clear"] == 0


def test_manual_previous_claims_work_before_queue_or_async_submission() -> None:
    events = []

    class _Queue:
        def previous(self):
            events.append("queue_previous")

    engine = SimpleNamespace(
        image_queue=_Queue(),
        _display_image_history=[[object()]],
        _current_image=None,
        _try_begin_image_change_work=lambda: events.append("claim") or True,
        _show_images_for_displays=lambda _metas: events.append("submit") or True,
        _rebase_rotation_timer=lambda *, reason: events.append(reason),
        _clear_unaccepted_image_change_work=lambda: events.append("clear"),
    )

    ScreensaverEngine._on_previous_requested(engine)

    assert events == [
        "claim",
        "queue_previous",
        "submit",
        "manual_previous",
    ]


def test_manual_previous_releases_owner_and_does_not_rebase_rejected_submission() -> None:
    calls = {"rebase": [], "clear": 0}

    class _Queue:
        def previous(self):
            return None

    engine = SimpleNamespace(
        image_queue=_Queue(),
        _display_image_history=[[object()]],
        _current_image=None,
        _try_begin_image_change_work=lambda: True,
        _show_images_for_displays=lambda _metas: False,
        _rebase_rotation_timer=lambda *, reason: calls["rebase"].append(reason),
        _clear_unaccepted_image_change_work=lambda: calls.__setitem__(
            "clear",
            calls["clear"] + 1,
        ),
    )

    ScreensaverEngine._on_previous_requested(engine)

    assert calls["rebase"] == []
    assert calls["clear"] == 1


def test_show_images_for_displays_propagates_async_submission_rejection(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "engine.image_pipeline.load_and_display_image_async_with_metas",
        lambda _engine, _metas: False,
    )
    engine = SimpleNamespace(
        display_manager=object(),
        thread_manager=object(),
    )

    assert ScreensaverEngine._show_images_for_displays(
        engine,
        [object()],
    ) is False


def test_previous_work_claim_is_visible_to_rotation_timer() -> None:
    pending = []
    display_manager = SimpleNamespace(
        set_transition_work_pending=lambda value: pending.append(value),
        has_transition_work_pending=lambda: bool(pending and pending[-1]),
    )
    engine = SimpleNamespace(
        _loading_lock=threading.Lock(),
        _loading_in_progress=False,
        display_manager=display_manager,
    )

    assert ScreensaverEngine._try_begin_image_change_work(engine) is True
    assert engine._loading_in_progress is True
    assert pending == [True]
    assert ScreensaverEngine._has_active_image_change_work(engine) is True


def test_rotation_rebase_never_starts_an_inactive_timer() -> None:
    class _Timer:
        def __init__(self, active):
            self.active = active
            self.start_calls = 0

        def isActive(self):
            return self.active

        def interval(self):
            return 40000

        def start(self):
            self.start_calls += 1

    inactive = _Timer(False)
    active = _Timer(True)

    assert ScreensaverEngine._rebase_rotation_timer(
        SimpleNamespace(_rotation_timer=inactive),
        reason="inactive",
    ) is False
    assert ScreensaverEngine._rebase_rotation_timer(
        SimpleNamespace(_rotation_timer=active),
        reason="active",
    ) is True
    assert inactive.start_calls == 0
    assert active.start_calls == 1


def test_show_next_image_does_not_prepare_random_choice_without_runtime_targets() -> None:
    calls = {"prepare": 0}

    engine = SimpleNamespace(
        image_queue=None,
        display_manager=None,
        _prepare_random_transition_if_needed=lambda: calls.__setitem__("prepare", calls["prepare"] + 1),
    )

    assert ScreensaverEngine._show_next_image(engine) is False
    assert calls["prepare"] == 0


def test_show_next_image_does_not_prepare_random_choice_for_empty_queue_result() -> None:
    calls = {"prepare": 0, "load": 0, "pending": []}
    lock = threading.Lock()

    class _Queue:
        def next(self):
            return None

    display_manager = SimpleNamespace(
        set_transition_work_pending=lambda value: calls["pending"].append(value),
        show_error=lambda _message: None,
    )
    engine = SimpleNamespace(
        image_queue=_Queue(),
        display_manager=display_manager,
        _loading_lock=lock,
        _loading_in_progress=False,
        _prepare_random_transition_if_needed=lambda: calls.__setitem__("prepare", calls["prepare"] + 1),
        _load_and_display_image=lambda _image_meta: calls.__setitem__("load", calls["load"] + 1) or True,
        thread_manager=None,
        _current_image=None,
    )

    assert ScreensaverEngine._show_next_image(engine) is False
    assert calls["prepare"] == 0
    assert calls["load"] == 0
    assert calls["pending"] == [True, False]


def test_show_next_image_prepares_random_choice_once_for_accepted_image_batch() -> None:
    calls = {"prepare": 0, "load": 0, "pending": []}
    lock = threading.Lock()
    image_meta = {"path": "accepted-image.jpg"}

    class _Queue:
        def next(self):
            return image_meta

    display_manager = SimpleNamespace(
        set_transition_work_pending=lambda value: calls["pending"].append(value),
        show_error=lambda _message: None,
    )
    engine = SimpleNamespace(
        image_queue=_Queue(),
        display_manager=display_manager,
        _loading_lock=lock,
        _loading_in_progress=False,
        _prepare_random_transition_if_needed=lambda: calls.__setitem__("prepare", calls["prepare"] + 1),
        _load_and_display_image=lambda _image_meta: calls.__setitem__("load", calls["load"] + 1) or True,
        thread_manager=None,
        _current_image=None,
    )

    assert ScreensaverEngine._show_next_image(engine) is True
    assert calls["prepare"] == 1
    assert calls["load"] == 1
    assert calls["pending"] == [True]
    assert engine._current_image is image_meta
