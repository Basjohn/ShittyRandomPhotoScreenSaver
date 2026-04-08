import main


def test_schedule_runtime_reddit_helper_session_starts_keepalive(monkeypatch):
    class _FakeTimer:
        def __init__(self):
            self.stopped = False
            self.deleted = False

        def stop(self):
            self.stopped = True

        def deleteLater(self):
            self.deleted = True

    breadcrumb_calls: list[str] = []
    fake_timers: list[_FakeTimer] = []
    scheduled_calls: list[tuple[int, object, str]] = []

    class _FakeThreadManager:
        def schedule_recurring(self, interval_ms, func, description=None):
            scheduled_calls.append((interval_ms, func, description or ""))
            timer = _FakeTimer()
            fake_timers.append(timer)
            return timer

    class _FakeEngine:
        def __init__(self):
            self._running = True
            self._reddit_helper_session_timer = None
            self.thread_manager = _FakeThreadManager()

    engine = _FakeEngine()
    refresh_calls: list[str] = []
    ensure_calls: list[str] = []

    monkeypatch.setattr(main, "is_script_mode", lambda: False)
    monkeypatch.setattr("core.mc.is_mc_build", lambda: False)
    monkeypatch.setattr(
        "core.windows.reddit_helper_installer._log_helper_event",
        lambda msg: breadcrumb_calls.append(msg),
    )
    monkeypatch.setattr(
        "core.windows.reddit_helper_runtime.refresh_session_ticket",
        lambda *, source, valid_for_seconds=25.0: refresh_calls.append(source) or True,
        raising=False,
    )
    monkeypatch.setattr(
        "core.windows.reddit_helper_runtime.ensure_helper_runtime",
        lambda **kwargs: ensure_calls.append(kwargs["source"]) or True,
        raising=False,
    )
    monkeypatch.setattr(
        "core.windows.reddit_helper_runtime.is_helper_healthy",
        lambda: True,
        raising=False,
    )
    monkeypatch.setattr(
        "core.windows.reddit_helper_runtime.SESSION_TICKET_REFRESH_SECONDS",
        10.0,
        raising=False,
    )

    assert main._schedule_runtime_reddit_helper_session(engine) is True
    assert refresh_calls == ["run_session_start"]
    assert ensure_calls == ["run_session_start"]
    assert len(fake_timers) == 1
    assert scheduled_calls[0][0] == 10000
    assert scheduled_calls[0][2] == "Reddit helper session keepalive"
    assert "session helper start launched=1" in breadcrumb_calls


def test_schedule_runtime_reddit_helper_session_skips_script_mode(monkeypatch):
    breadcrumb_calls: list[str] = []

    monkeypatch.setattr(main, "is_script_mode", lambda: True)
    monkeypatch.setattr("core.mc.is_mc_build", lambda: False)
    monkeypatch.setattr(
        "core.windows.reddit_helper_installer._log_helper_event",
        lambda msg: breadcrumb_calls.append(msg),
    )
    monkeypatch.setattr(main.sys, "argv", ["main.py"])
    monkeypatch.setattr(main.sys, "executable", r"C:\Python311\python.exe")

    class _FakeEngine:
        _reddit_helper_session_timer = None
        thread_manager = object()

    assert main._schedule_runtime_reddit_helper_session(_FakeEngine()) is False
    assert breadcrumb_calls == ["session helper skipped script=1 mc=0 argv0=main.py exe=python.exe"]


def test_schedule_runtime_reddit_helper_session_skips_without_thread_manager(monkeypatch):
    breadcrumb_calls: list[str] = []

    class _FakeEngine:
        def __init__(self):
            self.thread_manager = None
            self._reddit_helper_session_timer = None

    engine = _FakeEngine()

    monkeypatch.setattr(main, "is_script_mode", lambda: False)
    monkeypatch.setattr("core.mc.is_mc_build", lambda: False)
    monkeypatch.setattr(
        "core.windows.reddit_helper_installer._log_helper_event",
        lambda msg: breadcrumb_calls.append(msg),
    )

    assert main._schedule_runtime_reddit_helper_session(engine) is False
    assert breadcrumb_calls[-1] == "session helper skipped no-thread-manager"
