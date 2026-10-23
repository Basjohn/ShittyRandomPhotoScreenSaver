"""Headless tests for single-active Settings bucket persistence (no GUI or env setup)."""
from __future__ import annotations

import unittest

from core.settings.default_settings import DEFAULT_SETTINGS
from core.settings.ui_bucket_state import (
    normalize_active_visualizer_leaf_path,
    normalize_active_widget_bucket_path,
    project_settings_bucket_context,
    retire_settings_bucket_context,
    set_active_widget_bucket_path,
    sparse_open_bucket_states,
)


class MemorySettings:
    def __init__(self, **entries):
        self.entries = entries
        self.writes = []

    def get_application_name(self):
        return "Screensaver"

    def get(self, key):
        return self.entries.get(key)

    def set(self, key, value, *, emit_change=True):
        self.entries[key] = value
        self.writes.append((key, value, emit_change))


class SettingsActiveBucketPathTests(unittest.TestCase):
    def test_nested_steam_path_replaces_old_cohort(self):
        keys = ("steam:achievement_pulse", "steam:achievement_pulse_appearance",
                "steam:friend_pulse", "steam:friend_pulse_layout", "media:controls")
        states = dict.fromkeys(keys, False)
        set_active_widget_bucket_path(states, "steam:achievement_pulse", True)
        set_active_widget_bucket_path(states, "steam:achievement_pulse_appearance", True)
        self.assertEqual(sparse_open_bucket_states(states), {
            "steam:achievement_pulse": True, "steam:achievement_pulse_appearance": True,
        })
        set_active_widget_bucket_path(states, "steam:friend_pulse", True)
        self.assertEqual(sparse_open_bucket_states(states), {"steam:friend_pulse": True})
        set_active_widget_bucket_path(states, "steam:friend_pulse_layout", True)
        set_active_widget_bucket_path(states, "steam:friend_pulse", False)
        self.assertEqual(sparse_open_bucket_states(states), {})

    def test_legacy_nested_orphan_and_wrong_pills_are_pruned(self):
        keys = DEFAULT_SETTINGS["ui"]["widget_bucket_states"]
        raw = {"clock:time": True, "media:controls": True,
               "steam:achievement_pulse_appearance": True,
               "steam:achievement_pulse": True,
               "steam:friend_pulse_layout": True}
        result = normalize_active_widget_bucket_path(keys, raw, "steam")
        self.assertEqual(sparse_open_bucket_states(result), {
            "steam:friend_pulse": True, "steam:friend_pulse_layout": True,
        })
        self.assertFalse(any(normalize_active_widget_bucket_path(keys, raw, None).values()))

    def test_visualizer_only_selected_mode_leaf_remains(self):
        ui = DEFAULT_SETTINGS["ui"]
        custom, technical = normalize_active_visualizer_leaf_path(
            ui["visualizer_bucket_states"], ui["visualizer_tech_bucket_states"],
            {"bubble:appearance": True, "extruded_bubble:bubbles": True},
            {"extruded_bubble:agc": True}, "extruded_bubble")
        self.assertEqual(sparse_open_bucket_states(custom), {})
        self.assertEqual(sparse_open_bucket_states(technical), {"extruded_bubble:agc": True})

    def test_dialog_projection_preserves_one_current_path_and_retires_old(self):
        settings = MemorySettings(**{
            "ui.widget_bucket_states": {"clock:time": True, "steam:achievement_pulse_appearance": True},
            "ui.gmail_bucket_states": {"layout": True},
            "ui.visualizer_bucket_states": {"bubble:appearance": True},
            "ui.visualizer_tech_bucket_states": {"extruded_bubble:agc": True},
            "ui.visualizer_adv_states": {"bubble": True},
            "ui.visualizer_tech_states": {"extruded_bubble": True},
            "ui.basic_bucket_path": "sources:folders",
        })
        project_settings_bucket_context(settings, "widgets", "steam")
        self.assertEqual(settings.get("ui.widget_bucket_states"), {
            "steam:achievement_pulse": True, "steam:achievement_pulse_appearance": True,
        })
        for key in ("ui.gmail_bucket_states", "ui.visualizer_bucket_states", "ui.visualizer_tech_bucket_states",
                    "ui.visualizer_adv_states", "ui.visualizer_tech_states"):
            self.assertFalse(settings.get(key), key)
        self.assertEqual(settings.get("ui.basic_bucket_path"), "")
        self.assertTrue(all(not emitted for _, _, emitted in settings.writes))
        retire_settings_bucket_context(settings)
        self.assertEqual(settings.get("ui.widget_bucket_states"), {})

    def test_only_current_simple_tab_keeps_bucket(self):
        settings = MemorySettings(**{"ui.basic_bucket_path": "sources:feeds"})
        project_settings_bucket_context(settings, "sources")
        self.assertEqual(settings.get("ui.basic_bucket_path"), "sources:feeds")
        project_settings_bucket_context(settings, "transitions", "Particle")
        self.assertEqual(settings.get("ui.basic_bucket_path"), "")

    def test_projection_idempotent_on_clean_state(self):
        settings = MemorySettings(**{
            "ui.widget_bucket_states": {"media:controls": True},
            "ui.basic_bucket_path": "",
        })
        project_settings_bucket_context(settings, "widgets", "media")
        settings.writes.clear()
        project_settings_bucket_context(settings, "widgets", "media")
        self.assertEqual(settings.writes, [])


if __name__ == "__main__":
    unittest.main()
