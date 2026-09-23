# 04 — Providers, Widget Models and Shared Threads

Owners audited: `widgets/*_runtime.py`, `core/media/media_controller.py`, `rendering/quick/widgets/*.py`,
`widgets/{clock_ticker,overlay_timers}.py`, `core/threading/manager.py`, `core/process/supervisor.py`,
`utils/image_prefetcher.py`, `sources/rss/*`.

**Binding:** R-66 (Media event ownership; no fast-poll fallback), R-84 (single-notify churn precedent; Toolhelp),
R-83/R-29/R-40 (provider cadence authority), R-41 (thread ownership), R-88 (Edit churn), Spec §Last-good cache.

## What is already healthy (do not re-audit)

- Media observation is event-owned with one refresh in flight + one pending dirty edge and a ~30 s watchdog
  (`widgets/media_runtime.py:820-891`); artwork decode is key-gated (only 2 decodes in the 8.5-min local run).
- Clock uses one shared 1 s ticker with weak subscribers (`widgets/clock_ticker.py`); hands step at 1 Hz with no
  continuous QML animation.
- Reddit/Gmail/Steam/Friend Pulse list models update rows in place with `dataChanged`.
- System Stats samples every ≥10 s on one shared owner; its bar `Behavior on width` (420 ms) is ≈4 % duty.
- All QML `Canvas` items repaint on explicit state edges only; no infinite animations exist in runtime QML.

---

## PW-02 — Media truth and user media commands share a FIFO 4-worker IO pool with network work · P1 · R3 · Risk Medium

**Evidence (source).** `ThreadManager` IO pool = 4 workers (`core/threading/manager.py:537`), a FIFO
`ThreadPoolExecutor`; `TaskPriority` is passive metadata (Guardrails §Qt Quick states this explicitly). The same
pool carries:

- Media refresh queries (`widgets/media_runtime.py:1043`) — the source of the Visualizer's play/pause truth
  (`quick_display_visualizer_owner.set_playing`);
- Media transport commands, submitted as `TaskPriority.HIGH` (`core/media/media_controller.py:776-784`) with
  inflight de-duplication (a command stuck in the queue causes later presses to be dropped, `:725-730`);
- every network provider: Reddit (10 s `requests` timeouts), Gmail IMAP (30 s), Steam (12 s), Feeds (4+8 s),
  Weather (10 s), RSS startup load (30 s), plus raw image prefetch decodes (`utils/image_prefetcher.py:390-398`)
  and System Stats samples.

`requests`/`urllib` timeouts do not bound DNS resolution (`getaddrinfo` has no timeout); an offline or DNS-stalled
start can pin all four workers for tens of seconds (`Current_Plan.md` already lists "native DNS/connect stall
retirement" as an open FEEDS check). During that window Media refreshes and transport commands queue behind them:
play/pause edges reach the Visualizer late (reactivity/latency is protected) and media keys can be silently dropped.

**Evidence step first (no new runtime instrumentation).** A focused test with a real `ThreadManager`: occupy the
four IO workers with blocking tasks, submit a Media refresh and a transport command, assert queue wait. Then a
physical check: start offline with Reddit/Feeds/Gmail enabled and press Play/Pause.

**Candidate repair if confirmed.** Give Media its own serial lane using the existing lane infrastructure — the
GSMTC session/subscriptions already live on a ThreadManager **affinity lane** (Spec §State/actions). Running refresh
queries and commands on that same owner is cleaner ownership (no per-query `request_async()` manager on arbitrary IO
threads) and removes head-of-line blocking without adding a generic executor. Alternatively bound network work with
per-family slots. Do **not** "fix" by raising the IO worker count (hides the ownership problem) or by adding a
Media poll.

**Must remain true.** R-66: native events feed the one shared owner; one in flight + one pending; watchdog unchanged;
no fast-poll fallback. Command result authority stays with the shared owner (Spec §Media transport).

- [ ] Fault-injection test written; result recorded.
- [ ] If confirmed: lane change + `tests/test_media_runtime*.py` + transport tests; physical offline-start check.

---

## PW-01 — Timeline edges re-read and re-hash the whole album-art thumbnail · P2 · R2 · Risk Low · `[~]`

**Evidence (local 2026-09-22 dev run).** `[MEDIA_EVENT] summary`: `events={'timeline': 119, 'playback': 2,
'media_properties': 2}`, `refreshes={'activation': 1, 'event': 121, 'reconcile': 17, 'command': 2}`; the verbose log
shows **85** `Thumbnail stream` reads (145–171 KB each) and only **2** `Artwork decode` lines. Each refresh opens the
WinRT thumbnail stream, reads it fully (`core/media/media_controller.py:1235-1275`), and hashes it to decide the key is
unchanged. Timeline edges (position/duration) cannot change artwork on their own.

**Proposal.** Make the refresh query scope reason-aware inside the one shared owner: timeline-only edges read
timeline/playback fields and reuse the prior artwork payload/key while the track identity (title/artist/album/
provider) is unchanged; `media_properties`, `playback`, `activation`, `reconcile`, `wake` and `command` keep the full
query. If the last full query produced no artwork for the current track, keep reading on subsequent events so a
lazily-published thumbnail is still picked up.

**Must remain true.** R-66 event ownership and coalescing; "every changing artwork surface fades" (ArtworkFadeImage);
no unchanged-image reupload; no new timer.

**Re-confirmed in the 2026-09-22 22:53–22:59 operator run:** `events={'timeline': 70, 'playback': 5,
'media_properties': 4}`, 90 refreshes, **97** `Thumbnail stream` reads, **4** `Artwork decode` lines.

**Implemented.** Timeline-only edges carry a scope flag through the existing coalescing (a collapsed pending edge is
full if any non-timeline edge joined it). Such a refresh passes `media_track_identity(current)` to
`get_current_track_from_io_worker(reuse_artwork_identity=...)`; the controller skips the thumbnail stream only when
the freshly read host/title/artist/album identity matches, and the runtime reuses the held payload (same key, no
decode). Refresh count is unchanged; `[MEDIA_EVENT] summary` now reports `artwork_reused=N`.

- [x] Bars in `tests/test_media_runtime.py`: timeline-only edge reuses without a read (fails without the fix),
      properties/playback always read, a timeline edge on a new track reads and decodes, no held artwork keeps
      reading (lazy thumbnail), collapsed pending edge scope.
- [ ] Physical: track change, same-album next track, podcast/video providers, artwork fade.

---

## PW-03 — One `stateChanged` notify for 30–67 properties per family model · P3 · R1 · Risk Low

**Evidence.** Properties sharing one notify signal: Media 67/84, Achievement Pulse 59/98, Abandonment 54/91,
Gmail 44/51, Weather 36/38, Clock 33/34, Reddit 27/32, System Stats 24/41, Friend Pulse 23/59, Feeds 13/33.
Clock emits every second (`rendering/quick/widgets/clock.py:646-657`) and Media on every refresh because the runtime
revision always advances (`rendering/quick/widgets/media.py:943-996`, `widgets/media_runtime.py:664`). Each emission
re-evaluates every binding on every property (Python getter calls on the GUI thread), not only the ones that changed.
R-84 measured 75–94 ms stalls from the same single-notify shape on the context menu.

**Proposal (only after measuring).** Split high-rate content (Clock time/angles; Media title/position/state) from
style/config notifies. Measure first with a QML binding-evaluation count or GUI event-loop timing around a Clock tick
and a Media timeline edge; the per-tick cost is expected to be small.

- [ ] Measured; decision recorded per family (Clock and Media first).

---

## PW-04 — `FeedRowsModel.replace_rows` resets the whole model on any change · P3 · R1 · Risk Low

`rendering/quick/widgets/feeds.py:399-406` uses `beginResetModel/endResetModel`, so any refresh that changes one row
retires every delegate and re-requests every local artwork `Image` (`asynchronous: true`). Reddit/Gmail/Steam
update in place (`reddit.py:419-455`). Do this together with the FEEDS multi-source gate so Custom 2–4 inherit the
in-place pattern.

- [ ] In-place row diff + `dataChanged`; retained-delegate identity test; artwork not reloaded for unchanged rows.

---

## PW-05 — Hand-rolled parentless deadline timers; `single_shot` has no cancel handle · P2 · R1 · Risk Low

`widgets/feed_runtime.py:59-78` and `widgets/steam_followed_runtime.py:50-72` duplicate the same `_default_schedule`
creating parentless `QTimer`s outside the generation-owned single-shot registry that the destruction barrier observes
(`core/threading/manager.py:1456-1578`). They exist because `ThreadManager.single_shot()` returns nothing. Both owners
clear the handle when the deadline fires (`feed_runtime.py:540-554`, `steam_followed_runtime.py:293`), so no
double-delete race was found — this is a structure/accounting gap that will multiply with FEEDS Custom 2–4.

- [ ] Return a cancel handle from `ThreadManager.single_shot` (same registry/generation cancellation), migrate both
      families, delete the duplicates. Barrier/lifecycle tests: a retired family leaves no scheduled single-shot.

---

## PW-06 — Supervisor heartbeat creates a new OS thread every 3 s · P3 · R1 · Risk Low

`core/process/supervisor.py:1491-1579` re-arms `threading.Timer` after every check (`WORKER_HEARTBEAT_INTERVAL_MS =
3000`): ≈1,200 thread create/destroy cycles per hour for the life of the image worker. Not a leak, but handle/thread
churn in a process whose handle behaviour is under R-84 scrutiny.

- [ ] Replace with one persistent heartbeat thread waiting on an `Event` with timeout, stopped and joined on
      supervisor shutdown; it must never be able to keep the process alive at exit (R-30), so keep daemon semantics
      unless the join is proven on every exit path. Keep the documented Qt-independence exemption.
      `tests/test_process_supervisor.py`.
