"""Deterministic Phase 4 CPU/GL owner-budget and plateau harness."""
from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path
import sys
import time
from types import MappingProxyType, SimpleNamespace
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import psutil
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPixmap

from core.performance.resource_metrics import collect_resource_accounting
from rendering.gl_programs import texture_manager as texture_module
from rendering.gl_programs.texture_manager import GLTextureManager, PBOEntry
from rendering.image_resource_accounting import refresh_display_image_accounting
from rendering.transition_state import CrossfadeState
from utils.image_cache import ImageCache

_MIB = 1024 * 1024
_CPU_CACHE_BUDGET = 96 * _MIB
_GL_TEXTURE_BUDGET = 96 * _MIB
_PBO_BUDGET = 40 * _MIB
_VIRTUAL_INTERVAL_SECONDS = 40


class _EmptyOwner:
    def get_accounting_snapshot(self):
        return MappingProxyType({"resources": ()})


class _FakeGL:
    def __init__(self) -> None:
        self.deleted_textures: list[int] = []
        self.deleted_buffers: list[int] = []

    def glDeleteTextures(self, *args) -> None:
        value = args[-1]
        if isinstance(value, int):
            self.deleted_textures.append(value)
        else:
            self.deleted_textures.extend(int(item) for item in value)

    def glDeleteBuffers(self, _count, values) -> None:
        self.deleted_buffers.extend(int(item) for item in values)


def _pixmap(width: int, height: int, cycle: int) -> QPixmap:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor((cycle * 31) % 255, (cycle * 67) % 255, (cycle * 97) % 255))
    return QPixmap.fromImage(image)


def _qimage(width: int, height: int, cycle: int) -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor((cycle * 17) % 255, (cycle * 43) % 255, (cycle * 83) % 255))
    return image


def _display(index: int, compositor: Any) -> Any:
    display = SimpleNamespace(
        screen_index=index,
        current_pixmap=None,
        previous_pixmap=None,
        _seed_pixmap=None,
        _pending_transition_finish_args=None,
        _image_presenter=SimpleNamespace(
            _current_pixmap=None,
            _previous_pixmap=None,
            _seed_pixmap=None,
        ),
        _custom_layout_manager=None,
        _gl_compositor=compositor,
        _image_resource_owner=f"phase4-display:{index}",
        _image_resource_generation=1,
    )
    display.get_image_accounting_snapshot = lambda d=display: d._image_resource_accounting
    refresh_display_image_accounting(display)
    return display


def _compositor() -> Any:
    values = {"_base_pixmap": None}
    for name in (
        "crossfade", "slide", "wipe", "warp", "blockflip", "blockspin",
        "blinds", "diffuse", "raindrops", "crumble", "particle", "burn",
    ):
        values[f"_{name}"] = None
    return SimpleNamespace(**values)


def _texture_manager(fake_gl: _FakeGL, generation: int) -> GLTextureManager:
    manager = GLTextureManager(
        owner="phase4-compositor",
        generation=generation,
        max_cached_texture_bytes=_GL_TEXTURE_BUDGET,
        max_pbo_pool_bytes=_PBO_BUDGET,
    )
    next_texture = {"value": generation * 10_000 + 1}

    def _upload(pixmap: QPixmap) -> int:
        texture_id = next_texture["value"]
        next_texture["value"] += 1
        size = int(pixmap.width()) * int(pixmap.height()) * 4
        manager._texture_bytes_by_id[texture_id] = size
        manager._current_texture_bytes += size
        return texture_id

    manager.upload_pixmap = _upload
    texture_module.gl = fake_gl
    return manager


def _terminal_display_snapshot(displays: list[Any], pixmap: QPixmap) -> None:
    for display in displays:
        display.current_pixmap = pixmap
        display.previous_pixmap = None
        display._seed_pixmap = pixmap
        display._pending_transition_finish_args = None
        display._image_presenter._current_pixmap = pixmap
        display._image_presenter._previous_pixmap = None
        display._image_presenter._seed_pixmap = pixmap
        display._gl_compositor._base_pixmap = pixmap
        display._gl_compositor._crossfade = None
        refresh_display_image_accounting(display)


def _clear_displays(displays: list[Any]) -> None:
    for display in displays:
        display.current_pixmap = None
        display.previous_pixmap = None
        display._seed_pixmap = None
        display._pending_transition_finish_args = None
        display._image_presenter._current_pixmap = None
        display._image_presenter._previous_pixmap = None
        display._image_presenter._seed_pixmap = None
        display._gl_compositor._base_pixmap = None
        display._gl_compositor._crossfade = None
        refresh_display_image_accounting(display)


def run_harness(cycles: int) -> dict[str, Any]:
    app = QGuiApplication.instance() or QGuiApplication([])
    del app
    fake_gl = _FakeGL()
    cache = ImageCache(
        max_items=16,
        max_memory_mb=_CPU_CACHE_BUDGET / _MIB,
        owner="phase4-image-cache",
        generation=1,
    )
    manager = _texture_manager(fake_gl, 1)
    compositor = _compositor()
    displays = [_display(0, compositor), _display(1, compositor)]
    engine = SimpleNamespace(
        _image_cache=cache,
        resource_manager=_EmptyOwner(),
        display_manager=SimpleNamespace(displays=displays),
    )
    process = psutil.Process()
    sizes = [
        (1920, 1080),
        (3840, 2160),
        (1080, 1920),
        (2560, 1440),
        (3440, 1440),
        (1280, 720),
    ]
    records: list[dict[str, Any]] = []
    lifecycle_returns: list[dict[str, Any]] = []
    current: QPixmap | None = None
    started = time.perf_counter()

    for cycle in range(1, cycles + 1):
        width, height = sizes[(cycle - 1) % len(sizes)]
        raw = _qimage(width, height, cycle)
        scaled = _qimage(width, height, cycle + 1000)
        cache.put(f"raw:{cycle}", raw)
        cache.put(f"scaled:{cycle}", scaled)

        next_pixmap = _pixmap(width, height, cycle)
        old_pixmap = current or next_pixmap
        compositor._base_pixmap = old_pixmap
        compositor._crossfade = CrossfadeState(
            old_pixmap=old_pixmap,
            new_pixmap=next_pixmap,
            progress=0.5,
        )
        for display in displays:
            display.current_pixmap = next_pixmap
            display.previous_pixmap = old_pixmap
            display._seed_pixmap = next_pixmap
            display._pending_transition_finish_args = (
                next_pixmap, next_pixmap, f"image:{cycle}", False, None
            )
            display._image_presenter._current_pixmap = next_pixmap
            display._image_presenter._previous_pixmap = old_pixmap
            display._image_presenter._seed_pixmap = next_pixmap
            refresh_display_image_accounting(display)

        manager.prepare_transition_textures(old_pixmap, next_pixmap)
        active_resources = collect_resource_accounting(engine)
        active_gl = manager.get_stats()

        manager.release_transition_textures()
        _terminal_display_snapshot(displays, next_pixmap)
        terminal_resources = collect_resource_accounting(engine)
        terminal_gl = manager.get_stats()
        required_pbo = width * height * 4
        manager._pbo_pool.append(
            PBOEntry(cycle + 50_000, required_pbo, in_use=False)
        )
        manager._trim_pbo_pool()
        terminal_gl = manager.get_stats()
        current = next_pixmap
        if cycle % 5 == 0:
            gc.collect()

        records.append(
            {
                "cycle": cycle,
                "resolution": [width, height],
                "rss_bytes": process.memory_info().rss,
                "cache_bytes": cache.tracked_memory_usage(),
                "cache_items": cache.size(),
                "active_display_bytes": active_resources.cpu_display_bytes,
                "terminal_display_bytes": terminal_resources.cpu_display_bytes,
                "active_texture_bytes": active_gl["texture_bytes"],
                "terminal_texture_bytes": terminal_gl["texture_bytes"],
                "pbo_bytes": terminal_gl["pbo_bytes"],
            }
        )

        if cycle % 15 == 0:
            cache.clear()
            _clear_displays(displays)
            manager.cleanup(strict=True)
            stopped = collect_resource_accounting(engine)
            lifecycle_returns.append(
                {
                    "cycle": cycle,
                    "cpu_cache_bytes": stopped.cpu_cache_bytes,
                    "cpu_display_bytes": stopped.cpu_display_bytes,
                    "texture_bytes": manager.get_stats()["texture_bytes"],
                    "pbo_bytes": manager.get_stats()["pbo_bytes"],
                }
            )
            current = None
            if cycle != cycles:
                manager = _texture_manager(fake_gl, cycle // 15 + 1)
                cache = ImageCache(
                    max_items=16,
                    max_memory_mb=_CPU_CACHE_BUDGET / _MIB,
                    owner="phase4-image-cache",
                    generation=cycle // 15 + 1,
                )
                engine._image_cache = cache

    rss_tail = [item["rss_bytes"] for item in records[max(0, len(records) // 3):]]
    rss_growth = (rss_tail[-1] - rss_tail[0]) if len(rss_tail) >= 2 else 0
    rss_by_resolution: dict[tuple[int, int], list[int]] = {}
    for item in records:
        key = tuple(item["resolution"])
        rss_by_resolution.setdefault(key, []).append(item["rss_bytes"])
    repeat_drifts = [
        abs(values[-1] - values[-2])
        for values in rss_by_resolution.values()
        if len(values) >= 2
    ]
    max_repeat_drift = max(repeat_drifts, default=0)
    window_high_waters = [
        max(item["rss_bytes"] for item in records[index:index + len(sizes)])
        for index in range(0, len(records), len(sizes))
        if len(records[index:index + len(sizes)]) == len(sizes)
    ]
    tail_high_waters = window_high_waters[-3:]
    high_water_range = (
        max(tail_high_waters) - min(tail_high_waters)
        if tail_high_waters
        else 0
    )
    criteria = {
        "cpu_cache_within_byte_budget": all(
            item["cache_bytes"] <= _CPU_CACHE_BUDGET for item in records
        ),
        "texture_cache_within_byte_budget_after_terminal": all(
            item["terminal_texture_bytes"] <= _GL_TEXTURE_BUDGET for item in records
        ),
        "pbo_pool_within_byte_budget": all(
            item["pbo_bytes"] <= _PBO_BUDGET for item in records
        ),
        "terminal_display_is_single_unique_frame": all(
            item["terminal_display_bytes"] == item["resolution"][0] * item["resolution"][1] * 4
            for item in records
        ),
        "lifecycle_returns_all_owned_bytes_to_zero": all(
            all(value == 0 for key, value in item.items() if key != "cycle")
            for item in lifecycle_returns
        ),
        "rss_repeated_resolution_drift_under_8_mib": max_repeat_drift <= 8 * _MIB,
        "rss_tail_high_water_range_under_8_mib": high_water_range <= 8 * _MIB,
    }
    return {
        "schema_version": 1,
        "cycles": cycles,
        "virtual_interval_seconds": _VIRTUAL_INTERVAL_SECONDS,
        "virtual_duration_minutes": cycles * _VIRTUAL_INTERVAL_SECONDS / 60.0,
        "wall_clock_seconds": time.perf_counter() - started,
        "budgets": {
            "cpu_cache_bytes": _CPU_CACHE_BUDGET,
            "texture_cache_bytes": _GL_TEXTURE_BUDGET,
            "pbo_pool_bytes": _PBO_BUDGET,
        },
        "rss": {
            "first_bytes": records[0]["rss_bytes"] if records else 0,
            "last_bytes": records[-1]["rss_bytes"] if records else 0,
            "tail_growth_bytes_unadjusted_for_resolution": rss_growth,
            "tail_min_bytes": min(rss_tail) if rss_tail else 0,
            "tail_max_bytes": max(rss_tail) if rss_tail else 0,
            "max_repeated_resolution_drift_bytes": max_repeat_drift,
            "tail_high_water_range_bytes": high_water_range,
            "window_high_waters_bytes": window_high_waters,
        },
        "coverage": {
            "alternating_large_small": True,
            "portrait_landscape_ultrawide": True,
            "active_transition": True,
            "two_display_shared_backing": True,
            "modeled_full_owner_resets": len(lifecycle_returns),
            "driver_vram": "unsupported_in_deterministic_offscreen_harness",
        },
        "pass_criteria": criteria,
        "passed": all(criteria.values()),
        "lifecycle_returns": lifecycle_returns,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=45)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_harness(max(1, args.cycles))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "passed": report["passed"],
        "cycles": report["cycles"],
        "virtual_duration_minutes": report["virtual_duration_minutes"],
        "rss_repeat_drift_bytes": report["rss"]["max_repeated_resolution_drift_bytes"],
        "pass_criteria": report["pass_criteria"],
    }, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())