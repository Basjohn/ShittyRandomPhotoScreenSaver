# Spec

Last updated: 2026-07-29

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
- Context-affinity errors are never suppressed as routine cleanup.
- Settings, Edit, topology changes, and exit stop old work before destroying old GL resources.
- Compositor/surface destruction occurs after child/native resource cleanup.
- Late worker results are rejected by lifetime generation.
- Partial GL reinitialization is not part of the stable architecture unless separately designed and approved.
- Settings and committed CUSTOM Edit perform full display teardown before dialog/reload work and build a fresh `DisplayManager` afterward.
- Delayed GUI/worker publication is valid only when both the engine runtime generation and exact owning `DisplayManager` still match.
- Large image shared-memory is transfer-scoped: the worker retains only the in-flight producer handle until parent attachment, the parent owns consume/unlink, and every timeout/cancel/rejection/buffer/shutdown path disposes payload resources before dropping a response.
- `DisplayWidget.cleanup_runtime()` is the normal synchronous owner; `QObject.destroyed` is only a residual safety net.
- A compositor remains `DESTROYING` and retains failed resource ownership when context acquisition or GL deletion cannot be proved.
- Correctness never depends on optional deferred warmup.
- Primary overlays reveal through the display-local `FadeCoordinator` only after the first base frame and critical active resources are terminal. Optional transition shader/resource warmup runs one item per managed callback and pauses during coordinated overlay fades or any live display transition.

## 7. CPU and Threading Contract

- `ThreadManager` owns registered async tasks and workers; it is not a presentation clock.
- GUI and GL mutation remain on the GUI/context owner.
- Workers perform coarse I/O, decode, preparation, and measured pure computation.
- High-frequency tiny jobs are batched, coalesced, vectorized, or removed.
- More Python threads are not assumed to provide multi-core scaling.
- Hidden/static systems stop unnecessary recurring work.
- Task accounting is direct and passive; diagnostics do not enqueue UI work.

## 8. Image, Memory, and GPU Resource Contract

- CPU image caches are bounded by exact logical bytes and entry count; persisted legacy limits are clamped to the supported production envelope.
- Prefetch concurrency, pending count, and future decoded/scaled bytes are bounded independently of cache residency.
- Display-owned `QPixmap` backing stores are captured on the GUI thread into detached accounting sidecars and deduplicated by Qt backing identity.
- GPU textures and upload-PBO retention are byte-accounted, byte-bounded, and generation-safe.
- Normal cycling reaches a stable RAM/VRAM plateau.
- Image representations have explicit owners and lifetimes.
- Workers may publish immutable thread-safe upload data.
- Workers do not create GUI-affine `QPixmap` or call GL.
- Media artwork is keyed and decoded to `QImage` in the existing media worker job. Unchanged keys are text-only updates; the GUI creates one `QPixmap` only when the applied key changes.
- Media artwork replacement, art-dependent layout invalidation, and artwork fade are coalesced newest-only while any live display is preparing or running a transition, then flushed together after the final display becomes idle.
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

## 13. Recovery Boundary

Recovery work is based on:

```text
main (based on baseline)
00edb57a3076b845cb8ee4b6cb7f36ea83411f0c
```

Donor reference:

```text
donor-7376bb9
7376bb9bb380253f3bd14079e65d7bdbca062fad
```

The donor branch is reference-only, read-only, and not a merge target.

The stable architecture excludes:

- adaptive presentation workers;
- producer-to-paint acknowledgement;
- compositor-owned visualizer cadence;
- distributed terminal transactions;
- partial GL reinitialization;
- compatibility mega-layers;
- hot-path whole-buffer identity hashing.

The detailed recovery design lives in `Docs/Compositor_Architecture.md`.
