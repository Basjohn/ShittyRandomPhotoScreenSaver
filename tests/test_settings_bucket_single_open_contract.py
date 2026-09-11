from __future__ import annotations

from pathlib import Path

from core.settings.default_settings import DEFAULT_SETTINGS
from core.settings.structured_roots import (
    SPARSE_STRUCTURED_MAPPING_PATHS,
    merge_missing_structured_defaults,
)
from core.settings.ui_bucket_state import (
    flat_bucket_scope,
    normalize_single_open_bucket_states,
    set_single_open_bucket_state,
    sparse_open_bucket_states,
    visualizer_bucket_scope,
    widget_bucket_scope,
)
from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors

ROOT = Path(__file__).resolve().parents[1]


def test_fresh_settings_collapsible_state_is_all_closed() -> None:
    ui = DEFAULT_SETTINGS["ui"]
    for state_map_name in (
        "gmail_bucket_states",
        "widget_bucket_states",
        "visualizer_adv_states",
        "visualizer_bucket_states",
        "visualizer_tech_states",
        "visualizer_tech_bucket_states",
    ):
        states = ui[state_map_name]
        assert states
        assert not any(states.values()), f"ui.{state_map_name} must start fully collapsed"


def test_legacy_full_widget_map_normalizes_to_one_open_per_local_scope() -> None:
    canonical = (
        "reddit:reddit1",
        "reddit:secondary",
        "steam:achievement_pulse",
        "steam:abandonment_issues",
        "steam:achievement_pulse_layout",
        "steam:achievement_pulse_appearance",
    )
    raw = {
        "reddit:reddit1": True,
        "reddit:secondary": True,
        "steam:achievement_pulse": True,
        "steam:abandonment_issues": True,
        "steam:achievement_pulse_layout": True,
        "steam:achievement_pulse_appearance": True,
    }
    states = normalize_single_open_bucket_states(
        canonical,
        raw,
        scope_for_key=lambda key: widget_bucket_scope(key, canonical),
    )

    assert states["reddit:reddit1"] is False
    assert states["reddit:secondary"] is True
    assert states["steam:achievement_pulse"] is False
    assert states["steam:abandonment_issues"] is True
    # Nested card buckets are a separate local accordion scope from the card.
    assert states["steam:achievement_pulse_layout"] is False
    assert states["steam:achievement_pulse_appearance"] is True


def test_widget_state_persists_only_current_open_key_per_scope() -> None:
    canonical = (
        "media:appearance",
        "media:controls",
        "steam:achievement_pulse",
        "steam:achievement_pulse_layout",
        "steam:achievement_pulse_appearance",
    )
    states = {key: False for key in canonical}
    scope = lambda key: widget_bucket_scope(key, canonical)

    set_single_open_bucket_state(states, "media:appearance", True, scope_for_key=scope)
    set_single_open_bucket_state(states, "media:controls", True, scope_for_key=scope)
    set_single_open_bucket_state(states, "steam:achievement_pulse", True, scope_for_key=scope)
    set_single_open_bucket_state(
        states,
        "steam:achievement_pulse_layout",
        True,
        scope_for_key=scope,
    )

    assert sparse_open_bucket_states(states) == {
        "media:controls": True,
        "steam:achievement_pulse": True,
        "steam:achievement_pulse_layout": True,
    }


def test_flat_and_visualizer_scopes_replace_previous_open_bucket() -> None:
    gmail = {"backend": False, "layout": False, "appearance": False}
    set_single_open_bucket_state(gmail, "backend", True, scope_for_key=flat_bucket_scope)
    set_single_open_bucket_state(gmail, "layout", True, scope_for_key=flat_bucket_scope)
    assert sparse_open_bucket_states(gmail) == {"layout": True}

    visualizer = {
        "spectrum:appearance": False,
        "spectrum:shape": False,
        "bubble:appearance": False,
    }
    set_single_open_bucket_state(
        visualizer,
        "spectrum:appearance",
        True,
        scope_for_key=visualizer_bucket_scope,
    )
    set_single_open_bucket_state(
        visualizer,
        "spectrum:shape",
        True,
        scope_for_key=visualizer_bucket_scope,
    )
    set_single_open_bucket_state(
        visualizer,
        "bubble:appearance",
        True,
        scope_for_key=visualizer_bucket_scope,
    )
    assert sparse_open_bucket_states(visualizer) == {
        "spectrum:shape": True,
        "bubble:appearance": True,
    }


def test_shared_rainbow_and_spectrum_bar_appearance_are_real_bucket_schema() -> None:
    keys = set(DEFAULT_SETTINGS["ui"]["visualizer_bucket_states"])
    descriptors = iter_all_visualizer_mode_descriptors()
    for descriptor in descriptors:
        rainbow_key = f"{descriptor.mode_id}:rainbow"
        if descriptor.rainbow_controls:
            assert rainbow_key in keys
        else:
            assert rainbow_key not in keys

    assert "spectrum:bar_appearance" in keys
    assert "sphere:bar_appearance" not in keys

    source = (ROOT / "ui" / "tabs" / "visualizers_tab.py").read_text(encoding="utf-8")
    assert 'bucket_key="bar_appearance"' in source
    assert 'title="Bar Appearance"' in source
    assert 'bucket_key="rainbow"' in source
    assert 'title="Rainbow"' in source



def test_structured_default_merge_does_not_materialize_sparse_bucket_maps() -> None:
    defaults = {
        "settings_theme_selection": "theme-a",
        "widget_bucket_states": {"media:appearance": False, "media:controls": False},
        "gmail_bucket_states": {"layout": False, "appearance": False},
        "visualizer_bucket_states": {"spectrum:shape": False},
        "visualizer_tech_bucket_states": {"spectrum:agc": False},
        "other_nested": {"enabled": True},
    }

    fresh, changed = merge_missing_structured_defaults({}, defaults, path=("ui",))
    assert changed is True
    assert fresh == {
        "settings_theme_selection": "theme-a",
        "other_nested": {"enabled": True},
    }

    existing = {
        "widget_bucket_states": {"media:controls": True},
        "other_nested": {},
    }
    merged, changed = merge_missing_structured_defaults(existing, defaults, path=("ui",))
    assert changed is True
    assert merged["widget_bucket_states"] == {"media:controls": True}
    assert merged["other_nested"] == {"enabled": True}
    assert "gmail_bucket_states" not in merged
    assert "visualizer_bucket_states" not in merged
    assert "visualizer_tech_bucket_states" not in merged

    assert SPARSE_STRUCTURED_MAPPING_PATHS == frozenset(
        {
            ("ui", "gmail_bucket_states"),
            ("ui", "visualizer_bucket_states"),
            ("ui", "visualizer_tech_bucket_states"),
            ("ui", "widget_bucket_states"),
        }
    )

def test_shared_bucket_helper_closes_peers_synchronously_without_timer() -> None:
    source = (ROOT / "ui" / "tabs" / "shared_styles.py").read_text(encoding="utf-8")
    start = source.index("def bind_bucket_accordion(")
    end = source.index("\ndef build_bucket_toggle(", start)
    accordion_source = source[start:end]

    assert "QSignalBlocker" in accordion_source
    assert "peer.setChecked(False)" in accordion_source
    assert "apply_peer(False)" in accordion_source
    assert "QTimer" not in accordion_source


def test_visualizer_technical_leaf_sections_use_real_sparse_buckets() -> None:
    canonical = DEFAULT_SETTINGS["ui"]["visualizer_tech_bucket_states"]
    states = normalize_single_open_bucket_states(
        canonical.keys(),
        {"spectrum:agc": True, "spectrum:transient": True, "bubble:agc": True},
        scope_for_key=visualizer_bucket_scope,
    )
    assert sparse_open_bucket_states(states) == {
        "spectrum:transient": True,
        "bubble:agc": True,
    }

    # Custom and Technical are separate schema maps but one logical leaf accordion
    # per mode. A legacy dual-open profile therefore normalizes to one winner.
    custom = DEFAULT_SETTINGS["ui"]["visualizer_bucket_states"]
    combined_keys = tuple(custom) + tuple(canonical)
    combined_raw = {key: False for key in combined_keys}
    combined_raw["spectrum:shape"] = True
    combined_raw["spectrum:agc"] = True
    combined = normalize_single_open_bucket_states(
        combined_keys,
        combined_raw,
        scope_for_key=visualizer_bucket_scope,
    )
    assert combined["spectrum:shape"] is False
    assert combined["spectrum:agc"] is True

    source = (ROOT / "ui" / "tabs" / "media" / "technical_controls.py").read_text(
        encoding="utf-8"
    )
    assert "shared_styles.build_bucket_toggle(" in source
    assert 'label="AGC"' in source
    assert 'label="Transient"' in source
    assert "accordion_owner=tab" in source
    assert 'accordion_scope=("visualizer", str(mode_key).strip().lower())' in source
    assert 'QCheckBox(label)' not in source

    context = (ROOT / "ui" / "tabs" / "visualizer_settings_context.py").read_text(
        encoding="utf-8"
    )
    assert "def _normalize_visualizer_leaf_bucket_states(" in context
    assert "def _set_visualizer_leaf_bucket_state(" in context
    assert context.count("self._set_visualizer_leaf_bucket_state(") == 2


def test_widget_bucket_finalization_has_one_shared_owner() -> None:
    shared = (ROOT / "ui" / "tabs" / "shared_styles.py").read_text(encoding="utf-8")
    assert "def finalize_bucket_body(" in shared

    widget_modules = (
        "widgets_tab_defaults.py",
        "widgets_tab_clock.py",
        "widgets_tab_media.py",
        "widgets_tab_weather.py",
        "widgets_tab_reddit.py",
        "widgets_tab_gmail.py",
        "widgets_tab_steam.py",
    )
    for name in widget_modules:
        source = (ROOT / "ui" / "tabs" / name).read_text(encoding="utf-8")
        assert "def _finalize_bucket_body(" not in source
        assert "finalize_bucket_body as _finalize_bucket_body" in source


def test_bucket_policy_has_no_stale_default_open_or_eager_spectrum_claims() -> None:
    gmail = (ROOT / "ui" / "tabs" / "widgets_tab_gmail.py").read_text(encoding="utf-8")
    media = (ROOT / "ui" / "tabs" / "widgets_tab_media.py").read_text(encoding="utf-8")
    assert "only default-open bucket" not in gmail
    assert "Spectrum eager exception" not in media
    assert "_LAZY_VISUALIZER_MODES" not in media

def test_deferred_bucket_builders_have_explicit_finalization_paths() -> None:
    # Deferred bodies prevent startup flashes while their controls are populated.
    # Every builder using that mode must explicitly finalize visibility afterwards.
    widget_modules = (
        "widgets_tab_defaults.py",
        "widgets_tab_clock.py",
        "widgets_tab_media.py",
        "widgets_tab_weather.py",
        "widgets_tab_reddit.py",
        "widgets_tab_gmail.py",
        "widgets_tab_steam.py",
    )
    for name in widget_modules:
        source = (ROOT / "ui" / "tabs" / name).read_text(encoding="utf-8")
        assert "defer_initial_visibility=True" in source
        assert "_finalize_bucket_body(" in source

    technical = (ROOT / "ui" / "tabs" / "media" / "technical_controls.py").read_text(
        encoding="utf-8"
    )
    assert "defer_initial_visibility=True" in technical
    assert "shared_styles.finalize_bucket_body(" in technical


def test_visualizer_parent_disclosures_remain_independent_from_leaf_accordions() -> None:
    scaffold = (ROOT / "ui" / "tabs" / "media" / "builder_scaffold.py").read_text(
        encoding="utf-8"
    )
    technical = (ROOT / "ui" / "tabs" / "media" / "technical_controls.py").read_text(
        encoding="utf-8"
    )

    # Advanced and Technical are disclosure parents. Their children must be able
    # to open without causing the parent that contains them to close.
    assert 'toggle.setText("Advanced")' in scaffold
    assert "get_visualizer_adv_state(mode_key)" in scaffold
    assert 'setter = getattr(tab, "set_visualizer_adv_state", None)' in scaffold
    assert "setter(mode_key, checked)" in scaffold
    advanced_start = scaffold.index('toggle.setText("Advanced")')
    advanced_end = len(scaffold)
    assert "bind_bucket_accordion(" not in scaffold[advanced_start:advanced_end]

    assert 'toggle.setText("Technical")' in technical
    assert "get_visualizer_tech_state(mode_key)" in technical
    assert 'setter = getattr(tab, "set_visualizer_tech_state", None)' in technical
    assert "setter(mode_key, checked)" in technical
    outer_start = technical.index('toggle.setText("Technical")')
    assert "bind_bucket_accordion(" not in technical[outer_start:]


def test_explicit_non_bucket_surfaces_stay_outside_collapsible_contract() -> None:
    accessibility = (ROOT / "ui" / "tabs" / "accessibility_tab.py").read_text(
        encoding="utf-8"
    )
    about = (ROOT / "ui" / "settings_about_tab.py").read_text(encoding="utf-8")
    visualizers = (ROOT / "ui" / "tabs" / "visualizers_tab.py").read_text(
        encoding="utf-8"
    )

    assert "build_bucket_toggle(" not in accessibility
    assert "build_collapsible_bucket(" not in accessibility
    assert "build_bucket_toggle(" not in about
    assert "build_collapsible_bucket(" not in about

    setup_start = visualizers.index('QGroupBox("Setup")')
    setup_end = visualizers.index("def _build_mode_page", setup_start)
    setup_source = visualizers[setup_start:setup_end]
    assert "build_bucket_toggle(" not in setup_source
    assert "build_collapsible_bucket(" not in setup_source

