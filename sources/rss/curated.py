"""The one explicit curated-wallpaper source action."""


def apply_curated_wallpaper_feeds(settings) -> list[str]:
    """Replace feeds with the curated set; preserve folders and cached images."""
    from sources.rss.constants import DEFAULT_RSS_FEEDS

    feeds = list(DEFAULT_RSS_FEEDS.values())
    settings.set("sources.rss_feeds", feeds)
    settings.save()
    return feeds
