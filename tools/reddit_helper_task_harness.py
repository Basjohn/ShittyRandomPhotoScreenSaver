from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pythoncom

try:
    import win32com.client  # type: ignore[import]
except ImportError:  # pragma: no cover - optional integration dependency
    win32com = None  # type: ignore[assignment]
else:
    win32com = win32com.client


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = REPO_ROOT / "scripts" / "reddit_helper_task_template.xml"
DEFAULT_TASK_NAME = "SRPSS_RedditHelper"
LEGACY_TASK_NAMES = (r"\SRPSS\RedditHelper", r"SRPSS\RedditHelper")


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


def main() -> int:
    parser = argparse.ArgumentParser(description="SRPSS Reddit helper task harness")
    parser.add_argument(
        "--action",
        choices=("smoke-test", "render-helper-xml"),
        default="smoke-test",
    )
    parser.add_argument("--task-name", default=f"SRPSS_TaskHarness_{os.getpid()}")
    parser.add_argument("--helper-exe")
    parser.add_argument("--queue-dir")
    parser.add_argument("--log-dir")
    parser.add_argument("--signal-dir")
    parser.add_argument("--session-ticket")
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

    result = smoke_test(args.task_name)
    print(json.dumps(result, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
