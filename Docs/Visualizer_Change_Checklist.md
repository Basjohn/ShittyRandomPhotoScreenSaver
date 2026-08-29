# Visualizer Change Checklist

Last updated: 2026-08-28

Use this before changing visualizer runtime, geometry, rendering, CUSTOM behavior or presentation.

## 1. Read first

- `Docs/QtQuick_Migration/03_Visualizer.md`
- `Docs/Guardrails/Visualizer_Presentation.md`
- `Docs/Guardrails/Bubble_Temporal_Fidelity.md`
- `Docs/Visualizer_Reference.md`
- `Current_Plan.md`

If source contradicts these durable destination contracts, determine whether source is missing implementation before
weakening the contract.

## 2. One authored clock

`VisualizerLogicalRuntime` remains sole mode-general authored cadence. No QML/render-thread/per-mode replacement clock,
paint acknowledgement, catch-up queue or display-rate divisor.

## 3. One presentation surface

Visualizer content stays inside the owning display's single retained `QQuickWindow`/scene. No separate native overlay,
`QQuickWidget`, second accelerated surface or old-presenter fallback.

## 4. Immutable/latest render boundary

Render-thread state is detached, generation/activation fenced and latest-state oriented. Do not pass live
`SpotifyVisualizerWidget`, provider, SettingsManager or mutable heavy arrays to the render thread.

## 4A. Consumer-driven configuration ownership

- [ ] For every changed setting, identify its actual consumer.
- [ ] Anything read by authored logical evolution or a mode-owned Spectrum/Oscilloscope/Sine/Bubble/DevCurve frame runtime is
      available without `SpotifyVisualizerWidget`.
- [ ] Pure renderer/style/chrome values remain presentation-owned.
- [ ] A resolved "technical" value is routed by actual consumer rather than treated as one monolithic technical bucket:
      BeatEngine/audio-worker input -> the one shared engine boundary; authored-logical input -> controller-owned logical state.
- [ ] Bar-count changes keep controller authority, shared-engine reconfiguration/generation and logical bar-mirror freshness
      coherent.
- [ ] Legacy overlay-only technical mirrors were not recreated without an exact retained consumer.
- [ ] No broad copy of legacy widget attributes into `VisualizerRuntimeController` was used to hide missing ownership.

## 4B. Quick snapshot publication

- [ ] One GUI/Quick synchronization owner consumes the freshest logical publication.
- [ ] Runtime generation, engine generation, activation and mode identity are fenced before publication.
- [ ] Current presentation geometry/policy/fade/style is resolved into `ResolvedVisualizerPresentation`.
- [ ] A complete `VisualizerRenderSnapshot` is published into the existing bridge and reaches the retained Quick consumer.
- [ ] The same resolved presentation record used for snapshot composition is committed to the retained item at synchronization;
      presentation is not independently re-resolved into conflicting geometry/policy.
- [ ] A direct test call to `bridge.take_for_render()` is not treated as retained-consumer proof; the real retained
      item/render-node synchronization path admits the exact snapshot identity.
- [ ] Bridge binding alone is never treated as proof.
- [ ] No second timer/cadence, FIFO, catch-up, paint acknowledgement or legacy `present_tick()` call was introduced.

## 5. Shell / clip

Current modes are CARD + CARD_INTERIOR. Custom GL stays above card fill, below border and inside the rounded inner path.
Use the selected render-node-local SDF/stencil host; do not revive the failed QSGClipNode handoff or shrink authored
content geometry to hide bleed.

## 6. Geometry authority

One presentation-neutral geometry record feeds retained shell, clip, render node, DPR and CUSTOM.

Keep distinct:

```text
baseline aspect / reference extent
uniform_visual_scale
viewport_extent
```

The 420x280 value is a reference coordinate extent, not a required visible size. Default/baseline aspect is 1.5.

## 7. Required CUSTOM resize semantics

```text
scroll wheel   -> uniform scale; extent unchanged
corner handles -> uniform scale; extent unchanged
left/right     -> viewport width; scale unchanged
top/bottom     -> viewport height; scale unchanged
```

Viewport expansion changes available world/layout and current aspect; it never stretches final pixels independently on
X/Y.

**All five current modes must support viewport resizing, including Bubble.** The all-five-mode capability policy is landed;
do not reintroduce a false Bubble gate to mask a resize/reflow bug.

For viewport changes also verify ownership precedence: ordinary committed extent remains truth outside CUSTOM, the working
CUSTOM extent overrides only while editing, Save preserves the new committed extent, and Cancel restores the pre-edit
committed extent. Inactive CUSTOM is not an implicit reset to canonical.

Expected adaptation:

- Spectrum redistributes/reflows bars;
- Oscilloscope/Sine/DevCurve adapt domains while stroke scale stays coherent;
- Bubble changes spatial bounds while circles stay circles and velocity/radius/collision/BTF semantics remain coherent.

Persist and restore uniform scale and viewport extent separately through Save/Cancel, geometry variants and layout slots.

## 8. Bubble

BTF is binding. Geometry changes are configuration, never another clock. Do not retune Bubble simulation to hide
presentation or resize defects. Preserve continuous positional evolution, collisions, trails, ghosts/pop/transients,
protected renderer-visible consequences and source freshness.

## 9. Fade / readiness

One authored fade progress may derive scene/content layer values; it must not create a second fade clock. Keep
`presentation_ready` distinct from `reactive_source_ready`; paused Spectrum may reveal idle presentation without a fake
source identity.

## 9A. Product display admission / semantic input

- [ ] Exactly one visualizer owner is admitted across participating displays for the current product instance.
- [ ] Requested-monitor/fallback and committed/CUSTOM geometry semantics are preserved.
- [ ] Non-owning displays do not construct duplicate controller/source/logical runtime ownership.
- [ ] Retained visualizer double-click cycles mode before display-level next-image fallback.

## 9B. Retirement barrier

- [ ] Visualizer publication closes before display teardown.
- [ ] Sole authored logical runtime stop/join succeeds before owner/display retirement is reported complete.
- [ ] A deliberately failed join leaves the generation unresolved and blocks terminal teardown.
- [ ] Retry/success path is idempotent and does not duplicate owners.

## 10. Playback / lifecycle

Pause/Play preserves runtime identity and warm-source semantics. Generation zero is valid. Stale snapshots are rejected.
GPU resources retire on the legal render owner.

## 11. Required proof for geometry changes

- all five modes from canonical settings/preset resolution through technical-engine/logical/presentation ownership,
  logical publication and complete retained Quick snapshot consumption;
- baseline + wide + tall extents;
- no anisotropic final-pixel stretch;
- separate scale/extent round-trip;
- retained item/model/render identity where required;
- CUSTOM Save/Cancel and layout-slot replay;
- cross-display/DPR projection;
- Bubble deterministic/BTF + eyes-on evidence when spatial behavior changes.
