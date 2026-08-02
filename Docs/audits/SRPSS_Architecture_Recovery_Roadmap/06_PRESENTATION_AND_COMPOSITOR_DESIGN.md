# 06 — Presentation and Compositor Design

Last reconciled: 2026-08-02

## Design objective

Provide predictable display-local presentation without recreating donor scheduling failure or the rejected Spectrum second-cadence experiment.

One surface per display remains a later architecture target. It is not required for current Phase 5 fixes and does not authorize moving simulation, lifecycle, or scheduling into the compositor.

## Absolute presentation rules

Do not port or introduce:

- adaptive timer workers waiting for paint;
- dirty/requested/acknowledged frame-generation protocols;
- producer waits for `paintGL()` or `update()` completion;
- compositor cadence starvation as ordinary control flow;
- compositor-owned visualizer simulation/cadence;
- self-requested visualizer repaint loops;
- paint-derived clocks;
- authoritative state mutation in `paintGL()`;
- distributed transition terminal transactions;
- broad compatibility forwarding;
- hidden fallback presentation paths;
- retry/backoff state for ordinary frame delivery.

There is one authoritative visualizer presentation cadence. A compositor paint is a consumer opportunity, not a new animation clock.

## Current approved visualizer boundary

The current approved Bubble/Spectrum runtime is `ff934616`, code-equivalent to the ordinary-executor restoration at `4bde89e`.

Presentation work must preserve:

- shared-source ordering and event integration;
- mode-owned authored steps;
- engine generation and activation identity;
- source-to-first-visible behaviour;
- authoritative state publication cadence;
- mode/activation/generation resets.

No compositor/presentation refactor may reintroduce the rejected `666624d` lane scheduling or `ebfec397` paint-local smoothing shapes.

## Latest-state presentation model

When an authoritative producer/controller accepts new immutable state:

1. logical work and events are fully integrated;
2. current render/scene state is replaced atomically or on the GUI owner;
3. one GUI-local update request may be coalesced;
4. Qt paints the latest accepted state when it has an opportunity.

The compositor may skip intermediate immutable render snapshots. It may not cause logical events, authored steps, or scheduler publications to be skipped.

## GUI-local update coalescing

A display-local coalescing flag is acceptable only as request deduplication:

```text
update_requested: bool
```

Rules:

- only the GUI/display owner mutates it;
- producers never wait for it;
- it does not count or acknowledge logical frames;
- clearing it does not advance simulation or smoothing;
- if current scene state changed while a paint was pending, one later request may be posted by the GUI owner;
- no paint method recursively becomes the animation scheduler.

The flag must not become requested/acknowledged generations or a producer backpressure channel.

## Local compositor animation

The compositor may request continued frames only for animation it genuinely owns, such as an active image transition.

That continuation mechanism:

- is GUI-thread owned;
- exists only while compositor-local animation is active;
- uses monotonic time;
- stops when the local animation is static/complete;
- does not advance visualizer state;
- does not submit a worker task per frame;
- does not wait for paint acknowledgement;
- does not emit catch-up bursts;
- is not reused as a generic visualizer or overlay scheduler.

A visualizer remaining active is not by itself permission for a compositor-local timer. Visualizer state publication follows the established visualizer authority.

## Spectrum second-cadence guard

The rejected paint-local smoothing experiment produced roughly 977–1000 authoritative state updates but 1417–1544 paints per ten seconds and was reported significantly less smooth.

Therefore:

- no `paintGL()` or render callback may advance Spectrum smoothing;
- no falling-value decay continuation may self-request more paints;
- no overlay-local timer may create additional state updates;
- paint count above publication count is not proof of smoother motion;
- any future smoothing experiment runs on the existing authoritative tick only and requires explicit user approval.

## Scene composition order

Define explicit display-local order, for example:

1. clear/background;
2. base image or transition;
3. visualizer render state;
4. metadata/text/widget overlays;
5. interaction/cursor halo;
6. diagnostics when enabled.

Do not depend on display 0, stacked-widget z-order, or a cross-display singleton for visibility or updates.

## Display independence

Each display owns:

- its surface/context;
- viewport/DPR;
- scene snapshot;
- local resource owners/leases;
- update-coalescing state;
- compositor-local transition continuation.

Global controllers may publish shared logical state. They may not make one display the implicit presentation owner for all displays.

Tests intentionally vary primary display, indices, resolution/DPR/refresh, one/all display routes, and topology changes.

## Immutable scene snapshot

A snapshot contains explicit current-generation identities, such as:

```text
SceneSnapshot
- runtime_generation
- context_generation
- exact display identity
- base resource/lease
- optional TransitionSnapshot
- optional visualizer render state with engine/activation identity
- overlay/widget state
- viewport/DPR
- scene_generation
```

The compositor does not mutate producer-owned state or retain old snapshots without a bounded reason.

## Transition design

A transition owns:

```text
TransitionSnapshot
- source resource reference
- destination resource reference
- start monotonic timestamp
- duration
- easing identity/parameters
```

At presentation:

```text
progress = clamp((now - start) / duration, 0, 1)
```

Local exactly-once finalization:

- destination becomes base;
- source transition ownership releases;
- temporary FBO/PBO/texture state releases;
- transition becomes inactive;
- no worker/image-pipeline acknowledgement is required.

Interrupted, replaced, resized, Settings, Edit, and topology paths must release the same ownership deterministically.

## First-frame and reveal boundary

A newly reconstructed display remains hidden until fresh authoritative state from its current runtime and exact owner identities is ready.

Paint opportunity, GL initialization, timer fire, stale cached state, old visualizer publication, or construction alone cannot satisfy readiness.

Presentation changes may not bypass `FadeCoordinator` or create another reveal authority without a separately approved design.

## Frame-pacing evidence

Record:

- authoritative state publication rate;
- scene replacement rate;
- coalesced update count;
- `update()` request rate;
- paint rate and intervals;
- paint duration;
- latest-state age at paint;
- source-to-first-visible latency;
- skipped render snapshots versus dropped logical events;
- transition progress at presentation;
- event-loop lateness and transition/GUI-stall markers.

Paint rate is diagnostic only. More paints are not automatically better.

## Failure behaviour

If presentation is late:

- draw current accepted state;
- do not replay stale snapshots;
- do not flood Qt;
- do not block producers;
- do not create a new scheduler/cadence;
- record bounded diagnostics;
- preserve local exactly-once resource release.

## Acceptance criteria

- zero producer-to-paint waits;
- zero second visualizer cadence;
- zero paint-local authoritative mutation;
- no persistent update-queue growth;
- source-to-first-visible and p99/max meet the approved gate;
- user reports no visualizer degradation;
- cursor halo/UI remain smooth;
- transitions do not visibly jump under controlled idle conditions;
- Settings/Edit full lifecycle remains safe;
- active resource usage does not increase without explained benefit;
- known-bad `ebfec397` fails the presentation guard.