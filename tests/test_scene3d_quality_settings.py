"""The 3D Detail tiers (H2): one resolver over General / family / entry levels, Auto by GPU class,
the retired ``transitions.detail_3d`` promoted once at the input seams, the 3D Settings tab writing
only its own level, and the transition request carrying the resolved tier."""
from __future__ import annotations

import json
import uuid

import pytest

from core.settings.scene3d_detail_input_compat import (
    LEGACY_TRANSITIONS_DETAIL_KEY,
    SCENE3D_TRANSITIONS_DETAIL_KEY,
)
from core.settings.scene3d_quality import (
    SCENE3D_ENTRY_CHOICES,
    SCENE3D_FAMILY_CHOICES,
    SCENE3D_GENERAL_CHOICES,
    classify_gpu,
    resolve_scene3d_tier,
    scene3d_auto_tier,
)
from core.settings.settings_manager import SettingsManager
from rendering.gl_programs.scene3d import SCENE3D_DETAIL_NAMES

DISCRETE = ("NVIDIA Corporation", "NVIDIA GeForce RTX 4090/PCIe/SSE2")


def test_each_level_follows_the_one_above_unless_it_sets_its_own():
    assert SCENE3D_GENERAL_CHOICES[0] == "Auto" and SCENE3D_FAMILY_CHOICES[0] == "General"
    assert SCENE3D_ENTRY_CHOICES[0] == "Auto"
    for general in SCENE3D_DETAIL_NAMES:
        for family in ("General", *SCENE3D_DETAIL_NAMES):
            for entry in ("Auto", *SCENE3D_DETAIL_NAMES):
                section = {"detail": general, "visualizers_detail": family, "shockwave_grid_detail": entry}
                expected = entry if entry != "Auto" else family if family != "General" else general
                assert resolve_scene3d_tier(section, "visualizers", "shockwave_grid", gpu=DISCRETE) == expected
    # Auto at the top resolves by the GPU; families stay independent of each other.
    section = {"detail": "Auto", "transitions_detail": "KAK", "visualizers_detail": "General"}
    assert resolve_scene3d_tier(section, "transitions") == "KAK"
    assert resolve_scene3d_tier(section, "visualizers", gpu=DISCRETE) == scene3d_auto_tier(DISCRETE)
    # A malformed stored value means what its default means: follow the level above.
    section = {"detail": "Ultra", "visualizers_detail": 3, "shockwave_grid_detail": None}
    assert resolve_scene3d_tier(section, "visualizers", "shockwave_grid", gpu=None) == scene3d_auto_tier(None)
    with pytest.raises(ValueError):
        resolve_scene3d_tier({}, "sounds")


@pytest.mark.parametrize(("vendor", "renderer", "kind"), [
    DISCRETE + ("discrete",),
    ("ATI Technologies Inc.", "AMD Radeon RX 7900 XTX", "discrete"),
    ("ATI Technologies Inc.", "AMD Radeon(TM) Graphics", "integrated"),
    ("Intel", "Intel(R) UHD Graphics 770", "integrated"),
    ("Intel", "Intel(R) Arc(TM) Graphics", "integrated"),
    ("Intel", "Intel(R) Arc(TM) A770 Graphics", "discrete"),
    ("Microsoft Corporation", "GDI Generic", "software"),
    ("Mesa", "llvmpipe (LLVM 15.0.7, 256 bits)", "software"),
])
def test_auto_follows_the_gpu_class(vendor, renderer, kind):
    assert classify_gpu(vendor, renderer) == kind
    tier = scene3d_auto_tier((vendor, renderer))
    assert tier in SCENE3D_DETAIL_NAMES
    order = list(SCENE3D_DETAIL_NAMES)
    if kind == "integrated":
        assert order.index(tier) > order.index(scene3d_auto_tier(DISCRETE))
    if kind == "software":
        assert order.index(tier) > order.index(scene3d_auto_tier(("Intel", "Intel(R) UHD Graphics 770")))


def _manager(tmp_path, name: str) -> SettingsManager:
    return SettingsManager(organization="Test", application=f"scene3d_{name}_{uuid.uuid4().hex}",
                           storage_base_dir=tmp_path / name)


def _reload(manager, tmp_path, name):
    return SettingsManager(organization=manager.get_organization_name(),
                           application=manager.get_application_name(), storage_base_dir=tmp_path / name)


@pytest.mark.parametrize(("legacy", "expected"), [
    ("Balanced", "Balanced"), ("Performance", "Performance"),
    ("High", None), ("Ultra", None),       # the old default, and nonsense: follow General
])
def test_a_profile_promotes_the_retired_transitions_tier_once(tmp_path, legacy, expected):
    manager = _manager(tmp_path, "profile")
    canonical = manager.get(SCENE3D_TRANSITIONS_DETAIL_KEY)
    with manager._lock:
        manager._settings.remove(SCENE3D_TRANSITIONS_DETAIL_KEY)
        manager._settings.setValue(LEGACY_TRANSITIONS_DETAIL_KEY, legacy)
        manager._settings.sync()
    reloaded = _reload(manager, tmp_path, "profile")
    assert reloaded.get(SCENE3D_TRANSITIONS_DETAIL_KEY) == (expected or canonical)
    assert reloaded._settings.contains(LEGACY_TRANSITIONS_DETAIL_KEY) is False
    with pytest.raises(KeyError, match="Retired setting key"):
        reloaded.get(LEGACY_TRANSITIONS_DETAIL_KEY)
    again = _reload(reloaded, tmp_path, "profile")                      # idempotent
    assert again.get(SCENE3D_TRANSITIONS_DETAIL_KEY) == (expected or canonical)


def test_a_current_family_tier_wins_over_the_retired_one(tmp_path):
    manager = _manager(tmp_path, "current")
    with manager._lock:
        manager._settings.setValue(SCENE3D_TRANSITIONS_DETAIL_KEY, "KAK")
        manager._settings.setValue(LEGACY_TRANSITIONS_DETAIL_KEY, "Balanced")
        manager._settings.sync()
    assert _reload(manager, tmp_path, "current").get(SCENE3D_TRANSITIONS_DETAIL_KEY) == "KAK"


def test_an_sst_import_promotes_the_retired_tier(tmp_path):
    from core.settings.sst_io import import_from_sst

    manager = _manager(tmp_path, "sst")
    snapshot = tmp_path / "old.sst"
    snapshot.write_text(json.dumps({"snapshot": {"transitions": {"detail_3d": "Performance"}}}), encoding="utf-8")
    assert import_from_sst(manager, str(snapshot), merge=True) is True
    assert manager.get(SCENE3D_TRANSITIONS_DETAIL_KEY) == "Performance"
    assert "detail_3d" not in manager.get("transitions")
    explicit = tmp_path / "both.sst"
    explicit.write_text(json.dumps({"snapshot": {"transitions": {"detail_3d": "Performance"},
                                                 "scene3d": {"transitions_detail": "High"}}}), encoding="utf-8")
    assert import_from_sst(manager, str(explicit), merge=True) is True
    assert manager.get(SCENE3D_TRANSITIONS_DETAIL_KEY) == "High"


def test_a_transition_request_carries_the_tier_resolved_from_the_3d_settings(tmp_path):
    from rendering.quick.transitions.request_resolution import resolve_quick_transition_spec

    manager = _manager(tmp_path, "request")
    transitions = dict(manager.get("transitions"))
    transitions.update({"type": "Exploding Tiles", "random_always": False,
                        "activation": {**dict(transitions.get("activation") or {}), "Exploding Tiles": True}})
    manager.set("transitions", transitions)
    for general, family, expected in (("Balanced", "General", "Balanced"), ("Balanced", "KAK", "KAK")):
        manager.set("scene3d.detail", general)
        manager.set("scene3d.transitions_detail", family)
        spec = resolve_quick_transition_spec(manager)
        assert spec is not None and spec.transition_id == "exploding_tiles"
        assert dict(spec.parameters)["detail"] == expected


@pytest.mark.qt
def test_the_tab_writes_only_its_own_level_and_shows_what_resolves(qt_app, tmp_path):
    from ui.tabs.scene3d_tab import PAGES, Scene3DTab, scene3d_visualizer_entries

    manager = _manager(tmp_path, "tab")
    tab = Scene3DTab(manager)
    try:
        assert [key for key, _label in PAGES] == ["general", "transitions", "visualizers"]
        entries = dict(scene3d_visualizer_entries())
        assert {"extruded_spectrum", "shockwave_grid"} <= set(entries)
        before = {key: manager.get(f"scene3d.{key}") for key in tab._combos}
        combo = tab._combos["visualizers_detail"]
        combo.setCurrentIndex(combo.findData("Performance"))
        after = {key: manager.get(f"scene3d.{key}") for key in tab._combos}
        assert after == {**before, "visualizers_detail": "Performance"}
        assert tab._now_labels["shockwave_grid_detail"].text() == "Now: Performance"   # inherits
        entry = tab._combos["shockwave_grid_detail"]
        entry.setCurrentIndex(entry.findData("High"))
        assert manager.get("scene3d.shockwave_grid_detail") == "High"
        assert tab._now_labels["shockwave_grid_detail"].text() == "Now: High"
        assert tab._now_labels["extruded_spectrum_detail"].text() == "Now: Performance"
        tab.show_page("visualizers")
        assert tab._pages["visualizers"].isVisibleTo(tab) and not tab._pages["general"].isVisibleTo(tab)
        # A reload shows what is stored.
        manager.set("scene3d.detail", "KAK")
        tab.load_from_settings()
        assert tab._combos["detail"].currentData() == "KAK"
    finally:
        tab.deleteLater()


def test_an_activation_carries_each_modes_tier_from_the_3d_settings(tmp_path):
    from types import SimpleNamespace

    from core.settings.models import SpotifyVisualizerSettings
    from engine.display_manager import DisplayManager
    from widgets.spotify_visualizer.config_applier import (
        apply_presentation_vis_mode_kwargs,
        extruded_spectrum_parameters,
        shockwave_grid_parameters,
    )

    manager = _manager(tmp_path, "activation")
    manager.set("scene3d.detail", "Balanced")
    manager.set("scene3d.visualizers_detail", "Performance")
    manager.set("scene3d.shockwave_grid_detail", "KAK")
    display = SimpleNamespace(settings_manager=manager)
    model = SpotifyVisualizerSettings()
    kwargs = {mode: DisplayManager._visualizer_presentation_kwargs(display, model, mode)
              for mode in ("extruded_spectrum", "shockwave_grid", "spectrum")}
    assert kwargs["extruded_spectrum"]["scene3d_detail"] == "Performance"      # follows its family
    assert kwargs["shockwave_grid"]["scene3d_detail"] == "KAK"                 # its own entry
    assert kwargs["spectrum"]["scene3d_detail"] == "Performance"
    for mode, parameters in (("extruded_spectrum", extruded_spectrum_parameters),
                             ("shockwave_grid", shockwave_grid_parameters)):
        host = SimpleNamespace(_view_orbit_motion=None)
        apply_presentation_vis_mode_kwargs(host, kwargs[mode])
        assert parameters(host)["scene3d_detail"] == kwargs[mode]["scene3d_detail"]


@pytest.fixture
def render_rig(qt_app):
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tests.test_qtquick_extruded_spectrum import _Target

    target = _Target()
    host = QuickVisualizerRenderHost()
    yield target, host
    host.release_resources()
    target.close()


def _snapshot(mode, **parameters):
    import dataclasses

    from tests.test_qtquick_extruded_spectrum import H, W
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot

    snapshot = _build_spectrum_preview_snapshot(width=W, height=H, mode=mode)
    state = snapshot.logical.mode_state
    state = dataclasses.replace(state, parameters={**dict(state.parameters), **parameters})
    return dataclasses.replace(snapshot, logical=dataclasses.replace(snapshot.logical, mode_state=state))


@pytest.mark.qt
@pytest.mark.parametrize("tier", SCENE3D_DETAIL_NAMES)
def test_a_3d_visualizer_draws_with_its_tiers_levers(render_rig, tier):
    from rendering.gl_programs.scene3d import scene3d_detail
    from rendering.gl_programs.shockwave_grid_program import shockwave_grid_cells

    target, host = render_rig
    detail = scene3d_detail(tier)
    for smooth in (False, True):
        target.render(host, _snapshot("extruded_spectrum", scene3d_detail=tier, extruded_spectrum_smooth_edges=smooth,
                                      extruded_spectrum_face_mirror=0.6))
        extruded = host._implementations["extruded_spectrum"]
        expected = max(1, detail.overlay_samples * (2 if smooth else 1))
        assert extruded._target.allocation[2] == expected, (tier, smooth)
        assert extruded._backdrop.has_resources == bool(detail.backdrop_refresh)   # Mirror Faces off at KAK
    target.render(host, _snapshot("shockwave_grid", scene3d_detail=tier, shockwave_grid_glow=0.8))
    shockwave = host._implementations["shockwave_grid"]
    assert shockwave._target.allocation[2] == max(1, detail.overlay_samples)
    assert bool(shockwave._target._names["emission"]) == detail.post_effects        # glow only with post effects
    columns, rows = shockwave_grid_cells(detail.grid_cells)
    assert shockwave._resources.has_mesh(f"grid {columns}x{rows}")
