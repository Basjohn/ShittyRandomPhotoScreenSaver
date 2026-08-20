# Visualizer Reference

Last updated: 2026-08-20

Current visualizer behaviour and accepted presentation destination.

## 1. Modes

Canonical mode ids remain owned by the settings/mode registry:

- `spectrum`
- `oscilloscope`
- `sine_wave`
- `bubble`
- `devcurve`

## 2. Capability model

| Mode | Idle reveal | Idle self-animation | Presentation-owned idle scene | Fresh real source required for reactive playback |
|---|---:|---:|---:|---:|
| Bubble | yes | yes | no | no |
| Spectrum | yes | no | yes | yes |
| Sine | yes | yes | no | no |
| Oscilloscope | yes | yes | no | no |
| DevCurve | yes | yes | no | no |

Paused Spectrum remains intentionally mixed:

```text
presentation_ready = true
reactive_source_ready = false
source identity = absent
```

## 3. Logical cadence

Primary owner:

`VisualizerLogicalRuntime`

Supporting logical/source modules remain Python.

Current durable flow:

```text
source/audio
    -> VisualizerLogicalRuntime
    -> latest plain-data state
    -> presentation bridge
    -> Quick scene/render owner
```

During migration, old GUI `present_tick`/compositor code may still be the current implementation.
It is not the destination contract.

## 4. Presentation ownership

Destination:

- visualizer pixels live inside the display's sole `QQuickWindow`;
- no separately presented visualizer surface;
- no `QQuickWidget`;
- no independent swap/vsync owner;
- no self-driven visualizer repaint loop.

The historical `SpotifyBarsGLOverlay` name may temporarily survive as state/resource code while
migration occurs. It is not a presentation-surface contract.

## 5. Logical / presentation split

Logical worker owns plain-data evolution.

Presentation side owns:

- current scene state;
- presentation geometry;
- card/pixel representation;
- fade/reveal;
- GPU resource use;
- physical presentation.

The worker does not mutate Quick items or GPU resources.

## 6. Latest-state semantics

One slot/latest wins.

No FIFO, catch-up, or paint acknowledgement.

Every authored event integrates before later state may supersede it.

## 7. Presentation geometry

One authoritative display-local geometry snapshot must feed all visual parts that need alignment:

- card;
- shader/render item;
- viewport/scissor equivalent;
- DPR;
- mask/border;
- CUSTOM geometry.

Do not create separate QWidget and Quick pixel geometry authorities.

## 8. Card

Card visual fidelity must be preserved.

Implementation may reuse existing raster output initially or migrate the card to retained Quick
primitives, but steady presentation must not rebuild expensive stable pixels every visualizer frame.

Choose based on parity and measured cost.

## 9. Bubble / BTF

`Docs/Guardrails/Bubble_Temporal_Fidelity.md` is binding.

Bubble is a canary for shared timing and must not receive mode-specific cadence hacks to hide
presentation defects.

## 10. Playback

Pause/Play preserves:

- logical runtime identity;
- mode identity;
- source/capture policy;
- no visualizer pause debounce;
- prompt visible authored state change.

The migration must not turn normal Pause/Play into renderer/window recreation.

## 11. CUSTOM / Edit

CUSTOM/Edit must preserve one authoritative committed geometry.

Control UI may remain QWidget if appropriate.

Live runtime pixels belong to the Quick scene after migration; edit plumbing must not recreate a
second accelerated presentation surface.

## 12. Validation

Use:

- deterministic authored-behaviour goldens;
- logical scheduler tests;
- BTF;
- source freshness tests;
- real renderer/output tests where visibility matters;
- Quick runtime-shaped presentation checks;
- lifecycle generation tests;
- installed manual review.

A test name does not prove it exercises the real output path.
