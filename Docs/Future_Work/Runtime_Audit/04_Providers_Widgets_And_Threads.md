# 04 — Providers, Widget Models and Shared Threads

Owners audited: `widgets/*_runtime.py`, `core/media/media_controller.py`, `rendering/quick/widgets/*.py`,
`widgets/{clock_ticker,overlay_timers}.py`, `core/threading/manager.py`, `core/process/supervisor.py`,
`utils/image_prefetcher.py`, `sources/rss/*`. (PW-06, the supervisor heartbeat, is closed: 06 §Considered and
rejected.)

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
- D1 soak (08): `artwork_reused=1196` of 1,222 event refreshes over ≈92 minutes — the reuse works in real use.
- [ ] Physical: track change, same-album next track, podcast/video providers, artwork fade.

---

## PW-03 — One `stateChanged` notify for 30–67 properties per family model · P3 · R1 · Risk Low · Clock `[~]`

**Evidence.** Properties sharing one notify signal: Media 67/84, Achievement Pulse 59/98, Abandonment 54/91,
Gmail 44/51, Weather 36/38, Clock 33/34, Reddit 27/32, System Stats 24/41, Friend Pulse 23/59, Feeds 13/33.
Clock emits every second (`rendering/quick/widgets/clock.py:646-657`) and Media on every refresh because the runtime
revision always advances (`rendering/quick/widgets/media.py:943-996`, `widgets/media_runtime.py:664`). Each emission
re-evaluates every binding on every property. **Measured (2026-09-23):** one Clock emit costs 0.69–0.77 ms of GUI
binding work with no value change. Soak Media summary: 1,207 timeline, 14 playback, 12 media_properties events in
≈92 minutes.

**Decision (operator 2026-09-23).**

- **Clock — Do with care**, as its own slice: split high-rate time/tick state from style/config state as a few
  semantic epochs, not one signal per property. `customEditableChildRoles` stays independent of the new signals
  (R-88); Edit/CUSTOM contracts unchanged.
- **Media — Watch:** after the Clock pattern exists, measure one real Media timeline/playback edge; split only if the
  binding saving is material.
- No repository-wide "one notify per property" refactor.

- [x] Clock split (`rendering/quick/widgets/clock.py`): `timeChanged` notifies `timeText`, `calendarText`,
      `timezoneText`, `showSeparator` (it also depends on the calendar text) and the three hand angles and fires on
      every snapshot change; `stateChanged` is now the config/style epoch and fires only when config or style changed
      (a config edge emits both). No QML change: bindings follow the properties' notify signals.
      Measured on a live bound Clock (`_publish_tick`, idle machine): **597–618 → 48–50 µs median** per tick, digital
      and analogue.
- [x] Bars (`tests/test_qtquick_clock_presentation.py`): per-property notify epochs pinned via the meta-object; a tick
      emits only `timeChanged` and an unchanged tick nothing; config/style edges emit both; `customEditableChildRoles`
      never rebuilds on a tick (R-88 guard with a positive control on mode switch). Clock, family-binder,
      custom-layout-owner, Edit/child-geometry and size-policy suites green per file.
- [ ] Physical: both faces tick correctly each second; live Settings edits; Clock CUSTOM Edit.

---

## PW-04 — `FeedRowsModel.replace_rows` resets the whole model when a row changes · P3 · R1 · Risk Low · Watch

`rendering/quick/widgets/feeds.py:399-406` returns early when the new row tuple equals the current one, so unchanged
refreshes do nothing. When even one row genuinely changes it calls `beginResetModel/endResetModel`, which retires every
delegate and re-requests every local artwork `Image` (`asynchronous: true`). Reddit/Gmail/Steam update in place
(`reddit.py:419-455`). The soak completed only 13 FEEDS IO tasks in ≈92 minutes, so this is not hot at current
cadence.

**Decision (operator 2026-09-23): Watch — not currently worth changing.** The structural issue exists, but no in-place
diff on principle. Trigger: FEEDS Custom 2–4 multiply live feed instances and retained image delegates; if
multi-source physical testing shows delegate/artwork churn on ordinary changed feeds, implement a stable-ID row diff
with `dataChanged` (bars: retained-delegate identity test; artwork not reloaded for unchanged rows).

---

## PW-05 — Hand-rolled parentless deadline timers; `single_shot` has no cancel handle · P2 · R1 · Risk Low · `[~]`

`widgets/feed_runtime.py:59-78` and `widgets/steam_followed_runtime.py:48-72` duplicate the same `_default_schedule`
creating parentless `QTimer`s outside the generation-owned single-shot registry that the destruction barrier observes
(`core/threading/manager.py:1302-1425`). They exist because `ThreadManager.single_shot()` returns `None`, although it
already owns generation fencing, a registry, `_srpss_cancel_single_shot` and payload release in
`_finish(execute=False)`. Both owners clear their handle when the deadline fires (`feed_runtime.py:540-554`,
`steam_followed_runtime.py:293`), so no double-delete race was found. Soak: OS timer handles held at ≈13–14 for
92 minutes, so this is ownership/durability work before Custom 2–4 multiplies the timers, not an observed leak.

**Decision (operator 2026-09-23): Do — return a cancellation handle, not a raw `QTimer`.** `single_shot` may be called
off the UI thread while its `QTimer` is created later on the UI thread, so no timer can be returned synchronously.

- A lightweight `SingleShotHandle` is constructed immediately; `cancel()` is idempotent.
- Cancel before the timer exists: timer creation is skipped (or the timer finishes immediately).
- The UI-thread timer creation binds itself to the handle; a later cancel routes through the existing
  registry/`_finish(execute=False)`, releasing callback payload and owner references exactly as today.
- Firing marks the handle completed.
- Generation-wide retirement stays authoritative; the handle is not a second timer registry or lifecycle authority.

- [x] `SingleShotHandle` (`core/threading/manager.py`): pending → scheduled → fired/cancelled under one lock. A
      pending cancel releases the payload and the later UI-thread creation skips; a scheduled cancel runs the timer's
      existing `_finish(execute=False)` (posted to the UI thread when cancelled elsewhere, and the timeout only
      executes if it claims the fire first); `_finish` settles the handle on retirement/owner death. Calls that cannot
      schedule return an already-cancelled handle. Both families' `_default_schedule` are now one-line adapters over
      `single_shot(...).cancel` (the System Stats idiom); their injectable seams are unchanged.
- [x] Bars: `tests/test_single_shot_handle.py` — cancel after creation, after fire (no-op), before creation from a
      worker thread, off-thread cancel racing the timeout, payload released without GC, generation retirement still
      cancels, Feed/Games-You-Follow deadlines registered (fails with the old parentless timers). Thread-manager,
      runtime-destruction, Feed, Steam, System Stats and Friend Pulse suites green per file.
- [ ] Physical: Feed and Games-You-Follow refresh on schedule; a Settings round-trip leaves no stray deadline.
