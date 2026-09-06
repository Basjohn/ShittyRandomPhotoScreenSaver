# Historical Bug — Theme defaults split authority

Date closed: 2026-09-06

## Symptom

Defaults Foundry exposed `widget_theme.selected_id`, `widget_theme.keep_synced`, and `widget_theme.custom`, but no Settings GUI theme-selection default. The runtime nevertheless had a persisted Settings-theme key (`ui.settings_theme_selection`) and silently supplied `builtin:default-dark` when that key was absent.

Widget Theme had the same architectural smell in a subtler form: its canonical root existed, but the missing-state reader independently supplied `default_dark` / `True` / `None` rather than reading the canonical defaults.

The result was two possible fresh-install authorities. Editing theme defaults in Defaults Foundry could diverge from what a missing persisted theme state actually resolved to.

## Cause

Theme-selection fallback literals lived in the UI selection readers instead of treating `core/settings/default_settings.py` as the fresh-install/reset authority. `ui.settings_theme_selection` was also absent from the canonical defaults literal and derived defaults snapshot.

The compiled Default Dark Settings theme is a valid **runtime availability fallback**; it must not also act as a second product-default source.

## Repair

- Added `ui.settings_theme_selection` to canonical Normal defaults and `core/settings/defaults_snapshot.json`.
- Missing Settings-theme selection now asks the canonical defaults literal for its default identity.
- Missing or partially persisted Widget Theme state now takes `selected_id`, `keep_synced`, and `custom` defaults from the canonical `widget_theme` root.
- Malformed/unavailable persisted theme identities still resolve through the existing compiled Default Dark safety path; that availability fallback is separate from default selection ownership.

## Invariant

**Defaults Foundry / `core/settings/default_settings.py` is the sole fresh-install/reset authority for theme selection and theme-link defaults.**

Do not add a new hard-coded default for any of these fields in a runtime reader:

- `ui.settings_theme_selection`
- `widget_theme.selected_id`
- `widget_theme.keep_synced`
- `widget_theme.custom`

Runtime fallbacks may protect against malformed or unavailable assets, but they must not decide what a missing setting is supposed to default to.

## Regression coverage

`tests/test_theme_defaults_authority.py` checks that:

- Settings-theme selection exists in canonical defaults and the derived snapshot;
- the Settings-theme missing-value reader consults canonical defaults;
- the Widget-theme missing/partial-state reader consults canonical defaults for all three persisted fields.
