"""SRPSS material-experiment debris mover with reversible /deleteme batches.

Overlay-style checkpoint installs cannot remove files deleted by a newer source
snapshot. This helper finds only known rejected card-material experiment debris
(and matching failed experiment artifacts copied into the repository root), moves
selected items to ``<repo>/deleteme/<timestamp>/`` while preserving relative
paths, records a manifest, and can undo the newest live batch.

Nothing is permanently deleted by this tool.
"""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Iterable

KNOWN_RELATIVE_DEBRIS = (
    "rendering/quick/qml/CardMaterialBackdrop.qml",
    "rendering/quick/qml/OverlayCardMaterialMask.qml",
    "tests/test_widget_material_shared_contract.py",
    "Docs/QtQuick_Migration/Widget_Theme_And_Card_Material_Implementation_Plan.md",
)

ROOT_ARTIFACT_PATTERNS = (
    # Rejected experiment packages only. Deliberately do NOT use a generic
    # *MATERIAL* wildcard: the accepted rollback checkpoint/handoff also carry
    # MATERIAL in their names and must never be proposed as debris.
    "SRPSS_GOD_CHECKPOINT_*MATERIAL_ADMISSION*.zip",
    "SRPSS_GOD_CHECKPOINT_*MATERIAL_DIAGNOSTICS*.zip",
    "SRPSS_GOD_CHECKPOINT_*MATERIAL_V3_LAYER_SOURCE*.zip",
    "SRPSS_GOD_CHECKPOINT_*MATERIAL_V31_LAYER_REFRESH*.zip",
    "SRPSS_Stand_Alone_Handoff_*Material_Admission*.md",
    "SRPSS_THEME8_WIDGET_COUNTERPART_REPLACEMENTS*.zip",
)

MANIFEST_NAME = "move_manifest.json"


def looks_like_repo(root: Path) -> bool:
    root = root.resolve()
    return (
        (root / "rendering" / "quick").is_dir()
        and (root / "ui").is_dir()
        and (root / "Current_Plan.md").exists()
    )



def default_repo_root() -> Path:
    """Resolve a useful default whether launched from tools/ or copied standalone."""

    candidates: list[Path] = []
    script = Path(__file__).resolve()
    candidates.extend((script.parent, *script.parents))
    cwd = Path.cwd().resolve()
    candidates.extend((cwd, *cwd.parents))
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if looks_like_repo(candidate):
            return candidate
    return cwd

def scan_candidates(root: Path) -> list[tuple[Path, str]]:
    """Return known debris without recursing into unrelated project content."""

    root = root.resolve()
    candidates: list[tuple[Path, str]] = []
    seen: set[Path] = set()

    for relative in KNOWN_RELATIVE_DEBRIS:
        path = root / relative
        if path.exists() and path not in seen:
            candidates.append((path, "Known material debris"))
            seen.add(path)

    # Architecture-v3 ships colour-only Widget-theme filenames. Overlaying a ZIP
    # cannot delete the old material-suffixed v2 files, so offer only those stale
    # Widget mirrors for reversible removal. Settings-theme filenames are not
    # touched because Glass/Acrylic still legitimately describe the Settings HWND.
    widget_theme_dir = root / "themes" / "widgets"
    if widget_theme_dir.is_dir():
        for path in sorted(widget_theme_dir.glob("*.srwtheme")):
            if not path.name.endswith((" [Glass].srwtheme", " [Acrylic].srwtheme")):
                continue
            if path.is_file() and path not in seen:
                candidates.append((path, "Retired material-named Widget theme"))
                seen.add(path)

    # Failed checkpoint/handoff files are candidates only if copied into the
    # repository root. Do not recursively sweep arbitrary user archives.
    for pattern in ROOT_ARTIFACT_PATTERNS:
        for path in sorted(root.glob(pattern)):
            if path.is_file() and path not in seen:
                candidates.append((path, "Root experiment artifact"))
                seen.add(path)

    return candidates


def move_to_deleteme(
    root: Path,
    paths: Iterable[Path],
    *,
    stamp: str | None = None,
) -> Path | None:
    """Move selected repo children into one reversible batch and return its dir."""

    root = root.resolve()
    selected = [Path(path).resolve() for path in paths]
    if not selected:
        return None

    stamp = stamp or datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    batch = root / "deleteme" / stamp
    records: list[dict[str, str]] = []

    for path in selected:
        try:
            rel = path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"Refusing to move path outside repository: {path}") from exc
        if rel.parts and rel.parts[0] == "deleteme":
            raise ValueError(f"Refusing to re-move /deleteme content: {rel}")
        if not path.exists():
            continue
        target = batch / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise FileExistsError(f"Unexpected batch collision: {target}")
        shutil.move(str(path), str(target))
        records.append({"source": str(rel), "moved_to": str(target.relative_to(root))})

    if not records:
        if batch.exists():
            shutil.rmtree(batch, ignore_errors=True)
        return None

    manifest = {
        "version": 1,
        "created": datetime.now().isoformat(timespec="seconds"),
        "repo_root": str(root),
        "moves": records,
        "undone": False,
    }
    (batch / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return batch


def latest_live_manifest(root: Path) -> Path | None:
    deleteme = root.resolve() / "deleteme"
    if not deleteme.exists():
        return None
    for manifest_path in sorted(deleteme.glob(f"*/{MANIFEST_NAME}"), reverse=True):
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not payload.get("undone", False):
            return manifest_path
    return None


def undo_manifest(root: Path, manifest_path: Path) -> int:
    """Restore one move batch without overwriting newer files."""

    root = root.resolve()
    manifest_path = manifest_path.resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    moves = payload.get("moves", [])

    collisions = [move["source"] for move in moves if (root / move["source"]).exists()]
    if collisions:
        raise FileExistsError(
            "Undo would overwrite existing path(s): " + ", ".join(collisions)
        )

    restored = 0
    for move in reversed(moves):
        source = root / move["moved_to"]
        target = root / move["source"]
        if not source.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        restored += 1

    payload["undone"] = True
    payload["undone_at"] = datetime.now().isoformat(timespec="seconds")
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return restored


class CleanupApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("SRPSS Material Rollback Cleanup")
        self.geometry("980x620")
        self.minsize(760, 480)

        self.repo_var = tk.StringVar(value=str(default_repo_root()))
        self.status_var = tk.StringVar(value="Ready.")
        self._candidates: list[tuple[Path, str]] = []
        self._build_ui()
        self.after(0, self.scan)

    @property
    def repo_root(self) -> Path:
        return Path(self.repo_var.get()).expanduser().resolve()

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="Repository root:").pack(side="left")
        ttk.Entry(top, textvariable=self.repo_var).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(top, text="Browse…", command=self.browse).pack(side="left")
        ttk.Button(top, text="Scan", command=self.scan).pack(side="left", padx=(8, 0))

        ttk.Label(
            self,
            text=(
                "Moves known rejected card-material experiment debris into "
                "repo/deleteme/<timestamp>. Nothing is permanently deleted; "
                "Undo Last Move restores the newest batch."
            ),
            wraplength=940,
            padding=(10, 0, 10, 8),
        ).pack(fill="x")

        frame = ttk.Frame(self, padding=(10, 0, 10, 8))
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            frame, columns=("kind", "path"), show="headings", selectmode="extended"
        )
        self.tree.heading("kind", text="Kind")
        self.tree.heading("path", text="Candidate")
        self.tree.column("kind", width=170, stretch=False)
        self.tree.column("path", width=720, stretch=True)
        y = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=y.set)
        self.tree.pack(side="left", fill="both", expand=True)
        y.pack(side="right", fill="y")

        controls = ttk.Frame(self, padding=(10, 0, 10, 8))
        controls.pack(fill="x")
        ttk.Button(controls, text="Select All", command=self.select_all).pack(side="left")
        ttk.Button(controls, text="Clear Selection", command=self.clear_selection).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Move Selected → /deleteme", command=self.move_selected).pack(side="left", padx=(18, 0))
        ttk.Button(controls, text="Undo Last Move", command=self.undo_last).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Open /deleteme", command=self.open_deleteme).pack(side="left", padx=(8, 0))

        ttk.Separator(self).pack(fill="x")
        ttk.Label(self, textvariable=self.status_var, padding=10).pack(fill="x")

    def browse(self) -> None:
        selected = filedialog.askdirectory(
            initialdir=self.repo_var.get(), title="Select SRPSS repository root"
        )
        if selected:
            self.repo_var.set(selected)
            self.scan()

    def scan(self) -> None:
        root = self.repo_root
        self.tree.delete(*self.tree.get_children())
        self._candidates.clear()
        if not looks_like_repo(root):
            self.status_var.set("Selected folder does not look like the SRPSS repository root.")
            return
        self._candidates = scan_candidates(root)
        for index, (path, kind) in enumerate(self._candidates):
            self.tree.insert(
                "", "end", iid=str(index), values=(kind, str(path.relative_to(root)))
            )
        if self._candidates:
            self.select_all()
            self.status_var.set(
                f"Found {len(self._candidates)} rollback-debris candidate(s). Review, then move selected."
            )
        else:
            self.status_var.set(
                "No known material-experiment debris found. The repository is already clean for this list."
            )

    def select_all(self) -> None:
        self.tree.selection_set(self.tree.get_children())

    def clear_selection(self) -> None:
        self.tree.selection_remove(self.tree.get_children())

    def move_selected(self) -> None:
        selected = list(self.tree.selection())
        if not selected:
            messagebox.showinfo("Nothing selected", "Select one or more candidates first.")
            return
        try:
            batch = move_to_deleteme(
                self.repo_root, [self._candidates[int(iid)][0] for iid in selected]
            )
        except Exception as exc:
            messagebox.showerror("Move failed", str(exc))
            return
        if batch is not None:
            self.status_var.set(
                f"Moved {len(selected)} item(s) to {batch.relative_to(self.repo_root)}. Undo is available."
            )
        self.scan()

    def undo_last(self) -> None:
        manifest_path = latest_live_manifest(self.repo_root)
        if manifest_path is None:
            messagebox.showinfo("Nothing to undo", "No live /deleteme move batch was found.")
            return
        try:
            restored = undo_manifest(self.repo_root, manifest_path)
        except Exception as exc:
            messagebox.showerror("Undo failed", str(exc))
            return
        self.status_var.set(
            f"Restored {restored} item(s) from {manifest_path.parent.name}."
        )
        self.scan()

    def open_deleteme(self) -> None:
        path = self.repo_root / "deleteme"
        path.mkdir(exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror("Open failed", str(exc))


def main() -> None:
    CleanupApp().mainloop()


if __name__ == "__main__":
    main()
