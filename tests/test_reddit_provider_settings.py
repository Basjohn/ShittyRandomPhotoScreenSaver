from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication, QWidget

from core.settings.defaults import get_default_settings
from core.settings.models import RedditWidgetSettings
from rendering.widget_factories import RedditWidgetFactory


def test_reddit_defaults_use_pullpush_provider() -> None:
    defaults = get_default_settings()

    assert defaults["widgets"]["reddit"]["provider"] == "pullpush"


def test_reddit_widget_settings_round_trip_provider() -> None:
    settings = RedditWidgetSettings.from_mapping(
        {
            "provider": "public_json",
            "subreddit": "python",
            "limit": 7,
        }
    )

    assert settings.provider == "public_json"
    payload = settings.to_dict()
    assert payload["widgets.reddit.provider"] == "public_json"


def test_reddit2_inherits_family_provider_from_factory() -> None:
    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(1920, 1080)
    factory = RedditWidgetFactory(MagicMock())

    widget = None
    try:
        widget = factory.create(
            parent,
            {
                "enabled": True,
                "subreddit": "games",
                "limit": 5,
            },
            settings_key="reddit2",
            base_reddit_settings={
                "provider": "public_json",
                "font_family": "Inter",
                "font_size": 14,
            },
        )

        assert widget is not None
        assert getattr(widget._post_provider, "provider_id", None) == "public_json"  # type: ignore[attr-defined]
    finally:
        if widget is not None:
            widget.cleanup()
            widget.deleteLater()
        parent.deleteLater()
