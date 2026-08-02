# Visualizer Runtime Shape Audit

Last updated: 2026-06-28

Status: `Historical / watchlist`

## Objective

Preserve the root-cause map for the visualizer geometry family where:

- the saved CUSTOM rect is correct
- replay logs can look green
- runtime can still produce impossible visualizer shapes anyway

Any future solution or regression pass must:

- preserve the strict uniform CUSTOM resize contract
- avoid endangering unrelated widget behavior
- avoid steady-state frame churn
- avoid masking the real problem with sloppy fallbacks

## Non-Negotiable Constraints

- No widget gets extra width authority from Reddit/Gmail growth or content-budget paths.
- Visualizer CUSTOM rect authority must remain uniform-only.
- Recovery paths are secondary safety nets, not substitutes for root-cause work.
- A green `replay_final` log is not enough for closure.
- Automation bars must fail the real user-visible runtime shape, not just helper seams.

## Watchlist Status

The visualizer geometry family is no longer active in `Current_Plan.md` after the preserved `2026-06-28 16:31-16:36` `--geo` run:

- evidence snapshot: `.tmp/perf_collapse_evidence_20260628_164113`
- ordinary `spotify_visualizer` edit/save/replay cycles were clean
- no `[CUSTOM_LAYOUT][FALLBACK] Repaired spotify_visualizer CUSTOM save route...` appeared in that run
- no duplicate-owner or requested-CUSTOM-monitor fallback appeared in that run
- saved/replayed rects stayed coherent through the inspected transfers:
  - `16:32:15` save to monitor `2`
  - `16:33:13` save to monitor `1`
  - `16:34:47` save on monitor `1`

Reopen this audit only when fresh `--geo` evidence shows route repair, duplicate owner fallback, impossible visualizer shape, or runtime replay drift. Recovery paths must remain loud if they fire.

## Prior Reopen: 2026-06-28 Save-Route Poison

The newest `--geo` evidence changes the immediate priority. The recovery seam is behaving better, but the clean edit-save path is not clean:

- `logs/screensaver_geometry.log`
  - `03:51:35` `widget=spotify_visualizer phase=edit_shell_create ... local=(492,348,724,483) global=(492,348,724,483) ... had_prior_custom=true`
  - `03:51:47` `WARNING [CUSTOM_LAYOUT][FALLBACK] Repaired spotify_visualizer CUSTOM save route from shell rect ownership old_monitor=1 new_monitor=2 ... rect=(2584,600,724,483)`
  - `03:51:47` `widget=spotify_visualizer phase=save_scene local=(24,600,724,483) global=(2584,600,724,483) ... monitor=2`

### Why this matters

- the visible/edit shell rect can be correct
- save-time repair can make persistence survive
- but the shell state still starts with stale monitor authority and needs a fallback to avoid poisoning settings

This is not acceptable as steady state. The save-time repair remains a useful loud safety net, but the next root-cause pass must make the normal path stop needing it.

### Current-tree route-authority map

| Phase | Current owner | Current behavior | Risk verdict |
|---|---|---|---|
| Runtime spawn owner | `rendering/spotify_display_participation.py` and `rendering/widget_setup_all.py` | Chooses a participating owner for CUSTOM visualizer creation and delays fallback when a requested display is present but temporarily non-participating. | Keep, but do not blame without matching `[SPOTIFY_VIS][FALLBACK]` evidence. |
| Creator-time `Custom+ALL` repair | `rendering/spotify_widget_creators.py` | Recovers missing CUSTOM monitor only from the live screen bucket; otherwise suppresses or restores authored route loudly. | Narrower than earlier versions, but must stay separate from edit-session save-route repair. |
| Startup CUSTOM rect priming | `rendering/spotify_widget_creators.py::_prime_visualizer_custom_rect_for_startup()` | Attaches committed rect before `startup_create` so preferred-height cannot freelance from a bogus shell. | Keep. This is not the current save-route poison. |
| Startup stabilization | `rendering/widget_setup_all.py::_verify_saved_custom_layouts_after_startup()` | Delayed verify/confirm reapply if live card or overlay disagree with committed rect. | Keep narrow and loud; do not expand into a steady-state corrector. |
| Runtime card positioning | `rendering/widget_manager.py::position_spotify_visualizer()` | Uses `_custom_layout_local_rect` first; refuses authored placement when CUSTOM is selected but rect is pending. | Keep. Current issue is earlier route metadata inside edit shell state, not this card rect authority by itself. |
| Runtime overlay geometry | `rendering/display_image_ops.py::_resolve_spotify_visualizer_overlay_rect()` | Prefers visualizer GPU/custom rect before live geometry fallback. | Keep. Current log shows saved/live rect correctness, not overlay-first divergence. |
| Edit shell creation | `rendering/custom_layout_manager.py::_create_shell_state()` | Uses the display manager's screen for `current_screen`, but reads the widget settings monitor into `current_monitor_value`. | Current highest-confidence root-cause seam. This can birth a shell on display 2 carrying monitor 1 authority. |
| Cross-display shell drag | `rendering/custom_layout_manager.py::_resolve_shell_global_rect()` | Updates `current_screen` and `current_screen_signature` when transfer is allowed. | Needs proof that `current_monitor_value` is updated in the same authority step instead of waiting for save-time inference. |
| Corner/scroll resize | `rendering/custom_layout_manager.py::_resolve_resize_drag_rect_on_fixed_screen()` | Keeps resize on the current screen and updates screen/signature. | Must preserve the correct current monitor when resizing after a move/transfer. |
| Save-time repair | `rendering/custom_layout_manager.py::_repair_visualizer_save_screen_if_needed()` | Infers actual screen/monitor from shell rect overlap and logs loud fallback if state metadata disagrees. | Safety net only. A clean edit session should not hit this in ordinary operation. |
| Media-shell recovery | `rendering/custom_layout_manager.py::_reset_visualizer_from_media_shell()` | Creates/restores a visualizer edit shell without saving settings or leaving edit mode. | Valid recovery path, but it must not become the explanation for ordinary save-route poison. |

### Required proof before code changes

- [x] Document whether the shell's `current_monitor_value` should always represent physical owner display once edit mode starts, while `source_monitor_value` preserves reset-to-source semantics.
- [x] Prove whether cross-display drag updates monitor authority at transfer time or only indirectly during save.
- [x] Prove resize after transfer cannot reintroduce stale monitor authority.
- [x] Prove media-shell recovery assigns current screen and monitor from the recovery shell's physical display, not from stale widget settings.
- [x] Preserve save-time repair as a loud fallback bar, but add a normal-path bar that fails when a shell starts on display 2 with monitor 1 authority.

### First 2026-06-28 root-cause cut landed

- `rendering/custom_layout_manager.py::_create_shell_state()` now splits visualizer edit-session route state:
  - `source_monitor_value` keeps the settings/authored source route for reset and comparison
  - `current_monitor_value` follows the shell's physical display owner immediately
- `rendering/custom_layout_manager.py::_resolve_shell_global_rect()` and `_resolve_resize_drag_rect_on_fixed_screen()` now update current monitor authority when current screen authority changes.
- The `ALL` lock for ordinary duplicate widgets stays intact:
  - non-visualizer `ALL` widgets keep `ALL` current authority, so cross-display transfer remains blocked
  - visualizer `ALL -> Custom` promotion still receives a numbered current owner when saved as a single custom visualizer
- The save-time repair fallback remains loud and tested, but it is no longer the normal path for the modeled visualizer-current-display mismatch.

### Validation for this cut

- `tests/test_custom_layout_manager.py::test_custom_layout_manager_initializes_visualizer_current_route_from_shell_display` fails on the old poisoned normal path and passes after the route split.
- `tests/test_custom_layout_manager.py::test_custom_layout_manager_repairs_visualizer_monitor_from_rect_owner_on_save` keeps the loud fallback safety net for deliberately poisoned state.
- Full custom-layout suite passes after the cut: `90 passed`.
- Startup/reconcile visualizer owner tests and widget-manager committed-rect tests were rerun as guard coverage.

## Confirmed Evidence

### Geometry log evidence

`logs/screensaver_geometry.log` repeatedly shows startup replay beginning from poisoned live geometry:

- `05:18:16` `widget=spotify_visualizer phase=replay_start local=(696,840,840,560) global=(0,0,100,400)`
- `05:18:16` `phase=replay_after_payload local=(0,0,840,560) global=(0,0,840,560)`
- `05:18:16` `phase=replay_final local=(696,840,840,560) global=(696,840,840,560)`

The same pattern appears again at:

- `05:33:53`
- `05:34:30`

### Visualizer log evidence

`logs/screensaver_spotify_vis.log` still shows startup ownership churn around the same family:

- `Card height set: 88 -> 400 (mode=spectrum)`
- `startup_create`
- `settings_refresh`
- `FIRST_FRAME_PRIMER problems=overlay_generation_stale,overlay_activation_stale`

The newer duplicate-startup failure also produced explicit double-birth evidence:

- `2026-06-14 22:27:14` `Created visualizer widget (screen=0, ... monitor=2, custom_routing=True)`
- `2026-06-14 22:27:14` `Created visualizer widget (screen=1, ... monitor=2, custom_routing=True)`
- both are preceded by the loud fallback warning claiming the requested CUSTOM monitor `1` is not participating

That combination proved the old fallback was firing too early during sequential multi-display startup:

- screen 0 treated screen 1 as absent because screen 1 was not fully ready yet
- then screen 1 finished startup and created the real local visualizer anyway
- result: a self-reforming duplicate visualizer instead of one authoritative owner

### User-level evidence

- the user did not change preset card widths/heights to create these shapes
- the visualizer alone still deforms into shapes that should be impossible under strict uniform custom resizing
- replay parity improvements already landed, which means the remaining family is broader than the older shrink/parity bug

## What Is Already Fixed

These are real wins and should not be thrown away casually:

- committed visualizer CUSTOM rects are persisted as explicit `width` / `height`
- replay now primes `_custom_layout_local_rect` and reasserts the committed rect
- widget-manager visualizer positioning prefers the committed custom rect path when available
- GL overlay rect resolution also now prefers the committed custom/GPU target rect

These changes narrowed the bug, but they did not close it.

## Newly Landed Milestone

Two production guardrails are now in place and covered by automation:

1. creator-time CUSTOM rect priming
   - `rendering/spotify_widget_creators.py` now attaches the committed CUSTOM rect before `startup_create`
   - this keeps startup activation, startup staging, and overlay prewarm from freelancing off the bogus default shell when the saved rect already exists
2. widget-local CUSTOM outer-geometry authority
   - `widgets/spotify_visualizer_widget.py` now resolves the runtime CUSTOM rect first and rejects foreign outer `setGeometry(...)` writes while committed CUSTOM authority is active
   - this is intentionally narrow:
     - visualizer only
     - CUSTOM only
     - no steady-state correction loop
3. participating-display spawn ownership
   - creator-time local spawn and remote CUSTOM reconcile now choose a display owner from the active participating display set
   - if the requested CUSTOM monitor is not currently participating in the compositor/runtime set, the visualizer falls back to a participating display instance instead of spawning into unseen/off-screen territory
   - this is intentionally not tied to media ownership; it is chosen from runtime display participation
4. unique saved-rect reuse during topology fallback
   - creator-time CUSTOM priming no longer assumes the participating fallback display can always match the original saved screen bucket
   - when there is exactly one saved visualizer rect in the custom-layout map, startup now treats that rect as the sole authoritative candidate instead of birthing a default square because the requested monitor bucket is missing
   - the same topology-fallback truth is now covered at remote CUSTOM reconcile as well, so secondary-stage spawn fallback does not silently lose the sole saved rect
   - the same unique-rect fallback is now also covered for active-target signature drift:
     - the requested CUSTOM monitor may still be participating
     - but the live screen signature can still differ from the saved bucket after topology/display identity churn
     - startup and remote reconcile must still recover the sole authoritative visualizer rect in that case instead of birthing fallback square geometry
   - this stays narrow on purpose:
   - visualizer only
   - CUSTOM only
   - only when the saved rect is unique, so normal per-screen routing is not weakened
5. pending-startup display deferral instead of premature fallback
   - `rendering/spotify_display_participation.py` now distinguishes:
     - truly absent / non-participating requested displays
     - requested displays that already exist and have a live screen but are still pending full startup participation
   - during that pending-startup window, owner selection now defers spawn to the requested display instance instead of birthing a temporary fallback visualizer on another screen
   - this is covered by a startup-shaped regression bar that fails if sequential multi-display startup can create a fallback visualizer first and the real requested-display visualizer second

What this milestone means:

- the visualizer no longer has to wait for replay before a saved CUSTOM rect can become startup truth
- later outer-geometry pressure can no longer freely deform the card once committed CUSTOM authority already exists
- spawn ownership no longer trusts a dead/non-participating CUSTOM monitor target
- spawn ownership also no longer mistakes a live-but-pending requested display for a missing one during sequential startup
- topology fallback no longer discards the only saved visualizer rect just because the active owner display changed
- remaining risk is now narrower:
  - display recreation
  - display swap / remote-instance handoff
  - any still-misaligned overlay-first-visible path in those flows

## Current Hold State

This audit is closed to watchlist. Geometry work should not re-enter the active queue unless fresh logs show the save-route repair, duplicate-owner fallback, top-left/narrow shape, square-creep, or replay/runtime divergence again.

### Latest validation note: 2026-06-27

The newest extensive edit-mode/reset run supports the current Reset Visualizer
contract:

- `recover_visualizer_edit_rect` warnings are expected and intentionally loud
  when the edit shell creates a usable visualizer rect without saving settings,
  forcing a runtime reload, or leaving edit mode
- latest visualizer creation logs show one visualizer owner at a time during
  the inspected route changes, not the older simultaneous duplicate-owner
  shape
- no new evidence in this run requires reopening the visualizer CUSTOM shape
  family

Do not downgrade those recovery warnings. They are operator-visible proof that
the safety path activated. However, a fallback warning during an ordinary edit
save is not a clean success. It is evidence that the normal route-authority
chain still has stale state upstream.

Why this is a good stopping point:

- creator/startup/reconcile/topology fallback bars are materially stronger than before
- the currently landed protections are narrow and one-shot rather than steady-state correction loops
- pushing deeper right now risks turning a mostly-contained geometry family into churn through extra rescue layers

What is now policy, not just preference:

- fallbacks are not a success state
- if a geometry/display fallback is forced, it must log loudly at `WARNING` or higher through the existing diagnostics family
- silent fallback activation is not acceptable because it hides whether root cause is really solved

What is intentionally *not* landed:

- no broad obscene-shape rescue loop
- no per-frame geometry correction
- no generic overlay-level fallback masking

Low / deferred follow-up only if the issue returns:

1. Add a true display-recreation first-visible bar that proves whether a recreated fullscreen display can still birth the visualizer into fallback geometry before the committed rect is visible.
2. Add a true display-swap / handoff bar beyond the current topology/setup-chain cases if runtime logs show a new failure class.
3. Only if new evidence appears, define a one-shot obscene-shape plausibility detector and repair path. That work should stay:
   - visualizer-only
   - CUSTOM-only
   - startup/rebuild-triggered only
   - loud in logs when it activates

## Reopened 2026-06-20 Route-Recovery Evidence

This family is no longer only "post-replay geometry writers."
The latest logs add a narrower but more destructive seam:

- `logs/screensaver_spotify_vis.log`
  - `17:27:06` `WARNING [SPOTIFY_VIS] Restored invalid Custom+ALL visualizer route back to authored layout`
  - the same rebuild immediately continues with:
    - `Created visualizer widget (screen=1, ... monitor=2, custom_routing=True)`
- `logs/screensaver_geometry.log`
  - the same run still shows the committed visualizer CUSTOM rect replaying as:
    - `widget=spotify_visualizer phase=replay_final ... global=(732,900,750,500)`

### Why this matters

- the saved rect is not the lie
- the recreate-time route validator is
- the warning claims an authored-route recovery happened
- the next creator log proves the visualizer is still in `Custom` anyway

That means the old recovery path is not merely noisy. It is allowed to mutate
state during a valid CUSTOM recreate even when the committed visualizer rect is
still authoritative and healthy.

### Updated root-cause reading

The reopened top-left family now has an extra upstream trigger:

1. a recreate-time route derivation can transiently read the visualizer as `Custom + ALL`
2. the creator then calls the broad authored restore helper
3. that helper can report success for reasons broader than "visualizer truly left Custom"
4. the creator logs a false authored recovery and persists the mutated widgets map
5. later startup/replay/staging paths now have a dirtied route/rect world to work from

### Updated safest fix direction

- treat creator-time route repair as its own seam, separate from overlay geometry stabilization
- recover a missing visualizer monitor only from matching committed custom-layout screen-bucket evidence
- never let creator-time recovery claim success unless the visualizer actually exits `Custom`
- do not clear saved visualizer layout entries just because a transient route read looked like `ALL`

## Issue Inventory

### Issue 1. Replay success is not final runtime truth

- **Severity:** Critical
- **Why it matters:** the system can claim geometry success while the user still sees a wrong live shape
- **Likely class:** later geometry writers or stale authority re-entry after replay

### Issue 2. Widget rect and GL overlay rect can still diverge

- **Severity:** Critical
- **Why it matters:** the saved card can be correct while the rendered visualizer surface still uses a stale or wrong rect
- **Likely class:** separate geometry consumers reading different snapshots at different times

### Issue 3. Startup staging still births the visualizer at stale geometry

- **Severity:** High
- **Why it matters:** stale startup geometry can seed later bad decisions or leave the first visible state poisoned
- **Likely class:** startup create / settings refresh / secondary-stage ordering

### Issue 4. Preferred-height and mode-owned live sizing remain active seams

- **Severity:** High
- **Why it matters:** even if deferral during active CUSTOM is correct, any re-entry after CUSTOM authority can silently mutate the card again
- **Likely class:** mode-owned `resize(self.width(), h)` behavior or similar geometry writes outside the committed rect contract

### Issue 5. Existing automation still proves local truths better than end-to-end truth

- **Severity:** High
- **Why it matters:** the branch can look safe in tests while still shipping an impossible runtime shape
- **Likely class:** bars focus on replay/prewarm correctness, not runtime-shape persistence

## Geometry Authority Map

### Authority A. CUSTOM replay

- **Primary file:** `rendering/custom_layout_manager.py`
- **Current role:** writes `_custom_layout_local_rect`, primes geometry, applies payload, calls `_update_position()`, reasserts committed rect
- **Risk:** replay may no longer be the last writer

### Authority B. Widget-local visualizer geometry

- **Primary file:** `widgets/spotify_visualizer_widget.py`
- **Current role:** active custom rect checks, custom min/max constraint lock, GPU target resolution, preferred-height application
- **Risk:** mode-owned height application or later widget-local geometry writers can re-enter after replay

### Authority C. Runtime positioning

- **Primary file:** `rendering/widget_manager.py`
- **Current role:** chooses custom branch vs authored media-relative branch
- **Risk:** stale state or later calls can route through the wrong branch or recompute geometry after replay

### Authority D. GL overlay transport

- **Primary file:** `rendering/display_image_ops.py`
- **Current role:** resolves overlay rect for prewarm/push and owns overlay creation/sync
- **Risk:** overlay rect can still come from a different snapshot than the card rect

### Authority E. Generic overlay helpers

- **Primary file:** `transitions/overlay_manager.py`
- **Current role:** generic full-widget geometry helpers
- **Risk:** visualizer-owned GL surfaces may still be touched by generic overlay assumptions that were safe for fullscreen transitions but unsafe here

### Authority F. Startup / first-frame / activation staging

- **Primary files:** `startup_staging.py`, `mode_transition.py`, `spotify_bars_gl_overlay.py`, `spotify_visualizer_widget.py`
- **Current role:** controls cold startup, activation readiness, first overlay push, reveal timing
- **Risk:** staged ownership can leave stale geometry alive or let it re-enter before stable runtime handoff

## Root-Cause Hypotheses Ranked

### 1. Post-replay geometry writers still exist

- **Confidence:** Highest
- **Reason:** replay now lands the right rect more often, but runtime can still drift later
- **Best correction:** identify and eliminate or redirect all later visualizer geometry writes so the committed custom rect remains authoritative

### 2. Widget and overlay are resolving geometry from different snapshots

- **Confidence:** High
- **Reason:** the visualizer has separate card and GL overlay surfaces with separate life cycles
- **Best correction:** collapse both onto one authoritative committed-rect source once CUSTOM authority exists

### 3. Startup sequencing and recreated-instance handoff can still expose stale geometry long enough to poison runtime

- **Confidence:** High
- **Reason:** repeated `global=(0,0,100,400)` replay-start evidence plus the remaining user reports around recreated / swapped instances
- **Best correction:** stop recreated-instance startup geometry from ever being visible/consumed after the custom rect is known

### 4. Preferred-height or mode-owned live sizing can re-enter after CUSTOM authority

- **Confidence:** Medium-high
- **Reason:** `_apply_preferred_height()` is still a live geometry seam outside CUSTOM windows
- **Best correction:** prove this seam cannot run once a committed custom rect is active, or move that authority fully out of the runtime path when custom is present

### 5. Generic overlay helper contamination

- **Confidence:** Medium
- **Reason:** there are generic `setGeometry(0, 0, widget.width(), widget.height())` helpers in overlay infrastructure
- **Best correction:** explicitly prove the visualizer path is isolated from generic fullscreen overlay geometry contracts

## Best Correction Strategy

The safest fix is not “keep correcting bad shapes forever.”

The safest fix is:

1. strengthen automation so the true runtime-shape failure is red
2. identify every post-replay geometry authority touching the visualizer
3. collapse visualizer geometry onto one committed CUSTOM rect authority for both:
   - widget outer rect
   - GL overlay target rect
4. add a very narrow obscene-shape detector only as a one-shot recovery net if runtime still needs it afterward

### Why this is the best approach

- it targets the architecture smell instead of papering over symptoms
- it minimizes risk to other widgets because it stays visualizer-owned and CUSTOM-owned
- it reduces future drift because one authority is easier to validate than several loosely coordinated ones
- it keeps performance safe because it avoids per-frame fighting

## Does This Endanger Other Features?

### If done correctly

Risk to unrelated features should be low because the correction can stay scoped to:

- the visualizer only
- CUSTOM geometry only
- startup / replay / overlay / positioning seams only

### What could be endangered if done poorly

- media-follow authored placement when not in CUSTOM
- mode-switch startup/reveal timing
- first-frame/overlay activation sequencing
- display-swap or settings-refresh rebuild behavior
- visualizer card/overlay parity if only one side is corrected

### Risk verdict

This work is worth doing, but only if we keep it narrowly scoped and do not introduce:

- per-frame geometry correction
- global overlay hacks
- new fallback paths that let bad runtime state masquerade as success

## Correction Methods

### Method A. Strengthen the automation bar first

- **Priority:** P0
- **Why first:** without this, every later “fix” can regress back into replay-green/runtime-wrong lies
- **Target:** make the real failure shape fail decisively before asking for more runtime verification

### Method B. Audit and remove post-replay geometry writers

- **Priority:** P0
- **Why second:** this is the most likely true root-cause class
- **Target:** ensure no later writer can mutate width/height/shape after committed custom replay wins

### Method C. Collapse widget rect and overlay rect onto one committed source

- **Priority:** P1
- **Why third:** even if replay is correct, dual authorities can still disagree later
- **Target:** card rect and GL rect must stay sourced from the same committed geometry truth

### Method D. Add a narrow obscene-shape safety net

- **Priority:** P2
- **Why last:** this is mitigation, not the primary fix
- **Target:** detect impossible shapes cheaply and trigger one repair/rebuild/correction-save route without steady-state churn

## Risks

### Risk 1. Breaking non-CUSTOM authored follow-media behavior

- **Containment:** keep authored branch and CUSTOM branch explicitly separate in tests and implementation

### Risk 2. Reopening first-frame or activation churn

- **Containment:** all geometry changes must be validated against startup/first-frame bars, not just steady-state replay

### Risk 3. Fixing card rect but not overlay rect

- **Containment:** bars must compare widget and overlay geometry truth together

### Risk 4. Reintroducing manual/fallback masking

- **Containment:** no silent fallback that merely hides bad state; if recovery exists it must be explicit, narrow, and observable

### Risk 5. Over-centralizing into a new brittle mega-helper

- **Containment:** collapse authority, but keep ownership explicit by seam instead of creating a vague do-everything helper

## Guardrails

- Do not widen the fix into generic overlay code unless logs prove the generic seam is actually culpable.
- Do not fight geometry every frame.
- Do not allow a fix that only makes logs look cleaner while runtime can still deform.
- Do not reopen shared audio/reactivity work during this geometry pass.
- Do not let visualizer mode-owned preferred height become a second authority after custom replay.
- Do not add legacy/fallback compatibility aliases to geometry ownership if they hide the real writer.
- Any new logging belongs behind `--geo` or the relevant visualizer diagnostics family.

## Ordered Work Plan

### Phase 1. Bar Hardening

- add runtime-shaped bars for:
  - replay-green/runtime-wrong startup
  - aspect-ratio drift / unauthorized width drift
  - display swap / rebuild / mode-switch persistence
  - widget-rect vs overlay-rect disagreement

### Phase 2. Geometry Writer Audit

- trace every visualizer geometry writer from current tree:
  - startup create
  - settings refresh
  - secondary-stage activation
  - preferred-height apply
  - widget-manager positioning
  - overlay prewarm
  - first overlay push
  - overlay sync
  - generic overlay geometry helpers

### Phase 3. Authority Collapse

- make committed custom rect the sole geometry source for:
  - widget outer rect
  - overlay target rect
- prevent later writers from changing the shape while CUSTOM authority is active

### Phase 4. Safety Net

- only if still justified after Phases 1-3
- add impossible-shape plausibility check
- trigger one-shot repair/rebuild/correction-save only

## Actionable Checklist

### Phase 1. Bar Hardening

- [x] Add a startup bar that fails when the visualizer ever settles into a live rect materially different from committed custom rect after replay.
- [x] Add an aspect-ratio drift bar that fails if repeated save/rebuild cycles introduce unauthorized width drift.
- [x] Add a top-left poisoned-shape bar that fails if the visualizer can remain at a narrow startup-origin block.
- [x] Add a widget-vs-overlay parity bar that fails if overlay target rect diverges from widget outer rect under CUSTOM authority.
- [x] Add a startup-finalize settle bar that forces post-replay square/startup pressure and still requires `_finalize_widget_startup(...)` to settle both widget and overlay back onto the committed custom rect.
- [x] Add a live settings-refresh bar that proves committed CUSTOM rect + stale overlay still re-settle onto the committed rect during canonical refresh.
- [x] Add a creator-time CUSTOM startup bar that fails if `startup_create` expands the visualizer to authored preferred height before committed replay attaches the saved rect.
- [x] Add a creator-time CUSTOM birth bar that fails if startup is born at a bogus default rect instead of the saved rect when a committed CUSTOM entry already exists.
- [x] Add a creator-time CUSTOM pressure bar that fails if post-create outer-geometry pressure can still push the visualizer away from its committed rect.
- [x] Add a remote CUSTOM reconcile bar that fails if a square fallback rect is accepted after the committed rect has already been attached.
- [x] Keep existing replay parity bars green without softening thresholds.

### Phase 2. Geometry Writer Audit

- [x] Inventory all direct visualizer `setGeometry`, `resize`, min/max-size, and overlay-rect writers from the current tree.
- [x] Mark each inventoried writer as authoritative, conditional-authoritative, or non-authoritative/removable in the audit table.
- [x] Prove whether `_apply_preferred_height()` can re-enter after committed custom rect is active.
- [x] Prove whether generic overlay-manager geometry helpers can touch visualizer-owned overlay state.
- [x] Document the exact last-authority chain for:
  - cold startup
  - settings refresh
  - display recreation
  - mode switch
  - display swap

## Phase 2 Findings

### Geometry Writer Inventory

| Seam | File / Function | Current role | Classification | Risk / Priority | Notes |
|---|---|---|---|---|---|
| CUSTOM replay prime + final reassert | `rendering/custom_layout_manager.py::_apply_entry_to_widget()` | Writes `_custom_layout_local_rect`, primes `widget.setGeometry(local_rect)`, calls payload apply, calls `_update_position()`, reasserts `widget.setGeometry(local_rect)`, then syncs overlay | Authoritative | P0 keep | This is the current intended source of truth during replay. If runtime still deforms later, this seam is likely being overridden rather than being wrong by itself. |
| Runtime CUSTOM visualizer positioning | `rendering/widget_manager.py::position_spotify_visualizer()` custom branch | Applies constraints, clamps through `resolve_custom_card_rect(...)`, sets widget rect, syncs overlay | Conditional-authoritative | P0 keep / inspect callers | This is correct while CUSTOM is active, but it becomes dangerous if later callers route through it with stale or mutated inputs. |
| Runtime authored visualizer positioning | `rendering/widget_manager.py::position_spotify_visualizer()` authored branch | Applies media-relative authored rect and syncs overlay | Conditional-authoritative | P0 guard against CUSTOM bleed | This branch is valid only outside CUSTOM. A stale route into this branch after CUSTOM replay would directly reintroduce user-visible drift. |
| Widget-local preferred-height writer | `widgets/spotify_visualizer_widget.py::_apply_preferred_height()` | Mutates min/max height and calls `resize(self.width(), h)` or `resize(self.width(), base)` | Conditional-authoritative | P0 first dangerous writer | It correctly defers when CUSTOM is active, but it remains one of the strongest candidates for later geometry mutation if CUSTOM authority is absent, stale, or temporarily invisible. |
| Deferred mode-transition geometry relay | `widgets/spotify_visualizer/mode_transition.py::apply_pending_mode_transition_layout()` | Calls `_apply_preferred_height()` and `_request_reposition()` after mode transition | Conditional-authoritative | P0 high-risk relay | This is not a standalone geometry policy, but it can still reactivate dangerous writers later in runtime. Existing bars now prove repeated square-drift recovery here, but the seam remains important. |
| Widget reposition request relay | `widgets/spotify_visualizer_widget.py::_request_reposition()` | Routes to `WidgetManager.position_spotify_visualizer(...)` | Conditional-authoritative | P1 relay | Safe if route state is correct; unsafe if CUSTOM authority is stale and request lands in the wrong branch. |
| Overlay rect resolution | `rendering/display_image_ops.py::_resolve_spotify_visualizer_overlay_rect()` | Resolves overlay target rect from committed custom rect or live geometry fallback | Authoritative for overlay | P0 keep / unify | This should become the same committed truth source as the widget rect under CUSTOM authority. |
| Overlay rect sync | `rendering/display_image_ops.py::sync_spotify_visualizer_overlay_geometry()` | Realigns overlay to resolved target rect | Authoritative for overlay | P0 keep | Good seam. New bar now proves it prefers committed custom rect over stale widget and stale overlay geometry. |
| Overlay state push geometry | `widgets/spotify_bars_gl_overlay.py::set_state()` | Calls `self.setGeometry(rect)` when incoming rect differs | Overlay consumer | P1 keep / validate inputs | Should never invent geometry; must remain a downstream consumer of the committed rect source. |
| Overlay prewarm geometry | `widgets/spotify_bars_gl_overlay.py::prewarm_context()` | Calls `self.setGeometry(rect)` during prewarm | Overlay consumer | P1 keep / validate inputs | Same rule as `set_state()`: it must only consume authoritative rects, not freelance geometry. |
| Generic transition overlay geometry | `transitions/overlay_manager.py::set_overlay_geometry()` and `rendering/display_setup.py::ensure_overlay_stack()` | Full-widget overlay geometry for transition overlays | Non-authoritative for visualizer bars overlay | Lower risk than suspected | `GL_OVERLAY_KEYS` does not include `_spotify_bars_overlay`, so this generic transition overlay family is currently not a direct geometry writer for the visualizer bars overlay. Keep in view, but do not attack this seam first. |
| Create-time canonical refresh replay | `rendering/spotify_widget_creators.py::create_spotify_visualizer_widget()` -> `WidgetManager._refresh_spotify_visualizer_config(...)` | Re-enters the canonical settings-refresh path immediately after `startup_create` | Conditional-authoritative | P0 startup risk | Safe for authored startup parity, but it was a duplicate pre-replay pass for CUSTOM startup and could fire before `_custom_layout_local_rect` existed. |
| Startup-create manager visibility seam | `rendering/spotify_widget_creators.py::create_spotify_visualizer_widget()` -> `SpotifyVisualizerWidget.apply_resolved_activation_payload(...)` | Applies startup mode/card-height work before ordinary registration/bind is complete | Conditional-authoritative | P0 startup truth seam | If the widget cannot see the real `WidgetManager` yet, `_is_custom_layout_route_selected()` lies during `startup_create`, so `_apply_preferred_height()` can freelance into authored growth before committed replay ever attaches the saved rect. |

### Current Writer Classification Verdict

- The highest-risk writer family is still the widget-owned runtime height/position relay:
  - `_apply_preferred_height()`
  - `apply_pending_mode_transition_layout()`
  - `_request_reposition()`
  - `WidgetManager.position_spotify_visualizer(...)`
- The replay seam itself looks more like the victim than the culprit.
- The overlay path is now much less mysterious:
  - it has its own authority chain
  - but the generic transition-overlay helpers are probably not the direct cause because `_spotify_bars_overlay` is outside `GL_OVERLAY_KEYS`

### Preliminary Last-Authority Chains

#### Cold startup with CUSTOM visualizer

1. visualizer is constructed with ordinary startup/default geometry pressure
2. startup create can still apply preferred-height behavior if the widget cannot yet see truthful CUSTOM-route state through `WidgetManager`
3. CUSTOM replay writes `_custom_layout_local_rect` and reasserts the committed rect
4. runtime positioning may reapply the CUSTOM rect through `WidgetManager`
5. overlay prewarm / sync / first push resolve the overlay rect separately
6. current bars now also prove `_finalize_widget_startup(...)` can survive a forced post-replay square/startup-pressure shove and still settle back onto the committed rect by the end of the startup finalize sequence

#### Mode transition while CUSTOM visualizer is active

1. `apply_pending_mode_transition_layout()` fires after transition
2. `_apply_preferred_height()` runs, but current tests prove it defers while CUSTOM authority is active
3. `_request_reposition()` routes back through `WidgetManager.position_spotify_visualizer(...)`
4. current first-wave bars prove repeated square-drift recovery and overlay parity through this path

#### Settings refresh while CUSTOM visualizer is active

1. `WidgetManager._refresh_spotify_visualizer_config(...)` reapplies the canonical activation payload
2. current tests prove the live committed rect survives that refresh
3. current tests also prove the stale overlay is re-synced onto the committed rect during that refresh-owned reposition path

### What The New Bars Narrowed

- Ordinary startup-finalize settle is now covered and currently green.
- Ordinary canonical settings refresh under active CUSTOM authority is now covered and currently green.
- Creator-time CUSTOM startup now also has a dedicated guard: if `startup_create` tries to expand the visualizer to authored preferred height before committed replay, the bar fails.
- Creator-time CUSTOM birth now has a stronger guard too: if a saved rect exists, the visualizer must be born at that rect rather than the bogus default shell.
- Creator-time CUSTOM pressure is now explicit: once the committed rect is attached, later outer `setGeometry(...)` pressure is not allowed to deform the card.
- Remote CUSTOM reconcile is narrower too: once the committed rect is attached, a square fallback rect is no longer accepted as a valid startup shape for the widget itself.
- Requested-monitor participation is now explicit too: the visualizer no longer tries to spawn against a non-participating CUSTOM monitor target when choosing its runtime owner.
- That means the remaining highest-risk runtime family is no longer "generic startup" or "ordinary settings refresh" in isolation.
- The remaining search space is narrower:
  - true display recreation / display swap sequencing
  - first visible runtime churn after those flows
  - any seam where committed CUSTOM authority is temporarily absent or read from the wrong display/widget instance

### What This Means For The Next Runtime Cut

- The first production change should probably not touch replay again.
- The first production change should probably tighten the widget-owned relay path so:
  - committed CUSTOM authority is impossible to “temporarily lose”
  - authored preferred-height / authored positioning cannot reassert shape once a committed CUSTOM rect exists

### First Runtime Cut Landed

- Widget-local preferred-height now defers not only when the committed CUSTOM rect is active, but also when the visualizer is already routed through the `Custom` slot and the rect is still pending attachment.
- `WidgetManager.position_spotify_visualizer(...)` now refuses to fall back into the authored media-relative branch when the settings route already says `Custom` but `_custom_layout_local_rect` is not attached yet.
- This is intentionally narrow:
  - it does not change authored follow-media behavior outside CUSTOM
  - it does not introduce per-frame correction
  - it only blocks temporary authored fallback while committed CUSTOM authority is pending

### Second Runtime Cut Landed

- `rendering/spotify_widget_creators.py::create_spotify_visualizer_widget()` no longer immediately re-enters `WidgetManager._refresh_spotify_visualizer_config(...)` when the visualizer is already routed through `Custom`.
- Authored startup still keeps the old parity rule:
  - `startup_create`
  - then immediate canonical refresh reuse
- CUSTOM startup now stays on the narrower path:
  - `startup_create`
  - wait for committed CUSTOM replay to attach `_custom_layout_local_rect`
  - then let replay/positioning own geometry instead of taking an extra pre-replay settings-refresh lap
- Why this matters:
  - it removes one more startup-only geometry authority leak without changing non-CUSTOM follow-media behavior
  - it keeps the earlier preferred-height/position guards from having to absorb a duplicate create-time refresh pass that should not have run in CUSTOM at all

### Third Runtime Cut Landed

- `rendering/spotify_widget_creators.py::create_spotify_visualizer_widget()` now seeds the real `WidgetManager` onto the visualizer before `startup_create` activation work runs.
- Why this matters:
  - the visualizer's own `_is_custom_layout_route_selected()` check depends on `WidgetManager -> SettingsManager` truth
  - before this cut, `startup_create` could run while that seam was still invisible, so `_apply_preferred_height()` treated a CUSTOM-routed startup as if it were ordinary authored startup and expanded the card to the authored preferred height
  - this was a real architectural lie, not just a missing replay: the route-aware guard existed, but startup was running it before the route owner was attached
- Scope:
  - no new per-frame correction
  - no new fallback path
  - no change to non-CUSTOM authored startup beyond making the manager visible slightly earlier inside the existing creator seam

### Fourth Runtime Cut Landed

- `rendering/spotify_widget_creators.py::create_spotify_visualizer_widget()` now primes the committed CUSTOM rect before `startup_create` whenever a saved CUSTOM visualizer entry already exists for the live display.
- `widgets/spotify_visualizer_widget.py` now resolves the runtime CUSTOM rect first and rejects foreign outer `setGeometry(...)` writes while committed CUSTOM authority is active.
- Why this matters:
  - startup activation, startup staging, and overlay prewarm no longer have to infer geometry from the bogus default shell when committed CUSTOM truth is already known
  - later widget-local outer-geometry pressure can no longer silently push the visualizer into the recurring top-left / square family once committed CUSTOM authority is already active
- Scope:
  - visualizer only
  - CUSTOM only
  - still no per-frame correction
  - still no generic overlay hack
  - authored follow-media behavior outside CUSTOM remains untouched

### Phase 3. Authority Collapse

- [x] Ensure one committed custom rect source feeds widget outer geometry while CUSTOM is active.
- [x] Prevent later widget-local outer `setGeometry(...)` writers from mutating the visualizer shape once CUSTOM authority exists.
- [ ] Finish proving first-visible overlay truth for recreated / swapped display instances.
- [ ] Preserve authored media-relative placement only outside CUSTOM.
- [ ] Preserve first-frame reveal correctness while collapsing geometry authority.

### Phase 4. Safety Net

- [ ] Define obscene-shape plausibility thresholds relative to committed custom rect.
- [ ] Ensure the detector is one-shot and not per-frame corrective churn.
- [ ] Ensure recovery path is observable in logs and does not silently hide architectural regressions.

## Reopen Criteria

Reopen this audit if any of these return:

- ordinary edit/save emits `[CUSTOM_LAYOUT][FALLBACK] Repaired spotify_visualizer CUSTOM save route...`
- startup, rebuild, display swap, or mode switch produces a duplicate visualizer owner
- widget outer rect and overlay target rect diverge under CUSTOM authority
- unauthorized width/aspect drift returns
- runtime settles into the narrow top-left or square-creep failure shape
- a recovery path becomes the primary way correctness is achieved instead of a loud safety net

## Recommendation

Yes, solving this by collapsing geometry authority is the best route, and if it is done with the scope above it should not endanger the rest of the application materially.

The dangerous approach would be repeated correction, broad fallbacks, or generic overlay hacks. The safe approach is:

- stronger bars first
- explicit writer audit second
- authority collapse third
- one-shot safety net last
