"""
Wallpaper feeds (image RSS): a wallpaper pool acquired through the shared feed core.

Modules:
    constants    - historical curated URLs, cache bounds, rotation and politeness
    pools        - named discovery intents and bounded pass selection
    cache        - RSSCache: the on-disk pool, its size index, retirement, rejections
    image_fetch  - one vetted image stream per wallpaper, judged by its real pixels
    json_listing - generic JSON image listings read by shape (a FeedSource adapter)
    coordinator  - RSSCoordinator: acquisition passes and session rotation
"""
__all__ = [
    "RSSCoordinator",
    "RSSState",
]


def __getattr__(name):
    # Cheap source-readiness and pool Settings must not import image/network/Qt
    # acquisition machinery merely by importing the neutral pool catalogue.
    if name in __all__:
        from sources.rss.coordinator import RSSCoordinator, RSSState
        return {"RSSCoordinator": RSSCoordinator, "RSSState": RSSState}[name]
    raise AttributeError(name)
