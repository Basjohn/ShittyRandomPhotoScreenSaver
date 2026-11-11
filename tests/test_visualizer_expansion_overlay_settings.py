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
    LEGACY_ARTWORK_FACTOR_KEYS,
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
    VOLUME_OSD_ID,
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
        for key in TEXT_EXTENT_KEYS:
            options[key] = 7.5 if options[key] != 7.5 else 3.25
    return value


def _manager(root: Path) -> SettingsManager:
    return SettingsManager(organization="TestOrg", application=f"TestApp_{uuid.uuid4().hex}", storage_base_dir=root)


# ------------------------------------------------------------------------------------- schema and normaliser


@pytest.mark.parametrize("profile", [NORMAL_PROFILE, MC_PROFILE])
def test_canonical_default_has_the_schema_every_consumer_reads(profile):
    value = require_canonical_default(FULLSCREEN_OVERLAYS_KEY, profile)
    assert isinstance(value["font_family"], str) and value["font_family"].strip()
    assert isinstance(value["font_size"], int) and FONT_SIZE_MIN <= value["font_size"] <= FONT_SIZE_MAX
    assert set(value) == {"font_family", "font_size", *OVERLAY_IDS, VOLUME_OSD_ID}
    # The Volume OSD's placement over the expanded card: placement members only (no Settings options).
    assert set(value[VOLUME_OSD_ID]) == set(PLACEMENT_KEYS[VOLUME_OSD_ID])
    assert all(isinstance(number, float) for number in value[VOLUME_OSD_ID].values())
    for overlay in OVERLAY_IDS:
        options = value[overlay]
        # Placement: anchor corner + offset + scale relative to the safe area (M3c edits them).
        assert options["corner"] in CORNERS
        assert isinstance(options["offset_x"], float) and isinstance(options["offset_y"], float)
        assert isinstance(options["scale"], float)
        assert isinstance(options["always_show"], bool) and isinstance(options["card"], bool)
    assert isinstance(value["now_playing"]["media_controls"], bool)
    assert "media_controls" not in value["preset"]
    # One artwork size carrier (plan 1B.7d): the artwork child record; the retired block factors are not members.
    assert not set(LEGACY_ARTWORK_FACTOR_KEYS) & set(value["now_playing"])
    # The single-axis extents (Fullscreen Edit's side handles): every overlay's text box.
    for overlay in OVERLAY_IDS:
        assert all(isinstance(value[overlay][key], float) for key in TEXT_EXTENT_KEYS)
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


@pytest.mark.parametrize("style", ["bar", "floating"])
def test_transport_style_survives_normalization_and_runtime_projection(style):
    from widgets.spotify_visualizer.expanded_overlays import resolve_expanded_overlay_config

    value = normalize_fullscreen_overlays({"now_playing": {"media_controls_style": style}})
    assert value["now_playing"]["media_controls_style"] == style
    projected = resolve_expanded_overlay_config({"fullscreen_overlays": value})
    assert projected["nowPlaying"]["mediaControlsStyle"] == style


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
    # The single-axis extents: text boxes clamp to 0 (natural) .. TEXT_EXTENT_MAX ems, artwork shape like a scale.
    for raw, expected in ((-3.0, 0.0), (TEXT_EXTENT_MAX * 10, TEXT_EXTENT_MAX), ("wide", None), (float("inf"), None)):
        for overlay in OVERLAY_IDS:
            result = normalize_fullscreen_overlays({overlay: {"text_width": raw, "text_height": raw}})[overlay]
            for key in TEXT_EXTENT_KEYS:
                assert result[key] == (canonical[overlay][key] if expected is None else expected), (overlay, key, raw)


def test_a_value_stored_with_the_retired_artwork_factors_loads_them_into_the_artwork_record():
    """Load bridge (plan 1B.7d, Persisted_Input_Compatibility.md): the block factors ``artwork_scale`` /
    ``artwork_width`` / ``artwork_height`` multiply into the ``artwork`` child record (the one carrier), keeping the
    artwork's drawn size; an existing record's factors compose; the role's limits clamp; unit factors add nothing; a
    malformed factor reads as 1; the result is normal (a second pass changes nothing)."""
    from core.settings.fullscreen_overlays import NOW_PLAYING_CHILD_ROLES

    artwork = next(role for role in NOW_PLAYING_CHILD_ROLES if role.role_id == "artwork")
    stored = {"now_playing": {"artwork_scale": 1.5, "artwork_width": 1.2, "artwork_height": 0.8,
                              "child_geometry": {"artwork": {"width_scale": 1.1, "height_scale": 1.0,
                                                             "x_offset": 0.05, "y_offset": -0.02}}}}
    result = normalize_fullscreen_overlays(stored)["now_playing"]
    assert not set(LEGACY_ARTWORK_FACTOR_KEYS) & set(result)
    record = result["child_geometry"]["artwork"]
    assert record["width_scale"] == pytest.approx(min(artwork.maximum_scale[0], 1.1 * 1.5 * 1.2))
    assert record["height_scale"] == pytest.approx(1.5 * 0.8)
    assert (record["x_offset"], record["y_offset"]) == (0.05, -0.02)
    assert normalize_fullscreen_overlays({"now_playing": result})["now_playing"] == result
    unit = normalize_fullscreen_overlays({"now_playing": {"artwork_scale": 1.0, "artwork_width": "tall"}})
    assert unit["now_playing"]["child_geometry"] == {}
    huge = normalize_fullscreen_overlays({"now_playing": {"artwork_scale": 3.0, "artwork_width": 3.0}})
    assert huge["now_playing"]["child_geometry"]["artwork"]["width_scale"] == pytest.approx(artwork.maximum_scale[0])


LEGACY_PROFILE = Path(__file__).resolve().parent / "fixtures" / "fullscreen_overlays_legacy_artwork_factors_profile.json"


def test_a_raw_profile_file_with_the_retired_artwork_factors_loads_through_the_bridge(tmp_path):
    """A settings file as an older build wrote it (``now_playing`` carrying ``artwork_scale`` / ``artwork_width`` /
    ``artwork_height`` beside an artwork record; never normalised by today's write path) loads, through a fresh
    manager reading the file, to the Now Playing geometry the load bridge gives that raw value: the factors fold into
    the artwork record once, every other stored member is kept, and a save + reload changes nothing."""
    import json
    import shutil

    from core.settings.fullscreen_overlays import NOW_PLAYING_CHILD_ROLES
    from core.settings.json_store import determine_storage_path
    from widgets.spotify_visualizer.expanded_overlays import resolve_expanded_overlay_config

    raw = json.loads(LEGACY_PROFILE.read_text(encoding="utf-8"))["snapshot"]["widgets"]["spotify_visualizer"][KEY]
    raw_now = raw["now_playing"]
    # The fixture is the old shape (distinguishing: non-unit factors beside a record).
    assert set(LEGACY_ARTWORK_FACTOR_KEYS) <= set(raw_now)
    assert any(raw_now[key] != 1.0 for key in LEGACY_ARTWORK_FACTOR_KEYS)

    application = f"TestApp_{uuid.uuid4().hex}"
    path = determine_storage_path(application, base_dir=tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(LEGACY_PROFILE, path)

    settings = _manager_for(tmp_path, application)
    loaded = normalize_fullscreen_overlays(settings.get(FULLSCREEN_OVERLAYS_KEY))
    expected = normalize_fullscreen_overlays(raw)
    assert loaded == expected

    now = loaded["now_playing"]
    assert not set(LEGACY_ARTWORK_FACTOR_KEYS) & set(now)
    for key, item in raw_now.items():
        if key not in LEGACY_ARTWORK_FACTOR_KEYS and key != "child_geometry":
            assert now[key] == item, key
    assert now["child_geometry"]["title"] == raw_now["child_geometry"]["title"]
    artwork_role = next(role for role in NOW_PLAYING_CHILD_ROLES if role.role_id == "artwork")
    record, stored = now["child_geometry"]["artwork"], raw_now["child_geometry"]["artwork"]
    assert record["width_scale"] == pytest.approx(min(artwork_role.maximum_scale[0], stored["width_scale"]
                                                      * raw_now["artwork_scale"] * raw_now["artwork_width"]))
    assert record["height_scale"] == pytest.approx(min(artwork_role.maximum_scale[1], stored["height_scale"]
                                                       * raw_now["artwork_scale"] * raw_now["artwork_height"]))
    # The runtime's projection (what the expanded overlay draws) reads the same geometry.
    section = settings.get("widgets.spotify_visualizer")
    assert resolve_expanded_overlay_config(section)["nowPlaying"] == resolve_expanded_overlay_config(
        {KEY: expected})["nowPlaying"]

    # Saved and read again (a restart after the bridge ran): the factors are not applied a second time.
    settings.set(FULLSCREEN_OVERLAYS_KEY, loaded)
    settings.save()
    assert normalize_fullscreen_overlays(_manager_for(tmp_path, application).get(FULLSCREEN_OVERLAYS_KEY)) == expected


def _manager_for(root: Path, application: str) -> SettingsManager:
    return SettingsManager(organization="TestOrg", application=application, storage_base_dir=root)


def test_a_value_stored_before_the_single_axis_extents_reads_them_as_the_natural_look():
    """Persisted input: a value from before the extents existed (every member but them) normalises with each extent at
    its canonical (natural) value and everything stored kept; a second normalisation changes nothing. No bridge: the
    one normaliser fills a missing member from the canonical default, member by member."""
    canonical = canonical_fullscreen_overlays()
    stored = _flipped()
    for overlay in OVERLAY_IDS:
        for key in TEXT_EXTENT_KEYS:
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
    assert not {"artworkScale", "artworkWidth", "artworkHeight"} & set(projected["nowPlaying"])   # one carrier
    assert projected["nowPlaying"]["mediaControls"] is value["now_playing"]["media_controls"]
    assert "mediaControls" not in projected["preset"]
    assert projected["nowPlaying"]["hoverReveal"] is value["now_playing"]["hover_reveal"]
    assert "hoverReveal" not in projected["preset"]
    # Now Playing's part records reach the QML as plain values (never a reference into the settings value).
    value["now_playing"]["child_geometry"] = {"title": {"width_scale": 1.25, "height_scale": 1.25, "x_offset": 0.5}}
    projected = resolve_expanded_overlay_config({KEY: value})
    assert projected["nowPlaying"]["childGeometry"] == value["now_playing"]["child_geometry"]
    assert projected["nowPlaying"]["childGeometry"]["title"] is not value["now_playing"]["child_geometry"]["title"]
    assert "childGeometry" not in projected["preset"]


# ----------------------------------------- Now Playing's parts: ordinary Edit's child records (operator, 8 Nov)


def test_now_playings_part_records_are_ordinary_child_geometry_and_old_values_read_as_todays_look():
    """``now_playing.child_geometry`` is ordinary Edit's CUSTOM child carrier for the block's declared roles: parsed
    by the same ``normalize_child_geometry`` (known roles only, clamped by each role's own bounds, authored records
    omitted), idempotent. A value stored before it (and before Show On Hover) reads both members as the canonical
    value, everything stored kept; no bridge."""
    from core.settings.fullscreen_overlays import CHILD_GEOMETRY_KEY, NOW_PLAYING_CHILD_ROLES

    canonical = canonical_fullscreen_overlays()
    roles = {role.role_id: role for role in NOW_PLAYING_CHILD_ROLES}
    assert {"artwork", "title", "artist", "album", "controls", "seek_bar"} == set(roles)
    assert all(role.movable for role in roles.values())
    assert CHILD_GEOMETRY_KEY in PLACEMENT_KEYS["now_playing"] and CHILD_GEOMETRY_KEY not in canonical["preset"]
    # The canonical value holds no record: every part where today's layout puts it.
    assert normalize_fullscreen_overlays(canonical)["now_playing"][CHILD_GEOMETRY_KEY] == {}

    stored = _flipped()
    for key in (CHILD_GEOMETRY_KEY, "hover_reveal"):
        stored["now_playing"].pop(key)
    result = normalize_fullscreen_overlays(stored)
    for key, item in result["now_playing"].items():
        assert item == (stored["now_playing"][key] if key in stored["now_playing"] else canonical["now_playing"][key])
    assert normalize_fullscreen_overlays(result) == result

    title_max = roles["title"].maximum_scale[0]
    raw = {"title": {"width_scale": title_max * 10, "x_offset": 0.25},
           "artwork": {"width_scale": 1.5, "height_scale": 0.75, "y_offset": -0.5},
           "controls": {"width_scale": 1.0, "height_scale": 1.0},          # authored: omitted
           "artist": "junk", "stray": {"width_scale": 2.0}}
    records = normalize_fullscreen_overlays({"now_playing": {CHILD_GEOMETRY_KEY: raw}})["now_playing"][
        CHILD_GEOMETRY_KEY]
    assert set(records) == {"title", "artwork"}
    assert records["title"]["width_scale"] == records["title"]["height_scale"] == title_max   # uniform, clamped
    assert records["title"]["x_offset"] == 0.25
    assert records["artwork"] == raw["artwork"] | {"width_scale": 1.5, "height_scale": 0.75}
    value = normalize_fullscreen_overlays({"now_playing": {CHILD_GEOMETRY_KEY: records}})
    assert value["now_playing"][CHILD_GEOMETRY_KEY] == records
    for junk in (None, "x", 3, []):
        assert normalize_fullscreen_overlays({"now_playing": {CHILD_GEOMETRY_KEY: junk}})["now_playing"][
            CHILD_GEOMETRY_KEY] == {}


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
