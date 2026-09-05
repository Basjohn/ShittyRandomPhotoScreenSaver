from __future__ import annotations

from copy import deepcopy

from core.settings.layout_slots import (
    apply_layout_slot,
    capture_layout_slot,
    get_layout_slot_payload,
    normalize_layout_slot_id,
    save_layout_slot,
)


def test_capture_layout_slot_includes_layout_state_and_excludes_sources():
    widgets = {
        "clock": {
            "enabled": True,
            "position": "Top Right",
            "monitor": "ALL",
            "font_size": 64,
            "timezone": "Europe/Paris",
        },
        "reddit": {
            "enabled": True,
            "position": "Bottom Left",
            "monitor": "2",
            "limit": 12,
            "font_size": 18,
            "subreddit": "CityPorn",
            "provider": "rss",
        },
        "gmail": {
            "enabled": False,
            "position": "Top Center",
            "limit": 5,
            "sender_subject_ratio": 42,
            "account_slot": "2",
            "filter_label": "Alerts",
        },
        "spotify_visualizer": {
            "enabled": True,
            "position": "Custom",
            "monitor": "1",
            "mode": "bubble",
            "bubble_big_count": 11,
        },
        "custom_layout": {"version": 2, "displays": {"screen:a": {"clock": {"digital": {"rect": {"x": 0.1}}}}}},
        "custom_layout_restore": {"widgets": {"clock": {"position": "Top Right", "monitor": "ALL"}}},
        "layout_slots": {"version": 1, "slots": {"1": {"bad": "recursive"}}},
    }

    payload = capture_layout_slot(widgets)

    assert payload["custom_layout"] == widgets["custom_layout"]
    assert payload["custom_layout_restore"] == widgets["custom_layout_restore"]
    assert payload["widgets"]["clock"] == {
        "enabled": True,
        "position": "Top Right",
        "monitor": "ALL",
        "font_size": 64,
    }
    assert payload["widgets"]["reddit"] == {
        "enabled": True,
        "position": "Bottom Left",
        "monitor": "2",
        "limit": 12,
        "font_size": 18,
    }
    assert payload["widgets"]["gmail"] == {
        "enabled": False,
        "position": "Top Center",
        "limit": 5,
        "sender_subject_ratio": 42,
    }
    assert payload["widgets"]["spotify_visualizer"] == {
        "enabled": True,
        "position": "Custom",
        "monitor": "1",
        "mode": "bubble",
    }
    assert "layout_slots" not in payload["widgets"]


def test_apply_layout_slot_preserves_sources_and_replaces_layout_fields():
    widgets = {
        "clock": {
            "position": "Bottom Right",
            "font_size": 30,
            "timezone": "local",
        },
        "reddit": {
            "position": "Top Left",
            "limit": 3,
            "subreddit": "Games",
            "provider": "public_json",
        },
        "custom_layout": {"version": 2, "displays": {"screen:stale": {"clock": {"digital": {}}}}},
        "layout_slots": {
            "version": 1,
            "slots": {
                "1": {
                    "version": 1,
                    "widgets": {
                        "clock": {"position": "Top Right", "font_size": 64},
                        "reddit": {
                            "position": "Bottom Left",
                            "limit": 12,
                            "subreddit": "ShouldNotApply",
                        },
                    },
                    "custom_layout": {"version": 2, "displays": {}},
                    "custom_layout_restore": {"widgets": {}},
                }
            },
        },
    }

    assert apply_layout_slot(widgets, "1") is True

    assert widgets["clock"]["position"] == "Top Right"
    assert widgets["clock"]["font_size"] == 64
    assert widgets["clock"]["timezone"] == "local"
    assert widgets["reddit"]["position"] == "Bottom Left"
    assert widgets["reddit"]["limit"] == 12
    assert widgets["reddit"]["subreddit"] == "Games"
    assert widgets["reddit"]["provider"] == "public_json"
    assert widgets["custom_layout"] == {"version": 2, "displays": {}}
    assert widgets["custom_layout_restore"] == {"widgets": {}}


def test_layout_slot_replays_ordinary_enabled_state_both_directions():
    widgets = {
        "clock": {"enabled": False, "position": "Top Left"},
        "weather": {"enabled": True, "position": "Top Right"},
        "layout_slots": {
            "version": 1,
            "slots": {
                "1": {
                    "version": 1,
                    "widgets": {
                        "clock": {"enabled": True, "position": "Bottom Right"},
                        "weather": {"enabled": False, "position": "Bottom Left"},
                    },
                    "custom_layout": {"version": 2, "displays": {}},
                    "custom_layout_restore": {"widgets": {}},
                }
            },
        },
    }

    assert apply_layout_slot(widgets, "1") is True

    assert widgets["clock"]["enabled"] is True
    assert widgets["clock"]["position"] == "Bottom Right"
    assert widgets["weather"]["enabled"] is False
    assert widgets["weather"]["position"] == "Bottom Left"


def test_layout_slot_saved_on_cannot_reactivate_deactivated_family():
    widgets = {
        "family_activation": {"clocks": False},
        "clock": {"enabled": False, "position": "Top Left"},
        "layout_slots": {
            "version": 1,
            "slots": {
                "1": {
                    "version": 1,
                    "widgets": {
                        "clock": {"enabled": True, "position": "Bottom Right"},
                    },
                    "custom_layout": {"version": 2, "displays": {}},
                    "custom_layout_restore": {"widgets": {}},
                }
            },
        },
    }

    assert apply_layout_slot(widgets, "1") is True

    assert widgets["family_activation"] == {"clocks": False}
    assert widgets["clock"]["enabled"] is False
    assert widgets["clock"]["position"] == "Bottom Right"


def test_layout_slot_saved_on_cannot_bypass_deactivated_family_dependency():
    widgets = {
        "family_activation": {"media": False, "visualizers": True},
        "spotify_visualizer": {"enabled": False, "position": "Top Left"},
        "layout_slots": {
            "version": 1,
            "slots": {
                "1": {
                    "version": 1,
                    "widgets": {
                        "spotify_visualizer": {
                            "enabled": True,
                            "position": "Bottom Right",
                        },
                    },
                    "custom_layout": {"version": 2, "displays": {}},
                    "custom_layout_restore": {"widgets": {}},
                }
            },
        },
    }

    assert apply_layout_slot(widgets, "1") is True

    assert widgets["family_activation"] == {
        "media": False,
        "visualizers": True,
    }
    assert widgets["spotify_visualizer"]["enabled"] is False
    assert widgets["spotify_visualizer"]["position"] == "Bottom Right"


def test_layout_slot_enabled_replay_preserves_provider_account_and_source_settings():
    widgets = {
        "reddit": {
            "enabled": False,
            "provider": "public_json",
            "subreddit": "Games",
        },
        "gmail": {
            "enabled": True,
            "account_slot": "2",
            "filter_label": "Alerts",
        },
        "layout_slots": {
            "version": 1,
            "slots": {
                "1": {
                    "version": 1,
                    "widgets": {
                        "reddit": {
                            "enabled": True,
                            "provider": "rss",
                            "subreddit": "CityPorn",
                        },
                        "gmail": {
                            "enabled": False,
                            "account_slot": "1",
                            "filter_label": "Inbox",
                        },
                    },
                    "custom_layout": {"version": 2, "displays": {}},
                    "custom_layout_restore": {"widgets": {}},
                }
            },
        },
    }

    assert apply_layout_slot(widgets, "1") is True

    assert widgets["reddit"] == {
        "enabled": True,
        "provider": "public_json",
        "subreddit": "Games",
    }
    assert widgets["gmail"] == {
        "enabled": False,
        "account_slot": "2",
        "filter_label": "Alerts",
    }


def test_slot_zero_round_trips_and_invalid_slots_do_not_mutate():
    widgets = {
        "clock": {"position": "Top Left", "font_size": 24},
        "reddit": {"subreddit": "All", "limit": 5},
    }

    assert save_layout_slot(widgets, "0") is True
    assert normalize_layout_slot_id("0") == "0"
    assert get_layout_slot_payload(widgets, "0") is not None

    widgets["clock"]["position"] = "Bottom Right"
    widgets["reddit"]["limit"] = 2
    before_invalid = deepcopy(widgets)

    assert apply_layout_slot(widgets, "bad") is False
    assert widgets == before_invalid

    assert apply_layout_slot(widgets, "0") is True
    assert widgets["clock"]["position"] == "Top Left"
    assert widgets["reddit"]["limit"] == 5


def test_save_layout_slot_never_recursively_captures_slots():
    widgets = {
        "clock": {"position": "Top Left", "font_size": 24},
        "layout_slots": {"version": 1, "slots": {"1": {"old": "payload"}}},
    }

    assert save_layout_slot(widgets, "2") is True
    payload = get_layout_slot_payload(widgets, "2")

    assert payload is not None
    assert "layout_slots" not in payload["widgets"]


def test_visualizer_layout_slot_round_trips_active_mode_without_copying_mode_tuning():
    widgets = {
        "spotify_visualizer": {
            "enabled": True,
            "position": "Custom",
            "monitor": "2",
            "mode": "sphere",
            "sphere_deformation": 4.25,
            "bubble_big_count": 17,
        },
    }

    assert save_layout_slot(widgets, "3") is True
    payload = get_layout_slot_payload(widgets, "3")
    assert payload is not None
    assert payload["widgets"]["spotify_visualizer"] == {
        "enabled": True,
        "position": "Custom",
        "monitor": "2",
        "mode": "sphere",
    }

    widgets["spotify_visualizer"].update(
        mode="bubble", sphere_deformation=1.25, bubble_big_count=4
    )
    assert apply_layout_slot(widgets, "3") is True
    assert widgets["spotify_visualizer"]["mode"] == "sphere"
    # A geometry slot selects the visible mode, but does not become a second
    # authority for per-mode presets/tuning.
    assert widgets["spotify_visualizer"]["sphere_deformation"] == 1.25
    assert widgets["spotify_visualizer"]["bubble_big_count"] == 4
