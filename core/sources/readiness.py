"""Cheap source admission shared by launch, Settings and Guided Setup."""


def has_image_sources(settings) -> bool:
    """Configuration readiness, without scanning folders or contacting feeds."""
    from sources.rss.pools import online_source_count
    return bool(settings.get("sources.folders")) or bool(online_source_count(settings))
