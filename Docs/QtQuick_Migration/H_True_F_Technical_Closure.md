# H — True F Closure: Technical Configuration + Retained Consumer

Status: **CLOSED correction evidence — permanent regression lessons promoted to current contracts**  
Status authority remains `Current_Plan.md`. This note records the bounded post-GREEN correction discovered by audit of
`45b7c8f8`; it is not a standing prerequisite to rerun before every H slice.

The durable ownership rules are now also carried by `Docs/Contracts.md`, `Docs/Guardrails/Visualizer_Presentation.md`,
`Docs/Visualizer_Reference.md`, `Docs/Visualizer_Change_Checklist.md` and `03_Visualizer.md`. Keep this file as the compact
reason those rules exist.

## What stays accepted

Do **not** reopen Findings A–E, the controller-owned logical-state extraction, `VisualizerPresentationState`, the hard join barrier, single-display admission, or semantic double-click work merely because F was overstated.

The remaining problem is narrower: the prior F test stopped at the bridge and hand-fed resolved logical/presentation dictionaries. It did not exercise the widget-coupled technical engine apply path.

## Exact remaining ownership split

The canonical `SpotifyVisualizerSettings` technical resolver is already presentation-neutral enough: `build_technical_cache()` does not use its historical `widget` argument. Keep that resolver.

The destination apply must classify the resolved technical cache by **actual consumer**:

```text
BeatEngine / audio-worker technical inputs
    bar_count
    dynamic_floor / manual_floor
    adaptive_sensitivity / sensitivity
    audio_block_size
    dynamic_range_enabled -> energy boost
    agc_strength
    input_gain
    kick_lane_gain
    spectrum_lane_transient_mix

-> apply through the single controller-owned shared BeatEngine.

Authored-logical inputs that happen to originate in the technical section
    transient_pulse_gain
    transient_clamp
    bubble_transient_mix_bass / vocal
    sine_wave_transient_width_mix
    oscilloscope_transient_width_mix

-> controller-owned VisualizerLogicalTickState.

Legacy-only overlay mirroring
    parent._spotify_bars_overlay transient mirrors

-> no Quick successor; delete with the legacy presenter unless exact destination
   source proves a retained consumer needs the value.
```

Needing the BeatEngine is **not** a reason to keep a QWidget: `VisualizerRuntimeController` already owns the shared engine, and the BeatEngine already has neutral setters for bar-count reconfiguration, floor, sensitivity, energy boost, AGC and input gain. Add small engine forwarding methods only where the worker currently has the sole setter (for example audio block size) rather than reaching through a widget.

Bar-count changes must update the controller's `bar_count`, the shared engine generation via its existing reconfiguration contract, and the controller-owned logical display-bar mirror/freshness state. They must not recreate legacy QWidget geometry/GPU caches.

## Retained presentation boundary

`QuickVisualizerPresentationSync` already resolves the complete immutable presentation before publishing the snapshot. The **same resolved record** must be committed to the retained `VisualizerRenderItem` when publication succeeds, then the item is dirtied/requested.

Do not resolve presentation twice if that can produce different geometry. Prefer passing the already-resolved `ResolvedVisualizerPresentation` into the request-present callback.

The deterministic proof is:

```text
logical publication
-> QuickVisualizerPresentationSync resolves P
-> compose/publish snapshot(logical, P)
-> retained scene commits P to VisualizerRenderItem
-> VisualizerRenderItem.updatePaintNode()
-> bridge take for exact identity
-> VisualizerRenderNode.snapshot is admitted
```

## Closure bar that admitted DisplayManager conversion

The bounded closure required:

1. canonical settings/model resolves a technical cache without QWidget;
2. Quick owner/controller applies that cache to the one shared BeatEngine;
3. technical values consumed by authored logical evolution live on controller-owned logical state;
4. bar-count technical changes leave controller, engine and logical mirror coherent;
5. the retained Quick item, not a test calling `bridge.take_for_render()` directly, consumes the published snapshot;
6. the existing all-five visual/config/golden/cadence bars remain GREEN.

No new visualizer subsystem, settings authority, timer, bridge, compatibility facade or legacy overlay mirror is required.

This closure is now a permanent regression boundary. Future failures should reopen only the smallest demonstrated owner
(engine technical apply, authored-logical state, retained synchronization/consumer, bar-count coherence, etc.), not the whole
pre-cutover audit.

## Cutover checkpointing clarification

"Atomic cutover" means the **finished destination has one presenter/authority topology**. It does not require one uninterrupted coding session or one giant commit. The migration application is intentionally non-runnable before the flip. DisplayManager/engine caller conversion may be checkpointed across as many commits/sessions as needed, provided those checkpoints do not invent a dual-authority production architecture or a fake DisplayWidget compatibility facade.
