from __future__ import annotations

import importlib.util
import pytest
from pathlib import Path

from core.settings.visualizer_mode_registry import (
    get_owned_mode_setting_keys,
    get_resolved_mode_setting_keys,
    get_resolved_mode_setting_profile,
    get_technical_profile_mode,
    mode_has_rainbow_controls,
    mode_has_shared_bar_appearance,
    get_visualizer_mode_descriptor,
    iter_all_visualizer_mode_descriptors,
)


def _load_technical_config_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "widgets/spotify_visualizer/technical_config.py"
    )
    spec = importlib.util.spec_from_file_location("_srpss_technical_config_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sphere_declares_reference_technical_profile_without_technical_ui() -> None:
    descriptor = get_visualizer_mode_descriptor("sphere")
    assert descriptor.technical_controls is False
    assert descriptor.rainbow_controls is False
    assert mode_has_rainbow_controls("sphere") is False
    assert descriptor.shared_bar_appearance is False
    assert mode_has_shared_bar_appearance("sphere") is False
    assert get_owned_mode_setting_keys("sphere", "shared_bar") == {}
    assert get_resolved_mode_setting_profile("sphere", "shared_bar") == "spectrum"
    assert get_technical_profile_mode("sphere") == "spectrum"


def test_normal_modes_resolve_their_own_technical_profile() -> None:
    for descriptor in iter_all_visualizer_mode_descriptors():
        if descriptor.technical_controls:
            assert get_technical_profile_mode(descriptor.mode_id) == descriptor.mode_id


def test_technical_cache_resolution_is_descriptor_driven() -> None:
    technical_config = _load_technical_config_module()
    spectrum = {"bar_count": 24, "sentinel": object()}
    cache = {"spectrum": spectrum}
    assert technical_config.resolve_technical_config(cache, "sphere") is spectrum


def test_rejected_smooth_sphere_settings_are_not_canonical_defaults() -> None:
    import json
    from core.settings.default_settings import DEFAULT_SETTINGS

    snapshot_path = Path(__file__).resolve().parents[1] / "core/settings/defaults_snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert DEFAULT_SETTINGS == snapshot
    sphere_defaults = DEFAULT_SETTINGS["widgets"]["spotify_visualizer"]
    assert sphere_defaults["sphere_shadow_enabled"] is True
    for key in (
        "sphere_antialiasing",
        "sphere_shadow_strength",
        "sphere_rainbow_enabled",
        "sphere_rainbow_speed",
        "sphere_rainbow_ghosting",
        "sphere_idle_motion",
        "sphere_surface_detail",
        "sphere_bass_response",
        "sphere_mid_response",
        "sphere_high_response",
        "sphere_energy_curve",
        "sphere_deformation",
        "sphere_bump_reactivity",
    ):
        assert key not in sphere_defaults


def test_rejected_smooth_sphere_keys_are_forward_stripped() -> None:
    from core.settings.visualizer_retired_modes import strip_retired_visualizer_settings

    cleaned = strip_retired_visualizer_settings(
        {
            "mode": "sphere",
            "sphere_deformation": 1.25,
            "sphere_bump_reactivity": 1.4,
            "sphere_antialiasing": True,
            "sphere_shadow_enabled": True,
            "sphere_shadow_strength": 0.7,
            "sphere_rainbow_enabled": True,
            "sphere_rainbow_speed": 1.5,
            "sphere_rainbow_ghosting": True,
            "sphere_idle_motion": 0.7,
            "sphere_surface_detail": 1.6,
            "sphere_bass_response": 1.8,
            "sphere_mid_response": 1.7,
            "sphere_high_response": 1.5,
            "sphere_energy_curve": 0.4,
        }
    )
    assert cleaned == {"mode": "sphere", "sphere_shadow_enabled": True}


def test_legacy_sphere_response_controls_migrate_without_retuning() -> None:
    from core.settings.visualizer_settings_contract import migrate_legacy_sphere_control_keys

    migrated = migrate_legacy_sphere_control_keys({
        "sphere_deformation": 2.25,
        "sphere_bump_reactivity": 1.60,
        "sphere_shadow_enabled": False,
    })
    assert migrated["sphere_fragment_strength"] == 3.60
    assert migrated["sphere_particle_distance"] == 2.25
    assert migrated["sphere_shadow_enabled"] is False
    assert "sphere_deformation" not in migrated
    assert "sphere_bump_reactivity" not in migrated

    partial = migrate_legacy_sphere_control_keys({"sphere_deformation": 2.0})
    assert partial["sphere_fragment_strength"] == 1.70
    assert partial["sphere_particle_distance"] == 2.0


def test_schema_v8_migrates_cached_custom_sphere_payload_too() -> None:
    from core.settings.visualizer_presets import normalize_visualizer_custom_snapshot_cache

    cache = normalize_visualizer_custom_snapshot_cache({
        "sphere": {
            "mode": "sphere",
            "sphere_deformation": 2.45,
            "sphere_bump_reactivity": 1.60,
            "sphere_vocal_response": 1.45,
        }
    })
    sphere = cache["sphere"]
    assert sphere["sphere_fragment_strength"] == pytest.approx(3.92)
    assert sphere["sphere_particle_distance"] == 2.45
    assert sphere["sphere_vocal_response"] == 1.35
    assert "sphere_deformation" not in sphere
    assert "sphere_bump_reactivity" not in sphere


def test_sphere_descriptor_points_only_at_voxel_renderer() -> None:
    descriptor = get_visualizer_mode_descriptor("sphere")
    assert descriptor.renderer_module == "rendering.quick.visualizer.implementations.sphere_voxel"
    root = Path(__file__).resolve().parents[1]
    assert not (root / "rendering/quick/visualizer/implementations/sphere.py").exists()


def test_canonical_defaults_normalize_without_synthesizing_retired_sphere_rainbow_keys() -> None:
    # This is an import-time boot contract: defaults.py resolves and normalizes
    # canonical visualizer defaults while the application module graph imports.
    # A disabled/experimental mode that opts out of Rainbow must therefore not
    # make the normalizer require keys the product schema intentionally removed.
    from core.settings.defaults import CANONICAL_DEFAULTS, get_default_settings

    visualizer = CANONICAL_DEFAULTS["widgets"]["spotify_visualizer"]
    assert "sphere_rainbow_enabled" not in visualizer
    assert "sphere_rainbow_speed" not in visualizer
    assert visualizer["sphere_fragment_strength"] == 1.1475
    assert visualizer["sphere_particle_distance"] == 1.35
    assert visualizer["sphere_particle_amount"] == 1.0
    assert visualizer["sphere_perspective_strength"] == 1.0
    assert visualizer["sphere_taste_the_rainbow_enabled"] is False
    assert get_default_settings() == CANONICAL_DEFAULTS


def test_rainbow_capability_matches_canonical_default_key_ownership() -> None:
    """Mode capability may gate UI/normalization, never invent persisted defaults.

    Canonical DEFAULT_SETTINGS remains the single authority for persisted product
    values.  The descriptor's capability bit must agree with the presence of the
    corresponding canonical keys so an experimental mode cannot silently split
    Settings authority again.
    """
    from core.settings.default_settings import DEFAULT_SETTINGS

    visualizer = DEFAULT_SETTINGS["widgets"]["spotify_visualizer"]
    for descriptor in iter_all_visualizer_mode_descriptors():
        enabled_key = f"{descriptor.mode_id}_rainbow_enabled"
        speed_key = f"{descriptor.mode_id}_rainbow_speed"
        assert (enabled_key in visualizer) is descriptor.rainbow_controls
        assert (speed_key in visualizer) is descriptor.rainbow_controls


def test_shared_bar_appearance_capability_matches_canonical_default_key_ownership() -> None:
    """Descriptor capability must match canonical persisted bar-appearance keys.

    Like Rainbow capability, this metadata only tells generic Settings/migration
    consumers whether a mode participates. It is never a source of values.
    """
    from core.settings.default_settings import DEFAULT_SETTINGS

    visualizer = DEFAULT_SETTINGS["widgets"]["spotify_visualizer"]
    suffixes = ("bar_fill_color", "bar_border_color", "bar_border_opacity")
    for descriptor in iter_all_visualizer_mode_descriptors():
        for suffix in suffixes:
            key = f"{descriptor.mode_id}_{suffix}"
            assert (key in visualizer) is descriptor.shared_bar_appearance


def test_legacy_shared_bar_migration_does_not_synthesize_sphere_keys() -> None:
    from core.settings.visualizer_settings_contract import migrate_legacy_global_visual_keys

    migrated = migrate_legacy_global_visual_keys({
        "bar_fill_color": [1, 2, 3, 4],
        "bar_border_color": [5, 6, 7, 8],
        "bar_border_opacity": 0.4,
    })
    assert "sphere_bar_fill_color" not in migrated
    assert "sphere_bar_border_color" not in migrated
    assert "sphere_bar_border_opacity" not in migrated
    for mode in ("spectrum", "bubble", "sine_wave", "oscilloscope", "devcurve"):
        assert migrated[f"{mode}_bar_fill_color"] == [1, 2, 3, 4]
        assert migrated[f"{mode}_bar_border_color"] == [5, 6, 7, 8]
        assert migrated[f"{mode}_bar_border_opacity"] == 0.4


class _FakeToggle:
    def __init__(self, checked: bool = False) -> None:
        self._checked = checked

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        self._checked = bool(checked)


class _FakeSlider:
    def __init__(self, value: int = 50) -> None:
        self._value = value

    def value(self) -> int:
        return self._value

    def setValue(self, value: int) -> None:
        self._value = int(value)


class _FakeLabel:
    def setText(self, _text: str) -> None:
        pass


class _FakeRainbowTab:
    def __init__(self, mode: str = "sphere") -> None:
        self._active_visualizer_mode_id = mode
        self._rainbow_per_mode = {}
        self.rainbow_enabled = _FakeToggle(True)
        self.rainbow_speed_slider = _FakeSlider(77)
        self.rainbow_speed_label = _FakeLabel()
        self.visibility_updates = 0

    def _get_active_visualizer_mode(self) -> str:
        return self._active_visualizer_mode_id

    def _config_bool(self, _section, config, key) -> bool:
        return bool(config.get(key, False))

    def _config_float(self, _section, config, key) -> float:
        return float(config.get(key, 0.5))

    def _default_bool(self, _section, key) -> bool:
        assert not key.startswith("sphere_rainbow"), key
        return False

    def _default_float(self, _section, key) -> float:
        assert not key.startswith("sphere_rainbow"), key
        return 0.5

    def _update_rainbow_visibility(self) -> None:
        self.visibility_updates += 1


def test_sphere_rainbow_ui_binding_never_requires_or_persists_retired_keys() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "ui/tabs/media/visualizer_mode_binding.py"
    )
    spec = importlib.util.spec_from_file_location("_srpss_visualizer_mode_binding_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    tab = _FakeRainbowTab("sphere")
    module.load_visualizer_rainbow_state(
        tab,
        {
            "rainbow_enabled": False,
            "rainbow_speed": 0.15,
            "spectrum_rainbow_enabled": False,
            "spectrum_rainbow_speed": 0.5,
        },
    )
    assert "sphere" not in tab._rainbow_per_mode
    assert tab.visibility_updates == 1

    saved = {}
    module.collect_visualizer_rainbow_state(tab, saved)
    assert "sphere_rainbow_enabled" not in saved
    assert "sphere_rainbow_speed" not in saved
    assert "sphere" not in tab._rainbow_per_mode


def _load_widgets_tab_media_functions(*names: str):
    """Load selected pure/early-exit functions without importing PySide6.

    The production module is Qt-heavy, but these contract tests need to prove
    that experimental mode selection/save does not even *request* canonical
    keys the descriptor says the mode does not own. Extracting the exact
    function AST keeps the test bound to production source without inventing a
    fake duplicate implementation.
    """
    import ast

    path = Path(__file__).resolve().parents[1] / "ui/tabs/widgets_tab_media.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    selected = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names
    ]
    assert {node.name for node in selected} == set(names)
    module = ast.Module(body=selected, type_ignores=[])
    code = compile(ast.fix_missing_locations(module), str(path), "exec")
    namespace: dict[str, object] = {}
    exec(code, namespace)
    return namespace


class _FakeChecked:
    def __init__(self, checked: bool) -> None:
        self._checked = checked

    def isChecked(self) -> bool:
        return self._checked


class _FakeVisualSaveTab:
    def __init__(self) -> None:
        self.vis_enabled_checkbox = _FakeChecked(True)

    def _default_bool(self, _section: str, key: str) -> bool:
        assert not key.startswith("sphere_bar_"), key
        return False

    def _default_float(self, _section: str, key: str) -> float:
        assert not key.startswith("sphere_bar_"), key
        return 0.15


class _NoSphereAppearanceDefaultTab:
    def _widget_default(self, _section: str, key: str):
        raise AssertionError(f"Sphere selection requested non-owned appearance default: {key}")


def test_sphere_shared_bar_appearance_ui_load_and_save_do_not_touch_retired_keys() -> None:
    functions = _load_widgets_tab_media_functions(
        "load_shared_visualizer_appearance_settings",
        "save_visualizer_settings",
    )
    loader = functions["load_shared_visualizer_appearance_settings"]
    saver = functions["save_visualizer_settings"]

    # Inject only the globals those exact production functions need on the Sphere
    # paths. A regression that reaches QColor/default access will fail loudly.
    loader.__globals__.update({
        "get_owned_mode_setting_keys": get_owned_mode_setting_keys,
    })
    loader(_NoSphereAppearanceDefaultTab(), {}, "sphere")

    saver.__globals__.update({
        "get_owned_mode_setting_keys": get_owned_mode_setting_keys,
        "collect_visualizer_mode_selection": lambda _tab: "sphere",
        "collect_visualizer_rainbow_state": lambda _tab, _cfg: None,
        "collect_per_mode_technical_controls": lambda _tab, _cfg, current_mode=None: None,
        "collect_visualizer_preset_indices": lambda _tab, _cfg: None,
        "_VIS_MODE_CONTAINER_ATTR": {"sphere": "_sphere_settings_container"},
    })
    saved = saver(_FakeVisualSaveTab())
    assert saved["mode"] == "sphere"
    assert not any(key.startswith("sphere_bar_") for key in saved), saved

def test_all_resolved_shared_bar_profiles_point_at_canonical_owned_keys() -> None:
    from core.settings.default_settings import DEFAULT_SETTINGS

    visualizer = DEFAULT_SETTINGS["widgets"]["spotify_visualizer"]
    for descriptor in iter_all_visualizer_mode_descriptors():
        resolved = get_resolved_mode_setting_keys(descriptor.mode_id, "shared_bar")
        assert set(resolved) == {
            "bar_fill_color",
            "bar_border_color",
            "bar_border_opacity",
        }
        for persisted_key in resolved.values():
            assert persisted_key in visualizer


def test_sphere_runtime_presentation_defaults_use_resolved_profile_not_sphere_keys(monkeypatch) -> None:
    """Exercise the runtime seam that previously crashed owner construction.

    ``install_default_presentation_state`` must never manufacture
    ``sphere_bar_*`` keys. Sphere consumes the descriptor-declared Spectrum
    shared-bar profile while the values themselves still come only from
    canonical defaults.
    """
    import sys
    import types

    from core.settings.default_settings import DEFAULT_SETTINGS

    presentation_path = (
        Path(__file__).resolve().parents[1]
        / "widgets/spotify_visualizer/presentation_state.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_srpss_presentation_state_test", presentation_path
    )
    assert spec is not None and spec.loader is not None
    presentation_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(presentation_module)
    VisualizerPresentationState = presentation_module.VisualizerPresentationState
    install_default_presentation_state = presentation_module.install_default_presentation_state

    captured: dict[str, object] = {}
    fake_applier = types.ModuleType("widgets.spotify_visualizer.config_applier")

    def _capture(_state, kwargs):
        captured.update(kwargs)

    fake_applier.apply_presentation_vis_mode_kwargs = _capture
    monkeypatch.setitem(
        sys.modules,
        "widgets.spotify_visualizer.config_applier",
        fake_applier,
    )

    class _Controller:
        mode_id = "sphere"

    state = VisualizerPresentationState(_Controller())
    install_default_presentation_state(state)

    visualizer = DEFAULT_SETTINGS["widgets"]["spotify_visualizer"]
    assert captured["bar_fill_color"] == visualizer["spectrum_bar_fill_color"]
    assert captured["bar_border_color"] == visualizer["spectrum_bar_border_color"]
    assert captured["bar_border_opacity"] == visualizer["spectrum_bar_border_opacity"]
    assert not any(key.startswith("sphere_bar_") for key in captured)



def test_shared_consumers_do_not_manufacture_dynamic_mode_family_keys() -> None:
    """Keep per-mode family-key construction behind the canonical helper seam.

    The canonical model/helper modules are allowed to build bounded keys while
    iterating the fixed technical-profile owner set. Shared UI/runtime/migration
    consumers must not independently manufacture ``{mode}_bar_*`` or
    ``{mode}_rainbow_*`` keys, which is how the Sphere integration escaped two
    earlier partial fixes.
    """
    import re

    root = Path(__file__).resolve().parents[1]
    allowed = {
        Path("core/settings/visualizer_mode_registry.py"),
        Path("core/settings/models/_spotify_visualizer.py"),
        Path("core/settings/models/_visualizer_helpers.py"),
    }
    dynamic_family_key = re.compile(
        r'''f["'].*\{[^}]*mode[^}]*\}_(?:bar_fill_color|bar_border_color|bar_border_opacity|rainbow_enabled|rainbow_speed)'''
    )
    offenders: list[str] = []
    for top in ("core", "ui", "widgets", "engine", "rendering"):
        for path in (root / top).rglob("*.py"):
            relative = path.relative_to(root)
            if relative in allowed:
                continue
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if dynamic_family_key.search(line):
                    offenders.append(f"{relative}:{line_no}:{line.strip()}")
    assert offenders == []
