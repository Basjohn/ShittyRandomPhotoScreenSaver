#!/usr/bin/env python3
"""
SRPSS R-80 corrected ABC oracle runner.

Place this file in the SRPSS repository root and run it with the same Python
environment you use for SRPSS. It provides buttons for corrected A/B runs and
packages the resulting evidence automatically.

No product settings are changed. The harness itself launches main_mc.py with:
    --usage --viz --perf --life
and uses saved geometry slot 1 with 4 contention workers.
"""

from __future__ import annotations

import os
import queue
import shlex
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from zipfile import ZIP_DEFLATED, ZipFile


RUNS = {
    "A": "ABC_R80_A",
    "B": "ABC_R80_B",
}

CONTENTION_SECONDS = 260
DEADLINE_SECONDS = 260
LAYOUT_SLOT = 1
WORKERS = 4


def find_repo_root() -> Path:
    """Prefer the script directory; fall back to current working directory."""
    candidates = [Path(__file__).resolve().parent, Path.cwd()]
    for candidate in candidates:
        if (
            (candidate / "main_mc.py").is_file()
            and (candidate / "tools" / "visualizer_switch_abc_harness.py").is_file()
        ):
            return candidate
    return Path(__file__).resolve().parent


REPO = find_repo_root()
LOGS = REPO / "logs"
EVIDENCE = LOGS / "abc_evidence"
HARNESS = REPO / "tools" / "visualizer_switch_abc_harness.py"
MAIN_MC = REPO / "main_mc.py"
PERF_LOG = LOGS / "screensaver_perf.log"
USAGE_LOG = LOGS / "screensaver_usage.log"
RESULT_ZIP = EVIDENCE / "ABC_R80_results.zip"


class RunnerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("SRPSS R-80 ABC Oracle Runner")
        self.geometry("820x560")
        self.minsize(720, 480)

        self._messages: queue.Queue[tuple[str, object]] = queue.Queue()
        self._busy = False
        self._build_ui()
        self.after(100, self._drain_messages)

        self._log(f"Repository: {REPO}")
        self._log(f"Python: {sys.executable}")

        missing = []
        if not MAIN_MC.is_file():
            missing.append(str(MAIN_MC))
        if not HARNESS.is_file():
            missing.append(str(HARNESS))
        if missing:
            self._log("ERROR: Expected SRPSS files are missing:")
            for item in missing:
                self._log(f"  {item}")
            self.after(
                150,
                lambda: messagebox.showerror(
                    "Wrong location",
                    "Put this script in the SRPSS repository root.\n\nMissing:\n"
                    + "\n".join(missing),
                ),
            )

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="Corrected R-80 ABC Oracle",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            outer,
            text=(
                "Slot 1 • 4 contention workers • main_mc.py • --usage --viz --perf --life\n"
                "Run A and B separately or use Run A → B. Results are copied into "
                "logs\\abc_evidence and can be zipped with one click."
            ),
        ).pack(anchor="w", pady=(2, 10))

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(0, 10))

        self.run_a_btn = ttk.Button(
            buttons, text="Run A", command=lambda: self._start_runs(["A"])
        )
        self.run_a_btn.pack(side="left", padx=(0, 6))

        self.run_b_btn = ttk.Button(
            buttons, text="Run B", command=lambda: self._start_runs(["B"])
        )
        self.run_b_btn.pack(side="left", padx=(0, 6))

        self.run_ab_btn = ttk.Button(
            buttons, text="Run A → B", command=lambda: self._start_runs(["A", "B"])
        )
        self.run_ab_btn.pack(side="left", padx=(0, 18))

        self.package_btn = ttk.Button(
            buttons, text="Package Results", command=self._package_results
        )
        self.package_btn.pack(side="left", padx=(0, 6))

        self.folder_btn = ttk.Button(
            buttons, text="Open Evidence Folder", command=self._open_evidence_folder
        )
        self.folder_btn.pack(side="left")

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(0, 6))

        log_frame = ttk.Frame(outer)
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(
            log_frame,
            wrap="word",
            state="disabled",
            font=("Consolas", 9),
        )
        scrollbar = ttk.Scrollbar(
            log_frame, orient="vertical", command=self.log_text.yview
        )
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        for button in (
            self.run_a_btn,
            self.run_b_btn,
            self.run_ab_btn,
            self.package_btn,
        ):
            button.configure(state=state)

    def _log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text.rstrip() + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _post_log(self, text: str) -> None:
        self._messages.put(("log", text))

    def _post_status(self, text: str) -> None:
        self._messages.put(("status", text))

    def _drain_messages(self) -> None:
        try:
            while True:
                kind, payload = self._messages.get_nowait()
                if kind == "log":
                    self._log(str(payload))
                elif kind == "status":
                    self.status_var.set(str(payload))
                elif kind == "done":
                    self._set_busy(False)
                    ok, message = payload
                    self.status_var.set(message)
                    if ok:
                        messagebox.showinfo("ABC runner", message)
                    else:
                        messagebox.showerror("ABC runner", message)
        except queue.Empty:
            pass
        self.after(100, self._drain_messages)

    def _start_runs(self, conditions: list[str]) -> None:
        if self._busy:
            return

        if not MAIN_MC.is_file() or not HARNESS.is_file():
            messagebox.showerror(
                "Wrong location",
                "This script cannot find main_mc.py and the ABC harness.\n"
                "Put it in the SRPSS repository root.",
            )
            return

        EVIDENCE.mkdir(parents=True, exist_ok=True)
        self._set_busy(True)
        self.status_var.set("Starting…")

        thread = threading.Thread(
            target=self._run_sequence,
            args=(conditions,),
            daemon=True,
        )
        thread.start()

    def _run_sequence(self, conditions: list[str]) -> None:
        try:
            for condition in conditions:
                self._run_one(condition)

            zip_path = self._package_results_worker()
            self._messages.put(
                (
                    "done",
                    (
                        True,
                        "Completed successfully.\n\n"
                        f"Evidence ZIP:\n{zip_path}",
                    ),
                )
            )
        except Exception as exc:
            self._post_log("")
            self._post_log(f"ERROR: {exc}")
            self._messages.put(("done", (False, str(exc))))

    def _run_one(self, condition: str) -> None:
        name = RUNS[condition]
        self._post_status(f"Running condition {condition}…")
        self._post_log("")
        self._post_log("=" * 72)
        self._post_log(f"RUNNING {condition}: {name}")
        self._post_log("=" * 72)

        EVIDENCE.mkdir(parents=True, exist_ok=True)

        for live_log in (PERF_LOG, USAGE_LOG):
            try:
                live_log.unlink()
            except FileNotFoundError:
                pass

        # The harness parses --run-cmd with POSIX shlex even on Windows. A normal
        # backslash path such as C:\\Python311\\pythonw.exe is therefore mangled.
        # Pass a forward-slash path instead, which Windows accepts and shlex preserves.
        #
        # Prefer python.exe over pythonw.exe for the child app so diagnostic failures
        # remain observable; keep the same interpreter installation/venv.
        gui_python = Path(sys.executable).resolve()
        if gui_python.name.lower() == "pythonw.exe":
            console_python = gui_python.with_name("python.exe")
            if not console_python.is_file():
                console_python = gui_python
        else:
            console_python = gui_python

        python_for_shlex = console_python.as_posix()
        run_cmd = " ".join(
            [
                shlex.quote(python_for_shlex),
                "main_mc.py",
                "--usage",
                "--viz",
                "--perf",
                "--life",
            ]
        )

        # Fail before starting contention if the resolved child interpreter vanished.
        if not console_python.is_file():
            raise RuntimeError(
                "Could not resolve the Python interpreter for the SRPSS child run: "
                f"{console_python}"
            )

        command = [
            sys.executable,
            str(HARNESS),
            "auto",
            "--condition",
            condition,
            "--layout-slot",
            str(LAYOUT_SLOT),
            "--workers",
            str(WORKERS),
            "--contention-seconds",
            str(CONTENTION_SECONDS),
            "--deadline-seconds",
            str(DEADLINE_SECONDS),
            "--log",
            str(PERF_LOG),
            "--rep-out",
            str(EVIDENCE / f"{name}.json"),
            "--out",
            str(EVIDENCE / f"{name}.auto.json"),
            "--run-cmd",
            run_cmd,
        ]

        self._post_log("Harness command:")
        self._post_log(subprocess.list2cmdline(command))
        self._post_log("")
        self._post_log(
            "The screensaver may take over the display during this run. "
            "Let the harness finish automatically."
        )

        process = subprocess.Popen(
            command,
            cwd=str(REPO),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        assert process.stdout is not None
        for line in process.stdout:
            self._post_log(line.rstrip())

        return_code = process.wait()
        self._post_log(f"Harness exit code: {return_code}")

        # Preserve whatever the app produced even when the harness fails, because
        # failed/invalid runs are still useful diagnostic evidence.
        self._copy_live_log(PERF_LOG, EVIDENCE / f"{name}.perf.log")
        self._copy_live_log(USAGE_LOG, EVIDENCE / f"{name}.usage.log")

        if return_code != 0:
            raise RuntimeError(
                f"Condition {condition} failed with harness exit code {return_code}.\n\n"
                "The partial evidence has still been preserved and will remain in "
                f"{EVIDENCE}."
            )

        self._post_log(f"{name} completed successfully.")

    def _copy_live_log(self, source: Path, destination: Path) -> None:
        if source.is_file():
            shutil.copy2(source, destination)
            self._post_log(f"Saved: {destination.name}")
        else:
            self._post_log(f"Not produced: {source.name}")

    def _package_results_worker(self) -> Path:
        EVIDENCE.mkdir(parents=True, exist_ok=True)

        files = sorted(
            path
            for path in EVIDENCE.glob("ABC_R80_*")
            if path.is_file() and path.resolve() != RESULT_ZIP.resolve()
        )

        if not files:
            raise RuntimeError(
                "No ABC_R80 evidence files exist yet. Run A and/or B first."
            )

        temp_zip = RESULT_ZIP.with_suffix(".zip.tmp")
        try:
            temp_zip.unlink()
        except FileNotFoundError:
            pass

        with ZipFile(temp_zip, "w", compression=ZIP_DEFLATED, compresslevel=6) as zf:
            for path in files:
                zf.write(path, arcname=path.name)

        os.replace(temp_zip, RESULT_ZIP)
        self._post_log("")
        self._post_log(f"Packaged: {RESULT_ZIP}")
        return RESULT_ZIP

    def _package_results(self) -> None:
        if self._busy:
            return

        try:
            path = self._package_results_worker()
            self.status_var.set("Results packaged")
            messagebox.showinfo(
                "Evidence packaged",
                f"Give ChatGPT this file:\n\n{path}",
            )
        except Exception as exc:
            messagebox.showerror("Packaging failed", str(exc))

    def _open_evidence_folder(self) -> None:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(EVIDENCE))  # type: ignore[attr-defined]
        except Exception as exc:
            messagebox.showerror("Could not open folder", str(exc))


if __name__ == "__main__":
    app = RunnerApp()
    app.mainloop()
