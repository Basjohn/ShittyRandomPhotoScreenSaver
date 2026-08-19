# Visualizer Presentation Guardrails

Last updated: 2026-08-19

Read after `Docs/Presentation_Change_Preflight.md` for any visualizer cadence, source freshness,
render-state, fade/readiness or presentation work.

For Bubble timing/feel also read `Docs/Guardrails/Bubble_Temporal_Fidelity.md` (**BTF**).

## 1. Current owner boundary

There are separate authorities with one-way handoffs:

```text
audio / analysis owner
        ↓ source snapshots
VisualizerLogicalRuntime
        ↓ latest logical publication
GUI presentation owner
        ↓ current scene state
display compositor
        ↓
physical presentation
```

### Logical runtime

`VisualizerLogicalRuntime` is the one mode-general authored visualizer clock.

It is current architecture, not a future proposal.

Worker-callable code owns:

- authored logical deadline/dt;
- source snapshot consumption;
- mode simulation;
- envelopes/events/transients;
- visual-only motion state;
- latest plain-data logical publication;
- readiness decisions that do not mutate GUI state.

It does **not** own:

- QWidget show/hide/update;
- presentation geometry mutation;
- QPixmap/QPainter;
- fade execution;
- card/shadow raster;
- compositor/GL mutation.

### GUI/compositor

The GUI half consumes the latest publication and owns reveal/layout/card/GL-facing commit.

The display compositor owns physical presentation opportunity and pixels.

## 2. One logical clock

The production visualizer logical clock is the dedicated runtime.

Forbidden logical owners:

- recurring GUI visualizer timer;
- AnimationManager visualizer listener;
- per-mode logical timers;
- hidden fallback logical timer;
- physical compositor timer.

Qt timers may remain for real UI/lifecycle/fade deadlines.

## 3. Logical cadence rules

- preserve authored source/logical cadence;
- integrate every logical input before presentation coalescing;
- never derive logical dt/event consumption from paint;
- never pause simulation until paint;
- never catch up by replaying stale deadlines;
- never mutate logical arrays in compositor render callbacks;
- measure scheduler health by achieved cadence and gap tails, not callback body time alone.

## 4. Latest-state publication

The logical-to-GUI handoff is one-slot/latest-wins.

Allowed:

```text
N published
N+1 supersedes N before GUI consumes
GUI consumes N+1
```

Forbidden:

- FIFO render queue;
- callback posted to GUI for every logical publication;
- paint acknowledgement/backpressure;
- catch-up replay.

Every authored event must integrate before its state may be superseded.

Protected short-lived visible edges require explicit edge-survival tests.

## 5. Physical presentation

The display compositor's existing render strategy is the sole physical presentation strategy for
that display.

It may stay active for transition, visualizer or other scene reasons.

It is not the logical visualizer clock.

R-61/R-62 remain negative controls against transition-scoped/paint-coupled pacing of a separate
visualizer surface. They do not ban the current display compositor's physical adaptive strategy.

## 6. Dispatch / admission

A queued-GUI dispatch guard may prevent duplicate queued Python callbacks only until the callback
actually executes.

Paint completion does not release the next producer or display deadline.

Forbidden:

- pending-until-paint;
- paint/swap acknowledgement;
- producer timestamp/display-rate gate;
- repaint rescue/retry;
- render self-requeue;
- source/event decimation.

## 7. Readiness: presentation vs reactive source

Never overload “fresh source” to mean “allowed to display anything.”

At minimum:

```text
presentation_ready
reactive_source_ready
```

Presentation readiness may include:

- current runtime/QRhi generation;
- renderer GL resources;
- card texture;
- authoritative geometry;
- valid presentation owner.

Reactive-source readiness concerns current real analysis/source identity.

### Paused Spectrum

Paused Spectrum may be:

```text
presentation_ready = true
reactive_source_ready = false
waiting_for_fresh_engine_frame = true
source generation/activation = absent
```

Its idle baseline is presentation-owned state.

Do not fabricate source identity.

When Play occurs, fresh current-generation/current-activation real data replaces the idle scene in
place.

## 8. Fade authority

The compositor owns visualizer/card pixels from fade zero through completion.

One scalar/easing authority applies to both card and shader.

No midway QWidget/compositor opacity handoff.

A presentation-owned idle scene may fade in when presentation-ready even while reactive source
authority remains false.

## 9. Source freshness

Measure separately:

```text
capture/source age
logical integration
logical publication
GUI dispatch age
state-to-paint age
physical display delivery
```

Smooth motion over stale audio is not healthy.

Do not retune shader/Bubble smoothing to compensate for source staleness.

## 10. Pause / Play

Ordinary Pause/Play:

- keeps the logical runtime alive;
- preserves mode/card/GL identity;
- changes authored logical playback/idle state promptly;
- keeps capture lifetime under BeatEngine policy;
- does not enter cold startup on warm resume;
- does not reintroduce a visualizer pause debounce.

Identity continuity is necessary but does not prove perceptual continuity.

If the edge still hitches, inspect edge-owned GUI/presentation work with current evidence.

## 11. Fidelity

Preserve all mode personality and current goldens.

For Bubble, BTF additionally binds:

- authored shape;
- logical cadence/gap tails;
- source freshness;
- protected event/positional-edge survival;
- state-to-screen timing;
- final perceptual result.

Average FPS or a green deterministic replay cannot overrule a BTF failure.

## 12. Generation fencing

Generation/activation are ownership identity.

Valid `0` stays valid `0`.

Never use truthiness conversion that turns zero into an invalid sentinel.

Retired generation state cannot:

- enter replacement mailbox/presentation;
- trigger reveal;
- mutate current GUI/GL state.

## 13. Validation

Runtime-shaped tests must cover:

- scheduler actual cadence;
- one logical clock;
- worker thread cannot reach GUI/GL;
- all five modes actually reveal;
- paused Spectrum actual rendered idle visibility;
- source authority remains separate;
- quick Pause/Play identity **and** no-hitch/delivery behavior;
- valid generation 0 fencing;
- 60 Hz and high-refresh physical presentation;
- injected GUI stalls;
- Settings/Edit recreation;
- short-lived Bubble visible edge;
- BTF.

Installed manual review remains required for visual/timing changes.
