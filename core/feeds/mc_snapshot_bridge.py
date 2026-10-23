"""Forward-only bridge: adopt MC's pre-2026-10-24 Feeds snapshots into the shared root.

Before the shared data-root rule, MC wrote Feeds snapshots and artwork under
``SRPSS_MC/cache/feeds``. Both profiles now read ``SRPSS/cache/feeds``. This
moves the old files across once so MC keeps its offline last-good content:
files the target lacks are moved, a name collision keeps the newer mtime, and
emptied MC cache folders (plus an empty ``SRPSS_MC/steam`` left by old path
resolution) are removed. Per-profile files are never touched. A failed file
stays in place and is retried by the next process.

Removal horizon: one release after 5.0.8 (see
``Docs/Architecture/Persisted_Input_Compatibility.md``).
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path

from core.logging.logger import get_logger

logger = get_logger(__name__)

_ONCE_LOCK = threading.Lock()
_ATTEMPTED = False


@dataclass(frozen=True)
class AdoptionResult:
    moved: int = 0
    replaced: int = 0
    discarded_older: int = 0
    failed: int = 0


def adopt_mc_feed_snapshots(source: Path, target: Path) -> AdoptionResult:
    """Merge-move every file under ``source`` into ``target``; idempotent."""
    source = Path(source)
    target = Path(target)
    if not source.is_dir():
        return AdoptionResult()
    moved = replaced = discarded = failed = 0
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        destination = target / path.relative_to(source)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                os.replace(path, destination)
                moved += 1
            elif path.stat().st_mtime > destination.stat().st_mtime:
                os.replace(path, destination)
                replaced += 1
            else:
                path.unlink()
                discarded += 1
        except OSError:
            failed += 1
            logger.debug("[FEEDS][MC_BRIDGE] Could not adopt %s", path, exc_info=True)
    _remove_empty_tree(source)
    return AdoptionResult(moved, replaced, discarded, failed)


def _remove_empty_tree(root: Path) -> None:
    if not root.is_dir():
        return
    for directory in sorted((p for p in root.rglob("*") if p.is_dir()), reverse=True):
        _rmdir_if_empty(directory)
    _rmdir_if_empty(root)


def _rmdir_if_empty(directory: Path) -> None:
    try:
        directory.rmdir()
    except OSError:
        pass  # Not empty, already gone, or in use: leave it.


def adopt_canonical_mc_feed_snapshots_once(shared_feed_dir: Path) -> None:
    """Run the canonical-profile bridge at most once per process."""
    global _ATTEMPTED
    with _ONCE_LOCK:
        if _ATTEMPTED:
            return
        _ATTEMPTED = True
        # Derive the MC folder from the same base as the shared root, so a
        # caller (or test) that relocated the data root never reaches the
        # real profile: <base>/SRPSS/cache/feeds -> <base>/SRPSS_MC.
        shared_feed_dir = Path(shared_feed_dir)
        data_root = shared_feed_dir.parent.parent
        if shared_feed_dir.name != "feeds" or data_root.name != "SRPSS":
            return
        mc_profile_dir = data_root.parent / "SRPSS_MC"
        source = mc_profile_dir / "cache" / "feeds"
        if not source.is_dir():
            _rmdir_if_empty(mc_profile_dir / "steam")
            return
        result = adopt_mc_feed_snapshots(source, shared_feed_dir)
        _rmdir_if_empty(mc_profile_dir / "cache")
        _rmdir_if_empty(mc_profile_dir / "steam")
        logger.info(
            "[FEEDS][MC_BRIDGE] Adopted MC Feeds snapshots moved=%d replaced=%d "
            "discarded_older=%d failed=%d",
            result.moved, result.replaced, result.discarded_older, result.failed,
        )
