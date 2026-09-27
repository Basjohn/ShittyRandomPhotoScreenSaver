"""Save the image on screen into the user's collection ("Save Image").

The destination is the folder the user chose for Sources → Save Feed Images
(``sources.rss_save_directory``) when they ever chose one; otherwise
``Pictures/SRPSS Collections``, which becomes a local source after its first
save (the engine registers it without rebuilding the running sources).

The copy is the file SRPSS already has on disk, byte for byte: no re-encode, no
extra sizes, no prefetch or cache involvement. One ``shutil.copy2`` per request,
run on an I/O worker; nothing here schedules, polls or watches.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

COLLECTION_FOLDER_NAME = "SRPSS Collections"


@dataclass(frozen=True)
class CollectionTarget:
    directory: Path
    is_default: bool  # the Pictures fallback, which joins local sources once used


def default_collection_directory() -> Path:
    from PySide6.QtCore import QStandardPaths
    pictures = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation)
    base = Path(pictures) if pictures else Path.home() / "Pictures"
    return base / COLLECTION_FOLDER_NAME


def resolve_collection_target(settings) -> CollectionTarget:
    chosen = str(settings.get("sources.rss_save_directory") or "").strip()
    if chosen:
        return CollectionTarget(Path(chosen), False)
    return CollectionTarget(default_collection_directory(), True)


def save_image_to_collection(source: Path, directory: Path) -> Path | None:
    """Copy ``source`` into ``directory``; return the saved path (or the existing copy).

    Runs on an I/O worker. An identical-size file of the same name counts as
    already saved; a different file with the same name gets a numbered name.
    """
    source = Path(source)
    if not source.is_file():
        return None
    directory.mkdir(parents=True, exist_ok=True)
    size = source.stat().st_size
    candidate = directory / source.name
    number = 2
    while candidate.exists():
        if candidate.stat().st_size == size:
            return candidate
        candidate = directory / f"{source.stem} ({number}){source.suffix}"
        number += 1
    shutil.copy2(source, candidate)
    return candidate
