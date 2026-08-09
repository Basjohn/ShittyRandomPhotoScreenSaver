"""Unified SRPSS build runner for normal and repo-root-venv build workers.

Usage:
    python tools/build_runner.py
    python tools/build_runner.py --mode venv
    python tools/build_runner.py --smoke-test --mode normal

The GUI intentionally uses only the Python standard library. Build workers keep
their existing ownership: normal mode uses ``scripts/*.ps1`` and venv mode uses
``scripts/venv/*.ps1``. Both modes compile the canonical installers in
``scripts/``.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Literal, Sequence

import tkinter as tk
from tkinter import ttk


ModeName = Literal["normal", "venv"]

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from versioning import APP_VERSION  # noqa: E402
from core.visualizer_preset_manifest import (  # noqa: E402
    write_curated_visualizer_preset_manifest,
)

LOG_DIR = REPO_ROOT / "logs"
RELEASE_DIR = REPO_ROOT / "release"
CANONICAL_SCRIPTS_DIR = REPO_ROOT / "scripts"
VENV_SCRIPTS_DIR = CANONICAL_SCRIPTS_DIR / "venv"


def _build_runner_data_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / "SRPSS" / "BuildRunner"


def helper_state_path(repo_root: Path = REPO_ROOT) -> Path:
    repo_key = hashlib.sha256(str(repo_root.resolve()).casefold().encode("utf-8")).hexdigest()[:12]
    return _build_runner_data_dir() / f"reddit_helper_{repo_key}.json"


HELPER_ARTIFACT = RELEASE_DIR / "reddit_helper" / "SRPSS_RedditHelper.exe"
HELPER_STATE_PATH = helper_state_path()

ISCC_CANDIDATES = (
    Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
)

COLORS = {
    "root": "#0d181e",
    "shell_border": "#ffffff",
    "titlebar": "#0c0c0c",
    "panel": "#10191b",
    "panel_alt": "#1f2626",
    "panel_hover": "#263b3a",
    "border": "#8f7950",
    "text": "#f4f0e6",
    "muted": "#c8d4d1",
    "faint": "#7d918e",
    "amber": "#f4c66d",
    "amber_dark": "#d59b42",
    "amber_hover": "#efb65a",
    "green": "#9fc9bd",
    "red": "#ef7f7f",
    "close_hover": "#e81123",
}


WINDOWS_APP_ID = "JaydeVerElst.SRPSS.BuildFoundry"
TASKBAR_TITLE = "Build Foundry"
BASE_WINDOW_SIZE = (820, 670)
BASE_MINIMUM_SIZE = (760, 640)
OUTER_BORDER_DIP = 1.5
PROGRESS_TICK_MS = 24
RUNNER_LOGS_PER_JOB = 10
WINDOW_STYLE_REFRESH_MS = 120


def enable_windows_dpi_awareness() -> str:
    """Enable the strongest DPI mode available before Tk creates any windows."""
    if sys.platform != "win32":
        return "non-windows"

    try:
        user32 = ctypes.windll.user32
        set_context = user32.SetProcessDpiAwarenessContext
        set_context.argtypes = [ctypes.c_void_p]
        set_context.restype = ctypes.c_bool
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 == (HANDLE)-4
        if set_context(ctypes.c_void_p(-4)):
            return "per-monitor-v2"
    except (AttributeError, OSError, ValueError):
        pass

    try:
        shcore = ctypes.windll.shcore
        set_awareness = shcore.SetProcessDpiAwareness
        set_awareness.argtypes = [ctypes.c_int]
        set_awareness.restype = ctypes.c_long
        # PROCESS_PER_MONITOR_DPI_AWARE == 2. S_OK and E_ACCESSDENIED both
        # mean the process already has an awareness mode and must not retry.
        if set_awareness(2) in (0, -2147024891):
            return "per-monitor-v1"
    except (AttributeError, OSError, ValueError):
        pass

    try:
        if ctypes.windll.user32.SetProcessDPIAware():
            return "system-aware"
    except (AttributeError, OSError, ValueError):
        pass
    return "unavailable"


def set_windows_app_user_model_id(app_id: str = WINDOWS_APP_ID) -> None:
    """Give the taskbar button a stable SRPSS identity and icon grouping."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except (AttributeError, OSError, ValueError):
        pass


@dataclass(frozen=True)
class Job:
    key: str
    name: str
    kind: Literal["powershell", "inno"]
    script: Path
    output_dir: Path
    expected_artifact: Path
    default_selected: bool = True


@dataclass
class PreflightResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unavailable_jobs: set[str] = field(default_factory=set)
    pwsh: Path | None = None
    iscc: Path | None = None

    @property
    def ok(self) -> bool:
        return not self.errors and not self.warnings

    def summary(self) -> str:
        if self.errors:
            return f"{len(self.errors)} blocking issue(s), {len(self.warnings)} warning(s)"
        if self.warnings:
            return f"Ready with {len(self.warnings)} warning(s)"
        return "Pre-flight complete — all selected build tools are available"


@dataclass(frozen=True)
class HelperBuildStatus:
    needs_rebuild: bool
    reason: str
    fingerprint: str
    input_count: int


@dataclass(frozen=True)
class JobResult:
    returncode: int
    detail: str
    log_path: Path
    output_path: Path


@dataclass(frozen=True)
class Preferences:
    auto_close: bool = True
    mode: ModeName = "venv"


def normalize_mode(value: str) -> ModeName:
    return "venv" if str(value).strip().lower() == "venv" else "normal"


def jobs_for_mode(mode: ModeName, repo_root: Path = REPO_ROOT) -> tuple[Job, ...]:
    scripts_dir = repo_root / "scripts"
    worker_dir = scripts_dir / "venv" if mode == "venv" else scripts_dir
    release_dir = repo_root / "release"
    installers_dir = release_dir / "installers"
    return (
        Job(
            "standard",
            "Standard Screensaver",
            "powershell",
            worker_dir / "build_nuitka.ps1",
            release_dir / "screensaver",
            release_dir / "screensaver" / "SRPSS.scr",
        ),
        Job(
            "media_center",
            "Media Center",
            "powershell",
            worker_dir / "build_nuitka_mc_onedir.ps1",
            release_dir / "media_center",
            release_dir / "media_center" / "SRPSS_Media_Center.exe",
        ),
        Job(
            "diagnostic",
            "Diagnostic Runtime",
            "powershell",
            scripts_dir / "venv" / "build_nuitka_diagnostic.ps1",
            release_dir / "diagnostic",
            release_dir / "diagnostic" / "SRPSS_Diagnostic.exe",
            default_selected=False,
        ),
        Job(
            "reddit_helper",
            "Reddit Helper",
            "powershell",
            worker_dir / "build_reddit_helper.ps1",
            release_dir / "reddit_helper",
            release_dir / "reddit_helper" / "SRPSS_RedditHelper.exe",
        ),
        Job(
            "standard_installer",
            "Standard Installer",
            "inno",
            scripts_dir / "SRPSS_Installer.iss",
            installers_dir,
            installers_dir / "Setup_SRPSS.exe",
        ),
        Job(
            "media_center_installer",
            "Media Center Installer",
            "inno",
            scripts_dir / "SRPSS_MediaCenter_Installer.iss",
            installers_dir,
            installers_dir / "Setup_SRPSS_Media_Center.exe",
        ),
        Job(
            "diagnostic_installer",
            "Diagnostic Installer",
            "inno",
            scripts_dir / "SRPSS_Diagnostic_Installer.iss",
            installers_dir,
            installers_dir / "Setup_SRPSS_Diagnostic.exe",
            default_selected=False,
        ),
    )


def _find_iscc() -> Path | None:
    override = os.environ.get("SRPSS_ISCC_PATH")
    if override:
        candidate = Path(override)
        if candidate.is_file() and candidate.name.lower() == "iscc.exe":
            return candidate
    return next((path for path in ISCC_CANDIDATES if path.is_file()), None)


def _find_pwsh() -> Path | None:
    resolved = shutil.which("pwsh")
    return Path(resolved) if resolved else None


def run_preflight(mode: ModeName, repo_root: Path = REPO_ROOT) -> PreflightResult:
    result = PreflightResult(pwsh=_find_pwsh(), iscc=_find_iscc())
    jobs = jobs_for_mode(mode, repo_root)

    for job in jobs:
        if not job.script.is_file():
            result.unavailable_jobs.add(job.key)
            if job.default_selected:
                result.errors.append(f"{job.name}: missing {job.script}")

    if result.pwsh is None:
        result.errors.append("PowerShell 7 (pwsh.exe) is not available on PATH")
        result.unavailable_jobs.update(
            job.key for job in jobs if job.kind == "powershell"
        )
    if result.iscc is None:
        result.errors.append("Inno Setup 6 console compiler (ISCC.exe) was not found")
        result.unavailable_jobs.update(job.key for job in jobs if job.kind == "inno")

    if not (repo_root / ".venv").is_dir():
        if mode == "venv":
            result.warnings.append(
                "Repo-root .venv is absent; the venv workers will create it on first build"
            )
        else:
            result.warnings.append(
                "Diagnostic Runtime uses the repo-root venv worker and will create .venv if selected"
            )

    required_assets = (
        repo_root / "SRPSS.ico",
        repo_root / "images" / "LogoBMP.bmp",
        repo_root / "resources" / "tutuogg.ogg",
    )
    for asset in required_assets:
        if not asset.is_file():
            result.errors.append(f"Required build asset is missing: {asset}")

    for job in jobs:
        if job.default_selected and not job.expected_artifact.exists():
            result.warnings.append(f"{job.name}: output does not exist yet")

    return result


def preferences_path() -> Path:
    return _build_runner_data_dir() / "preferences.json"


def load_preferences(path: Path | None = None) -> Preferences:
    target = path or preferences_path()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("preferences root is not an object")
        return Preferences(
            auto_close=bool(payload.get("auto_close", True)),
            mode=normalize_mode(str(payload.get("mode", "venv"))),
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return Preferences()


def save_preferences(preferences: Preferences, path: Path | None = None) -> bool:
    target = path or preferences_path()
    tmp_path = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    payload = {
        "schema_version": 1,
        "auto_close": bool(preferences.auto_close),
        "mode": preferences.mode,
    }
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(target)
        return True
    except OSError:
        return False
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def helper_input_paths(
    mode: ModeName,
    repo_root: Path = REPO_ROOT,
) -> tuple[Path, ...]:
    paths: set[Path] = {
        repo_root / "helpers" / "reddit_helper_worker.py",
        repo_root / "core" / "constants" / "timing.py",
        repo_root / "core" / "logging" / "logger.py",
        repo_root / "core" / "mc.py",
        repo_root / "core" / "windows" / "browser_window_routing.py",
        repo_root / "build_deps" / "requirements_helper.txt",
        repo_root / "tools" / "build_layout.ps1",
        repo_root / "versioning.py",
        repo_root / "SRPSS.ico",
    }
    paths.update((repo_root / "core" / "windows").glob("reddit_helper*.py"))
    helper_job = next(job for job in jobs_for_mode(mode, repo_root) if job.key == "reddit_helper")
    paths.add(helper_job.script)
    return tuple(sorted((path for path in paths if path.is_file()), key=lambda item: str(item).lower()))


def helper_fingerprint(mode: ModeName, repo_root: Path = REPO_ROOT) -> tuple[str, int]:
    digest = hashlib.sha256()
    digest.update(f"schema=1\nmode={mode}\n".encode("utf-8"))
    paths = helper_input_paths(mode, repo_root)
    for path in paths:
        try:
            relative = path.relative_to(repo_root).as_posix()
        except ValueError:
            relative = str(path)
        digest.update(relative.encode("utf-8", errors="replace"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest(), len(paths)


def helper_bundle_fingerprint(bundle_dir: Path) -> tuple[str, int, int] | None:
    if not bundle_dir.is_dir():
        return None
    files = sorted(
        (path for path in bundle_dir.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(bundle_dir).as_posix().casefold(),
    )
    if not files:
        return None

    digest = hashlib.sha256()
    digest.update(b"srpss-reddit-helper-bundle-v1\0")
    total_size = 0
    try:
        for path in files:
            relative = path.relative_to(bundle_dir).as_posix()
            digest.update(relative.encode("utf-8", errors="replace"))
            digest.update(b"\0")
            with path.open("rb") as handle:
                while chunk := handle.read(1024 * 1024):
                    digest.update(chunk)
                    total_size += len(chunk)
            digest.update(b"\0")
    except OSError:
        return None
    return digest.hexdigest(), len(files), total_size


def _load_helper_build_record(state_path: Path = HELPER_STATE_PATH) -> dict:
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def helper_build_status(
    mode: ModeName,
    repo_root: Path = REPO_ROOT,
    *,
    state_path: Path | None = None,
) -> HelperBuildStatus:
    fingerprint, input_count = helper_fingerprint(mode, repo_root)
    artifact = repo_root / "release" / "reddit_helper" / "SRPSS_RedditHelper.exe"
    record_path = state_path or helper_state_path(repo_root)
    record = _load_helper_build_record(record_path)

    if not artifact.is_file():
        return HelperBuildStatus(True, "Output missing — rebuild required", fingerprint, input_count)
    if record.get("schema_version") != 2:
        return HelperBuildStatus(
            True,
            "No trusted build fingerprint — rebuild recommended",
            fingerprint,
            input_count,
        )
    if record.get("mode") != mode:
        return HelperBuildStatus(
            True,
            f"Last helper build used {record.get('mode', 'another')} mode",
            fingerprint,
            input_count,
        )
    if record.get("fingerprint") != fingerprint:
        return HelperBuildStatus(True, "Helper inputs changed — rebuild selected", fingerprint, input_count)
    bundle_record = helper_bundle_fingerprint(artifact.parent)
    if bundle_record is None:
        return HelperBuildStatus(
            True,
            "Helper output is unreadable — rebuild selected",
            fingerprint,
            input_count,
        )
    bundle_hash, file_count, bundle_size = bundle_record
    if (
        record.get("bundle_sha256") != bundle_hash
        or record.get("bundle_file_count") != file_count
        or record.get("bundle_size") != bundle_size
    ):
        return HelperBuildStatus(
            True,
            "Published helper payload changed — rebuild selected",
            fingerprint,
            input_count,
        )
    return HelperBuildStatus(False, "Helper inputs unchanged — rebuild optional", fingerprint, input_count)


def record_helper_build(
    mode: ModeName,
    fingerprint: str,
    artifact: Path = HELPER_ARTIFACT,
    state_path: Path = HELPER_STATE_PATH,
) -> bool:
    if not artifact.is_file():
        return False
    bundle_record = helper_bundle_fingerprint(artifact.parent)
    if bundle_record is None:
        return False
    bundle_hash, file_count, bundle_size = bundle_record
    payload = {
        "schema_version": 2,
        "mode": mode,
        "fingerprint": fingerprint,
        "artifact": str(artifact),
        "artifact_size": artifact.stat().st_size,
        "bundle_sha256": bundle_hash,
        "bundle_file_count": file_count,
        "bundle_size": bundle_size,
        "recorded_at": time.time(),
    }
    tmp_path = state_path.with_name(f".{state_path.name}.{os.getpid()}.tmp")
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(state_path)
        return True
    except OSError:
        return False
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def stamp_iss_version(path: Path, version: str = APP_VERSION) -> None:
    text = path.read_text(encoding="utf-8")
    updated = re.sub(
        r"^(AppVersion|VersionInfoVersion)=.*$",
        lambda match: f"{match.group(1)}={version}",
        text,
        flags=re.MULTILINE,
    )
    if updated != text:
        path.write_text(updated, encoding="utf-8")


def _windows_subprocess_kwargs() -> dict:
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 6
    return {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
        "startupinfo": startupinfo,
    }


def _safe_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "job"


def prune_build_runner_logs(
    log_dir: Path = LOG_DIR,
    *,
    job_key: str | None = None,
    keep: int = RUNNER_LOGS_PER_JOB,
) -> None:
    """Keep a bounded number of runner-owned logs per build job."""
    if keep < 0 or not log_dir.is_dir():
        return

    matcher = re.compile(
        r"^build_runner_(?P<job>.+)_\d{8}_\d{6}\.log$",
        flags=re.IGNORECASE,
    )
    requested_job = _safe_slug(job_key) if job_key is not None else None
    grouped: dict[str, list[Path]] = {}
    try:
        candidates = tuple(log_dir.glob("build_runner_*.log"))
    except OSError:
        return

    for path in candidates:
        match = matcher.match(path.name)
        if match is None:
            continue
        group = match.group("job").casefold()
        if requested_job is not None and group != requested_job.casefold():
            continue
        grouped.setdefault(group, []).append(path)

    for paths in grouped.values():
        def modified(path: Path) -> float:
            try:
                return path.stat().st_mtime
            except OSError:
                return 0.0

        paths.sort(key=modified, reverse=True)
        for stale_path in paths[keep:]:
            try:
                stale_path.unlink()
            except OSError:
                pass


def run_job(job: Job, preflight: PreflightResult, log_dir: Path = LOG_DIR) -> JobResult:
    log_dir.mkdir(parents=True, exist_ok=True)
    # Leave room for the log about to be created, yielding ten retained logs
    # for each runner job rather than ten old logs plus the current one.
    prune_build_runner_logs(
        log_dir,
        job_key=job.key,
        keep=max(0, RUNNER_LOGS_PER_JOB - 1),
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"build_runner_{_safe_slug(job.key)}_{timestamp}.log"

    if job.kind == "powershell":
        if preflight.pwsh is None:
            return JobResult(1, "PowerShell 7 unavailable", log_path, job.output_dir)
        command = [
            str(preflight.pwsh),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(job.script),
        ]
    else:
        if preflight.iscc is None:
            return JobResult(1, "ISCC.exe unavailable", log_path, job.output_dir)
        try:
            stamp_iss_version(job.script)
        except OSError as exc:
            return JobResult(1, f"Version stamp failed: {exc}", log_path, job.output_dir)
        command = [str(preflight.iscc), "/Qp", str(job.script)]

    try:
        with log_path.open("wb") as log_handle:
            header = (
                f"SRPSS Build Runner {APP_VERSION}\n"
                f"Job: {job.name}\n"
                f"Command: {subprocess.list2cmdline(command)}\n"
                f"Started: {datetime.now().isoformat(timespec='seconds')}\n"
                f"{'=' * 72}\n"
            )
            log_handle.write(header.encode("utf-8", errors="replace"))
            log_handle.flush()
            completed = subprocess.run(
                command,
                cwd=str(REPO_ROOT),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                check=False,
                **_windows_subprocess_kwargs(),
            )
            returncode = completed.returncode
            artifact_missing = returncode == 0 and not job.expected_artifact.is_file()
            if artifact_missing:
                returncode = 1
            footer = (
                f"\n{'=' * 72}\n"
                f"Process exit code: {completed.returncode}\n"
                f"Runner exit code: {returncode}\n"
                f"Expected artifact: {job.expected_artifact}\n"
                f"Artifact present: {job.expected_artifact.is_file()}\n"
                f"Finished: {datetime.now().isoformat(timespec='seconds')}\n"
            )
            log_handle.write(footer.encode("utf-8", errors="replace"))
        if artifact_missing:
            detail = "Compiler exited 0, but the expected artifact is missing"
        else:
            detail = "Completed" if returncode == 0 else f"Failed (exit {returncode})"
        return JobResult(returncode, detail, log_path, job.output_dir)
    except OSError as exc:
        return JobResult(1, f"Launch failed: {exc}", log_path, job.output_dir)


def open_local_path(path: Path) -> bool:
    target = path if path.exists() else path.parent
    try:
        if os.name == "nt":
            os.startfile(str(target))  # type: ignore[attr-defined]
        else:
            import webbrowser

            webbrowser.open(target.resolve().as_uri())
        return True
    except OSError:
        return False


class LinkLabel(tk.Label):
    def __init__(self, parent: tk.Misc, text: str, command) -> None:  # noqa: ANN001
        super().__init__(
            parent,
            text=text,
            bg=COLORS["panel"],
            fg=COLORS["amber"],
            activebackground=COLORS["panel"],
            activeforeground=COLORS["amber_hover"],
            cursor="hand2",
            font=("Segoe UI", 9, "underline"),
            padx=4,
        )
        self._command = command
        self.bind("<Button-1>", lambda _event: self._command())
        self.bind("<Enter>", lambda _event: self.configure(fg=COLORS["amber_hover"]))
        self.bind("<Leave>", lambda _event: self.configure(fg=COLORS["amber"]))


class FoundryCheckbutton(tk.Frame):
    """Large, DPI-aware checkbox with a deterministic vector check mark.

    ttk's theme indicator is intentionally not used here: under Windows DPI
    scaling the Clam indicator bitmap can be enlarged without scaling the mark
    cleanly, which is what produced the malformed checked glyph in Build Foundry.
    """

    def __init__(
        self,
        parent: tk.Misc,
        *,
        text: str,
        variable: tk.BooleanVar,
        command=None,  # noqa: ANN001
        background: str = COLORS["panel"],
        indicator_size: int = 24,
        gap: int = 6,
        font=("Segoe UI", 10, "bold"),
    ) -> None:
        super().__init__(
            parent,
            bg=background,
            bd=0,
            highlightthickness=0,
            takefocus=1,
            cursor="hand2",
        )
        self._variable = variable
        self._command = command
        self._background = background
        self._indicator_size = max(18, int(indicator_size))
        self._disabled = False
        self._trace_name: str | None = None

        self._indicator = tk.Canvas(
            self,
            width=self._indicator_size,
            height=self._indicator_size,
            bg=background,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self._indicator.pack(side="left", padx=(0, max(1, int(gap))))
        self._label = tk.Label(
            self,
            text=text,
            bg=background,
            fg=COLORS["text"],
            font=font,
            anchor="w",
            padx=0,
            pady=0,
            cursor="hand2",
        )
        self._label.pack(side="left")

        for widget in (self, self._indicator, self._label):
            widget.bind("<Button-1>", self._on_click)
        self.bind("<space>", self._on_keyboard_toggle)
        self.bind("<Return>", self._on_keyboard_toggle)
        self.bind("<Destroy>", self._on_destroy, add="+")

        self._trace_name = self._variable.trace_add("write", self._on_variable_changed)
        self._render()

    def _on_click(self, _event: tk.Event) -> str:
        if self._disabled:
            return "break"
        self.focus_set()
        self._toggle()
        return "break"

    def _on_keyboard_toggle(self, _event: tk.Event) -> str:
        if not self._disabled:
            self._toggle()
        return "break"

    def _toggle(self) -> None:
        self._variable.set(not bool(self._variable.get()))
        if self._command is not None:
            self._command()

    def _on_variable_changed(self, *_args) -> None:  # noqa: ANN002
        self._render()

    def _on_destroy(self, event: tk.Event) -> None:
        if event.widget is not self or self._trace_name is None:
            return
        try:
            self._variable.trace_remove("write", self._trace_name)
        except tk.TclError:
            pass
        self._trace_name = None

    def _render(self) -> None:
        size = self._indicator_size
        selected = bool(self._variable.get())
        disabled = self._disabled
        outline = COLORS["faint"] if disabled else COLORS["amber"]
        fill = COLORS["panel_alt"] if disabled and selected else (
            COLORS["amber_dark"] if selected else self._background
        )
        check_color = COLORS["muted"] if disabled else COLORS["text"]

        self._indicator.delete("all")
        border_width = max(2, int(round(size * 0.085)))
        inset = max(1, border_width // 2)
        self._indicator.create_rectangle(
            inset,
            inset,
            size - inset - 1,
            size - inset - 1,
            fill=fill,
            outline=outline,
            width=border_width,
        )
        if selected:
            self._indicator.create_line(
                round(size * 0.22),
                round(size * 0.52),
                round(size * 0.42),
                round(size * 0.72),
                round(size * 0.79),
                round(size * 0.29),
                fill=check_color,
                width=max(2, int(round(size * 0.11))),
                capstyle=tk.ROUND,
                joinstyle=tk.ROUND,
            )

        text_color = COLORS["faint"] if disabled else COLORS["text"]
        cursor = "arrow" if disabled else "hand2"
        self.configure(cursor=cursor)
        self._indicator.configure(cursor=cursor)
        self._label.configure(fg=text_color, cursor=cursor)

    def state(self, statespec: Sequence[str] | str | None = None) -> tuple[str, ...]:
        """Small ttk-compatible state surface used by BuildRunnerApp."""
        if statespec is None:
            states: list[str] = []
            if self._disabled:
                states.append("disabled")
            if bool(self._variable.get()):
                states.append("selected")
            return tuple(states)

        tokens = (statespec,) if isinstance(statespec, str) else tuple(statespec)
        for token in tokens:
            if token == "disabled":
                self._disabled = True
            elif token == "!disabled":
                self._disabled = False
            elif token == "selected":
                self._variable.set(True)
            elif token == "!selected":
                self._variable.set(False)
        self._render()
        return self.state()


@dataclass
class JobWidgets:
    frame: tk.Frame
    variable: tk.BooleanVar
    checkbox: FoundryCheckbutton
    status: tk.Label
    log_link: LinkLabel
    output_link: LinkLabel


class BuildRunnerApp:
    AUTO_CLOSE_MS = 3000

    def __init__(self, root: tk.Tk, *, initial_mode: ModeName | None = None) -> None:
        self._root = root
        self._events: queue.Queue[tuple] = queue.Queue()
        self._running = False
        self._auto_close_after_id: str | None = None
        self._drag_state: tuple[int, int, int, int] | None = None
        self._preflight = PreflightResult()
        self._jobs: tuple[Job, ...] = ()
        self._job_widgets: dict[str, JobWidgets] = {}
        self._progress_total = 0
        self._progress_completed = 0
        self._preferences = load_preferences()
        self._dpi_scale = self._initial_dpi_scale()
        self._shell: tk.Frame | None = None
        self._initial_show_complete = False
        selected_mode = initial_mode or self._preferences.mode
        self._mode_var = tk.StringVar(value=selected_mode)
        self._auto_close_var = tk.BooleanVar(value=self._preferences.auto_close)

        self._configure_window()
        self._configure_styles()
        self._build_ui()
        self._apply_mode(selected_mode, persist=False)
        self._poll_events()
        self._root.after_idle(self._show_initial_window)

    def _initial_dpi_scale(self) -> float:
        try:
            return max(1.0, float(self._root.winfo_fpixels("1i")) / 96.0)
        except (tk.TclError, ValueError, TypeError):
            return 1.0

    def _dip(self, value: float) -> int:
        return max(1, int(round(value * self._dpi_scale)))

    def _configure_window(self) -> None:
        # Keep this as a normal unowned Windows top-level so Explorer owns a
        # stable taskbar button. Native frame styles are stripped after mapping
        # instead of using Tk's override-redirect mode, which can de-register
        # and recreate the taskbar entry.
        self._root.title(TASKBAR_TITLE)
        width = self._dip(BASE_WINDOW_SIZE[0])
        height = self._dip(BASE_WINDOW_SIZE[1])
        minimum_width = self._dip(BASE_MINIMUM_SIZE[0])
        minimum_height = self._dip(BASE_MINIMUM_SIZE[1])
        self._root.geometry(f"{width}x{height}")
        self._root.minsize(minimum_width, minimum_height)
        self._root.configure(bg=COLORS["shell_border"])
        self._root.overrideredirect(False)
        self._root.protocol("WM_DELETE_WINDOW", self._request_close)
        self._root.bind("<Map>", self._on_window_mapped)
        self._root.bind("<Alt-F4>", lambda _event: self._request_close())
        # Child widgets include the toplevel in their default bindtags, so this
        # single handler also covers blank space in dynamically created rows.
        self._root.bind("<ButtonPress-1>", self._on_drag_surface_press, add="+")
        self._root.bind("<B1-Motion>", self._drag_window_fallback, add="+")
        self._root.bind("<ButtonRelease-1>", self._end_drag_fallback, add="+")
        self._root.bind("<FocusOut>", self._cancel_drag, add="+")
        self._root.bind("<Unmap>", self._cancel_drag, add="+")

    def _native_toplevel_hwnd(self) -> int | None:
        if sys.platform != "win32":
            return None
        try:
            self._root.update_idletasks()
            child_hwnd = int(self._root.winfo_id())
            user32 = ctypes.windll.user32
            user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            user32.GetAncestor.restype = ctypes.c_void_p
            root_hwnd = int(user32.GetAncestor(child_hwnd, 2) or 0)  # GA_ROOT
            if root_hwnd:
                return root_hwnd
            parent_hwnd = int(user32.GetParent(child_hwnd) or 0)
            return parent_hwnd or child_hwnd
        except (AttributeError, OSError, tk.TclError, TypeError, ValueError):
            return None

    def _apply_windows_window_styles(self) -> None:
        """Keep a native taskbar window while removing only the Windows frame."""
        hwnd = self._native_toplevel_hwnd()
        if hwnd is None:
            return

        try:
            user32 = ctypes.windll.user32
            get_window_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
            set_window_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
            get_window_long.argtypes = [ctypes.c_void_p, ctypes.c_int]
            get_window_long.restype = ctypes.c_ssize_t
            set_window_long.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
            set_window_long.restype = ctypes.c_ssize_t
            user32.SetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
            user32.SetWindowTextW.restype = ctypes.c_bool

            self._root.title(TASKBAR_TITLE)
            child_hwnd = int(self._root.winfo_id())
            user32.SetWindowTextW(hwnd, TASKBAR_TITLE)
            if child_hwnd and child_hwnd != hwnd:
                user32.SetWindowTextW(child_hwnd, TASKBAR_TITLE)

            gwl_style = -16
            gwl_exstyle = -20
            ws_caption = 0x00C00000
            ws_thickframe = 0x00040000
            ws_maximizebox = 0x00010000
            ws_ex_toolwindow = 0x00000080
            ws_ex_appwindow = 0x00040000

            style = int(get_window_long(hwnd, gwl_style))
            style &= ~(ws_caption | ws_thickframe | ws_maximizebox)
            set_window_long(hwnd, gwl_style, style)

            exstyle = int(get_window_long(hwnd, gwl_exstyle))
            exstyle = (exstyle & ~ws_ex_toolwindow) | ws_ex_appwindow
            set_window_long(hwnd, gwl_exstyle, exstyle)

            swp_nosize = 0x0001
            swp_nomove = 0x0002
            swp_nozorder = 0x0004
            swp_noactivate = 0x0010
            swp_framechanged = 0x0020
            user32.SetWindowPos(
                hwnd,
                0,
                0,
                0,
                0,
                0,
                swp_nosize
                | swp_nomove
                | swp_nozorder
                | swp_noactivate
                | swp_framechanged,
            )
        except (AttributeError, OSError, TypeError, ValueError, tk.TclError):
            return

    def _show_initial_window(self) -> None:
        """Map once as a normal app window, then remove only its native frame."""
        if self._initial_show_complete:
            return

        if sys.platform != "win32":
            self._root.deiconify()
            self._initial_show_complete = True
            return

        try:
            # Alpha hides the brief native-frame setup without withdrawing the
            # window again. The single map is what gives Explorer a stable
            # taskbar button from startup onward.
            self._root.attributes("-alpha", 0.0)
            self._root.deiconify()
            self._root.update_idletasks()
            self._apply_windows_window_styles()
            self._root.attributes("-alpha", 1.0)
            self._root.lift()
            self._root.after(WINDOW_STYLE_REFRESH_MS, self._apply_windows_window_styles)
        except tk.TclError:
            self._root.deiconify()
        finally:
            self._initial_show_complete = True

    def _on_window_mapped(self, _event: tk.Event | None = None) -> None:
        if sys.platform == "win32":
            self._root.after_idle(self._apply_windows_window_styles)

    def _configure_styles(self) -> None:
        style = ttk.Style(self._root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Foundry.TButton",
            background=COLORS["panel_alt"],
            foreground=COLORS["text"],
            bordercolor=COLORS["border"],
            padding=(12, 7),
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "Foundry.TButton",
            background=[("active", COLORS["panel_hover"]), ("disabled", COLORS["panel"])],
            foreground=[("disabled", COLORS["faint"])],
        )
        style.configure(
            "Primary.TButton",
            background=COLORS["amber_dark"],
            foreground="#11191a",
            bordercolor=COLORS["amber"],
            padding=(18, 8),
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Primary.TButton",
            background=[("active", COLORS["amber_hover"]), ("disabled", COLORS["panel_alt"])],
            foreground=[("disabled", COLORS["faint"])],
        )
        style.configure(
            "Foundry.Horizontal.TProgressbar",
            troughcolor=COLORS["panel_alt"],
            background=COLORS["amber_dark"],
            bordercolor=COLORS["border"],
            lightcolor=COLORS["amber"],
            darkcolor=COLORS["amber_dark"],
            thickness=9,
        )

    def _build_ui(self) -> None:
        self._shell = tk.Frame(
            self._root,
            bg=COLORS["root"],
            bd=0,
            highlightbackground=COLORS["shell_border"],
            highlightcolor=COLORS["shell_border"],
            highlightthickness=self._dip(OUTER_BORDER_DIP),
        )
        self._shell.pack(fill="both", expand=True)
        self._build_titlebar()
        body = tk.Frame(self._shell, bg=COLORS["root"], padx=24, pady=18)
        body.pack(fill="both", expand=True)

        tk.Label(
            body,
            text="BUILD FOUNDRY",
            bg=COLORS["root"],
            fg=COLORS["amber"],
            font=("Jost", 23, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            body,
            text=(
                "Build Normal or repo-root-venv artifacts from one place. "
                "Workers stay sequential so build products cannot collide. "
                "Installer-only selections package the existing canonical release payload."
            ),
            bg=COLORS["root"],
            fg=COLORS["muted"],
            font=("Segoe UI", 10),
            justify="left",
            anchor="w",
            wraplength=750,
        ).pack(fill="x", pady=(2, 14))

        controls = tk.Frame(body, bg=COLORS["root"])
        controls.pack(fill="x", pady=(0, 12))
        tk.Label(
            controls,
            text="BUILD ENVIRONMENT",
            bg=COLORS["root"],
            fg=COLORS["faint"],
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left", padx=(0, 10))
        self._mode_buttons: list[tk.Radiobutton] = []
        for label, mode in (("NORMAL", "normal"), ("REPO VENV", "venv")):
            button = tk.Radiobutton(
                controls,
                text=label,
                value=mode,
                variable=self._mode_var,
                command=self._on_mode_changed,
                indicatoron=False,
                selectcolor=COLORS["amber_dark"],
                bg=COLORS["panel_alt"],
                fg=COLORS["text"],
                activebackground=COLORS["panel_hover"],
                activeforeground=COLORS["amber"],
                font=("Segoe UI", 9, "bold"),
                relief="flat",
                bd=0,
                padx=14,
                pady=6,
                cursor="hand2",
            )
            button.pack(side="left", padx=(0, 6))
            self._mode_buttons.append(button)

        LinkLabel(controls, "Logs folder", lambda: open_local_path(LOG_DIR)).pack(
            side="right", padx=(8, 0)
        )
        LinkLabel(controls, "Release folder", lambda: open_local_path(RELEASE_DIR)).pack(
            side="right"
        )

        self._preflight_panel = tk.Frame(
            body,
            bg=COLORS["panel_alt"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            padx=12,
            pady=9,
        )
        self._preflight_panel.pack(fill="x", pady=(0, 10))
        self._preflight_label = tk.Label(
            self._preflight_panel,
            text="Running pre-flight checks…",
            bg=COLORS["panel_alt"],
            fg=COLORS["green"],
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        )
        self._preflight_label.pack(fill="x")
        self._preflight_detail = tk.Label(
            self._preflight_panel,
            text="",
            bg=COLORS["panel_alt"],
            fg=COLORS["muted"],
            font=("Segoe UI", 8),
            anchor="w",
            justify="left",
            wraplength=740,
        )
        self._preflight_detail.pack(fill="x", pady=(2, 0))

        self._jobs_panel = tk.Frame(
            body,
            bg=COLORS["panel"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        self._jobs_panel.pack(fill="x")

        self._helper_badge = tk.Label(
            body,
            text="Checking Reddit helper inputs…",
            bg=COLORS["root"],
            fg=COLORS["amber"],
            font=("Segoe UI", 9),
            anchor="w",
        )
        self._helper_badge.pack(fill="x", pady=(7, 0))

        progress_panel = tk.Frame(body, bg=COLORS["root"])
        progress_panel.pack(fill="x", pady=(10, 0))
        progress_header = tk.Frame(progress_panel, bg=COLORS["root"])
        progress_header.pack(fill="x", pady=(0, 4))
        tk.Label(
            progress_header,
            text="BUILD PROGRESS",
            bg=COLORS["root"],
            fg=COLORS["faint"],
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left")
        self._progress_detail = tk.Label(
            progress_header,
            text="Ready",
            bg=COLORS["root"],
            fg=COLORS["muted"],
            font=("Segoe UI", 8),
        )
        self._progress_detail.pack(side="right")
        self._progress_bar = ttk.Progressbar(
            progress_panel,
            orient="horizontal",
            mode="determinate",
            maximum=1,
            value=0,
            style="Foundry.Horizontal.TProgressbar",
        )
        self._progress_bar.pack(fill="x")

        footer = tk.Frame(body, bg=COLORS["root"])
        footer.pack(fill="x", pady=(12, 0))
        self._footer_status = tk.Label(
            footer,
            text="Ready.",
            bg=COLORS["root"],
            fg=COLORS["green"],
            font=("Segoe UI", 9),
            anchor="w",
        )
        self._footer_status.pack(side="left", fill="x", expand=True)

        self._auto_close_checkbox = FoundryCheckbutton(
            footer,
            text="Auto-close after full success",
            variable=self._auto_close_var,
            command=self._persist_preferences,
            background=COLORS["root"],
            indicator_size=self._dip(24),
            gap=self._dip(6),
        )
        self._auto_close_checkbox.pack(side="right", padx=(10, 0))
        self._start_button = ttk.Button(
            footer,
            text="START SELECTED",
            command=self._on_start,
            style="Primary.TButton",
        )
        self._start_button.pack(side="right", padx=(10, 0))
        self._select_none_button = ttk.Button(
            footer,
            text="None",
            command=lambda: self._set_all(False),
            style="Foundry.TButton",
        )
        self._select_none_button.pack(side="right", padx=(6, 0))
        self._select_all_button = ttk.Button(
            footer,
            text="All",
            command=lambda: self._set_all(True),
            style="Foundry.TButton",
        )
        self._select_all_button.pack(side="right", padx=(6, 0))

    def _build_titlebar(self) -> None:
        if self._shell is None:
            raise RuntimeError("Build shell must exist before the titlebar")
        titlebar = tk.Frame(self._shell, bg=COLORS["titlebar"], height=40)
        titlebar.pack(fill="x")
        titlebar.pack_propagate(False)
        icon_path = REPO_ROOT / "SRPSS.ico"
        try:
            if icon_path.is_file():
                self._root.iconbitmap(default=str(icon_path))
        except tk.TclError:
            pass

        # With side="right", the first packed widget owns the outermost edge.
        # Pack Close first, then Minimize, so Windows-standard ordering is kept.
        close = tk.Button(
            titlebar,
            text="×",
            command=self._request_close,
            bg=COLORS["titlebar"],
            fg=COLORS["text"],
            activebackground=COLORS["close_hover"],
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            width=5,
            font=("Segoe UI", 12),
            cursor="hand2",
        )
        close.pack(side="right", fill="y")
        minimize = tk.Button(
            titlebar,
            text="—",
            command=self._minimize,
            bg=COLORS["titlebar"],
            fg=COLORS["text"],
            activebackground="#3e3e3e",
            activeforeground=COLORS["text"],
            relief="flat",
            bd=0,
            width=5,
            cursor="hand2",
        )
        minimize.pack(side="right", fill="y")

        title = tk.Label(
            titlebar,
            text=f"  SRPSS BUILD FOUNDRY   ·   v{APP_VERSION}",
            bg=COLORS["titlebar"],
            fg=COLORS["text"],
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        )
        title.pack(side="left", fill="both", expand=True)

    @staticmethod
    def _is_drag_surface(widget: tk.Misc) -> bool:
        if isinstance(widget, LinkLabel):
            return False
        interactive = (
            tk.Button,
            tk.Radiobutton,
            tk.Checkbutton,
            tk.Entry,
            tk.Text,
            tk.Listbox,
            tk.Scale,
            tk.Scrollbar,
            ttk.Button,
            ttk.Checkbutton,
            ttk.Radiobutton,
            ttk.Entry,
            ttk.Combobox,
            ttk.Scale,
            ttk.Scrollbar,
            ttk.Progressbar,
            FoundryCheckbutton,
        )
        if isinstance(widget, interactive):
            return False
        return isinstance(widget, (tk.Tk, tk.Frame, tk.Label, ttk.Frame, ttk.Label))

    def _on_drag_surface_press(self, event: tk.Event) -> str | None:
        if not self._is_drag_surface(event.widget):
            self._drag_state = None
            return None

        if sys.platform == "win32":
            hwnd = self._native_toplevel_hwnd()
            if hwnd is None:
                return None
            try:
                class _RECT(ctypes.Structure):
                    _fields_ = [
                        ("left", ctypes.c_long),
                        ("top", ctypes.c_long),
                        ("right", ctypes.c_long),
                        ("bottom", ctypes.c_long),
                    ]

                user32 = ctypes.windll.user32
                user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(_RECT)]
                user32.GetWindowRect.restype = ctypes.c_bool
                rect = _RECT()
                if not user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect)):
                    return None
                self._drag_state = (
                    int(event.x_root),
                    int(event.y_root),
                    int(rect.left),
                    int(rect.top),
                )
                return "break"
            except (AttributeError, OSError, TypeError, ValueError):
                self._drag_state = None
                return None

        self._drag_state = (
            int(event.x_root),
            int(event.y_root),
            int(self._root.winfo_x()),
            int(self._root.winfo_y()),
        )
        return "break"

    def _drag_window_fallback(self, event: tk.Event) -> str | None:
        if self._drag_state is None:
            return None

        start_x, start_y, window_x, window_y = self._drag_state
        target_x = window_x + int(event.x_root) - start_x
        target_y = window_y + int(event.y_root) - start_y

        if sys.platform == "win32":
            hwnd = self._native_toplevel_hwnd()
            if hwnd is None:
                return None
            try:
                user32 = ctypes.windll.user32
                user32.SetWindowPos.argtypes = [
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_int,
                    ctypes.c_int,
                    ctypes.c_int,
                    ctypes.c_int,
                    ctypes.c_uint,
                ]
                user32.SetWindowPos.restype = ctypes.c_bool
                swp_nosize = 0x0001
                swp_nozorder = 0x0004
                swp_noactivate = 0x0010
                user32.SetWindowPos(
                    ctypes.c_void_p(hwnd),
                    None,
                    target_x,
                    target_y,
                    0,
                    0,
                    swp_nosize | swp_nozorder | swp_noactivate,
                )
                return "break"
            except (AttributeError, OSError, TypeError, ValueError):
                return None

        self._root.geometry(f"+{target_x}+{target_y}")
        return "break"

    def _end_drag_fallback(self, _event: tk.Event) -> str | None:
        if self._drag_state is None:
            return None
        self._drag_state = None
        return "break"

    def _cancel_drag(self, _event: tk.Event | None = None) -> None:
        self._drag_state = None

    def _minimize(self) -> None:
        self._root.iconify()

    def _request_close(self) -> None:
        if self._running:
            self._footer_status.configure(
                text="A build is running. Let it finish before closing the runner.",
                fg=COLORS["amber"],
            )
            return
        self._cancel_auto_close()
        self._root.destroy()

    def _cancel_auto_close(self) -> None:
        if self._auto_close_after_id is None:
            return
        try:
            self._root.after_cancel(self._auto_close_after_id)
        except tk.TclError:
            pass
        self._auto_close_after_id = None

    def _auto_close_if_idle(self) -> None:
        self._auto_close_after_id = None
        if not self._running and self._auto_close_var.get():
            self._root.destroy()

    def _persist_preferences(self) -> None:
        if not self._auto_close_var.get():
            self._cancel_auto_close()
        preferences = Preferences(
            auto_close=bool(self._auto_close_var.get()),
            mode=normalize_mode(self._mode_var.get()),
        )
        if not save_preferences(preferences):
            self._footer_status.configure(
                text="Could not persist Build Foundry preferences.",
                fg=COLORS["red"],
            )

    def _on_mode_changed(self) -> None:
        if self._running:
            return
        self._apply_mode(normalize_mode(self._mode_var.get()), persist=True)

    def _apply_mode(self, mode: ModeName, *, persist: bool) -> None:
        self._mode_var.set(mode)
        self._jobs = jobs_for_mode(mode)
        self._progress_bar.stop()
        self._progress_bar.configure(mode="determinate", maximum=1, value=0)
        self._progress_detail.configure(text="Ready")
        self._progress_total = 0
        self._progress_completed = 0
        for child in self._jobs_panel.winfo_children():
            child.destroy()
        self._job_widgets.clear()

        helper_status = helper_build_status(mode)
        for index, job in enumerate(self._jobs, start=1):
            self._create_job_row(index, job, helper_status)

        self._helper_badge.configure(
            text=f"REDDIT HELPER · {helper_status.reason} · {helper_status.input_count} fingerprinted inputs",
            fg=COLORS["amber"] if helper_status.needs_rebuild else COLORS["green"],
        )
        if persist:
            self._persist_preferences()
        self._start_button.state(["disabled"])
        threading.Thread(target=self._preflight_worker, args=(mode,), daemon=True).start()

    def _create_job_row(
        self,
        index: int,
        job: Job,
        helper_status: HelperBuildStatus,
    ) -> None:
        frame = tk.Frame(
            self._jobs_panel,
            bg=COLORS["panel"],
            padx=11,
            pady=7,
            highlightbackground="#28383a",
            highlightthickness=0 if index == 1 else 1,
        )
        frame.pack(fill="x")
        selected = bool(job.default_selected) and (
            job.key != "reddit_helper" or helper_status.needs_rebuild
        )
        variable = tk.BooleanVar(value=selected)
        checkbox = FoundryCheckbutton(
            frame,
            text=f"{index}.  {job.name}",
            variable=variable,
            background=COLORS["panel"],
            indicator_size=self._dip(24),
            gap=self._dip(6),
        )
        checkbox.pack(side="left")
        status = tk.Label(
            frame,
            text="Pending" if selected else "Unchanged",
            bg=COLORS["panel"],
            fg=COLORS["muted"] if selected else COLORS["green"],
            font=("Segoe UI", 9, "bold"),
            width=13,
            anchor="e",
        )
        status.pack(side="right")
        output_link = LinkLabel(frame, "Output", lambda path=job.output_dir: open_local_path(path))
        output_link.pack(side="right", padx=(4, 2))
        output_link.pack_forget()
        log_link = LinkLabel(frame, "Log", lambda: None)
        log_link.pack(side="right", padx=(4, 2))
        log_link.pack_forget()
        self._job_widgets[job.key] = JobWidgets(
            frame,
            variable,
            checkbox,
            status,
            log_link,
            output_link,
        )

    def _preflight_worker(self, mode: ModeName) -> None:
        result = run_preflight(mode)
        self._events.put(("preflight", mode, result))

    def _set_all(self, value: bool) -> None:
        if self._running:
            return
        for widgets in self._job_widgets.values():
            if "disabled" not in widgets.checkbox.state():
                widgets.variable.set(value)

    def _on_start(self) -> None:
        if self._running:
            return
        self._cancel_auto_close()
        selected = {
            job.key
            for job in self._jobs
            if self._job_widgets[job.key].variable.get()
        }
        if not selected:
            self._footer_status.configure(
                text="Select at least one build step.",
                fg=COLORS["amber"],
            )
            return

        self._running = True
        self._progress_total = len(selected)
        self._progress_completed = 0
        self._progress_bar.stop()
        self._progress_bar.configure(mode="indeterminate", maximum=100, value=0)
        self._progress_bar.start(PROGRESS_TICK_MS)
        self._progress_detail.configure(
            text=f"Preparing · 0 / {self._progress_total} jobs"
        )
        self._set_controls_enabled(False)
        self._footer_status.configure(
            text="Running selected jobs sequentially. Build Foundry will stay open.",
            fg=COLORS["green"],
        )
        mode = normalize_mode(self._mode_var.get())
        jobs = tuple(self._jobs)
        preflight = self._preflight
        threading.Thread(
            target=self._pipeline_worker,
            args=(mode, jobs, selected, preflight),
            daemon=True,
        ).start()

    def _set_controls_enabled(self, enabled: bool) -> None:
        state = ["!disabled"] if enabled else ["disabled"]
        for widgets in self._job_widgets.values():
            widgets.checkbox.state(state)
        self._start_button.state(state)
        self._select_all_button.state(state)
        self._select_none_button.state(state)
        self._auto_close_checkbox.state(state)
        for button in self._mode_buttons:
            button.configure(state="normal" if enabled else "disabled")

    def _pipeline_worker(
        self,
        mode: ModeName,
        jobs: Sequence[Job],
        selected: set[str],
        preflight: PreflightResult,
    ) -> None:
        all_ok = True
        try:
            preset_root = REPO_ROOT / "presets" / "visualizer_modes"
            entries = write_curated_visualizer_preset_manifest(preset_root)
            self._events.put(
                (
                    "footer",
                    f"Regenerated the curated preset manifest for {len(entries)} artifacts.",
                    COLORS["green"],
                )
            )
        except Exception as exc:
            self._events.put(("pipeline_done", False, f"Preset regeneration failed: {exc}"))
            return

        helper_status = helper_build_status(mode)
        for job in jobs:
            if job.key not in selected:
                self._events.put(("job_skipped", job.key))
                continue
            self._events.put(("job_running", job.key))
            result = run_job(job, preflight)
            if result.returncode == 0 and job.key == "reddit_helper":
                if not record_helper_build(
                    mode,
                    helper_status.fingerprint,
                    artifact=job.expected_artifact,
                    state_path=HELPER_STATE_PATH,
                ):
                    result = JobResult(
                        1,
                        "Build succeeded, but helper fingerprint could not be recorded",
                        result.log_path,
                        result.output_path,
                    )
            all_ok = all_ok and result.returncode == 0
            self._events.put(("job_done", job.key, result))

        message = (
            "All selected jobs completed successfully."
            if all_ok
            else "Pipeline completed with one or more failures."
        )
        self._events.put(("pipeline_done", all_ok, message))

    def _poll_events(self) -> None:
        try:
            while True:
                self._dispatch_event(self._events.get_nowait())
        except queue.Empty:
            pass
        self._root.after(100, self._poll_events)

    def _dispatch_event(self, event: tuple) -> None:
        kind = event[0]
        if kind == "preflight":
            _, mode, result = event
            if mode != normalize_mode(self._mode_var.get()) or self._running:
                return
            self._preflight = result
            self._preflight_label.configure(
                text=result.summary(),
                fg=COLORS["red"] if result.errors else COLORS["green"],
            )
            details = [*result.errors[:2], *result.warnings[:2]]
            self._preflight_detail.configure(text="  ·  ".join(details))
            for job in self._jobs:
                widgets = self._job_widgets[job.key]
                if job.key in result.unavailable_jobs:
                    widgets.checkbox.state(["disabled"])
                    widgets.variable.set(False)
                    widgets.status.configure(text="Unavailable", fg=COLORS["red"])
            self._start_button.state(["!disabled"])
            return

        if kind == "footer":
            _, text, color = event
            self._footer_status.configure(text=text, fg=color)
            return

        if kind == "job_running":
            key = event[1]
            widgets = self._job_widgets[key]
            widgets.status.configure(text="Running…", fg=COLORS["amber"])
            job_name = next(job.name for job in self._jobs if job.key == key)
            self._progress_bar.stop()
            self._progress_bar.configure(mode="indeterminate", maximum=100, value=0)
            self._progress_bar.start(PROGRESS_TICK_MS)
            self._progress_detail.configure(
                text=(
                    f"{job_name} · {self._progress_completed} / "
                    f"{self._progress_total} jobs complete"
                )
            )
            return

        if kind == "job_skipped":
            widgets = self._job_widgets[event[1]]
            widgets.status.configure(text="Skipped", fg=COLORS["faint"])
            return

        if kind == "job_done":
            _, key, result = event
            widgets = self._job_widgets[key]
            success = result.returncode == 0
            self._progress_completed += 1
            self._progress_bar.stop()
            self._progress_bar.configure(
                mode="determinate",
                maximum=max(1, self._progress_total),
                value=self._progress_completed,
            )
            self._progress_detail.configure(
                text=f"{self._progress_completed} / {self._progress_total} jobs complete"
            )
            widgets.status.configure(
                text="Complete" if success else f"Failed {result.returncode}",
                fg=COLORS["green"] if success else COLORS["red"],
            )
            widgets.log_link._command = lambda path=result.log_path: open_local_path(path)
            widgets.log_link.pack(side="right", padx=(4, 2), before=widgets.status)
            if result.output_path.exists():
                widgets.output_link.pack(side="right", padx=(4, 2), before=widgets.log_link)
            return

        if kind == "pipeline_done":
            _, success, message = event
            self._running = False
            self._progress_bar.stop()
            self._progress_bar.configure(
                mode="determinate",
                maximum=max(1, self._progress_total),
                value=self._progress_completed,
            )
            self._progress_detail.configure(
                text=(
                    f"{self._progress_completed} / {self._progress_total} jobs · "
                    f"{'success' if success else 'finished with errors'}"
                )
            )
            self._set_controls_enabled(True)
            self._footer_status.configure(
                text=message,
                fg=COLORS["green"] if success else COLORS["red"],
            )
            if success and self._auto_close_var.get():
                self._footer_status.configure(
                    text=f"{message} Closing in {self.AUTO_CLOSE_MS // 1000} seconds…"
                )
                self._auto_close_after_id = self._root.after(
                    self.AUTO_CLOSE_MS,
                    self._auto_close_if_idle,
                )


def smoke_payload(mode: ModeName) -> dict:
    status = helper_build_status(mode)
    preflight = run_preflight(mode)
    jobs = jobs_for_mode(mode)
    return {
        "success": not any(
            job.default_selected and not job.script.is_file()
            for job in jobs
        ),
        "mode": mode,
        "jobs": [
            {
                "key": job.key,
                "kind": job.kind,
                "script": str(job.script),
                "output_dir": str(job.output_dir),
                "default_selected": bool(job.default_selected),
            }
            for job in jobs
        ],
        "helper": {
            "needs_rebuild": status.needs_rebuild,
            "reason": status.reason,
            "input_count": status.input_count,
        },
        "preflight": {
            "errors": preflight.errors,
            "warnings": preflight.warnings,
        },
        "preferences_path": str(preferences_path()),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified SRPSS Build Foundry")
    parser.add_argument("--mode", choices=("normal", "venv"))
    parser.add_argument(
        "--venv",
        action="store_true",
        help="Compatibility alias for --mode venv",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Validate mode/job/fingerprint routing without opening the GUI or running builds",
    )
    args = parser.parse_args(argv)
    if args.venv:
        args.mode = "venv"
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    persisted = load_preferences()
    mode = normalize_mode(args.mode or persisted.mode)
    if args.smoke_test:
        payload = smoke_payload(mode)
        print(json.dumps(payload, indent=2))
        return 0 if payload["success"] else 1

    if sys.platform != "win32":
        print("Warning: the SRPSS Build Foundry is intended for Windows")
    dpi_mode = enable_windows_dpi_awareness()
    set_windows_app_user_model_id()
    prune_build_runner_logs(LOG_DIR)
    root = tk.Tk()
    root.withdraw()
    try:
        root.tk.call("tk", "appname", TASKBAR_TITLE)
    except tk.TclError:
        pass
    try:
        root.tk.call("tk", "scaling", max(1.0, root.winfo_fpixels("1i") / 72.0))
    except (tk.TclError, ValueError, TypeError):
        pass
    if os.environ.get("SRPSS_BUILD_RUNNER_DEBUG"):
        print(f"Build Foundry DPI mode: {dpi_mode}")
    BuildRunnerApp(root, initial_mode=mode)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
