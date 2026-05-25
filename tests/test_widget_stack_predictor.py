from __future__ import annotations


def test_widget_stack_predictor_includes_gmail_and_modern_reddit2_limit():
    from ui.widget_stack_predictor import WidgetType, build_widget_estimates

    estimates = build_widget_estimates(
        {
            "weather": {"enabled": True, "position": "Top Left", "font_size": 18},
            "gmail": {"enabled": True, "position": "Middle Left", "font_size": 18, "limit": 25, "width": 600},
            "reddit2": {"enabled": True, "position": "Bottom Left", "limit": 4},
            "reddit": {"font_size": 18},
        }
    )

    gmail = next(est for est in estimates if est.widget_type == WidgetType.GMAIL)
    reddit2 = next(est for est in estimates if est.widget_type == WidgetType.REDDIT2)

    assert gmail.estimated_width == 600
    assert gmail.estimated_height > 0
    assert reddit2.estimated_height > 0


def test_widget_stack_predictor_flags_same_column_conflict_across_top_middle_bottom():
    from ui.widget_stack_predictor import WidgetType, get_position_status_for_widget

    settings = {
        "global": {"stacking_enabled": True},
        "weather": {
            "enabled": True,
            "position": "Top Left",
            "monitor": "ALL",
            "font_size": 18,
        },
        "gmail": {
            "enabled": True,
            "position": "Middle Left",
            "monitor": "ALL",
            "font_size": 18,
            "limit": 25,
            "width": 600,
        },
        "reddit": {
            "enabled": True,
            "position": "Bottom Left",
            "monitor": "ALL",
            "font_size": 18,
            "limit": 25,
        },
    }

    can_stack, message = get_position_status_for_widget(
        settings,
        WidgetType.GMAIL,
        "Middle Left",
        "ALL",
    )

    assert can_stack is False
    assert "Conflicts with" in message


def test_widget_stack_predictor_suppresses_status_when_stacking_disabled():
    from ui.widget_stack_predictor import WidgetType, get_position_status_for_widget

    settings = {
        "global": {"stacking_enabled": False},
        "weather": {
            "enabled": True,
            "position": "Top Left",
            "monitor": "ALL",
            "font_size": 18,
        },
        "gmail": {
            "enabled": True,
            "position": "Middle Left",
            "monitor": "ALL",
            "font_size": 18,
            "limit": 25,
            "width": 600,
        },
    }

    can_stack, message = get_position_status_for_widget(
        settings,
        WidgetType.GMAIL,
        "Middle Left",
        "ALL",
    )

    assert can_stack is True
    assert message == ""


def test_widget_stack_predictor_reserves_spotify_visualizer_footprint_with_media():
    from ui.widget_stack_predictor import WidgetType, build_widget_estimates

    estimates = build_widget_estimates(
        {
            "media": {
                "enabled": True,
                "position": "Bottom Right",
                "monitor": "ALL",
                "font_size": 14,
                "artwork_size": 80,
            },
            "spotify_visualizer": {
                "enabled": True,
                "visualizers_enabled": True,
                "mode": "devcurve",
                "base_height": 80,
            },
        }
    )

    media = next(est for est in estimates if est.widget_type == WidgetType.MEDIA)
    visualizer = next(est for est in estimates if est.widget_type == WidgetType.SPOTIFY_VIS)

    assert visualizer.position == media.position
    assert visualizer.monitor == media.monitor
    assert visualizer.estimated_width == media.estimated_width
    assert visualizer.estimated_height > 0


def test_widget_stack_predictor_treats_media_visualizer_as_fixed_block_for_right_lane_conflicts():
    from ui.widget_stack_predictor import WidgetType, get_position_status_for_widget

    settings = {
        "global": {"stacking_enabled": True},
        "clock": {
            "enabled": True,
            "position": "Top Right",
            "monitor": "ALL",
            "font_size": 48,
            "display_mode": "analogue",
        },
        "gmail": {
            "enabled": True,
            "position": "Bottom Right",
            "monitor": "ALL",
            "font_size": 18,
            "limit": 25,
            "width": 600,
        },
        "media": {
            "enabled": True,
            "position": "Bottom Right",
            "monitor": "ALL",
            "font_size": 14,
            "artwork_size": 80,
        },
        "spotify_visualizer": {
            "enabled": True,
            "visualizers_enabled": True,
            "mode": "devcurve",
            "base_height": 80,
        },
    }

    can_stack, message = get_position_status_for_widget(
        settings,
        WidgetType.GMAIL,
        "Bottom Right",
        "ALL",
    )

    assert can_stack is False
    assert "Media" in message
