# R-112 | Extruded historical response used mutable Organs as a frozen oracle

**Status:** TEST / MIGRATION CONTRACT REPAIR IN CODE / WINDOWS GROUPED GATE PENDING

## Trigger

After the Extruded ownership migration, the operator legitimately retuned Spectrum's Organs preset. Two regressions then failed even though current Extruded runtime ownership was independent:

- schema-10 repair expected `extruded_spectrum_lane_transient_mix = 0.9` but produced the current donor value `0.94`;
- curated Extruded ownership tests compared every frozen Extruded response field against the *current* Organs JSON, so an Organs value of `0.7` made an accepted Extruded value of `0.5` look wrong.

The user's local Organs JSON is authored product state and must remain freely tunable.

## Root cause

The migration history had two distinct concepts that were accidentally conflated:

1. old persisted configurations that truly **borrowed a user's selected Spectrum profile** and therefore require a one-time source-to-owner promotion at the persisted-input boundary;
2. the narrow schema-10 generated Extruded bundle and shipped curated Extruded presets, whose accepted historical response had already been frozen into canonical `extruded_spectrum_*` values.

Tests and the schema-10 generated-bundle repair treated today's mutable Organs preset as the oracle for case 2. That made future Organs authoring capable of rewriting history.

## Repair

The narrow schema-10 generated-profile repair now fills every missing newly-owned Extruded response key from Extruded's own canonical frozen defaults. It never consults current Organs. Existing explicit Extruded values, including genuine user edits, remain authoritative.

Curated Extruded regression coverage likewise compares against the canonical Extruded-owned baseline and explicitly poisons Spectrum values to prove no runtime/test borrowing remains.

The general legacy profile-lender migration is **not removed**. Old compatible persisted inputs that genuinely lack owned keys still receive their one-time promoted copy from the user's selected source profile, then become mode-local. This preserves the intended historical input migration without turning mutable donor state into a permanent test oracle.

## Permanent regression

- schema-10 generated Extruded repair must restore canonical Extruded-owned values such as 35 bars, 128-sample blocks and lane transient mix 0.9 while preserving unrelated explicit user edits;
- every shipped Extruded curated preset must own its complete response in `extruded_spectrum_*` keys;
- poisoning current Spectrum/Organs values must not change an applied Extruded curated preset;
- generic profile-lender migration tests continue to prove one-time promotion for genuinely old missing-owner inputs.

The operator's locally modified `presets/visualizer_modes/spectrum/preset_1_organs.json` is intentionally excluded from the Godzip carrying this repair so archive application cannot overwrite that local authoring.
