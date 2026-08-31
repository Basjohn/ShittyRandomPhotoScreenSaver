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
| [ ] | O-053 | J | Context-menu theme colours do not follow the active theme; the menu remains stuck on one palette despite being a themed element. | Trace the menu palette/style binding back to the canonical theme authority. Repair through the existing theme pipeline; do not create a menu-only palette owner or hard-code another colour set. **AWAITING VALIDATION** after implementation. |
| [ ] | O-040 | H/J validation | Startup formerly flashed diagnostic/test colour bands and still showed a black clear afterward. | Proof palette leak is repaired. Trace then proved native show could precede first real image. Current repair arms geometry/visible intent while hidden and commits show only after a real `PresentationImage` exists. **AWAITING PHYSICAL VALIDATION**; close when neither proof bands nor black first-show clear remains. |

## Visualizer

| State | ID | Phase | Observation | Durable handling / close condition |
|---|---|---|---|---|
| [x] | O-012 | H preservation | Visualizer retained delivery now visibly evolves. | Preserve `adcfd96d`. |
| [ ] | O-013 | **H** | Spectrum/Organ migration regression. | R1 physical re-measure: Spectrum is again recognizable and strongly reactive after topology/source-shaping/0.55-transfer repairs. Remaining H5c defect is narrowly the brief zero-bars gap immediately after Pause before the already-correct idle floor appears. No global gain. |
| [ ] | O-014 | **H/J audit** | Line-mode parity follow-up. | R1 physical re-measure confirms Sine idle transport exists but is a little weak; R2 raises paused-only motion 20%. DevCurve is broadly good but has jagged/doubled outlines and weak bottom heavy-hit visibility; source audit found Quick-only rendered ghost curves that were a historical no-op, now removed before any viewport/AA retune. Oscilloscope remains comparative control. |
| [ ] | O-015 | **H active (H5c)** | Bubble remains visually barely reactive under music. | R1 logs now exonerate source admission and authored cadence: `ready=True`, strong live energy/pulses and ~90 Hz 1:1 integration are present. R2 removes a Quick-only stale geometry override: protected consume-once edges no longer carry/replace full Bubble arrays; newest ordinary `BubbleFrame` is the sole geometry authority. Next physical run decides whether any simulation->snapshot->renderer magnitude defect remains. Preserve current resizing and do not global-gain tune. |
| [x] | O-016 | J preservation | Bubble partial/CUSTOM resize works quite well. | Preserve. |
| [ ] | O-044 | **H active (H5a)** | In CUSTOM, Visualizer does not activate when its committed display differs from Media's display. | Existing source contract already grants Visualizer its own monitor in CUSTOM. `[VIS_ROUTING]` and a two-live-unit production-admission pin are now GREEN without a routing change; reproduce physically and localize the first wrong trace field before repairing persistence/admission/failover. |
| [ ] | O-052 | **H active (H5c)** | Visualizer has a visible reactivity startup delay after long idle Pause; app startup and hotswap fade-in do not show the same problem. | R1 diagnostics proved the original 1.5 s T3 reading could be sampler-induced and Bubble can receive a fresh frame in ~tens of ms. Historical pause->play `engine.wake()` was missing in Quick and is restored. Cold reactivity ramp is now 1.0 s; warm resume remains unramped; freshness fencing is unchanged. Corrected T0-T7 trace remains the closure gate. |

## Media — functional/settings

| State | ID | Phase | Observation | Durable handling / close condition |
|---|---|---|---|---|
| [x] | O-017 | H closed | Media artwork previously decoded but never displayed. | Closed: production model now uses the exact engine-registered provider and latest physical run visibly shows artwork. Preserve cross-layer provider identity. |
| [x] | O-018 | **H — CLOSED** | Play/Pause transport semantics. | Operator validated H4 physically; archived from active execution. |
| [x] | O-019 | preservation | Previous/Next work. | Preserve. |
| [x] | O-020 | **H — CLOSED** | Seek/progress transport semantics. | Operator validated H4 physically; archived from active execution. |
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
| [x] | O-032 | **H — CLOSED** | Reddit URL opener. | Operator validated H3 physically; archived from active execution. |
| [x] | O-033 | preservation | Gmail URL opening works. | Preserve. |
| [x] | O-048 | **H — CLOSED** | Clock analogue/digital state + CUSTOM geometry recreation. | Operator validated H3b physically; archived from active execution. |

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
