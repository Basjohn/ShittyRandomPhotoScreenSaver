# P2 Behavioral Gates — Stabilized Reference + Qt Quick Architecture Spike

## A. Worker reference gates

### A1 Dedicated logical cadence
- one logical clock;
- ~90 Hz authored class;
- no old ~64 Hz scheduler collapse.

### A2 Push restoration
- latest mailbox semantics;
- at most one pending GUI presentation callback;
- no FIFO/catch-up;
- no pull-at-paint liveness machinery.

### A3 Spawn/reveal
- cold startup physically paints visualizer;
- no 10–30 second zero-paint intervals;
- Settings/recreate repeats deterministically.

### A4 K remains non-blocking
- transport command ingress returns before backend completion;
- restoring push may not restore synchronous GSMTC waiting.

### A5 Playback-state epoch
- stale pre-command refresh result cannot reverse newer optimistic state;
- one accepted command yields one visualizer playback edge unless genuinely newer authoritative state reverses.

## B. Integrated benchmark gates

### B1 Two-display production-shaped workload
165 Hz Blockspin + 60 Hz visualizer + deterministic ~90 Hz synthetic source.

### B2 Repetition
Three identical runs for each architecture/load condition.

### B3 Metrics
FPS, request acceptance, logical cadence, dt tails, frame-gap classes, media.paint, CPU/GPU,
publish-to-physical age, first paint, playback edges.

### B4 Controlled load
Both low-load and repeatable heavy-load modes.

## C. Qt Quick spike gates

### C1 Real QQuickWindow
Standalone top-level `QQuickWindow` per display.

`QQuickWidget` is explicitly disallowed for the architecture proof.

### C2 Threaded render loop proven
Enable Qt scene-graph logging and record:
- selected render loop;
- GUI thread id;
- render thread id per window.

No claim of threaded presentation without this proof.

### C3 Existing authored workload
Representative current OpenGL Blockspin + Bubble/Spectrum render logic.
No fidelity-cut substitute.

### C4 No-vsync topology
60/165 Hz, swap interval 0/no-vsync policy retained.

### C5 No extra full-screen offscreen pass in the first benchmark
Prefer direct/native underlay or inline scene-graph render path.

### C6 Startup
First current-generation frame deterministic.

### C7 Performance migration bar
Repeated Quick result must materially beat worker+push under controlled load and improve tail gaps.

A prettier architecture with equal/worse product behavior is rejected.

### C8 Failure decision
If Quick does not materially improve delivery, do not port the runtime UI.
Escalate to a small native physical renderer candidate rather than more QWidget scheduling tweaks.
