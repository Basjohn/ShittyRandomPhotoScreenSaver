# Historical Bug — Canonical defaults schema drift and duplicate authority

Date closed: 2026-09-06

## Symptom

Defaults Foundry was reading `core/settings/default_settings.py` as the canonical editable base, but that literal had accumulated several incompatible kinds of state:

- duplicate nested + dotted representations of the same setting under `accessibility`, `workers`, and especially `ui`;
- captured Settings-window/session state (`dialog_geometry`, last tab/scroll state, Visualizer scroll position) that is not a product default;
- engine-managed transition history (`random_choice`, `last_random_choice`, Wipe `last_direction`);
- retired global preset payloads (`preset`, `custom_preset_backup`) that the runtime already discarded;
- real persisted product settings that existed only as reader fallbacks (`cache.*`, `queue.history_size`, and MC `mc.always_on_top`).

There was a more serious ownership defect behind the file pollution: `SettingsManager._set_defaults()` seeded only a hand-maintained subset of canonical sections. As a result, a setting could appear editable in Defaults Foundry yet never be written on a fresh profile. Reset/SST code also carried independent lists of which roots had to remain nested, and those lists omitted `ui` / `widget_theme` in some paths.

## Cause

The settings system evolved from flat QSettings-style dotted keys toward a JSON store with explicitly structured roots, but the defaults/reset/SST paths did not all move to the shared structured-root contract at the same time. Generated/default artifacts and runtime reader fallbacks then became accidental secondary authorities.

The old literal also contained values captured from a live profile. For Accessibility, the duplicate dotted values would win during the old reset flattening path, while a genuinely fresh profile did not seed Accessibility at all and therefore used the UI/model fallback values. There was no single answer to “what is the default?”

## Repair

- `default_settings.py` now contains one representation per canonical setting; the nested/dotted duplicates were removed.
- Accessibility is canonicalized to the pre-repair **fresh-profile behavior**: dimming OFF / 30% and pixel shift OFF / rate 1. This avoids converting a defaults cleanup into silently enabling accessibility effects on new installs.
- `workers` keeps its nested canonical representation only.
- Captured Settings session state was removed from `ui`; authored UI presentation defaults, including Settings theme selection and bucket open/closed defaults, remain canonical.
- Engine-owned transition choice/history fields were removed from defaults.
- Retired `preset` / `custom_preset_backup` payloads were removed from the canonical literal rather than being emitted and immediately discarded.
- Added real missing product defaults: `cache.prefetch_ahead=5`, `cache.max_items=16`, `cache.max_memory_mb=256`, `cache.max_concurrent=2`, and `queue.history_size=50`.
- `mc.always_on_top=true` is canonicalized in the **Screensaver_MC profile override**, not polluted into Normal/Screensaver defaults.
- Fresh-install seeding now walks every canonical section; there is no hand-maintained top-level allow-list.
- Reset, SST-default generation, and `get_flat_defaults()` use `STRUCTURED_SETTINGS_ROOTS` rather than independent special-case lists.
- Existing malformed `ui.*` / `widget_theme.*` persisted shapes are forward-normalized into their structured roots, with already-nested values winning over compatibility dotted members.
- SST import/preview normalizes the same malformed structured-root shape immediately rather than requiring a restart before the imported values are readable.
- `defaults_snapshot.json` remains a derived Normal-profile artifact and no longer invents snapshot-only MC/worker defaults.

## Deliberate non-defaults

A literal settings-read audit was classified after the repair. The remaining apparent “missing defaults” fall into two categories and must **not** be added to `default_settings.py` merely to make a string scan green:

1. runtime/session state such as `ui.dialog_geometry`, `ui.last_tab_*`, `ui.tab_state`, `ui.visualizer_scroll_positions`, `transitions.random_choice`, `transitions.last_random_choice`, and per-transition `last_direction` history;
2. old model/parser aliases such as Media `text_color/background_color/background_opacity` and Weather `animated_icon_*` / `background_*` names. Current Quick/widget runtime uses the canonical `color`, `bg_color`, `bg_opacity`, `icon_alignment`, `show_condition_icon`, etc. These aliases are not new settings and must not be resurrected as duplicate defaults.

## Invariants

1. **One persisted product setting has one canonical path and one canonical value.**
2. **Defaults Foundry / `default_settings.py` is the fresh-install + Reset authority.** Reader fallbacks are defensive only.
3. **Session/history state is not a product default.**
4. **Every declared canonical section is seeded on a fresh profile.** Adding a new section must not require editing a second allow-list.
5. **Every root in `STRUCTURED_SETTINGS_ROOTS` remains nested across store, reset, SST, and derived-default paths.**
6. **Profile-only settings belong in profile overrides.** MC-only settings must not leak into the Normal defaults catalogue.

## Regression coverage

`tests/test_defaults_schema_authority.py` checks duplicate removal, missing product defaults, MC-only ownership, transient/session exclusions, derived snapshot parity, generic fresh-install/reset authority, structured-root ownership, and the forward repair path. `tests/test_theme_defaults_authority.py` separately protects Settings/Widget Theme default authority.
## Deeper sanitization findings

- `JsonSettingsStore.setValue()` previously used `dict.get()` for equality checks, conflating an absent key with an explicitly persisted JSON `null`. Canonical nullable scalars such as `input.widget_glow_color = None` therefore failed fresh-profile seeding. Missing-vs-null is now distinguished by membership before equality.
- The literal Visualizer defaults and the derived normalized snapshot had drifted in *schema*: dead `osc_glow_size`, `sine_glow_size`, and `sine_line1_color` leaves survived only in the literal, while `sphere_rainbow_enabled` / `sphere_rainbow_speed` were synthesized only by normalization. Dead leaves were retired and the real Sphere per-mode Rainbow state was made canonical.
- Curated files under `presets/visualizer_modes/` are **not** defaults debris. They remain authored overlay assets. Defaults/reset normalization uses `apply_preset_overlay=False`; preset activation keeps CLEAR-then-APPLY semantics; Custom activation leaves its stored snapshot unchanged; startup missing-value repair never deep-merges canonical defaults into an existing `visualizer_custom_presets` cache.
- UI collectors/builders are part of the authority audit too: a literal used only when a control is absent can still become a persisted shadow default. These are being removed or replaced by fail-loud/preserve-existing behavior rather than legitimized as new defaults.

- Collapsible Settings UI state is canonical presentation state, but **fresh-profile buckets are collapsed by default**. Gmail/Widget/Visualizer/Advanced/Technical state maps now enumerate their buckets with `False`; persisted user expansion state overlays that baseline normally.
- Capability activation/pool readers previously retained hard-coded `True`/`False` missing-member behavior despite canonical `widgets.family_activation` and `transitions.activation/pool/random_always` maps. Known capabilities now resolve missing members through canonical defaults; only genuinely unknown capability ids retain compatibility admission behavior.
- Display and Transitions Settings pages had defensive parser/save literals (`fill`, `circle`, boolean fallbacks, `3000`, `Ripple`, etc.) that could become a second authority under malformed/partial state. Defensive repair now derives from the active profile's canonical defaults.
- The Phase-C transition parameter resolver claimed canonical fallback ownership while still carrying a second table of local numbers/colours. Its canonical sub-maps now fail loudly when schema is incomplete, and invalid persisted values repair against those canonical values instead of local product-default literals.


## Post-close correction — schema membership vs runtime state (2026-09-07)

The initial sanitization correctly identified many session/history values that did not belong in product defaults, but one verification assumption was too broad: **a runtime consumer needing a value is not proof that the value belongs in persisted Settings schema**. This distinction must remain explicit.

Two concrete failure classes surfaced during reconciliation:

- transient Visualizer DSP snapshot attributes were required by `make_compute_snapshot()` but belonged to `audio_worker` runtime initialization; adding them to canonical defaults would have been the wrong repair;
- stale default-init descriptors requested unprefixed Visualizer appearance fields (`bar_fill_color` / `bar_border_color`) as if they were plain canonical settings even though current ownership projects the real mode-specific values elsewhere. The repair was to remove the false descriptor request, not invent new schema keys.

Therefore the permanent invariant is stronger than “every runtime-resolvable key has a default”:

1. persisted user/product configuration has one canonical Settings/default authority;
2. derived runtime configuration is projected from that authority/environment;
3. transient runtime/DSP/lifecycle state is initialized by its runtime owner;
4. static capability/renderer metadata belongs to registries/descriptors, not persisted Settings;
5. a canonical setting may not be removed until every current consumer/import/persistence path has a legitimate replacement authority in the same change.

`tests/test_settings_defaults_completeness.py` is intentionally scoped to **settings/default-resolvable contracts**. Runtime initialization requires separate owner-specific tests and must never be used to expand schema by reflex.
