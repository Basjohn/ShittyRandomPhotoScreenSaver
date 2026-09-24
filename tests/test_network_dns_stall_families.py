"""Each IO-lane network family: a stalled DNS server can neither pin the lane nor hold exit.

Measured 2026-09-24: one stalled lookup pinned an IO worker, held the engine's
5 s exit wait and kept the process alive for the rest of the stall. FEEDS has
its own bar in ``test_feed_dns_stall.py``; the shared harness and its two
phases (retirement fence, process exit fence) are described in
``tests/_network_stall_harness.py``. Every request here goes through the
family's real transport seam with the fence its runtime actually passes.
"""
from __future__ import annotations

from tests._network_stall_harness import assert_lane_and_exit_bounded, run_family_stall


def test_reddit_requests_retire_with_the_widget_shutdown_event():
    facts = run_family_stall(
        category="reddit_fetch",
        setup="""
            from threading import Event
            import core.reddit_post_provider as reddit
            # The shared rate limiter may legitimately wait between requests and
            # persists state; it is not the network boundary under test.
            reddit._acquire_widget_reddit_request_slot = lambda request, **_k: "acquired"
            fence = Event()   # RedditRuntimeService._shutdown_event, set by stop()/retire()
            provider = reddit.RedditPublicJsonProvider(record_blocked=False)
        """,
        work="""
            provider.fetch_posts(reddit.RedditFetchRequest(
                subreddit="python", sort="hot", limit=10, cache_key="reddit",
                shutdown_event=fence))
        """,
        retire="fence.set()",
        rearm="fence = Event()",
    )
    assert_lane_and_exit_bounded(facts)


def test_weather_requests_retire_with_the_service_fence(tmp_path):
    facts = run_family_stall(
        category="weather_fetch",
        setup=f"""
            import weather.open_meteo_provider as open_meteo
            # Never the operator's profile cache.
            open_meteo._WEATHER_CACHE_FILE = {str(tmp_path / "open_meteo.json")!r}
            alive = [True]   # WeatherRuntimeService._still_wanted: running, not retired, current request
            provider = open_meteo.OpenMeteoProvider(timeout=10, persist_results=False,
                                                    should_continue=lambda: alive[0])
        """,
        work='provider.get_current_weather("London")',
        retire="alive[0] = False",
        rearm="alive[0] = True",
    )
    assert_lane_and_exit_bounded(facts)


def test_settings_geocode_lookups_retire_when_the_query_is_superseded():
    facts = run_family_stall(
        category="geocode",
        setup="""
            from ui.widgets.geocode_completer import GeocodeCompleter
            current = ["Lond"]   # GeocodeCompleter._pending_query; a keystroke replaces it
            query = "Lond"
        """,
        work="GeocodeCompleter._fetch_cities(query, should_continue=lambda: current[0] == query)",
        retire='current[0] = "London"',
        rearm='current[0] = "Lond"',
    )
    assert_lane_and_exit_bounded(facts)


def test_gmail_imap_fetch_retires_with_the_runtime_generation():
    """IMAP (App Password) is the operator's Gmail backend."""
    facts = run_family_stall(
        category="gmail_fetch",
        setup="""
            from core.gmail.gmail_imap import GmailImapClient
            alive = [True]   # GmailRuntime._fetch_is_retired, passed as should_cancel
            client = GmailImapClient("reader@example.test", "not-a-real-app-password")
        """,
        work='client.list_messages(label_ids=["INBOX"], max_results=5, should_cancel=lambda: not alive[0])',
        retire="alive[0] = False",
        rearm="alive[0] = True",
    )
    assert_lane_and_exit_bounded(facts)


def test_gmail_api_client_retires_with_the_runtime_generation():
    """The still-selectable OAuth/API backend uses the same fence."""
    facts = run_family_stall(
        category="gmail_fetch",
        setup="""
            from types import SimpleNamespace
            from core.gmail.gmail_client import GmailClient
            alive = [True]
            oauth = SimpleNamespace(credentials=SimpleNamespace(access_token="not-a-real-token"))
            client = GmailClient(oauth)
        """,
        work='client.list_messages(label_ids=["INBOX"], max_results=5, should_cancel=lambda: not alive[0])',
        retire="alive[0] = False",
        rearm="alive[0] = True",
    )
    assert_lane_and_exit_bounded(facts)


def test_steam_requests_are_bounded_by_the_dns_deadline_and_the_exit_fence():
    """Steam requests are shared across widgets through its request coordinators,
    so a single widget retiring does not cancel them: the DNS deadline frees the
    lane instead, and the process exit fence releases work in flight at exit."""
    facts = run_family_stall(
        category="steam",
        setup="""
            from core.steam.backend import SteamSourceId, build_endpoint, fetch_json
            endpoint = build_endpoint(SteamSourceId.PLAYER_SUMMARIES,
                                      api_key="not-a-real-key", steamids="76561197960287930")
        """,
        work="fetch_json(endpoint)",
        retire=None,
    )
    assert_lane_and_exit_bounded(facts, retirement_fenced=False)


def test_wallpaper_image_downloads_retire_with_the_pool_shutdown_check(tmp_path):
    facts = run_family_stall(
        category="rss",
        setup=f"""
            from pathlib import Path
            from sources.rss.image_fetch import fetch_wallpaper
            alive = [True]   # RSSCoordinator._alive: engine shutdown check and request_stop()
            cache = Path({str(tmp_path)!r})
        """,
        work='fetch_wallpaper("https://images.example.test/wallpaper.jpg", cache, file_stem="w", '
             'still_needed=lambda: alive[0], required=(1920, 1080))',
        retire="alive[0] = False",
        rearm="alive[0] = True",
    )
    assert_lane_and_exit_bounded(facts)
