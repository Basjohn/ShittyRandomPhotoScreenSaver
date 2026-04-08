"""SRPSS Build Runner — builds both executables and both installers.

Usage:
    python tools/build_runner.py

Pipeline (sequential):
  1. Standard Build      — scripts/build_nuitka.ps1
  2. Media Center Build  — scripts/build_nuitka_mc_onedir.ps1
  3. Reddit Helper Build — scripts/build_reddit_helper.ps1
  4. Standard Installer  — scripts/SRPSS_Installer.iss  (ISCC.exe)
  5. MC Installer         — scripts/SRPSS_MediaCenter_Installer.iss (ISCC.exe)

Pre-flight checks run before any work begins.  If issues are found the GUI
offers a **Proceed Anyway** button so you can skip non-critical problems.

Inno Setup notes
----------------
* **ISCC.exe** is the *console-mode* command-line compiler.  It supports
  ``/Qp`` (quiet with progress on stdout), ``/O<dir>`` (output dir),
  ``/F<name>`` (output filename), ``/D<name>=<value>`` (preprocessor define),
  and returns exit codes 0 (ok), 1 (bad params), 2 (compile failed).
* **Compil32.exe** is the *GUI* IDE.  Its ``/cc`` flag pops up a progress
  window and has NO quiet, log, or define support.  We never use it.
* Installer version is stamped by regex-replacing ``AppVersion`` and
  ``VersionInfoVersion`` in the ``.iss`` files before invoking ISCC.
* ISCC stdout/stderr is captured into ``logs/<script>_<timestamp>.log``.
"""

from __future__ import annotations

import os
import queue
import re
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List

import tkinter as tk
from tkinter import ttk, messagebox


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from versioning import APP_VERSION  # noqa: E402
from core.visualizer_preset_manifest import (  # noqa: E402
    regenerate_repo_shipped_visualizer_preset_artifacts,
)

LOG_DIR = REPO_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

SCRIPTS_DIR = REPO_ROOT / "scripts"

# Candidate locations for the Inno Setup *console* compiler (ISCC.exe).
# Compil32.exe is the GUI IDE and must NOT be used for automation.
ISCC_CANDIDATES = (
    Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
)


# ---------------------------------------------------------------------------
# Job definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Job:
    name: str
    kind: str          # "powershell" | "inno"
    script: Path


JOBS: tuple[Job, ...] = (
    Job("Standard Build",     "powershell", SCRIPTS_DIR / "build_nuitka.ps1"),
    Job("Media Center Build", "powershell", SCRIPTS_DIR / "build_nuitka_mc_onedir.ps1"),
    Job("Reddit Helper Build","powershell", SCRIPTS_DIR / "build_reddit_helper.ps1"),
    Job("Standard Installer", "inno",       SCRIPTS_DIR / "SRPSS_Installer.iss"),
    Job("MC Installer",       "inno",       SCRIPTS_DIR / "SRPSS_MediaCenter_Installer.iss"),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_iscc() -> Path | None:
    """Locate ISCC.exe (console compiler).  Checks env override first."""
    env = os.environ.get("SRPSS_ISCC_PATH")
    if env:
        p = Path(env)
        if p.is_file() and p.name.lower() == "iscc.exe":
            return p
    for candidate in ISCC_CANDIDATES:
        if candidate.is_file():
            return candidate
    return None


def _find_pwsh() -> Path | None:
    """Return the path to pwsh if it is on PATH."""
    return Path(p) if (p := shutil.which("pwsh")) else None


def _windows_subprocess_kwargs() -> dict:
    """Best-effort child-process window suppression for Windows build tools."""
    if os.name != "nt":
        return {}

    kwargs: dict = {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
    }
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 6  # SW_MINIMIZE
    kwargs["startupinfo"] = startupinfo
    return kwargs


@dataclass
class PreflightResult:
    """Collects warnings and errors from pre-flight checks."""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    pwsh: Path | None = None
    iscc: Path | None = None

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0 and len(self.warnings) == 0

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def summary(self) -> str:
        lines: list[str] = []
        for e in self.errors:
            lines.append(f"ERROR: {e}")
        for w in self.warnings:
            lines.append(f"WARNING: {w}")
        return "\n".join(lines) if lines else "All checks passed."


def _run_preflight() -> PreflightResult:
    """Validate that every tool and file needed for the pipeline exists."""
    r = PreflightResult()

    # -- Tools --
    r.pwsh = _find_pwsh()
    if r.pwsh is None:
        r.errors.append("pwsh (PowerShell 7+) not found on PATH.")

    r.iscc = _find_iscc()
    if r.iscc is None:
        r.errors.append(
            "ISCC.exe (Inno Setup 6 console compiler) not found.\n"
            "  Looked in: C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe\n"
            "  Override with env var SRPSS_ISCC_PATH=<full path to ISCC.exe>"
        )

    # -- Scripts --
    for job in JOBS:
        if not job.script.is_file():
            r.errors.append(f"Script missing: {job.script}")

    # -- Build artifacts referenced by .iss files --
    std_scr = REPO_ROOT / "release" / "SRPSS.scr"
    mc_dist = REPO_ROOT / "release" / "main_mc.dist"
    mc_exe = mc_dist / "SRPSS_Media_Center.exe"
    icon = REPO_ROOT / "SRPSS.ico"
    logo = REPO_ROOT / "images" / "LogoBMP.bmp"

    helper_exe = REPO_ROOT / "release" / "helpers" / "SRPSS_RedditHelper.exe"

    if not std_scr.exists():
        r.warnings.append(
            "release/SRPSS.scr not found (will be created by build step 1)."
        )
    if not mc_exe.exists():
        r.warnings.append(
            "release/main_mc.dist/SRPSS_Media_Center.exe not found "
            "(will be created by build step 2)."
        )
    if not helper_exe.exists():
        r.warnings.append(
            "release/helpers/SRPSS_RedditHelper.exe not found "
            "(will be created by build step 3)."
        )
    if not icon.exists():
        r.warnings.append("SRPSS.ico not found (needed by installers).")
    if not logo.exists():
        r.warnings.append("images/LogoBMP.bmp not found (needed by installers).")

    return r


def _stamp_iss_version(path: Path) -> None:
    """Replace AppVersion / VersionInfoVersion in an .iss file with APP_VERSION."""
    text = path.read_text(encoding="utf-8")

    def _sub(m: re.Match[str]) -> str:
        return f"{m.group(1)}={APP_VERSION}"

    new_text = re.sub(
        r"^(AppVersion|VersionInfoVersion)=.*$",
        _sub,
        text,
        flags=re.MULTILINE,
    )
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class BuildRunnerApp:
    AUTO_CLOSE_MS = 3000

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._root.title(f"SRPSS Build Runner  (v{APP_VERSION})")
        self._root.resizable(True, False)
        self._queue: queue.Queue[tuple] = queue.Queue()
        self._pipeline_started = False

        # -- Header --
        self._header = ttk.Label(root, text="Running pre-flight checks…")
        self._header.pack(padx=16, pady=(12, 4))

        # -- Job rows --
        self._job_vars: list[tk.BooleanVar] = []
        self._status_labels: list[ttk.Label] = []
        for idx, job in enumerate(JOBS, start=1):
            frame = ttk.Frame(root)
            frame.pack(fill="x", padx=16, pady=2)
            var = tk.BooleanVar(value=True)
            chk = ttk.Checkbutton(frame, text=f"{idx}. {job.name}", variable=var)
            chk.pack(side="left")
            self._job_vars.append(var)
            lbl = ttk.Label(frame, text="Pending")
            lbl.pack(side="right", padx=(8, 0))
            self._status_labels.append(lbl)

        # -- Actions --
        actions = ttk.Frame(root)
        actions.pack(fill="x", padx=16, pady=(8, 0))
        self._start_button = ttk.Button(actions, text="Start Selected Builds", command=self._on_start_pressed)
        self._start_button.pack(side="left")
        self._start_button.state(["disabled"])

        self._select_all_button = ttk.Button(actions, text="All", command=lambda: self._set_all_jobs(True))
        self._select_all_button.pack(side="left", padx=(8, 0))

        self._select_none_button = ttk.Button(actions, text="None", command=lambda: self._set_all_jobs(False))
        self._select_none_button.pack(side="left", padx=(8, 0))

        # -- Footer --
        self._footer = ttk.Label(root, text="")
        self._footer.pack(padx=16, pady=(8, 12))

        # Kick off pre-flight on a thread so the GUI stays responsive.
        self._preflight: PreflightResult | None = None
        self._proceed = False
        threading.Thread(target=self._do_preflight, daemon=True).start()
        self._poll_queue()

    # -- Pre-flight ---------------------------------------------------------

    def _do_preflight(self) -> None:
        result = _run_preflight()
        self._preflight = result
        self._queue.put(("preflight_done", result))

    def _handle_preflight(self, result: PreflightResult) -> None:
        if result.ok:
            self._header["text"] = "Pre-flight OK. Select the jobs you want, then press Start."
            self._footer["text"] = "Tip: for SCR-only testing, Standard Build + Standard Installer is usually enough."
            self._start_button.state(["!disabled"])
            return

        summary = result.summary()
        if result.has_errors:
            title = "Pre-flight errors"
            msg = (
                f"The following issues were found:\n\n{summary}\n\n"
                "Errors (marked ERROR) will likely cause failures.\n"
                "Proceed anyway?"
            )
        else:
            title = "Pre-flight warnings"
            msg = (
                f"The following warnings were found:\n\n{summary}\n\n"
                "These may resolve during earlier build steps.\n"
                "Proceed anyway?"
            )

        proceed = messagebox.askyesno(title, msg, parent=self._root)
        if proceed:
            self._header["text"] = "Proceeding with warnings. Select the jobs you want, then press Start."
            self._footer["text"] = "Unchecked jobs will be skipped."
            self._start_button.state(["!disabled"])
        else:
            self._header["text"] = "Aborted by user."
            self._footer["text"] = "Close this window when ready."

    # -- Pipeline -----------------------------------------------------------

    def _selected_job_indices(self) -> list[int]:
        return [idx for idx, var in enumerate(self._job_vars) if bool(var.get())]

    def _set_all_jobs(self, value: bool) -> None:
        if self._pipeline_started:
            return
        for var in self._job_vars:
            var.set(value)

    def _on_start_pressed(self) -> None:
        if self._pipeline_started:
            return
        if not self._selected_job_indices():
            messagebox.showwarning("Nothing Selected", "Select at least one build step first.", parent=self._root)
            return
        self._header["text"] = "Building selected jobs…"
        self._footer["text"] = "Running selected pipeline steps in order."
        self._start_pipeline()

    def _start_pipeline(self) -> None:
        self._pipeline_started = True
        self._start_button.state(["disabled"])
        self._select_all_button.state(["disabled"])
        self._select_none_button.state(["disabled"])
        threading.Thread(target=self._run_pipeline, daemon=True).start()

    def _run_pipeline(self) -> None:
        pf = self._preflight or PreflightResult()
        all_ok = True
        selected = set(self._selected_job_indices())

        try:
            artifacts = regenerate_repo_shipped_visualizer_preset_artifacts(REPO_ROOT)
            self._queue.put(
                (
                    "footer",
                    f"Regenerated shipped visualizer preset artifacts "
                    f"({artifacts['entry_count']} curated files mirrored).",
                )
            )
        except Exception as exc:
            self._queue.put(("header", "Preset artifact regeneration failed."))
            self._queue.put(("footer", f"Build aborted before pipeline start: {exc}"))
            self._queue.put(("pipeline_done", False))
            return

        for idx, job in enumerate(JOBS):
            if idx not in selected:
                self._queue.put(("status", idx, "Skipped"))
                continue

            self._queue.put(("status", idx, "Running…"))

            try:
                if job.kind == "powershell":
                    code, detail = self._exec_powershell(idx, job, pf)
                elif job.kind == "inno":
                    code, detail = self._exec_inno(idx, job, pf)
                else:
                    code, detail = 1, "Unknown job kind"
            except Exception as exc:
                code, detail = 1, f"Unexpected: {exc}"

            if code == 0:
                self._queue.put(("status", idx, detail or "Done"))
            else:
                all_ok = False
                self._queue.put(("status", idx, detail or f"Failed (exit {code})"))

        self._queue.put(("pipeline_done", all_ok))

    def _exec_powershell(
        self, idx: int, job: Job, pf: PreflightResult
    ) -> tuple[int, str]:
        if pf.pwsh is None:
            return 1, "pwsh not available"
        cmd = [
            str(pf.pwsh),
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", str(job.script),
        ]
        code = self._run_cmd(cmd)
        return code, ("Done" if code == 0 else f"Failed (exit {code})")

    def _exec_inno(
        self, idx: int, job: Job, pf: PreflightResult
    ) -> tuple[int, str]:
        if pf.iscc is None:
            return 1, "ISCC.exe not available"

        # Stamp version into .iss before compiling.
        try:
            _stamp_iss_version(job.script)
        except Exception as exc:
            return 1, f"Version stamp failed: {exc}"

        # Build ISCC command.
        # /Qp = quiet compile with progress on stdout
        # stdout/stderr are captured to a log file.
        log_path = LOG_DIR / f"{job.script.stem}_{datetime.now():%Y%m%d_%H%M%S}.log"
        cmd = [
            str(pf.iscc),
            "/Qp",
            str(job.script),
        ]

        try:
            completed = subprocess.run(
                cmd,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
                **_windows_subprocess_kwargs(),
            )
            # Write combined stdout+stderr to log file.
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"Command: {' '.join(cmd)}\n")
                f.write(f"Exit code: {completed.returncode}\n")
                f.write(f"{'='*60}\n")
                if completed.stdout:
                    f.write(completed.stdout)
                if completed.stderr:
                    f.write("\n--- STDERR ---\n")
                    f.write(completed.stderr)

            code = completed.returncode
            if code == 0:
                return 0, f"Done (log: {log_path.name})"
            return code, f"Failed exit {code} (see {log_path.name})"

        except FileNotFoundError:
            return 1, f"ISCC.exe not found at {pf.iscc}"
        except Exception as exc:
            return 1, f"Error: {exc}"

    def _run_cmd(self, cmd: list[str]) -> int:
        """Run a command, return exit code.  Stdout/stderr go to console."""
        try:
            return subprocess.run(
                cmd,
                cwd=str(REPO_ROOT),
                check=False,
                **_windows_subprocess_kwargs(),
            ).returncode
        except FileNotFoundError:
            return 1
        except Exception:
            return 1

    # -- Queue polling ------------------------------------------------------

    def _poll_queue(self) -> None:
        try:
            while True:
                msg = self._queue.get_nowait()
                self._dispatch(msg)
        except queue.Empty:
            pass
        self._root.after(100, self._poll_queue)

    def _dispatch(self, msg: tuple) -> None:
        kind = msg[0]

        if kind == "preflight_done":
            self._handle_preflight(msg[1])

        elif kind == "header":
            _, text = msg
            self._header["text"] = text

        elif kind == "footer":
            _, text = msg
            self._footer["text"] = text

        elif kind == "status":
            _, idx, text = msg
            if 0 <= idx < len(self._status_labels):
                self._status_labels[idx]["text"] = text

        elif kind == "pipeline_done":
            success = msg[1]
            if success:
                self._header["text"] = "All steps completed successfully."
                self._footer["text"] = f"Auto-closing in {self.AUTO_CLOSE_MS // 1000}s…"
                self._root.after(self.AUTO_CLOSE_MS, self._root.destroy)
            else:
                self._header["text"] = "Pipeline finished with errors."
                self._footer["text"] = "Close this window when ready."


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    root = tk.Tk()
    root.geometry("520x320")
    BuildRunnerApp(root)
    root.mainloop()


if __name__ == "__main__":
    if sys.platform != "win32":
        print("Warning: build_runner.py is intended for Windows (PowerShell)")
    main()
