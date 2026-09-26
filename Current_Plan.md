# SRPSS | Current Plan

## Wallpaper feeds (image RSS) | rebuild on the shared feed core (ACTIVE)

Assessment 2026-09-24: of the 12 default feeds only NASA and Wallhaven ever yielded images (Bing's relative, HTML-escaped image URLs never downloaded; all 9 Flickr public feeds max out at 1024 px in every format and were downloaded then deleted each pass); the 30-image pool was 16–19 days old because a full cache skipped downloads and nothing rotated; per-site parser branches and domain tables; failures only recorded for Reddit feeds; unconditional feed re-downloads; no byte cap, public-address check or honest User-Agent on image downloads; a dead facade and a never-started worker process. It stays a separate product (wallpaper pool, rotation, save-to-disk) but acquires through the FEEDS core. Operator rules: fill mode is the yardstick; larger than the displays is good, smaller is not; crop is not judged in advance; no Wikimedia.

- [ ] **Physical check (next ordinary run with wallpaper feeds):** the session pass logs `[RSS_COORD] Pass:` then `+1 WxH` lines only at or above your displays' size; a stale pool retires a third after replacements land; nothing under the displays' size is shown. Built 2026-09-24: shared vetted image stream with header-size early rejection and one-time right-sizing of oversized images; feeds through `FeedSource` plus the generic JSON-listing adapter; rejected-URL memory; once-per-session rotation (replace, then retire; retired files deleted next session); defaults NASA IOTD, NASA JPL Photojournal, Wallhaven, Bing (Flickr removed). Existing feed lists are left to the user.

Landed 2026-09-25: the never-started RSS worker, `WorkerType.RSS` and the dead `workers.rss`/`workers.fft` switches are removed (migrated out of saved profiles and SST import); the Sources tab describes wallpaper feeds as they work; `Docs/Reference/Feeds.md` § Wallpaper feeds.

## FEEDS | Custom 1 closure and bounded family expansion (ACTIVE)

**Authority:** `Docs/Reference/Feeds.md` owns implemented architecture. `Docs/Future_Work/Feeds.md` owns the still-pending expansion/deferred work. Continue to audit **durability, content adaptability and performance neutrality** before multiplying sources or widget identities.

### Accepted current-tree evidence

- [x] `feeds_custom_1` uses the shared bounded RSS/Atom transport/parser/cache/source/runtime path, retained List/Grid/Compact QML, HTTP/S (and, since 2026-09-26, validated magnet) external actions, event-admitted local artwork and the ordinary shared Edit/CUSTOM owner.
- [x] The requested consolidated Windows regression gate is green on the current tree. Do not retain older focused pass counts as current acceptance evidence.
- [x] Physical Custom 1 artwork editing is accepted for free X/Y/width/height adjustment, with Grid text/content reflow following the changed artwork geometry rather than preserving a fixed landscape slot.
- [x] Physical source adaptability has exercised an image-sparse Hacker News feed plus image-bearing GitHub and Ars feeds. Image absence is a valid feed/content state, and tested story links reached the correct external destinations.
- [x] Product-wide clickable highlighting is physically accepted on the current tree: semantic colour is the resting/state language and an admitted active click target uses bright white where the shared contract calls for a border/separator/emphasized text cue. Text-dense row surfaces remain borderless where specified; Media retains its no-hover-border exception.
- [x] Website-address discovery is physically accepted (2026-09-24): `arstechnica.com` resolved to its feed in Custom 1. Standards-based, no per-site rules; `Docs/Reference/Feeds.md` § Feed discovery.
- [x] Custom 1 closure is physically accepted (2026-09-24): full Edit transaction (alignment flip, resize, child edits, Reset, Ctrl-Z, lock, Save, re-entry, fresh runtime), Show Feed Subtitle off/on with Save/reopen, last-good through an offline restart and reconnect, and disable/replace while work was in flight.
- [x] Modern feed formats are physically accepted (2026-09-24): Mastodon posts read as text titles, Daring Fireball's JSON Feed renders with dates and images, and Reddit resolves through the `.rss` suffix.
- [x] The secure Winlogon handoff remains the external-link authority: saver-side queue admission is the success boundary, helper wake is best-effort, and helper readiness never gates normal saver exit. Reddit/Reddit2, Gmail, FEEDS and Steam-family actions stay behind the same product-action/session boundary rather than calling direct browser APIs from retained runtime code.

### NEWS categories

- [~] **Awaiting physical check.** World, US, Politics, Gaming and Tech cards merge their selected publishers (CBS, ABC, BBC, NPR, Ars Technica, PC Gamer, Eurogamer; two or three per category) newest first on the shared path, with the publisher named on each row. Physical: `Docs/Future_Work/Feeds.md` § NEWS categories.

### Magnet links

- [~] **Awaiting physical check.** A validated BitTorrent magnet row opens in the registered torrent client (MC direct; saver through the Winlogon helper, which must be rebuilt first). Physical: `Docs/Future_Work/Feeds.md` § Torrent and magnet actions.

### Custom 2–4

- [~] **Awaiting physical check.** All four CUSTOM slots run through the Custom 1 path (generated descriptors, one adapter, one presentation, one Settings builder with per-slot controls and CUSTOM-lock scopes); same-initial names get a monogram ordinal. Physical: two slots with different feeds live together, then the same feed in two slots (fetched once, independent display settings); Settings save/reopen of every slot.

### Independent Games You Follow verification

- [ ] When a newly refreshed syndicated Steam article actually contains its validated original article URL, verify that exact article opens that destination. Older cached records without that URL correctly fall back to the app news hub. This check must not trigger a whole followed-set sweep and does not block FEEDS work.

## Voxel Sphere | isolated energy-floor controls

The independent fragment and particle minimum-energy settings are implemented with curated/default and user-authored preset protection. Focused pure-Python settings/preset gates were previously reported green. The remaining Sphere-specific operator gate is the native Windows settings/preset run and active-music observation of independent floor effects, Reset and Custom Save/reopen. Do not retune authored values on the operator's behalf; promote a reproduced defect here if one appears.

## Future Work transitions | correction and removal

`Docs/Future_Work/Transition_Expansion.md` owns the detailed work; `Docs/Reference/Transitions.md` owns current behavior and controls.

- [~] Crumble's separate crack-formation stage is implemented on real fracture borders before chunk/debris motion; retain solid depth and wall debris. Operator visual acceptance remains open.
- [~] Awaiting operator visual acceptance of Glass, Tiles, Ink and corrected Crumble at authored durations.
- [~] **Glass collisions / break-again options (operator 2026-09-23).** Implemented, off by default: shards can bounce off each other in flight and crack again (on collision, or ~30% at random without collisions), and a split piece can crack once more; solved once per run at build time. Glass and Melt are activated and pooled by default. Details: `Docs/Future_Work/Transition_Expansion.md`. Physical: turn each option on and judge the look in motion.
- [~] **Crumble control rework (operator 2026-09-23).** Each run now draws a different crack layout (seeded impact/cluster/warp patterns), crack complexity is live over its whole range (irregularity 0.34 → 1.00 across 0.5 → 2.0), and debris varies per run with the amount driving chip count and size. Details and measurements: `Docs/Future_Work/Transition_Expansion.md` §Control rework. Physical: visual acceptance at authored durations on both displays; judge whether the 1.8 default is now too broken.
- [ ] Observe both displays with active music and representative heavy external load; confirm Visualizer freshness and transition first-use behavior against the accepted baseline.
- [ ] Validate the installed/frozen build, material save/reopen/Reset and repeated switch/interrupt/retire.


## Runtime -> Settings replacement lifecycle

- [~] Restore the last Settings top-level tab plus its semantic subsection/builder on every runtime round-trip. Widgets, Visualizers, Display, Transitions and Themes persist semantic selection only; restored content is anchored at the top rather than replaying stale pixel scroll. Native round-trip validation remains open.

Transition terminalization, Visualizer owner retirement and shared Core Audio callback retirement are accepted current contracts guarded by source/tests and `Docs/Guardrails.md`; they are not active-plan tasks unless a concrete regression reopens them.

## Runtime audit 2026-09-22 | accepted 2026-09-23/24

`Docs/Future_Work/Runtime_Audit/` holds the register (00, including the accepted-items table with commits and closing evidence), item detail (01–05), structure and the considered-and-rejected list (06), historical-bug constraints (07) and the open-item evidence (08). The whole admitted queue (TX-01/02, LC-05/06, PR-01/03, PR-04 Stages A+B, PW-01/02/03-Clock/05, VZ-01/03/04/05) is accepted from the 2026-09-23 19:29–19:35 run, earlier physical runs and automated bars; the 19:29 trace also exposed and closed a TX-01 duplicate Glass geometry build.

- Watch: PW-04 Feed model reset (trigger: FEEDS Custom 2–4 or NEWS physical testing shows delegate/artwork churn; a NEWS card republishes once per publisher result). Parked: PR-02 (DC-04 stays documented), PR-01 resolve memo, PR-07, ST-01/02, VZ-05 epoch cache, VZ-07. Closed: LC-01, PR-05, PW-06, PW-03 Media, the prefetch double batch.

## Display wake freeze and overnight memory (2026-09-25 evidence)

Records: R-96 (wake freeze and reveal), R-97 (memory), R-98 (TLS). Landed 2026-09-25: one first-image owner per replacement, a hang window from construction to reveal, queued quit, bounded and per-display reveal ownership, no work-area rebuilds, texture-wrapper retention, MC identity without `SettingsManager`, and one verified TLS context. Linux tooling: `tools/memory_slope_report.py`, `tools/linux_xvfb_hotplug_churn.py`.

- [~] **Awaiting validation — Windows dual-monitor built check (R-96, R-98).** The operator procedure was given in chat on 2026-09-25. Pass requires all of:
  - repeated double wakes reveal every generation;
  - no `logs/hang_stacks.log` (if one appears, it is the evidence);
  - no `[DISPLAY][FALLBACK]`, and at most one first-image admission per rebuild;
  - `[STARTUP_REVEAL][FALLBACK]` only while a monitor is genuinely still waking;
  - tray exit and a Settings round-trip exit cleanly;
  - Gmail refreshes succeed with certificate verification (no `CERTIFICATE_VERIFY_FAILED`).
- [~] **Awaiting validation: Windows steady private-commit slope (R-97).** Root cause: SRPSS created ~30 threads/min (a new heartbeat `threading.Timer` every 3 s; Qt's private image pool recreated by every wallpaper), and the NVIDIA GL driver keeps ~70 KB per thread ever created. Both owners fixed 2026-09-26: one persistent heartbeat thread, and the Qt image pool keeps its ≤ 8 threads. The invisible full saver went from ~140 MB/h to +4 MB/h with 0 new app threads. Physical: one unattended overnight run with `--usage`; `tools/memory_slope_report.py` should show a flat warm plateau.

- [~] **Memory footprint reduction (operator 2026-09-25): R-99.** Four owners are fixed and measured on the real app:
  - a consumed derivative leaves the cache (49% of prefetch work had been wasted);
  - the parked transition node no longer pins the previous frame;
  - OpenBLAS runs one thread (≈700 MB of commit per process on 24 CPUs);
  - settings reads no longer create GC cycles.

  Awaiting the built check's Phase 3: `private_children_mb` ~816 → ≲ 200, main warm private roughly −700 MB, ~46 fewer threads.
  - [ ] The ImageWorker re-imports the whole app graph on `spawn` (~1,060 modules). A lean worker entry could save ~100 MB resident, but it must be validated under Nuitka multiprocessing first.

Side defects found while working (not yet fixed):

- [ ] **Watch (low priority, not visible): scaled prefetch holds the GIL on the background CPU lane.** `QImage.scaled` runs for up to ~70 ms per 4K derivative while holding the GIL. It is not a stutter: overnight on 2026-09-25 the Visualizer logical runtime skipped 125 of 1,812,107 steps (0.007%), and its worst paint gap rose only three times (43/60/62 ms) in 4.5 h. At the scene level, 10% of seconds had one frame over 25 ms (90 Hz), and only 18% of those overlapped prefetch scaling. R-99 already halved the scaling work (no more rebuilt derivatives). Measure on the next `--perf` run before acting: seconds with `dt_max_ms` > 25 in `[PERF_HUD]`, their overlap with `Scaled prefetch` lines in `screensaver_cache.log`, and `skipped_deadlines` in `[SPOTIFY_VIS][LOGICAL] Runtime stopped`. Only if overlap remains material, move the scaling off the GIL with identical output.
- [ ] **Gmail refresh adds ~1.5 main-process handles per refresh.** The +18–25 handles/h slope tracks the Gmail cadence. Classify the type with `--handle-attribution`, then fix at the owner.
- [ ] **PyOpenGL/ctypes array types accumulate** (~20 new types over 140 rotations on the Linux soak). Find the per-call `(ctype * n)` construction and hoist it. Low priority.

## Known failing tests and anomalies (tracked until resolved)

Pre-existing reds and runtime anomalies found while gating the runtime audit. Each stays here until fixed or explicitly retired; do not treat them as noise in a gate.

- [ ] **A runtime-barrier timeout poisons every later Qt event loop in the test process (pre-existing, found 2026-09-25).**
  - On Linux full-suite runs, `test_s_hotkey_workflow.py::test_s_hotkey_opens_settings_without_crash` never completes its destruction barrier, because a `QuickDisplayUnit`/`QuickDisplayPresenter` Python owner is retained. It fails the same way on base.
  - The barrier timeout (8,000 ms) equals the test's `waitUntil` (8,000 ms). When the timeout wins, the non-terminal timeout path's `QCoreApplication.exit(1)` sets Qt's per-thread `quitNow`. From then on every nested `QEventLoop.exec()` (`qtbot.wait`/`waitUntil`) returns immediately, and later event-loop tests fail in cascade: `test_s_hotkey_workflow`, `test_settings_dialog`, `test_single_shot_handle`, `test_startup_reveal_stalled_display`, `test_steam_phase3_settings_descriptors`.
  - Done 2026-09-26: the cascade can no longer happen silently. A conftest tripwire records any real `QCoreApplication.exit()` and ends the session right after that test, naming it (return code 3; `tests/test_qt_exit_tripwire.py`).
  - Still open: find the retained owner in the Linux full-suite context. It does not reproduce on Windows (the file passes in isolation). On the next Linux full run, the barrier's `[LIFECYCLE_BARRIER] timeout` and `[PYTHON_OWNER_REFS_SUMMARY]` lines for the named test are the evidence.

- [ ] **Spectrum extreme-viewport smoothness (pre-existing, not an audit regression).** The 2026-09-23 16:53–17:06 acceptance run saw significantly reduced visual smoothness for Spectrum at extreme viewport shapes. Pre-dates the audit; do not reopen VZ-04 over it. Watch item until investigated separately.
- Evidence runs: 2026-09-22 22:53–22:59 — no native fault; the replacement-construction watchdog armed 13× and never fired. 2026-09-23 D1 soak 09:07–10:40 — no native fault, no QML message, watchdog armed 6× and never fired; one `viz_geometry_mismatches` increment at 10:38:32, which is the fail-closed stale-presentation guard working, not a defect. 2026-09-23 16:53–17:06 acceptance run (two processes, each with a Settings round-trip) — no native fault, replacement watchdog never fired. Note: starting a new `--frame-trace` session replaces the previous session's trace segments; copy them first when a trace must survive a restart.

## Handoff and regression rules

When an accepted behavior changes, select only the relevant targeted tests and physical observations; do not re-accept unrelated OSD, Media or widget systems. Keep full superseding GODZIPs with the canonical three `.godzip/` files, manifest-backed replace/delete instructions and no temporary scripts or compiled artifacts. Test commands belong in chat, not an added documentation file.
