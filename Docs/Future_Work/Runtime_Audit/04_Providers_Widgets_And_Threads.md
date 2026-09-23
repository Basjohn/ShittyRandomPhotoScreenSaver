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

