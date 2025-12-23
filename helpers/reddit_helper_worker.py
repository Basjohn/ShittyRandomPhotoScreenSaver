"""
User-session Reddit helper worker.

This script runs inside the interactive user session (triggered via a
scheduled task).  It drains the ProgramData queue populated by the
Winlogon screensaver build and opens each deferred Reddit URL using the
user's default browser.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
import subprocess
import textwrap

DEFAULT_PROGRAM_DATA = Path(os.getenv("PROGRAMDATA", r"C:\ProgramData"))
DEFAULT_BASE = DEFAULT_PROGRAM_DATA / "SRPSS"
DEFAULT_QUEUE = DEFAULT_BASE / "url_queue"
DEFAULT_LOG_DIR = DEFAULT_BASE / "logs"
DEFAULT_MAX_BATCH = 50
_DEFAULT_TASK_NAME = os.getenv("SRPSS_REDDIT_HELPER_TASK", r"SRPSS\RedditHelper")


def configure_logging(log_dir: Path, verbose: bool) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "reddit_helper.log"

    handlers = [
        logging.FileHandler(log_file, encoding="utf-8"),
    ]
    if verbose:
        handlers.append(logging.StreamHandler(sys.stdout))

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [helper] %(levelname)s - %(message)s",
        handlers=handlers,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SRPSS Reddit helper worker")
    parser.add_argument(
        "--queue",
        type=Path,
        default=DEFAULT_QUEUE,
        help="Queue directory containing deferred URL JSON files",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=DEFAULT_LOG_DIR,
        help="Directory for helper logs",
    )
    parser.add_argument(
        "--max-batch",
        type=int,
        default=DEFAULT_MAX_BATCH,
        help="Maximum number of URLs to process per run",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose console logging",
    )
    parser.add_argument(
        "--register-only",
        action="store_true",
        help="Only register/refresh the scheduled task, then exit",
    )
    return parser.parse_args()


def iter_queue_files(queue_dir: Path):
    for path in sorted(queue_dir.glob("*.json")):
        if path.is_file():
            yield path


def open_url(url: str) -> bool:
    if not url:
        return False
    try:
        os.startfile(url)  # type: ignore[attr-defined]
        return True
    except OSError:
        return False


def process_queue(queue_dir: Path, max_batch: int) -> int:
    processed = 0
    for entry_path in iter_queue_files(queue_dir):
        if processed >= max_batch:
            break
        try:
            data = json.loads(entry_path.read_text(encoding="utf-8"))
            url = data.get("url")
        except Exception as exc:
            logging.warning("Failed to parse %s: %s", entry_path.name, exc)
            entry_path.rename(entry_path.with_suffix(".corrupt"))
            continue

        if not url:
            logging.warning("Queue entry missing URL: %s", entry_path.name)
            entry_path.unlink(missing_ok=True)
            continue

        logging.info("Launching deferred URL: %s", url)
        start = time.perf_counter()
        launched = open_url(url)
        duration = time.perf_counter() - start
        if launched:
            logging.info(
                "Launch succeeded (%.2f ms): %s",
                duration * 1000.0,
                url,
            )
            entry_path.unlink(missing_ok=True)
        else:
            logging.error("Launch failed: %s", url)
            entry_path.rename(entry_path.with_suffix(".retry"))
        processed += 1
    return processed


def main() -> int:
    args = parse_args()
    args.queue.mkdir(parents=True, exist_ok=True)
    configure_logging(args.log_dir, args.verbose)
    helper_path = Path(sys.argv[0]).resolve()
    if args.register_only:
        success = ensure_scheduled_task_registered(helper_path, args.queue, args.log_dir)
        return 0 if success else 1
    try:
        ensure_scheduled_task_registered(helper_path, args.queue, args.log_dir)
    except Exception:
        logging.debug("Scheduled task registration skipped due to error", exc_info=True)

    logging.info("Helper started (queue=%s)", args.queue)
    processed = process_queue(args.queue, args.max_batch)
    logging.info("Helper finished (processed=%d)", processed)
    return 0


def ensure_scheduled_task_registered(helper_exe: Path, queue_dir: Path, log_dir: Path) -> bool:
    if not _DEFAULT_TASK_NAME:
        return False
    if os.getenv("SRPSS_SKIP_TASK_REGISTER"):
        return False
    False
    task_path, _, task_leaf = _DEFAULT_TASK_NAME.rpartition("\\")
    if not task_leaf:
        task_leaf = task_path
        task_path = ""
    if not task_leaf:
        task_leaf = "RedditHelper"
    sanitized_task_path = task_path.strip("\\")
    folder_parts = [part for part in sanitized_task_path.split("\\") if part]
    folder_array_literal = ", ".join(f"'{part}'" for part in folder_parts)
    folder_array_expr = f"@({folder_array_literal})" if folder_parts else "@()"

    helper_literal = helper_exe.as_posix().replace("'", "''")
    queue_literal = queue_dir.as_posix().replace("'", "''")
    log_literal = log_dir.as_posix().replace("'", "''")
    args_literal = f"--queue \"{queue_literal}\" --log-dir \"{log_literal}\""
    description = "SRPSS Reddit helper worker"

    ps_script = textwrap.dedent(
        f"""
        $ErrorActionPreference = 'Stop'
        try {{
            $taskName = '{task_leaf}'
            $taskFolderParts = {folder_array_expr}
            $service = New-Object -ComObject 'Schedule.Service'
            $service.Connect()
            $targetFolder = $service.GetFolder("\\")
            foreach ($part in $taskFolderParts) {{
                if ([string]::IsNullOrWhiteSpace($part)) {{ continue }}
                $normalized = $part.Trim()
                if (-not $normalized) {{ continue }}
                $nextPath = if ($targetFolder.Path -eq "\\") {{ "\\" + $normalized }} else {{ $targetFolder.Path.TrimEnd("\\") + "\\" + $normalized }}
                try {{
                    $targetFolder = $service.GetFolder($nextPath)
                }} catch {{
                    $targetFolder = $targetFolder.CreateFolder($normalized)
                }}
            }}

            $definition = $service.NewTask(0)
            $definition.RegistrationInfo.Description = '{description}'
            $definition.Settings.Enabled = $true
            $definition.Settings.AllowDemandStart = $true
            $definition.Settings.StartWhenAvailable = $true
            $definition.Settings.DisallowStartIfOnBatteries = $false
            $definition.Settings.StopIfGoingOnBatteries = $false
            $definition.Settings.ExecutionTimeLimit = "PT5M"
            $definition.Principal.UserId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
            $definition.Principal.LogonType = 3  # TASK_LOGON_INTERACTIVE_TOKEN
            $definition.Principal.RunLevel = 1   # TASK_RUNLEVEL_HIGHEST
            $definition.Triggers.Clear()

            $action = $definition.Actions.Create(0) # TASK_ACTION_EXEC
            $action.Path = '{helper_literal}'
            $action.Arguments = '{args_literal}'
            $action.WorkingDirectory = '{helper_exe.parent.as_posix().replace("'", "''")}'

            $targetFolder.RegisterTaskDefinition($taskName, $definition, 6, $null, $null, 3, $null) | Out-Null
        }} catch {{
            Write-Output ("TASK_REGISTER_ERROR: " + $_.Exception.Message)
            if ($_.InvocationInfo -and $_.InvocationInfo.PositionMessage) {{
                Write-Output ("TASK_REGISTER_ERROR_POS: " + ($_.InvocationInfo.PositionMessage.Trim()))
            }}
            exit 1
        }}
        """
    ).strip()

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            ps_script,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        logging.debug(
            "Scheduled task registration failed (rc=%s): %s",
            result.returncode,
            message,
        )
        logging.warning(
            "Scheduled task registration failed (rc=%s): %s",
            result.returncode,
            message,
        )
        return False
    logging.info("Scheduled task ensured (%s)", _DEFAULT_TASK_NAME)
    return True


if __name__ == "__main__":
    raise SystemExit(main())
