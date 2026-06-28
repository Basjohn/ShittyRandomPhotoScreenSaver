from __future__ import annotations

import random
import threading
from collections import Counter
from types import SimpleNamespace

from engine.screensaver_engine import ScreensaverEngine


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


def test_rotation_timer_does_not_prepare_random_choice_twice() -> None:
    calls = {"show": 0, "prepare": 0}

    def _show_next_image():
        calls["show"] += 1
        return True

    def _prepare_random_transition_if_needed():
        calls["prepare"] += 1

    engine = SimpleNamespace(
        _show_next_image=_show_next_image,
        _prepare_random_transition_if_needed=_prepare_random_transition_if_needed,
    )

    ScreensaverEngine._on_rotation_timer(engine)

    assert calls == {"show": 1, "prepare": 0}


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
