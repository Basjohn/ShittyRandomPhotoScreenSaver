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

Execution order is dependency-driven: complete the contained General-widget-settings UX/cache work and existing drift-log evidence pass while no fresh compiled runtime is required; then runtime-validate the paused-visualizer pressure correction because the latest mixed-refresh log regressed both displays into visible transition collapse; then retire deprecated Blob against the supported-visualizer baseline and canonical generated defaults; then spend the longer compiled Steam budget against the intended release shape; then classify the ignored audit documents. No existing Steam, Blob, or audit bar is displaced or treated as complete.

### General Widget Settings And Cache Maintenance

- [x] Rename only the user-facing WidgetsTab `Defaults` section/button/group copy to `General`. Preserve the internal descriptor `section_id="defaults"`, existing attribute/function/module names, Defaults Foundry, canonical-default terminology, reset wording, and documentation titles whose subject is genuinely defaults. Focused UI/descriptor/docs oracles now lock that distinction without broad word replacement.
- [x] Recompose the General section into styled buckets. Existing shadow controls and card border width remain under Appearance, authored stacking and reset positions remain under Layout, and Cache Maintenance is collapsed by default; descriptor-owned lazy build/load/save, hydration guards, scroll state, and current settings authority remain intact.
- [x] Add explicit cache maintenance with per-cache-family selection, a confirmation step naming the selected scope, safe locked/in-use-file handling, and gentle completion/failure feedback. The allowlist contains RSS images, Reddit post snapshots, Weather responses, Gmail metadata, Steam responses/public artwork, and Settings performance data only; recursive Steam deletion runs on ThreadManager IO, follows no symlinks, removes no directories, and credentials/settings/layouts/defaults/pacing markers/deprecated Imgur remain excluded.
- [x] Assess a global eight-direction shadow control against the real shadow pipeline. `widgets.shadows.offset` currently persists but does not drive the fragmented painter consumers, while card/visualizer/volume outer geometry reserves right/bottom-only gutter and Clock/Weather/Media retain special offsets. A GUI selector would therefore be misleading and top/left directions could clip; the required signed-vector/four-sided-padding/cache-key unification and eight-direction DPR bar are preserved in `Future_Cleanup.md` rather than shipping a partial control.

### Drift Reactivity Evidence

- [ ] Correlate the newest usable `--viz`/perf logs across idle, soft passages, and loud passages. Quantify whether Drift displacement/energy visibly and measurably rises with loudness while remaining minimal at idle, separate source-energy movement from transition/paint cadence, and record exact windows plus any missing telemetry. Do not retune Drift from aggregate FPS alone; promote implementation only if evidence shows a real response defect.

### Paused Visualizer / Mixed-Refresh Cadence Recovery

- [x] Correlate the 2026-07-14 06:03-06:09 run across perf, visualizer, lifecycle, widget, and cache logs. Wipe/Diffuse were healthy near `151/59` paint FPS before live visualizer authority; after Bubble activation and confirmed pause, every tested transition family collapsed both displays to roughly `22-33` paint FPS while Bubble worker cost stayed around `1.8-2.7 ms`, transition paints were generally cheap, image cache remained at `100%` hits with no worker fallback, and swap/shader/pending-requeue noise stayed absent. Treat this as shared child-GL/UI delivery pressure, not a transition shader or growing Bubble-simulation leak.
- [x] Bound timer-owned paused idle animation at `75 Hz` so synthetic idle frames cannot inherit the live no-transition `100 Hz` boost. Preserve live playback at the existing `90-100 Hz`, preserve one overlay `update()` request per accepted payload, retain paused Bubble motion, and do not revive the failed owner-target producer throttle that visibly delivered only `39-40 FPS` on a 60 Hz owner. Overlay perf telemetry now records `playing` state so the next run can distinguish live authority from paused idle pressure directly.
- [ ] In a fresh compiled mixed-refresh run with `--perf --viz`, exercise one healthy live Bubble passage, confirm pause through the six-second capture grace, then run both ordinarily spaced and several back-to-back random transitions. Require paused overlay `set_state` to settle at or below the authored 75 Hz source budget without visible idle judder, live Bubble to return to its existing cadence/reactivity, and Display 0 / Display 1 transition paint to avoid the latest near-`60/40` render and `22-33` paint collapse. Require no new pending-paint requeue, repaint retry, shader/swap/cache fallback, severe **live-playback** latency, or slow `_on_tick` phase owner; paused forced latency probes are diagnostic and must be reviewed separately rather than treated as a live-audio failure.
- [ ] If both displays still collapse while paused overlay input is correctly bounded, add passive child-overlay paint-duration/accepted-update-to-paint attribution and evaluate same-surface compositor ownership as the next structural target. Do not lower playing Bubble cadence, drop accepted repaint requests, subscribe visualizer work to transition `AnimationManager`, or add UI timers/retries without new evidence.

### Deprecated Blob End-To-End Removal

- [ ] Inventory every Blob-owned dev gate, default/descriptor, settings field/control, preset, runtime builder/binding, shader/asset, package rule, log route, test, and documentation reference. Treat the current 267 collected tests and 115-file / 5,955-match footprint as deletion scope, not a repair queue; shared visualizer/audio/animation/compositor behavior is frozen unless removal proves a direct dependency.
- [ ] Add the migration seam first: a saved Blob mode must resolve once to the registry-owned supported default, obsolete Blob keys must be stripped without being re-emitted, and normal/MC imported settings plus generated defaults must remain valid. Preserve only absence/migration tests that protect supported modes.
- [ ] Remove Blob implementation and its dedicated test corpus end to end, then remove the temporary default pytest skip and `--run-deprecated-blob-tests` escape hatch. A repository-wide search may retain only explicit historical migration notes; startup, settings, presets, packaging, synthetic audio, and the focused supported-visualizer reactivity lock must pass without Blob fixtures or branches.

### Widget And Visual Timing Runtime Bar

- [ ] In a fresh normal and MC compiled run, validate Achievement Pulse's default `140 x 196` Portrait art at `600 x 334`: left/right padding matches the family rails, header/art alignment stays exact, `Unlocked` remains six authored pixels below art and renders complete high counts without ellipsis in Portrait/Wide/Square/art-off, and the 40px achievement icon occupies the prior-unlock lane without narrowing the primary unlock title. Long game/latest/prior names must shrink before elision while preserving game >= latest >= prior font size; the first capsule rail retains its measured gap, and 140/190 width changes, high DPR, large capsule font, settings rebuild, and Custom scaling do not clip or rearrange content. With two recent games whose play order and latest-unlock order disagree, require Most Recent, Previous, and Settings labels to follow the newest positive unlock timestamp while missing timestamp evidence falls back stably.
- [ ] Run solid-bar Spectrum with `--viz --perf` through quiet/dropout material and at least one image transition: the 2026-07-14-style coherent input collapse must decay/recover without a brief zero flash or delayed-frame snap, while ordinary smoothing remains visually unchanged and logs show no new timer/repaint/audio-floor pressure.
- [ ] Run the analogue clock with seconds visible for several minutes in normal and MC builds: require discrete six-degree second ticks with matching one-second minute/hour progression, no semi-smooth pause/jump interpolation, and unchanged shared clock-ticker/paint cadence. At a clearly non-default CUSTOM scale, switch digital/analogue through Settings and double-click in both directions and restart each time; require mode-appropriate centered geometry, scale, position, and display route to survive while `--geo` payloads contain only `font_size` plus `geometry_variant`, never behavior-authoritative `display_mode`.

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
- [ ] Oscilloscope, Sine Waves, Bubble, and Dev Curve visual behavior remains accepted. The active paused-source cadence correction above is shared scheduling work and must not become mode-owned retuning. Reopen mode visuals only with fresh `--viz` evidence. Spectrum is temporarily covered by the active rare-dropout runtime bar above.
- [ ] Media metadata preservation during live visualizer preset churn: if it reopens, first suspect partial same-track playback snapshots during visualizer-only settings writes.
- [ ] Steam Journey and Friend Pulse remain production-hidden until each is explicitly promoted beyond `--devsteam`; Journey's next gate is editorial classification/noise/request-budget evidence, not transport discovery.

## Deferred / Not Active

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
