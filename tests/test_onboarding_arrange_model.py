"""Draft-only Arrange regression bars; no QML/runtime/provider construction."""
from __future__ import annotations

from copy import deepcopy
import pytest

from PySide6.QtCore import QRect

from ui.onboarding.arrange_model import ArrangeDisplay, ArrangeModel
from core.settings.default_settings import DEFAULT_SETTINGS
from core.settings.layout_slots import save_layout_slot


def _display() -> ArrangeDisplay:
    return ArrangeDisplay("screen:test", ("screen:test",), QRect(0, 0, 1000, 700), "1")


def _two_displays() -> tuple[ArrangeDisplay, ArrangeDisplay]:
    return (_display(), ArrangeDisplay("screen:two", ("screen:two",), QRect(1000, 0, 1000, 700), "2"))


def _widgets() -> dict:
    return {
        "family_activation": {"weather": True},
        "weather": {"enabled": True, "position": "Top Right", "monitor": "1", "margin": 24},
    }


def _custom_payload(widgets: dict, widget_id: str, variant: str = "default") -> dict:
    return widgets["custom_layout"]["displays"]["screen:test"][widget_id][variant]["size_payload"]


def _only_default_widget(widget_id: str) -> dict:
    widgets = deepcopy(DEFAULT_SETTINGS["widgets"])
    for family in widgets["family_activation"]:
        widgets["family_activation"][family] = False
    family = {
        "clock": "clocks",
        "spotify_visualizer": "visualizers",
    }[widget_id]
    widgets["family_activation"][family] = True
    if widget_id == "spotify_visualizer":
        widgets["family_activation"]["media"] = True
    return widgets


def test_authored_arrange_view_is_inert_until_an_operator_moves_it() -> None:
    widgets = _widgets()
    model = ArrangeModel(widgets, (_display(),))

    assert len(model.session.items()) == 1
    assert model.pending is False
    assert model.apply() == widgets


def test_first_authored_move_becomes_content_sized_custom_and_apply_is_explicit() -> None:
    model = ArrangeModel(_widgets(), (_display(),))
    item = model.session.items()[0]
    model.move(item.source_key, QRect(650, 42, 300, 150))

    assert model.pending is True
    assert model.free_placement(item.source_key) is True
    committed = model.apply()
    payload = committed["custom_layout"]["displays"]["screen:test"]["weather"]["default"]["size_payload"]
    assert payload["_size_from_content"] is True
    assert payload["_placement_anchor"] == "right,top"
    assert committed["weather"]["position"] == "Custom"


def test_settings_scale_keeps_promoted_content_sized_entry_and_discard_is_lossless() -> None:
    model = ArrangeModel(_widgets(), (_display(),))
    item = model.session.items()[0]
    model.move(item.source_key, QRect(650, 42, 300, 150))
    model.scale(item.source_key, 1.25)
    committed = model.apply()
    payload = committed["custom_layout"]["displays"]["screen:test"]["weather"]["default"]["size_payload"]
    assert payload["_size_from_content"] is True
    assert payload["_custom_resize_scale"] == 1.25

    clean = ArrangeModel(committed, (_display(),))
    before = deepcopy(clean.widgets)
    clean.move(clean.session.items()[0].source_key, QRect(500, 80, 320, 170))
    clean.discard()
    assert clean.widgets == before


def test_slot_load_is_draft_only_and_slot_save_refuses_pending_edits() -> None:
    widgets = _widgets()
    model = ArrangeModel(widgets, (_display(),))
    assert model.save_slot("1") is True
    snapshot = deepcopy(model._committed)
    item = model.session.items()[0]
    model.move(item.source_key, QRect(650, 42, 300, 150))
    assert model.save_slot("2") is False
    assert model.load_slot("1") is True
    assert model.pending is True
    assert model._committed == snapshot


def test_arrange_page_is_offscreen_draft_until_apply(qt_app) -> None:
    from ui.onboarding.arrange import ArrangePage

    class Settings:
        def __init__(self): self.values = {"widgets": _widgets()}; self.writes = []
        def get(self, key, default=None): return self.values.get(key, default)
        def set(self, key, value): self.values[key] = value; self.writes.append(key)

    settings = Settings()
    page = ArrangePage(settings)
    try:
        item = page.model.session.items()[0]
        page.model.move(item.source_key, QRect(650, 42, 300, 150))
        page._pending_changed()
        assert settings.writes == []
        assert page.leave() is True
        assert settings.writes == ["widgets"]
    finally:
        page.deleteLater()


def test_default_widget_map_admits_every_enabled_custom_capable_widget(qt_app) -> None:
    """The Settings canvas must cover production defaults, including Volume OSD."""

    from ui.onboarding.arrange import ArrangePage

    widgets = deepcopy(DEFAULT_SETTINGS["widgets"])
    model = ArrangeModel(widgets, (_display(),))
    osd = next(item for item in model.session.items() if item.model_identity == "system_audio_osd")
    assert osd.current_global_rect.size().width() == widgets["system_audio_osd"]["preferred_width"]
    assert osd.current_global_rect.size().height() == widgets["system_audio_osd"]["preferred_height"]

    class Settings:
        def __init__(self): self.values = {"widgets": widgets, "display": {"show_on_monitors": "ALL"}}; self.writes = []
        def get(self, key, default=None):
            value = self.values
            for part in key.split("."):
                if not isinstance(value, dict) or part not in value: return default
                value = value[part]
            return deepcopy(value)
        def set(self, key, value): self.writes.append(key)

    page = ArrangePage(Settings())
    try:
        assert any(item.model_identity == "system_audio_osd" for item in page.model.session.items())
        assert page.load_slot("missing") is False
    finally:
        page.deleteLater()


def test_arrange_page_opens_from_an_isolated_settings_manager_default_map(qt_app, tmp_path) -> None:
    """Capture-shaped Settings construction stays wholly local and provider-free."""

    from core.settings.settings_manager import SettingsManager
    from ui.onboarding.arrange import ArrangePage

    settings = SettingsManager(application="onboarding_arrange_test", storage_base_dir=tmp_path)
    page = ArrangePage(settings)
    try:
        assert any(item.model_identity == "system_audio_osd" for item in page.model.session.items())
        assert page.model.pending is False
    finally:
        page.deleteLater()
        settings.deleteLater()


@pytest.mark.parametrize("widget_id,payload_key", [("clock", "font_size"), ("weather", "_custom_resize_scale"), ("spotify_visualizer", "width")])
def test_settings_scale_promotes_each_resize_mode_to_content_sized(widget_id, payload_key) -> None:
    widgets = deepcopy(DEFAULT_SETTINGS["widgets"])
    for family in widgets["family_activation"]: widgets["family_activation"][family] = False
    if widget_id == "clock":
        widgets["family_activation"]["clocks"] = True
    elif widget_id == "weather":
        widgets["family_activation"]["weather"] = True
    else:
        widgets["family_activation"]["media"] = True; widgets["family_activation"]["visualizers"] = True
    model = ArrangeModel(widgets, (_display(),))
    item = next(entry for entry in model.session.items() if entry.model_identity == widget_id)
    model.scale(item.source_key, 1.2)
    result = model.apply()
    payload = result["custom_layout"]["displays"]["screen:test"][widget_id][item.source_key.geometry_variant]["size_payload"]
    assert payload["_size_from_content"] is True
    assert payload_key in payload


def test_existing_explicit_custom_entry_remains_explicit_when_scaled_in_settings() -> None:
    model = ArrangeModel(_widgets(), (_display(),))
    item = model.session.items()[0]
    model.move(item.source_key, QRect(650, 42, 300, 150))
    content = model.apply()
    payload = content["custom_layout"]["displays"]["screen:test"]["weather"]["default"]["size_payload"]
    payload.pop("_size_from_content"); payload.pop("_placement_anchor")
    explicit = ArrangeModel(content, (_display(),))
    explicit.scale(explicit.session.items()[0].source_key, 1.1)
    result = explicit.apply()
    payload = result["custom_layout"]["displays"]["screen:test"]["weather"]["default"]["size_payload"]
    assert "_size_from_content" not in payload


def test_all_route_promotes_one_content_sized_entry_per_selected_display() -> None:
    widgets = _widgets(); widgets["weather"]["monitor"] = "ALL"
    model = ArrangeModel(widgets, _two_displays())
    first = model.session.items()[0]
    model.move(first.source_key, QRect(650, 42, 300, 150))
    result = model.apply()
    displays = result["custom_layout"]["displays"]
    for screen in ("screen:test", "screen:two"):
        assert displays[screen]["weather"]["default"]["size_payload"]["_size_from_content"] is True


def test_reset_one_parent_display_keeps_other_display_payload_untouched() -> None:
    widgets = _widgets(); widgets["weather"]["monitor"] = "ALL"
    seeded = ArrangeModel(widgets, _two_displays())
    seeded.move(seeded.session.items()[0].source_key, QRect(650, 42, 300, 150))
    committed = seeded.apply()
    other_payload = committed["custom_layout"]["displays"]["screen:two"]["weather"]["default"]["size_payload"]
    other_payload["child_geometry"] = {"retained_child": [0.5, 0.5]}
    model = ArrangeModel(committed, _two_displays())
    first = next(item for item in model.session.items() if item.source_key.display_identity == "screen:test")
    model.reset(first.source_key)
    result = model.apply()
    assert "weather" not in result["custom_layout"]["displays"].get("screen:test", {})
    assert result["custom_layout"]["displays"]["screen:two"]["weather"]["default"]["size_payload"]["child_geometry"] == {"retained_child": [0.5, 0.5]}


def test_arrange_page_list_selects_small_or_overlapping_item_and_scales_content(qt_app, monkeypatch) -> None:
    from ui.onboarding.arrange import ArrangePage

    class Settings:
        def __init__(self):
            self.values = {"widgets": _widgets(), "display": {"show_on_monitors": "ALL"}}
        def get(self, key, default=None):
            value = self.values
            for part in key.split("."):
                if not isinstance(value, dict) or part not in value:
                    return deepcopy(default)
                value = value[part]
            return deepcopy(value)
        def set(self, key, value): self.values[key] = deepcopy(value)

    page = ArrangePage(Settings())
    try:
        page.item_list.setCurrentRow(0)
        item = page.model.session.selected_item()
        assert item is not None
        assert "display 1" in page.item_list.currentItem().text()
        page.scale_slider.setValue(125)
        assert item.content_sized is True
        assert item.resize_scale == pytest.approx(1.25)
        assert "size follows content" in page.selection_hint.text()
    finally:
        page.deleteLater()


def test_arrange_page_refuses_pending_slot_load_until_confirmed(qt_app, monkeypatch) -> None:
    from ui.onboarding.arrange import ArrangePage
    import ui.onboarding.arrange as arrange_module

    class Settings:
        def __init__(self): self.values = {"widgets": _widgets(), "display": {"show_on_monitors": "ALL"}}
        def get(self, key, default=None):
            value = self.values
            for part in key.split("."):
                if not isinstance(value, dict) or part not in value: return deepcopy(default)
                value = value[part]
            return deepcopy(value)
        def set(self, key, value): self.values[key] = deepcopy(value)

    page = ArrangePage(Settings())
    try:
        assert page.model.save_slot("1") is True
        item = page.model.session.items()[0]
        page.model.move(item.source_key, QRect(650, 42, 300, 150))
        monkeypatch.setattr(arrange_module.StyledPopup, "question", lambda *_args, **_kwargs: False)
        assert page.load_slot("1") is False
        assert page.model.pending is True
        monkeypatch.setattr(arrange_module.StyledPopup, "question", lambda *_args, **_kwargs: True)
        assert page.load_slot("1") is True
        assert page.model.pending is True
    finally:
        page.deleteLater()


def test_settings_scale_keeps_the_selected_content_anchor_exact() -> None:
    model = ArrangeModel(_widgets(), (_display(),))
    item = model.session.items()[0]
    model.move(item.source_key, QRect(650, 42, 300, 150))
    before = QRect(model.item(item.source_key).current_global_rect)
    model.scale(item.source_key, 1.25)
    scaled = model.item(item.source_key).current_global_rect
    # Top-right remains the authority while Settings changes the estimate.
    assert scaled.x() + scaled.width() == before.x() + before.width()
    assert scaled.y() == before.y()
    payload = model.apply()["custom_layout"]["displays"]["screen:test"]["weather"]["default"]["size_payload"]
    assert payload["_placement_anchor"] == "right,top"


def test_cross_display_drag_transfers_with_runtime_threshold_and_commits_route() -> None:
    model = ArrangeModel(_widgets(), _two_displays())
    item = model.session.items()[0]
    proposed = QRect(1050, 42, 300, 150)
    model.move(item.source_key, proposed, cursor_global=proposed.center())

    moved = model.item(item.source_key)
    assert moved.current_display_identity == "screen:two"
    assert moved.current_monitor_route == "2"
    result = model.apply()
    assert result["weather"]["monitor"] == "2"
    assert "weather" in result["custom_layout"]["displays"]["screen:two"]


def test_settings_scale_promotes_all_route_peers_to_content_sized_entries() -> None:
    widgets = _widgets()
    widgets["weather"]["monitor"] = "ALL"
    model = ArrangeModel(widgets, _two_displays())
    item = model.session.items()[0]
    model.scale(item.source_key, 1.2)
    result = model.apply()
    for screen in ("screen:test", "screen:two"):
        payload = result["custom_layout"]["displays"][screen]["weather"]["default"]["size_payload"]
        assert payload["_size_from_content"] is True


def test_authored_same_anchor_items_use_the_runtime_stack_projection() -> None:
    widgets = deepcopy(DEFAULT_SETTINGS["widgets"])
    for family in widgets["family_activation"]:
        widgets["family_activation"][family] = False
    widgets["family_activation"]["weather"] = True
    widgets["family_activation"]["system_stats"] = True
    widgets["weather"].update(enabled=True, position="Top Right", monitor="1")
    widgets["system_stats"].update(enabled=True, position="Top Right", monitor="1")
    model = ArrangeModel(widgets, (_display(),))
    weather = next(item for item in model.session.items() if item.model_identity == "weather")
    stats = next(item for item in model.session.items() if item.model_identity == "system_stats")
    assert weather.current_global_rect != stats.current_global_rect


def test_existing_content_extent_and_child_payload_survive_move_exactly() -> None:
    seeded = ArrangeModel(_widgets(), (_display(),))
    seeded_item = seeded.session.items()[0]
    seeded.move(seeded_item.source_key, QRect(600, 50, 360, 240))
    widgets = seeded.apply()
    payload = _custom_payload(widgets, "weather")
    payload.pop("_size_from_content")
    payload.pop("_placement_anchor")
    payload["content_extent"] = [520.0, 310.0]
    payload["child_geometry"] = {
        "condition_icon": {
            "width_scale": 1.25,
            "height_scale": 0.75,
            "future_child_field": ["keep", 4],
        },
        "future_role": {"opaque": [1, 2, 3]},
    }
    payload["future_payload"] = {"nested": [True, "keep", 9]}
    before = deepcopy(payload)

    model = ArrangeModel(widgets, (_display(),))
    item = model.session.items()[0]
    assert item.current_content_extent == (520.0, 310.0)
    assert "condition_icon" in item.current_child_sizes
    model.move(item.source_key, QRect(500, 80, 360, 240))
    result = model.apply()

    assert _custom_payload(result, "weather") == before

    scaled = ArrangeModel(result, (_display(),))
    scaled_item = scaled.session.items()[0]
    scaled.scale(scaled_item.source_key, 1.1)
    scaled_payload = _custom_payload(scaled.apply(), "weather")
    assert scaled_payload["content_extent"] == before["content_extent"]
    assert scaled_payload["child_geometry"] == before["child_geometry"]
    assert scaled_payload["future_payload"] == before["future_payload"]


def test_visualizer_viewport_rotation_and_future_payload_survive_move_and_scale() -> None:
    seeded = ArrangeModel(_only_default_widget("spotify_visualizer"), (_display(),))
    item = next(entry for entry in seeded.session.items() if entry.model_identity == "spotify_visualizer")
    seeded.move(item.source_key, QRect(300, 100, 420, 280))
    widgets = seeded.apply()
    payload = _custom_payload(widgets, "spotify_visualizer")
    payload.pop("_size_from_content")
    payload.pop("_placement_anchor")
    payload.update(width=420, height=280)
    payload["viewport_extent"] = [610.0, 333.0]
    payload["content_rotation_quarters_by_mode"] = {
        "spectrum": 1,
        "oscilloscope": 3,
    }
    payload["future_visualizer_state"] = {"opaque": ["x", 7]}
    preserved = {
        key: deepcopy(payload[key])
        for key in (
            "viewport_extent",
            "content_rotation_quarters_by_mode",
            "future_visualizer_state",
        )
    }

    model = ArrangeModel(widgets, (_display(),))
    item = next(entry for entry in model.session.items() if entry.model_identity == "spotify_visualizer")
    assert item.current_viewport_extent == (610.0, 333.0)
    model.move(item.source_key, QRect(250, 120, 420, 280))
    model.scale(item.source_key, 1.1)
    result = model.apply()
    result_payload = _custom_payload(result, "spotify_visualizer")

    for key, value in preserved.items():
        assert result_payload[key] == value
    assert result_payload["width"] == 462
    assert result_payload["height"] == 308


def test_repeated_saved_clock_scaling_uses_absolute_scale_without_payload_loss() -> None:
    widgets = _only_default_widget("clock")
    first = ArrangeModel(widgets, (_display(),))
    item = next(entry for entry in first.session.items() if entry.model_identity == "clock")
    first.scale(item.source_key, 1.2)
    saved = first.apply()
    payload = _custom_payload(saved, "clock", item.source_key.geometry_variant)
    payload["clock_bool"] = True
    payload["clock_list"] = [1, "opaque"]
    payload["clock_text"] = "keep"
    first_font = payload["font_size"]

    second = ArrangeModel(saved, (_display(),))
    item = next(entry for entry in second.session.items() if entry.model_identity == "clock")
    assert item.baseline_resize_scale == pytest.approx(1.2)
    second.scale(item.source_key, 1.2)
    result_payload = _custom_payload(
        second.apply(), "clock", item.source_key.geometry_variant
    )

    assert result_payload["font_size"] == round(first_font * 1.2)
    assert result_payload["_custom_resize_scale"] == pytest.approx(1.44)
    assert result_payload["clock_bool"] is True
    assert result_payload["clock_list"] == [1, "opaque"]
    assert result_payload["clock_text"] == "keep"


def test_slot_load_refreshes_authored_estimates_from_loaded_layout_fields() -> None:
    widgets = _widgets()
    widgets["weather"]["font_size"] = 18
    assert save_layout_slot(widgets, "1") is True
    widgets["weather"]["font_size"] = 44
    model = ArrangeModel(widgets, (_display(),))
    before_width = model._estimates["weather"].estimated_width

    assert model.load_slot("1") is True

    assert model.widgets["weather"]["font_size"] == 18
    assert model._estimates["weather"].estimated_width < before_width


def test_arrange_page_refreshes_selected_list_route_after_drag_finishes(qt_app) -> None:
    from ui.onboarding.arrange import ArrangePage

    class Settings:
        def __init__(self): self.values = {"widgets": _widgets(), "display": {"show_on_monitors": "ALL"}}
        def get(self, key, default=None):
            value = self.values
            for part in key.split("."):
                if not isinstance(value, dict) or part not in value: return deepcopy(default)
                value = value[part]
            return deepcopy(value)
        def set(self, key, value): self.values[key] = deepcopy(value)

    page = ArrangePage(Settings())
    try:
        item = page.model.session.items()[0]
        page.model.transfer(item.source_key, item.current_display_identity, item.current_global_rect)
        page.model.session.select_item(item)
        # The canvas owns the completion seam; it rebuilds labels after a transfer.
        page.canvas.dragFinished.emit()
        assert "display 1" in page.item_list.item(0).text()
    finally:
        page.deleteLater()


def test_apply_merges_onto_current_settings_instead_of_a_stale_snapshot() -> None:
    """A write made elsewhere while a draft is pending must survive Apply."""
    widgets = _widgets()
    model = ArrangeModel(widgets, (_display(),))
    item = next(iter(model.session.active_items()))
    model.move(item.source_key, item.current_global_rect.translated(-200, 120))

    current = deepcopy(widgets)
    current["weather"]["enabled"] = False          # toggled on another page meanwhile
    current["weather"]["location"] = "Oslo"        # an unrelated content edit
    current["layout_slots"] = {"slots": {"3": {"version": 2, "widgets": {}}}}  # slot saved elsewhere
    result = model.apply(base=current)

    assert result["weather"]["enabled"] is False
    assert result["weather"]["location"] == "Oslo"
    assert result["layout_slots"] == current["layout_slots"]
    assert result["weather"]["position"] == "Custom"   # the draft's placement landed
    assert "screen:test" in result["custom_layout"]["displays"]
