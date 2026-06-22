# Test Suite Guide

Last updated: 2026-06-04

Testing strategy, execution guidance, and minimum quality bar.

## 1. Testing Philosophy
- Keep fast deterministic unit coverage for core logic.
- Add integration/regression coverage for lifecycle and cross-module behavior.
- Treat visual/timing-sensitive bugs as requiring runtime validation in addition to tests.

## 2. How to Run
- Full suite:
```powershell
pytest tests -q
```
- Collect only:
```powershell
pytest --collect-only tests -q
```
- Targeted file/class:
```powershell
pytest tests/test_settings_manager.py -q
pytest tests/test_visualizer_presets.py::TestVisualizerPresetRepair -q
```

## 3. High-Value Regression Areas
- Settings manager cache invalidation and section-write behavior.
- Visualizer mode/preset contracts and schema normalization.
- Overlay/widget lifecycle and startup staging behavior.
- Rendering/compositor fallback and transition lifecycle.
- Input routing and runtime interaction-mode behavior.
- Gmail widget OAuth flow, DPAPI token storage, and backend routing.

## 3.1 Regression Test Inventory
Keep these regression-focused files discoverable and up to date when their bug family changes:

- `tests/test_settings_manager.py`
  Settings cache invalidation, section/root writes, legacy alias migration, visualizer schema version-gating, reset-to-defaults profile overrides, SST replace-import semantics, and bulk-mutation stale-cache prevention.
- `tests/test_settings_defaults_parity.py`
  Canonical defaults parity, preserve-on-reset keys, and derived defaults snapshot expectations.
- `tests/test_visualizer_presets.py`
  Preset repair/reindex behavior, SST export/import roundtrip, and canonical visualizer snapshot integrity.
- `tests/test_gmail_oauth.py`
  Gmail OAuth callback/threading contract, fake-credential token handling, and DPAPI safety expectations.
- `tests/test_widget_manager.py`
  Overlay re-raise ordering, deferred raise timer cleanup, `WidgetManager` startup/teardown coordination, explicit runtime-pause quiesce behavior before display teardown, fade-coordinator re-prime behavior for already-ready compositor rebuilds, stale fade-participant clearing on runtime rebuild, CUSTOM-position stacking exclusion, and live media refresh reapplication of authored font/artwork/rounded-border inputs.
- `tests/test_widget_descriptors.py`
  Canonical factory-backed widget descriptor metadata, WidgetsTab section order, builder/load/save routing including the Defaults section, descriptor-owned load/save orchestration helpers, shared authored-layout restore mutation ownership, descriptor-owned save-result application for standard persisted keys, descriptor-owned signal-block membership and target collection for standard sections, descriptor-owned default-init metadata for standard widget settings attrs, descriptor-owned lazy/programmatic dependency metadata for inter-section hydration, runtime capability ownership, descriptor-owned service-runtime contract participation, inheritance kwargs, config-injection contracts, live-refresh handler routing, canonical widget position-option/layout-edit metadata, explicit `Custom` slot availability/selection helpers, first-phase CUSTOM attr/resize-mode ownership, and descriptor-owned stack-preview/settings-composition field ownership.
- `tests/test_custom_layout_contract.py`
  CUSTOM layout normalized-rect schema helpers, grid/display/peer snapping, snap-guide reporting, clamp rules, target-screen resolution, display-local persistence roundtrip coverage, transfer-target eligibility limited to active compositor-backed displays, and the narrow legacy MC display-signature ingestion bridge that resolves old identity-plus-geometry buckets onto the canonical display identity.
- `tests/test_custom_layout_manager.py`
  CUSTOM edit-session save/cancel behavior, global session activation across active display instances, first-class `custom` position persistence, saved authored-route reset behavior, late screen-binding recovery, size-payload persistence for clock/weather/media plus Reddit/Gmail font-driven resize families, live peer-snapping/clamp behavior, canonical rebuild-on-save/reset behavior, numbered-monitor cross-display ownership transfer, `ALL`-locked transfer blocking, deferred processed-image flush behavior, non-forced widget visibility during runtime custom-layout reapply, edit-shell reset-affordance placement, temporary per-display grid overlay lifecycle, visualizer shell capture via card-plus-overlay composition rather than whole-display grabs, visualizer-owned CUSTOM rect persistence including committed-rect replay authority over live mode-height policy, and media-owned CUSTOM persistence plus scale-contract reapply for secondary dependents like `spotify_volume`.
- `tests/test_widget_manager_refresh.py`
  Descriptor-driven factory-backed widget setup parity for clock/weather/media/reddit/gmail creation paths.
- `tests/test_service_widget_runtime.py`
  Shared service-backed widget lifecycle helper coverage: parent transition probing, deferred single-shot timer reuse, deferred refresh/value staging, spinner suspend/resume, shared fetch-in-progress guards, shared manual-refresh flow, visible-fallback preservation for non-authoritative empty/error results, shared deferred-runtime timer/state reset, and timer-stop cleanup.
- `tests/test_widget_lifecycle.py`
  Base overlay lifecycle state machine coverage plus widget setup startup arbitration guards: lifecycle-first activation, loud legacy `start()` fallback only when lifecycle declines, and reused active widget no-op behavior.
- `tests/test_qt_timer_threading.py`
  Overlay timer stop-thread routing guard: direct owner-thread stop and queued off-thread stop through the timer owner seam without relying on flaky real Qt event-loop cleanup.
- `tests/test_clock_widget.py`
  Clock fade-sync parity and analogue-specific rendering contracts such as circular background-card behavior.
- `tests/test_widgets_tab.py`
  Descriptor-driven WidgetsTab section order, descriptor-owned position-combo parity, explicit `Custom` slot enable/disable behavior, section-level CUSTOM size-lock UX, styled `Disable Custom Mode` revert affordance behavior, descriptor-owned current-widget preview/config composition, descriptor-owned section load/save routing, lazy-section build parity, descriptor-owned inter-section dependency restore behavior, bucket-state persistence, and visualizer/settings integration paths.
- `tests/test_widget_visual_padding.py`
  BaseOverlayWidget visual-padding math plus `_custom_layout_local_rect` override behavior used by first-phase CUSTOM layout reapply.
- `tests/test_spotify_visualizer_widget.py`
  Secondary-stage startup ownership, manager/coordinator reveal routing, fresh-frame reveal gating, post-reset stale-frame blocking, parent deadline coordination, activation/reset runtime contracts, live audio block-size capture rebinding, lifecycle-aware latency diagnostics (including startup audio-ready suppression and explicit-probe preservation), Bubble dispatch hot-path guards (single pre-AGC snapshot read plus reused payload dicts), authored Bubble `Preset 1 (Deep Sea)` feed-plus-visible-motion oracle coverage including sustained-loud hold, live big-size edit authority, seeded Preset 1 vs Preset 9 runtime comparison, Spectrum GPU extras reuse, authored Spectrum `Preset 1 (Organs)` first-visible/startup-parity oracle coverage, first-visible-frame synthetic oracle parity for hot mode switch/preset cycle versus fresh activation, and architecture-split engine-resolution regression coverage.
- `tests/test_visualizer_settings_plumbing.py`
  Visualizer settings-model round-trip coverage, active-mode parity between `from_mapping()` and `from_settings()` for Bubble/Spectrum/Spline, curated-vs-custom preset authority, grouped build/serialize field-family contracts, legacy migration normalization, and create-time cross-display media-anchor resolution for Custom-routed visualizers.
- `tests/test_spotify_visualizer_mode_transition.py`
  Mode-fade-out reset ordering, runtime bar-array zeroing before engine prepare, no hidden `_replay_engine_config()` reintroduction, and stale activation/generation rejection before display-bar authority returns.
- `tests/test_ghost_isolation.py`
  Overlay per-mode state isolation, manual reset bookkeeping, mode-switch cold-reset behavior, and ghost/runtime buckets staying mode-local rather than bleeding across visualizer modes.
- R-22 closure family
  For first-bar / first-frame / preset-drift watch work, treat this trio plus runtime log grep as the standing closure set:
  - `tests/test_spotify_visualizer_widget.py -k "first_frame_guard or before_first_overlay_push_logs_once_per_source_signature or runtime_switch_paths_reset_all_bleed_state_for_all_modes or mode_switch_synthetic_audio_matches_fresh_worker_after_reset or widget_manager_preset_cycle_discards_real_engine_bleed_state or mode_switch_discards_stale_audio_buffer_before_next_frame"`
  - `tests/test_spotify_visualizer_mode_transition.py`
  - `tests/test_ghost_isolation.py -k "TestOverlayModeResetIsolation"`
- `tests/test_devcurve_builder_contract.py`
  Spline Curve builder structure contracts such as bucket composition, scaffold usage, and canonical default-color helper usage.
- `tests/test_mute_button_widget.py`
  Mute button secondary-stage gating, late-anchor recovery, centralized deadline respect, and canonical enable/disable/cleanup runtime reset behavior.
- `tests/test_media_widget_runtime_methods.py`
  Media deferred callbacks, canonical smart-poll timer reset, pending-state debounce cleanup, optimistic media-control repaint/update behavior, and the rule that live media visibility re-entry stays suppressed while a CUSTOM shell session is active.
- `tests/test_weather_widget.py`
  Weather retry timer cleanup, retry timer reuse, retry timeout state handling, provider-backed stale startup cache recovery when widget-local cache is invalid or mismatched, lifecycle initialize cache-authority parity, and canonical startup/steady-state refresh scheduling parity across lifecycle entry paths.
- `tests/test_imgur_widget.py`
  Imgur lifecycle cleanup, grid/layout behavior, click routing, and canonical periodic refresh timer reschedule/stop ownership.
- `tests/test_spotify_volume_widget.py`
  Spotify volume flush-timer reset parity across stop/deactivate/cleanup paths, provider-switch volume resync, hidden→visible mixer-session resync without high-frequency polling, centralized secondary-stage reveal gating/positioning, and authored scale-contract stability while remaining media-owned in CUSTOM layout mode.
- `tests/test_s_hotkey_workflow.py`
  Settings-entry regression coverage, including the rule that an active CUSTOM shell session is cancelled before the engine stop/settings-dialog startup path proceeds and that the engine stop path quiesces displays before clear/hide.
- `tests/test_media_keys.py`
  Focused hotkey/input-routing coverage for media transport and volume shortcuts, including `Space`/`Home` play-pause, `Left`/`Right` track navigation, `Up`/`Down` slider volume steps, and `PgUp`/`PgDn`/`End` system-audio intent routing through the shared input/display seams.
- `tests/test_gmail_widget.py`
  Gmail cache/fallback behavior, empty-fetch preservation of valid displayed mail, empty-state header-safe layout, shared transition-aware refresh deferral, shared manual-refresh short-circuiting, timer cleanup, grouping formatting, and stable-content caching rules.
- `tests/test_reddit_widget.py`
  Reddit fetch/result transition deferral, spinner suspend/resume, deferred timer cleanup, cache-regeneration deferral, shared manual-refresh short-circuiting, visible-content preservation on non-authoritative empty/error fetches, and interactive refresh behavior.
- `tests/test_rss_behavior.py`
  RSS facade/current pipeline behavior: mocked multi-feed JSON ingestion, wallpaper-sized image validation/download caching, queue rotation across RSS/local pools, and duplicate-history protection without relying on live Reddit access.
- `tests/test_gmail_imap_actions.py`
  Gmail IMAP UID action helpers, mailbox order preservation, and partial-fetch failure rejection so truncated IMAP snapshots cannot overwrite valid Gmail display/cache state.
- `tests/test_settings_dialog.py`
  Settings-dialog destructive flows such as reset-defaults completion/auto-close behavior, plus lazy WidgetsTab programmatic access and hidden-close guardrails.
- `tests/test_flicker_fix_integration.py`
  R-18 settings startup flicker/taskbar ghost regression guard.
- `tests/test_display_tab.py`
  Display-tab interaction-mode settings behavior, including MC lock-on policy expectations.
- `tests/test_mc_context_menu.py`
  MC context-menu interaction-mode contract and safe disable-path prevention.
- `tests/test_mc_entrypoint_contract.py`
  MC startup policy contract, especially forced interaction-mode behavior.
- `tests/test_dimming_and_interaction_fixes.py`
  Interaction/dimming regression coverage across recent runtime fixes.
- `tests/test_transition_distribution.py`
  Transition random-pool parity, enabled-pool selection, and approximate long-run uniformity for engine-driven random transition choice.
- `tests/test_transition_registry.py`
  Transition registry parity: canonical labels/aliases, hardware gating, cycle-list coverage, compositor program routing, and factory-side random fallback behavior.
- `tests/test_visualizer_card_geometry.py`
  Visualizer outer card geometry parity: mode/preset-owned preferred height, shrink-to-base behavior for strip-like modes, blob-width reduction, and media-relative placement ownership separate from stencil math.
- `tests/test_stencil_mask_alignment.py`
  GL stencil mask/card-boundary alignment for the painted-card visualizer path.
- `tests/test_startup_shader_warmup.py`
  Startup shader/program warmup policy: minimal transition startup subset and active-mode-first visualizer shader compile ordering.

## 4. Visualizer Test Expectations
When changing visualizer settings/contracts, include tests for:
- model serialization round-trip,
- active-mode parity between `from_mapping()` and `from_settings()` for the touched mode family when constructor/build seams move,
- normalization contracts,
- legacy shared-technical migration into per-mode keys without re-emitting shared keys,
- runtime bridge kwargs transport,
- preset repair/reindex behavior,
- mode-prefix compatibility for future/unknown-style payload prefixes.
- reset-order / stale-generation gating when touching mode-reset, activation, or overlay-handoff code.
- **Stencil mask alignment** (`tests/test_stencil_mask_alignment.py`): validates that the GL stencil mask exactly matches the visible card boundary (rounded corners included) and does not bleed outside the card fill or over the centred pen stroke. Must pass after any change to `paintGL()` mask uniforms, card inset math, or border-width handling in `SpotifyBarsGLOverlay`.
- **Outer card geometry policy** (`tests/test_visualizer_card_geometry.py`): validates that mode/preset-owned growth still drives preferred outer height, blob-width reduction stays media-relative, and top/bottom anchor placement remains correct independently of stencil-shell behavior.
- **CUSTOM adaptive visualizer sizing** (`tests/test_custom_layout_manager.py`, `tests/test_widget_manager.py`, `tests/test_visualizer_card_geometry.py`): validates that visualizer CUSTOM edit shells use a maximum-envelope footprint for safe alignment, saved CUSTOM payload stores width/height scales, and runtime re-resolves the live mode/preset card size instead of freezing the first captured CUSTOM rect dimensions.
- **First visible activation parity** (`tests/test_spotify_visualizer_widget.py`): validates that the first authoritative visible GPU frame after hot mode switch or preset cycle matches a fresh-activation oracle under the same synthetic audio and preset-owned technical values, so poisoned runtime state or entry-point drift cannot hide behind worker-only tests.
- **Authored runtime motion oracles** (`tests/test_spotify_visualizer_widget.py`, `tests/test_bubble_reactivity.py`): when a mode has a known curated “truth” preset such as Bubble `Preset 1 (Deep Sea)`, the bar should include runtime-path checks that measure visible simulation motion, not only helper/feed variance. Bubble closure now requires direct runtime-path oracles for both lanes: big bubbles must be present, visibly active under soft phrases, sustain visible authority through loud holds, and stay competitive with authored comparison presets without silently flattening under render-size clamp saturation; the small/medium lane must also remain alive through sustained loud passages instead of only looking good in quieter sections. Runtime pulse payload plumbing must be proven live, not merely present.
- **Sustained-loud Bubble movement bars** (`tests/test_bubble_reactivity.py`, `tests/test_spotify_visualizer_widget.py`): Bubble must also prove that hot sustained passages wake movement and both lanes quickly without falling into a delayed/lingering "loud mode". The strong bar should cover: fast absolute-loudness movement authority under calm-vocal bass-heavy passages, early loud-section engagement instead of late pickup, preserved soft-passage quality, and quick recovery after the drop.
- **Runtime-loud Bubble oracle** (`tests/test_spotify_visualizer_widget.py`): keep at least one harsh widget-path phrase that models the real failing shape rather than a polite helper loop: soft opening, then long bass-heavy sustained loudness with sparse onset/kick help. This bar should fail when only big bubbles move, when the hero lane arrives late, or when the small lane dies while the song is still obviously loud.
- **Replay-shaped Bubble oracle hygiene** (`tests/test_spotify_visualizer_widget.py`): when a loud-path regression is coming from real runtime logs, the helper must grade the real Bubble worker snapshot and cycle-aligned dispatch replay windows, not a second helper-side `snapshot(...)` call with neutral pulse params or a mixed soft/hot slice from a repeated profile. Otherwise the bar can quietly drift back into a proxy and stop matching live failure shape.
- **Runtime-loud Bubble failure-shape bars** (`tests/test_spotify_visualizer_widget.py`): the harsh widget-path oracle should also fail on the exact late-loud abnormalities seen in runtime, not just on generic "weak motion". Keep direct bars for: soft-window success followed by hot-window small-lane collapse, hero-lane visible size stuck at one late-window value, hero-lane clamp pressure staying pinned, and size/clamp edits that only free the hero lane by sacrificing the small lane.
- **Historical comparison when Bubble regressions get deep** (`tools/bubble_parity_harness.py`, `tests/test_bubble_reactivity.py`): when present-day Bubble bars stop matching runtime feel, compare current Deep Sea / Preset 9 behavior against `9d4925e` and `510520e` rather than trusting modern proxy bars alone. Treat the harness as a structural reference, not final runtime sign-off.

## 4.1 Gmail Test Expectations
When changing Gmail widget OAuth/backend, include tests for:
- DPAPI encrypt/decrypt roundtrip with fake credentials,
- PKCE parameter generation and state management,
- OAuth token storage with mocked file system,
- REST API client methods with mocked requests (list_messages, mark_as_read, archive_message),
- GmailPosition enum values and string parsing,
- Explicit non-dev-gated contract checks: Gmail feature paths should remain available without `is_gmail_enabled` / `force_gate` style gating helpers,
- Settings roundtrip and structure validation,
- Widget instantiation with Qt app fixture.
- **Critical**: All Gmail tests must use fake/mock credentials and never make real Google API calls.

## 5. Test Hygiene
- Keep tests isolated and deterministic.
- Clean up Qt objects/timers in teardown paths.
- Prefer focused assertions over broad brittle snapshots.
- Avoid locking tests to artistic preset content unless explicitly intentional.

## 6. Runtime Validation Rule
For bugs with user-visible rendering/startup/focus behavior:
- tests are required,
- but final sign-off requires runtime observation (manual or harness-backed evidence).

## 7. Harness Reference
- Use `Docs/Harness_Index.md` as the compact lookup for recurring investigation harnesses and smoke commands.
- If a new harness becomes part of normal diagnosis workflow, add it there in the same change.
