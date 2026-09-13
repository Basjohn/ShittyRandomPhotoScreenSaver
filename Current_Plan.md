# Current Plan — Active Work

Last updated: 2026-09-13

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
- [x] **Implemented unread-message notification (source acceptance awaiting validation):** replace the old `1 playing / N friends` secondary summary with ALL-CAPS `NN UNREAD MESSAGE(S)`. One unread opens that friend's Steam chat directly; multiple opens a small selectable sender menu with avatar where admitted. Reuse the existing finite event-glow path for count increases. Historical unread state must come from a real Steam unread source, never a fabricated counter. Do not add a second timer/poller; piggyback Friend Pulse's existing source owner/cadence/dormancy.
- [x] **Unread rail is fail-silent (2026-09-13 log follow-up):** zero proven unread messages renders a blank summary rail, and an unavailable/failing unread backend also renders blank. `MESSAGES UNAVAILABLE` is forbidden user-facing content. Only a proven positive count renders `NN UNREAD MESSAGE(S)`. The supplied 19:36/19:42 log proves `friend_message_sessions` itself failed twice and entered 60s then 120s shared backoff while ordinary Friend Pulse sources succeeded; the old log did not retain the safe result class/HTTP code, so exact 401/403/invalid-response cause is not recoverable from that run. New redacted diagnostics record only source + result status + HTTP status for the next acceptance run.
- [x] **Focused non-Qt recovery gates:** pure unread parsing/redaction, unlimited opaque pin persistence/order, FriendMessages endpoint construction/redaction, Friend Pulse source presentation contracts, and Restore Size source contract pass directly in the PySide-less build environment (10/10). New Qt/runtime behavior tests are authored rather than omitted.
- [?] **Recovery/Restore Qt test execution:** run the new Friend Pulse runtime/QML and CUSTOM session/overlay/owner tests in the project PySide6 environment. Confirm hover-only pins, removed status circles, offline desaturation/clipping, ALL-CAPS status/message chrome, `↶` Restore Size routing and exact X/Y/display preservation. Specifically side-resize Friend Pulse/System Stats, then Restore Size and prove the target is the canonical authored size rather than the just-committed CUSTOM `content_extent`.
- [x] **Restore Size authored-geometry authority repaired after 2026-09-13 log:** the log proved routing beyond Friend Pulse/Visualizer (Friend Pulse, System Stats, Weather, Media and Visualizer all received Restore Size with exact X/Y preserved and `emergency_fit=1.0000`), but it also exposed that `DisplayPresenter._base_geometries` could be overwritten by an effective committed CUSTOM rectangle/content extent. Geometry binding now publishes a separate committed-rect-free authored projection, and the presenter admits the canonical pre-CUSTOM preferred geometry once then freezes authored-cache updates while CUSTOM/edit owns layout. CUSTOM `content_extent` churn therefore cannot redefine the Restore Size target. Restore still clears `content_extent`, preserves display/X/Y, stays in CUSTOM, performs no stacking/ordinary auto-fit/shrink, and only emergency-fits when the authored rectangle itself exceeds the display.
- [?] **Unread-source live acceptance:** with the user's real configured Steam Web API credential, confirm `IFriendMessagesService/GetActiveMessageSessions/v1/` accepts the key and reports historical unread sessions/counts. If Valve rejects that credential class, keep the unread rail fail-silent/blank and do not fabricate zero; use the new redacted status/HTTP diagnostic to prove the rejection class, then investigate the already-documented Steam client callback/session route as the source upgrade.
- [?] **Awaiting Validation:** use a real connected Steam account to inspect long names/game names, Rich avatar-cache
  hydration, Strict/Balanced reprojection, private/unavailable/stale wording, manual refresh behavior, friend chat/profile
  routing, game Store routing, rounded avatar/tile borders, hover-only multi-pin behavior, and both finite theme-colored
  event glows against real themes. Friend-change glow remains game/presence evidence; unread-message glow is sourced only
  from an admitted increase in the real unread-session count.
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
- [x] Canonical default artifacts regenerated from `default_settings.py`; generated JSON + both SST files pass regeneration check, and the broader defaults-authority audit is GREEN. The audit also removed three pre-existing Friend Pulse runtime literal defaults in favour of canonical default-contract reads without changing behaviour.
- [?] **System Stats installed/PySide validation:** confirm the wider `System Stats` pill no longer clips, all four metric toggles round-trip, hidden metrics immediately disappear and their disabled OS reads stay skipped without sampler multiplication, horizontal/vertical side handles reflow cleanly at small/large extents, and Restore Size returns the canonical non-CUSTOM authored family rectangle when no emergency display fit is required.
- [?] **Awaiting Validation:** installed minimum-interval off-vs-on Visualizer contention run must confirm no meaningful
  freshness/reactivity or event-loop/presentation-tail regression with CPU/Memory/Uptime/Network enabled.
- [?] **Awaiting Validation:** repeated enable/disable, interval changes, runtime recreation and two-display soak must
  confirm one shared owner, no refresh multiplication and clean final retirement.

---

## 3. `dark.qss` retirement → ThemeSpec sole authority

Execution authority: `Docs/Future_Work/Settings_Dark_QSS_Retirement.md`.

Migrate the Settings dialog's remaining colour **and** structure authority out of
`themes/dark.qss` into `SettingsThemeSpec`, leaving ThemeSpec as the sole Settings GUI
style authority. Preserve the accepted dark-theme appearance and eliminate the
competing stylesheet authority completely.

- [ ] Inventory every remaining selector/property in `themes/dark.qss` against current
  `SettingsThemeSpec` ownership.
- [ ] Move required structural and colour semantics into the ThemeSpec-backed path
  without creating a second fallback authority.
- [ ] Delete `themes/dark.qss` once no runtime/build path requires it.
- [ ] Preserve dark-theme appearance with focused regression coverage and physical
  Settings GUI validation.
- [ ] Confirm widget themes/runtime theming remain unaffected by the Settings-only
  authority retirement.

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
  generation owner, retained Quick rows, canonical Settings/default migration and ordinary/CUSTOM acceptance.

---

## 4A. Settings slider commit / crash hardening — additional active work

This is additive and must not displace the Friend Pulse/message/Restore Size acceptance work above. A 2026-09-13
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
  text-shadow roles. Row/grid tile surfaces, avatar frames, pin/menu controls, separators, unread-message popup and empty-state
  icon do not currently own equivalent directional surface shadows.
- [x] **Shadow prescription:** add, if visual validation agrees, subtle same-direction shadows to row/grid tile surfaces and
  the unread-message popup. Avatar frames should not use a filled rectangular shadow: shadow the border-ring alpha itself
  (or an equivalent outline-only source) so the empty/transparent interior stays empty, using the existing global card
  shadow direction/color with lower alpha/blur. The empty-state icon may take a very light same-direction shadow. Leave thin
  separators, pin glyphs/buttons and three-dot affordances unshadowed by default; they are too small and become muddy fast.
  Do not invent a Friend Pulse-only direction authority.
- [x] Improve dynamic Media/Steam artwork changes through the shared event-driven `ArtworkFadeImage` SSOT. Keep the current
  readiness-gated two-buffer/no-flash contract and frame-demand ownership; make replacement transitions gentler for every
  existing Media/Achievement/Abandonment artwork consumer without per-widget timers or duplicate transition machinery.
  Shared replacement fade is now 520 ms with `InOutSine`; empty-source fade is 280 ms. The Abandonment-local 340 ms override
  was removed so the shared primitive is authoritative. Pure artwork/slider contract checks pass 9/9 combined.
- [?] Visual validation across Media + Steam artwork surfaces: rapid source churn, missing->ready, ready->missing, same-source
  withdrawal, DPR/theme changes, and no retained second texture after transition idle.

---

## 5. Test / debris reconciliation

Detailed ownership lives in `Future_Cleanup.md` and `Docs/TestSuite.md`; this active plan carries sequencing only.

- [x] Reconcile the known broad-suite fossil assertions against current owners without changing production authority.
  Completed at the test boundary on 2026-09-13: `test_widget_visual_roles.py` **16/16 PASS**; five touched Widget Theme
  state-machine cases PASS; `test_capability_activation.py` **33/33 PASS**; the four reproduced
  `test_widget_descriptors.py` fossils **4/4 PASS**; and the two GODZIP/AppData persistence fossils **2/2 PASS**. The
  repaired assertions now follow strict schema-v3 I/O, explicit canonical Theme state/defaults, current descriptor/lazy
  dependency ownership, shared Clock authored-position routing, retired Growth semantics, and repo-local Foundry settings
  without banning legitimate LocalAppData-based Git Bash discovery. No production defaults/fallbacks, retired QWidget
  paths, compositor owners, timers or pollers were restored to satisfy tests.
- [x] 2026-09-13 follow-up pure/source contracts: Friend Pulse recovery/unread fail-silent + Restore Size authored-cache separation + System Stats metric-selection/content-extent/pill-width/source skipping + Steam message parsing/backend construction execute directly without PySide. Latest focused direct runs: **9/9 System Stats source**, **4/4 System Stats reflow/selection**, **4/4 Friend Pulse/Restore**. Python compilation is clean for all touched Python modules.
- [?] Run the full installed `pytest tests/` inventory with real PySide6/Qt resources and reconcile any *additional*
  current-owner failures. This workspace cannot execute that gate because PySide6 is unavailable; do not treat the
  targeted direct-module passes above as a substitute for the full installed suite.
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
- [ ] **Games You Follow** (future) gets both axes when it exists (reuse the shared stack).
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
