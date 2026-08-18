# Future Cleanup

Last updated: 2026-08-18

## Priority Guidance

- `Current_Plan.md` owns active execution order. Do not use this file as an alternate implementation plan.
- Promote only when an item blocks active runtime-health work or fresh evidence makes it causal.
- Cleanup must not be mixed into the active QRhi architecture commits unless the old code physically prevents the migration from being correct.
- Compatibility-shell cleanup stays low priority unless it causes import/runtime ambiguity.
- Stale examples/docs are hygiene, not runtime risk; batch them rather than interrupting lifecycle/performance work.

# 2026-08-18 QRhi Migration / Diagnostic Retirement Ledger

The P4 Qt-source audit changed the active direction from further stage instrumentation to a bounded
`QOpenGLWidget -> QRhiWidget(OpenGL)` production architecture test. This section owns what should
be retained during that test and what becomes cleanup **after** the candidate is accepted.

## Keep through P4-RHI / P2-RHI acceptance

- [ ] **KEEP:** ordinary delivery-stage instrumentation in `rendering/adaptive_timer.py` separating deadline/wakeup lateness, queued-GUI-dispatch wait, paint-pending wait and skip ownership. It remains passive evidence and is not tied to QOpenGLWidget.
- [ ] **KEEP:** ordinary compositor request-age/paint summaries, event-loop lateness recorder, visualizer logical-publication/update/paint counters and sampled `--gpu-timing` where technically valid on the QRhi external-OpenGL path.
- [ ] **KEEP:** `--diag-pair-warm-finish` only while the hidden shared-context pair-warm mechanism still exists. It is an optional default-off negative control, never production behaviour.
- [ ] **KEEP until QRhi installed acceptance:** DWM timing, `--diag-p4-no-perf-hud`, P4 stage reports and the one-time present-context probe as forensic comparison tools. They are no longer an active investigation plan and must not block the production migration.
- [ ] **KEEP:** the P1 visualizer logical/temporal goldens and presentation negative controls. QRhi must satisfy them rather than replacing them.

## Retire or reshape after accepted main-compositor QRhi migration

- [ ] Remove QOpenGLWidget-only compositor lifecycle code once the rollback window closes: child `setFormat`, `setUpdateBehavior`, direct compositor `context()/makeCurrent()/doneCurrent()` ownership assumptions, and any compatibility wrapper whose only purpose was the retired widget type.
- [ ] Retire the QOpenGLWidget `aboutToCompose` / `frameSwapped` P4 observer from the QRhi compositor path. If QRhi `frameSubmitted` evidence is retained, give it a new name/semantic contract; never relabel it as the old boundary.
- [ ] Re-evaluate `P4_PRESENT_CONTEXT`. The child-context WGL probe is specifically about the old QOpenGLWidget composition topology and may become meaningless once the child context is gone.
- [ ] Retire P4 DWM/stage/no-HUD scaffolding after the QRhi runtime result is accepted and the evidence is written to the phase report. Do not carry an attribution laboratory forever after the architecture has changed.
- [ ] Audit stage/timer GL query ownership under the borrowed QRhi OpenGL context. Keep useful ordinary GPU timing; remove stage-specific query machinery whose only purpose was locating the old post-paint boundary.
- [ ] If the QRhi implementation no longer requires a separate hidden shared warmup context, retire its creation/destruction code only after equivalent startup/first-transition behaviour is proven. Do not delete it merely because the main surface no longer owns a QOpenGLWidget context.
- [ ] Preserve **global** `QSurfaceFormat` interval-0 startup configuration. `rendering/gl_format.py` is not globally dead merely because QRhiWidget does not accept the old per-child `setFormat()` path; Qt's top-level RHI swapchain still derives NoVSync from the top-level requested format.

## Retire or reshape after accepted Spotify visualizer QRhi migration

- [ ] Remove overlay-only QOpenGLWidget lifecycle/update-behaviour/context code once the QRhi overlay passes installed Bubble/Spectrum/CUSTOM/teardown gates.
- [ ] Delete duplicate external-OpenGL QRhi substrate code if compositor and overlay accidentally grow separate implementations during development; one small shared substrate is preferable after both are proven.
- [ ] Re-run the old A/B suppression question once on the QRhi overlay. If the update stream is no longer a material amplifier, retire the old temporary A/B-specific presentation scaffolding while preserving ordinary logical/update/paint counters.
- [ ] If P2 remains material after QRhi overlay migration, keep the one-surface visualizer/card scene-composition design as a deliberate architecture candidate. Do not revive request admission, AdaptiveTimer pacing, pending-until-paint, source decimation or paint acknowledgement.

# 2026-08-18 Debt Discovered During P4-RHI-A

- [ ] **Frame-timing harnesses measure nothing when the top-level is never shown.**
  `tests/test_slide_jitter.py` shows only the compositor and never its `compositor_parent`, so no
  frame is ever composed and `dt_max` degenerates to the full transition duration (~985 ms). Both
  its failures predate the QRhi migration and reproduce on clean `main`; they are harness defects,
  not delivery regressions. Fix by showing the top-level and asserting real paint delivery — do not
  relax the dt thresholds.
- [ ] Consider a shared frame-timing harness contract so compositor timing tests cannot silently
  measure update-request cadence on a widget that never paints. `tests/test_frame_timing_workload.py`
  was corrected during P4-RHI-A; `test_slide_jitter.py` still needs it.
- [ ] `QtCompositionObserver` in `rendering/gl_compositor_pkg/gpu_delivery_association.py` now has
  no production caller: the QRhi compositor cannot provide `aboutToCompose`/`frameSwapped`. It and
  its unit tests are retained only for historical stage-log analysis. Retire both together once the
  P4-RHI rollback window closes, rather than leaving a class with no caller indefinitely.
- [ ] Re-evaluate `_disable_current_context_swap_interval()` after P4-RHI-B. It is unchanged code at
  the equivalent lifecycle point, but it now acts on the top-level **presenting** context instead of
  the retired non-presenting child context, so it is no longer inert. Decide deliberately whether
  enforcing interval 0 there is the intended production policy once delivery evidence exists.
- [ ] Add a narrow bar that compositor test doubles expose the lifecycle attributes the real class
  requires. Several fakes drifted on `_rhi_gl` during this migration and only failed at call time.
  This overlaps the existing "production-contract bar for methods that exist on test doubles"
  backlog item; merge them when either is promoted.

# 2026-08-18 Debt Discovered During P4-RHI-C / P2-RHI-A

- [ ] **`tests/test_spotify_visualizer_widget.py::test_bubble_transition_time_worker_perf_oracle_stays_within_current_budget_band` is host-scheduling flaky.** Sampled 1 failure in 5 full-file runs on clean `main` and 1 in 3 with the P2 migration, at ~1.06 ms against a 1.0 ms band; it passes 3/3 in isolation. It measures Bubble worker snapshot cost, which the presentation-surface migration does not touch. Make the bound deterministic/tolerance-based like the known paused-AdaptiveTimer bar; do not delete the budget assertion and do not raise the band to hide drift.
- [x] ~~Decide the hw_accel=off visualizer contract.~~ **Decided: not debt.** Accelerated presentation is required for the modern compositor/visualizer runtime; visualizer availability without hardware acceleration is not a supported contract. Recorded in `Docs/Compositor_Architecture.md` section 0. Do not implement a CPU/QPainter visualizer, a QOpenGLWidget compatibility surface, or a software rendering architecture to preserve it.
- [ ] Re-check `prewarm_context()` once P2-RHI-B is accepted. The `grabFramebuffer()` force was removed because the surface now initializes on the real top-level QRhi from one ordinary `update()`; if installed startup shows any first-reveal shader stall, fix it at the warmup owner rather than reinstating a synchronous full-target readback.
- [ ] `tools/perf_integration_harness.py` constructs `SpotifyBarsGLOverlay` directly. It was not exercised by this migration; verify its construction order gives the overlay a live top-level QRhi before treating any harness output as valid.

- [ ] Retire the obsolete non-accelerated presentation path and the legacy `display.hw_accel` user-facing toggle if it is still present once P2-SINGLE-SURFACE lands. Accelerated presentation is now the supported contract, so a switch that claims to disable it is misleading. Do not perform a broad unrelated settings removal to achieve this; retire the path deliberately with caller/frozen-build proof.
- [ ] `rendering/gl_rhi_surface.py` keeps the per-class `RHI_CLEAR_COLOR` hook with a single opaque user after the sibling-surface rollback. Keep it while P2-SINGLE-SURFACE is in flight (a card/visualizer layer may want it); if the finished architecture still has exactly one opaque surface, collapse it back to a constant.

# Presentation / Delivery Test Debt

- [ ] Keep `tests/test_adaptive_timer.py::TestDeliveryStageInvariants` green whenever the passive delivery seam is touched: mutually exclusive skip reasons, non-negative/generation-bounded ages, unchanged PERF-off scheduling, no pending-timestamp inheritance across widget generations, independent per-display counters.
- [ ] Extend the P2 QRhi overlay suite with installed-shaped coverage still missing after P2-RHI-A: mode switching under live audio, state-to-paint latency, and Settings/display-reassignment recreation against a real QRhi generation change.
- [ ] A mixed-refresh 165 Hz + 60 Hz installed gate remains required; no unit test may substitute for physical presentation behaviour.

# Unrelated / Unvalidated Experiments That Must Not Contaminate The QRhi Lane

- [ ] **Browser GSMTC experiment remains unvalidated.** The recent `core/media/provider_registry.py` / `core/media/media_controller.py` browser-AUMID changes did not restore Firefox or Edge detection in live runtime. When media work resumes, capture literal Windows sessions/source IDs first, then supersede or revert the unproven resolver changes. Keep paused-desktop-vs-playing-browser failover separate from identity resolution.
- [ ] Do not preserve temporary monkeypatch presentation architecture as production. The old A/B/C probe proved an owner; it is evidence, not a design.

# Low-Priority Cleanup Items

- [ ] Make `tools/perf_integration_harness.py` safe to inspect/select: `--help` must print help rather than launch the long GUI sequence; add scenario/duration controls and guaranteed process/window cleanup. Keep it opt-in and never a runtime control mechanism.
- [ ] Silence the benign `EditShellWidget.retire_session()` PySide disconnect warning without weakening teardown. Prefer a receiver check or narrowly scoped warning filter over deleting the disconnect sweep.
- [ ] **Retire the dead legacy compositor visualizer seam.** `set_spotify_visualizer_state()` has no production caller; the old compositor Spectrum-only QPainter bars have no modern mode/stencil/CUSTOM ownership. Remove with caller/frozen-build proof. Do not revive it as a shortcut for P2.
- [ ] Stabilise `tests/test_adaptive_timer.py::TestAdaptiveTimerLifecycle::test_paused_worker_blocks_until_idle_deadline_instead_of_polling`. It is a pre-existing host-scheduling-sensitive bar; make the bound deterministic/tolerance-based rather than deleting its no-polling assertion.
- [ ] Define a low-pressure freshness policy for Gmail cached relative timestamps. Do not add a per-minute UI timer merely to update prose.

# 2026-08-09 CUSTOM/Edit Ownership Follow-Up

The compiled Settings/Edit survivor failure is fixed at the weak-forwarding ownership seam. The
following are hardening/cleanup only unless fresh evidence promotes them.

- [ ] Weakify the two `EditShellWidget` live-geometry callbacks created in `CustomLayoutManager` (`live_geometry_resolver`, `live_geometry_applier`) so an alternate teardown cannot retain the manager strongly.
- [ ] Retire `CustomLayoutManager._teardown_display_widgets()` and `_reapply_saved_layouts_across_instances()` only after dynamic/frozen-build caller proof; do not keep a second miniature teardown implementation indefinitely.
- [ ] Split `rendering/custom_layout_manager.py` after active Phase 5 closure by ownership (session/shell lifecycle, geometry/snap, persistence, visualizer recovery), not cosmetically.
- [ ] Audit `_scaled_rect_from_anchor()` discarding `corner`; document/test intentional top-centre scaling or fix the anchor contract only with UX evidence.
- [ ] Review broad `except Exception` density after lifecycle closure. Preserve defensive Qt cleanup but surface partial persistence/geometry/session failures where silence hides actionable state.

# Whole-Process Resource Profiling Audit

This remains attribution work, not permission to lower refresh, quality, transition fidelity,
widget content or visualizer response.

- [ ] Run controlled post-warm-up leak slopes over long repeated transitions, visualizer hotswaps, Settings restarts, provider refreshes and multi-display CUSTOM replay. Separate bounded cache high-water marks from monotonic ownership growth; teardown must return threads/tasks/children/GL resources to documented baseline.
- [ ] Attribute UI paint spikes before optimizing widgets. Existing high maxima in Reddit/Gmail/Media/Clock need cause labels (startup reveal, content commit, transition repaint, clock tick, cache regeneration, settings rebuild) and correlation with compositor gaps.
- [ ] Deepen `--usage` ThreadManager snapshots with queued/cancelled tasks by category, oldest task age, recurring count and callback backlog, consumed as immutable/copy snapshots without UI polling or new render locks.
- [ ] Define a hardware/profile comparison protocol: build/profile, resolution/DPR/refresh, transition/visualizer mode, instrumentation support, driver/GPU identity and source/cache state; compare percentiles/worst-event timelines rather than one average FPS.

# Repository Debris And Policy Audit

- [ ] Retire tracked preview-image debris after clean-checkout recreation bars: `tmp/steam_achievement_preview.png`, `tmp/steam_achievement_preview_segoe.png`, `tmp/steam_connect_preview.png`.
- [ ] Collapse deprecated `DisplayWidget` class-global input authority (`_global_ctrl_held`, `_halo_owner`) into `MultiMonitorCoordinator` one field at a time with multi-display Ctrl/edit/halo tests.
- [ ] Split the slow `tests/test_widgets_tab.py` monolith by lazy settings-section ownership while retaining at least one integrated hydration/save bar per section.
- [ ] Continue classifying the unrelated full-suite failure clusters and the repeatable native test-process exit; do not weaken current runtime contracts merely to make the aggregate count prettier.
- [ ] Add a lightweight AST test-topology bar for accidentally nested pytest cases while allowing intentional local helper/fake methods.
- [ ] Retire deprecated Imgur end-to-end rather than repairing it; preserve only migration/absence safety until deletion is promoted.
- [ ] Extend test portability policy with a narrow static bar for real absolute-path file reads, not synthetic parser/path fixtures.
- [ ] Preserve APPDATA + LOCALAPPDATA test isolation and add a bar that tests/default tools cannot resolve generated/cache/credential state into the user's live profile.

# Correctness And Privacy Validation Debt

- [ ] Add a two-profile Steam isolation matrix across cache, credentials, achievement-pulse and abandonment data. Overlapping app data must remain path/read/rotation/artwork/settings-isolated and logs must not expose credentials/raw IDs.
- [ ] Freeze Steam credential lifecycle in normal and MC packaged builds across callback cancellation, invalid key, disconnect, restart, failed validation and secure-desktop handoff; scan logs/exports/caches/generated artifacts for secrets.
- [ ] Expand Steam cache adversity tests to malformed/truncated/unknown-schema/wrong-profile/stale/failed/private/empty-success envelopes without timestamp freshening or cross-identity authority.

# Safe Optimization Candidates

- [ ] Consolidate bounded Steam settings-hydration cache reads behind one shared worker result while preserving signal-silent UI population and provider/decryption bans.
- [ ] Remove redundant Steam artwork scaling only after measuring decode/prepare/paint ownership; require pixel-sharp DPR comparison renders.
- [ ] Correlate Steam presentation commits with compositor/UI pressure before changing callback flow. No retries/timers/broad refreshes without a measured owner.
- [ ] Document/test the compatibility boundary between `rendering/gl_compositor.py` and `rendering/gl_compositor_pkg`; the package is active, not a deletion candidate.
- [ ] Add a repeatable repository-hygiene bar for generated debris, credential-shaped values, ignored artifacts and generated-default drift without reading local secrets into logs.

# Backlog

- [ ] True eight-direction widget shadows remain deferred. Preserve `shadowtuning.json` as per-surface fidelity authority and canonical offset signs as direction authority; do not shrink content or change the current bottom-right baseline during a future migration.
- [ ] First-run source onboarding restart remains deferred: closing RUN-mode startup Settings after adding valid sources must re-enter normal engine startup in the same `QApplication`, without changing CONFIG mode or established S-key/tray lifecycle.
- [ ] Classify Bubble tests that still exit through retired Preset 9 setup; do not restore the retired preset or retune healthy Bubble runtime to satisfy stale fixtures.
- [ ] Close the remaining real-runtime CUSTOM edit-shell oracle with one multi-widget session using bundled fonts; if it passes, retire the stale failure narrative.
- [ ] Audit a shared visualizer animation-clock migration from wall time to `time.monotonic()` only with explicit clock-jump injection and Bubble/Spectrum/Sine/Oscilloscope locks. Do not repeat the previous unscoped clock swap.
- [ ] Reconcile any curated Spectrum source/release mirror drift through the canonical preset regeneration path; do not revive retired assets/tests.
- [ ] Continue correlating old transition/visualizer DT and paint-gap spikes only if they remain after the QRhi architecture work. Do not use old paused/stale-audio windows to justify a cadence rewrite.
- [ ] Review image-pipeline `scaled-miss` worker-fallback telemetry only after confirming whether repeated misses indicate real decode/prescale churn or merely noisy recovery logging.
- [ ] Review repeated Spotify visualizer reveal-watchdog warnings while `playing=False`, `require_playing=True`, `authoritative_media=False`; expected idle waiting should not stay warning-level if live playback still reveals promptly.
- [ ] Split Spotify visualizer latency health by playback authority so forced paused/stale probes cannot imply a live-audio regression.
- [ ] Reclassify successful Reddit cache telemetry currently emitted at WARNING if fresh logs confirm ordinary success.
- [ ] Reconcile likely-stale Media/Visualizers descriptor tests against current intentionally split settings sections before changing production descriptors.
- [ ] Add a narrow production-contract bar for critical lifecycle/transition methods that exist on test doubles but not the real class.
- [ ] Decide whether `rendering/gl_compositor_pkg/__init__.py` remains a quarantined compatibility shell or becomes a cleaner package-facing contract.
- [ ] Retire/quarantine `rendering/render_strategy.py` only with caller/frozen-build proof; its old busy-wait/update-queue code must not return as a presentation solution.
- [ ] Classify remaining direct `QTimer.singleShot` sites only when they stop being UI-local polish/debounce helpers.
- [x] ImagePrefetcher selected-index deletion-order `IndexError` is promoted/handled under its active/historical owner; do not add retries or broad exception masking.
