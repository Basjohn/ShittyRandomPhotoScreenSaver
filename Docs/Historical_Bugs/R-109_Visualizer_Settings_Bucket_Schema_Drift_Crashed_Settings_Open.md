# R-109 | Visualizer Settings bucket schema drift crashed Settings open

**Status:** SOLVED / PHYSICALLY ACCEPTED 2026-10-08

## Trigger

After the C6 3D Settings visual-authoring pass, opening Settings from a running screensaver stopped the runtime cleanly and then failed before the Settings dialog appeared. The 2026-10-07 operator log captured:

`KeyError: 'bubble:bar_appearance'`

from `VisualizerSettingsContextMixin.get_visualizer_bucket_state()` while `VisualizersTab` was constructing its stable Custom accessories.

## Root cause

Two related schema/ownership mistakes were introduced in the Settings authoring pass.

First, the stable `Bar Appearance` and `Rainbow` accessory widgets are created before any lazy Visualizer mode body exists. Their constructor used the currently persisted Visualizer mode to fetch persisted bucket state. That is invalid because the active mode may not own the accessory at all. Bubble does not own the `bar_appearance` bucket, while Sphere / Extruded / Shockwave do not own the shared Rainbow bucket. A parked hidden accessory therefore tried to resolve a bucket identity that was intentionally absent from canonical UI state.

Second, C6 renamed and split the Extruded Spectrum and Shockwave Grid buckets in their builders without updating the canonical `ui.visualizer_bucket_states` identity map. The builders now author Extruded `Appearance`, `Material`, `Reflection`, `Shadow`, `Render`, etc. and Shockwave `Appearance` / `Render`, while canonical state still contained retired `extruded_spectrum:finish` and `shockwave_grid:look` identities. Fixing only the first crash would therefore have exposed additional KeyErrors when those lazy pages were selected.

## Repair

Dynamic stable accessories now bootstrap closed while parked and hidden. They do **not** query the current mode's persisted bucket map during shell construction. `_place_custom_accessories()` remains the sole point that attaches an accessory to a compatible mode body and applies that mode's canonical persisted bucket state.

The canonical `visualizer_bucket_states` map is synchronized to the actual C6 builder identities, including `extruded_spectrum:bar_appearance`. Retired C6 bucket names are removed from the canonical schema rather than retained as shims. Existing sparse persisted maps are normalized against the current canonical key set, so stale old identities simply stop participating.

## Permanent regressions

`tests/test_visualizer_settings_lazy_bodies_current.py` now constructs the Settings Visualizers shell once for **every persisted active Visualizer mode** before any lazy body is selected. This reproduces the original Bubble crash and also covers active modes that do not own shared Rainbow.

`tests/test_visualizer_settings_body_transaction_contract.py` now guards both sides of the contract: dynamic accessories must use inert bootstrap state, and the exact current Extruded/Shockwave bucket identities must match canonical defaults. The pre-existing static builder-schema test continues to assert that every literal lazy-builder bucket exists canonically.

Physical Windows acceptance passed on 2026-10-08: Settings opened from RUN, the 3D authoring pass was accepted, and the grouped tranche completed 578 tests. The later startup/reinit freeze was a separate Q2 presentation-cadence regression and is recorded as R-110.

## Lesson

A lazy Settings body can be dormant while its stable accessory chrome is already alive. Never infer that the currently selected product mode owns a parked accessory merely because the accessory's persistence will eventually follow an active mode. Bootstrap state and attached-mode persisted state are separate lifecycle phases, and canonical bucket identity changes must land atomically with their builders.
