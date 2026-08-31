# Post-Cutover Operator Observation Ledger — 2026-08-30

Applies to: H post-cutover runtime-reality correction and J final physical/visual acceptance.

This ledger is mandatory phase-close input. Narrow implementation prompts never imply that unmentioned rows are done.

## Baseline / parity rule

**J is Parity+.** Historical successful presentation is a quality/behavior floor where better, not a ceiling and never an implementation source. Preferred broad visual references are the 4.7.2/4.7.0 release screenshots and `15099d3`. **For visualizer reactivity specifically, the user-supplied `3fe5df6` tree is the known-good pre-Qt-Quick behavioral oracle.** Current operator observations outrank historical inference, and current Quick ownership remains implementation authority. Never restore/wrap/adapt the deleted QWidget/QRhi/GL presenter.

Legend:

- `[ ]` unresolved;
- `[x]` closed/passed or positive preservation target;
- **H** deterministic functional/runtime work;
- **J** physical visual/interaction/performance work;
- **H/J** instrument first, then classify.

## Lifecycle / recreation / terminal exit

| State | ID | Phase | Observation | Durable handling / close condition |
|---|---|---|---|---|
| [x] | O-001 | H closed subgate | Dual-display Settings recreation used to hang. | `2220782d` + physical pass: 3 Settings cycles at `af8896b5`, no watchdog dump. Preserve. |
| [x] | O-002 | H closed subgate | Dual-display CUSTOM Save/Continue recreation used to hang. | Physical pass: 5 CUSTOM cycles in same process, no watchdog dump. Preserve. |
| [x] | O-003 | preservation | CUSTOM saves correctly. | Preserve save semantics. |
| [x] | O-004 | H historical | Hang-induced lingering process/debug-session symptom did not recur because no reconstruction hang occurred. | Reopen only if replacement hang returns. Terminal crash is tracked separately in O-041. |
| [x] | O-005 | contrast | One-display MC recreation works. | Keep as a control; dual-display remains required. |
| [ ] | O-006 | J | CUSTOM/Edit interaction is less smooth than pre-Quick. | J eyes-on smoothness after H. |
| [x] | O-041 | H closed | Former terminal Exit access violation / dangling `BackgroundRenderItem` slot. | Closed by terminal-purpose destruction barrier; later dual-display exits complete barrier before process shutdown and terminate naturally. Preserve. |
| [x] | O-042 | H closed | Former Clock QML null-model retirement storm. | Closed by retained-model lifetime repair; verify permanently through `screensaver_qml.log`. |
| [x] | O-043 | H closed | Former late Settings event-filter AttributeErrors. | Closed by teardown-safe helper guards; preserve focused regression. |

## Context menu / exit / focus

| State | ID | Phase | Observation | Durable handling / close condition |
|---|---|---|---|---|
| [x] | O-007 | preservation | Context menu now opens/stays open/functions. | Preserve `747e3140`. |
| [ ] | O-008 | **J high priority / H conditional** | First context-menu open on each display can cause two rapid black/stale-frame flashes; second open on the same display is clean. | Trace keeps the same retained image identity and initialized scene graph; old wallpaper was glimpsed without an image-publication event. Current bounded repair reasserts the retained background once on menu visible/hidden. **AWAITING PHYSICAL VALIDATION**; if first-open-only flash remains, inspect retained menu first-visible QSG resources/prewarm path. |
| [ ] | O-009 | J/perf / H conditional | Exit previously felt slow. Current clean run accepts/quiesces immediately, terminal Quick barrier completes in ~250 ms, then script-only pycache cleanup consumes about a second. | Remeasure visible window dismissal. If prompt, classify remaining tail as J/perf/developer housekeeping rather than lifecycle H. |
| [ ] | O-010 | **J high priority / H conditional** | Clicking/focusing A -> B -> A can black-flash the whole scene on every activation swap. | `[QUICK_SURFACE]` proves active image, visibility/exposure and scene graph remain stable. Current bounded repair requests one retained background redraw on `window_active_changed`. **AWAITING PHYSICAL VALIDATION**; persistent flash after that points to native QQuickWindow/Windows activation-buffer continuity. |
| [ ] | O-011 | **J high priority / H conditional** | Black flashes/flicker at startup/focus/context menu/transition edges. | Trace has split owners: startup can expose a native surface before real image publication; focus/menu keep stable semantic scene/image. Startup show is now gated on first real retained image; focus/menu get one event-driven background reassertion. **AWAITING PHYSICAL VALIDATION** before escalating to native window policy or menu prewarming. |
| [ ] | O-039 | J | Context submenus remain open indefinitely after pointer leaves. | Same-scene hover-path dismissal/switching with bounded crossing grace; preserve opening-click fix. |
| [ ] | O-040 | H/J validation | Startup formerly flashed diagnostic/test colour bands and still showed a black clear afterward. | Proof palette leak is repaired. Trace then proved native show could precede first real image. Current repair arms geometry/visible intent while hidden and commits show only after a real `PresentationImage` exists. **AWAITING PHYSICAL VALIDATION**; close when neither proof bands nor black first-show clear remains. |

## Visualizer

| State | ID | Phase | Observation | Durable handling / close condition |
|---|---|---|---|---|
| [x] | O-012 | H preservation | Visualizer retained delivery now visibly evolves. | Preserve `adcfd96d`. |
| [ ] | O-013 | **H** | Spectrum/Organ is both visually and reactively broken: dense segmented topology, full-height/saturated response, and selected preset semantics do not survive the migration. | H5b source repair now restores canonical render-mode topology, canonical unique-colour translation, the shared BeatEngine mirror/shape/notch/lane/profile/drop block, and the historical bar+peak `0.55` final transfer. Focused test execution + physical S0-S7 re-measure remain open. No global gain. |
| [ ] | O-014 | **H/J audit** | Earlier smoke said Oscilloscope/Sine/DevCurve broadly looked good, but Sine is now physically reported to have lost its historical paused idle motion. That invalidates the blanket closed row. | H5c compares all three against `3fe5df6`. Sine runtime still advances paused time/travel/shift, so trace snapshot/uniform/present before changing formulas. Oscilloscope/DevCurve remain comparative controls; close only after exact reactivity/idle transport is proven. |
| [ ] | O-015 | **H active (H5c)** | Bubble is barely reactive under real music: delayed visible start/stop and little contraction/expansion despite healthy ~90 Hz authored cadence/integration. Intentional idle-energy motion can therefore mask loss of live-source reactivity. | H5c source repair now restores Bubble's three stranded logical settings **and** the historical shared BeatEngine notch/shaping preset block. The latter is cross-mode: missing notches forced fixed `4/10` source splits instead of preset-normalized boundaries (about `14/31` for Bubble's 48-bar domain). Existing Quick bar-count/block-size/floor/sensitivity/dynamic-range/AGC/input-gain mapping was separately verified correct, including `AGC=0.0` = no AGC. Re-measure B0-B9, then use bounded `source_ready` diagnostics before any sensitivity/physics tuning. Preserve current good resizing. |
| [x] | O-016 | J preservation | Bubble partial/CUSTOM resize works quite well. | Preserve. |
| [ ] | O-044 | **H** | In CUSTOM, Visualizer does not activate when its committed display differs from Media's display. | H5a. Existing source contract already grants Visualizer own monitor in CUSTOM; repair persistence/admission/failover seam without creating another owner. |
| [ ] | O-052 | **H active (H5c / H4 boundary)** | Visualizer has a visible startup/stop response delay on Play/Pause. | Current route is direct Media model -> Quick visualizer owner -> unchanged BeatEngine, whose historical cold ramp is 1.5 s with 6 s capture keepalive. Capture one T0-T7 edge trace to distinguish late Media truth, cold-vs-warm source, source-readiness delay, authored publication delay and retained draw delay. Do not tune the historical ramp as a workaround. |

## Media — functional/settings

| State | ID | Phase | Observation | Durable handling / close condition |
|---|---|---|---|---|
| [x] | O-017 | H closed | Media artwork previously decoded but never displayed. | Closed: production model now uses the exact engine-registered provider and latest physical run visibly shows artwork. Preserve cross-layer provider identity. |
| [ ] | O-018 | **H** | Play/Pause does nothing. | H4 real GSMTC result telemetry/fix. |
| [x] | O-019 | preservation | Previous/Next work. | Preserve. |
| [ ] | O-020 | **H** | Seek/progress click does nothing. | H4 verify can-seek, units, real result. |
| [ ] | O-045 | **H** | CUSTOM greys Media feature controls that do not author size, including progress/seek/glow-related controls. | H6. CUSTOM Media lock is font size + artwork size only; preserve ordinary dependency gates. |

## Media — J visual/design parity

| State | ID | Phase | Observation | Durable handling / close condition |
|---|---|---|---|---|
| [ ] | O-021 | J | Media overall proportions/layout are poor vs old design language. | Rebuild outcome in Quick. |
| [ ] | O-022 | J | Artwork region too small/mispositioned; chrome too thick. | H2 is now closed; tune geometry/chrome in J Parity+. |
| [ ] | O-046 | **J Parity+** | Media artwork is visible again but no longer has the nicer historical artwork-change fade. | Restore a retained-scene artwork transition/fade without delaying or duplicating the closed H2 provider path. |
| [x] | O-023 | J preservation | New transport strip looks better. | Preserve. |
| [ ] | O-024 | J | App volume is folded inside Media instead of canonical slim adjustable adjacent/outside accessory. | Restore adjacent/outside toggle outcome; integrated form only as explicit optional variant. |
| [ ] | O-025 | J | `Junk`/album and `Paused` lines should be optional. | Preserve configurability/conditional density. |
| [ ] | O-026 | J | Spotify header border too thin/inconsistent. | Shared header language. |
| [ ] | O-027 | J | Media provider logo/header alignment off. | Cross-family baseline matrix. |

## Gmail / Reddit / headers

| State | ID | Phase | Observation | Durable handling / close condition |
|---|---|---|---|---|
| [ ] | O-028 | J | Gmail rows/text escape card. | Proper content clipping/elision. |
| [ ] | O-029 | J | Gmail refresh treatment inconsistent; Reddit preferred. | Shared treatment where semantics match. |
| [ ] | O-030 | J | Gmail/Media/Reddit logos slightly misaligned. | Cross-family header baseline. |
| [ ] | O-031 | J | Header borders/radii inconsistent. | Explain setting-driven differences or remove. |
| [ ] | O-032 | **H — awaiting validation** | Reddit URLs did not open even in MC. | H3 production opener wiring is prepared in the replacement pack. Validate MC direct-open/no-exit and saver secure-handoff/normal-exit, plus `screensaver_qml.log`, before closing. |
| [x] | O-033 | preservation | Gmail URL opening works. | Preserve. |
| [ ] | O-048 | **H — awaiting validation** | Clock can preserve analogue/digital state yet recreate at the wrong geometry/scale after Settings/Edit. | H3b now aligns per-display mode selection with the matching CUSTOM variant, seeds independent analogue/digital rect+font states, keeps the display-owned geometry binding coherent during live toggles, and canonicalizes target variants outside active edit transactions. Validate analog↔digital variant restoration + Settings/CUSTOM recreation + restart before closing. |

## Achievement Pulse

| State | ID | Phase | Observation | Durable handling / close condition |
|---|---|---|---|---|
| [ ] | O-034 | J | Too much wasted space. | Use available card area. |
| [ ] | O-035 | J | Achievement icon poorly positioned. | Restore coherent hierarchy. |
| [ ] | O-036 | J | Unlocked amount truncates despite free space. | Correct width/elision allocation. |

## Additional physical layout/input

| State | ID | Phase | Observation | Durable handling / close condition |
|---|---|---|---|---|
| [ ] | O-037 | J | OS cursor + retained halo/cursor shape can appear as double cursors. | One coherent visible pointer treatment; same-scene auxiliary ownership remains. |
| [ ] | O-038 | J | Non-CUSTOM widgets dog-pile; Media/Visualizer overlap rather than using intended adjacent free space. | Ordinary layout should prefer usable adjacent region. CUSTOM committed overlap/cross-display remains legal. |
| [ ] | O-049 | **J low priority / H conditional** | CUSTOM/Edit currently shows no useful alignment/snap guidelines to the operator. | The retained Quick overlay already has grid/guide visuals and a `set_guides(...)` seam, but current source has no caller of that seam. Preserve as low-priority J interaction parity; if taken up, wire guide publication from the existing Python snap/layout owner rather than inventing another geometry owner. |
| [ ] | O-050 | **J low priority** | No performance/debug overlay is currently visible. | Preserve as a later operator/debug affordance. Any replacement must be Quick-native/read-only over current metrics and must not resurrect `gl_profiler.py`, QWidget/QRhi/GL presenter ownership, or another rendering surface. |
| [ ] | O-051 | **H** | Middle-click on the live Visualizer no longer hotswaps to the next preset in the current mode. | H8. Restore retained middle-button semantic admission and a same-mode preset activation transaction. Preserve wraparound, exact Custom snapshot round-trip, narrow `widgets.spotify_visualizer` persistence, one visualizer owner/runtime/pacer, and no next-image/exit/context-menu side effect. |

## Observability

| State | ID | Phase | Observation | Durable handling / close condition |
| --- | --- | --- | --- | --- |
| [x] | O-047 | permanent | Qt/QML diagnostics were previously invisible to Python log review. | Always-on `screensaver_qml.log` is permanent; every physical Quick H/J gate inspects it. Latest supplied sidecar proves the clean shape: session markers present, `messages=0`, `write_errors=0`. |

## Closure use

H cannot close until every unresolved H/H-J row is closed or explicitly carried to J with evidence. J cannot close from unit tests alone where the defect is physical pixels, clipping, interaction feel or black flash.

The active prompt is intentionally narrower than this ledger. Finishing it does not finish the ledger.
