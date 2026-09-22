"""Research/probation candidates for future built-in NEWS widgets.

This is *not* the shipped provider catalog.  Entries are intentionally inert
until the native probation tool establishes repeated fetch/parse evidence and a
later checkpoint promotes them into product descriptors.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NewsFeedCandidate:
    candidate_id: str
    provider: str
    category: str
    url: str
    official_directory: str


NEWS_WIDGET_IDS: tuple[str, ...] = (
    "feeds_news_world",
    "feeds_news_us",
    "feeds_news_politics",
    "feeds_news_gaming",
    "feeds_news_tech",
)


NEWS_CANDIDATES: tuple[NewsFeedCandidate, ...] = (
    NewsFeedCandidate("cbs_us", "CBS News", "us", "https://www.cbsnews.com/latest/rss/us", "https://www.cbsnews.com/rss/"),
    NewsFeedCandidate("abc_us", "ABC News", "us", "https://abcnews.go.com/abcnews/usheadlines", "https://abcnews.go.com/Site/page/rss-feeds-3520115"),
    NewsFeedCandidate("cbs_world", "CBS News", "world", "https://www.cbsnews.com/latest/rss/world", "https://www.cbsnews.com/rss/"),
    NewsFeedCandidate("abc_world", "ABC News", "world", "https://abcnews.go.com/abcnews/worldnewsheadlines", "https://abcnews.go.com/Site/page/rss-feeds-3520115"),
    NewsFeedCandidate("cbs_politics", "CBS News", "politics", "https://www.cbsnews.com/latest/rss/politics", "https://www.cbsnews.com/rss/"),
    NewsFeedCandidate("abc_politics", "ABC News", "politics", "https://abcnews.go.com/abcnews/politicsheadlines", "https://abcnews.go.com/Site/page/rss-feeds-3520115"),
    NewsFeedCandidate("cbs_technology", "CBS News", "tech", "https://www.cbsnews.com/latest/rss/technology", "https://www.cbsnews.com/rss/"),
    NewsFeedCandidate("abc_technology", "ABC News", "tech", "https://abcnews.go.com/abcnews/technologyheadlines", "https://abcnews.go.com/Site/page/rss-feeds-3520115"),
    NewsFeedCandidate("ars_all", "Ars Technica", "tech", "https://feeds.arstechnica.com/arstechnica/index", "https://arstechnica.com/rss-feeds/"),
    NewsFeedCandidate("ars_gaming", "Ars Technica", "gaming", "https://feeds.arstechnica.com/arstechnica/gaming", "https://arstechnica.com/rss-feeds/"),
    # Kept as probation candidates rather than product promises. The probe
    # must establish native reachability before Gaming NEWS can ship with the
    # required two-provider floor.
    NewsFeedCandidate("pcgamer_all", "PC Gamer", "gaming", "https://www.pcgamer.com/rss/", "https://www.pcgamer.com/"),
)
