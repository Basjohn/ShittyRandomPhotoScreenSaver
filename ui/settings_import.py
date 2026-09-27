"""Import Settings with a category chooser (Settings → About and Guided Setup).

A snapshot can be imported whole (ALL SETTINGS) or by category. Choosing some
categories merges only those parts; everything else stays as it is. Accounts
and passwords are never part of a settings snapshot (see core.settings.sst_io).
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import QCheckBox, QFileDialog, QVBoxLayout, QWidget

from core.logging.logger import get_logger
from core.settings.sst_io import IMPORT_CATEGORIES, available_snapshot_categories
from ui.styled_popup import StyledPopup

logger = get_logger(__name__)


def _checkbox(text: str) -> QCheckBox:
    check = QCheckBox(text)
    check.setProperty("circleIndicator", True)
    from ui.tabs import shared_styles
    shared_styles.bind_shared_styles(check, "CIRCLE_CHECKBOX_STYLE")
    return check


class ImportCategoryChooser(QWidget):
    """ALL SETTINGS plus one box per category the snapshot actually contains."""

    def __init__(self, available, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.all = _checkbox("ALL SETTINGS")
        layout.addWidget(self.all)
        self.boxes: dict[str, QCheckBox] = {}
        for key, label in IMPORT_CATEGORIES:
            box = _checkbox(label)
            present = key in available
            box.setEnabled(present)
            box.setChecked(present)
            if not present:
                box.setToolTip("This settings file has nothing in this category.")
            box.toggled.connect(self._sync_all)
            layout.addWidget(box)
            self.boxes[key] = box
        self.all.toggled.connect(self._set_all)
        self._sync_all()

    def _set_all(self, checked: bool) -> None:
        for box in self.boxes.values():
            if box.isEnabled():
                with QSignalBlocker(box):
                    box.setChecked(checked)

    def _sync_all(self, *_args) -> None:
        enabled = [box for box in self.boxes.values() if box.isEnabled()]
        with QSignalBlocker(self.all):
            self.all.setChecked(bool(enabled) and all(box.isChecked() for box in enabled))

    def chosen(self) -> tuple[str, ...]:
        return tuple(key for key, box in self.boxes.items() if box.isEnabled() and box.isChecked())

    def everything(self) -> bool:
        return self.all.isChecked()


def choose_snapshot_file(parent) -> str:
    base = Path.home() / "Documents"
    if not base.exists():
        base = Path.cwd()
    path, _ = QFileDialog.getOpenFileName(
        parent, "Import Settings Snapshot", str(base), "Settings Snapshot (*.sst *.json);;All Files (*)")
    return path


def run_settings_import(parent, settings, path: str | None = None) -> bool:
    """Pick a snapshot, choose categories, import. Returns True only on success."""

    path = path or choose_snapshot_file(parent)
    if not path:
        return False
    available = available_snapshot_categories(path)
    if not available:
        StyledPopup.show_error(parent, "Import Failed", "That file is not a readable SRPSS settings snapshot.")
        return False
    chooser = ImportCategoryChooser(available)
    popup = StyledPopup(
        parent, "Import Settings",
        "Choose what to import. Anything you leave out stays as it is. "
        "Accounts and passwords are never part of a settings file.",
        icon_type="question", buttons=[("Import", "import"), ("Cancel", "cancel")], content=chooser)
    popup.exec()
    chosen = chooser.chosen()
    if popup.result_value != "import" or not chosen:
        return False
    categories = None if chooser.everything() else chosen
    try:
        ok = bool(settings.import_from_sst(path, merge=True, categories=categories))
    except Exception:
        logger.exception("Import from SST failed")
        ok = False
    if not ok:
        StyledPopup.show_error(parent, "Import Failed", "Failed to import settings snapshot.\nSee log for details.")
        return False
    if categories is None or "theme" in categories:
        _activate_imported_theme(settings)
    StyledPopup.show_success(parent, "Import Complete", f"Settings imported from:\n{Path(path).name}")
    return True


def _activate_imported_theme(settings) -> None:
    """An imported theme choice applies now, not only after a restart."""
    try:
        from ui.settings_theme_catalog import get_current_settings_theme_catalog, read_persisted_theme_id
        from ui.settings_theme_selection import apply_settings_theme_selection
        apply_settings_theme_selection(settings, get_current_settings_theme_catalog(), read_persisted_theme_id(settings))
    except Exception:
        logger.warning("Imported Settings theme could not be applied live", exc_info=True)
