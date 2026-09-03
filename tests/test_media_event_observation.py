"""Controller-level native GSMTC observation contract (deterministic fakes).

These falsify the token-lifetime and session-replacement mistakes the migration
is most exposed to, without requiring real WinRT or active playback:

* manager + current-session ``add_*_changed`` subscriptions are established;
* a native event only hands a coarse dirty reason to ``on_dirty`` (it never
  queries, awaits, decodes, or touches presentation here);
* session replacement is transactional: old-session tokens are detached before
  the new identity is adopted, and a stale old-session callback is fenced;
* stop detaches every token exactly once and fences any late callback.

The deterministic lane below executes inline so these tests remain about token/
session semantics. ``test_media_winrt_affinity_and_native_fault_contract.py``
separately proves that the production affinity scheduler executes retained WinRT
work on one non-caller OS thread.

A separate environment-gated test exercises the *real* installed projection.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.media.media_controller import WindowsGlobalMediaController


class _SyncAffinityLane:
    """Minimal deterministic stand-in for ThreadManager's affinity lane API."""

    def __init__(self) -> None:
        self._stopped = False

    @property
    def is_stopped(self) -> bool:
        return self._stopped

    def submit(self, func) -> bool:
        if self._stopped:
            return False
        func()
        return True

    def call(self, func, *, timeout=None):
        del timeout
        if self._stopped:
            raise RuntimeError("lane stopped")
        return func()

    def stop(self, *, wait=True, timeout=None) -> bool:
        del wait, timeout
        self._stopped = True
        return True


class _SyncThreadManager:
    """Creates an inline deterministic lane for token/session unit tests."""

    def create_affinity_lane(self, **_kwargs):
        return _SyncAffinityLane()


class _FakeSession:
    def __init__(self, source_id: str, status) -> None:
        self.source_app_user_model_id = source_id
        self._status = status
        self._handlers: dict[str, dict[int, object]] = {}
        self._next_token = 1
        self.removed: list[tuple[str, int]] = []

    def get_playback_info(self):
        return SimpleNamespace(playback_status=self._status, controls=None)

    def _add(self, name, cb) -> int:
        token = self._next_token
        self._next_token += 1
        self._handlers.setdefault(name, {})[token] = cb
        return token

    def _remove(self, name, token) -> None:
        self.removed.append((name, token))
        self._handlers.get(name, {}).pop(token, None)

    def add_playback_info_changed(self, cb):
        return self._add("playback", cb)

    def remove_playback_info_changed(self, token):
        self._remove("playback", token)

    def add_media_properties_changed(self, cb):
        return self._add("media_properties", cb)

    def remove_media_properties_changed(self, token):
        self._remove("media_properties", token)

    def add_timeline_properties_changed(self, cb):
        return self._add("timeline", cb)

    def remove_timeline_properties_changed(self, token):
        self._remove("timeline", token)

    def fire(self, name) -> None:
        for cb in list(self._handlers.get(name, {}).values()):
            cb(self, None)

    def live_handler_count(self) -> int:
        return sum(len(v) for v in self._handlers.values())


class _FakeManager:
    def __init__(self, sessions, current) -> None:
        self._sessions = list(sessions)
        self._current = current
        self._handlers: dict[str, dict[int, object]] = {}
        self._next_token = 1
        self.removed: list[tuple[str, int]] = []

    def get_sessions(self):
        return list(self._sessions)

    def get_current_session(self):
        return self._current

    def set_current(self, session) -> None:
        self._current = session
        if session is not None and session not in self._sessions:
            self._sessions.append(session)

    def _add(self, name, cb) -> int:
        token = self._next_token
        self._next_token += 1
        self._handlers.setdefault(name, {})[token] = cb
        return token

    def _remove(self, name, token) -> None:
        self.removed.append((name, token))
        self._handlers.get(name, {}).pop(token, None)

    def add_current_session_changed(self, cb):
        return self._add("current_session", cb)

    def remove_current_session_changed(self, token):
        self._remove("current_session", token)

    def add_sessions_changed(self, cb):
        return self._add("sessions", cb)

    def remove_sessions_changed(self, token):
        self._remove("sessions", token)

    def fire(self, name) -> None:
        for cb in list(self._handlers.get(name, {}).values()):
            cb(self, None)

    def live_handler_count(self) -> int:
        return sum(len(v) for v in self._handlers.values())


_PLAYBACK = SimpleNamespace(PLAYING=object(), PAUSED=object(), STOPPED=object())


def _make_controller(manager: _FakeManager) -> WindowsGlobalMediaController:
    controller = WindowsGlobalMediaController(
        thread_manager=_SyncThreadManager(), app_filter="spotify"
    )
    controller._available = True
    controller._PlaybackStatus = _PLAYBACK

    class _FakeManagerClass:
        instance = manager

        @staticmethod
        async def request_async():
            return _FakeManagerClass.instance

    controller._MediaManager = _FakeManagerClass
    return controller


def test_observation_subscribes_manager_and_session_and_emits_coarse_reasons() -> None:
    session = _FakeSession("Spotify.exe", _PLAYBACK.PLAYING)
    manager = _FakeManager([session], session)
    controller = _make_controller(manager)
    reasons: list[str] = []

    established: list[tuple[bool, str]] = []
    assert controller.start_event_observation(
        reasons.append, lambda ok, detail: established.append((ok, detail))
    ) is True
    assert controller.is_event_observation_active() is True
    assert established and established[0][0] is True

    assert manager.live_handler_count() == 2
    assert session.live_handler_count() == 3

    session.fire("playback")
    session.fire("media_properties")
    session.fire("timeline")
    assert reasons == ["playback", "media_properties", "timeline"]

    controller.retire()


def test_session_replacement_detaches_old_tokens_before_adopting_new() -> None:
    old = _FakeSession("Spotify.exe", _PLAYBACK.PLAYING)
    manager = _FakeManager([old], old)
    controller = _make_controller(manager)
    reasons: list[str] = []
    controller.start_event_observation(reasons.append)
    assert old.live_handler_count() == 3

    new = _FakeSession("Spotify.exe", _PLAYBACK.PLAYING)
    manager.set_current(new)
    reasons.clear()
    manager.fire("current_session")

    assert {name for name, _token in old.removed} == {
        "playback", "media_properties", "timeline"
    }
    assert old.live_handler_count() == 0
    assert new.live_handler_count() == 3
    assert reasons == ["session"]

    reasons.clear()
    old.fire("playback")
    assert reasons == []
    new.fire("timeline")
    assert reasons == ["timeline"]

    controller.retire()


def test_stop_observation_detaches_all_tokens_and_fences_late_callbacks() -> None:
    session = _FakeSession("Spotify.exe", _PLAYBACK.PLAYING)
    manager = _FakeManager([session], session)
    controller = _make_controller(manager)
    reasons: list[str] = []
    controller.start_event_observation(reasons.append)
    assert session.live_handler_count() == 3
    assert manager.live_handler_count() == 2

    controller.stop_event_observation()
    assert controller.is_event_observation_active() is False
    assert session.live_handler_count() == 0
    assert manager.live_handler_count() == 0

    reasons.clear()
    session.fire("playback")
    manager.fire("current_session")
    assert reasons == []


def test_unavailable_controller_reports_no_observation_support() -> None:
    session = _FakeSession("Spotify.exe", _PLAYBACK.PLAYING)
    manager = _FakeManager([session], session)
    controller = _make_controller(manager)
    controller._available = False
    assert controller.supports_event_observation() is False
    assert controller.start_event_observation(lambda _reason: None) is False


@pytest.mark.skip(reason="environment-dependent: exercises real installed WinRT projection")
def test_real_winrt_projection_subscribe_unsubscribe_round_trip() -> None:
    import asyncio

    from winrt.windows.media.control import (  # type: ignore[import]
        GlobalSystemMediaTransportControlsSessionManager as Manager,
    )

    async def _run() -> None:
        mgr = await Manager.request_async()
        assert mgr is not None
        token = mgr.add_current_session_changed(lambda _s, _a: None)
        mgr.remove_current_session_changed(token)

    asyncio.run(_run())
