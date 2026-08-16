# 15 — Completion and Release Gates

Last reconciled: 2026-08-16

A release candidate fails when a critical gate fails even if one average metric improves.

## Architecture Gate

- [ ] Current plan/spec/guardrails/roadmap/code agree.
- [ ] One explicit owner per mutable concern/deletion identity.
- [ ] One authoritative monitor-topology decision owner exists; native/Qt/per-window notifications do not independently rebuild the display graph.
- [ ] Full fail-closed lifecycle remains correct; Settings/Edit ownership does not regress.
- [ ] Physical monitor replacement uses settle→snapshot→retire-once→barrier→rebuild→reveal.
- [ ] Visualizer producers never wait for paint and presentation is not a logical clock.
- [ ] No persistent Bubble lane, paint-local Spectrum state, hidden fallback runtime, monitor polling loop or catch-all thread.
- [ ] Temporary compatibility/diagnostic façades are gone or justified by a real current contract.

## Visualizer Gate

- [ ] `ff934616` behaviour remains approved until explicitly superseded.
- [ ] Strong source→state→publication→paint temporal package passes.
- [ ] Presentation opportunity changes do not alter logical state/events/dt.
- [ ] Same-display CUSTOM geometry/aspect correction remains intact.
- [ ] Temporary configured-display sleep/wake/non-participation never migrates ownership.
- [ ] Genuine settled-topology absence may fallback once only after one coarse ~60-second owned confirmation.
- [ ] No exact timing dependency, periodic timer, polling loop or dedicated monitor thread is introduced.
- [ ] Stable configured-display return restores ownership once from topology/readiness events and saved CUSTOM geometry remains authoritative.
- [ ] User installed review passes for affected modes.

## UI / Workload Gate

- [ ] Retained-current texture becomes next-old cache hit; steady transition uploads only new.
- [ ] Routine logging file/rotation work is off caller/UI threads with bounded queue/writer ownership.
- [x] Settings persistence is ordered/background with explicit flush semantics.
- [ ] Proven provider/cache preparation is outside GUI/paint hot paths.
- [ ] p95/p99/max request-age/tick tails improve or remaining owners are named.
- [ ] No catch-all background thread or unbounded queue.

## Lifecycle / Physical Display Gate

- [ ] Repeated ordinary installed both-monitors-off→screensaver-active→wake cycles pass.
- [ ] Simultaneous, D0→D1 and D1→D0 wake orders all restore both displays.
- [ ] Clock/widgets continue advancing and Escape/context-menu/input remain responsive.
- [ ] No Ctrl+Alt+Delete is required to break a wake hang.
- [ ] Duplicate native+Qt event storms result in one topology transaction.
- [ ] Strict GL teardown remains owner-context, fail-closed and byte-accounted.
- [ ] Before/after native breadcrumbs remain observational and bounded.
- [ ] Ordinary stable desktop→screensaver startup remains flash-free; `grabWindow(0)` is not globally removed.
- [ ] Physical-wake/topology recovery does not require synchronous desktop capture.

## GPU Gate

- [ ] Representative transitions produce truthful paint + non-blocking GPU timing samples.
- [ ] No routine `glFinish()` profiler synchronization.
- [ ] Process GPU busy is separated among upload/transition/visualizer/presentation owners sufficiently to guide action.
- [ ] Overlay state/update/paint rate is compared against display refresh without reducing logical cadence.
- [ ] Phase 8 is not started unless later evidence justifies the lifecycle risk.

## Memory / Resource Gate

- [ ] No post-warmup monotonic equivalent-state growth.
- [ ] Preferred whole-app warm RSS under ~600 MiB or approved explanation; >900 MiB unresolved blocks release.
- [ ] Preferred dedicated VRAM under ~300 MiB or approved explanation; >500 MiB unresolved blocks release.
- [ ] No unexplained multi-GiB private commit.
- [ ] Strict retired-generation application GL ownership reaches zero.
- [ ] No fidelity/cadence/quality reduction used to hit resource targets.

## Logging / Evidence Gate

- [ ] Main log remains readable with WARNING/ERROR/CRITICAL visibility.
- [ ] Routine families route to sidecars without systematic duplication.
- [x] Structured routing prevents token accidents.
- [ ] Logging queue depth/writer lag/drop/flush telemetry is bounded and visible.
- [ ] Raw logs/failed runs/manifests/parser commands are preserved when available.

## Product Gate

- [ ] Correct multi-display routing/geometry/overlays.
- [ ] Cursor/interaction overlays remain smooth.
- [ ] Image/transition quality unchanged unless explicitly approved.
- [ ] All supported visualizer modes retain approved behaviour.
- [ ] Configured visualizer monitor remains sticky through ordinary monitor sleep/wake.
- [ ] Background-load behaviour is equal or better than approved runtime.
- [ ] Resource/GPU usage is appropriate for a screensaver, not merely technically bounded.

## Final Comparison

Compare ordinary work against the exact previous/current approved commit. Use historical
commits only for named forensic/negative-control questions. State remaining weaknesses and
uncertainty; a single favorable metric is never release readiness.
