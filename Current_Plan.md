# Current Plan — Active Work

Last updated: 2026-09-15

Outside of Codex Work Began: `886e6fa419ff130ff2a9aedf5091ae6162d1e958`

The Qt Quick migration is closed and operator-accepted. This file contains **active work only**; completed migration,
Sphere polish, widget resize/Edit lifetime, bucket normalization and other accepted closeout items are intentionally absent.

---

## 1. Steam Friend Pulse — public implementation complete, awaiting live/installed acceptance

Execution authority: `Docs/Future_Work/Steam_Friend_Pulse.md`.

The retained implementation is complete through F6. It is a full friend-roster card with a default dynamically centred
**Avatar Grid** and selectable compact **Activity Rows** view. Online friends lead the model and offline friends fill the
remaining configured viewport; every accepted friend remains scroll-reachable. Both views use one stable virtualized
presentation model and fixed capacity-owned geometry, so roster size never owns card height and privacy changes do not
create a second source/model.

- [x] Pin pre-feature HEAD `e0314691` and preserve the maintained Steam request/cache/privacy fixtures.
- [x] Add immutable normalized Friend Pulse source/cache state. Validated Steam IDs may remain in the user's
  account-private cache and owner-only runtime action map; presentation snapshots/QML roles/logs receive no ID or full
  action URL and QML emits only a current row index.
- [x] Add cache-first FriendList + bounded PlayerSummaries preparation through existing Steam locks, request
  coordination, backoff and redaction. The only cadence setting remains canonical `widgets.steam.refresh_minutes`.
- [x] Add one runtime-generation shared source/avatar owner with per-display leases. Steam family activation,
  `widgets.steam.enabled`, member enable and a real presentation consumer all precede work; last release
  stops cadence, clears comparison/avatar state and fences source/avatar completions.
- [x] Add Strict/Balanced/Rich projection, online-first/offline-fill roster ordering, honest private/connect/empty/stale/
  failure states, per-friend presence/game details, Rich-only current-viewport local-avatar hydration, and no Strict
  identity leak.
- [x] Add retained virtualized Quick Grid/Rows presentation, dynamically spaced and centred avatar tiles, incomplete-row
  centring, optional centred names with bounded font size, branded/theme roles, finite theme-colored change glow,
  `ordinary_uniform`, global CUSTOM/40% floor, ordinary stacking/auto-fit, lazy transactional Settings and
  generated-default authority.
- [x] Add generation-fenced semantic clicks and one retained Gmail-style three-dot popup per card. Direct avatar actions
  request Steam chat with public-profile fallback; menu actions offer Profile, Chat, Copy Steam ID and Store when
  a current AppID exists. Friend game labels and Achievement/Abandonment artwork open the Store. MC/diagnostic tries the
  Steam client; normal screensaver routes HTTPS through the existing secure helper and exits once after accepted handoff.
  Join Game is deliberately absent because the admitted summaries prove only an AppID, not a joinable lobby/server token.
- [x] Focused source/runtime/privacy/cache/request/Settings/QML/binder/cardinality/normalization/action tests are GREEN;
  the real threaded-OpenGL DPR 1.5 roster/menu/Strict/Rows/40% capture is warning-free and proves the finite event glow.
- [x] Remove Friend Pulse's temporary product gate across Steam Settings, runtime/preview descriptors and retained
  binder admission. It is now always visible inside the Steam family; `--devsteam` owns only unfinished Games You Follow.
- [x] **Implemented recovery/polish (2026-09-13, e31 authority; awaiting validation):** land Friend Pulse ALL-CAPS status/game chrome, offline-avatar desaturation, hard avatar clipping, remove the redundant lower-right presence circle (and update presentation-test expectations), strengthen family-local linework, keep Title Case/bold/two-line name fitting, and add a real hover-only multi-pin/favourite affordance with account-private persistence.
- [x] **Implemented Restore Size (awaiting validation):** add an edit-mode bottom-left `↶` glyph styled like Close. Restore only the selected widget's authored non-CUSTOM size/shape while preserving current X/Y + display and staying in CUSTOM. Do not call `restore_baseline`, stacking, ordinary auto-fit, or ordinary shrink. Uniform reduction is allowed only when authored size itself physically exceeds the owning display.
- [x] **Unread-message experiment removed (2026-09-13 operator decision):** remove the experimental FriendMessages source IDs/endpoints/parser/cache/runtime request path, unread avatar hydration, message model/menu/glow, tests and backoff traffic. Do **not** add QR auth, a second Steam login/session or any credential expansion. Existing Friend Pulse friend-chat/profile actions remain unchanged.
- [x] **Friend Pulse wide-grid reflow:** remove the old 900 px CUSTOM width clamp and six-column ceiling. The 2026-09-13 installed log/visual check exposed one remaining accidental ceiling: `visible_row_capacity` still capped CUSTOM horizontal columns, so a baseline capacity of 4 could never expand beyond four columns. Authored/non-CUSTOM layout still respects the configured visible capacity, but once a CUSTOM horizontal `content_extent` exists the logical width owns the readable column count up to the project-wide 24-friend ceiling. Vertical capacity/scroll behavior remains intact.
- [x] **Friend Pulse dropped-message hotfix (2026-09-13):** after removing the unread-message experiment, one stale `_rebuild_message_rows()` call remained in `FriendPulsePresentationModel.on_friend_pulse_runtime_snapshot()` and raised on delivered roster snapshots. Remove that dead call/branch; source regression coverage now forbids `_rebuild_message_rows` / `message_rows_changed` from returning.
- [?] **Friend Pulse hotfix installed validation:** run a normal Friend Pulse refresh/lease delivery and confirm no UI-invoker `AttributeError`, roster/state updates continue, and the dropped unread-message path produces no source/backoff work.
- [x] **Optional online-count summary:** add canonical `widgets.friend_pulse.show_online_count = true`, expose a themed Settings checkbox, and project the already-owned Steam snapshot count as ALL-CAPS `X FRIEND(S) ONLINE` in the top-right summary area. This adds no source work/cadence and is blank until a ready/stale roster exists.
- [x] **Focused non-Qt recovery gates:** Friend Pulse visual/pin/Restore Size + dropped-message absence + wide-grid/online-count source contracts pass directly in the PySide-less environment; Steam backend core checks also pass. PySide runtime/QML execution remains a separate installed gate.
- [?] **Recovery/Restore Qt test execution:** run the Friend Pulse runtime/QML and CUSTOM session/overlay/owner tests in the project PySide6 environment. Confirm hover-only pins, removed status circles, offline desaturation/clipping, ALL-CAPS status/game chrome, `X FRIEND(S) ONLINE`, wide-grid expansion beyond four/six columns, `↶` Restore Size routing and exact X/Y/display preservation. Specifically side-resize Friend Pulse/System Stats, then Restore Size and prove the target is the canonical authored size rather than the just-committed CUSTOM `content_extent`.
- [x] **Restore Size authored-geometry authority repaired after 2026-09-13 log:** the log proved routing beyond Friend Pulse/Visualizer (Friend Pulse, System Stats, Weather, Media and Visualizer all received Restore Size with exact X/Y preserved and `emergency_fit=1.0000`), but it also exposed that `DisplayPresenter._base_geometries` could be overwritten by an effective committed CUSTOM rectangle/content extent. Geometry binding now publishes a separate committed-rect-free authored projection, and the presenter admits the canonical pre-CUSTOM preferred geometry once then freezes authored-cache updates while CUSTOM/edit owns layout. CUSTOM `content_extent` churn therefore cannot redefine the Restore Size target. Restore still clears `content_extent`, preserves display/X/Y, stays in CUSTOM, performs no stacking/ordinary auto-fit/shrink, and only emergency-fits when the authored rectangle itself exceeds the display.
- [?] **Awaiting Validation:** use a real connected Steam account to inspect long names/game names, Rich avatar-cache
  hydration, Strict/Balanced reprojection, private/unavailable/stale wording, manual refresh behavior, friend chat/profile
  routing, game Store routing, rounded avatar/tile borders, hover-only multi-pin behavior, finite friend-change glow,
  wide-grid expansion, and the optional top-right online-count summary against real themes.
- [?] **Awaiting Validation:** installed two-display/DPI/theme/CUSTOM/stacking soak must confirm one shared source owner,
  no refresh multiplication and clean last-card/family-deactivation retirement.

---

## 2. System Stats — public CPU/Memory/Uptime/Network implementation complete, awaiting installed soak

Execution authority: `Docs/Future_Work/System_Stats_Widget.md`.

The dedicated product source remains isolated from diagnostic `--usage`. The family is normally visible/activated while
the member remains disabled by default, so no sampler exists until the user enables System Stats and a retained card
consumer is admitted.

- [x] Preserve the admitted whole-system CPU/RAM source and extend that **same** sample pulse with system uptime plus
  aggregate network receive/transmit counters. Uptime captures boot time once and derives elapsed time on the existing
  pulse; Network derives rates from cumulative OS counters and therefore needs the same two-observation cadence as CPU.
  No process/core enumeration, network request, driver, second sampler or second timer was added.
- [x] Keep exactly one low-priority sampler owner per runtime generation. Display leases share one immutable snapshot;
  sampling is fixed-delay from completion, one-in-flight, generation fenced, and final lease release closes/clears source
  ownership with no recurring work left alive.
- [x] Promote the former hard-coded 10-second interval into canonical `widgets.system_stats.sample_interval_seconds`.
  Settings exposes one **Sample Interval** control with a hard 10-second minimum/default and slower values allowed up to
  one hour. It reuses the existing owner rather than introducing another cadence.
- [x] Expand the retained card from two to four fixed metrics: CPU LOAD, MEMORY, UPTIME and NETWORK ↓/↑. Fixed-capacity
  geometry remains value-independent; canonical capacity is 4 and preferred/authored height is 430 px. Uptime/Network
  do not invent meaningless percentage tracks.
- [x] Remove implementation/rejection commentary from the user interface. Settings no longer exposes implementation/rejection commentary, and the card no longer carries architecture/cadence filler.
- [x] Preserve canonical family/default/descriptor ownership, lazy Settings construction, generated JSON/SST defaults,
  ordinary stacking/global-CUSTOM/40% contracts and the existing packaged header asset/theme semantics.
- [x] **System Stats Settings/pill polish (2026-09-13):** Widgets-page section pills now reserve the real label width plus authored padding, fixing `System Stats` clipping at the shared descriptor button factory rather than with a one-off width. Add canonical CPU / Memory / Uptime / Network toggles under a lazy Metrics bucket; all four default on. Disabled metrics are skipped inside the existing shared source pulse (CPU/RAM/uptime/network reads are not performed for hidden metrics), while the single shared owner/cadence remains unchanged—selection creates no alternate timer/source owner.
- [x] **System Stats two-axis CUSTOM content extent:** opt System Stats into the existing shared `content_extent_axes=(horizontal, vertical)` contract. Side-resize reflows instead of uniformly scaling: extra horizontal room widens detail/value lanes; extra vertical room redistributes enabled metric panels and spacing/padding. The CUSTOM payload is presentation-only and never mutates real widget settings. Corners/wheel keep the ordinary uniform path and Restore Size clears back to authored geometry through the existing authority.
- [x] **System Stats metric-section border balance (2026-09-13):** increase only the per-metric section outline from the shared 1.0 px baseline to `scaleAwareStrokeWidth(1.25)`. The 5 px accent block on the left stays unchanged; this is a +0.25 px family-local balance tweak, not a new border/theme authority.
- [x] Canonical default artifacts regenerated from `default_settings.py`; generated JSON + both SST files pass regeneration check, and the broader defaults-authority audit is GREEN. The audit also removed three pre-existing Friend Pulse runtime literal defaults in favour of canonical default-contract reads without changing behaviour.
- [?] **System Stats installed/PySide validation:** confirm the wider `System Stats` pill no longer clips, all four metric toggles round-trip, hidden metrics immediately disappear and their disabled OS reads stay skipped without sampler multiplication, the +0.25 px metric-section outline visually merges better with the 5 px accent block without looking heavy, horizontal/vertical side handles reflow cleanly at small/large extents, and Restore Size returns the canonical non-CUSTOM authored family rectangle when no emergency display fit is required.
- [x] **Generic Widgets Settings family-retirement hotfix (2026-09-13 log):** deactivating System Stats correctly destroyed its lazy Settings section, but a delayed coalesced Widgets-tab save retained the section's CUSTOM-resize notice `QLabel` and called `setVisible()` after Qt had deleted the C++ object. Repair the shared retirement seam for every retireable family: invalidate any pending pre-retirement save token, drop family-owned notice side references before `deleteLater()`, clear both built/building ownership, reject invalid Shiboken wrappers during lock-state refresh, and let the post-retirement activation save arm a fresh token. This is not a System Stats exception.
- [x] **Retirement regression coverage:** pure source/lifetime contracts pass **2/2** and a PySide parameterized retire → delete processing → save → rebuild test now covers every CUSTOM-resize-lock family section (Clocks, Weather, Media, Reddit, Gmail, Steam, System Stats).
- [?] **All-widget load/unload installed validation:** repeatedly deactivate/reactivate every widget family, including while a coalesced Settings save is pending, and confirm no `Internal C++ object ... already deleted`, no stale-control mutation, no rejected UI callback, clean lazy rebuild, and unchanged persisted per-family configuration.

- [?] **Awaiting Validation:** installed minimum-interval off-vs-on Visualizer contention run must confirm no meaningful
  freshness/reactivity or event-loop/presentation-tail regression with CPU/Memory/Uptime/Network enabled.
- [?] **Awaiting Validation:** repeated enable/disable, interval changes, runtime recreation and two-display soak must
  confirm one shared owner, no refresh multiplication and clean final retirement.

---

## 4. Steam Games You Follow — dev-gated feasibility-first future slice

Execution authority: `Docs/Future_Work/Steam_Games_You_Follow.md`.

This replaces the unfinished Steam Progress / Steam Journey scaffold while retaining `steam_progress` as its
compatibility id. It is a bounded retained card for news from explicitly followed games, not a personalised Steam or
whole-library news feed. It stays behind `--devsteam` until its source/follow-list and source-article URL boundaries
are proven.

- [ ] Complete G0 before implementation: prove the follow-set authority (or obtain explicit approval for a local
  validated-AppID list), APP_NEWS field/response budget, and safe source-article URL/helper policy. Do not infer
  follows from ownership/recent play or add a fallback source.
- [ ] Then implement only through the documented G1-G5 sequence: feature-owned cache/model, one shared
  generation owner, retained Quick rows, canonical Settings/default migration and ordinary/CUSTOM acceptance. The
  first retained implementation must already consume shared horizontal + vertical `content_extent`; side handles reflow
  at constant uniform scale, corners/wheel remain whole-card uniform, both row variants have authored preferred geometry,
  Restore Size/slot replay/cross-display DPR transfer use the shared geometry owner, and no family-local resize system is
  permitted.

---

## 4A. Settings slider commit / crash hardening — additional active work

This is additive and must not displace the Friend Pulse/Restore Size acceptance work above. A 2026-09-13
older-checkpoint crash log ends during an extreme Accessibility slider save storm: each slider increment re-saved all four
Accessibility values and published four `settings.changed` events. `SettingsManager.set()` correctly treats every semantic
mutation as a persistence revision, so slider drag batching belongs at the shared UI-control/connection seam, not inside
SettingsManager and not behind a new polling/debounce owner.

- [x] **Diagnosed:** Accessibility slider drag currently calls `_save_settings()` on every `valueChanged`, re-emitting
  `dimming.enabled`, `dimming.opacity`, `pixel_shift.enabled`, and `pixel_shift.rate` for every increment. The supplied
  log terminates mid-storm at 17:51:19. This is strong correlation with the crash but not proof of native crash cause;
  `native_faults.log` contains no captured fault record.
- [x] Add one shared `NoWheelSlider` commit signal: live `valueChanged` remains available for labels/previews, while
  persistence-capable tabs bind save work to the release/commit boundary. Keyboard/programmatic discrete changes remain
  discrete commits; no timer/poller is introduced.
- [x] Migrate immediate-persistence slider paths (Accessibility, Display glow sliders, Sources ratio, Transitions sliders)
  to release-time commit and add focused tests. Accessibility additionally persists only the setting that actually changed,
  reducing the reproduced 46-save/186-event storm to one semantic mutation per committed slider interaction. Preserve
  existing Widgets/Visualizer coalescing authority; audit those slider bindings for redundant callback churn without
  layering a second debounce/persistence owner. Pure source/SSOT contract checks pass 3/3 in the PySide-less environment.
- [?] Installed Settings validation: drag each affected slider aggressively, confirm labels/previews remain live while
  persistence/settings events occur once per drag commit, then repeat the crash reproduction and inspect writer/event logs.

## 4B. Friend Pulse directional-shadow audit + dynamic artwork crossfade polish

- [x] **Audit started:** Friend Pulse already gives the BrandedHeader a directional card shadow and text uses the shared
  text-shadow roles. Row/grid tile surfaces, avatar frames, pin/menu controls, separators and the empty-state icon do not
  currently own equivalent directional surface shadows.
- [x] **Shadow prescription:** add, if visual validation agrees, subtle same-direction shadows to row/grid tile surfaces.
  Avatar frames should not use a filled rectangular shadow: shadow the border-ring alpha itself (or an equivalent
  outline-only source) so the empty/transparent interior stays empty, using the existing global card shadow direction/color
  with lower alpha/blur. The empty-state icon may take a very light same-direction shadow. Leave thin separators, pin
  glyphs/buttons and three-dot affordances unshadowed by default; they are too small and become muddy fast. Do not invent a
  Friend Pulse-only direction authority.
- [x] Improve dynamic Media/Steam artwork changes through the shared event-driven `ArtworkFadeImage` SSOT. Keep the current
  readiness-gated two-buffer/no-flash contract and frame-demand ownership; make replacement transitions gentler for every
  existing Media/Achievement/Abandonment artwork consumer without per-widget timers or duplicate transition machinery.
  Shared replacement fade is now 520 ms with `InOutSine`; empty-source fade is 280 ms. The Abandonment-local 340 ms override
  was removed so the shared primitive is authoritative. Pure artwork/slider contract checks pass 9/9 combined.
- [?] Visual validation across Media + Steam artwork surfaces: rapid source churn, missing->ready, ready->missing, same-source
  withdrawal, DPR/theme changes, and no retained second texture after transition idle.

---


## 4C. 2026-09-14 overnight soak — performance/lifetime findings

Authority/evidence: the 03:34–13:54 diagnostic soak with `--usage`/cache/perf sidecars and the 2026-09-14 source trace. The
run began on two displays; Windows removed the MSI panel from the logical topology at ~03:53 while displays were off, so
most of the overnight interval is a one-logical-display process/service soak. The 13:46 wake sequence is still valuable
monitor-loss/reconstitution evidence. Diagnose first, tests second, production fixes only after the tests encode the real
ownership/lifetime invariant. Do not add instrumentation unless end-to-end tracing remains below ~80% confidence; any new
high-volume diagnostic belongs in a dedicated sidecar rather than already-busy `--perf`.

- [x] **Scaled-prefetch queue root cause proven (>95% confidence).** `ImagePrefetcher.register_scaled_requests()` may admit a
  derivative while its raw parent is resident or owns an active/pending producer. `_submit_load()` then treats a returning
  `ImageCache.put(raw)` call as proof of residency even though the hard 256 MiB LRU is allowed to evict the inserted raw
  immediately; `_pump_scaled_prefetch()` dispatches only resident parents and has no orphan-reclamation path once the parent
  has neither residency nor a producer. The stranded derivative therefore keeps both `_pending_scaled_keys` and logical-byte
  budget forever. Soak proof: all 11 scaled-prefetch completions occurred by 03:37:01; the dead queue then stabilized at
  exactly **125,337,600 bytes** = `2×3840×2160×4 + 4×2560×1440×4`, **93.4%** of the 128 MiB pending-byte cap, while later
  registrations were repeatedly rejected. At shutdown: **4,675** scaled-prefetch intents, **11** scaled completions,
  **2,600** completed raw-prefetch IO tasks, only **9** scaled cache hits vs **962** scaled misses. The bounds prevented a
  memory leak but the pipeline spent most of ~10 h decoding speculative raw inputs with almost no derivative payoff.
- [x] **Prefetch regression authored before fix (2026-09-14; PySide run still required):** `test_image_prefetcher.py` now
  models the exact hard-cache case where raw `put()` succeeds but the inserted parent is immediately nonresident. Coverage
  requires orphan key+byte reclamation, immediate budget reuse by newer valid work, six repeated self-eviction cycles with
  zero pending drift, and the inverse invariant that a derivative remains owned while its raw parent is still queued/inflight.
  These are owner/lifetime regressions rather than stale list-shape assertions. `test_image_pipeline` remains separately
  classified for broader current-owner fixture reconciliation; do not make its old internal shape the new contract.
- [x] **Prefetch production repair landed after regression gate (2026-09-14):** raw completion now verifies actual
  post-`put()` cache residency; a bounded ownership sweep releases pending derivatives that are stale/already satisfied or
  whose raw parent has neither residency nor queued/inflight producer ownership. Cleanup runs before admission and before
  scaled dispatch, including during the post-transition compute cooldown, and raw-submit failure also triggers cleanup. The
  inverse producer-owned case is retained. No cache/backlog/concurrency/render/Visualizer limit changed. On the soak state this
  would release **125,337,600 bytes / 119.53 MiB** of dead logical budget, increasing usable admission headroom from
  **8.47 MiB to 128 MiB** (default queue: up to eight 2560×1440 derivatives by count, or four 3840×2160 by byte cap).
  Runtime cost is an O(pending) ownership scan over the already-bounded derivative queue (normally <=8 at concurrency 2),
  only cheap cache-membership/set checks; no image processing or new task/timer is introduced. Isolated A/B state-machine
  smoke against the tests-only checkpoint proves old=`1 pending / 16 MiB charged`, repaired=`0 / 0` for self-eviction.
- [x] **R-82 installed soak closure (2026-09-14, 58 min): PASS.** Under sustained scaled-cache churn the repaired
  pipeline stayed live: **93 scaled-prefetch requests / 91 completions**, **85 scaled evictions / 2.642 GiB evicted**,
  **45/45 deferred resume schedules/runs**, and **91** raw-prefetch sources released after their final derivative. Final
  cache state was bounded at **6 scaled items / 189.8 MiB** with **45 scaled hits / 0 misses / 0 worker requests**. The old
  stranded-derivative signature did not recur; admission recovered after bounded pressure rather than pinning near 128 MiB.
  Treat R-82 as closed unless a future regression reproduces orphaned pending bytes or scaled-prefetch death under eviction.

- [x] **Reddit zero-delay due-loop root cause proven (>95% confidence).** The blocked-cooldown path converts a positive
  floating remainder with `int(... * 1000)`. A positive sub-millisecond remainder becomes `0`; `_schedule_timer()` handles
  `delay <= 0` by synchronously calling `_on_periodic_due()`, which re-enters `fetch()`, sees the cooldown still positive,
  re-authors another zero delay and recursively repeats until wall time advances. The soak contains **854** due-arm records,
  **763** blocked-cooldown arms and **721 zero-delay blocked-cooldown arms** across 27 second-buckets; worst observed burst is
  **84 synchronous arms in one second**. Network rate limiting still prevented Reddit request multiplication, so the cost is
  avoidable UI-thread/log churn and recursion risk rather than remote hammering.
- [x] **Reddit regression authored before fix (2026-09-14; PySide run still required):** drive a controlled positive
  `0.4 ms` blocked cooldown through the real `fetch()` -> due-authoring -> timer seam and require exactly one deferred
  `>=1 ms` one-shot with no synchronous `_on_periodic_due()` entry. A second regression pins preserved positive sub-ms
  monotonic deadlines so they cannot truncate to zero before they are actually due.
- [x] **Reddit production repair landed after regression gate (2026-09-14):** all positive second remainders now preserve
  a positive integer delay via ceiling/minimum-one-ms conversion, including preserved monotonic dues and blocked fetches;
  `_schedule_timer()` always routes even a due-now edge through the existing one-shot instead of synchronously re-entering
  `_on_periodic_due()`. No timer/poller/cadence owner was added. Against the soak this removes the **721** observed zero-delay
  blocked-cooldown arms (worst 84/s recursive burst) and replaces each boundary with one deferred edge; the only timing cost
  is roughly 1–2 ms at an otherwise due-now boundary, negligible beside the 15-minute Reddit cadence. Isolated A/B smoke
  proves old=`1 synchronous due / 0 shots`, repaired=`0 synchronous / 1 positive shot`.
- [x] **R-83 installed soak closure (2026-09-14, 58 min): PASS.** The run contained two blocked-cooldown
  boundaries whose formatted remaining delay reached `0.0`, but neither produced the old synchronous re-arm storm. Each
  boundary advanced into one legitimate due fetch/fallback chain and then authored the normal ~900 s next edge. No same-second
  recursive burst or request multiplication returned; cooldown-gated manual refresh remained rejected normally. Treat R-83 as
  closed unless zero-delay recursive scheduling reappears.

- [?] **R-84 narrowed by handle-class attribution — stable runtime is flat; one replacement-generation baseline step remains.**
  The 2026-09-14 follow-up soak ran ~56.5 minutes with **226/226 `--usage` samples** and 57 independent
  `screensaver_handles.log` snapshots. During the long settled generation-0 interval (~18:13–18:40), the five-sample
  `handles_main` median moved only about **1812 -> 1814** and the persistent object classes were effectively flat
  (`type_56` ~236/237, `Key` 66, `Section` 390, `File` 419, `Semaphore` roughly 259–263). The old straight-line
  “+handles/hour” interpretation therefore did **not** reproduce as a continuous steady-generation leak. At the explicit
  Settings runtime replacement (~18:42), however, the settled generation-1 baseline stepped upward by a persistent bundle
  of approximately **type_56 +10, Semaphore +10, Key +6, Section +3, File +2**. Later ordinary mode/transition activity did
  not staircase those classes again. Remaining question: is that one-time native/lazy generation-1 initialization or does
  **each full runtime replacement** retain another bundle?
- [x] **R-84 attribution sidecar validated:** the out-of-process 60 s handle classifier ran for the whole soak, its PID stayed
  excluded from app aggregates, and its object-type history was sufficient to reject the continuous-leak hypothesis above.
  Do not add another handle probe or broaden cadence. If the final churn test staircases, investigate the already-identified
  generation retirement/constructor owners directly; if it plateaus after the first replacement, close R-84.
- [x] **`--usage` Toolhelp observer-effect repair validated (2026-09-14):** after startup, the two-minute topology refresh fell
  from the previous ~80–144 ms psutil/GIL-heavy samples to roughly **26–59 ms** (median ~47 ms) using `topology_source=toolhelp`,
  with zero skipped 15 s samples. The previous regular two-minute visualizer/frame hitch signature disappeared; refresh-period
  frame/event-loop tails are now broadly comparable with ordinary samples. Keep the psutil fallback only for Toolhelp failure/
  non-Windows continuity; do not restore the GIL-held Windows recursive `children()` + per-process `num_threads()` owner.
- [x] **Handle attribution is explicit again.** The smooth control used `--usage` without the later handle-enumeration child. `--usage` therefore starts only the low-cadence usage sampler; `--handle-attribution` explicitly admits the Windows sidecar and implies `--usage`. Diagnostic-all does not admit it. This prevents deep observer work from silently changing process topology.

- [x] **Settings 300–500 ms stalls classified by code ownership, not handwaved:** `on_settings_requested()` first performs the
  explicit full `engine.stop(exit_app=False, reason="settings")` and runtime destruction barrier; the ~335 ms Settings-dialog
  construction and later replacement `_initialize_display()`/`start()` occur while there is **no live display runtime**. The
  same full-replacement path is intentionally used only for Settings, committed CUSTOM edit reload, monitor-topology replacement,
  startup and teardown. Ordinary Visualizer mode/preset changes use the retained owner and do **not** rebuild DisplayManager.
  Therefore those several-hundred-ms stalls are admissible lifecycle/reconfiguration cost under the current policy. **Any
  comparable stall observed outside those explicit boundaries is a first-class performance bug and must not be excused as
  lifecycle noise.**
- [?] **Normal-runtime image-rotation GUI hitch — owner found and repair authored; Windows proof required.** The soak repeatedly
  shows ordinary 3840x2160 rotations spending roughly **28–53 ms** in UI-thread `present_processed_image`, often matching the
  50–72 ms event-loop tail in the same 15 s period. Code trace found a redundant Quick cutover seam: the compute task already
  owns the processed `QImage`, but the UI callback converts it to `QPixmap`, then `QuickDisplayUnit.capture_image()` converts
  it back to `QImage`, RGBA8888 and a ~33 MB Python `bytes` snapshot. Repair now captures the immutable `PresentationImage`
  directly from the processed `QImage` **inside the existing compute task** and publishes that detached value through a new
  DisplayManager contract. Startup/legacy QPixmap seeding remains intact. Same-transform multi-monitor reuse still shares one
  immutable detached value; current/previous-image paths both use the detached seam. Required Windows proof: normal rotations
  must show no `qimage_to_qpixmap` UI stage and `present_detached_image` must collapse toward low-single-digit UI time without
  changing image pixels/DPR/identity, transition source/destination truth, history/accounting, stale-generation rejection or
  scaled-cache behavior.
  **Known remaining copy boundary:** `PresentationImage` still owns a tightly packed Python `bytes` RGBA payload. Moving its
  capture into the compute task removes the proven GUI-thread QPixmap/QImage bounce, but the ~33 MiB bytes materialization
  can still briefly hold the GIL. Do not declare the whole image path solved merely because UI publication becomes cheap.
  The same FINAL churn/acceptance run must verify ordinary image changes no longer create meaningful Python/Visualizer cadence
  spikes. If a residual image-change spike survives while `present_detached_image` is cheap, the next repair is a **Qt-native
  detached image/buffer presentation contract through render-thread texture upload**, not another probe and not retuning the
  Visualizer.
- [?] **Normal-runtime Context Menu hitch — retained-model invalidation owner found and repair authored; Windows proof required.**
  Repeated 75–94 ms event-loop periods align with ordinary context-menu open/hide. The Python `open_at()` path itself is tiny;
  the architectural bug was that `entries`, `menuVisible`, `anchorX` and `anchorY` all used the same `stateChanged` notify.
  Every open/hide therefore notified the QML `Repeater` that `entries` changed, and the getter returns a fresh list-of-dicts,
  allowing the retained menu/submenus to be rebuilt even when only visibility/anchor changed. Notifications are now split into
  `entriesChanged`, `anchorChanged` and `visibilityChanged`; entry delegates invalidate only when the actual immutable entry set
  changes. Keep the aggregate `stateChanged` signal only as non-QML compatibility telemetry. Required Windows proof: repeated
  right-click/open/dismiss should no longer create 50+ ms event-loop tails; menu admission, click-outside swallow, submenu hover
  grace, single-owner policy and theme/shadow appearance must remain identical.
- [x] **R-87 — Qt Quick high-refresh freshness/scheduler regression is COMPLETELY FUCKED / OPEN until installed proof.** The durable incident record is `Docs/Historical_Bugs/R-87_QtQuick_HighRefresh_Freshness_And_Scheduler_Regression.md`; it embeds the critical readings so future work does not depend on log archives surviving. Smooth-control D0 Bubble was ~164.6 FPS / 0% median skip / ~10.1 ms drawn-state age at ~90 logical revisions/s; SettingsLifetime shifted to ~155.7 / ~3% / ~17.8 ms with the producer and pacer/render bridge materially unchanged. The long supervisor soak proves the current architecture can still reach ~166 FPS / ~9–10 ms age when Windows is quiet but collapses under UE5-class pressure to ~121 FPS / ~19% skip / ~22 ms age. The one-process shared-COMPUTE A/B recovered comparable-pressure D0 to ~134 FPS and cut app threads from ~113 to ~97, but did not close freshness. D1 is decisive against a naive 90-FPS bandage: under pressure Edit already rendered ~102–111 FPS while drawn Bubble state remained ~28–30 ms old; a later low-pressure Edit observation reached ~256.5 FPS. The smooth control could feel good around 60–61 D1 FPS with ~7–15 ms age. Judge the chain `produce -> publish -> Quick sync -> draw`, not FPS alone.
- [~] **Scaled speculation execution policy — third topology authored, installed proof required.** Preserve the supervisor-owned response-listener infrastructure, but do not keep a speculative child alive merely to use it. The second process was a real headroom tax (~20–30 extra native threads and ~800 MiB extra child private commit). The shared-COMPUTE A/B removed that tax but exposed another false assumption: `TaskPriority.LOW` is passive metadata on a FIFO executor, so 4K `QImage.scaled()` still ran at ordinary OS priority. Current source keeps all R-82 correctness/liveness, single-flight, bounded/latest-useful backlog, byte cap, generation fencing, raw release, QImage-only worker work and foreground authority for Lanczos/sharpen, but routes the derivative through one **lazy ThreadManager-owned serial background CPU thread**. On Windows it requests `THREAD_PRIORITY_BELOW_NORMAL` and disables dynamic wake-up priority boosts before executing best-effort work; if demotion cannot be installed the speculation fails closed rather than silently competing at normal priority. No timer/cadence, no second process, no IPC/shared memory, no generic COMPUTE worker occupancy. This is not closure until low/high-pressure mixed-refresh Windows evidence improves operator-visible smoothness/freshness without reviving R-80→R-86 defects.
- [~] **Gmail/Reddit hidden Repeater delegate forest removed / awaiting installed Qt validation.** Post-hotfix CUSTOM-resize support kept the full data buffer directly in each QML row model. Because Qt Quick `Repeater` instantiates every model entry, the dual run meant Gmail retained 18 rows for a visible limit of 10 and the two Reddit feeds retained 25/24 for visible limits of 20 — roughly **17 unnecessary hidden delegate trees** on Display 0. The larger accepted buffer now stays Python-owned; normal runtime materializes only the authored visible limit into the stable QAbstractListModel, while a CUSTOM vertical content extent conservatively projects additional buffered rows on demand and clearing CUSTOM returns to the exact limit. Fetch/cache capacity, instant CUSTOM expansion, settings SSOT and source cadence are unchanged. This is a documented secondary scene/sync-pressure repair, **not** a claim that 17 delegates explain the whole regression.
- [x] **R-86 forced Quick VSync hypothesis REJECTED / ROLLED BACK.** Source research correctly found that the generic ``swapInterval=0`` policy predates Qt Quick, but the production experiment that forced Quick to ``swapInterval=1`` was physically worse on the operator's two-display mixed-refresh setup: poorer pacing, poorer FPS/headroom, and higher apparent cost for ordinary interactions such as context-menu/Edit entry. This disproves the proposed repair for SRPSS even though the Qt documentation made it theoretically plausible. The Quick bootstrap is restored to the known-good release-era ``QUICK_SWAP_INTERVAL = 0`` contract. Do not reintroduce interval 1 as a generic Quick fix. Multi-window/mixed-refresh Qt scheduling must be treated as its own installed architecture problem; any future surface/pacer change needs an A/B against the known-good 5.0.0/5.0.1 Quick baseline and must improve operator-visible pacing on both 60 Hz and high-refresh windows without reducing Visualizer freshness/reactivity. ``QuickFramePacer`` remains architecture debt worth reviewing, but because it is unchanged from 5.0.1 it is not the primary fresh-regression suspect and must not be retuned blindly.
- [x] **CUSTOM Edit Save teardown regression — second exact cause repaired / INSTALLED VALIDATION GREEN.** The earlier call-signature `TypeError` masking bug remains repaired and typed. The fresh two-display run exposed a different deterministic combination: the Visualizer had coherently hopped **LG -> MSI**, System Stats was disabled in the same Edit transaction, and Save classified the ordinary retirement as `family_presence_changed`, queued `save_continue`, and tore down **1037 Qt objects** even though each operation is independently retained-safe. Root cause: `_presence_change_live_commit_is_coherent()` rejected display/monitor changes on *unrelated* session items before checking whether that item's presence changed. It now scopes route stability to the family being retired; the independent Visualizer transfer still must pass `_cross_display_transfer_is_coherent()` before live promotion. A regression test pins `System Stats disable + unrelated Visualizer transfer => display_transfer`, not `family_presence_changed`, so Save can execute both retained mutations without generation replacement. The SettingsLifetime follow-up logs then proved System Stats and Friend Pulse disable/save both live-retired without generation reconciliation, and multiple two-display Visualizer hops committed live.
- [x] **Settings critical exit after live family disable — Python ownership leak repaired / INSTALLED FOLLOW-UP GREEN.** At 22:53:28 Settings teardown destroyed all **846 Qt objects** and drained resources/work, but after 8 s the barrier still saw exactly one `QuickDisplayPresenter`, then correctly failed closed. The survivor came from the successful earlier Friend Pulse live disable: `retire_live_custom_layout_item()` removed its `OverlayGeometryBinding` from presenter ownership without calling `binding.retire()`. That orphan retains a preferred-size callback self-cycle, and its geometry sink closures capture the presenter; the barrier intentionally does not call cyclic GC to hide ownership mistakes. Mid-generation retirement now resolves the exact binding, retires/disconnects it first, then drops it from presenter records. A Qt regression test pins signal/callback/sink severance. The follow-up runs contain repeated Settings/Edit activity with no recurrence; final dual-display application retirement drained **1001 Qt objects / 4 Python presenter-unit owners in 469 ms**. Do **not** raise the barrier timeout or add `gc.collect()`; explicit ownership release is the contract.
- [~] **System Stats presentation invalidation narrowed; Windows/operator validation pending.** The shared 10 s source remains one low-priority event-driven/reconciliation owner and is not multiplied or sped up. A sample previously emitted broad `stateChanged`, causing QML to reconsider layout/style/config properties on every CPU/RAM/uptime/network update. Dynamic metrics now notify through dedicated `sampleChanged`; structural/config geometry remains on `stateChanged`. This is a direct fan-out reduction, not a slower poll or disabled functionality. Keep awaiting validation until normal runtime evidence/operator feel confirms benefit.
- [~] **Media first Play/Pause click duplicate — symptom contained, originating duplicate edge still under validation.** The torture log proved one initial interaction admitted `operation=play` followed immediately by `operation=toggle_play_pause`, undoing itself. Transport remains event-driven: one semantic command is submitted asynchronously and native GSMTC events/reconciliation update truth; do not convert Play/Pause/Next/Previous to polling. The shared Media owner now coalesces only a second Play/Pause semantic edge inside the same 200 ms input burst, arms only after provider admission succeeds, and logs the suppression. Failed first admission never blocks retry; Next/Previous are untouched. Treat this as `[~]` until the operator/log confirms the first-click double-action is gone and continue to prefer eliminating the duplicate at its originating admission seam over expanding the heuristic.
- [~] **CUSTOM Edit Save no longer treats disable as generation topology where retained owners can retire safely.** Disabling an already-retained ordinary widget now retires that exact presentation and neutral service group in-generation. Disabling the Visualizer now routes through the existing manager-owned Visualizer retirement/failover seam, fencing stale failover work and retiring the single controller/logical/GL owner without replacing DisplayManager. Live saves also advance `DisplayManager._widgets_config_snapshot` to the just-persisted map so an unrelated later topology event cannot resurrect stale enabled state. Incoherent ownership still fails closed to the existing reconstruction path. New admissions/enables remain a separate construction problem; do not generalize them by silently rebuilding unless the retained construction seam is proven impossible.

- [?] **FINAL R-84 diagnostic churn run — no more handle-discovery soaks after this.** Once the image/menu repairs above are in
  the local tree, run one deliberately bounded Windows acceptance session: keep one mode/preset stable; perform **3–5 explicit
  Settings open/close cycles**, allowing ~60–90 s of settled runtime after each, and exercise a few ordinary image rotations and
  context-menu opens between/after cycles. Use `--debug --fresh --usage --perf --life` only; no `--verbose` and no `--gpu-timing`.
  Decision is binary: (A) settled persistent handle classes staircase by ~20–30 each replacement -> treat as a real generation-
  retirement leak and repair those owners directly from existing lifecycle/type evidence, **without asking for another broad
  diagnostic soak**; or (B) only the first replacement steps and later cycles plateau -> close R-84 as one-time lazy/native
  initialization. The same final run is also the acceptance proof for Toolhelp, detached image publication and Context Menu
  notification isolation so the user is not asked for a separate performance soak afterward.
- [ ] **Quick-native startup/legacy image-boundary follow-up — do only after the normal-runtime detached path is proven.**
  There is real architectural value in extending the same ownership rule, but the paths are not equivalent. Startup desktop
  seeding originates from `QScreen.grabWindow(0)`, which necessarily yields a GUI-thread `QPixmap` and is already confined to
  startup/replacement-generation staging; optimize it only if startup profiling justifies the risk. The synchronous legacy
  `load_and_display_image()` / `show_image()` path still publishes QPixmaps and is reachable as a submission/failure fallback;
  after the normal async path is accepted, audit whether that fallback can consume/produce detached `QImage`/presentation state
  directly or be retired. Goal: one Quick-native presentation boundary, with QPixmap confined to genuinely GUI-native capture
  sources. Do **not** widen the current runtime-hitch repair until its Windows acceptance is known.

- [x] **Monitor wake double rebuild explained; no production optimization admitted yet.** Existing display detection already
  coalesces Qt topology/metric/application edges for 250 ms. On wake Windows exposed a genuinely different MSI-only topology
  at 13:46:11 and did not expose the final MSI+LG topology until ~13:46:14, roughly three seconds later. Each generation
  retired cleanly (destruction barriers ~344 ms and ~610 ms). A longer generic debounce would delay real hotplug/removal and
  still cannot reliably distinguish a seconds-long transient wake topology from a genuine one-screen state.
- [x] **Monitor regression/decision gate strengthened (2026-09-14; PySide run still required):** existing tests retain
  same-burst metric/resume coalescing and same-signature resume revalidation; a new two-stage wake test proves MSI-only can
  settle/reconcile first and a later genuinely distinct MSI+LG signature intentionally schedules/reconciles again. This
  explicitly protects against “fixing” the soak with a generic multi-second debounce. Do not add sleep/poll/debounce unless
  later evidence provides a reliable wake-specific settling signal; correctness currently outranks hiding this rare hitch.

- [x] **Previous generic 30–60 minute closure-soak request superseded.** The handle sidecar has already answered the broad
  attribution question; use only the bounded **FINAL R-84 diagnostic churn run** above. Do not ask the user for another hour-long
  discovery soak for this seam.


---

## 4D. Defaults/test authority hygiene — 2026-09-14 audit

The broad §0.18 “value-drift goldens” bucket was too coarse. Ordinary product defaults are intentionally mutable policy,
so tests must validate canonical ownership/parity rather than freeze today’s literal values. This audit is test/docs only:
production defaults and runtime behavior are not changed merely to satisfy assertions.

- [x] Audit the previously classified value-drift files plus a wider defaults/settings sweep. Mutable default expectations
  now derive from `core/settings/default_settings.py` through the canonical read seam or generated authority. Behavioral
  fixture inputs remain explicit test inputs rather than being coupled to product defaults. Exact literals are retained only
  when the literal itself is contractual and carry an adjacent `EXACT-VALUE INVARIANT:` rationale.
- [x] Defuse the Steam cadence trap: Abandonment/Achievement timer tests deliberately use their own short fixture cadence
  (`_FIXTURE_REFRESH_MINUTES`) and derive expected delays from that fixture. The current six-minute Steam product default may
  change without making those behavior tests red; separate authority/parity coverage owns the product default.
- [x] Reconcile non-default fossils misclassified as value drift: remove the retired transition-worker latency cell; align
  policy-compliance coverage with the explicitly permitted generation-owned Visualizer cadence lifetime; update installer
  reset-policy coverage to current installer behavior rather than the retired 5.0.0 migration default.
- [x] Canonical defaults audit and derived-artifact checks remain GREEN after the test rewrite: `check_defaults_authority.py`,
  `regenerate_defaults_artifacts.py --check`, and `regenerate_sst_defaults.py --check`. All 39 edited test modules compile.
  Full pytest execution still requires the intended Windows/PySide6 environment because project `tests/conftest.py` imports
  PySide6 unconditionally.
- [x] **Visualizer transient fallback/default duplication resolved without changing preset technical authority (2026-09-14).**
  End-to-end tracing confirmed the supported Quick lifecycle is configure -> apply complete technical mapping -> bind -> start;
  mode/preset changes stop/join the sole logical runtime before rebuilding/reapplying technical state and restarting it. Curated
  presets remain authoritative for every technical key they author, while Custom remains pass-through user-authored state; only a
  genuinely missing field reaches the model's canonical default. `tick_pipeline.py` therefore no longer invents `1.0/1.5` or
  Bubble `0.75/0.25` tuning, and Spectrum's FFT express lane no longer invents `kick_lane_gain=1.0` /
  `spectrum_lane_transient_mix=0.65`; those consumers require the already-resolved values and expose an ordering/ownership defect
  instead of silently substituting another tuning table. `visualizer_settings_contract.py` now names the old shared/global
  `1.5`-era values explicitly as **legacy migration baselines only**; special per-mode missing values fall through canonical
  authority rather than hard-coded compatibility literals. Pre/post semantic fingerprints across every shipped curated Bubble,
  Spectrum, Sine, Oscilloscope and Dev Curve preset plus arbitrary Custom technical values are byte-equivalent at the resolved
  value layer (SHA-256 `9a17f78e136f57be2e51b317692f0b4282c82b3fe17a61e089188c49f4eaac39`). Regression
  coverage now explicitly proves curated presets may author transient technical controls, Custom preserves them, and downstream
  Bubble/Spectrum consumers cannot regain numeric technical fallbacks. This changes no Bubble/Spectrum equations, tuning, preset
  payload or canonical product default. Retired global values remain untouched as compatibility signatures.
- [?] **Production/schema smell — retired transition worker default:** canonical settings still contain
  `workers.transition.enabled=True` although the supervised transition worker was retired when transitions became GPU/Quick-owned.
  Claude's production grep found **zero current production consumers** across core/engine/rendering/widgets. The remaining gate
  is therefore compatibility only: trace persisted-profile/import/migration handling, then remove the key through canonical
  schema + generated-artifact regeneration if no supported compatibility owner remains. Do not preserve dead schema because
  historical tests once referenced it.
- [x] **Windows/PySide6 mutable-default audit run completed (Claude, commit `f9343b53` preserved):** all **39 changed test
  modules** were executed. Initial result **760 passed / 9 failed**; two failures were defects introduced by the audit rewrite
  itself and were repaired test-only (symmetric nested `collect_diff()` handling plus the missing
  `require_canonical_default` import). Rerun result: **762 passed / 7 failed** with no production/default/artifact change.
  The seven survivors are now classified instead of being called generic value drift: four stale tests
  (`visualizer_bucket_toggles...`, Spectrum bucket order, retired Abandonment no-callers, fake rainbow visibility binding) and
  three real behavior/integration investigations (Spectrum preset-slider/custom index, audio-worker gain-one fixture requiring
  resolved technical config, MC interaction-mode profile behavior). None is a BTF/real-GL case in this set.
- [?] **Small positive-coverage gap from that audit:** Achievement runtime uses the same independent five-minute test fixture
  pattern as Abandonment, but lacks Abandonment's symmetric test proving its runtime default follows canonical
  `widgets.steam.refresh_minutes`. Runtime currently reads the same canonical Steam defaults, so this is coverage debt rather
  than a product defect; add the positive authority test when that test family is next touched.


---

## 4E. CUSTOM Visualizer quarter-turn orientation — feasibility accepted, implementation deferred

Feature request: while CUSTOM Edit mode is active, eligible Visualizers gain a small turn/flip glyph. Each click advances the
content orientation by one clockwise quarter-turn: `0° -> 90° -> 180° -> 270° -> 0°`. Example: a tall Spectrum whose bars
currently travel upward can be turned so the same authored/reactive visualizer behaves as a wide logical viewport rotated into
the tall physical card, with bars travelling right, then down, then left on successive clicks.

This is feasible, but it is **not** a finished-pixel/QML `rotation` feature. Viewport shape is semantic input to Bubble,
Spectrum, Sine, Oscilloscope and Dev Curve; rotating only the final pixels/vertices would bypass existing wide/tall shape
profiles and can break reaction amplitude, density, clipping, line thickness, Bubble tails/specular/gradient behaviour and
other viewport-derived invariants. The feature therefore belongs at the shared Visualizer presentation/layout seam.

- [ ] **Initial scope: carded accepted modes only.** Admit Spectrum, Oscilloscope, Sine Waves, Bubble and Dev Curve. Exclude
  frameless modes and specifically Voxel Sphere initially. Sphere has experimental unclipped overflow, 3-D lighting/shadow and
  its own coordinate semantics; do not make this feature a reason to couple Sphere back into accepted-mode architecture.
- [ ] Add one CUSTOM-layout-owned quarter-turn token, preferably `content_rotation_quarters` constrained to `{0,1,2,3}`.
  It is **layout/presentation state, not a Visualizer setting or preset technical setting**. Persist it inside the Visualizer's
  existing CUSTOM `size_payload`; old entries with no token resolve to `0`. Do not add a second settings authority or mutate
  authored preset payloads.
- [ ] Keep the physical saved geometry authoritative and unchanged. The committed `rect`, monitor route, uniform scale and
  `viewport_extent` remain exactly what the user edited. For `90°/270°`, resolve an **effective logical content viewport** with
  width/height swapped, run the existing mode shape/reactivity logic against that logical domain, then apply one shared
  logical-to-physical quarter-turn transform back into the unchanged card/content clip. `0°/180°` keep the logical axes;
  `180°` changes direction only. This is the critical distinction that lets a tall card behave like a wide visualizer without
  rewriting its stored geometry.
- [ ] Implement the transform once in the common Quick Visualizer render/presentation contract, not separately in five mode
  renderers. Mode-specific code may need only narrowly proven direction-vector adaptation where a shader currently consumes a
  screen-space direction directly (for example Bubble gradient/specular direction); prefer deriving those vectors through the
  common orientation transform rather than adding per-mode orientation settings.
- [ ] Edit UI: add one themed circular turn glyph to `CustomLayoutOverlay.qml`, visible only for the active Visualizer when the
  current descriptor admits quarter-turn orientation. It must not steal drag/resize/display-hop input zones and must remain
  scale/header aligned with existing edit chrome. Clicking changes working session state immediately; Cancel restores the
  admission value, Save commits it, Restore Size must **not** silently reset orientation unless product UX explicitly decides
  that Restore Size owns orientation too.
- [ ] Save/load/slot contract: existing layout slots already capture the whole `custom_layout` root, so orientation must round
  trip through ordinary CUSTOM save/load and slot Save/Load without a parallel slot schema. Cross-display hop must preserve the
  token. Legacy layouts/slots with no token must load identically to today (`0`). Version-bump only if the normalizer cannot
  safely treat the optional size-payload field as backward compatible; do not bump merely because a new optional payload key
  exists.
- [ ] **Golden behavioural proof before merge:** with orientation `0`, resolved presentation/render state must be semantically
  identical to pre-feature behaviour for every accepted mode and curated/Custom preset. Prove quarter-turn does not alter
  audio/reactivity values, preset technical authority, AGC/floor state, authored mode settings, uniform scale or stored extent.
  Add pure transform tests for four-click identity, `90+270 == 0`, axis swap only on odd quarters, Save/Cancel/slot round trips,
  cross-display preservation and legacy-no-token replay. Then run the existing visualizer geometry/reactivity suites plus
  installed eyes-on checks for extreme wide/tall Bubble, Spectrum, Oscilloscope, Sine and Dev Curve. Bubble's current reaction
  amplitude/freshness contract remains golden: no compensation that reduces reaction is acceptable.
- [ ] Performance/lifetime: quarter-turn is event-driven only. No timer, polling, alternate cadence, retained duplicate
  renderer or per-frame settings lookup. Changing orientation may publish/rebuild the normal immutable presentation snapshot,
  but must not reconstruct the Visualizer runtime or create a second logical state owner.

**Risk decision:** medium/high implementation risk but architecturally bounded. Keep in Current Plan because the persistence and
owner seams already exist and the safe shape is clear; do not implement opportunistically during unrelated Visualizer work.
If the common logical-to-physical transform cannot be made mode-neutral without mode-specific geometry forks, stop and move the
feature to `Future_Work.md` rather than compromising the existing viewport/preset/reactivity contracts.

## 5. Test / debris reconciliation

Detailed ownership lives in `Future_Cleanup.md` and `Docs/TestSuite.md`; this active plan carries sequencing only.

- [x] Reconcile the known broad-suite fossil assertions against current owners without changing production authority.
  Completed at the test boundary on 2026-09-13: `test_widget_visual_roles.py` **16/16 PASS**; five touched Widget Theme
  state-machine cases PASS; `test_capability_activation.py` **33/33 PASS**; the four reproduced
  `test_widget_descriptors.py` fossils **6/6 PASS**; and the two GODZIP/AppData persistence fossils **2/2 PASS**. The
  repaired assertions now follow strict schema-v3 I/O, explicit canonical Theme state/defaults, current descriptor/lazy
  dependency ownership, shared Clock authored-position routing, retired Growth semantics, and repo-local Foundry settings
  without banning legitimate LocalAppData-based Git Bash discovery. No production defaults/fallbacks, retired QWidget
  paths, compositor owners, timers or pollers were restored to satisfy tests.
- [x] 2026-09-13 follow-up pure/source contracts: Friend Pulse recovery/dropped-message absence + Restore Size authored-cache separation + System Stats metric-selection/content-extent/pill-width/source skipping execute directly without PySide. Latest focused direct runs: **9/9 System Stats source**, **4/4 System Stats reflow/selection**, **4/4 Friend Pulse/Restore**. Python compilation is clean for all touched Python modules.
- [x] Maintained `destination` profile executed on Windows/PySide6 6.9.1: **132/132 GREEN** (2026-09-14, see
  `Docs/TestSuite.md` §0.17). Every previously deferred red and destination-target NEEDS RUN was reconciled at the
  test boundary against current production; no production owner/default/fallback was changed.
- [x] Broad full-tree fossil-hygiene + reconciliation pass (2026-09-14, see `Docs/TestSuite.md` §0.18). `collect_ignore`
  confirmed empty (no fossil graveyard), 0 collection errors, module count 368→364. Four whole-file fossils deleted and
  fossil cells trimmed/rehomed from ~8 files; a large batch of stale current-owner tests reconciled. Broad per-file
  failures 58→32 files. No production behaviour/default/schema changed; destination profile still 132/132 GREEN.
- [?] Continue the remaining broad-tree reconciliation using `Docs/TestSuite.md` §0.21 as the current classification.
  The old §0.18 “value-drift goldens” bucket has been audited/superseded: mutable-default copies were rewritten to authority,
  several stale policy/migration cells were reconciled, and literal behavioral fixtures were explicitly preserved as test
  inputs. Outstanding reds are now to be treated individually as behavioral/integration work, BTF/real-GL acceptance, true
  documented exact-value invariants, or newly discovered stale tests. Do not preserve a red merely because §0.18 once listed it.
- [ ] Retire the temporary Visualizer `enabled_modes` compatibility migration only after automated persisted-profile/import
  coverage proves supported profiles no longer rely on it. Current runtime/default/UI state remains the canonical
  `widgets.spotify_visualizer.mode_activation` boolean map.
- [ ] Complete caller-proven READY deletion rows in `Future_Cleanup.md` only after their exact caller/test prerequisites are
  satisfied; dormant compatibility-horizon rows remain dormant.

---

## 6. Content-extent resize rollout (in progress, added 2026-09-13)

The chosen model is one **uniform CUSTOM-scoped presentation override** (no settings
mutation): the extent overrides the *effective* count / padding / separator / truncation
while in CUSTOM; the widget's real settings (`limit`, separator/word-count) stay the SSOT
default. One authority per context (setting = default, extent = CUSTOM override), persisted
via CUSTOM `size_payload` + slots, no teardown. Reusable stack lives in
`custom_layout_session` / `custom_layout_owner` / `custom_layout_overlay` /
`CustomLayoutOverlay.qml`, gated by the descriptor `content_extent_axes` field; a family
opts in by declaring axes + consuming `content_extent` in its payload handler + reflowing.

- [x] **Friend Pulse** — both axes; operator-validated.
- [x] **Reddit (reddit + reddit2)** — vertical count ± (buffer up to 25, `limit` = SSOT
  default) then row/separator spread; horizontal = free width-elide. Tested.
- [x] **Gmail** — vertical count ± (buffer up to cap, `limit` = SSOT default) then
  row/boundary-separator spread; horizontal = free width-elide + preferred-width widen.
  Tested.
- [x] **Media — CUSTOM presentation-only horizontal/vertical reflow implemented (2026-09-13).** Media now declares both shared content-extent axes and a family-owned **logical** direct-axis floor of `520×210`. The floor is consumed only by side gestures (projected through the current uniform transform); it does **not** replace the ordinary uniform corner/wheel shrink contract. No Media source owner, cadence or artwork transition owner is added. The only new real setting is `Allow Landscape Artwork`, canonical default OFF; it controls only the artwork aspect cap during CUSTOM horizontal reflow.
- [x] **Media side-handle `QSize` hotfix (2026-09-13):** `CUSTOM_LAYOUT_MIN_WIDGET_SIZE` is a `QSize`; the first Media content-extent floor incorrectly passed that object directly to scalar `max(...)`, producing repeated `TypeError: '<' not supported between instances of 'PySide6.QtCore.QSize' and 'int'` during side drags. The direct-axis floor now derives scalar generic minima via `quick_custom_minimum_size(item).width()/height()` before applying the family logical floor. No QML/layout policy change.
- [x] **Media metadata left-anchor hotfix (2026-09-13):** vertical compaction previously scaled the metadata column around `Item.Center`, so title/artist could visually drift right during CUSTOM reflow even while layout anchors remained correct. Metadata compaction now scales around `Item.Left`; no content-extent geometry, artwork, crossfade, controls, volume or Settings contract changed.
- [?] Installed visual validation: repeatedly horizontal/vertical resize Media through compaction/expansion and confirm Title/Artist stay visually pinned to the intended left edge at all extents/DPRs while artwork, seek/control alignment and volume behavior remain correct.
- [?] **Media side-handle hotfix installed validation:** drag all four direct side handles repeatedly at normal and uniformly scaled Media sizes; confirm no QML/Python exceptions, family floor enforcement remains axis-correct, and corner/wheel uniform resize is unchanged.
  - **Horizontal side resize:** changes only the logical content width at constant uniform scale. Seek track and control bar grow/shrink with the card while retaining alignments; metadata receives the added/removed lane; artwork consumes 35% of extra width while preserving a metadata lane. With canonical-default-OFF `Allow Landscape Artwork`, it is capped at `width <= height` so square is the maximum; enabling the checkbox removes only that shape cap and permits landscape artwork without changing the growth rate, metadata reserve, clipping, crossfade or shadow contracts. The external app-volume accessory keeps its authored horizontal width and does **not** widen from horizontal-only content extent.
  - **Vertical side resize:** changes only logical content height. Section/metadata spacing grows/shrinks with the box, artwork may extend into portrait while retaining the existing inset/mask/clipping/shadow/crossfade contracts, and the top/bottom-anchored volume track becomes longer/shorter with Media height.
  - **Uniform corner/wheel resize:** keeps the one whole-presentation uniform transform, including the external volume child. A side-reflowed logical box keeps its aspect/reflow while the entire result scales.
  - **Direct-axis shrink floors:** side handles no longer collapse Media to the generic 40 px floor. Vertical compaction hides Album first below 255 logical px, then playback-state chrome below 225, before the 210 px floor; Title + Artist and enabled seek/transport remain. Horizontal compaction stops at the 520 px logical outer floor. These are CUSTOM presentation policies, not Settings defaults.
  - **SSOT/guardrails:** `ArtworkFadeImage` remains the sole artwork swap primitive; existing clipping/mask/directional artwork shadow remain untouched. Restore Size clears Media `content_extent` back to canonical authored geometry while preserving CUSTOM X/Y/display. Focused no-PySide Media content-extent/landscape contracts pass **7/7**, Media external-volume/source contracts pass **6/6** (excluding the unrelated absent Steam-logo asset assertion), generated defaults/SST `--check` is GREEN, defaults-authority audit is GREEN, and touched Python compiles.
- [?] **Media installed/PySide validation:** exercise horizontal-only, vertical-only, then corner/wheel resize with and without the app-volume accessory. Confirm seek/control widths and metadata room respond horizontally; with `Allow Landscape Artwork` OFF artwork can reach square but not landscape, then toggle it ON and confirm only the square cap disappears; vertical growth creates portrait artwork + more spacing + a longer volume track; horizontal-only never widens the volume child; direct shrink hides Album then playback state at sane points; Restore Size clears the extent; clipping, rounded mask, directional artwork shadow and shared 520 ms crossfade remain clean across DPR/two displays.
- [ ] **Games You Follow** (future) must ship with both shared content-extent axes in its first retained implementation;
  horizontal/vertical side reflow, corner/wheel uniform scale, row-variant authored geometry, Restore Size, slot replay
  and mixed-DPI transfer are admission requirements rather than follow-up polish.
- Note: padding/separator/truncation are **not** promoted to real settings (Reddit had none;
  promoting would add per-widget schema + migration and risk SSOT). Kept CUSTOM-scoped.

## Standing guardrails

- **Voxel Sphere golden preservation:** current accepted Sphere reactivity/motion/preset behaviour is golden. Keep the mode architecturally isolated; do not retune or migrate it into permanent/shared Visualizer owners unless the operator explicitly requests that work.
- **Visualizer fidelity / scaling (R-69, binding):** extreme CUSTOM geometry must
  never be solved by globally reducing head radius, authored reaction amplitude,
  motion, Ghost/history displacement, or by adding a second viewport/domain
  compensation that makes wide/tall modes less reactive. Bubble is the golden
  reference; tall-Spectrum response protection is equally binding.
- **Live CUSTOM ownership:** CUSTOM outer geometry is Python/session-owned; QML
  reports gesture intent only. One operation publishes one coherent
  rectangle/extent/scale. Visualizer sides = one-axis viewport extent; corners =
  independent X/Y extent; wheel = uniform whole-Visualizer scale. **Save is not a
  teardown boundary.**
- **CUSTOM is global layout mode:** the first widget entering CUSTOM disables authored
  stacking/adjacency globally, including number-key saved-layout load. Visualizer
  preset `Custom` is a separate concept.
- **Media ownership:** GSMTC/event ownership is primary; no fast Media polling or
  process-probe fallbacks. Visualizer consumes Media admission but never acquires a
  second Media owner.
- **Performance admission:** the operator-visible Qt Quick smoothness regression is ACTIVE. Bubble is a canary only. Preserve logical freshness/reactivity; compare like-for-like settled frame/presentation-age tails and prefer fewer/event-owned mechanisms over polling. See `Docs/Guardrails/Performance_Optimization_Contract.md`.
- **Defaults SSOT:** `core/settings/default_settings.py` is the sole authority;
  `.json`/`.sst` are derived and audit-gated. Never add a second default authority.
- **Settings styling authority (dark.qss retired 2026-09-14):** `themes/dark.qss`
  is physically deleted and the retirement is operator-accepted. Settings/tray
  styling draws structure from narrow permanent renderers and semantic values
  from `SettingsThemeSpec`. Never reintroduce a monolithic Settings QSS file or a
  fallback stylesheet loader, even when the asset is absent.
- **Visualizer preset ownership:** per-mode preset files are user-authored state. Users may add arbitrary counts, delete down to one, and leave sparse authored numbers. Runtime compacts them into slider positions without renaming/deleting files. A shipped preset manifest is packaging/reconciliation metadata, never runtime authority over user-authored presets.
- **No fallback architecture:** failures should remain explicit and diagnosable; do
  not solve closeout work by adding silent fallback ownership, timers, or pollers.

## Authority order

```text
exact current source + current reconciled test tree
-> Current_Plan.md (this file: active work + order)
-> Spec.md
-> FWPlan.md (future / non-blocking implementation)
-> Future_Cleanup.md / Docs/TestSuite.md (cleanup + test truth)
-> Index.md + focused/decomposition docs
```

## Durable references

- `Index.md` — routing map to current owners.
- `Docs/TestSuite.md`
- `Future_Cleanup.md`
- `FWPlan.md`
- `Docs/Future_Work/Steam_Friend_Pulse.md`
- `Docs/Future_Work/System_Stats_Widget.md`
- `Docs/Future_Work/Settings_Dark_QSS_Retirement.md`
