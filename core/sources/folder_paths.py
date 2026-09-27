"""One spelling for local source folders.

Qt's folder picker returns ``C:/Users/...`` while ``pathlib`` and the Save Image
collection write ``C:\\Users\\...``. Every place that adds, shows, de-duplicates
or removes ``sources.folders`` entries uses these helpers, so a folder always
reads the same way and is never added twice under two spellings. Stored values
are read as they are; nothing is rewritten merely to change separators.
"""
from __future__ import annotations

import os
from collections.abc import Iterable


def display_folder_path(value: object) -> str:
    """The folder as Windows spells it: native separators, no trailing separator."""
    text = str(value or "").strip()
    return os.path.normpath(text) if text else ""


def same_folder(first: object, second: object) -> bool:
    """Whether two stored spellings name the same folder (case and separators ignored)."""
    a, b = display_folder_path(first), display_folder_path(second)
    return bool(a) and os.path.normcase(a) == os.path.normcase(b)


def contains_folder(folders: Iterable[object], folder: object) -> bool:
    return any(same_folder(existing, folder) for existing in folders)


def without_folder(folders: Iterable[object], folder: object) -> list:
    """``folders`` minus every spelling of ``folder``, other entries untouched."""
    return [existing for existing in folders if not same_folder(existing, folder)]
