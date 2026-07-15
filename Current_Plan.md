# Current Plan

Last updated: 2026-07-15

This file tracks active work only. Long-lived architecture truth belongs in `Spec.md`; dated bug narratives belong in `Docs/Historical_Bugs.md`.

## Guardrails

- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, `Docs/Historical_Bugs.md`, and `Docs/Harness_Index.md`.
- Prune validated work aggressively. This is not a changelog.
- Prefer automation bars over repeated runtime-verification asks.
- Fallbacks must stay loud and routed through the relevant CLI family; a fallback is evidence, not success.
- UI pressure is barred as a perf fix. Do not add repaint/update requeue loops, rescue timers, or broad UI refreshes to chase FPS.
- Fullscreen / one-pixel shrink / startup-flash behavior is frozen at last committed behavior unless explicitly greenlit through a document-first audit.
- Before touching shared visualizer/audio/activation/render/transition seams, run the focused visualizer reactivity lock from `Docs/Harness_Index.md`.

## Active Tasks

Execution order is dependency-driven: validate the new whole-process usage sidecar alongside the active paused-visualizer pressure correction because the latest mixed-refresh logs show visible cadence collapse without resource attribution; then spend the longer compiled Steam budget against the intended release shape; then classify the ignored audit documents. Oscilloscope direct-start/hotswap and all requested mixed-display Clock scenarios are user-validated and closed under R-45, R-47, and R-48 in `Docs/Historical_Bugs.md`; they no longer occupy the live plan. Blob retirement is complete and preserved under R-46. The completed General-widget-settings/cache work is canonical in `Spec.md`, `Index.md`, and `Docs/Guardrails.md`; its deferred shadow-direction prerequisite remains in `Future_Cleanup.md`. The Drift evidence pass is preserved under U-07 and found no implementation defect. No existing Steam or audit bar is displaced or treated as complete.

### Whole-Process Usage Telemetry Runtime Bar

- [ ] In a fresh packaged mixed-refresh run, use `--usage --perf --viz` for at least 30 minutes across ordinary playback, visualizer hotswaps, image transitions, Settings stop/restart, and one display rebuild. Require one bounded `screensaver_usage.log` sample roughly every 15 seconds with main-plus-child CPU, system CPU, RSS/private/VMS, thread/handle/IO totals, app-shared ThreadManager activity, vendor-neutral Windows GPU engine usage, and dedicated/shared VRAM where supported. Unsupported or temporarily absent GPU counters must remain `na`/explicitly classified rather than zero. The parser must merge the usage sidecar, report resource deltas/peaks, flag sampler cost/skips/gaps, and correlate samples with visualizer timing and first-frame/reactivity failures.
- [ ] Require telemetry non-interference: no tray polling, unmanaged thread, per-frame OS query/allocation, UI-thread collection/log write, repaint/update, visualizer retuning, source-cadence change, or automatic quality reduction. `collect_ms` must remain below the parser's 100 ms intrusion threshold after counter warmup, no sample may overlap or skip, current-good visualizer reactivity/smoothness and transition pixels/durations must remain unchanged, and shutdown must stop the sampler before the app-shared ThreadManager without task/resource warnings.

### Paused Visualizer / Mixed-Refresh Cadence Recovery

- [x] Correlate the 2026-07-14 06:03-06:09 run across perf, visualizer, lifecycle, widget, and cache logs. Wipe/Diffuse were healthy near `151/59` paint FPS before live visualizer authority; after Bubble activation and confirmed pause, every tested transition family collapsed both displays to roughly `22-33` paint FPS while Bubble worker cost stayed around `1.8-2.7 ms`, transition paints were generally cheap, image cache remained at `100%` hits with no worker fallback, and swap/shader/pending-requeue noise stayed absent. Treat this as shared child-GL/UI delivery pressure, not a transition shader or growing Bubble-simulation leak.
- [x] Bound timer-owned paused idle animation at `75 Hz` so synthetic idle frames cannot inherit the live no-transition `100 Hz` boost. Preserve live playback at the existing `90-100 Hz`, preserve one overlay `update()` request per accepted payload, retain paused Bubble motion, and do not revive the failed owner-target producer throttle that visibly delivered only `39-40 FPS` on a 60 Hz owner. Overlay perf telemetry now records `playing` state so the next run can distinguish live authority from paused idle pressure directly.
- [ ] In a fresh compiled mixed-refresh run with `--perf --viz`, exercise one healthy live Bubble passage, confirm pause through the six-second capture grace, then run both ordinarily spaced and several back-to-back random transitions. Require paused overlay `set_state` to settle at or below the authored 75 Hz source budget without visible idle judder, live Bubble to return to its existing cadence/reactivity, and Display 0 / Display 1 transition paint to avoid the latest near-`60/40` render and `22-33` paint collapse. Require no new pending-paint requeue, repaint retry, shader/swap/cache fallback, severe **live-playback** latency, or slow `_on_tick` phase owner; paused forced latency probes are diagnostic and must be reviewed separately rather than treated as a live-audio failure.
- [ ] If both displays still collapse while paused overlay input is correctly bounded, add passive child-overlay paint-duration/accepted-update-to-paint attribution and evaluate same-surface compositor ownership as the next structural target. Do not lower playing Bubble cadence, drop accepted repaint requests, subscribe visualizer work to transition `AnimationManager`, or add UI timers/retries without new evidence.

### Widget And Visual Timing Runtime Bar

- [ ] In a fresh normal and MC compiled run, validate Achievement Pulse's default `140 x 196` Portrait art at `600 x 334`: left/right padding matches the family rails, header/art alignment stays exact, `Unlocked` remains six authored pixels below art and renders complete high counts without ellipsis in Portrait/Wide/Square/art-off, and the 40px achievement icon occupies the prior-unlock lane without narrowing the primary unlock title. Long game/latest/prior names must shrink before elision while preserving game >= latest >= prior font size; the first capsule rail retains its measured gap, and 140/190 width changes, high DPR, large capsule font, settings rebuild, and Custom scaling do not clip or rearrange content. With two recent games whose play order and latest-unlock order disagree, require Most Recent, Previous, and Settings labels to follow the newest positive unlock timestamp while missing timestamp evidence falls back stably.
- [ ] Run solid-bar Spectrum with `--viz --perf` through quiet/dropout material and at least one image transition: the 2026-07-14-style coherent input collapse must decay/recover without a brief zero flash or delayed-frame snap, while ordinary smoothing remains visually unchanged and logs show no new timer/repaint/audio-floor pressure.

### Steam Abandonment Issues Production Runtime Bar

- [ ] In a fresh compiled run without `--devsteam`, enable Abandonment Issues and verify cached content appears before the first coordinated fade, Smart/Pinned/unknown-history states remain honest, cached library names populate without provider work, and explicit Refresh Steam Library gives gentle success/failure feedback.
- [ ] Run multi-display and long-idle passes with `--steam --perf --cache --set --geo --life`: set the shared Steam refresh interval to 5 minutes and confirm `ABANDONMENT_CADENCE` reports shared/rotation `5`, the recurring timer is 300,000 ms, automatic game changes follow that cadence without a competing 15/30-minute value, owned-library requests still respect their 24-hour source window, and recent games follow shared freshness. Widget/settings/display rebuilds or interval changes must preserve only the true remaining due interval; explicit widget refresh must force a visibly different non-repeating draw when alternatives exist; several due intervals must log preference-biased non-sequential backlog ranks without immediate repeats, and user-facing `BACKLOG N/M` remains rank rather than cursor. Selection must issue no owned/recent/candidate-achievement work; after each identity commit, enabled `ACHIEVEMENTS` / `LAST UNLOCK` shelves may cause at most one exact selected-app request, then `[STEAM][ABANDONMENT_ACHIEVEMENTS]` must report `hydrated` once and `cache_hit` within 24 hours without changing the selected app. A selected public-art cache miss may hydrate only on the existing IO job before the atomic fade commit; a requested-shape 404 may log one `fallback_hydrated` alternate, transient failures must not fan out, and `--noupdates` must keep both evidence and art automatic hydration cache-only. Require no blank committed art when an allowlisted variant succeeds, no repaint burst/UI-thread stall/DT spike, and one deferred retry rather than a lost interval on parent-transition collision. Keep 15-minute session-floor/2-hour/2-unlock/26-week ranking changes honest.
- [ ] Validate portrait/wide/art-off at the authoritative 600 px authored width, minimum/default/maximum portrait size, Guilt off/on/max, RGBA accent, rediscovery message off/on plus a longest alternate staying fitted and stable across displays/rebuilds, and every optional ledger-field combination. Specifically prove `PLAYED` / `ACHIEVEMENTS` / `LAST UNLOCK` / exact `LAST PLAYED` date plus optional `BACKLOG CLASS` remain truthful, unknown/private achievement evidence removes only its dependent shelf, a supported selected game visibly gains count and unlock data after bounded hydration, disabling both dependent shelves submits no selected achievement request, all eight enabled shelves grow complete rows, and game title remains at least as large as fitted reminder text before final elision. With `--steam`, require one `[STEAM][ABANDONMENT_SHELVES]` record per prepared presentation whose requested/rendered/unavailable IDs and evidence states match the visible settings without leaking titles or values. Large fonts, high DPR, and narrow/tall multi-monitor `Custom` geometry must not overlap, reflow, clip, shrink the authored hierarchy, or mutate the committed rect.
- [ ] Exercise `--noupdates`, offline, unauthorized-with-valid-cache, disconnect, settings restart, frozen build, and non-repository cwd; cache must remain authoritative, `--noupdates` must log `cache_miss_network_disabled` rather than fetching public art automatically, failed sources must not freshen it, teardown must leave no Steam timer/task/resource warnings, and credentials/account data must remain absent from logs/exports/repo artifacts.

### Canonical Audit Document Classification

- [ ] Review all nine ignored/untracked Markdown documents under `audits/` for unique evidence, stale conclusions, credentials, identifiers, screenshots, absolute machine paths, and generated debris. Do not unignore or upload the directory wholesale.
- [ ] For each document, either sanitize and deliberately track it as durable source, migrate still-valid guidance into `Spec.md` / `Docs/Historical_Bugs.md` / `Docs/Harness_Index.md` and retire the local copy, or leave it explicitly local and noncanonical with no navigation dependency.
- [ ] Add a bounded documentation-link check proving every canonical file reference in `Index.md` and this plan exists in tracked source. Restore specific audit links only for documents that pass classification, then prune this task.

## Watchlist

- [ ] Performance cadence: preserve fresh evidence if Display 0 falls into a suspicious near-60 visible cadence, Display 1 into near-40 under-delivery, or the parser reports paint starvation, overlay under-delivery, swap-interval warnings, shader/cache fallbacks, or repeated app-shared `AnimationManager` under-target windows with actionable `active_labels`.
- [ ] Visualizer timing: if `--viz` logs show slow `_on_tick` phase breakdowns, fix the named owner directly; if only tick gaps appear, treat it as event-loop/timer delivery pressure rather than visualizer work.
- [ ] Reddit cadence: in the next long compiled run, confirm both widgets fire near due cadence, sparse HTML does not become the repeated primary source after partial rescue, and failed/empty chains do not freshen cache timestamps.
- [ ] Visualizer CUSTOM geometry route repair: reopen only if fresh logs show repeated bucket repair, duplicate-owner fallback, requested-monitor fallback, replay-green/runtime-wrong geometry, or settings-return suppression/stranding.
- [ ] Display wake / monitor recreate: keep the latest behavior accepted unless black-background recovery, missing compositor surfaces, duplicate displays, placeholder truth, or an exhausted per-display image-replacement warning returns. A worker-rejected first candidate should now recover that display within the same compute pass.
- [ ] Settings runtime restart: expected lazy-section omission must stay free of `blocked_save_from_unhydrated_section`; reopen only if that warning reflects a real direct unhydrated save, deleted Qt wrapper errors, stale background hydration, or settings-exit runtime bleed in `--set` / main logs.
- [ ] Sources / RSS reset: validate that "Just Make It Work" preserves existing RSS cache, emits one deferred source-change during settings, and settings exit performs only one clean source/RSS initialization without stranding media or visualizer.
- [ ] Non-`Custom` authored stacking: default-on for new users; re-audit with `--geo` only if authored-layout collision behavior reopens.
- [ ] Supported visualizer reactivity and smoothness remain accepted. The active paused-source cadence correction and `--usage` profiling are shared scheduling/diagnostic work and must not become mode-owned retuning. Reopen mode visuals only with fresh `--viz` evidence. Spectrum is temporarily covered by the active rare-dropout runtime bar above.
- [ ] Media metadata preservation during live visualizer preset churn: if it reopens, first suspect partial same-track playback snapshots during visualizer-only settings writes.
- [ ] Steam Journey and Friend Pulse remain production-hidden until each is explicitly promoted beyond `--devsteam`; Journey's next gate is editorial classification/noise/request-budget evidence, not transport discovery.

## Deferred / Not Active

### First-Run Source Onboarding Restart

- [ ] Add an explicit startup-onboarding context/result contract instead of inferring intent from any Settings close. Enter it only when RUN mode reaches the no-source startup branch in `main.py`; ordinary CONFIG-mode opening, tray/S-key Settings, and engine-owned settings restart must retain their existing behavior. Record whether the dialog began without runnable sources and whether valid folders/RSS feeds exist when it closes, without logging source values.
- [ ] Reuse the existing modal Settings lifecycle and source persistence/change channels where practical. Return a typed outcome from the startup-onboarding dialog to the top-level RUN-mode state machine, clean up its `AnimationManager`, and start a fresh `ScreensaverEngine` in the same `QApplication` when sources became runnable. Do not recurse through `run_screensaver()`, create a second application/event loop, simulate a process launch, or make `SourcesTab` directly own engine startup.
- [ ] Cover every successful source path: a manually added folder, a manually added RSS feed, Sources-tab `Just Make It Work`, and `NoSourcesPopup` `Just Make It Work` must all close Settings and start the screensaver exactly once. Closing with no sources / choosing the explicit exit path must still exit cleanly; merely opening and closing manual Settings must never launch RUN mode.
- [ ] Preserve the current startup notice and styled no-source popup, but replace popup-owned `sys.exit()`/last-window side effects with the explicit onboarding outcome where required. Require one source initialization and queue build after dialog close, no stale Settings widget/background hydration callbacks, no duplicate ThreadManager/ResourceManager/engine instances, and no initial blank/exit interval that makes the successful setup look ignored.
- [ ] Add isolated startup-state-machine tests plus normal/MC frozen runtime coverage with `--set --life --cache`: prove manual and both `Just Make It Work` paths restart into visible images, existing RSS cache is preserved, source-change signals coalesce into the single post-dialog initialization, and ordinary engine Settings still performs its established stop-dialog-restart cycle once.

### True Eight-Direction Widget Shadows

- [ ] Freeze the current bottom-right visual baseline before changing authority. Capture representative card, text, header, artwork/icon, control, Weather, Media, Steam, Spotify volume/visualizer, and analogue Clock renders at 100/125/150/200% DPR, plus outer/content/card rects and cache keys. The shipped `[4, 4]` bottom-right setting must remain pixel- and geometry-equivalent after every phase.
- [ ] Make one direction contract authoritative without replacing authored per-surface fidelity. Keep `shadowtuning.json` as magnitude/blur/spread/alpha authority; normalize `widgets.shadows.offset` to the eight signed direction vectors (`[-4,-4]`, `[0,-4]`, `[4,-4]`, `[-4,0]`, `[4,0]`, `[-4,4]`, `[0,4]`, `[4,4]`) and use only its signs when applying each surface's existing local magnitude. Reject/normalize malformed values, preserve `[4,4]` as default, and keep Normal/MC defaults, Foundry descriptors/tooltips, imports, and exports in parity without introducing a competing direction key.
- [ ] Introduce one immutable/cached runtime shadow-style resolver at the shared shadow seam. Resolve direction when `set_shadow_config()` or equivalent config application occurs, carry direction-resolved offsets into painter/cache helpers, and include them in affected DPR pixmap keys. No SettingsManager reads, JSON reads, new effects, allocations, or generalized direction math may occur in steady-state paint loops.
- [ ] Replace right/bottom-only card assumptions with four-sided visual insets while preserving logical card/content size. Relocate the existing gutter budget for alternate directions, translate card and content composition as one unit, keep the committed outer rect stable, and teach authored positioning/visible-footprint calculations which side owns the visual overhang. Default bottom-right must use the exact current origin, shrink, border, and shadow pixels; alternate directions must not clip, shrink, reflow, alter CUSTOM authority, or change authored stacking gaps.
- [ ] Migrate every consumer before exposing the selector: `BaseOverlayWidget`, Clock and analogue details, Spotify visualizer card/volume, text and rich-text helpers, header frames, artwork/icon masks, rounded controls, Weather detail/icon paths, Media controls/artwork, Mute, and Steam cards. Remove or explicitly exempt each local positive-only offset so the UI cannot claim global direction while any visible family silently remains bottom-right.
- [ ] Add the inset 3x3 eight-direction selector to General > Appearance only after runtime parity is complete. Leave the center cell inert, use the established settings styling/tooltips/keyboard navigation, update the canonical signed offset through the existing save/refresh path, and provide immediate preview/runtime refresh without rebuilding widgets or adding repaint/timer pressure.
- [ ] Require all eight directions to pass synthetic clipping/bounds tests and visual renders across framed/unframed, shadows individually disabled, high DPR, large fonts, authored positions, stacking, live Settings refresh, CUSTOM replay, normal/MC defaults, and frozen builds. Reject the feature if fidelity is achieved only by reducing blur/spread/opacity, shrinking content, widening every default card, or reintroducing `QGraphicsDropShadowEffect`.

- [ ] Feeds widget family architecture track:
  - [ ] Keep Reddit as its own branded widget and shared runtime owner; do not replace it with Feeds.
  - [ ] Extract reusable list-feed seams from Reddit without changing Reddit UX first.
  - [ ] Design Feeds as an additional widget family with isolated per-spawn source/cache/settings contracts.
  - [ ] Prefer official/feed-native sources and avoid HTML scraping/session automation by default; Reddit HTML is the explicit paced exception because Reddit's structured public endpoints are fragile.
- Startup update-policy observability stays deferred behind current runtime-health priorities.
- Secure-desktop long-runtime exit reliability stays deferred.

## Documentation Rule

- Architecture: `Spec.md`
- Module map: `Index.md`
- Policy: `Docs/Guardrails.md`
- Dated regressions: `Docs/Historical_Bugs.md`
- Drift-check routine: `Docs/Documentation_Maintenance.md`
- Harness reference: `Docs/Harness_Index.md`
- Local ignored `audits/` notebooks are noncanonical until the active classification task either tracks a sanitized document or migrates its valid guidance into the sources above.

#######
### User Task Box: NEVER remove this box/section, only integrate its tasks into the active plan and then remove the text BELOW prompting the tasks.
----
----
######
