from __future__ import annotations

from types import MappingProxyType, SimpleNamespace
from unittest.mock import MagicMock

from PySide6.QtGui import QImage, QPixmap

from core.performance.resource_metrics import collect_resource_accounting
from engine.screensaver_engine import ScreensaverEngine
from rendering.gl_programs import texture_manager as texture_module
from rendering.gl_programs.texture_manager import GLTextureManager, PBOEntry
from rendering.image_resource_accounting import (
    aggregate_display_image_accounting,
    get_display_image_accounting,
    refresh_display_image_accounting,
)
from rendering.transition_state import BurnState, CrossfadeState, ParticleState
from rendering.gl_compositor_pkg.transition_lifecycle import cancel_current_transition


class _EmptyOwner:
    def get_accounting_snapshot(self):
        return MappingProxyType({"resources": ()})


def test_missing_display_accounting_snapshot_is_read_only_and_empty():
    display = SimpleNamespace()

    snapshot = get_display_image_accounting(display)

    assert snapshot["resources"] == ()
    assert snapshot["total_tracked_bytes"] == 0
    assert not hasattr(display, "_image_resource_accounting")


def _seed_texture_cache(manager: GLTextureManager, sizes: list[int]) -> None:
    manager._texture_cache = {index: 100 + index for index in range(1, len(sizes) + 1)}
    manager._texture_lru = list(manager._texture_cache)
    manager._texture_bytes_by_id = {
        texture_id: size
        for texture_id, size in zip(manager._texture_cache.values(), sizes)
    }
    manager._current_texture_bytes = sum(sizes)


def test_engine_clamps_legacy_cache_and_prefetch_budgets():
    configured = {
        "cache.max_items": 999,
        "cache.max_memory_mb": 4096,
        "cache.max_concurrent": 99,
    }
    engine = SimpleNamespace(
        settings_manager=SimpleNamespace(
            get=lambda key, default=None: configured.get(key, default)
        ),
        thread_manager=object(),
        _prefetch_ahead=5,
        _image_cache=None,
        _prefetcher=None,
    )

    ScreensaverEngine._initialize_cache_prefetcher(engine)

    assert engine._image_cache.max_items == 32
    assert engine._image_cache.max_memory_bytes == 256 * 1024 * 1024
    assert engine._prefetcher._max_concurrent == 4

def test_texture_cache_evicts_by_exact_bytes_and_preserves_active_pair(monkeypatch):
    fake_gl = MagicMock()
    monkeypatch.setattr(texture_module, "gl", fake_gl)
    manager = GLTextureManager(max_cached_texture_bytes=100)
    _seed_texture_cache(manager, [60, 60, 60])
    manager._old_tex_id = 101
    manager._new_tex_id = 102

    manager._evict_cache_to_budget(protected_ids={101, 102})

    assert set(manager._texture_cache.values()) == {101, 102}
    assert manager._current_texture_bytes == 120
    manager.release_transition_textures()
    assert manager._current_texture_bytes == 60
    assert len(manager._texture_cache) == 1
    assert fake_gl.glDeleteTextures.call_count == 2


def test_texture_cache_count_never_substitutes_for_byte_budget(monkeypatch):
    fake_gl = MagicMock()
    monkeypatch.setattr(texture_module, "gl", fake_gl)
    manager = GLTextureManager(max_cached_texture_bytes=100)
    _seed_texture_cache(manager, [80, 80])

    manager._evict_cache_to_budget()

    assert len(manager._texture_cache) == 1
    assert manager.get_stats()["texture_bytes"] == 80
    assert manager.get_stats()["texture_bytes"] <= manager.get_stats()["max_texture_bytes"]


def test_terminal_transition_retires_history_and_retains_destination(monkeypatch):
    fake_gl = MagicMock()
    monkeypatch.setattr(texture_module, "gl", fake_gl)
    manager = GLTextureManager(max_cached_texture_bytes=1024)
    _seed_texture_cache(manager, [60, 60, 60, 60])
    manager._old_tex_id = 103
    manager._new_tex_id = 104
    manager._release_resource_tracking = MagicMock()
    manager._pbo_pool = [PBOEntry(200, 240, resource_id="pbo")]

    manager.release_transition_textures(retain_active="new")

    assert list(manager._texture_cache.values()) == [104]
    assert manager._current_texture_bytes == 60
    assert manager.get_stats()["terminal_textures_reclaimed"] == 3
    assert manager.get_stats()["terminal_pbos_reclaimed"] == 1
    assert manager.get_stats()["pbo_count"] == 0
    assert fake_gl.glDeleteTextures.call_count == 3
    fake_gl.glDeleteBuffers.assert_called_once_with(1, [200])
    assert manager._release_resource_tracking.call_args_list[-1].args == ("pbo",)


def test_cancel_retains_base_side_selected_by_snap_policy(qt_app):
    old = QPixmap.fromImage(QImage(8, 8, QImage.Format.Format_ARGB32))
    new = QPixmap.fromImage(QImage(9, 9, QImage.Format.Format_ARGB32))
    keep_new = _transition_widget(
        "particle",
        ParticleState(old_pixmap=old, new_pixmap=new),
    )
    keep_old = _transition_widget(
        "particle",
        ParticleState(old_pixmap=old, new_pixmap=new),
    )

    cancel_current_transition(keep_new, snap_to_new=True)
    cancel_current_transition(keep_old, snap_to_new=False)

    keep_new._release_transition_textures.assert_called_once_with(
        retain_active="new"
    )
    keep_old._release_transition_textures.assert_called_once_with(
        retain_active="old"
    )


def test_pbo_pool_retains_only_one_idle_buffer_inside_byte_cap(monkeypatch):
    fake_gl = MagicMock()
    monkeypatch.setattr(texture_module, "gl", fake_gl)
    manager = GLTextureManager(max_pbo_pool_bytes=5000)
    manager._release_resource_tracking = MagicMock()
    manager._pbo_pool = [
        PBOEntry(1, 1024, resource_id="one"),
        PBOEntry(2, 4096, resource_id="two"),
        PBOEntry(3, 8192, resource_id="three"),
    ]

    manager._trim_pbo_pool()

    assert [(entry.pbo_id, entry.size) for entry in manager._pbo_pool] == [(2, 4096)]
    assert fake_gl.glDeleteBuffers.call_count == 2
    assert manager.get_stats()["pbo_bytes"] <= manager.get_stats()["max_pbo_bytes"]


def _transition_widget(state_name: str, state):
    values = {
        "_animation_manager": None,
        "_current_anim_id": None,
        "_crossfade": None,
        "_slide": None,
        "_wipe": None,
        "_warp": None,
        "_blockflip": None,
        "_blockspin": None,
        "_blinds": None,
        "_diffuse": None,
        "_raindrops": None,
        "_crumble": None,
        "_particle": None,
        "_burn": None,
        "_base_pixmap": None,
        "_release_transition_textures": MagicMock(),
        "update": MagicMock(),
    }
    values[f"_{state_name}"] = state
    return SimpleNamespace(**values)


def test_cancel_releases_particle_and_burn_pixmaps(qt_app):
    old = QPixmap.fromImage(QImage(8, 8, QImage.Format.Format_ARGB32))
    particle_new = QPixmap.fromImage(QImage(9, 9, QImage.Format.Format_ARGB32))
    burn_new = QPixmap.fromImage(QImage(10, 10, QImage.Format.Format_ARGB32))

    particle = _transition_widget("particle", ParticleState(old_pixmap=old, new_pixmap=particle_new))
    cancel_current_transition(particle, snap_to_new=True)
    assert particle._base_pixmap.cacheKey() == particle_new.cacheKey()
    assert particle._particle is None
    particle._release_transition_textures.assert_called_once()

    burn = _transition_widget("burn", BurnState(old_pixmap=old, new_pixmap=burn_new))
    cancel_current_transition(burn, snap_to_new=True)
    assert burn._base_pixmap.cacheKey() == burn_new.cacheKey()
    assert burn._burn is None
    burn._release_transition_textures.assert_called_once()


def test_display_accounting_deduplicates_alias_roles_and_displays(qt_app):
    pixmap = QPixmap.fromImage(QImage(64, 32, QImage.Format.Format_ARGB32))
    state = CrossfadeState(old_pixmap=pixmap, new_pixmap=pixmap)
    compositor = SimpleNamespace(
        _base_pixmap=pixmap,
        _crossfade=state,
        _slide=None,
        _wipe=None,
        _warp=None,
        _blockflip=None,
        _blockspin=None,
        _blinds=None,
        _diffuse=None,
        _raindrops=None,
        _crumble=None,
        _particle=None,
        _burn=None,
    )

    displays = []
    for index in range(2):
        display = SimpleNamespace(
            screen_index=index,
            current_pixmap=pixmap,
            previous_pixmap=pixmap,
            _seed_pixmap=pixmap,
            _pending_transition_finish_args=(pixmap, pixmap, "path", False, None),
            _image_presenter=SimpleNamespace(
                _current_pixmap=pixmap,
                _previous_pixmap=pixmap,
                _seed_pixmap=pixmap,
            ),
            _custom_layout_manager=None,
            _gl_compositor=compositor,
            _image_resource_owner=f"display:{index}",
            _image_resource_generation=7,
        )
        refresh_display_image_accounting(display)
        display.get_image_accounting_snapshot = lambda d=display: d._image_resource_accounting
        displays.append(display)

    first = displays[0]._image_resource_accounting
    assert first["resource_count"] == 1
    assert len(first["resources"][0]["roles"]) >= 8

    engine = SimpleNamespace(
        _image_cache=_EmptyOwner(),
        resource_manager=_EmptyOwner(),
        display_manager=SimpleNamespace(
            displays=displays,
            get_image_accounting_snapshot=lambda: aggregate_display_image_accounting(
                (display._image_resource_accounting for display in displays),
                generation=7,
            ),
        ),
    )
    snapshot = collect_resource_accounting(engine)
    expected = 64 * 32 * ((pixmap.depth() + 7) // 8)
    assert snapshot.cpu_display_resources == 1
    assert snapshot.cpu_display_bytes == expected
    assert snapshot.known_tracked_bytes == expected
