"""Cheap source admission shared by launch, Settings and Guided Setup."""


def has_image_sources(settings) -> bool:
    """Configuration readiness, without scanning folders or contacting feeds."""
    return bool(settings.get("sources.folders")) or bool(settings.get("sources.rss_feeds"))
