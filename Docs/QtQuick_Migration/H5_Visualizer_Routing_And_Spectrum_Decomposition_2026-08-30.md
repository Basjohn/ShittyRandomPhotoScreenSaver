# H5 Technical Decomposition — Visualizer CUSTOM Routing and Spectrum Saturation

Date: 2026-08-30  
Starting source: `af8896b52fbee153fe1cd0b627a55455c14625d1`

This decomposition covers two independent functional Visualizer regressions. Keep them separate in implementation and testing.

## Part A — CUSTOM cross-display admission

### Product contract

Outside CUSTOM:

```text
Visualizer effective position/monitor = Media effective position/monitor
```

Inside committed CUSTOM:

```text
Visualizer effective position/monitor = spotify_visualizer's own persisted CUSTOM route
```

CUSTOM may:

- overlap ordinary widgets;
- live on a different selected display from Media;
- transfer between selected displays;
- persist/rebuild on the new display.

There is still exactly one product Visualizer owner.

### Current-source evidence

`rendering/widget_descriptors.py` already implements the route-key split.

`DisplayManager._resolve_visualizer_requested_screen_index()` already calls the effective-monitor authority.

`QuickDisplayUnit.is_visualizer_participant()` only requires a live, non-binding-lost Quick unit. It does not require a Media card on that screen.

`QuickCustomLayoutOwner.save()` specially persists the Visualizer's current display monitor.

Therefore do not add another route system. Find where the existing truth is being lost.

### Diagnostic record

Emit one bounded generation-level record:

```text
runtime_generation
spotify_visualizer.enabled
spotify_visualizer.position
spotify_visualizer.monitor
media.enabled
media.monitor
is_custom
effective_monitor
requested_screen_index
participants=[screen_index, participating, binding_loss]
failover_state=[target, grace_generation, fallback]
chosen_screen
construct_result
reject_reason
```

Do not emit per-frame routing logs.

### Decision tree

1. `is_custom=False` unexpectedly:
   - inspect persisted `position` after CUSTOM Save and hydration;
   - fix persistence/hydration owner.
2. `is_custom=True`, `effective_monitor` equals Media:
   - effective routing regression; fix descriptor caller/data shape.
3. effective monitor correct, requested screen correct, but participant missing:
   - inspect selected display creation/binding loss.
4. participant exists but failover holds/chooses wrong unit:
   - fix failover/reconcile contract.
5. chosen unit correct but `_construct_quick_visualizer_owner_on()` returns false:
   - instrument exact capability/instance/activation rejection.
6. owner exists on screen 2 but no pixels:
   - then inspect retained scene transfer/admission; do not duplicate owner.

### Tests

Supplied semantic pin:

```text
tests/test_visualizer_custom_route_contract.py
```

Add a production admission test after localization:

```text
Media monitor 1
Visualizer position Custom
Visualizer monitor 2
participants 0 + 1 live
=> chosen owner screen_index 1
=> exactly one owner

same but Visualizer non-Custom
=> chosen owner screen_index 0
```

Also preserve missing-monitor 30 s grace/fallback/reclaim behavior.

## Part B — Spectrum saturation + wrong renderer topology

### Physical symptom

The current Spectrum/Organ result is wrong in two distinguishable ways:

1. energy is effectively pinned/saturated;
2. the **representation family itself is wrong** — a dense screen-filling matrix of tiny segmented blocks appears where the established Organ/Spectrum presentation uses bottom-aligned continuous vertical frequency columns.

The second point matters: all-1.00 data can make bars uniformly tall, but it cannot by itself explain a renderer drawing hundreds of repeated mini-cells instead of the intended column topology.

### Historical reference boundary

For user-visible Spectrum/Organ intent only:

```text
Primary broad visual baseline:
  release 4.7.2 screenshot
  https://github.com/Basjohn/ShittyRandomPhotoScreenSaver/releases/tag/4.7.2

Secondary broad baseline:
  release 4.7.0 screenshot
  https://github.com/Basjohn/ShittyRandomPhotoScreenSaver/releases/tag/4.7.0

Cleaner historical behavior code:
  15099d389e5091942a0ce3d6e6311d33b6043d3d

Later mixed reference:
  3fe5df687387b6b6a121142372c43a7719442386
```

`3fe5df6` already contains migration-era work. Neither historical commit is an implementation source for current H. Extract the neutral visible invariant only.

### Latest data evidence

Spectrum successfully switches/loads:

```text
Quick mode activation committed mode=spectrum
spectrum.frag loaded
bar_count=35
```

But the authored/computed bar sidecar repeatedly reports:

```text
[1.00, 1.00, ...] x35
```

Around the saturated frames, floor telemetry also shows Spectrum dynamic floor/gate inputs and a large expansion value (`5.527`).

### Two-branch investigation

#### B1 — data/shaping

Capture one bounded sample at each Spectrum-only layer:

```text
D0 audio FFT/bin magnitudes
D1 frequency-band aggregation
D2 resolved mode/preset technical parameters
D3 pre-floor/pre-expansion Spectrum bars
D4 post-floor/expansion/gain bars
D5 upper clamp count + final bar vector
D6 render snapshot bar payload
```

Stop where healthy variation first becomes persistent upper-bound saturation.

Likely classes to test, not assume:

- preset overlay applied twice;
- mode-specific gain/expansion interpreted in the wrong domain;
- dynamic floor support value used as multiplier rather than gate;
- wrong normalization reference;
- clamp ordering error;
- technical settings carried incorrectly from another mode during switch/recreation.

#### B2 — presentation identity/topology

Trace:

```text
P0 canonical mode id
P1 preset identity
P2 render snapshot mode/preset
P3 renderer implementation selected
P4 primitive/topology parameters (columns vs segments/cells)
P5 geometry/uniforms
P6 retained node drawn mode/preset
```

Find why the Organ/Spectrum path resolves to a dense segmented matrix rather than continuous frequency columns.

Possible classes to inspect, not assume:

- wrong renderer/preset implementation selected;
- a segmented visualization primitive reused accidentally;
- bar-count interpreted as rows/segments rather than columns;
- stale mode-specific geometry/technical payload surviving a mode switch;
- QSG node retaining topology from another mode.

Do not begin by copying old Spectrum renderer code. Recreate the correct presentation contract in the accepted retained Quick path.

### H acceptance

H5b is GREEN when:

- correct Spectrum mode/preset identity survives switch/recreation;
- live input produces non-degenerate bar variation;
- the final bar vector is not persistently all upper-bound;
- Organ/Spectrum renders the correct **basic continuous-column frequency representation**, not the current dense block matrix;
- one retained Spectrum owner/draw path remains;
- shared cadence/Bubble behavior is untouched.

H stops there.

J Parity+ then owns:

```text
column width/gap
outline thickness
gradient/rainbow distribution
glow strength
shell relationship
fine height/easing feel
overall elegance versus historical screenshots
```
## Part C — Bubble is deliberately excluded from this repair

Bubble still has a physical reactivity complaint. Do not alter its cadence, growth, sensitivity or physics in this H5 work merely because Spectrum is being touched.

Preserve:

- ~90 Hz authored cadence;
- requested/integrated ratio;
- one logical runtime;
- current good partial/CUSTOM resizing.

Only a separately proven stale/delayed source/logical/publication seam should promote Bubble out of J.
