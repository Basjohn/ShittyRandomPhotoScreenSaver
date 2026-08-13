# 07 — GL Lifecycle and Reconfiguration

Last reconciled: 2026-08-10

## Current Boundary

Full stop–destroy–recreate for Settings and committed Edit is solved architecture and a
regression contract. The compiled callback-retention/Diagnostic investigation is closed.
Do not reopen those incidents as a performance task.

The active GL questions are now **texture identity/reuse, GPU attribution and absolute
resource efficiency**.

## Durable Lifecycle Contract

- runtime coordinator admits stop/reload after originating owner frames return;
- retire old runtime generation and reject late publications;
- stop producers/timers before deleting display/GL ownership;
- make the sole owner context current for GL mutation/deletion;
- one numeric GL handle has one deletion owner;
- failed deletion retains ownership and fails closed;
- destroy compositor surfaces after child GL ownership is gone;
- destruction barriers prove release and never force it with GC/retry/event pumping;
- replacement construction waits for zero retired ownership;
- reveal waits for fresh current-generation authoritative state.

Stable weak forwarding callbacks at Qt→plain-Python lifetime seams are an accepted
ownership mechanism where PySide/Nuitka bound wrappers can otherwise retain a manager.

## Active Texture Identity Defect

The current terminal retention mechanism keeps a bounded current texture/PBO, but live
telemetry proves that repeated steady transitions do not find that retained current
texture under the next old-image lookup key. Acceptance is identity-level, not merely a
lower upload count:

- unchanged context/generation/size/source transform → retained current is next old;
- old is cache-hit before warm;
- steady transition allocates/uploads only the new image;
- explicit invalidation/resize/context boundaries may legitimately miss and must name why;
- strict full teardown still reaches zero.

Do not enlarge texture budgets or retain historical image sets to hide the identity bug.

## GPU Timing Contract

Transition profiling must cover every transition family through a shared compositor
paint seam. Ordinary `--perf` performs no query-driver calls. The explicit heavyweight
`--gpu-timing` profile uses sampled asynchronous/non-blocking GL timer queries with
delayed collection where supported. Never `glFinish()` to obtain a number. Log support,
observation, sampled-out, poll and collected counts.

Separate:

- texture upload/warm;
- shader/draw execution;
- swap/presentation/context work;
- visualizer overlay/context work;
- CPU/event-loop delay.

## Worker Publication

Workers return immutable, generation-labelled results. GUI/context owners reject stale
results before QWidget/QPixmap/GL mutation. Cancellation is bounded; worker completion
is not permission to publish into a retired runtime.

## First-Frame Contract

Destruction completion authorizes construction, not reveal. GL initialization, timer
fire, stale cache, previous visualizer state or a random paint opportunity cannot satisfy
fresh-frame authority.

## Verification

- focused texture identity/reuse tests plus live exact-key telemetry;
- repeated transition families with one terminal bracket and truthful GPU samples;
- resize/context/recreation invalidation boundaries;
- strict zero GL ownership on teardown;
- no cross-thread/currentness errors;
- visualizer cadence/feel unchanged by GL optimization;
- process GPU busy and VRAM measured separately.
