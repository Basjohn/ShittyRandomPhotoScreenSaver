"""Bounded persistent-cache inventory and deletion helpers."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from core.logging.logger import get_logger
from core.settings.storage_paths import get_app_data_dir

logger = get_logger(__name__)


@dataclass(frozen=True)
class CacheTarget:
    path: Path
    pattern: str = "*"
    recursive: bool = False


@dataclass(frozen=True)
class CacheFamilyDescriptor:
    family_id: str
    label: str
    description: str
    targets: tuple[CacheTarget, ...]


@dataclass(frozen=True)
class CacheClearResult:
    selected_ids: tuple[str, ...]
    removed_files: int
    removed_bytes: int
    skipped_files: int
    errors: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not self.errors and self.skipped_files == 0


def get_cache_family_descriptors(
    *,
    app_data_dir: Path | None = None,
    reddit_cache_dir: Path | None = None,
) -> tuple[CacheFamilyDescriptor, ...]:
    """Return the explicit cache families safe for user-requested deletion."""

    app_root = Path(app_data_dir) if app_data_dir is not None else get_app_data_dir()
    cache_root = app_root / "cache"
    reddit_root = (
        Path(reddit_cache_dir)
        if reddit_cache_dir is not None
        else Path(__file__).resolve().parents[1] / "cache" / "reddit"
    )
    return (
        CacheFamilyDescriptor(
            "rss",
            "RSS Images",
            "Downloaded images from configured RSS and JSON feeds.",
            (CacheTarget(cache_root / "rss"),),
        ),
        CacheFamilyDescriptor(
            "reddit",
            "Reddit Posts",
            "Saved Reddit post snapshots. Startup pacing markers are preserved.",
            (CacheTarget(reddit_root, pattern="*_posts.json"),),
        ),
        CacheFamilyDescriptor(
            "weather",
            "Weather",
            "Provider and last-visible weather responses.",
            (
                CacheTarget(cache_root / "weather.json"),
                CacheTarget(cache_root / "weather_widget_last.json"),
            ),
        ),
        CacheFamilyDescriptor(
            "gmail",
            "Gmail Messages",
            "Cached message metadata only. Sign-in credentials are never included.",
            (CacheTarget(cache_root / "gmail_cache.json"),),
        ),
        CacheFamilyDescriptor(
            "steam",
            "Steam Data And Artwork",
            "Account-scoped API responses and public artwork. Steam credentials are never included.",
            (CacheTarget(app_root / "steam" / "cache", recursive=True),),
        ),
        CacheFamilyDescriptor(
            "settings",
            "Settings Performance Data",
            "Cached defaults and font-list data used to open Settings faster.",
            (CacheTarget(cache_root / "settings_dialog_cache.json"),),
        ),
    )


def clear_cache_families(
    selected_ids: Iterable[str],
    *,
    descriptors: Sequence[CacheFamilyDescriptor] | None = None,
) -> CacheClearResult:
    """Delete files from selected allowlisted cache families without removing directories."""

    selected = tuple(dict.fromkeys(str(item).strip() for item in selected_ids if str(item).strip()))
    available = {
        descriptor.family_id: descriptor
        for descriptor in (descriptors if descriptors is not None else get_cache_family_descriptors())
    }
    unknown = tuple(family_id for family_id in selected if family_id not in available)
    if unknown:
        raise ValueError(f"Unknown cache family: {', '.join(unknown)}")

    removed_files = 0
    removed_bytes = 0
    skipped_files = 0
    errors: list[str] = []

    for family_id in selected:
        descriptor = available[family_id]
        for target in descriptor.targets:
            for candidate in _iter_target_files(target):
                if candidate.is_symlink():
                    skipped_files += 1
                    errors.append(f"{descriptor.label}: skipped symbolic link {candidate.name}")
                    continue
                try:
                    file_size = candidate.stat().st_size
                    candidate.unlink()
                    removed_files += 1
                    removed_bytes += max(0, int(file_size))
                except FileNotFoundError:
                    continue
                except PermissionError:
                    skipped_files += 1
                    errors.append(f"{descriptor.label}: {candidate.name} is in use")
                except OSError as exc:
                    skipped_files += 1
                    errors.append(f"{descriptor.label}: could not remove {candidate.name}")
                    logger.debug(
                        "[CACHE_MAINTENANCE] Delete failed family=%s file=%s error=%s",
                        family_id,
                        candidate.name,
                        exc,
                    )

    logger.info(
        "[CACHE_MAINTENANCE] selected=%s removed_files=%d removed_bytes=%d skipped=%d",
        ",".join(selected) or "none",
        removed_files,
        removed_bytes,
        skipped_files,
    )
    return CacheClearResult(
        selected_ids=selected,
        removed_files=removed_files,
        removed_bytes=removed_bytes,
        skipped_files=skipped_files,
        errors=tuple(errors),
    )


def _iter_target_files(target: CacheTarget) -> tuple[Path, ...]:
    path = Path(target.path)
    if path.is_file() or path.is_symlink():
        return (path,)
    if not path.exists() or not path.is_dir():
        return ()
    if not target.recursive:
        return tuple(candidate for candidate in path.glob(target.pattern) if candidate.is_file() or candidate.is_symlink())

    files: list[Path] = []
    for root, dir_names, file_names in os.walk(path, topdown=True, followlinks=False):
        root_path = Path(root)
        retained_dirs: list[str] = []
        for dir_name in dir_names:
            directory = root_path / dir_name
            if directory.is_symlink():
                files.append(directory)
            else:
                retained_dirs.append(dir_name)
        dir_names[:] = retained_dirs
        for file_name in file_names:
            candidate = root_path / file_name
            if candidate.match(target.pattern):
                files.append(candidate)
    return tuple(files)
