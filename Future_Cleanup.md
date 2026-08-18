# Future Cleanup

Last updated: 2026-08-18

This file is **not an alternate active plan**. `Current_Plan.md` owns execution order.

Promote an item only when current evidence makes it causal or when P2/P5 closure explicitly reaches
its retirement boundary. Do not interrupt active lifecycle/presentation work with cosmetic cleanup.

## 1. Documentation Pruning / Architecture-Epoch Cleanup

The QRhi + single-surface migration invalidated several old roadmap documents as live guidance. Their
useful rules are now owned by `Current_Plan.md`, `Spec.md`, `Docs/Guardrails.md`,
`Docs/Compositor_Architecture.md`, focused visualizer docs and the P5 lifecycle material.

### Delete after applying the 2026-08-18 reconciliation pack

These are duplicate live-planning/architecture documents whose continued existence creates more risk
than historical value:

- [ ] `Docs/audits/SRPSS_Architecture_Roadmap/00_INDEX_AND_LIVE_CHECKLIST.md`
- [ ] `Docs/audits/SRPSS_Architecture_Roadmap/01_EXECUTIVE_AUDIT_AND_DECISIONS.md`
- [ ] `Docs/audits/SRPSS_Architecture_Roadmap/02_CODEX_OPERATING_CONTRACT.md`
- [ ] `Docs/audits/SRPSS_Architecture_Roadmap/03_WORK_ORDER_AND_PHASE_GATES.md`
- [ ] `Docs/audits/SRPSS_Architecture_Roadmap/04_TARGET_ARCHITECTURE_AND_OWNERSHIP.md`
- [ ] `Docs/audits/SRPSS_Architecture_Roadmap/05_VISUALIZER_FIDELITY_CONTRACT.md`
- [ ] `Docs/audits/SRPSS_Architecture_Roadmap/06_PRESENTATION_AND_COMPOSITOR_DESIGN.md`
- [ ] `Docs/audits/SRPSS_Architecture_Roadmap/ROADMAP_MANIFEST.json`

Why these are safe to retire:

- active order now lives only in `Current_Plan.md`;
- current ownership lives in `Index.md`, `Docs/Contracts.md`, `Spec.md` and exact source;
- visualizer fidelity/prohibitions live in the focused guardrail/reference/checklist;
- compositor architecture lives in `Docs/Compositor_Architecture.md`;
- operating discipline lives in `Docs/Guardrails.md` and `Docs/Documentation_Maintenance.md`;
- historical causal evidence remains in phase reports / Historical_Bugs.

Keep the roadmap directory only for still-useful **specialized** audit/reference documents that have
not been absorbed elsewhere (for example P5 lifecycle, workload, memory/resource, test/triage docs).
Its README must explicitly say it is supplemental, not a live plan.

### Do NOT delete phase reports as a group

Phase reports are dated evidence. They intentionally contain old owners such as QOpenGLWidget and a
separate visualizer surface because that is what existed when the measurements were made.

Keep them, but treat `Docs/phase_reports/README.md` as mandatory reading: reports prove/reject
mechanisms at a checkpoint and are not current architecture maps.

When P05 presentation work closes, keep `P05_PRESENTATION_DELIVERY_ATTRIBUTION.md` as historical
evidence but stop routing normal current-owner questions through it.

## 2. P4 / QRhi Diagnostic Retirement

After current P2/P4 installed acceptance is complete:

- [ ] retire QOpenGLWidget-only compositor lifecycle compatibility that no production caller uses;
- [ ] retire `QtCompositionObserver` / old `aboutToCompose` + `frameSwapped` P4 observer and owning
  tests once no rollback path requires them;
- [ ] retire old P4 DWM/stage/no-HUD/present-context forensic scaffolding after the accepted evidence
  is permanently recorded;
- [ ] keep ordinary passive request-age, dispatch-wait, paint-wait, event-loop and state-to-paint
  summaries only where they remain cheap and architecture-neutral;
- [ ] retire stage-only GPU query machinery whose sole purpose was locating the old QOpenGLWidget
  post-paint boundary;
- [ ] keep useful ordinary sampled `--gpu-timing` with correct same-context non-nesting semantics;
- [ ] retain `--diag-pair-warm-finish` only while the exact hidden pair-warm mechanism it controls
  still exists; remove both together when obsolete;
- [ ] preserve global pre-`QApplication` interval-0 `QSurfaceFormat` policy unless a deliberate
  replacement is proven.

Diagnostics remain passive. Cleanup must never change cadence/admission to make perf output prettier.

## 3. Visualizer Single-Surface Legacy Cleanup

After the current P2 readiness/freshness/CUSTOM acceptance passes:

- [ ] remove any surviving code that treats `SpotifyBarsGLOverlay` as a presented surface;
- [ ] remove obsolete `overlay.show()/hide()/isVisible()/grabFramebuffer()` presentation semantics
  after exact caller proof;
- [ ] retire old one-update-per-publication counters/scaffolding that no longer describe the physical
  presentation route, retaining only metrics still used for logical/publication/freshness evidence;
- [ ] retire the dead legacy compositor `set_spotify_visualizer_state()` / Spectrum-only bars seam if
  it still has no production caller;
- [ ] remove redundant visualizer QOpenGLWidget/QRhiWidget compatibility imports/helpers;
- [ ] collapse `rendering/gl_rhi_surface.py::RHI_CLEAR_COLOR` if the final architecture still has one
  opaque user and no legitimate per-class need;
- [ ] retain one canonical card-pixel cache identity for both QPixmap generation and GL texture
  upload invalidation;
- [ ] keep card texture/resource deletion independent from current visibility/publication state.

Do not rename `SpotifyBarsGLOverlay` merely for cosmetic purity during active work. A later explicit
rename may be reasonable, but path stability currently has more value than aesthetic correctness.

## 4. Hardware-Acceleration Contract Cleanup

Accelerated presentation is required for the modern runtime.

- [ ] retire the obsolete non-accelerated compositor/visualizer path after frozen/runtime caller proof;
- [ ] retire or redefine any `display.hw_accel` user-facing toggle that falsely promises a supported
  software visualizer path;
- [ ] do not replace it with a CPU/QPainter visualizer.

## 5. Test / Harness Debt

- [ ] Fix `tests/test_slide_jitter.py` so the top-level is actually shown and the test measures paint
  delivery rather than a widget that never composes. Do not loosen dt limits to hide the harness bug.
- [ ] Establish one shared frame-timing harness contract so update-request cadence cannot silently be
  mistaken for rendered cadence.
- [ ] Stabilize host-scheduling-sensitive Bubble worker budget tests using deterministic/tolerance
  semantics without deleting the budget assertion.
- [ ] Stabilize the paused-AdaptiveTimer no-polling timing bar without weakening its no-polling
  contract.
- [ ] Make `tools/perf_integration_harness.py --help` safe and add bounded scenario/duration/cleanup
  controls before treating it as a convenient operator tool.
- [ ] Verify any harness that constructs `SpotifyBarsGLOverlay` directly uses the current logical-owner
  contract rather than assuming a presentation surface.
- [ ] Continue classifying unrelated full-suite failure clusters/native test-process exit without
  weakening current runtime contracts.
- [ ] Split the slow `tests/test_widgets_tab.py` monolith by lazy section ownership while retaining at
  least one integrated hydration/save bar per section.

## 6. CUSTOM / Edit Hardening After Active Integration

Only after the active compositor-owned edit integration works:

- [ ] weakify `EditShellWidget` live-geometry callbacks so alternate teardown cannot retain
  `CustomLayoutManager` strongly;
- [ ] retire duplicate CUSTOM miniature teardown/replay helpers after dynamic/frozen caller proof;
- [ ] split `rendering/custom_layout_manager.py` by actual ownership (session/shell, geometry/snap,
  persistence, visualizer recovery) rather than cosmetically;
- [ ] audit `_scaled_rect_from_anchor()` corner handling with UX evidence;
- [ ] review broad exception suppression where it can hide persistence/geometry/session failure;
- [ ] silence benign PySide disconnect warnings without removing required disconnect ownership.

## 7. P6 Whole-Process Resource / Performance Follow-Up

This work never authorizes fidelity or refresh reduction.

- [ ] run long post-warm-up leak slopes over transitions, visualizer hotswaps, Settings restarts,
  provider refreshes and multi-display CUSTOM replay;
- [ ] separate bounded cache high-water marks from monotonic ownership growth;
- [ ] attribute RAM, private commit, tracked GL bytes and driver VRAM separately;
- [ ] explain any multi-gigabyte private-commit gap rather than treating flat ownership as proof of
  efficiency;
- [ ] attribute UI paint spikes in Reddit/Gmail/Media/Clock before optimizing those widgets;
- [ ] deepen ThreadManager usage snapshots with queued/cancelled tasks, oldest age and recurring
  counts using immutable snapshots only;
- [ ] define a repeatable hardware/profile comparison protocol using refresh/DPR/display route,
  transition, visualizer mode, instrumentation support and p95/p99/max rather than average FPS alone.

## 8. Repository / Compatibility Debris

- [ ] remove tracked preview-image debris after clean-checkout recreation proof;
- [ ] collapse deprecated `DisplayWidget` class-global input authority into the existing multi-monitor
  coordinator one field at a time with multi-display tests;
- [ ] retire deprecated Imgur end-to-end rather than repairing it, preserving migration/absence safety
  until deletion is promoted;
- [ ] add a lightweight repository-hygiene bar for generated debris, credential-shaped values,
  ignored artifacts and generated-default drift;
- [ ] preserve APPDATA + LOCALAPPDATA test isolation and prove tests/tools cannot resolve generated,
  cache or credential state into the user's live profile;
- [ ] document/test the active boundary between `rendering/gl_compositor.py` and
  `rendering/gl_compositor_pkg`; the package itself is active, not deletion debt.

## 9. Unrelated / Unvalidated Work To Keep Separate

- [ ] Browser GSMTC resolver changes remain unvalidated. When media work resumes, capture literal
  Windows sessions/source IDs first; do not mix browser identity work into P2/P5.
- [ ] Define a low-pressure freshness policy for Gmail cached relative timestamps without a per-minute
  repaint timer.
- [ ] Consolidate bounded Steam settings-hydration cache reads only behind one shared worker result and
  preserve signal-silent UI hydration/provider bans.
- [ ] Remove redundant Steam artwork scaling only after measured decode/prepare/paint ownership and
  DPR-sharp comparison.
- [ ] Two-profile Steam isolation/credential/privacy validation remains required.

## 10. Product / Backlog Items Still Worth Keeping

- [ ] true eight-direction widget shadows remain deferred; preserve current authored shadow authority
  until a deliberate migration;
- [ ] first-run source onboarding should eventually re-enter normal RUN startup after Settings closes
  with valid sources, without changing CONFIG semantics;
- [ ] close remaining real-runtime CUSTOM edit-shell oracle with one multi-widget bundled-font session;
- [ ] audit visualizer wall-clock -> `time.monotonic()` only with explicit clock-jump injection and
  all-mode locks;
- [ ] reconcile curated Spectrum source/release mirror drift only through the canonical preset path;
- [ ] continue old transition/visualizer dt/gap correlation only if a real pathology survives the
  QRhi/single-surface + P5 architecture, not merely because old logs contained spikes.
