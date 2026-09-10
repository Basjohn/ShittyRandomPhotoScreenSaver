# SRPSS Voxel Sphere — Accepted Experimental Polish Handoff — 2026-09-10

## Where we are

Source provenance remains `c45845d44d21537ca4c09be41f6decf4cde0d16a` plus the supplied 2026-09-10 granular-cohort handoff. Sphere is **accepted experimental and isolated**. Acceptance does not authorize migration. All experimental modes stay on the reusable lazy/removable experimental-host boundary until the operator explicitly requests migration.

The accepted Sphere behaviour remains golden: fragmentation, granular intake/outtake cohort motion, stable four-corner population identity, sustained body growth, event-stepped tracer, continuous rotation and vocal-linked intake recoil may not be reduced or retuned by presentation/UI work.

This checkpoint now includes:

- former Presets 5/6 consolidated into **Glass Current** (Preset 1 / intake) and **Voxel Bloom** (Preset 2 / outtake);
- shared themed circular checkboxes, collapsible buckets and recommended slider markers in the Sphere Custom builder;
- complete retirement of Rainbow Ghosting and the dead Block Relief, Bass/Mid/High Response, Energy Curve and Idle Drift settings;
- exact schema-v8 migration of the old `Deformation × Block Reactivity` result into one **Fragment Strength** authority, with the former Deformation value independently preserved as **Particle Distance**;
- **Particle Amount** as a post-admission stable-population multiplier (`1.0` preserves accepted behaviour), plus the UI rename **Particle Density Response**;
- Vocal Response range trimmed to its existing effective ceiling (`1.35`) and Size Response to the existing growth saturation (`2.54`), with equivalent curated-preset values;
- Sphere-local **Taste The Rainbow** with independent **Surfaces** and **Edges** sub-controls. It uses one moving partial-spectrum field in the existing voxel draw, preserves Fill/Edge alpha, adds no timer/poller/worker/history pass and does not join the shared Rainbow family (`rainbow_controls=False`);
- **Perspective Strength** as a Sphere-local `0..1` control where `1.0` is the accepted current projection exactly and lower values only flatten toward orthographic; both curated presets remain at `1.0`, so the accepted camera/overflow envelope is unchanged;
- schema-v8 migration of the persisted live Sphere section **and** cached Custom Sphere payloads, so older Custom state cannot restore retired Deformation/Block Reactivity keys later;
- the reusable experimental-host seam documented as architecture without generalizing Sphere internals.

## What I’m looking for

Physical operator validation should concentrate on whether Glass Current and Voxel Bloom still feel identical in reactivity/motion after the control split, whether Particle Amount changes only population, and whether Taste The Rainbow behaves as intended:

- Surfaces only: moving partial-spectrum gradient on voxel faces while authored Edge RGB remains literal;
- Edges only: the same gradient on edges while Fill RGB remains literal;
- both: one coherent colour field across both surfaces and edges, with only a portion of the spectrum visible across the sphere at any instant;
- master off: accepted literal Fill/Edge path with no optional rainbow work beyond the uniform-gated branch.

The following presentation candidates remain **unimplemented pending operator decision**: Edge Weight, Voxel Size Variation, Shadow Opacity/Softness/Distance, Tracer Colour and Depth Cue. They are discussed with the operator in-session rather than maintained as a separate proposal specification.

## What I need to fix / validate next

Focused Sphere/geometry/technical-profile, user-authored preset catalogue, failed-body transaction and persisted-bucket schema tests pass **82/82**. Canonical JSON/SST defaults, schema-v8 old-state migration, cached Custom migration and curated preset normalization checks pass. Full Python source compile is clean.

`tests/test_settings_persistence.py` and several unrelated packaged tests cannot collect in this Linux workspace because optional target dependencies such as `PySide6` (and for one unrelated RSS test, `feedparser`) are absent. Run the Settings persistence/UI gate on the normal Windows/PySide6 environment before declaring the schema-v8 UI persistence path physically closed.

Before any future permanent migration, capture deterministic pre/post goldens for Glass Current and Voxel Bloom plus the five permanent visualizer modes. Migration fails if it changes Sphere fidelity or permanent-mode reactivity, latency, freshness, bleed/isolation, cadence, lifecycle, CPU/GPU behaviour or dormancy without explicit operator approval.

## Preset ownership correction

Per-visualizer preset files remain **user-authored state**. Users may add arbitrary preset counts, delete down to one surviving preset, and leave sparse authored filename/payload numbers. Runtime slider positions must compact those sparse authored identities without renaming or deleting the backing files. Shipped manifests are packaging/reconciliation metadata only and must never become runtime authority over user presets.

A regression found during this checkpoint was caused by treating authored slot numbers as if they had to be contiguous. The loader now accepts sparse authored identities (for example slots 1, 2 and 5), maps them to compact runtime slider positions, preserves the real source path for Edit Preset, and chooses Save-As numbering from the highest existing authored slot rather than the runtime Custom index.
## 2026-09-10 preset/startup correction

The preset catalogue is user-owned, not package-owned. Authored numbers may be sparse and arbitrary counts are valid. The former contiguous-slot import assertion is forbidden. A second Settings regression was exposed at the same time: failed lazy-body hydration could leave a partial QWidget attached, so repeated attempts visibly duplicated the preset/Advanced scaffold. Body construction is now transactional and failed bodies are removed before the original exception propagates.

The production traceback containing `curated slots are not contiguous` identifies the earlier ControlSeparation artifact, not the corrected sparse-catalog source. Future checkpoint validation must simulate overlay residue (for example retained `preset_5_*.json`) rather than testing only a clean extracted preset directory.


## 2026-09-10 Sphere bucket-state correction

The reorganized Sphere builder introduced `appearance`, `particle_flow`, `reaction`, `rotation` and `effects` persisted bucket identities but the canonical `ui.visualizer_bucket_states` mapping still contained the old `sphere:surface` / `sphere:motion` pair. Selecting Sphere therefore failed immediately with `KeyError: 'sphere:appearance'`.

The canonical defaults now contain the five current Sphere bucket keys and the derived JSON/SST defaults were regenerated. The fail-fast getter remains fail-fast; this was a schema omission, not a reason to add a silent UI fallback. A Qt-free AST contract now scans every visualizer builder's `build_collapsible_bucket(...)` calls and requires matching canonical bucket keys, so a future builder/schema rename mismatch fails before physical Settings testing.
