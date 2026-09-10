# Historical Bug — Experimental Visualizer mode key-family contract escaped shared consumers

## Symptom

The dormant/experimental `sphere` mode was changed to stop owning several shared persisted key families. Partial fixes updated one consumer at a time, but other generic consumers still manufactured `{mode}_...` keys independently. This produced successive hard failures when Sphere crossed deeper seams:

- canonical-default normalization required retired `sphere_rainbow_*` keys;
- Settings enable/save still requested retired `sphere_rainbow_*` keys;
- Settings mode selection still requested nonexistent `sphere_bar_*` keys;
- Quick runtime owner construction still requested nonexistent `sphere_bar_*` keys.

The failures were authority errors, not missing-default values to be papered over.

## Root cause

Per-mode persisted key syntax/ownership was duplicated across Settings UI, migration/normalization and runtime presentation initialization. Adding descriptor capability metadata did not automatically migrate those consumers, so a mode could correctly declare that it did not own a key family while another shared consumer still assumed that every mode did.

## Durable repair

- Canonical defaults/schema/SettingsManager remain the sole persisted-value authority.
- The visualizer mode registry now owns only **routing/capability metadata** for shared setting families; it does not provide values.
- Shared consumers resolve owned or inherited family keys through the canonical mode-setting-family helpers instead of independently manufacturing `{mode}_...` persisted keys.
- Sphere owns neither Rainbow nor shared bar-appearance persisted keys. Its internal non-persisted shared-bar mirrors explicitly resolve through the canonical Spectrum shared-bar profile.
- Descriptor participation is tested against canonical default-key ownership.
- A source guard rejects new dynamic shared-consumer `{mode}_bar_*` / `{mode}_rainbow_*` key construction outside the bounded canonical model/helper seams.
- Runtime presentation-default coverage exercises Sphere owner initialization so Settings-only tests cannot hide a runtime-only contract break.

## Guardrail

Experimental removability must never create a second Settings authority or a call-site fallback. If an experiment opts out of a generic persisted key family, every shared consumer must go through the canonical family ownership/profile seam. Missing canonical values remain fatal authority errors.
