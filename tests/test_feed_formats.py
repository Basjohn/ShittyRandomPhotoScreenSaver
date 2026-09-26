"""Every feed format lands in one model with the same content rules.

Fixtures follow the shapes of live sources checked on 2026-09-24: JSON Feed
1.0/1.1 (jsonfeed.org, Daring Fireball, micro.blog), title-less microblog RSS
(Mastodon, Bluesky), IndieWeb h-feed pages (tantek.com's value-class dates,
aaronparecki.com's ``u-author h-card``), podcast episode art and Reddit's
page-suffix feed.
"""
from __future__ import annotations

import json

import pytest

from core.feeds.discovery import resolve_feed
from core.feeds.hfeed import hfeed_document
from core.feeds.normalization import iso_timestamp, title_from_text
from core.feeds.parser import FeedEmptyError, FeedParseError, parse_feed_bytes
from core.feeds.transport import FeedHttpResponse, FeedTransportError


def _json(value: object) -> bytes:
    return json.dumps(value).encode("utf-8")


JSON_FEED_11 = _json({
    "version": "https://jsonfeed.org/version/1.1",
    "title": "Fireball",
    "home_page_url": "https://fireball.test/",
    "authors": [{"name": "Gruber"}],
    "items": [
        {
            "id": "https://fireball.test/1",
            "url": "https://fireball.test/linked/1",
            "title": "Linked post",
            "content_html": '<p>Body text.</p><img src="/img/inline.jpg">',
            "date_published": "2026-09-23T18:55:22-04:00",
            "image": "https://cdn.fireball.test/hero.jpg",
            "attachments": [
                {"url": "https://cdn.fireball.test/episode.mp3", "mime_type": "audio/mpeg", "size_in_bytes": 1234},
                {"url": "https://cdn.fireball.test/extra.png", "mime_type": "image/png"},
            ],
        },
        {
            "id": 2,
            "url": "https://fireball.test/notes/2",
            "content_text": "A title-less note that has two sentences. The second continues here.",
            "date_modified": "2026-09-22T10:00:00Z",
            "authors": [{"name": "Guest"}],
        },
        "not an item",
    ],
})

JSON_FEED_10 = _json({
    "version": "https://jsonfeed.org/version/1",
    "title": "Micro",
    "items": [{"id": "a", "url": "https://micro.test/a", "content_html": "<p>Short note.</p>",
               "author": {"name": "Manton"}, "date_published": "2026-09-23T12:00:00+00:00"}],
})

JF2_FEED = _json({
    "type": "feed",
    "name": "Notes",
    "url": "https://jf2.test/",
    "children": [
        {"type": "entry", "name": "An article", "url": "https://jf2.test/a", "published": "2026-09-20T12:00:00Z",
         "content": {"html": "<p>Text</p>", "text": "Text"}, "photo": ["https://jf2.test/p.jpg"],
         "author": {"type": "card", "name": "Author"}},
        {"type": "entry", "url": "https://jf2.test/b", "content": "Just a note."},
    ],
})

MICROBLOG_RSS = b'''<?xml version="1.0"?><rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel>
<title>Eugen</title><link>https://social.test/@eugen</link>
<item><guid>https://social.test/@eugen/1</guid><link>https://social.test/@eugen/1</link>
 <description>&lt;p&gt;Peaches is such a beautiful baby.&lt;/p&gt;&lt;p&gt;#CatsOfSocial&lt;/p&gt;</description>
 <media:content url="https://files.social.test/cat.jpg" type="image/jpeg" medium="image"/></item>
<item><guid>https://social.test/@eugen/2</guid><link>https://social.test/@eugen/2</link></item>
</channel></rss>'''

PODCAST_RSS = b'''<?xml version="1.0"?><rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
 xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><title>Show</title><link>https://show.test/</link>
<item><guid>ep1</guid><title>Episode 1</title><link>https://show.test/1</link>
 <itunes:image href="https://show.test/art/ep1.jpg"/>
 <content:encoded><![CDATA[<p>Show notes only live in content.</p>]]></content:encoded></item>
</channel></rss>'''

HFEED_PAGE = '''<!doctype html><html><head><title>Tantek</title></head><body>
<div class="h-feed"><h1 class="p-name">Updates</h1>
 <article class="h-entry">
  <h2 class="p-name">A real article title</h2>
  <div class="e-content"><p>Article body.</p><img src="/photos/a.jpg" alt=""></div>
  <a class="u-url" href="/2026/263/a"><time class="dt-published" datetime="2026-09-20T12:00:00-07:00">Sep 20</time></a>
  <span class="p-author h-card"><a class="p-name u-url" href="/">Tantek</a></span>
  <div class="h-entry"><span class="p-name e-content">a reply inside the post</span></div>
 </article>
 <li class="h-entry">
  <span class="p-name e-content">A note that has no title of its own. It keeps going.</span>
  <a href="/2026/262/t1" class="dt-published u-url u-uid"><time class="value" datetime="12:00-0700">12:00</time>
   on <time class="value">2026-262</time></a>
  <a class="u-author h-card" href="https://author.test/"><img class="u-photo" src="/me.jpg" alt="">Aaron</a>
 </li>
</div></body></html>'''.encode()


def test_json_feed_11_maps_into_the_shared_model():
    document = parse_feed_bytes(JSON_FEED_11, source_url="https://fireball.test/feeds/json")
    assert (document.format, document.title, document.home_url) == ("json11", "Fireball", "https://fireball.test/")
    first, note = document.items
    assert first.title == "Linked post" and first.summary == "Body text."
    assert first.action_url == "https://fireball.test/linked/1" and first.author == "Gruber"
    assert first.published_at == iso_timestamp("2026-09-23T22:55:22Z")
    assert [image.url for image in first.images] == [
        "https://cdn.fireball.test/hero.jpg",
        "https://cdn.fireball.test/extra.png",
        "https://fireball.test/img/inline.jpg",
    ]
    assert [(e.url, e.mime_type, e.length) for e in first.enclosures] == [
        ("https://cdn.fireball.test/episode.mp3", "audio/mpeg", 1234)]
    # A title-less post takes its title from its own text; the summary continues.
    assert (note.title, note.summary) == ("A title-less note that has two sentences.", "The second continues here.")
    assert note.author == "Guest" and note.published_at == iso_timestamp("2026-09-22T10:00:00Z")


def test_json_feed_10_and_jf2_feeds():
    micro = parse_feed_bytes(JSON_FEED_10, source_url="https://micro.test/feed.json")
    assert micro.format == "json1"
    assert (micro.items[0].title, micro.items[0].author) == ("Short note.", "Manton")

    jf2 = parse_feed_bytes(JF2_FEED, source_url="https://jf2.test/feed.jf2")
    assert (jf2.format, jf2.title) == ("jf2", "Notes")
    article, note = jf2.items
    assert (article.title, article.author, article.images[0].url) == ("An article", "Author", "https://jf2.test/p.jpg")
    assert (note.title, note.action_url) == ("Just a note.", "https://jf2.test/b")


_NOT_USABLE_JSON = {
    "empty_json_feed": (b'{"version": "https://jsonfeed.org/version/1.1", "title": "Empty", "items": []}',
                        FeedEmptyError),
    "other_json_api": (b'{"status": "ok", "data": [1, 2, 3]}', FeedParseError),
    "truncated": (b'{"version": "https://jsonfeed.org/version/1", "items": ', FeedParseError),
    "hostile_nesting": (b'{"items": ' + b"[" * 200_000 + b"]" * 200_000 + b"}", FeedParseError),
}


@pytest.mark.parametrize("case", sorted(_NOT_USABLE_JSON))
def test_json_that_is_not_a_usable_feed_is_rejected_cleanly(case):
    payload, error = _NOT_USABLE_JSON[case]
    with pytest.raises(error):
        parse_feed_bytes(payload, source_url="https://site.test/feed.json")


def test_title_less_microblog_items_read_as_text_not_url_scraps():
    document = parse_feed_bytes(MICROBLOG_RSS, source_url="https://social.test/@eugen.rss")
    post, bare = document.items
    assert (post.title, post.summary) == ("Peaches is such a beautiful baby.", "#CatsOfSocial")
    assert post.images[0].url == "https://files.social.test/cat.jpg"
    # Nothing but a link: the URL-derived title remains the last resort.
    assert bare.title == "2"


def test_podcast_episode_art_and_content_only_summaries():
    item = parse_feed_bytes(PODCAST_RSS, source_url="https://show.test/feed").items[0]
    assert item.images[0].url == "https://show.test/art/ep1.jpg"
    assert item.summary == "Show notes only live in content."


def test_hfeed_page_reads_entries_value_class_dates_and_authors():
    document = hfeed_document(HFEED_PAGE, page_url="https://tantek.test/", max_items=10)
    assert document is not None
    assert (document.format, document.title) == ("h-feed", "Updates")
    article, note = document.items
    assert (article.title, article.summary) == ("A real article title", "Article body.")
    assert article.action_url == "https://tantek.test/2026/263/a"
    assert article.published_at == iso_timestamp("2026-09-20T19:00:00Z")
    assert article.author == "Tantek"
    assert article.images[0].url == "https://tantek.test/photos/a.jpg"
    # Note: name repeats content, so the title comes from the text; the date is
    # split across value-class children (ordinal date plus time and offset).
    assert (note.title, note.summary) == ("A note that has no title of its own.", "It keeps going.")
    assert note.published_at == iso_timestamp("2026-09-19T19:00:00Z")
    assert note.author == "Aaron"


def test_legacy_mf1_markup_is_not_mistaken_for_an_hfeed():
    page = b'<html><body><div class="hentry"><h2 class="entry-title">Theme markup</h2></div></body></html>'
    assert hfeed_document(page, page_url="https://blog.test/") is None


@pytest.mark.parametrize("value, expected", [
    ("2026-09-20T12:00:00Z", "2026-09-20T12:00:00+00:00"),
    ("2026-09-20T12:00-0700", "2026-09-20T19:00:00+00:00"),
    ("2026-263", "2026-09-20T00:00:00+00:00"),
    ("2026-09-20 12:00", "2026-09-20T12:00:00+00:00"),
    ("Sun, 20 Sep 2026 12:00:00 GMT", "2026-09-20T12:00:00+00:00"),
])
def test_iso_timestamps_cover_feed_date_shapes(value, expected):
    from datetime import datetime
    assert iso_timestamp(value) == int(datetime.fromisoformat(expected).timestamp())
    assert iso_timestamp("not a date") is None


def test_long_title_less_text_is_cut_at_a_word_with_the_rest_continuing():
    text = "word " * 60
    title, rest = title_from_text(text)
    assert title.endswith("…") and len(title) <= 141 and not title[:-1].endswith(" ")
    assert rest.startswith("…word")


class _Web:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def fetch(self, url, **kwargs):
        self.calls.append(url)
        answer = self.routes.get(url, FeedTransportError("HTTP 404", status_code=404))
        if isinstance(answer, Exception):
            raise answer
        return answer


def _page(url: str, payload: bytes) -> FeedHttpResponse:
    return FeedHttpResponse("ok", payload, url, content_type="text/html")


def test_json_feed_advertised_as_application_json_is_discovered():
    page = (b'<html><head><link rel="alternate" type="application/json" title="JSON Feed" href="/feed.json">'
            b'<link rel="alternate" type="application/json" title="JSON" href="/wp-json/"></head></html>')
    web = _Web({
        "https://micro.test": _page("https://micro.test/", page),
        "https://micro.test/feed.json": FeedHttpResponse("ok", JSON_FEED_10, "https://micro.test/feed.json",
                                                         content_type="application/json"),
    })
    resolution = resolve_feed(web.fetch, "https://micro.test")
    assert (resolution.feed_url, resolution.document.format) == ("https://micro.test/feed.json", "json1")
    assert web.calls == ["https://micro.test", "https://micro.test/feed.json"]


def test_hfeed_page_is_its_own_feed_only_when_it_declares_no_other():
    web = _Web({"https://tantek.test": _page("https://tantek.test/", HFEED_PAGE)})
    resolution = resolve_feed(web.fetch, "https://tantek.test")
    assert (resolution.via, resolution.document.format, len(web.calls)) == ("direct", "h-feed", 1)

    declared = HFEED_PAGE.replace(
        b"<title>", b'<link rel="alternate" type="application/atom+xml" href="/updates.atom"><title>')
    atom = (b'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>T</title>'
            b'<entry><id>1</id><title>Atom entry</title><link href="https://tantek.test/1"/></entry></feed>')
    web = _Web({
        "https://tantek.test": _page("https://tantek.test/", declared),
        "https://tantek.test/updates.atom": FeedHttpResponse("ok", atom, "https://tantek.test/updates.atom"),
    })
    resolution = resolve_feed(web.fetch, "https://tantek.test")
    assert (resolution.feed_url, resolution.document.format) == ("https://tantek.test/updates.atom", "atom10")


def test_page_suffix_feed_convention_resolves_a_subreddit_style_page():
    shell = b"<!DOCTYPE html><html><head><title>r/programming</title></head><body></body></html>"
    atom = (b'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>r/programming</title>'
            b'<entry><id>t3_1</id><title>Post</title><link href="https://forum.test/r/programming/1"/></entry></feed>')
    web = _Web({
        "https://forum.test/r/programming": _page("https://forum.test/r/programming/", shell),
        "https://forum.test/r/programming.rss": FeedHttpResponse(
            "ok", atom, "https://forum.test/r/programming.rss", content_type="application/atom+xml"),
    })
    resolution = resolve_feed(web.fetch, "https://forum.test/r/programming")
    assert (resolution.feed_url, resolution.via) == ("https://forum.test/r/programming.rss", "conventional")
    assert len(web.calls) == 2


def test_large_feeds_are_parsed_in_short_gil_holding_calls(monkeypatch):
    """No single XML parser call gets a whole large feed: each is one bounded
    chunk (a 1 MB feed in one call held the GIL ~7 ms), and the image markup
    recovered from the chunked parse is unchanged."""
    from xml.etree import ElementTree

    from core.feeds import parser as feed_parser

    items = "".join(
        f'<item><title>Story {i}</title><link>https://example.test/{i}</link>'
        f'<description><![CDATA[<p>{"x" * 4000}</p><img data-src="https://cdn.example.test/{i}.jpg">]]>'
        f'</description></item>'
        for i in range(60)
    )
    payload = f'<?xml version="1.0"?><rss version="2.0"><channel><title>Big</title>{items}</channel></rss>'.encode()
    assert len(payload) > 3 * feed_parser._XML_PARSE_CHUNK_BYTES

    fed: list[int] = []

    class RecordingParser(ElementTree.XMLParser):
        def feed(self, data):
            fed.append(len(data))
            return super().feed(data)

    monkeypatch.setattr(feed_parser.ElementTree, "XMLParser", RecordingParser)
    monkeypatch.setattr(feed_parser.ElementTree, "fromstring", None)  # never the one-shot parse
    document = parse_feed_bytes(payload, source_url="https://example.test/feed.xml", max_items=60)
    assert fed and max(fed) <= feed_parser._XML_PARSE_CHUNK_BYTES and sum(fed) == len(payload)
    assert [item.images[0].url for item in document.items] == [
        f"https://cdn.example.test/{i}.jpg" for i in range(60)]
