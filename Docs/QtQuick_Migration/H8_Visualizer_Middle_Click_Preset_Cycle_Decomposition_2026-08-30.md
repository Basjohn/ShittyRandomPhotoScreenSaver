# H8 — Visualizer Middle-Click Preset Hotswap Decomposition — 2026-08-30

Status: **IMPLEMENTED / DETERMINISTIC GREEN. Physical H acceptance pending.**

Sequence authority remains `Current_Plan.md`. This file owns only the bounded H8 technical route.

## 1. Why this is H

The live product previously supported a separate visualizer gesture: **middle-click hotswapped to the next preset while staying in the current visualizer mode**. This is deterministic missing functionality, not visual polish.

Historical evidence is unusually strong:

- `Docs/Historical_Bugs/R-12_Runtime_Custom_Preset_Cycling.md` names the runtime `WidgetManager.cycle_visualizer_preset` path and makes the Custom snapshot/restore behavior a permanent contract.
- `Docs/Historical_Bugs/U-10_Oscilloscope_Strobe_Waveform_Ghost_Contract.md` records successful runtime validation during **middle-click preset cycling** and the sibling fix that narrowed persistence to `widgets.spotify_visualizer` so Media metadata was not erased.
- `Docs/Historical_Bugs/A-04_MC_Keyboard_Focus_Ctrl_Halo_Archive.md` records display-root mouse forwarding as load-bearing for preset cycling.

The Quick migration contracts retained visualizer **double-click = cycle mode** but originally omitted the separate middle-click preset gesture. H8 restores that interaction through the retained destination owners; this specific feature was a migration-contract omission. Do not generalize that finding to every post-cutover defect without evidence.

Historical QWidget/`WidgetManager` code is an outcome oracle only. It must not return to production architecture.

## 2. Binding product contract

```text
middle-click inside active retained visualizer
-> consume the visualizer semantic hit
-> advance exactly one preset in the current mode
-> wrap after the final slot
-> current mode remains unchanged
-> no next-image action
-> no screensaver exit
-> no context-menu action
```

Do not invent reverse-cycling or another gesture without a separately proven product contract.

### Custom is not an ordinary preset

`Custom` is a user-owned snapshot. Runtime cycling must preserve the same rule as Settings:

```text
leave Custom
-> snapshot exact normalized current Custom payload

return to Custom
-> restore that snapshot exactly
```

Curated preset application uses **replace semantics** for the mode payload so stale fields from the prior preset cannot leak into the target.

## 3. Landed source seam

The landed route is bounded:

```text
Quick window mouse press
-> QuickDisplayWindow middle-button semantic hit
-> QuickSceneController retained Visualizer admission
-> QuickVisualizerMiddleClickAdmission

QuickDisplayVisualizerOwner.request_mode_change()
-> intentionally rejects target == current mode

QuickDisplayVisualizerOwner.request_preset_change()
-> requires target == current mode
-> drops requests while another activation is active
```

The generic runtime input owner remains presentation-neutral. Preset hotswap is not disguised as a mode switch.

## 4. Destination route

Use the accepted owners:

```text
Quick window middle-button press
-> retained visualizer region hit admission
-> DisplayManager semantic preset-cycle authority
-> existing visualizer preset helpers resolve a detached target mapping
-> same-mode retained visualizer activation transaction
-> existing controller + one BeatEngine + one logical runtime + one retained presentation
-> fresh target snapshot admitted
-> atomically persist visualizer child + canonical Custom cache
```

QML/Quick may identify the retained hit region. Python remains semantic/settings/activation authority. Do not add a second global mouse router.

A middle click outside the active visualizer does **not** become a generic image-advance or exit gesture. Existing unrelated input semantics remain unchanged.

## 5. Preset resolution and persistence

Reuse the canonical helpers rather than reimplementing preset semantics:

```text
get_preset_count
resolve_preset_index_from_mapping
get_custom_preset_index
build_normalized_custom_snapshot
apply_preset_to_config
restore_visualizer_snapshot
VISUALIZER_CUSTOM_STORAGE_KEY
```

Required write scope:

```text
settings mutation/persistence
-> widgets.spotify_visualizer child
-> visualizer_custom_presets root
```

The Custom cache is a required companion authority, not a broad widget refresh. Do not emit or refresh the whole `widgets` mapping. `SettingsManager.replace_visualizer_runtime_preset_state()` preserves every widget sibling and submits both visualizer mappings together; historical U-10 evidence already shows why a broad live refresh is unsafe for Media metadata.

Schema v4 made `visualizer_custom_presets` a structured JSON/SST root and migrated the shipped flat `bubble.<key>` form to `cache["bubble"][key]`. Schema v5 closes the later route-ownership regression: a Custom snapshot is strictly the active mode-owned payload and cannot carry `enabled`, `visualizers_enabled`, `position`, `monitor`, or outer CUSTOM geometry. Existing leaked cache fields are stripped on migration and again at restore, so preset cycling cannot reroute the widget and make recreation hydrate another display's geometry bucket. Valid nested snapshots win over flat duplicate material. If a mode has no snapshot yet, H8 seeds it from that mode's persisted raw section before the first curated replacement; malformed cache roots fail loudly before activation.

If persistence is deferred/coalesced, it must remain non-blocking and generation-safe. The visible activation must not be declared successful merely because a settings write was queued.

## 6. Same-mode activation transaction

The cross-mode `request_mode_change()` still rejects same-mode targets. H8's distinct `request_preset_change(...)` shares the already-fenced hidden activation transaction with an explicit preset reason and never calls `set_mode()`.

The transaction must preserve:

- exactly one product-level visualizer owner;
- one controller and shared BeatEngine/source authority;
- at most one authored logical runtime;
- one display frame pacer/presentation opportunity;
- stop/join fencing before replacing authored logical state where the canonical owner requires it;
- one target activation/generation boundary, not duplicate reconfiguration passes;
- stale old-preset frame rejection and fresh-target admission;
- existing retained fade/reveal semantics;
- Bubble Temporal Fidelity and unrelated mode behavior.

A preset request while another visualizer transition/activation is active is consumed at the semantic hit and dropped by the owner. It cannot create an overlapping activation.

## 7. Deterministic evidence

The focused H8 route passes `122/122` across the new resolver/admission bars plus affected Quick, Settings, transfer and SST suites. The maintained `h-destination` profile passes `84/84`. Together they prove:

1. middle click inside the active retained visualizer is consumed and advances **one** preset;
2. middle click outside the visualizer does nothing to preset/image/exit state;
3. current visualizer mode is unchanged;
4. last preset wraps to first;
5. `Custom -> curated -> ... -> Custom` restores a semantically equivalent normalized Custom snapshot;
6. curated target uses replace semantics and does not inherit stale prior-preset keys;
7. only the visualizer child and canonical Custom cache are mutated/persisted; Media metadata/config remains untouched;
8. exactly one same-mode activation transaction occurs and no second owner/logical runtime/pacer is created;
9. a request during active transition cannot overlap another activation, and a replaced or retired owner cannot persist a stale completion;
10. selected preset/cache survives structured JSON/SST restart/reload; physical Settings and CUSTOM recreation remain below;
11. all five active visualizer modes can cycle their own preset table;
12. the global visualizer double-click mode-cycle contract remains unchanged.
13. preset/Custom round-trips preserve live widget admission and display route; schema v5 removes shipped `monitor` leakage from cached mode payloads.

Do not restore tests whose only purpose is the deleted QWidget presenter. Test current semantic and retained Quick owners.

## 8. Physical acceptance

After H5b has restored Spectrum's functional path, perform an eyes-on gate across at least two modes and include Spectrum before final H closure:

```text
start one mode
-> middle-click repeatedly through several presets
-> mode stays fixed; visible preset changes once per click
-> enter/leave/return to Custom and verify authored Custom state survives
-> recreate with Settings
-> recreate with CUSTOM Save/Continue
-> restart/reload
```

Require no image advance, unexpected exit, context action, duplicate visualizer owner/runtime, or unexplained `screensaver_qml.log` diagnostics.

## 9. Explicit anti-fixes

Do not:

- resurrect historical `rendering/widget_manager.py`, `DisplayWidget`, QRhiWidget/GLCompositor presentation or any compatibility presenter;
- rebuild/recreate the display merely to change a preset;
- route runtime hotswap through Settings UI widgets;
- perform a whole-`widgets` live refresh;
- call the cross-mode API with the current mode and weaken its guard just to make the request fit;
- create another BeatEngine/source/logical runtime/pacer/presentation owner;
- add polling, arbitrary sleeps or a timer-based input detector;
- retune Bubble/shared cadence to mask activation defects.

## 10. Close condition

Deterministic implementation is complete. H8 closes only after the physical runtime gate proves visible one-step current-mode hotswap, Custom round-trip and Settings/CUSTOM/restart recreation while logs remain clean. Double-click mode cycling and unrelated input behavior are already deterministic GREEN.
