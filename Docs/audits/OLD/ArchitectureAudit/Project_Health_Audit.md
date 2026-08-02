# Project Health Audit

Last updated: 2026-07-01

Document-first audit of SRPSS runtime health, contract drift, stale tests, and long-term prevention work.

This is not a changelog. Use it when deciding what high-value cleanup or hardening work should come next across compositor/rendering, fades/startup timing, timers, settings, legacy seams, and regression prevention.

## Scope

- compositor and display startup/rebuild ownership
- overlay fade and staged-startup timing
- timer / delayed-callback ownership
- settings mutation contracts
- lifecycle split and dead compatibility seams
- fallback usage and logging hygiene
- outdated but valuable tests worth repairing
- long-term codebase health and prevention bars

## Working Rules

- Prefer root-cause cleanup over more runtime mitigations.
- Keep fallbacks loud and attached to an existing CLI family.
- Treat `Spec.md` as the architecture owner, `Index.md` as the live map, `Current_Plan.md` as active checklist only, and `Docs/Historical_Bugs.md` as dated anti-regression evidence.
- When a seam is user-visible and repeatable in principle, strengthen automation before asking for more runtime runs.
- Do not “optimize” settings, timers, or startup by bypassing persistence, lazy-build, or first-frame contracts.
- Before touching shared visualizer/audio/activation/render/transition seams, run the visualizer reactivity lock from [Docs/Harness_Index.md](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/Docs/Harness_Index.md). `Spectrum`, `Sine Waves`, `Bubble`, `Dev Curve`, and `Oscilloscope` currently have accepted runtime behavior; stale Bubble oracle expectations must be re-baselined instead of used as permission to change Bubble feel.

## Confirmed Findings

### F-01. Lifecycle ownership is still split across two live contracts

- Severity: `High`
- Likely reward: `High`
- Risk if changed carelessly: `High`
- Evidence:
  - [rendering/widget_setup_all.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/widget_setup_all.py) `_start_widgets()` still prefers `initialize()` / `activate()` but then falls back to `start()`.
  - [rendering/widget_manager.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/widget_manager.py) `activate_all_widgets()` is explicitly marked dormant.
  - [widgets/base_overlay_widget.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/widgets/base_overlay_widget.py) still maintains legacy `_enabled` state alongside lifecycle state.
  - Multiple widgets such as [widgets/media_widget.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/widgets/media_widget.py), [widgets/weather_widget.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/widgets/weather_widget.py), [widgets/reddit_widget.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/widgets/reddit_widget.py), and [widgets/gmail_widget.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/widgets/gmail_widget.py) implement both `_activate_impl()` and legacy `start()/stop()/cleanup()` paths.
- Why this matters:
  - it creates two activation truths for timers, cache reloads, fade timing, and “running” flags
  - it makes settings-close, runtime rebuild, and reuse bugs much harder to reason about
  - old tests such as [tests/test_widget_lifecycle.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tests/test_widget_lifecycle.py) currently encode the dormant split as if it were the intended long-term state
- Best direction:
  - converge on one live activation contract instead of keeping “new lifecycle but old start path” indefinitely
  - if migration risk is too high for one pass, first create parity bars that prove `start()` and `activate()` do the same meaningful work for the chosen widget slice

### F-02. Weather cache authority split

- Severity: `High`
- Likely reward: `High`
- Risk if changed carelessly: `Medium`
- Status: `Implemented`
- Evidence:
  - [widgets/weather_widget.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/widgets/weather_widget.py) now routes constructor startup and lifecycle `_initialize_impl()` through one `_load_startup_cache()` path.
  - `_cleanup_impl()` clears `_cached_data` and `_cache_time`.
  - provider-backed stale cache lives separately in [weather/open_meteo_provider.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/weather/open_meteo_provider.py).
- Why this matters:
  - if widget-local persisted cache is missing or invalid but provider cache exists, a recreated widget can behave worse than a cold-created widget
  - this matches the class of “blank now, restores later” behavior the user has been seeing
- Guard:
  - [tests/test_weather_widget.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tests/test_weather_widget.py) covers provider-cache recovery when widget-local cache mismatches and when lifecycle initialize reloads the startup cache.
- Remaining watch:
  - keep stale display truth available until fresh provider data replaces it

### F-03. Visualizer CUSTOM recovery remains a loud safety net; settings-return stale buckets reopened narrowly

- Severity: `High`
- Likely reward: `High`
- Risk if changed carelessly: `High`
- Status: `Ordinary edit/save geometry is watchlist; settings-return stale-bucket creation suppression is active`
- Evidence:
  - [rendering/widget_setup_all.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/widget_setup_all.py) still carries:
    - immediate saved-layout reapply
    - delayed verify/confirm stabilization
    - remote custom visualizer fallback recheck
    - creator-time invalid `Custom+ALL` route repair
  - `Docs/Historical_Bugs.md` still lists `U-09` as unresolved.
  - the 2026-06-27 long `--geo` run showed the user-facing recovery seam behaving as intended: the visualizer could be recovered into an editable rect instead of being removed from all displays
  - the same run still emitted loud `[CUSTOM_LAYOUT][FALLBACK] Repaired spotify_visualizer CUSTOM save route...` warnings at `16:48:38` and `16:50:09`, followed by correct replay of the repaired rect
  - the preserved 2026-06-28 evidence at `.tmp/perf_collapse_evidence_20260628_164113` shows ordinary `spotify_visualizer` edit/save/replay cycles without save-route repair fallback, duplicate-owner fallback, or requested-monitor fallback
  - the 2026-06-29 preserved run at `.tmp/perf_collapse_evidence_20260628_164113/20260629_0417_settings_return_collapse` reopened a narrower seam: settings return suppressed visualizer creation because `spotify_visualizer` was routed to concrete monitor `2` while the only saved visualizer rect lived under a stale/foreign display bucket
  - the same run proved the rect data was not gone: the media recovery button found `source=saved_foreign_visualizer_centered`, and after recovery/save the later settings return recreated the visualizer on screen `1`
- Why this matters:
  - the safety net still exists and must remain loud, but the fresh failure is not a general rect replay failure; it is a display-bucket authority repair problem during settings/startup creation
  - every new patch in this area risks churn, first-frame poisoning, or another false correction unless a fresh failure reopens the ownership map
  - recovery paths that fire during intentional rescue are acceptable; recovery paths that fire during ordinary settings return, edit/save, or startup are reopen evidence unless they repair once and disappear after persistence
- Best direction:
  - keep the existing recovery affordance as the user escape hatch, but do not require it for a uniquely recoverable stale-bucket settings return
  - allow a single stale visualizer rect to be promoted only when the requested concrete monitor is active and matches the current display; keep absent/ambiguous/wrong-monitor foreign rects rejected
  - persist the repaired bucket so the fallback stops repeating
  - keep the dedicated Geo audit as historical/watchlist evidence
  - do not add more recovery layers unless fresh logs show route repair, duplicate ownership, impossible shape, repeated stale-bucket repair, or replay/runtime divergence again

### F-04. Authoritative delayed work is still spread across too many raw one-shot timers

- Severity: `Medium`
- Likely reward: `High`
- Risk if changed carelessly: `Medium`
- Evidence:
  - raw `QTimer.singleShot(...)` remains scattered across rendering, startup, settings, and widget glue
  - examples include:
    - [rendering/widget_manager.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/widget_manager.py)
    - [rendering/display_overlays.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/display_overlays.py)
    - [rendering/widget_setup_all.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/widget_setup_all.py)
    - [rendering/custom_layout_manager.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/custom_layout_manager.py)
    - [ui/settings_dialog.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/ui/settings_dialog.py)
  - shared timer ownership has improved through [widgets/overlay_timers.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/widgets/overlay_timers.py) and [widgets/service_widget_runtime.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/widgets/service_widget_runtime.py), but adoption is partial.
  - [rendering/custom_layout_manager.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/custom_layout_manager.py) edit-shell global restack scheduling now routes through `ThreadManager.single_shot(...)` and keeps coalescing/menu-deferral guards in [tests/test_custom_layout_manager.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tests/test_custom_layout_manager.py).
  - [widgets/base_overlay_widget.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/widgets/base_overlay_widget.py) CUSTOM geometry reapply scheduling now routes through `ThreadManager.single_shot(...)`; the regression bar also caught and prevents self-reschedule churn while enforcing the committed rect.
  - [widgets/spotify_volume_widget.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/widgets/spotify_volume_widget.py) CUSTOM geometry reapply scheduling now routes through `ThreadManager.single_shot(...)` with a coalescing guard for dependent-volume rect correction.
  - [rendering/widget_manager.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/widget_manager.py) deferred Spotify dependent visibility sync now routes through `ThreadManager.single_shot(...)` and keeps its duplicate-request coalescing under test.
  - [rendering/gl_compositor_pkg/transitions.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/gl_compositor_pkg/transitions.py) no longer falls back to a private `QTimer.singleShot(...)` for desynced transition starts; missing display-local scheduler state now routes through the ThreadManager seam loudly.
- Why this matters:
  - UI-local cosmetic delays are fine
  - authoritative retries, visibility reveals, post-startup stabilizers, and rebuild/self-heal paths are much riskier when scattered and tokenized inconsistently
- Best direction:
  - classify delayed work into:
    - UI-only convenience
    - widget-local recurring ownership
    - authoritative runtime retry/reconcile
  - only migrate the third class aggressively
  - keep UI-local scroll restore / notice auto-hide style shots local unless they are causing real trouble

### F-05. Silent authoritative settings writes are still a risk seam

- Severity: `Medium`
- Likely reward: `Medium`
- Risk if changed carelessly: `Medium`
- Evidence:
  - allowed `emit_change=False` widgets-map writes are now documented in [Docs/Contracts.md](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/Docs/Contracts.md) and the `SettingsManager.set_widgets_map()` docstring.
  - `emit_change=False` writes still occur in runtime-authoritative flows such as:
    - [rendering/custom_layout_manager.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/custom_layout_manager.py)
    - [rendering/spotify_widget_creators.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/spotify_widget_creators.py)
    - [ui/tabs/widgets_tab.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/ui/tabs/widgets_tab.py)
  - `set_many()` in [core/settings/settings_manager.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/core/settings/settings_manager.py) is still a plain loop of individual writes/signals rather than a formal batch mutation contract.
- Why this matters:
  - some silent writes are correct and necessary
  - but without a documented contract they are easy to misuse, especially in geometry/runtime repair paths where saved-file truth and in-memory runtime truth can drift
- Best direction:
  - document exactly when silent writes are allowed
  - prefer named helper paths such as `set_widgets_map(..., emit_change=False)` over ad hoc silent key writes
  - consider a future explicit batch mutation context only if real evidence shows settings storms, not as speculative optimization

### F-06. Test-suite drift is no longer just cosmetic

- Severity: `Medium`
- Likely reward: `High`
- Risk if changed carelessly: `Low`
- Evidence:
  - [tests/test_rss_behavior.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tests/test_rss_behavior.py) now covers the current RSS facade/current pipeline contract after repair.
  - retired Pan & Scan integration shells were removed instead of kept as permanent skips: `tests/test_pan_scan_integration.py` and `tests/test_transitions_integration.py`
  - several transition tests are still skipped because they require a live compositor-attached widget, e.g. [tests/test_block_puzzle_flip.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tests/test_block_puzzle_flip.py)
  - [tests/test_qt_timer_threading.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tests/test_qt_timer_threading.py) now covers overlay timer stop-thread routing through a deterministic fake owner-thread seam instead of the old flaky real event-loop cleanup path.
  - [tests/test_thread_manager.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tests/test_thread_manager.py) no longer carries the duplicate flaky overlay-timer warning test.
  - [tests/test_widget_lifecycle.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tests/test_widget_lifecycle.py) now covers lifecycle-first startup arbitration instead of blessing the dormant split contract.
- Why this matters:
  - some skips are honest and fine
  - others are hiding valuable regression surfaces that the project still cares about
  - lifecycle-migration work will be harder if tests keep blessing the split contract
- Best direction:
  - retire tests for removed features
  - repair tests for live features whose implementation changed
  - replace environment-heavy skips with narrower logic/harness coverage where possible
  - split current-good visualizer mode locks from stale or exploratory visualizer tests so Bubble/Spectrum/Sine/DevCurve do not get destabilized by unrelated cleanup

### F-06b. Current-good visualizer modes need an explicit reactivity lock before shared work

- Severity: `High`
- Likely reward: `High`
- Risk if changed carelessly: `High`
- Evidence:
  - fresh runtime logs show visualizer activation/generation and CUSTOM replay behaving sanely in the latest run
  - `Bubble` perf still produces occasional `dt spike_ms` warnings, but the accepted visual behavior is currently much better than the stale oracle history suggests
  - the user explicitly classifies `Spectrum`, `Sine Waves`, `Bubble`, `Dev Curve`, and the latest fixed `Oscilloscope` path as currently reacting correctly
  - the focused current-good lock is green, while the broad visualizer suite still contains stale Bubble expectations, old Sine UI doubles, exact-bucket settings tests, and stale doc-reference requirements
  - one broad-suite failure was a real hard exception: `BubbleSimulation.tick(None, ...)` left pulse values uninitialized; that path is now fixed without retuning Bubble behavior
- Why this matters:
  - lifecycle, timer, transition, cache, and compositor work can all accidentally pass through shared visualizer seams
  - stale Bubble oracle failures have repeatedly encouraged unnecessary Bubble behavior changes; that pattern must stop
- Best direction:
  - keep a focused reactivity lock command in [Docs/Harness_Index.md](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/Docs/Harness_Index.md)
  - run it before and after any shared visualizer-affecting change
  - re-baseline stale Bubble and old UI-doubled bars against accepted runtime feel, but do not tune visualizer visuals/reactivity unless new runtime evidence shows a real regression

### F-07. Documentation drift is real enough that it needs active maintenance, not occasional cleanup

- Severity: `Medium`
- Likely reward: `Medium`
- Risk if changed carelessly: `Low`
- Evidence:
  - this audit began with a live contradiction between canonical docs and defaults: `Spec.md` / `Docs/Guardrails.md` still said authored stacking defaulted off while canonical defaults already shipped `widgets.global.stacking_enabled = True`
  - exported settings examples under `Docs/` still show stale mute-button default values
- Why this matters:
  - wrong defaults in canonical docs create false audit conclusions and bad future fixes
  - stale example payloads are easy to mistake for active truth
- Best direction:
  - keep canonical defaults synced in `Spec.md` / `Guardrails.md`
  - either regenerate or clearly label stale example payloads as historical/non-canonical

### F-08. Legacy/compatibility seams exist in three very different classes and should not be treated the same

- Severity: `Low`
- Likely reward: `Medium`
- Risk if changed carelessly: `Medium`
- Evidence:
  - likely removable debt:
    - retired-feature skipped tests
    - comments and wrappers still describing intentionally dead patterns
    - stale cross-feature imports, such as the removed Reddit user-agent helper that Imgur scraping still referenced before this cleanup
  - likely quarantine-only compatibility:
    - [rendering/gl_compositor_pkg/__init__.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/gl_compositor_pkg/__init__.py)
    - `DisplayWidget.set_image()` legacy synchronous path in [rendering/display_widget.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/display_widget.py)
  - currently active but misleading “legacy” surfaces:
    - `_enabled` fields on overlay widgets
    - `start_legacy()` / `stop_legacy()` helpers in [widgets/spotify_visualizer/startup_staging.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/widgets/spotify_visualizer/startup_staging.py)
    - `core/lifecycle.py` protocol naming versus the richer `BaseOverlayWidget` lifecycle
- Why this matters:
  - “legacy” currently means everything from harmless compatibility to active split ownership
  - without classification, cleanup efforts either remove the wrong thing or leave the dangerous things untouched

### F-09. Compositor / GL improvement work has real upside, but a broad FBO rewrite is not yet justified

- Severity: `Medium`
- Likely reward: `Medium` to `High`
- Risk if changed carelessly: `High`
- Evidence:
  - the compositor already has hidden shared offscreen-context warmup support in [rendering/gl_compositor_pkg/gl_lifecycle.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/gl_compositor_pkg/gl_lifecycle.py)
  - startup/overlay prewarm still relies on expensive framebuffer-realization paths in places such as:
    - [widgets/spotify_bars_gl_overlay.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/widgets/spotify_bars_gl_overlay.py) `grabFramebuffer()` prewarm fallback
    - [transitions/overlay_manager.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/transitions/overlay_manager.py) `prepare_gl_overlay(..., grab_framebuffer=True)`
  - first-frame presentation still uses an explicit flush/repaint/single-shot completion path in [rendering/display_image_ops.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/display_image_ops.py)
  - viewport sizing still carries a suspicious `h + 1` adjustment in [rendering/gl_compositor_pkg/shader_dispatch.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/gl_compositor_pkg/shader_dispatch.py), which may be a valid compatibility hack but is not yet documented as one
- Why this matters:
  - there are likely real churn/perf wins in reducing framebuffer grabs, tightening prewarm sequencing, and proving DPR/viewport truth
  - but a wholesale “move everything to an FBO/render-to-texture compositor” pass is high-risk because:
    - `QOpenGLWidget` already renders through an internal backing FBO
    - the project has prior corruption history from a failed FBO attempt
    - first-frame, transition correctness, and overlay/card fidelity are more important than architecture neatness
- Best direction:
  - treat full explicit FBO compositing as a future experiment only after bounded seam audits and bars exist
  - focus near-term work on:
    - reducing expensive framebuffer-grab prewarm fallbacks
    - extending safe offscreen warmup where it clearly avoids live-surface churn
    - documenting and testing viewport/DPR quirks before anyone “cleans them up”
    - measuring transition texture-upload churn and first-use shader/resource prep more directly

### F-10. Cache fallback diagnostics exposed prefetch scheduling bugs

- Severity: `High`
- Likely reward: `High`
- Risk if changed carelessly: `Medium`
- Status: `Implemented through startup scheduling-order fix; fresh runtime validation pending`
- Evidence:
  - earlier `--cache` fallback warnings included prefetch state such as `raw_inflight:0`, `scaled_inflight:0`, and growing `scaled_pending` counts while fallback remained `scaled_miss raw_state=raw_missing`
  - that was different from an overloaded-worker shape; pending work existed while no worker lane was active
  - the 2026-06-27 `--cache` run showed the next lost-wakeup shape: scaled warmup requests were prepared, but registration was skipped during post-transition cooldown and the later resume could fire just before the prefetcher cooldown actually expired
  - [utils/image_prefetcher.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/utils/image_prefetcher.py) now preserves raw/scaled prefetch intent through post-transition cooldown while keeping dispatch paused, so cooldown no longer destroys the producer registration needed after transition pressure clears
  - [utils/image_prefetcher.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/utils/image_prefetcher.py) now also refuses scaled warmup entries for raw paths that are neither cached nor actually in-flight
  - [engine/image_pipeline.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/engine/image_pipeline.py) logs the accepted scaled warmup count instead of the prepared count, so `--cache` no longer overstates queued work
  - the 2026-06-22 20:49-20:51 `--cache` run confirmed the old idle-pending shape was gone, but showed the next scheduling bug: each preview prepared 5 scaled warmups, registered only 2, and skipped 3 because [utils/image_prefetcher.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/utils/image_prefetcher.py) stopped raw prefetch scheduling at `max_concurrent` instead of retaining a raw-producer backlog
  - [utils/image_prefetcher.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/utils/image_prefetcher.py) now keeps a bounded raw backlog: active raw IO remains capped, but the rest of the preview window stays queued as real producers and scaled warmups may wait behind them
  - [engine/image_pipeline.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/engine/image_pipeline.py) now includes `raw_pending` in loud cache fallback diagnostics so future logs can distinguish queued raw work from absent producer work
  - [tests/test_image_prefetcher.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tests/test_image_prefetcher.py) covers pending-idle prevention, no-raw-producer refusal, and full-preview raw backlog behavior
  - [tools/transition_perf_health_parser.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tools/transition_perf_health_parser.py) now fails the newer zero-producer fallback shape directly
  - [engine/image_pipeline.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/engine/image_pipeline.py) keeps the delayed post-transition prefetch resume armed while another display still reports transition work pending, and rearms again if the prefetcher cooldown has not actually expired, covered by [tests/test_image_pipeline.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tests/test_image_pipeline.py)
  - the 2026-06-27 long `--cache` run still showed one zero-producer fallback at `16:45:43`: `raw_inflight:0,raw_pending:0,scaled_inflight:0,scaled_pending:0`
  - the latest preserved `--cache` sidecar showed a stronger startup pattern: first scaled fallbacks had no registered raw or scaled producers because the initial prefetch was scheduled before displays exposed target sizes
  - [engine/screensaver_engine.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/engine/screensaver_engine.py) now constructs cache/prefetcher after queue build but schedules the first display-sized prefetch only after display creation
  - [tests/test_engine_lifecycle.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tests/test_engine_lifecycle.py) guards the ordering: cache construction, display creation, then first prefetch scheduling
- Why this matters:
  - repeated fallback display during transitions costs perf and can force lower-quality or delayed visual output
  - the wrong fix would move decode/scale pressure onto the UI thread or add synchronous retries, both of which violate project guardrails
- Best direction:
  - runtime-check the next `--cache` run for no startup/early zero-producer scaled fallback before reopening promotion/cancellation/wakeup ownership
  - if zero-producer fallback survives the startup-order fix, inspect cache promotion, cancellation, and worker wakeup ownership with the `raw_pending` evidence instead of repeating the old idle-pending, first-two-only backlog, cooldown lost-wakeup, or pre-display-target hypotheses
  - keep the cache/pipeline bars that fail when scaled warmup can enqueue without an active raw/scaled producer
  - keep all fallback diagnostics loud under `--cache`

### F-11. Shader fallback diagnostics exposed a deferred-start contract ambiguity

- Severity: `High`
- Likely reward: `Medium`
- Risk if changed carelessly: `High`
- Status: `Diagnostic guard implemented; deferred-start token contract implemented; fresh-log confirmation needed`
- Evidence:
  - newest logs showed `GLCompositorRainDropsTransition` starting and then repeated `[GL PAINT] All shader paths failed` messages for dozens of frames
  - the prior log only proved that fallback happened; it did not say whether the active shader path failed capability checks, texture prep, or a render exception
  - [rendering/gl_compositor_pkg/shader_dispatch.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/gl_compositor_pkg/shader_dispatch.py) now records the active shader failure reason
  - [rendering/gl_compositor_pkg/paint.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/gl_compositor_pkg/paint.py) now emits one loud `[GL PAINT][FALLBACK]` record per repeated failure signature, including active transition names and the last failure reason
  - [tests/test_gl_shader_fallback_diagnostics.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tests/test_gl_shader_fallback_diagnostics.py) prevents regression to blind spam or silent fallback
  - [transitions/gl_compositor_raindrops_transition.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/transitions/gl_compositor_raindrops_transition.py) now treats Rain Drops as shader-owned: no compositor or failed shader start returns a loud failure instead of reporting a diffuse/immediate-display substitute as success
  - [rendering/display_image_ops.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/display_image_ops.py) now logs transition start refusal/failure at `ERROR` with screen, transition, and overlay identity before displaying the final image
  - [rendering/gl_compositor_pkg/transitions.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/gl_compositor_pkg/transitions.py) now returns an explicit deferred token for desynced compositor starts, so a real delayed Rain Drops start is not misreported as unavailable merely because the animation id is not created until the delayed callback runs
  - [rendering/display_image_ops.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/display_image_ops.py) replaced the stale compositor-prewarm handwritten widget raise list with the owner-based runtime-widget raise helper and reuses that helper after true transition refusal
- Why this matters:
  - fallback usage must stay loud, but per-frame log spam hides the useful signal and can make performance logs harder to interpret
  - a thrown shader exception can demote the compositor shader pipeline for the session, so RainDrops/Diffuse failure classification matters before changing GL behavior
- Best direction:
  - next logs should show either a real shader/deferred start or a clean transition refusal; if Rain Drops still reaches `[GL PAINT][FALLBACK]`, inspect compositor shader capability/warmup instead of restoring a substitute path
  - if future failures are texture-prep related, inspect texture ownership and warmup timing before touching shader code
  - if future failures are exception-related, fix the transition/program path directly and keep session-level demotion loud
  - do not downgrade the fallback warning or switch to a silent software/legacy path

### F-12. Transition/display FPS asymmetry is now the top performance seam

- Severity: `High`
- Likely reward: `High`
- Risk if changed carelessly: `High`
- Evidence:
  - the 2026-06-27 long `--perf` run shows Display 0 render timer metrics staying near `164.7-165.0fps` with `target=165Hz` while `GL PAINT` often lands around `75-80fps`, occasionally around `52-68fps`, and later sometimes improves only to roughly `96-113fps`
  - the same run shows `GL ANIM` as a separate cadence: some Display 0 windows stay healthy around `130-150fps`, while later windows can fall near `60-62fps` even when `GL PAINT` is higher
  - Display 1 still shows true 60Hz under-target windows, including roughly `39-45fps` animation cadence during some transitions
  - the 2026-06-28 post-timer-yield run validates the win from removing the adaptive timer busy-spin: high-refresh near-60 paint windows dropped to `0`, paired render-healthy/paint-starved windows dropped to `14`, visualizer timing warnings dropped to `64`, and high-refresh animation/control callback collapse dropped to `3`
  - the same 2026-06-28 run exposed a separate lifecycle bug: two adaptive timer tasks created during a settings/display rebuild stayed active until `ThreadManager` shutdown timed out, matching late lazy compositor animation callbacks that can start render timers after `stop_rendering()`
  - the 2026-07-01 display-cycle run sharpened that lifecycle bug: the app reached `ShittyRandomPhotoScreenSaver Exiting (code=0)`, but `ThreadManager` still timed out on an older `adaptive_timer_*` task from an earlier display generation, so Python stayed alive until manually killed
  - [rendering/adaptive_timer.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/adaptive_timer.py) now waits on a loop-stopped acknowledgement before dropping adaptive-timer ownership, and [core/threading/manager.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/core/threading/manager.py) registers active-task truth before executor submission so fast completions cannot leave stale active entries
  - GL render timer, GL paint, and GL animation metrics disagree in key windows, which points toward timer/event-loop/paint-cadence ownership rather than one simple shader cost
  - compositor context init logs `swap=SwapBehavior.DoubleBuffer, interval=1` while the project render timer still targets `165Hz` on Display 0; this is not proof of a swap/update-delivery lock by itself, but it is now a first-class suspect after display rebuild/edit-save paths
  - visualizer tick latency clusters around transition windows, especially `devcurve` and `oscilloscope`; the same run does not show evidence of simultaneous duplicate visualizer creation, but duplicate owner/worker/overlay checks must remain part of the first investigation
  - cache fallbacks still appear with `raw_inflight:0,raw_pending:0,scaled_inflight:0,scaled_pending:0`, meaning some transition images miss the warmup window entirely
  - the preserved 2026-06-28 evidence at `.tmp/perf_collapse_evidence_20260628_164113` is the current compact collapse sample: Display 0 `GL RENDER` remains near `164.8fps` while `GL PAINT` lands around `91-117fps`, Display 0 `GL ANIM` falls near `61-62fps` for several later transitions, and Display 1 `GL ANIM` falls around `39fps` for Raindrops/Wipe/Blockspin
  - the same preserved cache log has two Display 1 zero-producer scaled-miss fallbacks at `16:32:33` and `16:36:10`
  - the 2026-06-27 log showed multiple random transition choices prepared for one rotation/startup batch, explaining why one display could report `Diffuse` while another display used `Ripple`
  - [engine/screensaver_engine.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/engine/screensaver_engine.py) now makes `_show_next_image()` the single random-transition choice owner for an image batch; `start()` and `_on_rotation_timer()` no longer prepare additional random choices around the same display update
  - a GC pause of roughly `132ms` appears in the latest run; it can explain spikes, but not sustained near-60 behavior by itself
  - [tools/transition_perf_health_parser.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tools/transition_perf_health_parser.py) now flags high-refresh near-60 windows, stable high-refresh divisor/cadence windows, render/paint split windows, 60Hz under-target windows, AnimationManager under-target windows, pending-paint requeue rescues, zero-producer cache fallbacks, and shader fallbacks
  - the parser now keeps long completed `AnimationManager` under-target runs red even when `active_count=0`; the older interpretation was too soft because transition metrics can finish with `active_count=0` while still proving a multi-second control-callback cadence collapse
  - the 2026-07-01 `18:46` evidence narrowed the fresh active shape: no pending-paint requeues, shader fallbacks, cache worker fallbacks, or 60Hz under-target display windows appeared, but `Raindrops` on Display 0 still showed high-refresh paint under-delivery around `80fps` and later `69-74fps`
  - [rendering/adaptive_timer.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/adaptive_timer.py) now records accepted update submissions separately from raw timer wakeups, and [tools/transition_perf_health_parser.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tools/transition_perf_health_parser.py) flags `pending_skips` so coalesced update pressure is not misread as healthy render cadence
  - `AnimationManager` perf logs now include passive `listeners=` counts so future `--perf` runs can distinguish listener pressure from generic event-loop/manager delivery starvation without queueing more UI work
  - `FrameState` paint interpolation previously extrapolated from the last two `AnimationManager` samples, so high-refresh paint frames could still be visibly tethered to a low-cadence callback stream; it now has a paint-authoritative elapsed-time/easing timeline while `AnimationManager` keeps completion/callback ownership
  - [tests/test_frame_interpolator.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tests/test_frame_interpolator.py) now fails if paint-time progress cannot outrun stale samples, or if delayed animations advance before the authored delay boundary
  - [tools/spotify_vis_metrics_parser.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tools/spotify_vis_metrics_parser.py) now loads the sibling `tools/slide_metrics_parser.py` directly instead of a stale `scripts.slide_metrics_parser` path, so visualizer metrics can be parsed from current logs again
  - the 2026-06-29 post-`FrameState` evidence at `.tmp/perf_collapse_evidence_20260628_164113/20260629_154319_post_framestate_collapse` shows no pending-paint requeues, shader fallbacks, cache fallbacks, CUSTOM visualizer suppression, or slow GL uploads; the active shape is narrower now: Display 0 has render-healthy/paint-under-delivered windows, while Display 1's suspicious `~40fps` signature is `GL ANIM` / AnimationManager control cadence rather than visible `GL PAINT`
  - a startup/rebuild seam was found in the same pass: the old multi-display stagger preserved load spreading by pumping `QCoreApplication.processEvents()` inside display initialization. That can let unrelated settings/edit/UI work run inside a sensitive rebuild boundary. Display startup now keeps stagger through owned `ThreadManager.single_shot(...)` scheduling with stale-generation suppression.
  - `AnimationManager` perf metrics now include peak active/listener counts for the sampled run, and the parser flags under-target windows with `max_active=0,max_listeners=0` as idle/no-work timer churn. This prevents completed transitions from being confused with genuinely stray manager timers.
  - the 2026-06-27 parser pass over `screensaver_perf.log` flagged high-refresh near-60 paint windows, high-refresh divisor/split paint windows, high-refresh far-under-target paint windows, 60Hz under-target windows, and 83 Spotify visualizer timing warnings; the parser still needs a concise timeline that correlates render, paint, animation, lifecycle, GC, and cache state
  - the attempted bounded active-transition pending-paint requeue guard has been rejected: the latest runtime fired `134` pending-paint rescues, materially worsened cadence/churn, and did not solve the high-refresh paint deficit
  - the latest runtime also shows slow GL texture uploads (`20-47ms`), one real MediaWidget smart-poll gap, and a slow Widgets settings tab build around `2609ms`; these are contributors/suspects, not permission to add UI-thread repaint or upload retries
- Why this matters:
  - the project has historically reached mixed-refresh output much closer to `165/60`
  - a display that still reports `target_fps=165` but renders near `60fps` is an ownership bug until proven otherwise
  - optimizing a single transition or visualizer mode could miss a shared timer/paint cadence flaw and risk current-good visualizer behavior
- Best direction:
  - extend the parser only where useful for the active cadence-lock question; do not turn it into a broad dashboard before it answers why suspicious divisor/60-ish behavior appears and disappears
  - correlate per-display target, render timer FPS, GL animation FPS, GL paint FPS, transition type, visualizer mode, tick latency, cache fallbacks, GC events, display rebuilds, settings close, and edit-mode save/re-entry
  - keep the random-transition seam classified as currently improved unless fresh logs show conflicting choices again; current tests cover one random choice per accepted image batch and concrete transition warmup after that choice is resolved
  - runtime-check the compositor lifecycle fix with `--life` and `--perf`: no adaptive timer tasks should survive display cleanup/exit, no post-stop adaptive frame signalling should appear, no late deleted-`GLCompositorWidget` callback should fire, and no `[PERF][ADAPTIVE_TIMER][FALLBACK] Stop timed out...` warning should appear
  - runtime-check the `FrameState` timeline fix with `--perf`: suspicious `GL ANIM` callback cadence may still appear as diagnostic evidence, but it should no longer cap shader-visible transition progress when `GL PAINT` is delivering frames
  - runtime-check the no-`processEvents` display-startup rebuild pass with `--perf --life --set`: delayed display shows should not survive cleanup, settings/edit rebuilds should not pump arbitrary UI work, and any remaining `GL ANIM` collapse should include enough `owner=` / `listeners=` detail to classify shared/settings/display manager ownership
  - use the new peak-count metrics to distinguish slow completed transition managers from idle manager churn before changing animation cadence or timer ownership
  - prove whether the near-60 Display 0 behavior is:
    - a timer target mutation
    - Qt paint/update-delivery cadence lock
    - timer wakeups being coalesced behind a still-pending paint update
    - event-loop starvation
    - shared animation-manager pacing
    - hidden duplicate visualizer/overlay/tick work
    - a display-recreate state leak where edit/settings paths restore render-timer target but not paint/swap cadence equivalently
  - classify `GL ANIM` separately from `GL PAINT`: an AnimationManager control-callback cadence near 60 is not automatically the same as visible paint collapse, but it can still reveal shared-manager leakage, listener pressure, or event-loop starvation
  - on the next long run, split suspicious `GL ANIM` windows by listener count: `listeners=0` points toward manager/event-loop delivery or lifecycle churn, while `listeners>0` makes visualizer tick-listener pressure a first-class suspect
  - keep all changes off the UI thread and preserve first-frame / last-frame transition correctness

### F-13. Digital Clock still has a live text-measurement wobble seam

- Severity: `Medium`
- Likely reward: `Medium`
- Risk if changed carelessly: `Medium`
- Evidence:
  - latest `--geo` logs show two digital clock CUSTOM rects replaying correctly, but Display 0 uses a larger flush-left rect (`local=(0,24,676,196)`, `font_size=109`) while Display 1 uses a smaller inset rect (`local=(24,108,575,167)`, `font_size=92`)
  - user-visible behavior reports Display 0 shrinking/growing/wobbling on numerical changes while Display 1 remains stable
  - earlier fixes solved the common seconds-width wobble, so this is likely an edge case in digital text measurement, frame/background alignment, or per-display/custom replay interaction
  - [tests/test_clock_widget.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tests/test_clock_widget.py) now covers the Display-0-shaped CUSTOM rect across `08:08:08`, `11:11:11`, `18:49:11`, and `23:59:59`
  - [widgets/clock_widget.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/widgets/clock_widget.py) no longer rebuilds the digital stylesheet on every time tick; frame styling is setting-driven instead of second-driven
- Why this matters:
  - a clock should not move or resize because the seconds digits changed
  - the fix must not regress analogue clock sizing, digital clipping, timezone alignment, or CUSTOM runtime double-click swaps
- Best direction:
  - use the next `--geo` run to confirm Display 0 no longer wobbles at runtime
  - if wobble persists despite stable text measurement bars, inspect custom replay/parent geometry writers rather than retuning text fit

### F-14. Oscilloscope visual contract drift is closed to watchlist

- Severity: `Low` watchlist
- Likely reward: `Medium`
- Risk if changed carelessly: `Medium`
- Evidence:
  - the earlier runtime report said Oscilloscope flickered rapidly in brightness and ghosting was not visually obvious
  - the Oscilloscope-owned pass added waveform response, ghost stability, idle/live-boundary, transient-width strobe, and metadata-preservation bars
  - the latest runtime validation reported idle startup/pause behavior acceptable, playback reaction in a good place, line ghost visibility restored through authored decay, and no media metadata wipe during preset cycling
- Why this matters:
  - Oscilloscope is now part of the current-good visualizer lock
  - if it reopens, fixes must remain mode-owned unless a shared seam is proven by a stronger oracle
- Best direction:
  - keep [audits/OscilloscopeAudit/Oscilloscope_End_To_End_Audit.md](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/audits/OscilloscopeAudit/Oscilloscope_End_To_End_Audit.md) as historical/watchlist context
  - do not change shared visualizer audio, floor, or tick behavior for Oscilloscope without fresh `--viz` evidence and a mode-owned failing bar

## Priority Order

1. Adaptive timer exit/lifecycle validation
2. Visualizer reactivity lock and stale-oracle split
3. Transition/display FPS asymmetry investigation
4. Cache/prefetch scheduling drain investigation
5. Lifecycle unification and parity bars
6. Visualizer CUSTOM stale-bucket settings-return validation, with broader geometry watchlist only
7. Digital Clock wobble runtime watch
8. Authoritative one-shot timer classification and migration
9. Settings silent-write contract and batch-write evidence audit
10. Test-suite rehabilitation
11. Compatibility/debris classification and cleanup
12. Bounded compositor / GL churn reduction

## Actionable Checklist

### P0. Adaptive timer exit/lifecycle validation

- [x] Preserve the 2026-07-01 evidence shape: app-level `code=0` exit plus `ThreadManager shutdown timed out` on an old `adaptive_timer_*` task.
- [x] Add loop-stopped acknowledgement to adaptive timer stop and remove render-strategy manager's immediate ownership drop.
- [x] Add a ThreadManager submit race bar so fast executor completion cannot leave a stale active task.
- [ ] Runtime-check the next `--life` / `--perf` exit for:
  - no pending adaptive timer tasks during shutdown
  - no `ThreadManager shutdown timed out`
  - no `[PERF][ADAPTIVE_TIMER][FALLBACK] Stop timed out...`
  - no deleted `GLCompositorWidget` callback spam after display cleanup
- [ ] If the stop-timeout fallback fires, root-cause the display/compositor owner still blocking loop exit rather than adding a force-exit mitigation.

Risk control:
- Do not reintroduce UI pressure, repaint retries, or process-force shutdown as a lifecycle fix.
- Keep the stop wait bounded; it is an ownership handshake, not a cadence mechanism.

### P0. Visualizer reactivity lock

- [x] Keep the focused visualizer lock in [Docs/Harness_Index.md](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/Docs/Harness_Index.md) current and runnable.
- [ ] Before shared visualizer/audio/activation/render/transition changes, run the lock for:
  - `Spectrum`
  - `Sine Waves`
  - `Bubble`
  - `Dev Curve`
  - `Oscilloscope`
- [x] Run the current focused lock and keep it green before the cache/perf implementation pass.
- [x] Fix real non-behavioral breakage exposed by the broad suite: `BubbleSimulation.tick(None, ...)` and stale visualizer doc-reference tests.
- [ ] After any shared visualizer-affecting change, re-run the same lock and compare results.
- [ ] Re-baseline stale Bubble expectations against accepted runtime feel without changing Bubble behavior.
- [ ] Keep broad visualizer-suite failures classified as stale test debt vs real production bug before using them as project-health signals.

Risk control:
- Do not “fix” Bubble/Spectrum/Sine/DevCurve based only on stale proxy expectations.
- Treat visualizer lock failures as stop signs for shared seam work.

### P0. Cache/prefetch scheduling drain pass

- [x] Reproduce or unit-model the `scaled_pending` growth with no active raw/scaled inflight workers.
- [x] Prevent scaled warmup registration during transition cool-down, so scaled pending work cannot be orphaned while raw prefetch is intentionally asleep.
- [x] Add a regression bar for transition cool-down scaled registration that must not create idle pending work.
- [x] Prevent scaled warmup registration for raw paths that are neither cached nor actually scheduled/in-flight.
- [x] Log the accepted scaled warmup count so `--cache` diagnostics reflect real queued work.
- [x] Preserve raw producers for the full preview window with a bounded raw backlog instead of stopping scheduling at `max_concurrent`.
- [x] Add a regression bar so preview windows larger than active IO concurrency retain queued raw producers and scaled warmup requests.
- [x] Add a perf/cache parser bar that flags cache fallbacks where `raw_inflight`, `raw_pending`, `scaled_inflight`, and `scaled_pending` are all zero.
- [x] Keep transition-delayed prefetch resume armed while another display still has transition work pending.
- [x] Preserve raw/scaled prefetch registration intent through post-transition cooldown without dispatching work during the cooldown window.
- [x] Rearm transition-complete prefetch resume until the prefetcher cooldown has actually expired.
- [x] Root-cause the latest startup zero-producer fallback pattern to first prefetch scheduling before displays expose display-sized target specs.
- [x] Schedule the first prefetch after display creation and guard the cache/display/prefetch initialization order.
- [ ] Runtime-check the next `--cache` run for no startup/early zero-producer scaled fallback.
- [ ] Audit cache promotion, cancellation, and worker wakeups if fresh logs still show zero-producer fallbacks after the startup-order fix.
- [ ] Use `.tmp/perf_collapse_evidence_20260628_164113` and the latest `--cache` sidecar as compact repro evidence for zero-producer scaled-miss fallbacks.
- [ ] Keep fallback logs loud under `--cache` and avoid UI-thread decode/scale retries.

Risk control:
- Preserve transition fidelity and first-frame correctness before pursuing raw FPS gains.
- Prefer worker/cache ownership fixes over synchronous fallback paths.

### P0. Transition/display FPS asymmetry pass

- [x] Add the first perf parser/bar that reports:
  - refresh target / configured target FPS
  - GL animation FPS and `dt_max`
  - active transition name
  - GL render timer FPS and `dt_max`
  - AnimationManager FPS and `dt_max`
  - cache fallback producer state
  - shader fallback presence
- [x] Make random transition selection single-owner per image batch so participating displays cannot prepare conflicting transitions around one rotation.
- [x] Confirm the next runtime log has one random choice per image batch and matching transition identity across displays.
- [x] Extend the parser only as needed to add:
  - stable high-refresh divisor/cadence-lock detection
  - render/paint split classification when the timer target remains high but visible paint cadence does not
  - pending-paint requeue rescue warnings
- [ ] Extend the parser later only if needed to add:
  - per-display grouping beyond target-FPS inference
  - GC pauses during the window
- [ ] Use that parser to prove whether the Display 0 near-60 behavior is caused by:
  - target mutation
  - Qt paint/update delivery coalescing
  - shared animation-manager pacing
  - event-loop starvation
  - hidden duplicate visualizer/overlay/tick ownership
- [ ] Separate `GL ANIM` cadence from `GL PAINT` cadence before timer changes:
  - prove each display transition owns the expected target FPS
  - prove app-shared AnimationManager users do not retarget display-local transition managers
  - prove visualizer tick listeners attach/detach without cross-display/shared-manager leakage
- [x] Add a display-local AnimationManager bar proving mixed-refresh transition widgets do not retarget each other's manager FPS.
- [ ] Validate the no-`processEvents` display startup/settings rebuild pass:
  - display startup stagger remains active through owned scheduling, not a UI-pumping delay loop
  - stale delayed shows are suppressed after cleanup/settings/edit rebuild
  - fresh logs classify any remaining Display 0 paint under-delivery or Display 1 `GL ANIM` cadence collapse with `owner=` / `listeners=` / `max_active=` / `max_listeners=` evidence
- [x] Test and reject the bounded active-transition pending-paint requeue guard: the latest runtime produced `134` requeue rescues and worse cadence, so production returns to strict update coalescing.
- [x] Keep pending-paint requeue detection in the parser as a red regression bar; future fixes must not rely on repaint/requeue loops to force cadence.
- [ ] Root-cause the update-delivery deficit without adding UI-thread churn:
  - paint/update delivery state after settings/edit rebuilds
  - GL texture upload spikes during transition windows
  - visualizer tick-listener latency during transitions
  - display-specific render-target/refresh ownership after recreate
- [ ] Audit active visualizer ownership during the same windows:
  - one live visualizer widget
  - one beat/tick engine owner
  - no hidden overlay duplicate
  - no stale worker loop after settings/edit-mode rebuild
- [ ] Classify Display 1 under-target behavior separately from Display 0 near-60 behavior.
- [ ] Use `.tmp/perf_collapse_evidence_20260628_164113` as the current compact collapse evidence before requesting another long runtime run.
- [ ] Keep current-good visualizer modes locked before and after any render/tick ownership changes.
- [ ] Do not move transition/image/visualizer work onto the UI thread to “fix” FPS.

Risk control:
- First-frame and last-frame transition correctness outrank FPS.
- No visualizer fidelity, reactivity, or mode-specific behavior changes are allowed as a side effect.
- Treat GC and cache fallbacks as contributors unless parser evidence proves they are sole causes.

### P0. Lifecycle unification audit and bar pass

- [ ] Inventory every widget where `start()/stop()/cleanup()` and `_activate_impl()/_deactivate_impl()/_cleanup_impl()` can diverge materially.
- [ ] Add or refresh parity bars for at least `media`, `weather`, `reddit`, `gmail`, and one simple non-service widget.
- [ ] Decide the migration shape:
  - `Option A`: route `start()/stop()` through lifecycle calls and retire dormant split behavior
  - `Option B`: keep wrappers but make them thin aliases with no independent state
- [x] Update `tests/test_widget_lifecycle.py` so it stops treating the split as the desired future contract.
- [x] Make lifecycle-to-legacy startup fallback log loudly when lifecycle was attempted but could not activate the widget.
- [ ] Do not migrate every widget at once without parity bars.

Risk control:
- Keep startup/first-frame/secondary-stage paths under targeted tests.
- Use current runtime-sensitive suites from `Docs/TestSuite.md` before touching mass widget activation logic.

### P0. Weather cache authority collapse

- [x] Create one canonical startup-cache loader for Weather that both constructor startup and lifecycle re-initialize use.
- [x] Preserve “show stale until replaced” behavior across widget recreate, settings-close rebuild, and stop/start.
- [x] Add regression bars for:
  - widget-local cache only
  - provider cache only
  - invalid widget-local cache + valid provider cache
  - cleanup/reinitialize path

Risk control:
- Do not tighten cache age semantics; keep display cache permissive and refresh cadence separate.

### P0. Visualizer CUSTOM authority reduction

- [x] Preserve the latest settings-return failure evidence under `.tmp/perf_collapse_evidence_20260628_164113/20260629_0417_settings_return_collapse`.
- [x] Add a narrow startup/settings-return repair: a single stale `spotify_visualizer` rect may be promoted only when the visualizer route points at the current active concrete monitor.
- [x] Keep absent target, ambiguous foreign rect, and wrong-monitor fallback paths rejected.
- [x] Add parser markers so visualizer CUSTOM suppression and bucket repair are visible in future timeline diagnostics.
- [ ] Runtime-check that the repair is one-shot: after it persists the canonical bucket, normal settings return should create the visualizer without suppression or repeated repair.
- [ ] Keep `audits/GeoAudit/Visualizer_Runtime_Shape_Audit.md` as historical/watchlist context if replay-green/runtime-wrong geometry reappears.

Risk control:
- Do not relax foreign rect replay broadly. The repair must stay unique, routed, concrete-monitor-only, and loud when it fires.

### P1. Authoritative delayed-work classification

- [x] Inventory raw `QTimer.singleShot(...)` call sites and classify them as `UI-local` vs `authoritative runtime`.
- [ ] Migrate only authoritative runtime retries/reconciles/stabilizers onto a shared owner with token cancellation or explicit lifecycle ownership.
  - [x] `CustomLayoutManager.schedule_raise_all_active_shells(...)` edit-shell restack uses `ThreadManager.single_shot(...)` and still coalesces/defer-runs under test.
  - [x] `BaseOverlayWidget` CUSTOM geometry reapply uses `ThreadManager.single_shot(...)` and suppresses reapply scheduling during its own authoritative correction.
  - [x] `SpotifyVolumeWidget` CUSTOM geometry reapply uses `ThreadManager.single_shot(...)` and coalesces duplicate queued corrections.
  - [x] `WidgetManager._queue_spotify_visibility_sync(...)` uses `ThreadManager.single_shot(...)` and coalesces duplicate media-visibility sync requests.
  - [ ] `SpotifyVolumeWidget` secondary-stage reveal retry remains a candidate, but needs a no-first-frame-poisoning/reveal-stage bar before migration.
- [ ] Leave harmless UI-only shots alone unless they are causing real state drift.

Current production classification:

| Class | Current examples | Direction |
|---|---|---|
| UI-local/cosmetic | `main.py` message auto-close, `ui/settings_dialog.py` notices/scroll/header image refresh, `ui/styled_popup.py`, `ui/system_tray.py`, `ui/tabs/widgets_tab.py` scroll restoration | Leave alone unless a real UI bug appears. |
| Input/focus follow-up | `rendering/display_setup.py` MC startup focus reclaim, `rendering/display_input.py` browser foreground follow-up, `rendering/display_native_events.py` mute poll nudge | Keep narrow; migrate only if focus/input logs show ownership drift. |
| Authoritative startup/reveal | `rendering/display_overlays.py`, `rendering/widget_manager.py`, `widgets/spotify_visualizer/startup_staging.py` | Migrate only with reveal-token/cancellation bars; first-frame/secondary-stage behavior is fragile. |
| Geometry/replay stabilization | `rendering/custom_layout_manager.py` shell restack, `widgets/base_overlay_widget.py` CUSTOM geometry reapply, and `widgets/spotify_volume_widget.py` CUSTOM geometry reapply now managed; `widgets/spotify_volume_widget.py` secondary-stage reveal retry remains raw | Good first migration candidates, but only with `--geo`/CUSTOM bars proving no shape churn. |
| Image/transition/GL timing | `rendering/display_image_ops.py`, `engine/image_pipeline.py`, `engine/screensaver_engine.py`, `rendering/gl_compositor_pkg/gl_lifecycle.py`, `rendering/gl_compositor_pkg/transitions.py` | Do not migrate casually; first-frame, prewarm, and transition correctness outrank cleanup. |
| Shared timer owner internals | `core/threading/manager.py`, `widgets/service_widget_runtime.py`, `widgets/overlay_timers.py` | Keep as owner seams; extend tests when behavior changes. |

Good targets:
- startup stabilization
- settings-close rebuild repair
- remote visualizer fallback recheck
- overlay reveal timing that still owns authoritative visibility gates

Avoid churn:
- scroll restoration
- short-lived settings notices
- purely cosmetic delayed styling

### P1. Settings mutation contract hardening

- [x] Document allowed `emit_change=False` call families and why they are safe.
- [x] Add a focused audit of geometry/runtime repair writes that persist silently.
- [x] Only introduce a batch-mutation API if evidence shows real settings storms or inconsistent runtime notifications.
- [x] Keep `set_widgets_map()` as the preferred silent widgets-root helper instead of scattered silent section writes.

Current `emit_change=False` audit:

| Caller family | Why the silence is currently acceptable | Guardrail |
|---|---|---|
| `rendering/custom_layout_manager.py` runtime content-height persistence | The live widget rect already changed; the write records the committed runtime truth without triggering a broader rebuild during edit/runtime geometry work. | Keep `--geo` logging on content-height persistence and do not use this path for width authority. |
| `rendering/spotify_widget_creators.py` visualizer route repair | The repaired monitor/authored-route value is consumed immediately by the same creator path; fallback logs are loud. | Keep `[SPOTIFY_VIS][FALLBACK]` warnings loud and avoid broad authored restore unless Custom truly exits. |
| `ui/tabs/widgets_tab.py` custom-mode/application-default reset buttons | The settings UI saves and then calls `load_from_settings()` immediately, so UI state refresh is explicit. | Keep coalesced saves cancelled before the silent root write. |
| `widgets/clock_widget.py` mode swap persistence | The live clock swaps/rebuilds its own CUSTOM rect before persisting the new mode; the save records the new live truth. | Do not use this pattern for changes that need other runtime widgets to react. |

Decision:
- No broad batch-write API is warranted from current evidence.
- Future silent widgets-root writes must either refresh their local runtime/UI state explicitly or be promoted to a notifying write.

### P1. Test-suite rehabilitation

- [x] Replace or repair [tests/test_rss_behavior.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tests/test_rss_behavior.py) against the current RSS contract.
  - [x] Keep the test feeds mocked and non-Reddit (`*.nasa.example.test`) with explicit fail-fast guards against Reddit URLs.
- [x] Remove retired Pan & Scan integration tests rather than keeping them as permanent skips.
- [ ] Replace the most valuable live-compositor skips with narrower logic/harness coverage where possible.
- [x] Revisit flaky Qt timer/threading tests with a narrower seam or documented harness path.

### P2. Compatibility classification and cleanup

- [ ] Create a small keep/quarantine/remove table for active compatibility seams.
- [ ] Remove misleading “legacy” comments once the owning contract is clarified.
- [ ] Keep only the compatibility layers that still protect real callers or packaging paths.

Potential cleanup candidates:
- stale skipped tests for removed features
- misleading “legacy” comments around active code paths
- dead export/import wrappers that no longer serve runtime

### P2. Bounded compositor / GL improvement pass

- [x] Add bounded loud diagnostics for active shader fallback so repeated transition fallback frames expose the active path and reason without blind per-frame spam.
- [x] Classify the latest Diffuse fallback as `capability_unavailable` from the reason-bearing `[GL PAINT][FALLBACK]` record.
- [x] Refuse Rain Drops cleanly when the shader/compositor path cannot start; do not report diffuse/immediate-display substitutes as successful Rain Drops transitions.
- [x] Return explicit deferred compositor-start tokens so delayed/desynced starts are not misclassified as unavailable capability.
- [x] Replace stale handwritten prewarm widget raises with the owner-based runtime-widget raise helper.
- [ ] Audit why Diffuse/Rain Drops capability can be unavailable at runtime if clean refusals still appear in fresh logs after the deferred-token fix.
- [ ] Keep refusal/fallback logs loud under the relevant CLI families until the selection/capability contract is clean.
- [ ] Audit expensive framebuffer-realization/prewarm seams before any broad render-target rewrite:
  - `widgets/spotify_bars_gl_overlay.py` `grabFramebuffer()` prewarm fallback
  - `transitions/overlay_manager.py` `prepare_gl_overlay(..., grab_framebuffer=True)`
  - first-frame flush path in `rendering/display_image_ops.py`
- [ ] Add or strengthen bars around:
  - first-frame correctness and timing
  - transition first-use parity vs warmed paths
  - overlay/card fidelity after GL warmup or prepaint changes
  - no new corruption / black-frame / wrong-DPR output
- [ ] Audit the `shader_dispatch.get_viewport_size()` DPR/viewport contract, especially the `h + 1` behavior, and either:
  - document it as an intentional compatibility rule with tests
  - or replace it only when a stricter viewport/bar proves the change safe
- [ ] Measure whether hidden shared offscreen warmup can safely take over more shader/resource prep without perturbing the live compositor surface.
- [ ] Do not attempt a full explicit FBO render-to-texture architecture pass unless the bounded audit proves a concrete fidelity-safe win that simpler churn-reduction work cannot deliver.

Risk control:
- preserve transition correctness over raw FPS vanity
- do not trade away image integrity, first-frame truth, or overlay/card fidelity for a cleaner GL graph
- any OpenGL optimization pass must stay heavily instrumented under existing `--perf` / `--viz` / `--life` families

## Tests Worth Fixing First

- [tests/test_rss_behavior.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tests/test_rss_behavior.py)
  - still valuable because source-ingestion and queue behavior remain core product behavior
- [tests/test_widget_lifecycle.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tests/test_widget_lifecycle.py)
  - currently blocks healthy lifecycle convergence by blessing dormancy
- [tests/test_qt_timer_threading.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tests/test_qt_timer_threading.py)
  - repaired as deterministic overlay timer stop-thread routing coverage; keep it green when changing timer ownership
- transition tests with live-compositor skips
  - keep the value, but move them closer to harness-backed or narrower logic checks instead of permanent hard skips

## Low-Priority Debris Worth Tracking

- `Docs/SRPSS_Settings_*.sst` example payloads appear stale relative to current defaults.
- `Imgur` still carries a TODO about overlay-raise behavior that should either become a tracked bug or be retired.
- `rendering/gl_compositor_pkg/__init__.py` is mostly a compatibility shell and should stay intentionally classified instead of drifting as “future refactor maybe”.

## Recommended Next Execution Pass

1. Fix canonical doc/default drift immediately.
2. Tackle lifecycle parity bars so future widget/runtime cleanup does not keep splitting ownership.
3. Keep the visualizer geometry root-cause map active in parallel, but do not pile on more recovery layers while lifecycle/timer ownership is still soft.
