from __future__ import annotations

import json
import time
from pathlib import Path


class TestRedditHelperRuntime:
    def test_is_helper_healthy_reads_recent_heartbeat(self, tmp_path, monkeypatch):
        from core.windows import reddit_helper_runtime as runtime

        signal_dir = tmp_path / "signals"
        signal_dir.mkdir(parents=True)
        heartbeat = signal_dir / runtime.HEARTBEAT_FILE_NAME
        heartbeat.write_text(
            json.dumps({"updated_at": time.time(), "pid": 123}),
            encoding="utf-8",
        )

        monkeypatch.setattr(runtime, "_signal_dir", lambda: signal_dir)

        assert runtime.is_helper_healthy()

    def test_ensure_helper_runtime_launches_when_stale(self, tmp_path, monkeypatch):
        from core.windows import reddit_helper_runtime as runtime

        base_dir = tmp_path / "base"
        queue_dir = base_dir / "url_queue"
        signal_dir = base_dir / "signals"
        queue_dir.mkdir(parents=True)
        signal_dir.mkdir(parents=True)

        launches: list[list[str]] = []
        registrations: list[list[str]] = []

        monkeypatch.setattr(runtime, "_running_as_system", lambda: False)
        monkeypatch.setattr(runtime.reddit_helper_bridge, "is_bridge_available", lambda: True)
        monkeypatch.setattr(runtime, "_base_dir", lambda: base_dir)
        monkeypatch.setattr(runtime, "_queue_dir", lambda: queue_dir)
        monkeypatch.setattr(runtime, "_signal_dir", lambda: signal_dir)
        monkeypatch.setattr(runtime, "_installed_helper_path", lambda: base_dir / "helper" / "SRPSS_RedditHelper.exe")
        monkeypatch.setattr(
            runtime,
            "resolve_helper_command",
            lambda: [str(base_dir / "helper" / "SRPSS_RedditHelper.exe"), "--watch", "--queue", str(queue_dir)],
        )
        monkeypatch.setattr(runtime, "_ensure_run_entry", lambda command: registrations.append(command) or True)
        monkeypatch.setattr(runtime, "_launch_helper", lambda command: launches.append(command) or True)

        assert runtime.ensure_helper_runtime(source="test") is True
        assert len(registrations) == 1
        assert len(launches) == 1

    def test_ensure_helper_runtime_skips_launch_when_heartbeat_is_fresh(self, tmp_path, monkeypatch):
        from core.windows import reddit_helper_runtime as runtime

        base_dir = tmp_path / "base"
        queue_dir = base_dir / "url_queue"
        signal_dir = base_dir / "signals"
        queue_dir.mkdir(parents=True)
        signal_dir.mkdir(parents=True)
        (signal_dir / runtime.HEARTBEAT_FILE_NAME).write_text(
            json.dumps({"updated_at": time.time(), "pid": 321}),
            encoding="utf-8",
        )

        launches: list[list[str]] = []

        monkeypatch.setattr(runtime, "_running_as_system", lambda: False)
        monkeypatch.setattr(runtime.reddit_helper_bridge, "is_bridge_available", lambda: True)
        monkeypatch.setattr(runtime, "_base_dir", lambda: base_dir)
        monkeypatch.setattr(runtime, "_queue_dir", lambda: queue_dir)
        monkeypatch.setattr(runtime, "_signal_dir", lambda: signal_dir)
        monkeypatch.setattr(runtime, "_installed_helper_path", lambda: base_dir / "helper" / "SRPSS_RedditHelper.exe")
        monkeypatch.setattr(
            runtime,
            "resolve_helper_command",
            lambda: [str(base_dir / "helper" / "SRPSS_RedditHelper.exe"), "--watch", "--queue", str(queue_dir)],
        )
        monkeypatch.setattr(runtime, "_ensure_run_entry", lambda command: True)
        monkeypatch.setattr(runtime, "_launch_helper", lambda command: launches.append(command) or True)

        assert runtime.ensure_helper_runtime(source="test") is True
        assert launches == []

    def test_ensure_helper_runtime_skips_in_system_context(self, monkeypatch):
        from core.windows import reddit_helper_runtime as runtime

        monkeypatch.setattr(runtime, "_running_as_system", lambda: True)

        assert runtime.ensure_helper_runtime(source="system") is False
