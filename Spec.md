# Spec

Last updated: 2026-08-11

Canonical stable architecture and product behaviour contracts for SRPSS.

Implementation plans, benchmark results, and dated regressions do not belong here.

## 1. Product Intent

SRPSS must provide:

- smooth multi-display image presentation;
- stable configurable overlays;
- responsive high-fidelity visualizers;
- durable and recoverable settings;
- predictable Normal and Media Center runtimes;
- resource use appropriate for a screensaver.

Priority order is defined in `Docs/Guardrails.md`.

## 2. Runtime Topology

- `main.py` and `main_mc.py` bootstrap runtime variants.
- `ScreensaverEngine` owns high-level runtime sequencing.
- `DisplayManager` owns active display instances and topology response.
- Each active display owns one presentation surface and its display-local geometry/DPR.
- `DisplayWidget` is the fullscreen presentation host.
- `WidgetManager` owns overlay widget lifecycle.
- Image selection/decode/preparation is separate from GL presentation.
- Visualizer simulation is separate from compositor presentation.
- Settings/Edit recreation uses one ordered lifecycle.

No display may silently borrow display 0 state, geometry, input authority, or presentation ownership.

## 3. Stable Ownership Principles

- One mutable concern has one authoritative owner.
- Shared managers are used only for the contracts they actually own.
- No shadow settings, task, transition, descriptor, lifecycle, or render frameworks.
- Cross-thread data is immutable or explicitly synchronized.
- Generations represent real lifetime boundaries.
- Existing files, public ids, and paths are not renamed without explicit user instruction.
- Fallbacks that change behaviour, quality, owner, display, or render path are loud failure evidence.

Routing details live in `Docs/Contracts.md`.

## 4. Presentation Contract

### 4.1 Display-local compositor

The long-term target is one compositor surface per display.

It composes:

- current image;
- optional transition;
- optional visualizer;
- dimming and overlays that belong in the GL scene.

Ordinary Qt widgets may remain above the compositor where appropriate.

### 4.2 Producer/consumer relationship

State producers publish the latest immutable state.

The compositor consumes the latest scene when Qt presents.

Normal producers never wait for paint acknowledgement.

A single pending GUI update may be coalesced, but it is not a producer scheduler.

### 4.3 Clocks

Separate logical clocks exist for:

- visualizer simulation;
- transition elapsed time;
- Qt presentation opportunity.

Paint delay may skip intermediate render snapshots. It may not change logical visualizer behaviour or create catch-up update bursts.

### 4.4 Transition completion

Transition progress uses monotonic elapsed time.

Completion is local:

- destination becomes base;
- source/temporary resources release;
- transition becomes inactive.

No distributed terminal transaction is part of the stable architecture.

## 5. Visualizer Contract

- Visualizer behaviour is mode-owned and protected.
- Spectrum, Sine Waves, Bubble, Dev Curve, Oscilloscope, and other supported modes retain distinct attack, decay, smoothing, responsiveness, and motion.
- Shared infrastructure changes must not flatten or overdamp modes.
- Simulation does not subscribe to transition cadence.
- Simulation does not wait for compositor paint.
- Render-state coalescing occurs only after logical input/simulation processing.
- Mode-specific arrays/history/work do not bleed across activation.
- All activation paths consume one resolved mode/preset payload.
- A narrow explicit renderer interface replaces compatibility forwarding.
- Deterministic timestamped feature replay uses the same logical simulation/tick path as live analysis and remains independent of presentation opportunities.
- Baseline fixtures and golden logical outputs are versioned; infrastructure verification is read-only and may not regenerate them.

Focused behaviour and settings contracts live in the existing visualizer documents.

## 6. GL and Lifecycle Contract

- All GL creation, mutation, and deletion occurs on the owning thread with the correct context current.
- Every GL resource has one owner, context/share generation, byte size, and deterministic deletion path.
- Compiled shader program IDs and uniform locations are compositor-local owner state. Reusing stateless shader helpers does not authorize sharing numeric GL handles; cross-compositor sharing requires explicit leases and exactly-once deletion.
- `ResourceManager` records GL identity and bytes passively; it never deletes a GL handle or substitutes for the context-bound owner.
- GPU timer-query diagnostics use a fixed owner-local handle set, poll availability without waiting, report unavailable/pending/dropped samples explicitly, and delete on the exact owner context. They never become presentation or cadence control flow.
- Context-affinity errors are never suppressed as routine cleanup.
- Settings, Edit, topology changes, and exit stop old work before destroying old GL resources.
- Compositor/surface destruction occurs after child/native resource cleanup.
- Late worker results are rejected by lifetime generation.
- Partial GL reinitialization is not part of the stable architecture unless separately designed and approved.
- Settings and committed CUSTOM Edit perform full display teardown before dialog/reload work and build a fresh `DisplayManager` afterward. Replacement construction is forbidden until the retiring generation's watched QObject roots have actually been destroyed and its runtime-scoped resources, tasks, timers, animations, and global subscriptions are absent.
- A successful RUN session is owned by explicit engine, tray, and error exit routes rather than Qt's top-level-window count. The intentional zero-window interval between Settings/dialog destruction and replacement construction must not quit the application; startup-failure/configuration-only paths retain their normal window-owned lifetime.
- Runtime generation invalidation rejects queued and delayed GUI/worker publication as well as new work. Valid publication requires the current engine runtime generation, exact owning `DisplayManager`, and any mode-owned engine generation/activation identity.
- The old-runtime destruction barrier and the replacement's authoritative-first-frame barrier are separate. Passing destruction never authorizes reveal; a replacement remains hidden until its own generation produces authoritative presentation state and the existing `FadeCoordinator` releases it.
- Large image shared-memory is transfer-scoped: the worker retains only the in-flight producer handle until parent attachment, the parent owns consume/unlink, and every timeout/cancel/rejection/buffer/shutdown path disposes payload resources before dropping a response.
- `DisplayWidget.cleanup_runtime()` is the normal synchronous owner; `QObject.destroyed` is only a residual safety net.
- A compositor remains `DESTROYING` and retains failed resource ownership when context acquisition or GL deletion cannot be proved.
- Teardown does not spin nested event processing, run production garbage collection, trim memory, recycle processes/workers, reuse retired trees, or construct a replacement while the old graph is merely queued through `deleteLater()`.
- Correctness never depends on optional deferred warmup.
- Primary overlays reveal through the display-local `FadeCoordinator` only after the first base frame and critical active resources are terminal. Optional transition shader/resource warmup runs one item per managed callback and pauses during coordinated overlay fades or any live display transition.

## 7. CPU and Threading Contract

- `ThreadManager` owns registered async tasks and workers; it is not a presentation clock.
- GUI and GL mutation remain on the GUI/context owner.
- Workers perform coarse I/O, decode, preparation, and measured pure computation.
- GUI-affine service/backend QObjects are construction-inert when initialization needs filesystem, JSON, credential decryption, or migration; workers publish detached snapshots and the GUI installs them through one coalesced, lifetime-gated authority.
- GUI-owned stable widget `QPixmap` caches are prepared at state/invalidation commit boundaries; paint may validate exact logical-size/DPR/revision identity and blit, but does not build a cold static layer or expose hit geometry that does not match the displayed cache.
- High-frequency tiny jobs are batched, coalesced, vectorized, or removed only when their logical inputs and visible authored behaviour remain intact. A reactive visualizer may not gain a second cadence authority or terminal-only multi-step batch that delays first-visible attack, consumes a discrete edge without publishing it, reduces loud-passage elasticity, or changes mode smoothing merely to lower task counts. Final-state/order/task-count tests do not authorize that change; runtime-shaped temporal validation and installed visual review are required.
- More Python threads are not assumed to provide multi-core scaling.
- Hidden/static systems stop unnecessary recurring work.
- Task accounting is direct and passive; diagnostics do not enqueue UI work.

## 8. Image, Memory, and GPU Resource Contract

- CPU image caches are bounded by exact logical bytes and entry count; persisted legacy limits are clamped to the supported production envelope.
- Prefetch concurrency, pending count, and future decoded/scaled bytes are bounded independently of cache residency.
- Display-owned `QPixmap` backing stores are captured on the GUI thread into detached accounting sidecars and deduplicated by Qt backing identity. Background usage sampling consumes detached display and ResourceManager aggregates; it never inspects live `QPixmap`, `DisplayWidget`, or QObject validity.
- GPU textures and upload-PBO retention are byte-accounted, byte-bounded, and generation-safe.
- Normal cycling reaches a stable RAM/VRAM plateau.
- Image representations have explicit owners and lifetimes.
- Workers may publish immutable thread-safe upload data.
- Workers do not create GUI-affine `QPixmap` or call GL.
- Media artwork is keyed and decoded to `QImage` in the existing media worker job. Unchanged keys are text-only updates; the GUI creates one `QPixmap` only when the applied key changes.
- Display-change and manual refresh requests do not bypass an existing media query; its generation remains authoritative through worker decode and UI consumption.
- Media artwork replacement, art-dependent layout invalidation, and artwork fade are coalesced newest-only while any live display is preparing or running a transition, then flushed together after the final display becomes idle.
- On startup, the media card owns reveal order: prepared artwork remains hidden until the coordinated card fade completes, then fades in once when all displays are transition-idle.
- Track title/artist changes publish painter-owned metadata immediately, but fixed-height/card-margin Qt setters run only when the actual structural footprint changes.
- External media-key routes converge through one process-wide 200 ms ingress claim before widget lookup, feedback, or refresh. The accepted route still preserves OS pass-through and wakes the visualizer; immediate duplicate routes do no widget work.
- Media providers are registered stable ids with exact GSMTC source identities. Unknown non-empty ids remain visible and inert; they never silently select or persist another provider.
- Browser GSMTC identifies the browser host rather than a website/tab. Browser-provider failover uses one background manager/session snapshot and may accept an exact matching current session even when enumeration is empty or nonmatching. Browser volume remains inert until that accepted snapshot identifies one registered host; it then targets `spotify.exe` first and only that exact browser's whole audio session as fallback, never an unrelated browser or tab-specific session.
- Optional media playback progress is part of that existing background GSMTC snapshot. It owns no timer, polling loop, animation or independent media query; the GUI stores a bounded timeline ratio and requests a repaint only when the pill's logical filled-pixel width or configured paint style changes. Invalid/unknown duration hides the pill, and a paused unchanged snapshot remains static.
- Media transport feedback remains immediate. While any display has transition work pending it is one static acknowledgement cleared by one managed, token-checked callback, not a frame-by-frame media-card repaint animation; normal idle presentation retains the authored fade.
- Visible paint does not decode, convert, or hash whole image buffers.
- Stable source and transform metadata provide normal identity.
- Shared texture reuse is legal only in a verified live share group with explicit leases and exactly-once deletion.
- Context-local GL objects remain context-local.
- Prefetch is bounded by bytes and outstanding work.
- Same-image reuse is permitted only for exact source/transform/size/mode/DPR identity; differing targets retain independent representations.
- Terminal transition completion or cancellation releases active texture pins; owner-context teardown returns application-owned GL resources to zero.
- Deterministic application-owned byte accounting is required in automation; driver-reported VRAM remains a real-platform validation gate.

## 9. Settings and Persistence Contract

- `SettingsManager` owns settings read/write/migration.
- Public mutation becomes authoritative in memory immediately and synchronously invalidates/notifies every live manager for the same profile path.
- One process-scoped ordered persistence writer, outside runtime generations, owns routine JSON serialization, temp-file fsync and durable atomic replacement for all profiles; one shared store authority exists per normalized path.
- Store revisions are monotonic. Only complete superseded snapshots still pending for the same store may coalesce; an older or failed write cannot be acknowledged over newer in-memory state.
- Routine save/sync requests persistence. Explicit bounded flushes acknowledge durability at startup repair/migration completion, Settings completion, reload and process shutdown; failed writes remain dirty and retryable.
- Canonical defaults and profile differences remain single-source.
- Root/section writes invalidate dependent caches.
- All widgets-map/import mutation routes use one normalization contract.
- Reset/import preservation is centralized.
- Public mutation APIs have coherent persistence and notification semantics.
- Credentials and machine-private identity do not enter normal settings exports.
- Visualizer mode-owned technical settings remain mode-owned.

Detailed rules live in focused defaults/settings documents.

## 10. Widget and CUSTOM Layout Contract

- Widget family metadata is descriptor-owned.
- Widget setup has one authority.
- Shared service-widget lifecycle mechanics remain centralized without absorbing provider behaviour.
- CUSTOM layout uses one normalized display-local contract.
- Persisted geometry is display-bounded and DPR-aware.
- Live content refresh cannot silently override committed CUSTOM geometry.
- Edit is a coordinated active-display session.
- Drag/resize feel and recovery affordances are product contracts.
- Settings/Edit widget work follows the runtime lifecycle contract.

## 11. Diagnostics Contract

Diagnostics are:

- CLI-first;
- family-scoped;
- sampled;
- bounded;
- passive;
- privacy-safe.

Ordinary records may declare immutable multi-family routing metadata. Valid explicit
metadata is authoritative, supports delivery to more than one existing family sidecar,
and does not replace visible human/parser tags. Unclassified and third-party records
retain compatible name/tag fallback, and every WARNING+ remains main-visible.

Ordinary standard and Media Center packaged launches remain diagnostics-off.
An installable diagnostic product activates all existing diagnostic families
only through its explicit compiled entry-point identity. It uses one separate
bounded rotating-log directory beside its executable with per-user fallbacks,
never registers as or replaces the
standard screensaver, never owns or mutates the secure-desktop helper, and is
not a performance-baseline authority.

After a destruction barrier has already timed out and committed its fail-closed
exit, the explicit diagnostic product may take an aggregate-bounded,
identity-only direct-referrer batch for surviving plain-Python owners. The
owner count, `gc.get_referrers()` query count, Python-side inspection, and log
payload must all be capped; an individual CPython referrer query is diagnostic
and not pre-emptible. Attribution may not call `gc.collect()`, retain owners
beyond the timeout call, change completion policy, expose object
representations/settings payloads, or run in standard/Media Center products.

They must not:

- repaint;
- retune visualizers;
- alter cadence;
- lower quality;
- create per-component or unbounded observation timers or queues;
- become runtime control flow.

Exactly one app-owned, opt-in, bounded, low-rate event-loop lateness sampler is permitted. It is a diagnostic recorder only: it may aggregate and report sampled lateness, but must never control scheduling, cadence, quality, lifecycle, retries, or any other runtime behaviour.

## 12. Validation Contract

Tests are necessary but not sufficient for:

- visual fidelity;
- frame pacing;
- focus/windowing;
- multi-display presentation;
- GL lifecycle;
- RAM/VRAM behaviour.

High-risk changes require:

- focused automation;
- runtime-shaped validation;
- p95/p99/max timing;
- memory/resource accounting;
- repeated lifecycle tests;
- manual visual review where applicable.

Detailed validation lives in `Docs/TestSuite.md` and `Docs/Harness_Index.md`.

## 13. Current Architecture Boundary

Current `main` is the implementation and design authority. Historical baseline and
candidate commits may be used as forensic references or negative controls, but they are
not merge targets, implementation starting points, or competing architecture owners.

The stable architecture excludes:

- adaptive presentation workers;
- producer-to-paint acknowledgement;
- compositor-owned visualizer cadence;
- distributed terminal transactions;
- partial GL reinitialization;
- compatibility mega-layers;
- hot-path whole-buffer identity hashing.

The detailed current design and active architecture roadmap live in
`Docs/Compositor_Architecture.md` and `Docs/audits/SRPSS_Architecture_Roadmap/`.
