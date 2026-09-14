# Current Plan — Active Work

Last updated: 2026-09-14

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

- [?] **COMPLETELY FUCKED — `--usage` handle trend has a >80% PDH-observer attribution, but the residual application-handle
  leak question is not closed until the instrumented Windows soak proves it.** Stable 04:00–13:30 RSS/USS/private memory and app/thread/resource ownership are flat while main handles rise about
  +180 overall. `WindowsGpuUsageCollector` intentionally rebuilds its process-scoped `GPU Engine` / `GPU Process Memory` PDH
  query every 300 s because GPU-engine instances are dynamic. The process-handle sample is captured before the GPU collector
  rebuild; the sample immediately after each `gpu_status=warming` boundary therefore reflects the newly enumerated query's
  current counter cardinality. Across that stable interval those post-rebuild samples contribute **+341 handles**, while all
  other sample-to-sample changes net **-161**. This is strong attribution, not closure: until the next Windows soak shows no
  independent residual slope after PDH cardinality is accounted for, R-84 remains **COMPLETELY FUCKED**. The collector closes
  the old query before opening the new one and rebuild steps
  can decrease as well as increase, which is inconsistent with a monotonically leaked old query. Rebuild samples are modest:
  median collection ~17.9 ms vs ~15.4 ms ordinary samples at a 15 s usage cadence / 300 s GPU rediscovery cadence.
- [x] **Usage instrumentation/regression authored (2026-09-14; Windows soak still required to close R-84):** preserve full GPU/VRAM
  statistics and the 300 s rediscovery requirement. A dynamic fake-PDH lifecycle test now changes engine/memory instance
  cardinality across two real `collect()` rebuilds, requires the prior query to close before the replacement opens, proves
  counter lists are replaced rather than appended, and proves final `close()` drains query/counter ownership. `--usage` now
  also logs the already-owned `gpu_query_generation`, engine/dedicated/shared counter counts and total PDH counter cardinality
  beside `handles_main`. This adds no new OS query, enumeration, timer or work when `--usage` is off and preserves full
  GPU/VRAM fidelity while making the required closure soak possible. Instrumentation is not a fix and does not promote R-84
  out of **COMPLETELY FUCKED**. Do **not** reduce GPU coverage/cadence merely to flatten `handles_main`. If the Windows soak
  still shows growth after accounting for PDH cardinality, add targeted handle-type diagnostics in a dedicated sidecar
  (not `--perf`) and pursue the surviving owner.

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

- [?] **Installed validation after soak repairs:** run the new §0.19 regressions in the intended Windows/PySide6 environment,
  then repeat a bounded cache-heavy soak with cache/usage diagnostics. Confirm scaled-prefetch completions continue after raw
  eviction pressure, pending scaled bytes do not pin near the cap without producers, Reddit produces no zero-delay due bursts,
  and use `--usage`'s query/cardinality fields to determine whether any residual main-process handle slope survives. R-84
  stays **COMPLETELY FUCKED** until that result is known. Also confirm full GPU/VRAM statistics and query replacement/close
  ownership remain intact. Monitor wake remains an
  observational gate only; two rebuilds are still correct when Windows presents two genuinely distinct settled signatures.

---

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
- [?] Resolve the remaining 32 broad-tree red files (enumerated in `Docs/TestSuite.md` §0.18). None are fossils — they are
  current-owner value/behaviour drift (goldens needing per-value confirmation, deeper integration-fixture work, Bubble
  reactivity BTF judgment, and real-GL acceptance). Reconcile per-owner as each is confirmed intended; do not weaken
  Bubble goldens or alter production to satisfy them.
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
- **Performance admission:** no Visualizer performance investigation is active. Reopen only from a persistent/growing/traceable defect observed in normal use or logs; do not schedule synthetic probe campaigns to search for one. Any admitted optimization must preserve freshness/reactivity and latency-tail quality and prefer fewer/event-owned mechanisms over polling. See `Docs/Guardrails/Performance_Optimization_Contract.md`.
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
