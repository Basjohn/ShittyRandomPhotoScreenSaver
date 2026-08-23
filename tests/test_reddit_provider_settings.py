from __future__ import annotations

from core.settings.defaults import get_default_settings
from core.settings.models import RedditWidgetSettings
from rendering.widget_runtime_services import get_runtime_service_spec


def test_reddit_defaults_use_rss_provider() -> None:
    defaults = get_default_settings()

    assert defaults["widgets"]["reddit"]["provider"] == "rss"


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


def test_reddit_widget_settings_round_trip_html_provider() -> None:
    settings = RedditWidgetSettings.from_mapping(
        {
            "provider": "html",
            "subreddit": "python",
            "limit": 7,
        }
    )

    assert settings.provider == "html"
    payload = settings.to_dict()
    assert payload["widgets.reddit.provider"] == "html"


def test_reddit2_inherits_family_provider_from_runtime_service() -> None:
    # E1 slice 2: the Reddit post-provider lifetime is owned by the neutral
    # runtime-service registry (not the QWidget factory). reddit2 with no own
    # provider must inherit the reddit family's provider through that registry.
    spec = get_runtime_service_spec("reddit2")
    assert spec is not None

    widgets_config = {
        "reddit": {"provider": "public_json", "font_family": "Inter", "font_size": 14},
        "reddit2": {"enabled": True, "subreddit": "games", "limit": 5},
    }
    service = spec.build("reddit2", widgets_config)
    assert getattr(service, "provider_id", None) == "public_json"


def test_reddit2_own_provider_overrides_family_inheritance() -> None:
    spec = get_runtime_service_spec("reddit2")
    assert spec is not None
    widgets_config = {
        "reddit": {"provider": "public_json"},
        "reddit2": {"provider": "html"},
    }
    service = spec.build("reddit2", widgets_config)
    assert getattr(service, "provider_id", None) == "html"


def test_reddit_missing_provider_normalizes_to_rss_default() -> None:
    spec = get_runtime_service_spec("reddit")
    assert spec is not None
    service = spec.build("reddit", {"reddit": {"subreddit": "games"}})
    assert getattr(service, "provider_id", None) == "rss"
