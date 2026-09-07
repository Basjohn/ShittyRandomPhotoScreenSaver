from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _literal(relative: str, name: str) -> dict:
    parsed = ast.parse(_text(relative))
    for node in parsed.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            value = ast.literal_eval(node.value)
            assert isinstance(value, dict)
            return value
    raise AssertionError(f"{name} literal not found in {relative}")


def test_canonical_defaults_have_one_shape_for_previously_duplicated_roots() -> None:
    defaults = _literal("core/settings/default_settings.py", "DEFAULT_SETTINGS")

    assert defaults["accessibility"] == {
        "dimming": {"enabled": True, "opacity": 15},
        "pixel_shift": {"enabled": False, "rate": 1},
    }
    assert defaults["workers"] == {
        "fft": {"enabled": False},
        "image": {"enabled": True},
        "max_workers": "auto",
        "rss": {"enabled": True},
        "transition": {"enabled": True},
    }

    for root in ("accessibility", "workers", "ui"):
        assert all("." not in str(key) for key in defaults[root])

    assert "preset" not in defaults
    assert "custom_preset_backup" not in defaults


def test_real_persisted_fallbacks_are_canonical_product_defaults() -> None:
    defaults = _literal("core/settings/default_settings.py", "DEFAULT_SETTINGS")

    assert defaults["cache"] == {
        "max_concurrent": 2,
        "max_items": 16,
        "max_memory_mb": 256,
        "prefetch_ahead": 5,
    }
    assert defaults["queue"]["history_size"] == 50

    overrides = _literal(
        "core/settings/default_profile_overrides.py",
        "PROFILE_DEFAULT_OVERRIDES",
    )
    assert "mc" not in defaults
    assert overrides["Screensaver_MC"]["mc"]["always_on_top"] is True


def test_runtime_history_and_settings_session_state_are_not_product_defaults() -> None:
    defaults = _literal("core/settings/default_settings.py", "DEFAULT_SETTINGS")

    transitions = defaults["transitions"]
    assert "random_choice" not in transitions
    assert "last_random_choice" not in transitions
    assert "last_direction" not in transitions["wipe"]

    ui = defaults["ui"]
    for transient in (
        "dialog_geometry",
        "last_tab_index",
        "last_tab_key",
        "last_tab_scroll",
        "tab_state",
        "visualizer_scroll_positions",
    ):
        assert transient not in ui

    # Theme selection and authored bucket defaults are product defaults, not
    # session captures, and therefore stay canonical.
    assert ui["settings_theme_selection"] == "file:Default Dark [Single] [Glass].srtheme"
    assert isinstance(ui["widget_bucket_states"], dict)


def test_fresh_profile_collapsible_settings_ui_is_closed_by_default() -> None:
    defaults = _literal("core/settings/default_settings.py", "DEFAULT_SETTINGS")
    ui = defaults["ui"]

    for state_map_name in (
        "gmail_bucket_states",
        "widget_bucket_states",
        "visualizer_adv_states",
        "visualizer_bucket_states",
        "visualizer_tech_states",
        "visualizer_tech_bucket_states",
    ):
        state_map = ui[state_map_name]
        assert state_map, f"ui.{state_map_name} must enumerate its canonical buckets"
        assert all(value is False for value in state_map.values()), (
            f"Fresh-profile collapsible UI must start closed: ui.{state_map_name}"
        )


def test_approved_fresh_profile_defaults_are_canonical_and_dormancy_safe() -> None:
    defaults = _literal("core/settings/default_settings.py", "DEFAULT_SETTINGS")
    widgets = defaults["widgets"]

    # Standard/Screensaver starts every widget route on Display 1.  Enabled
    # state remains a separate product choice; routing must not turn anything on.
    monitor_routes = {
        widget_id: section["monitor"]
        for widget_id, section in widgets.items()
        if isinstance(section, dict) and "monitor" in section
    }
    assert monitor_routes
    assert {str(value) for value in monitor_routes.values()} == {"1"}

    # This tranche changes placement/default mode only.  Preserve the approved
    # fresh-profile screen-space policy exactly: do not accidentally turn on a
    # family merely because its route is now Display 1.
    assert {
        widget_id: section["enabled"]
        for widget_id, section in widgets.items()
        if isinstance(section, dict) and "enabled" in section and widget_id != "shadows"
    } == {
        "abandonment_issues": False,
        "achievement_pulse": False,
        "clock": True,
        "clock2": False,
        "clock3": False,
        "friend_pulse": False,
        "gmail": True,
        "media": True,
        "reddit": True,
        "reddit2": True,
        "spotify_visualizer": True,
        "steam": False,
        "steam_progress": False,
        "weather": True,
    }

    assert widgets["weather"]["enabled"] is True
    assert widgets["weather"]["location"] == ""
    assert str(widgets["weather"]["monitor"]) == "1"

    assert widgets["gmail"]["enabled"] is True
    assert str(widgets["gmail"]["monitor"]) == "1"

    visualizer = widgets["spotify_visualizer"]
    # The Visualizer itself is ON by default; its existing Media-family and
    # now-playing admission keep it dormant until there is media to visualize.
    assert visualizer["enabled"] is True
    assert visualizer["visualizers_enabled"] is True
    assert visualizer["mode"] == "bubble"
    assert visualizer["enabled_modes"] == [
        "spectrum",
        "oscilloscope",
        "sine_wave",
        "bubble",
        "devcurve",
    ]
    assert "sphere" not in visualizer["enabled_modes"]

    # Random mode is the one canonical transition-mode authority.  The concrete
    # type remains the remembered manual choice, not a second "Random" sentinel.
    assert defaults["transitions"]["random_always"] is True
    assert defaults["transitions"]["type"] != "Random"

    ui = defaults["ui"]
    assert ui["settings_theme_selection"] == "file:Default Dark [Single] [Glass].srtheme"
    bucket_roots = {
        key: value
        for key, value in ui.items()
        if key.endswith("_bucket_states")
    }
    assert bucket_roots
    assert all(
        isinstance(states, dict) and states and all(value is False for value in states.values())
        for states in bucket_roots.values()
    )


def test_derived_snapshot_tracks_clean_normal_defaults() -> None:
    defaults = _literal("core/settings/default_settings.py", "DEFAULT_SETTINGS")
    snapshot = json.loads(_text("core/settings/defaults_snapshot.json"))

    for root in ("accessibility", "cache", "queue", "ui", "workers", "widget_theme"):
        assert snapshot[root] == defaults[root]

    assert "mc" not in snapshot
    assert "random_choice" not in snapshot["transitions"]
    assert "last_random_choice" not in snapshot["transitions"]
    assert "last_direction" not in snapshot["transitions"]["wipe"]


def test_fresh_install_and_reset_follow_the_shared_structured_root_contract() -> None:
    manager = _text("core/settings/settings_manager.py")
    builder = _text("core/settings/defaults_snapshot_builder.py")
    sst = _text("core/settings/sst_io.py")
    defaults_module = _text("core/settings/defaults.py")

    # Fresh install and Reset consume the same runtime-store projection.  There
    # must not be a second hand-maintained section allow-list in either path.
    assert manager.count("get_flat_defaults(self._application)") >= 2
    assert "canonical_store = get_flat_defaults(self._application)" in manager
    assert "for key, value in canonical_store.items():" in manager
    assert "self._settings.replace_all(get_flat_defaults(self._application))" in manager
    assert "for section in ('display', 'input', 'queue', 'sources', 'timing')" not in manager

    # Snapshot/default tooling and SST all import the one structured-root owner.
    assert "STRUCTURED_SETTINGS_ROOTS" in manager
    assert "STRUCTURED_SETTINGS_ROOTS" in builder
    assert "STRUCTURED_SETTINGS_ROOTS" in sst
    assert "STRUCTURED_SETTINGS_ROOTS" in defaults_module

    # Visualizer defaults/reset transport must normalize schema without applying
    # a curated preset overlay: presets remain a separate authored authority.
    assert manager.count("apply_preset_overlay=False") >= 2
    assert "apply_preset_overlay=False" in builder


def test_all_structured_roots_share_one_forward_repair_path() -> None:
    manager = _text("core/settings/settings_manager.py")
    roots = _text("core/settings/structured_roots.py")

    assert "for root in sorted(self._STRUCTURED_ROOTS):" in manager
    assert "dotted members only fill missing paths" in manager
    assert "self._settings.remove(flat_key)" in manager
    for root in (
        "transitions",
        "ui",
        "visualizer_custom_presets",
        "widgets",
        "widget_theme",
    ):
        assert f'"{root}"' in roots


def test_import_coercion_is_schema_driven_not_key_list_driven() -> None:
    manager = _text("core/settings/settings_manager.py")
    assert "canonical = get_canonical_default(" in manager
    assert "if isinstance(canonical, bool):" in manager
    assert "if isinstance(canonical, int)" in manager
    assert "if isinstance(canonical, float):" in manager
    assert '"queue.history_size",' not in manager
    assert '"mc.always_on_top",' not in manager


def test_json_store_persists_explicit_null_as_distinct_from_missing() -> None:
    store = _text("core/settings/json_store.py")
    assert "if key in self._data and self._data[key] == value:" in store
    assert "current = self._data.get(key)" not in store


def test_visualizer_literal_and_derived_snapshot_have_identical_schema() -> None:
    defaults = _literal("core/settings/default_settings.py", "DEFAULT_SETTINGS")
    snapshot = json.loads(_text("core/settings/defaults_snapshot.json"))
    literal_vis = defaults["widgets"]["spotify_visualizer"]
    snapshot_vis = snapshot["widgets"]["spotify_visualizer"]

    assert set(snapshot_vis) == set(literal_vis)
    for retired in ("osc_glow_size", "sine_glow_size", "sine_line1_color"):
        assert retired not in literal_vis
    assert literal_vis["sphere_rainbow_enabled"] is False
    assert literal_vis["sphere_rainbow_speed"] == 0.5


def test_curated_visualizer_preset_assets_remain_separate_authored_inputs() -> None:
    preset_root = ROOT / "presets" / "visualizer_modes"
    expected_counts = {
        "bubble": 9,
        "devcurve": 2,
        "oscilloscope": 4,
        "sine_wave": 6,
        "spectrum": 4,
        "sphere": 5,
    }

    for mode, count in expected_counts.items():
        files = sorted((preset_root / mode).glob("preset_*.json"))
        assert len(files) == count
        indices = []
        for path in files:
            payload = json.loads(path.read_text(encoding="utf-8"))
            snapshot = payload["snapshot"]["widgets"]["spotify_visualizer"]
            assert snapshot["mode"] == mode
            indices.append(int(payload["preset_index"]))
            # Presets are authored overlays, not copies of the whole defaults
            # authority.  They must retain substantive mode-owned content.
            assert len(snapshot) > 5
        assert indices == list(range(count))

    presets_source = _text("core/settings/visualizer_presets.py")
    assert "For Custom (last index), *config* is returned unchanged" in presets_source
    assert "First: CLEAR all mode-specific keys not in preset" in presets_source


def test_settings_visualizer_builders_do_not_reintroduce_shadow_defaults() -> None:
    widgets_media = _text("ui/tabs/widgets_tab_media.py")
    widgets_tab = _text("ui/tabs/widgets_tab.py")
    visualizers_tab = _text("ui/tabs/visualizers_tab.py")
    devcurve_builder = _text("ui/tabs/media/devcurve_builder.py")
    devcurve_editor = _text("ui/tabs/media/devcurve_shape_editor.py")
    spectrum_editor = _text("ui/tabs/media/spectrum_shape_editor.py")

    assert "software_visualizer_enabled" not in widgets_media
    assert "_LAYER_DEFAULTS" not in devcurve_builder
    assert "DEFAULT_NODES" not in devcurve_editor
    assert "_LANE_STRENGTHS_" not in devcurve_editor
    assert "DEFAULT_NODES" not in spectrum_editor
    assert "_LANE_STRENGTHS_" not in spectrum_editor
    assert "default_layer_nodes=" in devcurve_builder
    assert "default_nodes=" in _text("ui/tabs/media/spectrum_builder.py")

    # Settings controls must initialize from the canonical Widget defaults, not
    # stale local numbers/colours that can later leak through a save path.
    assert "rainbow_enabled.setChecked(False)" not in visualizers_tab
    assert "rainbow_speed_slider.setValue(50)" not in visualizers_tab
    assert "QColor(0, 200, 255, 230)" not in widgets_tab
    assert "QColor(35, 35, 35, 255)" not in widgets_media


def test_capability_missing_members_resolve_through_canonical_defaults() -> None:
    source = _text("core/settings/capability_activation.py")

    assert 'activation.get(family_id, True)' not in source
    assert 'activation.get(canonical, True)' not in source
    assert 'pool.get(name, False)' not in source
    assert 'config.get(TRANSITION_RANDOM_MODE_KEY, False)' not in source
    assert 'transitions_config.get(TRANSITION_RANDOM_MODE_KEY, False)' not in source
    assert 'require_canonical_default(f"widgets.{WIDGET_FAMILY_ACTIVATION_KEY}.{family_id}")' in source
    assert 'require_canonical_default(f"transitions.{TRANSITION_ACTIVATION_KEY}.{canonical}")' in source
    assert 'require_canonical_default(f"transitions.{TRANSITION_POOL_KEY}.{name}")' in source


def test_display_and_transition_tabs_do_not_invent_product_fallbacks() -> None:
    display = _text("ui/tabs/display_tab.py")
    transitions = _text("ui/tabs/transitions_tab.py")

    assert "SettingsManager.to_bool(shuffle_raw, True)" not in display
    assert "SettingsManager.to_bool(lanczos_raw, True)" not in display
    assert "SettingsManager.to_bool(sharpen_raw, False)" not in display
    assert "mode_map.get(mode_index, 'fill')" not in display
    assert "else 'circle'" not in display
    assert "fallback='Ripple'" not in transitions
    assert "default_duration = 3000" not in transitions
    assert "_activation_by_type.get(name, True)" not in transitions
    assert "_pool_by_type.get(name, True)" not in transitions


def test_custom_visualizer_state_is_not_a_product_default_and_reset_preserves_it() -> None:
    defaults = _literal("core/settings/default_settings.py", "DEFAULT_SETTINGS")
    snapshot = json.loads(_text("core/settings/defaults_snapshot.json"))
    defaults_module = _text("core/settings/defaults.py")
    manager = _text("core/settings/settings_manager.py")
    sst = _text("core/settings/sst_io.py")

    assert "visualizer_custom_presets" not in defaults
    assert "visualizer_custom_presets" not in snapshot
    assert "'visualizer_custom_presets'," in defaults_module
    assert "self._settings.replace_all(get_flat_defaults(self._application))" in manager
    assert 'if "visualizer_custom_presets" not in normalized_root:' in sst
    assert "normalize_visualizer_custom_snapshot_cache(existing_cache)" in sst


def test_retired_visualizer_growth_is_invalidated_once_not_preserved_as_schema() -> None:
    defaults = _literal("core/settings/default_settings.py", "DEFAULT_SETTINGS")
    snapshot = json.loads(_text("core/settings/defaults_snapshot.json"))
    visualizer = defaults["widgets"]["spotify_visualizer"]
    snapshot_visualizer = snapshot["widgets"]["spotify_visualizer"]
    model = _text("core/settings/models/_spotify_visualizer.py")
    normalizer = _text("core/settings/visualizer_settings_snapshot.py")

    retired = {
        "spectrum_growth",
        "osc_growth",
        "sine_wave_growth",
        "bubble_growth",
        "devcurve_growth",
    }
    assert retired.isdisjoint(visualizer)
    assert retired.isdisjoint(snapshot_visualizer)
    for key in retired:
        assert f'"{key}"' not in model
        assert f'"{key}"' in normalizer

    # The old height authority itself is gone. Ordinary geometry is estimated
    # from the same retained 1.5 presentation-aspect contract used by Quick.
    assert not (ROOT / "widgets/spotify_visualizer/card_geometry.py").exists()
    assert not (ROOT / "widgets/spotify_visualizer/card_height.py").exists()
    predictor = _text("ui/widget_stack_predictor.py")
    assert "CANONICAL_VISUALIZER_BASELINE_ASPECT_RATIO" in predictor
    assert "build_growth_map_from_widget" not in predictor


def test_runtime_recovery_metadata_starts_empty_instead_of_copying_widget_defaults() -> None:
    defaults = _literal("core/settings/default_settings.py", "DEFAULT_SETTINGS")
    restore = defaults["widgets"]["custom_layout_restore"]
    assert restore == {"version": 1, "widgets": {}}


def test_dead_transition_precompute_and_qwidget_visualizer_renderers_are_removed() -> None:
    engine = _text("engine/screensaver_engine.py")
    worker_types = _text("core/process/types.py")
    workers_init = _text("core/process/workers/__init__.py")

    assert "transition_worker_main" not in engine
    assert "WorkerType.TRANSITION" not in engine
    assert "TRANSITION_PRECOMPUTE" not in worker_types
    assert "TransitionWorker" not in workers_init
    assert not (ROOT / "core/process/workers/transition_worker.py").exists()
    assert not (ROOT / "widgets/spotify_visualizer/renderers").exists()

    for build_file in (
        "scripts/build_nuitka.ps1",
        "scripts/build_nuitka_mc_onedir.ps1",
        "scripts/venv/build_nuitka.ps1",
        "scripts/venv/build_nuitka_mc_onedir.ps1",
        "tools/build_layout.ps1",
    ):
        assert "widgets.spotify_visualizer.renderers" not in _text(build_file)


def test_visualizer_runtime_config_has_canonical_replacement_not_empty_holes() -> None:
    """Live product config is seeded/resolved; retired schema has no live consumer.

    Sanitization must never mean deleting a local fallback and leaving an active
    runtime field uninitialized. Logical/presentation owners seed from canonical
    defaults, then the resolved preset/settings overlay replaces those values.
    Truly retired keys are invalidated at normalization and have no runtime/UI
    consumer left to resurrect them.
    """

    logical = _text("widgets/spotify_visualizer/logical_tick_state.py")
    presentation = _text("widgets/spotify_visualizer/presentation_state.py")
    owner = _text("widgets/spotify_visualizer/quick_display_visualizer_owner.py")
    sphere_capture = _text("widgets/spotify_visualizer/sphere_capture.py")
    devcurve_tick = _text("widgets/spotify_visualizer/tick_pipeline.py")

    assert 'get_raw_default_settings()["widgets"]["spotify_visualizer"]' in logical
    assert "apply_logical_vis_mode_kwargs(state, canonical_visualizer)" in logical
    assert 'get_raw_default_settings()["widgets"]["spotify_visualizer"]' in presentation
    assert "apply_presentation_vis_mode_kwargs(state, defaults)" in presentation
    assert "install_default_logical_tick_state(state" in owner
    assert "install_default_presentation_state(controller.presentation_state)" in owner

    # Sphere/DevCurve immutable capture consumes configure-owned values rather
    # than reviving another local product baseline after the canonical seed.
    assert "SPHERE_DEFAULT_PARAMETERS" not in sphere_capture
    assert 'parameters = widget._sphere_parameters' in sphere_capture
    assert "_DEVCURVE_LAYER_DEFAULTS" not in devcurve_tick
    assert "_DEVCURVE_DEFAULT_NODES" not in devcurve_tick

    # These keys are genuinely retired, not empty live settings.  Their names
    # may remain only in migration/schema guards, never in active consumers.
    active_roots = ("widgets", "ui", "rendering")
    for retired in ("osc_glow_size", "sine_glow_size"):
        hits = []
        for root_name in active_roots:
            for path in (ROOT / root_name).rglob("*.py"):
                if retired in path.read_text(encoding="utf-8"):
                    hits.append(path.relative_to(ROOT).as_posix())
        assert hits == [], f"retired Visualizer key {retired!r} still consumed by {hits}"


def test_resolved_runtime_consumers_do_not_rebuild_product_defaults() -> None:
    """Active settings reach strict runtime consumers; local product baselines do not."""

    display_manager = _text("engine/display_manager.py")
    presentation = _text("widgets/spotify_visualizer/presentation_geometry.py")
    scene = _text("rendering/quick/scene_controller.py")
    devcurve_frame = _text("widgets/spotify_visualizer/devcurve_frame_runtime.py")
    devcurve_solver = _text("widgets/spotify_visualizer/devcurve_runtime.py")
    transition_request = _text("rendering/quick/transitions/request_resolution.py")
    image_pipeline = _text("engine/image_pipeline.py")
    image_worker = _text("core/process/workers/image_worker.py")

    # Visualizer card Settings are repaired against canonical Widgets state at
    # admission, then supplied as one complete presentation payload. Resize/QML
    # consumers do not maintain another colour/shadow/border default table.
    assert 'canonical_widgets = get_default_settings()["widgets"]' in display_manager
    assert 'QuickShadowSnapshot.from_mapping(self._shadow_values_snapshot)' in display_manager
    assert 'canonical_global = canonical_widgets["global"]' in display_manager
    assert "technical_config=technical_cache[mode]" in display_manager
    assert "_DEFAULT_BACKGROUND_COLOR" not in presentation
    assert "_DEFAULT_BORDER_COLOR" not in presentation
    assert "_DEFAULT_SHADOW_COLOR" not in presentation
    assert 'style["background_color"]' in presentation
    assert 'style["shadow_extensions"]' in presentation
    assert 'style["background_color"]' in scene
    assert 'style.get("background_color"' not in scene

    # DevCurve receives a canonical-seeded parameter/node snapshot. Its logical
    # integration and solver may clamp constraints, but cannot author a missing
    # product shape, layer enable state, power, offset or order.
    assert "_DEFAULT_SHAPE" not in devcurve_frame
    assert "def _parameter(parameters: Mapping[str, object], name: str)" in devcurve_frame
    assert 'layer_shape_nodes[name]' in devcurve_frame
    assert 'layer_settings[key]' in devcurve_solver
    assert 'layer_shape_nodes[key]' in devcurve_solver
    assert 'ls.get("enabled", True)' not in devcurve_solver

    # Transition and image workers consume resolved requests rather than
    # substituting the old Crossfade/1300/Lanczos defaults downstream.
    assert '"Crossfade"' not in transition_request
    assert "1300" not in transition_request
    assert "require_canonical_default" in image_pipeline
    assert "data['same_image']" in image_pipeline
    assert "use_lanczos = data.get" not in image_worker
    assert "sharpen = data.get" not in image_worker
    assert not (ROOT / "rendering/image_processor.py").exists()

    # Global shadow product values are repaired once at the typed Settings
    # boundary and consumed as a complete generation snapshot. Ordinary Quick
    # widget projections must not carry the old SE/18/.77/.33 fallback table.
    shadow_snapshot = _text("rendering/quick/shadow_snapshot.py")
    shadow_model = _text("core/settings/models/_core.py")
    assert "require_canonical_default" in shadow_model
    assert "QuickShadowSnapshot" in shadow_snapshot
    for relative in (
        "rendering/quick/context_menu.py",
        "rendering/quick/widgets/reddit.py",
        "rendering/quick/widgets/gmail.py",
        "rendering/quick/widgets/media.py",
        "rendering/quick/widgets/clock.py",
        "rendering/quick/widgets/weather.py",
        "rendering/quick/widgets/steam_common.py",
    ):
        consumer = _text(relative)
        assert "QuickShadowSnapshot.from_mapping(shadow_values)" in consumer
        assert 'shadow_values.get("direction", "SE")' not in consumer
        assert 'shadow_values.get("blur_radius"), 18' not in consumer
        assert 'shadow_values.get("frame_opacity"), 0.77' not in consumer
        assert 'shadow_values.get("text_opacity"), 0.33' not in consumer

    gmail_runtime = _text("widgets/gmail_runtime.py")
    assert '_gmail_default("sound_volume_percent")' in gmail_runtime
    assert 'sound_volume_percent: int = 50' not in gmail_runtime


def test_defaults_snapshot_tooling_is_headless_and_exact() -> None:
    """Derived-default tooling must not require Qt or become a second authority."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "core.settings.defaults_snapshot_builder", "--check-all"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "defaults snapshot OK" in result.stdout
    assert "SST defaults documents OK" in result.stdout

    package_init = _text("core/settings/__init__.py")
    assert "def __getattr__(name: str)" in package_init
    assert "if TYPE_CHECKING:" in package_init
    # The subprocess check above proves the runtime package import itself does
    # not execute the Qt-backed SettingsManager import.

    builder = _text("core/settings/defaults_snapshot_builder.py")
    assert "return json.dumps(build_defaults_snapshot(), indent=2, sort_keys=True)" in builder
    assert "def defaults_snapshot_matches" in builder
    assert "def write_defaults_snapshot" in builder
    assert "def sst_defaults_documents_match" in builder
    assert "def write_sst_defaults_documents" in builder


def test_widget_preview_and_custom_position_repair_use_canonical_sections() -> None:
    """Settings previews/layout UI must not carry copied widget product defaults."""
    descriptors = _text("rendering/widget_descriptors.py")
    widgets_tab = _text("ui/tabs/widgets_tab.py")

    assert "fallback_position" not in descriptors
    assert "field.fallback" not in descriptors
    assert "_canonical_preview_value" in descriptors
    assert "resolver(widget_id, field.canonical_key or field.key)" in descriptors
    assert 'canonical_key="show_timezone"' in descriptors

    # Previously this registry duplicated positions such as Top Left/Bottom
    # Right for Custom-slot recovery; current profile canonical state owns them.
    assert 'WidgetCustomPositionOptionDescriptor("weather", "weather_position")' in descriptors
    assert 'WidgetCustomPositionOptionDescriptor("media", "media_position")' in descriptors
    assert 'self._widget_default(settings_key, "position")' in widgets_tab


def test_profile_layering_contains_only_real_behavioral_differences() -> None:
    """MC profile overrides preserve its established monitor routing and behavior."""
    import sys
    sys.path.insert(0, str(ROOT))
    from core.settings.defaults import get_default_settings

    normal = get_default_settings("Screensaver")
    mc = get_default_settings("Screensaver_MC")

    def collect_diff(left: object, right: object, prefix: str = "") -> dict[str, tuple[object, object]]:
        if isinstance(left, dict) and isinstance(right, dict):
            result: dict[str, tuple[object, object]] = {}
            for key in sorted(set(left) | set(right)):
                path = f"{prefix}.{key}" if prefix else key
                if key not in left:
                    result[path] = (None, right[key])
                elif key not in right:
                    result[path] = (left[key], None)
                else:
                    result.update(collect_diff(left[key], right[key], path))
            return result
        return {} if left == right else {prefix: (left, right)}

    expected_monitor_diffs = {
        "widgets.clock.monitor": ("1", "ALL"),
        "widgets.clock2.monitor": (1, 2),
        "widgets.clock3.monitor": ("1", "ALL"),
        "widgets.friend_pulse.monitor": ("1", "ALL"),
        "widgets.gmail.monitor": (1, 2),
        "widgets.media.monitor": (1, 2),
        "widgets.reddit.monitor": (1, 2),
        "widgets.reddit2.monitor": (1, 2),
        "widgets.spotify_visualizer.monitor": ("1", "ALL"),
        "widgets.steam_progress.monitor": ("1", "ALL"),
    }
    assert collect_diff(normal, mc) == {
        "display.show_on_monitors": ("ALL", [1]),
        "input.interaction_mode": (False, True),
        "mc": (None, {"always_on_top": True}),
        **expected_monitor_diffs,
    }

    overrides = _literal(
        "core/settings/default_profile_overrides.py",
        "PROFILE_DEFAULT_OVERRIDES",
    )["Screensaver_MC"]
    assert overrides["widgets"] == {
        "clock": {"monitor": "ALL"},
        "clock2": {"monitor": 2},
        "clock3": {"monitor": "ALL"},
        "friend_pulse": {"monitor": "ALL"},
        "gmail": {"monitor": 2},
        "media": {"monitor": 2},
        "reddit": {"monitor": 2},
        "reddit2": {"monitor": 2},
        "spotify_visualizer": {"monitor": "ALL"},
        "steam_progress": {"monitor": "ALL"},
    }


def test_fresh_reset_and_sst_replace_share_canonical_projection_and_custom_ownership() -> None:
    """Fresh/Reset/SST use canonical product state while Custom remains authored state."""
    from copy import deepcopy
    import sys
    sys.path.insert(0, str(ROOT))

    from core.settings.defaults import get_flat_defaults
    from core.settings.sst_io import _project_import_state

    fresh = get_flat_defaults("Screensaver")
    for structured_root in ("transitions", "ui", "widget_theme", "widgets"):
        assert isinstance(fresh[structured_root], dict)
    assert "visualizer_custom_presets" not in fresh

    class _Store:
        def __init__(self, values: dict[str, object]) -> None:
            self.values = values

        def allKeys(self) -> list[str]:
            return list(self.values)

        def value(self, key: str) -> object:
            return deepcopy(self.values[key])

    class _Manager:
        def __init__(self, values: dict[str, object]) -> None:
            self._settings = _Store(values)

        @staticmethod
        def get_application_name() -> str:
            return "Screensaver"

        @staticmethod
        def _coerce_import_value(_key: str, value: object) -> object:
            return deepcopy(value)

        @staticmethod
        def _normalize_structured_mapping_shape(value: object) -> tuple[dict[str, object], bool]:
            assert isinstance(value, dict)
            return deepcopy(value), False

    existing_custom = {"bubble": {"bubble_size": 1.23}}
    mgr = _Manager({
        "timing.interval": 99,
        "visualizer_custom_presets": existing_custom,
    })

    replaced = _project_import_state(mgr, {}, merge=False)
    assert replaced["timing.interval"] == fresh["timing.interval"] == 40
    assert replaced["visualizer_custom_presets"] == existing_custom

    incoming_custom = {"sine_wave": {"sine_wave_sensitivity": 1.5}}
    replaced_explicit = _project_import_state(
        mgr,
        {"visualizer_custom_presets": incoming_custom},
        merge=False,
    )
    assert replaced_explicit["timing.interval"] == fresh["timing.interval"]
    assert replaced_explicit["visualizer_custom_presets"] == incoming_custom

    merged = _project_import_state(mgr, {}, merge=True)
    assert merged["timing.interval"] == 99
    assert merged["visualizer_custom_presets"] == existing_custom

    # Reset uses the identical canonical store projection and restores the
    # declared authored/user-specific state afterwards.
    defaults_module = _text("core/settings/defaults.py")
    manager_module = _text("core/settings/settings_manager.py")
    assert "'visualizer_custom_presets'," in defaults_module
    assert "self._settings.replace_all(get_flat_defaults(self._application))" in manager_module


def test_profile_identity_is_manager_owned_not_an_sst_fallback_default() -> None:
    """SST transport reads the resolved manager identity instead of inventing Screensaver."""
    manager = _text("core/settings/settings_manager.py")
    sst = _text("core/settings/sst_io.py")

    assert "return self._application" in manager
    assert "return self._organization" in manager
    assert 'getattr(self, "_application", "Screensaver")' not in manager
    assert 'getattr(self, "_organization", "ShittyRandomPhotoScreenSaver")' not in manager
    assert "app_name = mgr.get_application_name()" in sst
    assert 'getattr(mgr, "_application", "Screensaver")' not in sst


def test_settings_manager_get_bool_uses_canonical_value_for_missing_product_keys() -> None:
    manager = _text("core/settings/settings_manager.py")
    # The canonical bool must be used both as the coercion fallback and as the
    # actual storage-read default. Using the method signature's False here was
    # the historical bug: a missing canonical-True value became False before
    # coercion could repair it.
    assert "read_default = bool_default if isinstance(canonical, bool) else bool(default)" in manager
    assert "raw = self.get(key, read_default)" in manager
    assert "raw = self.get(key, default)" not in manager


def test_authority_audit_forbids_static_bool_coercion_around_direct_product_reads() -> None:
    audit = _text("core/settings/defaults_authority_audit.py")
    assert "direct SettingsManager.to_bool around canonical product read" in audit


def test_quick_visualizer_renderer_inputs_are_strict_resolved_contracts() -> None:
    helper = _text("rendering/quick/visualizer/implementation_values.py")
    assert "immutable visualizer frame missing parameter" in helper
    assert "Renderer colours are part of the immutable resolved frame" in helper
    assert "except KeyError" in helper

    for relative in (
        "rendering/quick/visualizer/implementations/bubble.py",
        "rendering/quick/visualizer/implementations/devcurve.py",
        "rendering/quick/visualizer/implementations/oscilloscope.py",
        "rendering/quick/visualizer/implementations/sine_wave.py",
        "rendering/quick/visualizer/implementations/spectrum.py",
    ):
        tree = ast.parse(_text(relative))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "parameter":
                    assert len(node.args) == 2 and not node.keywords, (relative, node.lineno)
                if node.func.id == "rgba":
                    assert len(node.args) == 1 and not node.keywords, (relative, node.lineno)

def test_defaults_authority_audit_covers_tooling_and_root_entrypoints() -> None:
    audit = _text("core/settings/defaults_authority_audit.py")

    assert 'for path in root.rglob("*.py")' in audit
    assert '"tests"' in audit
    assert '"deleteme"' in audit
    assert '_SCAN_ROOTS' not in audit

    # The audit itself is first-party and therefore covers the dangerous authoring
    # surfaces that previously escaped runtime/UI-only scans: tools and root apps.
    from core.settings.defaults_authority_audit import _iter_python_files

    scanned = {path.relative_to(ROOT).as_posix() for path in _iter_python_files(ROOT)}
    assert "tools/build_runner.py" in scanned
    assert "tools/check_defaults_authority.py" in scanned
    assert "main.py" in scanned
    assert "tests/test_defaults_schema_authority.py" not in scanned

