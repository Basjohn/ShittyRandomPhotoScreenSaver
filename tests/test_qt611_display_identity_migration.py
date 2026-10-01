"""Qt manufacturer drift cannot move CUSTOM cards or change a saved Clock face."""
from copy import deepcopy

import pytest
from PySide6.QtCore import QRect

from core.settings.default_settings import DEFAULT_SETTINGS
from core.widget_product_actions import update_clock_display_mode_override
from rendering.custom_layout_contract import (
    canonicalize_screen_layout_bucket,
    get_screen_layout_entries_for_screen,
    get_screen_signature,
    get_screen_signature_aliases,
    saved_screen_signature_aliases,
)
from rendering.quick.custom_layout_hydration import resolve_quick_committed_entry
from rendering.quick.state import capture_display_identity
from rendering.quick.widgets.clock import ClockPresentationConfig
from ui.onboarding.arrange_model import ArrangeDisplay, ArrangeModel


OLD = "serial:DB9A15270000|manufacturer:Microstep|model:MSI G321Q|name:MSI G321Q"
NEW = OLD.replace("Microstep", "osoft")
CANONICAL = "serial:DB9A15270000|model:MSI G321Q|name:MSI G321Q"


class Screen:
    def __init__(self, manufacturer="osoft", serial="DB9A15270000", model="MSI G321Q"):
        self.maker, self.serial, self.panel = manufacturer, serial, model

    serialNumber = lambda self: self.serial
    manufacturer = lambda self: self.maker
    model = lambda self: self.panel
    name = lambda self: "MSI G321Q"
    geometry = lambda self: QRect(0, 0, 1707, 960)
    availableGeometry = geometry
    devicePixelRatio = lambda self: 1.5
    refreshRate = lambda self: 165.0


def payload(x, *, mode="clock_font"):
    return {"rect": {"x": x, "y": .2, "width": .2, "height": .15},
            "size_payload": {"_custom_resize_scale": .75, "font_size": 49}, "resize_mode": mode}


def widgets():
    value = deepcopy(DEFAULT_SETTINGS["widgets"])
    value["family_activation"] = {family: family == "clocks" for family in value["family_activation"]}
    value["clock"].update(enabled=True, position="Custom", monitor="1", display_mode="analog",
                          display_mode_overrides={OLD: "digital"})
    value["clock2"]["enabled"] = value["clock3"]["enabled"] = False
    value["custom_layout"] = {"version": 2, "displays": {
        OLD: {"clock": {"digital": payload(.1)}},
        NEW: {"clock": {"analog": payload(.7)}},
    }}
    return value


def test_runtime_and_custom_share_one_serial_identity_despite_qt_metadata_drift():
    before, after = Screen("Microstep"), Screen()
    assert get_screen_signature(before) == get_screen_signature(after) == CANONICAL
    assert capture_display_identity(screen_index=0, runtime_generation=0, screen=after).screen_key == CANONICAL
    assert get_screen_signature(Screen(serial="other")) != CANONICAL
    assert get_screen_signature(Screen(model="other")) != CANONICAL
    assert get_screen_signature(Screen(serial="")) != get_screen_signature(Screen("Microstep", serial=""))


def test_reads_merge_old_independent_variants_without_mutating_saved_geometry():
    custom = widgets()["custom_layout"]
    before = deepcopy(custom)
    matched, entries = get_screen_layout_entries_for_screen(custom, Screen())
    assert matched == NEW
    assert entries["clock"] == {"digital": payload(.1), "analog": payload(.7)}
    assert custom == before
    assert get_screen_layout_entries_for_screen(custom, Screen(serial="other")) == (None, {})


def test_save_migrates_buckets_once_and_current_label_wins_conflicting_variant():
    custom = widgets()["custom_layout"]
    custom["displays"][NEW]["clock"]["digital"] = payload(.4)
    canonicalize_screen_layout_bucket(custom, Screen())
    assert custom["displays"] == {CANONICAL: {"clock": {"digital": payload(.4), "analog": payload(.7)}}}
    before = deepcopy(custom)
    canonicalize_screen_layout_bucket(custom, Screen())
    assert custom == before


def test_clock_hydration_recovers_the_saved_face_and_its_original_custom_box():
    value = widgets()
    config = ClockPresentationConfig.from_widgets_mapping("clock", value, display_signature=CANONICAL)
    assert config.display_mode == "digital"
    entry = resolve_quick_committed_entry(value, Screen(), "clock")
    assert entry is not None and entry.geometry_variant == "digital"
    assert entry.rect.x == .1 and entry.size_payload["font_size"] == 49


@pytest.mark.usefixtures("qt_app")
def test_arrange_reads_and_commits_the_same_box_and_migrates_all_face_variants():
    screen = Screen()
    value = widgets()
    display = ArrangeDisplay(CANONICAL, get_screen_signature_aliases(screen), screen.geometry(), "1")
    model = ArrangeModel(value, (display,))
    try:
        item, = model.session.items()
        assert item.source_key.geometry_variant == "digital"
        assert item.current_global_rect == QRect(171, 192, 341, 144)
        assert not model.pending and model.apply() == value
        model.move(item.source_key, item.current_global_rect.translated(1, 0), snap=False)
        committed = model.apply()
        assert list(committed["custom_layout"]["displays"]) == [CANONICAL]
        assert committed["custom_layout"]["displays"][CANONICAL]["clock"]["analog"] == payload(.7)
        assert resolve_quick_committed_entry(committed, screen, "clock").rect.x == pytest.approx(172 / 1707)
    finally:
        model._meter.close()


def test_clock_action_retires_old_override_key_without_changing_other_displays():
    value = widgets()
    value["clock"]["display_mode_overrides"]["screen:other"] = "analog"
    updated, changed = update_clock_display_mode_override(value, widget_id="clock", display_identity=CANONICAL,
                                                          normalized_mode="digital")
    assert changed
    assert updated["clock"]["display_mode_overrides"] == {CANONICAL: "digital", "screen:other": "analog"}
    assert value["clock"]["display_mode_overrides"][OLD] == "digital"
    assert not update_clock_display_mode_override(updated, widget_id="clock", display_identity=CANONICAL,
                                                  normalized_mode="digital")[1]


def test_serialless_quick_keys_migrate_encoding_without_guessing_identity():
    screen = Screen(serial="")
    canonical = get_screen_signature(screen)
    old = "manufacturer:osoft|model:MSI G321Q|name:MSI G321Q|geometry:(0, 0, 1707, 960)"
    assert old in saved_screen_signature_aliases((canonical,), {old: "digital"})
    assert old not in saved_screen_signature_aliases((get_screen_signature(Screen("Microstep", serial="")),), {old: "digital"})
    assert get_screen_signature_aliases(screen) == (canonical,)
