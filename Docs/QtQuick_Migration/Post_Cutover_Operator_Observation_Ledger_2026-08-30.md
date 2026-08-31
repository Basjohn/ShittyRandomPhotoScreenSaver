# Post-Cutover Operator Observation Ledger — 2026-08-30

Applies to: H post-cutover runtime-reality correction and J final physical/visual acceptance.

This ledger is mandatory phase-close input. Narrow implementation prompts never imply that unmentioned rows are done.

## Baseline / parity rule

**J is Parity+.** For covered ordinary families, the paired repository oracle under `images/migration/Ideal (PreMigration)/` versus `images/migration/Current (PostMigration)/` is the **highest visible parity authority** for pixels it shows and should be worked early by a vision-capable agent. The 4.7.2/4.7.0 release screenshots and `15099d3` are secondary broad-composition/archaeology references. **For visualizer reactivity specifically, the user-supplied `3fe5df6` tree remains the known-good pre-Qt-Quick behavioral oracle.** Current explicit operator decisions may preserve a newer preferred treatment, but implementation stays with current Quick owners. Never restore/wrap/adapt the deleted QWidget/QRhi/GL presenter.

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
| [ ] | O-008 | J | First context-menu open on each display historically could cause rapid black/stale-frame flashes. | The old event-driven retained-background refresh experiment **physically failed and was removed**. R-63 PresentMode overscan is the accepted recurring-flash fix. Revalidate first-open behavior under the current R7 exterior-edge overscan; if a first-open-only defect survives with R-63 stable, investigate retained-menu first-visible resources/native continuity without restoring the failed refresh path. |
| [ ] | O-009 | J/perf / H conditional | Exit previously felt slow. Current clean run accepts/quiesces immediately, terminal Quick barrier completes in ~250 ms, then script-only pycache cleanup consumes about a second. | Remeasure visible window dismissal. If prompt, classify remaining tail as J/perf/developer housekeeping rather than lifecycle H. |
| [ ] | O-010 | J | Clicking/focusing A -> B -> A historically black-flashed the whole scene. | PresentMon later localized recurring activation flash to exact-cover fullscreen-flip promotion and R-63 fixed the recurring class. The activation background-redraw experiment failed and was removed. Revalidate under R7 overscan; do not restore redraw-on-focus as a workaround. |
| [ ] | O-011 | J | Black flashes/flicker were reported at startup/focus/context-menu/transition edges. | Recurring/activation flash is solved by R-63 and must stay solved. The deferred-show and event-driven background-refresh experiments both physically failed and were removed. Only residual startup/first-visible behavior that still reproduces under current R7 belongs here; diagnose from current surface/PresentMode evidence rather than reintroducing those experiments. |
| [ ] | O-039 | J | Context submenus remain open indefinitely after pointer leaves. | Same-scene hover-path dismissal/switching with bounded crossing grace; preserve opening-click fix. |
| [ ] | O-053 | J | Context-menu theme colours do not follow the active theme; the menu remains stuck on one palette despite being a themed element. | Trace the menu palette/style binding back to the canonical theme authority. Repair through the existing theme pipeline; do not create a menu-only palette owner or hard-code another colour set. **AWAITING VALIDATION** after implementation. |
| [ ] | O-040 | J | Startup formerly flashed diagnostic/test colour bands and sometimes a black clear. | Proof palette leak is repaired and remains closed. The later deferred-native-show experiment made startup worse and was removed; do not restore it. Re-test only the residual current startup micro-flash under R-63/R7 and close when no proof band or unexplained black first-visible frame remains. |

## Visualizer

| State | ID | Phase | Observation | Durable handling / close condition |
|---|---|---|---|---|
| [x] | O-012 | H preservation | Visualizer retained delivery now visibly evolves. | Preserve `adcfd96d`. |
| [ ] | O-013 | **H** | Spectrum/Organ migration regression. | R1 physical re-measure: Spectrum is again recognizable and strongly reactive after topology/source-shaping/0.55-transfer repairs. Remaining H5c defect is narrowly the brief zero-bars gap immediately after Pause before the already-correct idle floor appears. No global gain. |
| [ ] | O-014 | **H/J audit** | Line-mode parity follow-up. | R1 physical re-measure confirms Sine idle transport exists but is a little weak; R2 raises paused-only motion 20%. DevCurve is broadly good but has jagged/doubled outlines and weak bottom heavy-hit visibility; source audit found Quick-only rendered ghost curves that were a historical no-op, now removed before any viewport/AA retune. Oscilloscope remains comparative control. |
| [ ] | O-015 | **H/J audit** | Bubble migration had several reactivity/viewport artifacts. | Radius projection loss is fixed. R4/R5 source-centre + radial/ring-spacing wake scaling is physically accepted for the tested problematic viewport shapes and removed the excess ghost/motion-tail footprint. Preserve BTF/cadence and do not retune physics to hide presentation problems. Separate open contract: Bubble Ghost/Decay semantics are still not actually consumed by the current Quick/shared shader path; resolve that explicitly rather than treating the accepted wake repair as proof that all Bubble parity is closed. |
| [x] | O-016 | J preservation | Bubble partial/CUSTOM resize works quite well. | Preserve. |
| [ ] | O-044 | **H active (H5a)** | In CUSTOM, Visualizer does not activate when its committed display differs from Media's display. | New logs prove correct screen-1 route/owner/draw with Media on screen 0, but playback remains false. Source-localized cause: initial/bound Media model lookup was same-unit-only. The repair now resolves the already-admitted Media model across active units and pins screen-0 Media -> sole screen-1 Visualizer playback; no duplicate Media card or routing/failover change. Await physical confirmation. |
| [ ] | O-052 | **H active (H5c)** | Visualizer has a visible reactivity startup delay after long idle Pause; app startup and hotswap fade-in do not show the same problem. | R1 diagnostics proved the original 1.5 s T3 reading could be sampler-induced and Bubble can receive a fresh frame in ~tens of ms. Historical pause->play `engine.wake()` was missing in Quick and is restored. Cold reactivity ramp is now 1.0 s; warm resume remains unramped; freshness fencing is unchanged. Corrected T0-T7 trace remains the closure gate. |

## Media — functional/settings

| State | ID | Phase | Observation | Durable handling / close condition |
|---|---|---|---|---|
| [x] | O-017 | H closed | Media artwork previously decoded but never displayed. | Closed: production model now uses the exact engine-registered provider and latest physical run visibly shows artwork. Preserve cross-layer provider identity. |
| [x] | O-018 | **H — CLOSED** | Play/Pause transport semantics. | Operator validated H4 physically; archived from active execution. |
| [x] | O-019 | preservation | Previous/Next work. | Preserve. |
| [x] | O-020 | **H — CLOSED** | Seek/progress transport semantics. | Operator validated H4 physically; archived from active execution. |
| [ ] | O-045 | **H validation** | CUSTOM was reported to grey Media feature controls that do not author size, including progress/seek/glow-related controls. | H6 current-source audit finds no second CUSTOM setter. The normal profile's exact `Custom` + all-feature-on state passes a real `WidgetsTab` gate: only font/artwork are disabled; progress/glow/volume/mute follow their normal dependencies. Full Settings/descriptor suite is `126/126`. Re-open current Settings physically; if still grey, capture control and parent enabled/style state rather than force-enabling. |

## Media — J visual/design parity

| State | ID | Phase | Observation | Durable handling / close condition |
|---|---|---|---|---|
| [ ] | O-021 | J | Media overall proportions/layout are poor vs old design language. | Rebuild outcome in Quick. |
| [ ] | O-022 | J | Artwork region too small/mispositioned; chrome too thick. | H2 is now closed; tune geometry/chrome in J Parity+. |
| [ ] | O-046 | **J Parity+** | Media artwork is visible again but no longer has the nicer historical artwork-change fade. | Restore a retained-scene artwork transition/fade without delaying or duplicating the closed H2 provider path. |
| [x] | O-023 | J preservation | Current post-migration Media transport/control strip looks better. | **Preserve this strip. It is the only current Media visual treatment presently judged superior to the old implementation; do not infer broader Media exceptions from it.** |
| [ ] | O-024 | J | App volume is folded inside Media instead of being its own slim adjustable Media child widget; no separate/integrated selector exists yet. | Restore a separate retained adjacent/outside child item as the existing/unspecified default. Its own rect/size lives in Media's effective display bucket; visibility/lifecycle and display route remain Media-dependent, with no monitor choice. Integrated is an explicit optional variant only. Both reuse the existing Media presentation model plus one `MediaVolumeRuntimeService` lease/action seam; the child presentation does not own/duplicate the runtime or resurrect QWidget. |
| [ ] | O-025 | J | `Junk`/album and `Paused` lines should be optional. | Preserve configurability/conditional density. |
| [ ] | O-026 | J | Spotify header border too thin/inconsistent. | Shared header language. |
| [ ] | O-027 | J | Media provider logo/header alignment off. | Cross-family baseline matrix. |

## Gmail / Reddit / headers

| State | ID | Phase | Observation | Durable handling / close condition |
|---|---|---|---|---|
| [ ] | O-028 | J | Gmail rows/text escape card. | Proper content clipping/elision. |
| [ ] | O-029 | J | Gmail refresh treatment inconsistent; Reddit preferred. | Shared treatment where semantics match. |
| [ ] | O-030 | J | Gmail/Media/Reddit logos slightly misaligned. | Cross-family header baseline. |
| [ ] | O-059 | **J mandatory / early parity** | Ordinary-family logo + header-name groups do not scale with their cards/widgets after migration; they remain effectively fixed-size while the card changes size. | Treat logo + family/provider name as one authored header relationship. Restore coherent card-relative scaling and cross-family baseline/vertical alignment without creating per-family geometry owners or QML layout authority. |
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
| [x] | O-037 | J preservation | OS cursor + retained halo/cursor shape could appear as double cursors. | **R6 physically resolves the performance/ownership class:** the retained fake pointer is removed and one native `QCursor` owns pointer presentation; pointer movement no longer dirties the Quick scene. Preserve this architecture. Visible Halo styling is tracked separately because the operator currently sees only an ordinary-looking cursor. |
| [ ] | O-038 | J | Non-CUSTOM widgets dog-pile; Media/Visualizer overlap rather than using intended adjacent free space. | Ordinary layout should prefer usable adjacent region. CUSTOM committed overlap/cross-display remains legal. |
| [ ] | O-049 | **J mandatory / early parity** | CUSTOM/Edit currently shows none of the useful alignment/snap guide lines that existed pre-migration. | Restore centre/peer/edge/safe-gutter guide visibility through the existing Python snap/layout authority and retained Quick guide seam. This belongs in the early vision-capable J tranche beside the family screenshot oracle; it is not optional polish and must not create QML geometry truth or a second layout owner. |
| [ ] | O-050 | **J low priority** | No performance/debug overlay is currently visible. | Preserve as a later operator/debug affordance. Any replacement must be Quick-native/read-only over current metrics and must not resurrect `gl_profiler.py`, QWidget/QRhi/GL presenter ownership, or another rendering surface. |
| [ ] | O-051 | **H** | Middle-click on the live Visualizer no longer hotswaps to the next preset in the current mode. | H8. Restore retained middle-button semantic admission and a same-mode preset activation transaction. Preserve wraparound, exact Custom snapshot round-trip, narrow `widgets.spotify_visualizer` persistence, one visualizer owner/runtime/pacer, and no next-image/exit/context-menu side effect. |
| [ ] | O-054 | **J** | R6 fixes Halo performance/duplicate-pointer ownership, but the visible custom Halo treatment is currently absent; the operator sees an ordinary-looking cursor. | Fix native cursor artwork/selection/inactivity visual parity **without** restoring a moving QML cursor, mouse-rate Settings/provider reads, scene-root pointer properties or a second pointer. |
| [ ] | O-055 | **J geometry/parity** | Weather scaling once emitted repeated `preferredContentHeight` binding-loop warnings from `WeatherPresentation.qml`. | Source-localize the preferred-size/layout cycle and require repeated resize + Save/recreation with zero loop warnings. Keep in J unless it proves functional/committed geometry corruption before H closes. |
| [ ] | O-056 | **H physical validation** | One image change bare-flashed the destination instead of delivering a transition. | R7 source repair makes image-change admission transactional before queue/history mutation, rejects competing requests while a batch is active, forbids cancel-to-destination replacement, and withholds non-startup destination if no transition can be admitted. Hammer Next/natural rotation during transitions; bare image swap must be 0. |
| [ ] | O-057 | **H/J physical validation** | A transition can intermittently leave a one-device-pixel vertical seam at the shared display edge; another transition may remove it. | Preserve R-63. R7 narrows overscan to one virtual-desktop exterior edge and logs logical/device geometry. Acceptance requires **black/stale flash = 0 AND seam pixel = 0**; never trade one defect for the other. |
| [ ] | O-058 | **H validation** | Media steady-state polling was replaced by native GSMTC event observation. | Short installed multi-recreation smoke is positive: observation established each generation, real events arrived, `stale_rejected=0`, `missed=0`, `degraded=False`, QML sidecar clean, clean exit. Broader frozen/provider-switch/CUSTOM lifecycle validation remains before closure; no silent fast-poll fallback may return. |

## Observability

| State | ID | Phase | Observation | Durable handling / close condition |
| --- | --- | --- | --- | --- |
| [x] | O-047 | permanent | Qt/QML diagnostics were previously invisible to Python log review. | Always-on `screensaver_qml.log` is permanent; every physical Quick H/J gate inspects it. Latest supplied sidecar proves the clean shape: session markers present, `messages=0`, `write_errors=0`. |

## Closure use

H cannot close until every unresolved H/H-J row is closed or explicitly carried to J with evidence. J cannot close from unit tests alone where the defect is physical pixels, clipping, interaction feel or black flash.

The active prompt is intentionally narrower than this ledger. Finishing it does not finish the ledger.
