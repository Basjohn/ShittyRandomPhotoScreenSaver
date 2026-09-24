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
