from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pythoncom

try:
    import win32com.client  # type: ignore[import]
except ImportError:  # pragma: no cover - optional integration dependency
    win32com = None  # type: ignore[assignment]
else:
    win32com = win32com.client


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
TEMPLATE_PATH = REPO_ROOT / "scripts" / "reddit_helper_task_template.xml"
DEFAULT_TASK_NAME = "SRPSS_RedditHelper"
LEGACY_TASK_NAMES = (r"\SRPSS\RedditHelper", r"SRPSS\RedditHelper")
DEFAULT_PACKAGED_HELPER = (
    REPO_ROOT
    / "release"
    / "reddit_helper"
    / "SRPSS_RedditHelper.exe"
)


def xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def current_user_id() -> str:
    domain = os.environ.get("USERDOMAIN", "").strip()
    username = os.environ.get("USERNAME", "").strip()
    return f"{domain}\\{username}" if domain and username else username


def build_helper_arguments(
    *,
    queue_dir: str,
    log_dir: str,
    signal_dir: str,
    session_ticket: str,
    idle_exit_seconds: int = 20,
) -> str:
    parts = [
        "--watch",
        "--queue",
        f'"{queue_dir}"',
        "--log-dir",
        f'"{log_dir}"',
        "--signal-dir",
        f'"{signal_dir}"',
        "--session-ticket",
        f'"{session_ticket}"',
        "--idle-exit-seconds",
        str(int(idle_exit_seconds)),
    ]
    return " ".join(parts)


def render_task_xml(
    *,
    task_name: str,
    user_id: str,
    command: str,
    arguments: str,
    author: str = "SRPSS Installer",
) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    rendered = template.replace("__AUTHOR__", xml_escape(author))
    rendered = rendered.replace("__TASK_NAME__", xml_escape(task_name))
    rendered = rendered.replace("__USER_ID__", xml_escape(user_id))
    rendered = rendered.replace("__COMMAND__", xml_escape(command))
    rendered = rendered.replace("__ARGUMENTS__", xml_escape(arguments))
    return rendered


def schtasks_exe() -> str:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    return str(windir / "System32" / "schtasks.exe")


def run_schtasks(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    kwargs: dict[str, object] = {
        "capture_output": True,
        "text": True,
        "timeout": timeout,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run([schtasks_exe(), *args], check=False, **kwargs)


def delete_task(task_name: str) -> subprocess.CompletedProcess[str]:
    return run_schtasks(["/Delete", "/TN", task_name, "/F"])


def register_from_xml(*, task_name: str, xml_text: str) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".xml", encoding="utf-8", delete=False) as handle:
        handle.write(xml_text)
        xml_path = Path(handle.name)
    try:
        completed = run_schtasks(["/Create", "/TN", task_name, "/XML", str(xml_path), "/F"])
        return {
            "returncode": completed.returncode,
            "stdout": (completed.stdout or "").strip(),
            "stderr": (completed.stderr or "").strip(),
            "xml_path": str(xml_path),
        }
    finally:
        try:
            xml_path.unlink()
        except OSError:
            pass


def register_from_xml_via_com(*, task_name: str, xml_text: str) -> dict:
    if win32com is None:
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": "win32com.client is unavailable",
        }

    pythoncom.CoInitialize()
    try:
        service = win32com.Dispatch("Schedule.Service")
        service.Connect()
        root = service.GetFolder("\\")
        try:
            root.DeleteTask(task_name, 0)
        except Exception:
            pass
        task = root.RegisterTask(task_name, xml_text, 6, None, None, 3)
        return {
            "returncode": 0,
            "stdout": f"registered {task.Name}",
            "stderr": "",
        }
    except Exception as exc:  # pragma: no cover - exercised by smoke test
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": repr(exc),
        }


def query_task(task_name: str) -> dict:
    completed = run_schtasks(["/Query", "/TN", task_name, "/V", "/FO", "LIST"])
    return {
        "returncode": completed.returncode,
        "stdout": (completed.stdout or "").strip(),
        "stderr": (completed.stderr or "").strip(),
    }


def run_task(task_name: str) -> dict:
    completed = run_schtasks(["/Run", "/TN", task_name])
    return {
        "returncode": completed.returncode,
        "stdout": (completed.stdout or "").strip(),
        "stderr": (completed.stderr or "").strip(),
    }


def smoke_test(task_name: str) -> dict:
    stamp_path = Path(tempfile.gettempdir()) / f"{task_name}_stamp.txt"
    try:
        stamp_path.unlink()
    except OSError:
        pass

    command = str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "cmd.exe")
    arguments = f'/C echo ok>"{stamp_path}"'
    user_id = current_user_id()
    xml_text = render_task_xml(
        task_name=task_name,
        user_id=user_id,
        command=command,
        arguments=arguments,
        author="SRPSS Task Harness",
    )

    delete_task(task_name)
    register_result = register_from_xml_via_com(task_name=task_name, xml_text=xml_text)
    query_result = query_task(task_name)
    run_result = run_task(task_name)

    stamp_exists = False
    for _ in range(20):
        time.sleep(0.25)
        if stamp_path.exists():
            stamp_exists = True
            break

    delete_result = delete_task(task_name)
    try:
        stamp_path.unlink()
    except OSError:
        pass

    return {
        "success": (
            register_result["returncode"] == 0
            and query_result["returncode"] == 0
            and run_result["returncode"] == 0
            and stamp_exists
        ),
        "task_name": task_name,
        "user_id": user_id,
        "register": register_result,
        "query": query_result,
        "run": run_result,
        "delete": {
            "returncode": delete_result.returncode,
            "stdout": (delete_result.stdout or "").strip(),
            "stderr": (delete_result.stderr or "").strip(),
        },
        "stamp_exists": stamp_exists,
    }


def storage_recovery_test() -> dict:
    from core.windows import reddit_helper_bridge as bridge
    from core.windows.reddit_helper_storage import (
        HELPER_LOG_MAX_BYTES,
        HELPER_LOG_SEGMENT_MAX_BYTES,
        append_bounded_log,
    )
    from helpers import reddit_helper_worker as worker

    with tempfile.TemporaryDirectory(prefix="srpss_reddit_recovery_") as temp:
        root = Path(temp)
        queue = root / "url_queue"
        logs = root / "logs"
        signals = root / "helper_signals"
        queue.mkdir()
        signals.mkdir()

        old_bridge_state = (
            bridge._BASE_DIR,
            bridge._QUEUE_DIR,
            bridge._SIGNAL_DIR,
            bridge._SPOOL_READY,
            bridge._SPOOL_LAST_PROBE,
        )
        try:
            bridge._BASE_DIR = root
            bridge._QUEUE_DIR = queue
            bridge._SIGNAL_DIR = signals
            bridge._SPOOL_READY = False
            bridge._SPOOL_LAST_PROBE = 0.0
            (queue / ".bridge_ready").mkdir()
            marker_independent = bridge.enqueue_url(
                "https://www.reddit.com/r/srpss_recovery/?diagnostic=discard",
                source="runtime_harness",
            )
        finally:
            (
                bridge._BASE_DIR,
                bridge._QUEUE_DIR,
                bridge._SIGNAL_DIR,
                bridge._SPOOL_READY,
                bridge._SPOOL_LAST_PROBE,
            ) = old_bridge_state

        pending_tmp = queue / "interrupted.tmp"
        pending_tmp.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "token": "interrupted",
                    "action": "open_url",
                    "url": "https://www.reddit.com/r/srpss_recovery/",
                }
            ),
            encoding="utf-8",
        )
        recovery = worker.reconcile_queue(queue)

        blocked_log_dir = root / "blocked_logs"
        blocked_log_dir.write_text("not a directory", encoding="utf-8")
        with redirect_stderr(StringIO()):
            log_failure_survived = worker.configure_logging(blocked_log_dir, verbose=False) is False

        with patch.object(worker, "open_url", return_value=True), patch.object(
            worker,
            "bring_browser_foreground",
            return_value=True,
        ):
            processed, opened = worker.process_queue(queue, 10, signals)

        diagnostic_log = logs / "bounded.log"
        for _ in range(90):
            append_bounded_log(diagnostic_log, "x" * (16 * 1024))
        log_files = list(logs.glob("bounded.log*"))
        log_sizes = {path.name: path.stat().st_size for path in log_files}
        logs_bounded = bool(log_files) and all(
            size <= HELPER_LOG_SEGMENT_MAX_BYTES for size in log_sizes.values()
        ) and sum(log_sizes.values()) <= HELPER_LOG_MAX_BYTES

        success = all(
            (
                marker_independent,
                recovery["recovered"] == 1,
                log_failure_survived,
                processed == 2,
                opened,
                logs_bounded,
                not list(queue.glob("*.json")),
                len(list(queue.glob("*.receipt"))) == 2,
            )
        )
        return {
            "success": success,
            "marker_independent": marker_independent,
            "recovery": recovery,
            "log_failure_survived": log_failure_survived,
            "processed": processed,
            "opened": opened,
            "log_limit_bytes": HELPER_LOG_MAX_BYTES,
            "log_sizes": log_sizes,
            "receipts": sorted(path.name for path in queue.glob("*.receipt")),
        }


def installed_storage_audit(base_dir: Path | None = None) -> dict:
    """Read-only ACL and disk-bound audit for a packaged Windows installation."""
    if os.name != "nt":
        return {"success": False, "error": "installed storage audit is Windows-only"}

    try:
        import ntsecuritycon
        import win32security
    except ImportError as exc:
        return {"success": False, "error": f"pywin32 security APIs unavailable: {exc}"}

    from core.windows.reddit_helper_storage import HELPER_LOG_MAX_BYTES

    base_dir = base_dir or Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "SRPSS"
    protected = (base_dir, base_dir / "helper", base_dir / "presets", base_dir / "sounds")
    writable = (base_dir / "url_queue", base_dir / "logs", base_dir / "helper_signals")
    broad_sids = {"S-1-1-0", "S-1-5-11", "S-1-5-32-545"}
    system_sid = "S-1-5-18"
    administrators_sid = "S-1-5-32-544"
    try:
        current_user_sid = win32security.ConvertSidToStringSid(
            win32security.LookupAccountName(None, current_user_id())[0]
        )
    except Exception as exc:
        return {"success": False, "error": f"could not resolve current user SID: {exc}"}
    write_mask = (
        ntsecuritycon.FILE_ADD_FILE
        | ntsecuritycon.FILE_ADD_SUBDIRECTORY
        | ntsecuritycon.FILE_WRITE_DATA
        | ntsecuritycon.FILE_APPEND_DATA
        | ntsecuritycon.FILE_WRITE_ATTRIBUTES
        | ntsecuritycon.FILE_WRITE_EA
        | ntsecuritycon.DELETE
        | ntsecuritycon.WRITE_DAC
        | ntsecuritycon.WRITE_OWNER
    )

    acl_rows: dict[str, dict] = {}
    failures: list[str] = []
    for path in (*protected, *writable):
        row = {
            "exists": path.is_dir(),
            "unauthorized_write_sids": [],
            "required_write_sids": [],
            "aces": [],
        }
        if not row["exists"]:
            failures.append(f"missing directory: {path}")
            acl_rows[str(path)] = row
            continue
        try:
            security = win32security.GetFileSecurity(
                str(path),
                win32security.DACL_SECURITY_INFORMATION,
            )
            dacl = security.GetSecurityDescriptorDacl()
            for index in range(dacl.GetAceCount()):
                ace = dacl.GetAce(index)
                access_mask = int(ace[1])
                sid_text = win32security.ConvertSidToStringSid(ace[2])
                row["aces"].append({"sid": sid_text, "mask": access_mask})
                if path in protected and sid_text in broad_sids and access_mask & write_mask:
                    row["unauthorized_write_sids"].append(sid_text)
                if path in protected and sid_text == current_user_sid and access_mask & write_mask:
                    row["unauthorized_write_sids"].append(sid_text)
                if path in writable and sid_text in {
                    system_sid,
                    administrators_sid,
                    current_user_sid,
                } and access_mask & write_mask:
                    row["required_write_sids"].append(sid_text)
        except Exception as exc:
            failures.append(f"ACL read failed for {path}: {exc}")
        row["unauthorized_write_sids"] = sorted(set(row["unauthorized_write_sids"]))
        row["required_write_sids"] = sorted(set(row["required_write_sids"]))
        if row["unauthorized_write_sids"]:
            failures.append(f"unauthorized write grant on protected path: {path}")
        if path in writable:
            missing = {
                system_sid,
                administrators_sid,
                current_user_sid,
            } - set(row["required_write_sids"])
            if missing:
                failures.append(f"required writable principals missing on {path}: {sorted(missing)}")
        acl_rows[str(path)] = row

    log_sizes: dict[str, int] = {}
    log_dir = base_dir / "logs"
    if log_dir.is_dir():
        for path in log_dir.glob("*.log*"):
            try:
                size = path.stat().st_size
                log_sizes[path.name] = size
                if size > HELPER_LOG_MAX_BYTES:
                    failures.append(f"oversized helper log: {path}")
            except OSError as exc:
                failures.append(f"log stat failed for {path}: {exc}")
        for logical_name in ("reddit_helper.log", "scr_helper.log"):
            total_size = sum(
                size
                for name, size in log_sizes.items()
                if name == logical_name or name.startswith(f"{logical_name}.")
            )
            if total_size > HELPER_LOG_MAX_BYTES:
                failures.append(
                    f"helper log retention exceeds {HELPER_LOG_MAX_BYTES} bytes: {logical_name}"
                )

    return {
        "success": not failures,
        "base_dir": str(base_dir),
        "log_limit_bytes": HELPER_LOG_MAX_BYTES,
        "log_sizes": log_sizes,
        "acls": acl_rows,
        "failures": failures,
    }


def packaged_helper_smoke(helper_exe: Path = DEFAULT_PACKAGED_HELPER) -> dict:
    """Run the packaged helper against a disposable queue without opening a browser."""
    from core.windows.reddit_helper_storage import HELPER_LOG_MAX_BYTES

    if os.name != "nt":
        return {"success": False, "error": "packaged helper smoke test is Windows-only"}
    if not helper_exe.is_file():
        return {"success": False, "error": f"helper executable not found: {helper_exe}"}

    with tempfile.TemporaryDirectory(prefix="srpss_packaged_helper_") as temp:
        root = Path(temp)
        queue = root / "url_queue"
        logs = root / "logs"
        signals = root / "helper_signals"
        completion = signals / "settings_complete.ok"
        queue.mkdir()
        signals.mkdir()

        token = f"packaged_{os.getpid()}"
        command = str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "cmd.exe")
        (queue / f"{token}.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "token": token,
                    "timestamp": time.time(),
                    "action": "open_settings",
                    "command": [command, "/D", "/C", "exit", "0"],
                    "completion_token": str(completion),
                    "timeout_seconds": 30,
                    "source": "packaged_helper_smoke",
                }
            ),
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                str(helper_exe),
                "--one-shot",
                "--queue",
                str(queue),
                "--log-dir",
                str(logs),
                "--signal-dir",
                str(signals),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        log_sizes = {
            path.name: path.stat().st_size
            for path in logs.glob("reddit_helper.log*")
            if path.is_file()
        }
        success = all(
            (
                completed.returncode == 0,
                completion.exists(),
                not (queue / f"{token}.json").exists(),
                (queue / f"{token}.receipt").exists(),
                sum(log_sizes.values()) <= HELPER_LOG_MAX_BYTES,
            )
        )
        return {
            "success": success,
            "helper_exe": str(helper_exe),
            "returncode": completed.returncode,
            "completion_written": completion.exists(),
            "receipt_written": (queue / f"{token}.receipt").exists(),
            "log_limit_bytes": HELPER_LOG_MAX_BYTES,
            "log_sizes": log_sizes,
            "stdout": (completed.stdout or "").strip(),
            "stderr": (completed.stderr or "").strip(),
        }


def acl_reconciliation_fixture_test() -> dict:
    """Exercise the installer's ACL command shape against disposable ProgramData-like paths."""
    if os.name != "nt":
        return {"success": False, "error": "ACL fixture test is Windows-only"}

    icacls = str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "icacls.exe")
    current_user = current_user_id()
    if not current_user:
        return {"success": False, "error": "current user identity is unavailable"}

    def run_acl(path: Path, arguments: list[str]) -> dict:
        completed = subprocess.run(
            [icacls, str(path), *arguments],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return {
            "returncode": completed.returncode,
            "stdout": (completed.stdout or "").strip(),
            "stderr": (completed.stderr or "").strip(),
        }

    def apply(path: Path, rights: str) -> list[dict]:
        return [
            run_acl(
                path,
                [
                    "/grant:r",
                    "*S-1-5-18:(OI)(CI)F",
                    "*S-1-5-32-544:(OI)(CI)F",
                    f"{current_user}:(OI)(CI){rights}",
                    "/T",
                    "/Q",
                ],
            ),
            run_acl(
                path,
                [
                    "/inheritance:r",
                    "/remove:g",
                    "*S-1-1-0",
                    "*S-1-5-11",
                    "*S-1-5-32-545",
                    "/T",
                    "/Q",
                ],
            ),
        ]

    with tempfile.TemporaryDirectory(prefix="srpss_acl_fixture_") as temp:
        root = Path(temp) / "SRPSS"
        for relative in ("helper", "presets", "sounds", "url_queue", "logs", "helper_signals"):
            (root / relative).mkdir(parents=True, exist_ok=True)
        pending = root / "url_queue" / "pending.json"
        pending.write_text('{"schema_version":1}', encoding="utf-8")

        setup_result = run_acl(
            root,
            ["/grant", "*S-1-5-32-545:(OI)(CI)M", "/T", "/Q"],
        )
        command_results = [*apply(root, "RX")]
        for relative in ("helper", "presets", "sounds"):
            command_results.extend(apply(root / relative, "RX"))
        for relative in ("url_queue", "logs", "helper_signals"):
            command_results.extend(apply(root / relative, "M"))

        audit = installed_storage_audit(root)
        success = (
            setup_result["returncode"] == 0
            and all(result["returncode"] == 0 for result in command_results)
            and pending.exists()
            and audit["success"]
        )
        result = {
            "success": success,
            "pending_preserved": pending.exists(),
            "setup": setup_result,
            "commands": command_results,
            "audit": audit,
        }
        # The protected fixture intentionally leaves the caller at RX. Restore
        # disposable cleanup authority before TemporaryDirectory removes it.
        cleanup_results = [
            run_acl(path, ["/grant:r", f"{current_user}:F", "/Q"])
            for path in root.rglob("*")
            if path.is_file()
        ]
        cleanup_results.append(run_acl(
            root,
            ["/grant:r", f"{current_user}:(OI)(CI)F", "/T", "/Q"],
        ))
        result["cleanup_acl"] = cleanup_results
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="SRPSS Reddit helper task harness")
    parser.add_argument(
        "--action",
        choices=(
            "smoke-test",
            "render-helper-xml",
            "storage-recovery-test",
            "installed-storage-audit",
            "packaged-helper-smoke",
            "acl-fixture-test",
        ),
        default="smoke-test",
    )
    parser.add_argument("--task-name", default=f"SRPSS_TaskHarness_{os.getpid()}")
    parser.add_argument("--helper-exe")
    parser.add_argument("--queue-dir")
    parser.add_argument("--log-dir")
    parser.add_argument("--signal-dir")
    parser.add_argument("--session-ticket")
    parser.add_argument("--base-dir", type=Path)
    args = parser.parse_args()

    if args.action == "render-helper-xml":
        if not all((args.helper_exe, args.queue_dir, args.log_dir, args.signal_dir, args.session_ticket)):
            parser.error("render-helper-xml requires --helper-exe, --queue-dir, --log-dir, --signal-dir, and --session-ticket")
        print(
            render_task_xml(
                task_name=DEFAULT_TASK_NAME,
                user_id=current_user_id(),
                command=args.helper_exe,
                arguments=build_helper_arguments(
                    queue_dir=args.queue_dir,
                    log_dir=args.log_dir,
                    signal_dir=args.signal_dir,
                    session_ticket=args.session_ticket,
                ),
            )
        )
        return 0

    if args.action == "storage-recovery-test":
        result = storage_recovery_test()
        print(json.dumps(result, indent=2))
        return 0 if result["success"] else 1

    if args.action == "installed-storage-audit":
        result = installed_storage_audit(args.base_dir)
        print(json.dumps(result, indent=2))
        return 0 if result["success"] else 1

    if args.action == "packaged-helper-smoke":
        result = packaged_helper_smoke(Path(args.helper_exe) if args.helper_exe else DEFAULT_PACKAGED_HELPER)
        print(json.dumps(result, indent=2))
        return 0 if result["success"] else 1

    if args.action == "acl-fixture-test":
        result = acl_reconciliation_fixture_test()
        print(json.dumps(result, indent=2))
        return 0 if result["success"] else 1

    result = smoke_test(args.task_name)
    print(json.dumps(result, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
