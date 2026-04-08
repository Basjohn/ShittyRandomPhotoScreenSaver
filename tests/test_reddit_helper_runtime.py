from __future__ import annotations

import json
import time
from pathlib import Path


class TestRedditHelperRuntime:
    def test_enqueue_url_marks_secure_desktop_entries_with_not_before_timestamp(self, tmp_path, monkeypatch):
        from core.windows import reddit_helper_bridge as bridge

        queue_dir = tmp_path / "url_queue"
        queue_dir.mkdir(parents=True)

        monkeypatch.setattr(bridge, "_QUEUE_DIR", queue_dir)
        monkeypatch.setattr(bridge, "_SPOOL_READY", True)
        monkeypatch.setattr(bridge.os, "getpid", lambda: 4242)
        monkeypatch.setattr(
            bridge.os,
            "getenv",
            lambda key, default=None: "Winlogon" if key == "SESSIONNAME" else default,
        )

        assert bridge.enqueue_url("https://example.com/winlogon", source="scr_click") is True

        queued_files = list(queue_dir.glob("*.json"))
        assert len(queued_files) == 1
        payload = json.loads(queued_files[0].read_text(encoding="utf-8"))
        assert payload["session"] == "Winlogon"
        assert payload["not_before_ts"] >= payload["timestamp"] + 3.0

    def test_enqueue_url_leaves_normal_session_entries_immediate(self, tmp_path, monkeypatch):
        from core.windows import reddit_helper_bridge as bridge

        queue_dir = tmp_path / "url_queue"
        queue_dir.mkdir(parents=True)

        monkeypatch.setattr(bridge, "_QUEUE_DIR", queue_dir)
        monkeypatch.setattr(bridge, "_SPOOL_READY", True)
        monkeypatch.setattr(bridge.os, "getpid", lambda: 4242)
        monkeypatch.setattr(
            bridge.os,
            "getenv",
            lambda key, default=None: "Console" if key == "SESSIONNAME" else default,
        )

        assert bridge.enqueue_url("https://example.com/manual", source="manual_test") is True

        queued_files = list(queue_dir.glob("*.json"))
        assert len(queued_files) == 1
        payload = json.loads(queued_files[0].read_text(encoding="utf-8"))
        assert payload["session"] == "Console"
        assert "not_before_ts" not in payload

    def test_resolve_helper_command_keeps_installed_helper_session_scoped_when_requested(self, tmp_path, monkeypatch):
        from core.windows import reddit_helper_runtime as runtime

        base_dir = tmp_path / "base"
        installed = base_dir / "helper" / "SRPSS_RedditHelper.exe"
        installed.parent.mkdir(parents=True)
        installed.write_text("", encoding="utf-8")

        monkeypatch.setattr(runtime, "_base_dir", lambda: base_dir)
        monkeypatch.setattr(runtime, "_queue_dir", lambda: base_dir / "url_queue")
        monkeypatch.setattr(runtime, "_installed_helper_path", lambda: installed)
        monkeypatch.setattr(runtime, "_repo_helper_candidates", lambda: [])

        command = runtime.resolve_helper_command(persistent=False)

        assert command is not None
        assert command[0] == str(installed)
        assert "--persistent" not in command
        assert "--owner-pid" in command

    def test_resolve_helper_command_uses_explicit_owner_and_idle_for_session_scope(self, tmp_path, monkeypatch):
        from core.windows import reddit_helper_runtime as runtime

        base_dir = tmp_path / "base"
        installed = base_dir / "helper" / "SRPSS_RedditHelper.exe"
        installed.parent.mkdir(parents=True)
        installed.write_text("", encoding="utf-8")

        monkeypatch.setattr(runtime, "_base_dir", lambda: base_dir)
        monkeypatch.setattr(runtime, "_queue_dir", lambda: base_dir / "url_queue")
        monkeypatch.setattr(runtime, "_installed_helper_path", lambda: installed)
        monkeypatch.setattr(runtime, "_repo_helper_candidates", lambda: [])

        command = runtime.resolve_helper_command(
            persistent=False,
            owner_pid=9999,
            idle_exit_seconds=123.0,
        )

        assert command is not None
        assert "--owner-pid" in command
        assert command[command.index("--owner-pid") + 1] == "9999"
        assert "--idle-exit-seconds" in command
        assert command[command.index("--idle-exit-seconds") + 1] == "123"

    def test_resolve_helper_command_marks_installed_helper_persistent_when_requested(self, tmp_path, monkeypatch):
        from core.windows import reddit_helper_runtime as runtime

        base_dir = tmp_path / "base"
        installed = base_dir / "helper" / "SRPSS_RedditHelper.exe"
        installed.parent.mkdir(parents=True)
        installed.write_text("", encoding="utf-8")

        monkeypatch.setattr(runtime, "_base_dir", lambda: base_dir)
        monkeypatch.setattr(runtime, "_queue_dir", lambda: base_dir / "url_queue")
        monkeypatch.setattr(runtime, "_installed_helper_path", lambda: installed)
        monkeypatch.setattr(runtime, "_repo_helper_candidates", lambda: [])

        command = runtime.resolve_helper_command(persistent=True)

        assert command is not None
        assert command[0] == str(installed)
        assert "--persistent" in command
        assert "--owner-pid" not in command

    def test_resolve_helper_command_marks_source_helper_session_scoped(self, tmp_path, monkeypatch):
        from core.windows import reddit_helper_runtime as runtime

        base_dir = tmp_path / "base"
        queue_dir = base_dir / "url_queue"
        signal_dir = base_dir / "signals"
        queue_dir.mkdir(parents=True)
        signal_dir.mkdir(parents=True)

        monkeypatch.setattr(runtime, "_base_dir", lambda: base_dir)
        monkeypatch.setattr(runtime, "_queue_dir", lambda: queue_dir)
        monkeypatch.setattr(runtime, "_signal_dir", lambda: signal_dir)
        monkeypatch.setattr(runtime, "_installed_helper_path", lambda: base_dir / "helper" / "SRPSS_RedditHelper.exe")
        monkeypatch.setattr(runtime, "_repo_helper_candidates", lambda: [])
        monkeypatch.setattr(
            runtime,
            "_source_helper_command",
            lambda: [r"C:\Python\pythonw.exe", r"F:\Programming\Apps\ShittyRandomPhotoScreenSaver\helpers\reddit_helper_worker.py"],
        )
        monkeypatch.setattr(runtime.os, "getpid", lambda: 4242)

        command = runtime.resolve_helper_command(persistent=False)

        assert command is not None
        assert "--owner-pid" in command
        assert "4242" in command
        assert "--idle-exit-seconds" in command
        assert "--persistent" not in command

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
        monkeypatch.setattr(runtime, "is_mc_build", lambda: False)
        monkeypatch.setattr(runtime.reddit_helper_bridge, "is_bridge_available", lambda: True)
        monkeypatch.setattr(runtime, "_base_dir", lambda: base_dir)
        monkeypatch.setattr(runtime, "_queue_dir", lambda: queue_dir)
        monkeypatch.setattr(runtime, "_signal_dir", lambda: signal_dir)
        monkeypatch.setattr(runtime, "_installed_helper_path", lambda: base_dir / "helper" / "SRPSS_RedditHelper.exe")
        monkeypatch.setattr(
            runtime,
            "resolve_helper_command",
            lambda **kwargs: [str(base_dir / "helper" / "SRPSS_RedditHelper.exe"), "--watch", "--queue", str(queue_dir), "--persistent"],
        )
        monkeypatch.setattr(runtime, "_ensure_run_entry", lambda command: registrations.append(command) or True)
        monkeypatch.setattr(runtime, "_launch_helper", lambda command: launches.append(command) or True)

        assert runtime.ensure_helper_runtime(source="test", persistent=True) is True
        assert len(registrations) == 1
        assert len(launches) == 1
        assert "--persistent" in registrations[0]
        assert "--persistent" in launches[0]

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
        monkeypatch.setattr(runtime, "is_mc_build", lambda: False)
        monkeypatch.setattr(runtime.reddit_helper_bridge, "is_bridge_available", lambda: True)
        monkeypatch.setattr(runtime, "_base_dir", lambda: base_dir)
        monkeypatch.setattr(runtime, "_queue_dir", lambda: queue_dir)
        monkeypatch.setattr(runtime, "_signal_dir", lambda: signal_dir)
        monkeypatch.setattr(runtime, "_installed_helper_path", lambda: base_dir / "helper" / "SRPSS_RedditHelper.exe")
        monkeypatch.setattr(
            runtime,
            "resolve_helper_command",
            lambda **kwargs: [str(base_dir / "helper" / "SRPSS_RedditHelper.exe"), "--watch", "--queue", str(queue_dir), "--persistent"],
        )
        monkeypatch.setattr(runtime, "_ensure_run_entry", lambda command: True)
        monkeypatch.setattr(runtime, "_launch_helper", lambda command: launches.append(command) or True)

        assert runtime.ensure_helper_runtime(source="test", persistent=True) is True
        assert launches == []

    def test_ensure_helper_runtime_skips_in_system_context(self, monkeypatch):
        from core.windows import reddit_helper_runtime as runtime

        monkeypatch.setattr(runtime, "_running_as_system", lambda: True)

        assert runtime.ensure_helper_runtime(source="system") is False

    def test_ensure_helper_runtime_skips_in_mc_build(self, monkeypatch):
        from core.windows import reddit_helper_runtime as runtime

        monkeypatch.setattr(runtime, "_running_as_system", lambda: False)
        monkeypatch.setattr(runtime, "is_mc_build", lambda: True)

        assert runtime.ensure_helper_runtime(source="mc") is False

    def test_ensure_helper_runtime_reaps_stale_helper_and_relaunches(self, tmp_path, monkeypatch):
        from core.windows import reddit_helper_runtime as runtime

        base_dir = tmp_path / "base"
        queue_dir = base_dir / "url_queue"
        signal_dir = base_dir / "signals"
        queue_dir.mkdir(parents=True)
        signal_dir.mkdir(parents=True)
        (signal_dir / runtime.HEARTBEAT_FILE_NAME).write_text(
            json.dumps({"updated_at": time.time() - 120.0, "pid": 999}),
            encoding="utf-8",
        )

        launches: list[list[str]] = []
        terminations: list[int] = []

        monkeypatch.setattr(runtime, "_running_as_system", lambda: False)
        monkeypatch.setattr(runtime, "is_mc_build", lambda: False)
        monkeypatch.setattr(runtime.reddit_helper_bridge, "is_bridge_available", lambda: True)
        monkeypatch.setattr(runtime, "_base_dir", lambda: base_dir)
        monkeypatch.setattr(runtime, "_queue_dir", lambda: queue_dir)
        monkeypatch.setattr(runtime, "_signal_dir", lambda: signal_dir)
        monkeypatch.setattr(runtime, "_installed_helper_path", lambda: base_dir / "helper" / "SRPSS_RedditHelper.exe")
        monkeypatch.setattr(
            runtime,
            "resolve_helper_command",
            lambda **kwargs: [str(base_dir / "helper" / "SRPSS_RedditHelper.exe"), "--watch", "--queue", str(queue_dir), "--persistent"],
        )
        monkeypatch.setattr(runtime, "_ensure_run_entry", lambda command: True)
        monkeypatch.setattr(runtime, "_recent_launch_attempt", lambda: True)
        monkeypatch.setattr(runtime, "_process_alive", lambda pid: pid == 999)
        monkeypatch.setattr(runtime, "_terminate_process", lambda pid: terminations.append(pid) or True)
        monkeypatch.setattr(runtime, "_launch_helper", lambda command: launches.append(command) or True)

        assert runtime.ensure_helper_runtime(source="test", persistent=True) is True
        assert terminations == [999]
        assert len(launches) == 1

    def test_ensure_helper_runtime_session_scope_does_not_write_run_entry(self, tmp_path, monkeypatch):
        from core.windows import reddit_helper_runtime as runtime

        base_dir = tmp_path / "base"
        queue_dir = base_dir / "url_queue"
        signal_dir = base_dir / "signals"
        queue_dir.mkdir(parents=True)
        signal_dir.mkdir(parents=True)

        launches: list[list[str]] = []
        registrations: list[list[str]] = []

        monkeypatch.setattr(runtime, "_running_as_system", lambda: False)
        monkeypatch.setattr(runtime, "is_mc_build", lambda: False)
        monkeypatch.setattr(runtime.reddit_helper_bridge, "is_bridge_available", lambda: True)
        monkeypatch.setattr(runtime, "_base_dir", lambda: base_dir)
        monkeypatch.setattr(runtime, "_queue_dir", lambda: queue_dir)
        monkeypatch.setattr(runtime, "_signal_dir", lambda: signal_dir)
        monkeypatch.setattr(runtime, "_installed_helper_path", lambda: base_dir / "helper" / "SRPSS_RedditHelper.exe")
        monkeypatch.setattr(
            runtime,
            "resolve_helper_command",
            lambda **kwargs: [str(base_dir / "helper" / "SRPSS_RedditHelper.exe"), "--watch", "--queue", str(queue_dir), "--owner-pid", "4242"],
        )
        removals: list[str] = []
        monkeypatch.setattr(runtime, "_ensure_run_entry", lambda command: registrations.append(command) or True)
        monkeypatch.setattr(runtime, "remove_helper_run_entry", lambda source="": removals.append(source) or True)
        monkeypatch.setattr(runtime, "_launch_helper", lambda command: launches.append(command) or True)

        assert runtime.ensure_helper_runtime(source="test", persistent=False) is True
        assert registrations == []
        assert removals == ["test"]
        assert len(launches) == 1

    def test_remove_helper_run_entry_deletes_existing_value(self, monkeypatch):
        from core.windows import reddit_helper_runtime as runtime

        class _WinReg:
            HKEY_CURRENT_USER = object()

            def __init__(self):
                self.values = {runtime.RUN_VALUE_NAME: "legacy command"}
                self.deleted: list[str] = []

            def CreateKey(self, root, path):  # noqa: N802, ARG002
                return "key"

            def QueryValueEx(self, key, name):  # noqa: N802, ARG002
                if name not in self.values:
                    raise FileNotFoundError
                return self.values[name], None

            def DeleteValue(self, key, name):  # noqa: N802, ARG002
                self.deleted.append(name)
                self.values.pop(name, None)

        fake_winreg = _WinReg()
        monkeypatch.setitem(__import__("sys").modules, "winreg", fake_winreg)

        assert runtime.remove_helper_run_entry(source="test_cleanup") is True
        assert fake_winreg.deleted == [runtime.RUN_VALUE_NAME]

    def test_ensure_helper_runtime_can_launch_session_scoped_helper_task_from_system_when_allowed(self, tmp_path, monkeypatch):
        from core.windows import reddit_helper_runtime as runtime

        base_dir = tmp_path / "base"
        queue_dir = base_dir / "url_queue"
        signal_dir = base_dir / "signals"
        queue_dir.mkdir(parents=True)
        signal_dir.mkdir(parents=True)

        task_runs: list[str] = []

        monkeypatch.setattr(runtime, "_running_as_system", lambda: True)
        monkeypatch.setattr(runtime, "is_mc_build", lambda: False)
        monkeypatch.setattr(runtime.reddit_helper_bridge, "is_bridge_available", lambda: True)
        monkeypatch.setattr(runtime, "_base_dir", lambda: base_dir)
        monkeypatch.setattr(runtime, "_queue_dir", lambda: queue_dir)
        monkeypatch.setattr(runtime, "_signal_dir", lambda: signal_dir)
        monkeypatch.setattr(runtime, "_run_helper_scheduled_task", lambda *, source: task_runs.append(source) or True)

        assert runtime.ensure_helper_runtime(
            source="system-test",
            persistent=False,
            allow_system=True,
            owner_pid=4242,
        ) is True
        assert task_runs == ["system-test"]

    def test_ensure_helper_runtime_prefers_scheduled_task_for_run_session_sources_even_when_not_system(self, tmp_path, monkeypatch):
        from core.windows import reddit_helper_runtime as runtime

        base_dir = tmp_path / "base"
        queue_dir = base_dir / "url_queue"
        signal_dir = base_dir / "signals"
        queue_dir.mkdir(parents=True)
        signal_dir.mkdir(parents=True)

        task_runs: list[str] = []
        launches: list[list[str]] = []

        monkeypatch.setattr(runtime, "_running_as_system", lambda: False)
        monkeypatch.setattr(runtime, "is_mc_build", lambda: False)
        monkeypatch.setattr(runtime.reddit_helper_bridge, "is_bridge_available", lambda: True)
        monkeypatch.setattr(runtime, "_base_dir", lambda: base_dir)
        monkeypatch.setattr(runtime, "_queue_dir", lambda: queue_dir)
        monkeypatch.setattr(runtime, "_signal_dir", lambda: signal_dir)
        monkeypatch.setattr(runtime, "_run_helper_scheduled_task", lambda *, source: task_runs.append(source) or True)
        monkeypatch.setattr(runtime, "_launch_helper", lambda command: launches.append(command) or True)

        assert runtime.ensure_helper_runtime(
            source="run_session_start",
            persistent=False,
            allow_system=True,
        ) is True
        assert task_runs == ["run_session_start"]
        assert launches == []

    def test_ensure_helper_runtime_still_rejects_persistent_system_launch(self, tmp_path, monkeypatch):
        from core.windows import reddit_helper_runtime as runtime

        base_dir = tmp_path / "base"
        queue_dir = base_dir / "url_queue"
        signal_dir = base_dir / "signals"
        queue_dir.mkdir(parents=True)
        signal_dir.mkdir(parents=True)

        monkeypatch.setattr(runtime, "_running_as_system", lambda: True)
        monkeypatch.setattr(runtime, "is_mc_build", lambda: False)
        monkeypatch.setattr(runtime.reddit_helper_bridge, "is_bridge_available", lambda: True)
        monkeypatch.setattr(runtime, "_base_dir", lambda: base_dir)
        monkeypatch.setattr(runtime, "_queue_dir", lambda: queue_dir)
        monkeypatch.setattr(runtime, "_signal_dir", lambda: signal_dir)

        assert runtime.ensure_helper_runtime(
            source="system-persistent",
            persistent=True,
            allow_system=True,
        ) is False

    def test_refresh_session_ticket_writes_programdata_signal(self, tmp_path, monkeypatch):
        from core.windows import reddit_helper_runtime as runtime

        signal_dir = tmp_path / "signals"
        monkeypatch.setattr(runtime, "_signal_dir", lambda: signal_dir)
        monkeypatch.setattr(runtime.os, "getpid", lambda: 777)

        assert runtime.refresh_session_ticket(source="test", valid_for_seconds=30.0) is True

        payload = json.loads((signal_dir / runtime.SESSION_TICKET_FILE_NAME).read_text(encoding="utf-8"))
        assert payload["source"] == "test"
        assert payload["pid"] == 777
        assert payload["expires_at"] > payload["updated_at"]

    def test_request_session_helper_shutdown_writes_signal_only_for_matching_session_owned_helper(self, tmp_path, monkeypatch):
        from core.windows import reddit_helper_runtime as runtime

        signal_dir = tmp_path / "signals"
        signal_dir.mkdir(parents=True)
        heartbeat = signal_dir / runtime.HEARTBEAT_FILE_NAME
        heartbeat.write_text(
            json.dumps(
                {
                    "updated_at": time.time(),
                    "pid": 999,
                    "persistent": False,
                    "owner_pid": 4242,
                }
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(runtime, "_signal_dir", lambda: signal_dir)
        monkeypatch.setattr(runtime, "_queue_has_pending_entries", lambda: False)
        monkeypatch.setattr(runtime.os, "getpid", lambda: 4242)

        assert runtime.request_session_helper_shutdown(source="test") is True
        shutdown_path = signal_dir / f"{runtime.SESSION_HELPER_SHUTDOWN_PREFIX}4242.json"
        assert shutdown_path.exists()
        payload = json.loads(shutdown_path.read_text(encoding="utf-8"))
        assert payload["owner_pid"] == 4242
        assert payload["source"] == "test"

    def test_request_session_helper_shutdown_skips_persistent_helper(self, tmp_path, monkeypatch):
        from core.windows import reddit_helper_runtime as runtime

        signal_dir = tmp_path / "signals"
        signal_dir.mkdir(parents=True)
        heartbeat = signal_dir / runtime.HEARTBEAT_FILE_NAME
        heartbeat.write_text(
            json.dumps(
                {
                    "updated_at": time.time(),
                    "pid": 999,
                    "persistent": True,
                    "owner_pid": 4242,
                }
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(runtime, "_signal_dir", lambda: signal_dir)
        monkeypatch.setattr(runtime.os, "getpid", lambda: 4242)

        assert runtime.request_session_helper_shutdown(source="test") is False
        shutdown_path = signal_dir / f"{runtime.SESSION_HELPER_SHUTDOWN_PREFIX}4242.json"
        assert not shutdown_path.exists()

    def test_process_alive_uses_windows_kernel_exit_code(self, monkeypatch):
        from core.windows import reddit_helper_runtime as runtime

        class _Kernel32:
            def __init__(self):
                self.closed = []

            def OpenProcess(self, access, inherit, pid):  # noqa: N802, ARG002
                return 123 if pid == 999 else 0

            def GetExitCodeProcess(self, handle, exit_code_ptr):  # noqa: N802
                exit_code_ptr._obj.value = 259 if handle == 123 else 0
                return 1

            def CloseHandle(self, handle):  # noqa: N802
                self.closed.append(handle)
                return 1

        fake_windll = type("Windll", (), {"kernel32": _Kernel32()})()
        monkeypatch.setattr(runtime.ctypes, "windll", fake_windll)

        assert runtime._process_alive(999) is True
        assert runtime._process_alive(111) is False
        assert fake_windll.kernel32.closed == [123]

    def test_launch_helper_uses_detached_windows_spawn_flags(self, tmp_path, monkeypatch):
        from core.windows import reddit_helper_runtime as runtime

        helper_dir = tmp_path / "helper"
        helper_dir.mkdir(parents=True)
        helper_path = helper_dir / "SRPSS_RedditHelper.exe"
        helper_path.write_text("", encoding="utf-8")

        popen_calls: list[tuple[list[str], dict]] = []

        monkeypatch.setattr(runtime.os, "name", "nt")
        monkeypatch.setattr(runtime, "_repo_root", lambda: tmp_path)
        monkeypatch.setattr(runtime, "_log_helper_event", lambda _msg: None)
        monkeypatch.setattr(runtime.subprocess, "DETACHED_PROCESS", 0x00000008, raising=False)
        monkeypatch.setattr(runtime.subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200, raising=False)
        monkeypatch.setattr(runtime.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
        monkeypatch.setattr(
            runtime.subprocess,
            "Popen",
            lambda command, **kwargs: popen_calls.append((command, kwargs)) or object(),
        )

        command = [str(helper_path), "--watch"]

        assert runtime._launch_helper(command) is True
        assert len(popen_calls) == 1

        launched_command, kwargs = popen_calls[0]
        assert launched_command == command
        assert kwargs["cwd"] == str(helper_dir)
        assert kwargs["close_fds"] is True
        assert kwargs["creationflags"] == (0x00000008 | 0x00000200 | 0x08000000)
