"""Expanded Visualizer M3b: the full-display overlays' one canonical setting,
``widgets.spotify_visualizer.fullscreen_overlays`` (plan 01 §G, "Settings home").

A global Visualizer setting with a canonical default (like ``expanded_display_requested``), never a mode preset value:
it has a canonical default in every profile, a typed model field and one normaliser (``core.settings.fullscreen_overlays``),
survives the Visualizer section's normalisation, the runtime preset transaction and Custom snapshots, and resets with
the defaults. Placement (corner + offset + scale relative to the expanded display's safe area) is stored for
Fullscreen Edit (M3c). Every value a test writes is test-owned or derived from the canonical default; no default,
preset or wording is pinned.
"""
from __future__ import annotations

import uuid
from copy import deepcopy
from pathlib import Path

import pytest

from core.settings.default_contract import MC_PROFILE, NORMAL_PROFILE, require_canonical_default
from core.settings.defaults import get_default_settings
from core.settings.fullscreen_overlays import (
    PLACEMENT_KEYS,
    TEXT_EXTENT_KEYS,
    TEXT_EXTENT_MAX,
    rebase_offset_for_corner,
    CORNERS,
    FONT_SIZE_MAX,
    FONT_SIZE_MIN,
    FULLSCREEN_OVERLAYS_KEY,
    OFFSET_MAX,
    OFFSET_MIN,
    OVERLAY_IDS,
    SCALE_MAX,
    SCALE_MIN,
    canonical_fullscreen_overlays,
    normalize_fullscreen_overlays,
)
from core.settings.models import SpotifyVisualizerSettings
from core.settings.settings_manager import SettingsManager
from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS, get_preset_key, is_mode_active
from core.settings.visualizer_presets import (
    apply_preset_to_config,
    build_normalized_custom_snapshot,
    get_custom_preset_index,
    get_preset_count,
)
from core.settings.visualizer_runtime_preset_cycle import resolve_next_visualizer_runtime_preset
from core.settings.visualizer_settings_snapshot import (
    normalize_visualizer_mode_payload,
    normalize_visualizer_section_mapping,
)

KEY = "fullscreen_overlays"
ACTIVE_MODES = [mode for mode in VISUALIZER_MODE_IDS if is_mode_active(mode)]


def _flipped() -> dict:
    """A test-owned value differing from the canonical default in every member, so a dropped member is observable."""
    value = canonical_fullscreen_overlays()
    value["font_family"] = value["font_family"] + " Test"
    value["font_size"] = FONT_SIZE_MIN if value["font_size"] != FONT_SIZE_MIN else FONT_SIZE_MAX
    for overlay in OVERLAY_IDS:
        options = value[overlay]
        options["corner"] = next(corner for corner in reversed(CORNERS) if corner != options["corner"])
        for key, item in options.items():
            if isinstance(item, bool):
                options[key] = not item
        options["offset_x"] = 0.25 if options["offset_x"] != 0.25 else -0.25
        options["offset_y"] = -0.125 if options["offset_y"] != -0.125 else 0.125
        options["scale"] = 1.5 if options["scale"] != 1.5 else 0.75
        if "artwork_scale" in options:
            options["artwork_scale"] = 1.75 if options["artwork_scale"] != 1.75 else 0.625
        for key in TEXT_EXTENT_KEYS:
            options[key] = 7.5 if options[key] != 7.5 else 3.25
        for key in ("artwork_width", "artwork_height"):
            if key in options:
                options[key] = 1.25 if options[key] != 1.25 else 0.75
    return value


def _manager(root: Path) -> SettingsManager:
    return SettingsManager(organization="TestOrg", application=f"TestApp_{uuid.uuid4().hex}", storage_base_dir=root)


# ------------------------------------------------------------------------------------- schema and normaliser


@pytest.mark.parametrize("profile", [NORMAL_PROFILE, MC_PROFILE])
def test_canonical_default_has_the_schema_every_consumer_reads(profile):
    value = require_canonical_default(FULLSCREEN_OVERLAYS_KEY, profile)
    assert isinstance(value["font_family"], str) and value["font_family"].strip()
    assert isinstance(value["font_size"], int) and FONT_SIZE_MIN <= value["font_size"] <= FONT_SIZE_MAX
    assert set(value) == {"font_family", "font_size", *OVERLAY_IDS}
    for overlay in OVERLAY_IDS:
        options = value[overlay]
        # Placement: anchor corner + offset + scale relative to the safe area (M3c edits them).
        assert options["corner"] in CORNERS
        assert isinstance(options["offset_x"], float) and isinstance(options["offset_y"], float)
        assert isinstance(options["scale"], float)
        assert isinstance(options["always_show"], bool) and isinstance(options["card"], bool)
    assert isinstance(value["now_playing"]["media_controls"], bool)
    assert "media_controls" not in value["preset"]
    # Now Playing's artwork has its own size factor (M3c); the preset toast has no artwork.
    assert isinstance(value["now_playing"]["artwork_scale"], float)
    assert "artwork_scale" not in value["preset"]
    # The single-axis extents (Fullscreen Edit's side handles): every overlay's text box, Now Playing's artwork shape.
    for overlay in OVERLAY_IDS:
        assert all(isinstance(value[overlay][key], float) for key in TEXT_EXTENT_KEYS)
    assert all(isinstance(value["now_playing"][key], float) for key in ("artwork_width", "artwork_height"))
    assert "artwork_width" not in value["preset"]
    # Fullscreen Edit writes exactly the placement members, which every overlay's canonical value declares.
    for overlay, keys in PLACEMENT_KEYS.items():
        assert set(keys) <= set(value[overlay])
    # The canonical value is already normal (a reset writes exactly it).
    assert normalize_fullscreen_overlays(value) == value
    assert get_default_settings(profile)["widgets"]["spotify_visualizer"][KEY] == value


def test_the_two_overlays_default_to_different_corners():
    # The operator's placements (preset top left, Now Playing bottom left) are defaults, not pinned here; the bar is
    # only that the two do not start stacked in one corner.
    value = canonical_fullscreen_overlays()
    assert value["preset"]["corner"] != value["now_playing"]["corner"]


def test_a_well_formed_value_round_trips_and_unknown_members_are_dropped():
    value = _flipped()
    stored = deepcopy(value)
    stored["stray"] = 1
    stored["preset"]["stray"] = True
    stored["preset"]["media_controls"] = True        # not a preset-toast option
    assert normalize_fullscreen_overlays(stored) == value
    for corner in CORNERS:
        assert normalize_fullscreen_overlays({"now_playing": {"corner": corner}})["now_playing"]["corner"] == corner


@pytest.mark.parametrize("raw", [None, "garbage", 3, [], {"preset": "x", "now_playing": None, "font_family": "  "}])
def test_malformed_values_fall_back_to_the_canonical_default(raw):
    assert normalize_fullscreen_overlays(raw) == canonical_fullscreen_overlays()


def test_malformed_members_fall_back_member_by_member_and_numbers_clamp():
    canonical = canonical_fullscreen_overlays()
    flipped = _flipped()
    stored = deepcopy(flipped)
    stored["now_playing"].update(corner="middle", always_show="maybe", card=[1], offset_x=float("nan"), scale="big")
    stored["preset"].update(offset_x=99.0, offset_y=-99.0, scale=1e9)
    stored["font_size"] = 10 ** 6
    result = normalize_fullscreen_overlays(stored)
    for key in ("corner", "always_show", "card", "offset_x", "scale"):
        assert result["now_playing"][key] == canonical["now_playing"][key], key
    assert result["now_playing"]["media_controls"] == flipped["now_playing"]["media_controls"]
    assert (result["preset"]["offset_x"], result["preset"]["offset_y"]) == (OFFSET_MAX, OFFSET_MIN)
    assert result["preset"]["scale"] == SCALE_MAX and result["font_size"] == FONT_SIZE_MAX
    # The usual boolean spellings are read; never bool(value).
    spelled = normalize_fullscreen_overlays({"preset": {"always_show": "on", "card": "off"}})["preset"]
    assert (spelled["always_show"], spelled["card"]) == (True, False)
    assert normalize_fullscreen_overlays({"preset": {"scale": SCALE_MIN / 10}})["preset"]["scale"] == SCALE_MIN
    for raw, expected in ((SCALE_MAX * 10, SCALE_MAX), (SCALE_MIN / 10, SCALE_MIN), ("big", None)):
        result = normalize_fullscreen_overlays({"now_playing": {"artwork_scale": raw}})["now_playing"]
        default = canonical_fullscreen_overlays()["now_playing"]["artwork_scale"]
        assert result["artwork_scale"] == (default if expected is None else expected)
    # The single-axis extents: text boxes clamp to 0 (natural) .. TEXT_EXTENT_MAX ems, artwork shape like a scale.
    for raw, expected in ((-3.0, 0.0), (TEXT_EXTENT_MAX * 10, TEXT_EXTENT_MAX), ("wide", None), (float("inf"), None)):
        for overlay in OVERLAY_IDS:
            result = normalize_fullscreen_overlays({overlay: {"text_width": raw, "text_height": raw}})[overlay]
            for key in TEXT_EXTENT_KEYS:
                assert result[key] == (canonical[overlay][key] if expected is None else expected), (overlay, key, raw)
    for raw, expected in ((SCALE_MAX * 10, SCALE_MAX), (SCALE_MIN / 10, SCALE_MIN), ("tall", None)):
        result = normalize_fullscreen_overlays({"now_playing": {"artwork_width": raw, "artwork_height": raw}})
        for key in ("artwork_width", "artwork_height"):
            assert result["now_playing"][key] == (canonical["now_playing"][key] if expected is None else expected)


def test_a_value_stored_before_the_single_axis_extents_reads_them_as_the_natural_look():
    """Persisted input: a value from before the extents existed (every member but them) normalises with each extent at
    its canonical (natural) value and everything stored kept; a second normalisation changes nothing. No bridge: the
    one normaliser fills a missing member from the canonical default, member by member."""
    canonical = canonical_fullscreen_overlays()
    stored = _flipped()
    for overlay in OVERLAY_IDS:
        for key in (*TEXT_EXTENT_KEYS, "artwork_width", "artwork_height"):
            stored[overlay].pop(key, None)
    result = normalize_fullscreen_overlays(stored)
    for overlay in OVERLAY_IDS:
        for key, item in result[overlay].items():
            assert item == (stored[overlay][key] if key in stored[overlay] else canonical[overlay][key]), key
    assert normalize_fullscreen_overlays(result) == result


# ------------------------------------------------------------------------------- model and section ownership


def test_typed_model_field_defaults_from_canonical_authority_and_serialises():
    model = SpotifyVisualizerSettings()
    assert model.fullscreen_overlays == canonical_fullscreen_overlays()
    model.fullscreen_overlays = _flipped()
    assert model.to_dict()[FULLSCREEN_OVERLAYS_KEY] == _flipped()


def test_the_section_normaliser_keeps_it_and_repairs_it():
    section = deepcopy(get_default_settings()["widgets"]["spotify_visualizer"])
    section[KEY] = _flipped()
    assert normalize_visualizer_section_mapping(section)[KEY] == _flipped()
    section[KEY] = "garbage"
    assert normalize_visualizer_section_mapping(section)[KEY] == canonical_fullscreen_overlays()
    section.pop(KEY)
    assert normalize_visualizer_section_mapping(section)[KEY] == canonical_fullscreen_overlays()


@pytest.mark.parametrize("mode", ACTIVE_MODES)
def test_presets_and_the_custom_snapshot_never_carry_it(mode):
    section = deepcopy(get_default_settings()["widgets"]["spotify_visualizer"])
    section[KEY] = _flipped()
    assert KEY not in normalize_visualizer_mode_payload(mode, section)
    assert KEY not in build_normalized_custom_snapshot(mode, section)
    for index in range(get_preset_count(mode)):
        assert apply_preset_to_config(mode, index, section)[KEY] == _flipped()


@pytest.mark.parametrize("mode", ACTIVE_MODES)
def test_the_runtime_preset_transaction_keeps_it(mode, tmp_path):
    settings = _manager(tmp_path)
    settings.set(f"widgets.spotify_visualizer.{KEY}", _flipped())
    settings.set("widgets.spotify_visualizer.mode", mode)
    section = settings.get("widgets.spotify_visualizer")
    target = resolve_next_visualizer_runtime_preset(
        section, settings.get("visualizer_custom_presets", {}) or {}, mode=mode, direction=1)
    settings.replace_visualizer_runtime_preset_state(target.visualizer_config, target.custom_presets)
    assert settings.get(f"widgets.spotify_visualizer.{KEY}") == _flipped()
    assert settings.get(f"widgets.spotify_visualizer.{get_preset_key(mode)}") == target.target_index
    assert 0 <= target.target_index <= get_custom_preset_index(mode)


def test_reset_restores_the_canonical_default(tmp_path):
    settings = _manager(tmp_path)
    settings.set(f"widgets.spotify_visualizer.{KEY}", _flipped())
    assert settings.get(f"widgets.spotify_visualizer.{KEY}") == _flipped()
    settings.reset_to_defaults()
    assert settings.get(f"widgets.spotify_visualizer.{KEY}") == canonical_fullscreen_overlays()


def test_the_settings_bucket_identities_are_canonical():
    """Fullscreen Mode's buckets are declared by canonical defaults (unknown bucket keys fail loud)."""
    from core.settings.ui_bucket_state import visualizer_bucket_scope
    from ui.tabs.visualizers_fullscreen_page import FULLSCREEN_BUCKET_SCOPE

    states = get_default_settings()["ui"]["visualizer_bucket_states"]
    keys = [key for key in states if visualizer_bucket_scope(key) == FULLSCREEN_BUCKET_SCOPE]
    assert len(keys) >= 3 and all(states[key] is False for key in keys)    # closed by default


# --------------------------------------------------------------------------- the preset toast's display name


@pytest.mark.parametrize("mode", ACTIVE_MODES)
def test_the_preset_toast_names_the_active_preset_in_title_case(mode):
    from core.settings.visualizer_presets import get_preset_names
    from utils.text_utils import title_case
    from widgets.spotify_visualizer.expanded_overlays import resolve_active_preset_display_name

    names = get_preset_names(mode)
    for index, name in enumerate(names):
        section = {"mode": mode, get_preset_key(mode): index}
        resolved = resolve_active_preset_display_name(section)
        assert resolved == title_case(name.strip()) and resolved
    assert resolve_active_preset_display_name(None) == ""


def test_title_case_is_the_one_shared_rule():
    """The Settings copy rule and the runtime's are one function (no runtime copy of the typography rule)."""
    import ui.onboarding.common as settings_copy
    from utils.text_utils import title_case

    assert settings_copy.title_case is title_case
    assert title_case("neon nights in the city") == "Neon Nights in the City"


def test_the_qml_projection_carries_every_option():
    from widgets.spotify_visualizer.expanded_overlays import resolve_expanded_overlay_config

    value = _flipped()
    projected = resolve_expanded_overlay_config({KEY: value})
    assert projected["fontFamily"] == value["font_family"] and projected["fontSize"] == value["font_size"]
    for overlay, name in (("preset", "preset"), ("now_playing", "nowPlaying")):
        options = value[overlay]
        assert projected[name]["corner"] == options["corner"]
        assert projected[name]["alwaysShow"] is options["always_show"]
        assert projected[name]["card"] is options["card"]
        assert (projected[name]["offsetX"], projected[name]["offsetY"], projected[name]["scale"]) == (
            options["offset_x"], options["offset_y"], options["scale"])
        assert (projected[name]["textWidth"], projected[name]["textHeight"]) == (
            options["text_width"], options["text_height"])
    assert (projected["nowPlaying"]["artworkWidth"], projected["nowPlaying"]["artworkHeight"]) == (
        value["now_playing"]["artwork_width"], value["now_playing"]["artwork_height"])
    assert projected["nowPlaying"]["mediaControls"] is value["now_playing"]["media_controls"]
    assert "mediaControls" not in projected["preset"]
    assert projected["nowPlaying"]["artworkScale"] == value["now_playing"]["artwork_scale"]
    assert "artworkScale" not in projected["preset"]


# ------------------------------------------------------------- a new corner rebases the offset (M3c decision)


def _inward(corner: str) -> tuple[float, float]:
    return (1.0 if corner.endswith("_left") else -1.0, 1.0 if corner.startswith("top_") else -1.0)


@pytest.mark.parametrize("source", CORNERS)
@pytest.mark.parametrize("target", CORNERS)
def test_a_new_corner_keeps_an_offset_that_stays_in_bounds_and_resets_one_that_would_not(source, target):
    """Settings' Corner rebases Fullscreen Edit's offset: per axis, kept when it still points into the display from
    the new corner, reset to zero when it would push the overlay out past the new anchor's edge."""

    for offset_x in (-0.4, -0.05, 0.0, 0.05, 0.4):
        for offset_y in (-0.3, 0.0, 0.3):
            options = dict(canonical_fullscreen_overlays()["now_playing"], corner=source, offset_x=offset_x,
                           offset_y=offset_y, scale=1.25, artwork_scale=0.75)
            result = rebase_offset_for_corner(options, target)
            inward_x, inward_y = _inward(target)
            assert result["corner"] == target
            assert result["offset_x"] == (offset_x if offset_x * inward_x >= 0.0 else 0.0)
            assert result["offset_y"] == (offset_y if offset_y * inward_y >= 0.0 else 0.0)
            # A kept offset lands the overlay inside the safe area from its new anchor (a toy overlay a fifth of it).
            size = 0.2
            for kept, inward in ((result["offset_x"], inward_x), (result["offset_y"], inward_y)):
                anchor = 0.0 if inward > 0 else 1.0 - size
                assert 0.0 <= anchor + kept <= 1.0 - size + 1e-9 or abs(kept) > 1.0 - size
            # Everything but the anchor and its offset is untouched.
            assert {k: v for k, v in result.items() if k not in ("corner", "offset_x", "offset_y")} == {
                k: v for k, v in options.items() if k not in ("corner", "offset_x", "offset_y")}
    assert rebase_offset_for_corner({"corner": source, "offset_x": 0.1}, "middle")["corner"] == source
