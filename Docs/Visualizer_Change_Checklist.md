# Visualizer Change Checklist

Last updated: 2026-09-03

Use this before changing visualizer runtime, geometry, rendering, CUSTOM behavior or presentation.

## 1. Read first

- `Docs/QtQuick_Migration/03_Visualizer.md`
- `Docs/Guardrails/Visualizer_Presentation.md`
- `Docs/Guardrails/Bubble_Temporal_Fidelity.md`
- `Docs/Visualizer_Reference.md`
- `Docs/QtQuick_Migration/H5c_Visualizer_Reactivity_Parity_Audit_Decomposition_2026-08-31.md`
- `Docs/QtQuick_Migration/Visualizer_Reactivity_Historical_Current_Evidence_Matrix_2026-08-31.md`
- `Current_Plan.md`
- `Docs/QtQuick_Migration/Visualizer_Mode_Modularization_And_Settings_Tab_Decomposition_2026-09-02.md` when changing mode registration/enablement/Settings composition
- `Docs/QtQuick_Migration/Visualizer_Hitch_Attribution_And_Optimization_Plan_2026-09-03.md` for any hitch/cadence/tail optimization

If source contradicts these durable destination contracts, determine whether source is missing implementation before weakening the contract.

## 1A. Mode modularization / enable-disable preflight

When changing mode registry, mode enablement, mode cycling or the planned Visualizers Settings tab:

- [ ] Treat **all registered canonical modes** and **currently enabled modes** as different sets. Schema/default/preset migration may need all registered modes; runtime selection/cycling/render imports/Settings pills use enabled modes only.
- [ ] If the Visualizer family is ON, at least one mode remains enabled, but any mode may be the sole enabled mode. Zero enabled modes is not a second family-disable mechanism.
- [ ] Disabling a mode preserves its settings/presets/Custom state and prevents renderer/frame-runtime/Settings-body construction.
- [ ] Disabling the currently selected mode transactionally selects another enabled mode before retirement; stale persisted requests resolve deterministically and log substitution rather than silently re-enabling the disabled mode.
- [ ] No activation polling, per-mode timer, worker, thread, new analysis lane or second authored clock was introduced.
- [ ] Common registry imports remain light; disabled heavy implementation modules are fresh-process dormant.
- [ ] Existing mode-specific branches that encode real physics/render semantics were not generified merely to make the registry look uniform.
- [ ] The existing preset slider and mode-level `Custom` system are preserved. Do not confuse mode preset Custom with global layout CUSTOM.
- [ ] The global CUSTOM three-entry contract remains untouched: persisted/effective Custom, live Edit Layout start, and number-key saved-layout load all keep authored stacking/Media↔Visualizer adjacency dormant.
- [ ] Media dependency remains one-way admission. If Media is disabled, the planned Visualizers tab may grey out with `Enable Media In Widgets`; it must not auto-enable or own Media.
- [ ] Before/after evidence covers canonical + wide + tall geometry for every affected mode. Registry/UI refactoring is never permission to retune scaling/reactivity.

## 1B. Hitch / delivery optimization preflight

When a visible freeze, jump or flicker is reported:

- [ ] Treat Bubble and extreme-tall Spectrum as sensitive **oracles**, not presumed owners. Do not damp their authored response to hide a global delivery stall.
- [ ] Correlate logical `dt`, source age, analysis handoff, Quick sync/presentation age, frame-pacer skips, GC, usage telemetry, UI callbacks and diagnostics by timestamp before changing smoothing.
- [ ] Separate steady-state periodic hitches from startup/recreation first-frame age.
- [ ] Keep R-76 Spectrum height-aware temporal scaling intact while global delivery is unhealthy; retest renderer quantization/pixel pitch only after deterministic hitches are removed.
- [ ] Keep Bubble R-69/BTF intact; no viewport compensation, radius/motion compression or lower cadence as a hitch workaround.
- [ ] Before deep active-path optimization, complete V0-V4 behavior-floor/authority/dormancy so work from disabled modes cannot pollute the owner graph. V5-V8 Settings extraction/rehosting/dependency/future-mode work may wait.
- [ ] A periodic diagnostics task that correlates with hitches is not exempt because it is "only diagnostics"; redesign it without losing needed observability.
- [ ] A GC hitch is an allocation/lifetime/scheduling problem to attribute, not permission to globally disable GC or accept unbounded retention.

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
- [ ] Historical canonicalization/translation steps were audited when a preset key differs from the current runtime field name (for example Spectrum `spectrum_render_mode` -> continuous/segmented runtime topology).
- [ ] Every key still read by BeatEngine/audio worker, authored tick/frame runtime, or retained Quick renderer has a current configuration route; plausible defaults/fallbacks do not count as proof.
- [ ] Engine-facing per-mode configuration removed from the old mixed applier has a narrow current controller/engine seam rather than silently remaining at defaults.

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

## 4C. Historical reactivity parity audit

For reactivity regressions, compare directly with known-good `3fe5df687387b6b6a121142372c43a7719442386` before tuning.

- [ ] Separate intentional idle energy/motion from real music reactivity; smooth authored idle motion at ~90 Hz is not proof that live source energy arrived.
- [ ] Compare source identity/readiness before changing gain. If `playing && !reactive_source_ready`, determine why current source identity was rejected/delayed.
- [ ] Compare raw engine state -> mode-runtime input -> resolved mode state -> snapshot -> Quick renderer input -> visible output.
- [ ] Preserve historical renderer-side numerical transfers when they are part of visible semantics; keep canonical logical state unmolested.
- [ ] Spectrum changes remain Spectrum-specific unless shared source evidence proves a common cause.
- [ ] Bubble physics/sensitivity are not tuned until source/configuration/publication parity is proven.
- [ ] Sine paused idle must continue through authored state/snapshot/presentation; no QML timer workaround.
- [ ] Play/Pause timing distinguishes historical cold-start shaping from migration-added warm/source/publication/presentation delay.
- [ ] Retired `*_growth` sizing controls stay retired.

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
presentation, configuration-ownership or resize defects. Preserve continuous positional evolution, collisions, trails, ghosts/pop/transients,
protected renderer-visible consequences and source freshness.

- [ ] `bubble_group_drift`, `bubble_collision_pop_mode` and `bubble_big_visual_smoothing` reach controller-owned logical state from resolved settings/presets.
- [ ] Active music magnitude is traced before/after `reactive_source_ready`; intentional idle-energy motion is not mistaken for healthy live response.

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

- [ ] Visible Play/Pause edge can be decomposed Media truth -> owner -> BeatEngine -> first current source -> mode readiness -> logical publication -> Quick snapshot -> retained draw.
- [ ] Historical BeatEngine cold ramp is not changed to hide a new delay; warm resumes are tested separately.
- [ ] Paused Sine continues authored idle evolution and retained publication without another clock.

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
