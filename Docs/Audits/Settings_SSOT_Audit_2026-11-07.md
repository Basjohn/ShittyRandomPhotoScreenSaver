# Settings system and single-source-of-truth audit (7 Nov 2026)

**Role:** a one-time, read-only audit of the post-registry Settings code (`main` at `71c909d4`, AC-01 merged),
requested in `Current_Plan.md` §3. It is evidence for the lead, who challenges each item and promotes what survives
into `Docs/Reference/Architecture_Checklist.md`. It changes no code and is not an authority over any contract.

**Binding constraint (operator, 7 Nov):** the spec systems stay the canonical owners: each Visualizer mode's
Settings are declared once in `core/settings/visualizer_mode_settings.py`, and each transition's in
`rendering/transition_settings.py`. Every item below folds a bypass **into** them. None replaces them.

**Method:**
- Read the source, the authority docs, the checklist and plan §3.
- Ran Qt-free introspection with the main checkout's venv: theme catalogs, the mirror generator, the transition
  resolver, the visualizer settings model, preset key coverage, and the shipped `tools/check_defaults_authority.py`
  (it passes).
- Read the operator's two stored profiles read-only, for the theme and material keys only.
- No window, no dialog, no test run.

**Priority key:**
- P0: a live, operator-visible defect.
- P1: a demonstrated divergence a user can reach, or the binding straggler.
- P2: a demonstrated divergence that is latent or cosmetic today.
- P3: hygiene.

Size is S (≤ half a day), M (≤ two days) or L (a multi-day slice). Every regression bar derives its expectations
from the canonical source (spec, canonical defaults, the theme files' own fields). None pins an authored preset,
theme or default value.

---

## SS-01 A theme pair's surface material is decided in two places, so a "[Glass]" theme gives Normal cards (P0)

**Reward:** high. The operator's field defect is fixed and the 6 Nov material feature reaches its default path.
**Risk:** medium. It changes the default look for every profile on a linked theme, so it needs operator sign-off
(see Fix). **Size:** M. **Depends on:** nothing. **Merges with:** `Current_Plan.md` §4 card surfaces, "The theme's
material doesn't reach the cards".

**Root cause.** Nothing in the runtime chain loses the value. The selected theme pair never carries a material on
the Widget side.

The runtime chain, traced:
1. The persisted `widget_theme` state.
2. `activate_persisted_widget_theme` at engine start (`engine/screensaver_engine.py:603-609`), or Themes-tab
   selection (`ui/tabs/themes_tab.py:478-576`).
3. `set_active_widget_theme`.
4. `family_binder` → `with_surface_material` (`rendering/quick/widgets/family_binder.py:465`, and ten more sites).
5. `resolve_global_surface_material` / `theme_surface_material` (`rendering/quick/widgets/surface_material.py:61-84`).
6. `OverlayCardStyle.surface_material` → `RetainedOverlayWidget.set_card_style` → host demand →
   `SurfaceBackdropOwner`.

Every step reads the one active theme's `surface_material` correctly. A forced Style Override works because it
short-circuits step 5.

**Evidence:**
- **The Settings side carries the material.** A Settings theme's material is `backdrop.mode`
  (`ui/settings_theme_spec.py:69`, `NATIVE_BACKDROP_MODES = {"off", "acrylic", "glass"}`), shown in its name as
  "[Glass]" or "[Acrylic]".
- **The Widget mirror drops it.** The linked Widget theme is a generated mirror
  (`tools/generate_widget_theme_mirrors.py:230-235` builds `WidgetThemeSpec(theme_id, name, linked_settings_theme_id,
  colors)`). The docstring at `:247` says: "Settings-window backdrop material is deliberately not projected into
  runtime cards".
- **The name tag goes too.** `_widget_display_name` (`:113`) strips the "[Glass]" tag from the Widget name.
- **Every linked pair, introspected:** 57 glass and 42 acrylic Settings themes all link to Widget mirrors with
  `surface_material=None`. The only material-bearing Widget themes are the 15 `widget:material:*` themes, and all
  are unlinked (`linked_settings_theme_id=None`).
- **The operator's stored profiles match exactly:**
  - `SRPSS_MC`: `widget_theme = {selected_id: "mirror:file:Navigator Nebula [Complex] [Glass].srtheme",
    keep_synced: true}`, `widgets.global.surface_material: "theme"`.
  - `SRPSS`: the same shape with Nebula Pharmacy [Glass], and `surface_material` absent, which also means Theme.
  - Both resolve to Normal.
- **Keep Synced blocks the 15 material themes.** Keep Synced is the canonical default
  (`core/settings/default_settings.py:451`). Under it, selecting any of the 15 is refused with "Switch to
  Independent before selecting it." (`ui/tabs/themes_tab.py:489-505`), so no material is reachable through themes
  in the default linked mode.
- **The docs still state the superseded rule:**
  - `Docs/Architecture/Card_Surface_Materials.md:244`: "Existing themes name none and stay Normal under Theme";
  - `ui/widget_theme_runtime.py:15`: "Card material is intentionally not part of Widget Theme state";
  - `core/settings/widget_theme_input_compat.py:3`: "colour-only schema v3".

  Each predates the 6 Nov supersession that let themes name a material.

**Fix (owning boundary: `widget_counterpart_for_settings_theme`, the one authority that pack generation, the Theme
Foundry and the theme sorter all call):**
- Project the pair's material once: `glass` → `glass`, `acrylic` → `acrylic`, `off` → none.
- Apply it to existing mirrors as a **fill of one key**, like the preset repair fill. Do not regenerate them
  wholesale: 10 of the 99 shipped mirrors differ from generator output in authored colour roles (for example
  `media.volume.fill`), and a regeneration would erase those edits.
- Update the three stale docstrings and Card_Surface_Materials §4.
- Optionally, restore a material tag on the Widget name so a user can see it.
- The runtime resolver is untouched. It must not reach into the Settings theme, because that would be a second
  resolver.

**Operator decision needed first:** the canonical default pair (`Default Dark [Single] [Glass]`, Keep Synced) would
then render Glass cards on every fresh profile. The alternative keeps the mirrors Normal and instead:
- gives the 15 material themes linked Settings counterparts;
- labels the Settings theme's "[Glass]" as window-only.

Either option removes the two-owner split. Today's state, where the name says Glass and the cards are Normal, is the
defect.

**Regression bar (fails today, because every linked mirror names no material):**
- For each linked pair in the shipped catalog, `widget_counterpart_for_settings_theme(settings_theme, ...)` and the
  shipped mirror file both carry the projection of that Settings theme's own `backdrop.mode`. The expected value is
  derived from the Settings theme, never pinned.
- **End-to-end on the binder:**
  1. Resolve a linked "[Glass]" pair with `keep_synced=True`.
  2. `set_active_widget_theme(resolved.theme)`.
  3. Build `ClockFamilyAdapter().presentation_model(widget_id="clock", widgets_config={"global":
     {"surface_material": "theme"}, "clock": {"surface_material": "inherit"}}, ...)`.
  4. `model.style.card_style.surface_material` equals the projected material. Today it is `"normal"`.

---

## SS-02 Fold the Audio Analysis (technical) controls into each mode's spec (P1, the known straggler)

**Reward:** high. One declaration per technical control, runtime admission, a complete preset guard, and the
Studio reading the spec. **Risk:** medium. Every mode's reactivity values pass through it, so admission must be
byte-identical for in-range values. **Size:** M-L. **Depends on:** nothing. Land before any new technical control.
**Merges with:** the AC-01 residue in plan §3 (the dead widget half is SS-07).

**Evidence (one control family, declared in five places with disagreeing ranges):**
- **Settings definitions:** `ui/tabs/media/technical_controls.py:256-424` (`_BASE_CONTROL_DEFS`: labels, ranges,
  scales, options).
  - Per-mode extras live at `:33-55` (`_TRANSIENT_MIX_META`) and `:470-492` (Bubble's vocal mix).
  - A second hiding mechanism, `modes=_KICK_GAIN_MODES/_PULSE_GAIN_MODES` (`:30-31`), sits beside the registry's
    audited `technical_hidden_suffixes` (`core/settings/visualizer_mode_registry.py:98`). For example,
    `bubble_kick_lane_gain` is owned but offered nowhere.
  - Per-mode recommendation tables (`:76-87`) duplicate what `Slider.recommended`
    (`visualizer_mode_settings.py:116`) already models.
  - Keys are built by string (`_storage_key` and `_resolve_default`, `:564-596`; the comment at `:448-450` records
    the doubled-prefix bug this caused), although the registry already maps suffix → key
    (`get_owned_mode_setting_keys(mode, "technical")`).
- **Membership:** the registry (`technical_controls`, `technical_setting_suffixes`, `technical_hidden_suffixes`,
  `visualizer_mode_registry.py:85-116`) and the contract (`PER_MODE_BASELINE_KEYS` / `SPECIAL_PER_MODE_KEYS`,
  `core/settings/visualizer_settings_contract.py:46-66`). The registry's technical set omits the mix keys that the
  Settings definitions add.
- **The Studio has its own admission:** `ui/studio/technical.py:56-61` uses `_coerce_value` + `_clamp_numeric`.
  It does not snap to the slider step or fall back to an option the way Settings' `admit_technical_value`
  (`technical_controls.py:640-649`) does.
  - Three adapters import the private `_control_defs_for_mode` directly (`ui/studio/bubble_adapter.py:376`,
    `engine_answers.py:299`, `sphere_adapter.py:431`).
  - So does `tools/visualizer_replay/analysis_controls_audit.py:68`.
- **Runtime clamps restated:** `widgets/spotify_visualizer/audio_worker.py:393` (sensitivity 0.25-2.5), `:494`
  (AGC 0-1), `:505` (input gain 0.05-2.0), `:518` (transient clamp 0-3), and `:183` (bar count ≥ 1, no upper
  bound).
- **Manual floor has three ranges:**
  - Settings and the Studio: 0.05-1.0 (`technical_controls.py:27`);
  - startup repair: 0.0-1.0 (`core/settings/settings_manager.py:85-86, 1648`);
  - the worker: 0.0-1.0 (`audio_worker.py:238-239, 401`).

  A stored floor below 0.05 therefore runs as authored but is rewritten to 0.05 by any Settings or Studio save of
  that mode. That is latent: no curated preset is below 0.05 today.
- **The model does not admit technical values.** Introspected:
  `SpotifyVisualizerSettings.from_mapping({"mode": "spectrum", "spectrum_bar_count": 500, "spectrum_manual_floor":
  0.01, "spectrum_input_gain": 7.0}, apply_preset_overlay=False)` keeps 500 / 0.01 / 7.0. Settings would admit them
  as 96 / 0.05 / 2.0. The model only type-casts (`core/settings/models/_spotify_visualizer.py:98-123`).
  Spec'd controls are clamped by the model through the spec (`visualizer_mode_settings.py` module docstring).
  - So an imported SST or hand-edited profile reaches the beat engine with 500 bars.
- **The preset completeness guard cannot see technical keys.** `preset_artwork_keys`
  (`core/settings/visualizer_presets.py:84-94`) and so `tests/test_visualizer_preset_completeness.py` and the repair
  fill (`Docs/Reference/Visualizer_Preset_Repair.md`) cover spec controls only. All 75 curated presets do author
  their technical keys today (introspected), but a new technical control would reach none of them unguarded and
  unfilled.

**Fix (owning boundary: `core/settings/visualizer_mode_settings.py`):**
- Declare the technical controls as ordinary spec entries:
  - a shared, Qt-free helper (for example `audio_analysis_entries(mode_id)`) returns `Slider`/`Toggle`/`Choice`
    entries with keys from the registry's suffix map;
  - they go in a non-body `technical` bucket, appended by every mode spec whose descriptor has
    `technical_controls`;
  - use `admission_low/high` and `runtime_low/high` where the worker keeps a wider domain, and `recommended` for
    the per-mode marks.
- Fold the mode filter (`_KICK_GAIN_MODES`/`_PULSE_GAIN_MODES`) into `technical_hidden_suffixes`, so one audited
  mechanism decides offered and hidden.
- Then:
  - `spec_mode_builder` seeds and collects the cache from `spec.controls`;
  - `ui/studio/technical.py` builds properties from the same entries and admits with `control.admit`;
  - the model admits through `admit_runtime`;
  - `preset_artwork_keys` includes them automatically.
- Choose one manual-floor domain and record it in the spec (the worker's 0.0 if any authored value may sit below
  0.05).
- Delete `_BASE_CONTROL_DEFS`, `_TRANSIENT_MIX_META` and the recommendation tables. The registry keeps membership;
  the spec keeps presentation and range.

**Regression bar (each fails today):**
- `set(technical_storage_keys(mode)) <= set(preset_artwork_keys(mode))` for every mode with technical controls.
- The model admits a test-owned out-of-range value (the control's declared high + 1, read from the spec) to the same
  value Settings' cache and the Studio's admission produce. Today 500 stays 500.
- For a floor at half the control's declared low, the Settings cache, the Studio admission and the model agree.
- Every technical key of every mode is `require_mode_settings(mode).control(key)`. Today it raises `KeyError`.

---

## SS-03 The process-local active themes are not re-derived after Reset or Import (P1)

**Reward:** medium. Reset and Import mean what they say in the same session. **Risk:** low. **Size:** S.
**Depends on:** nothing. **Merges with:** none (AC-07 is about publication, not activation).

**Evidence:** persisted `widget_theme` / `ui.settings_theme_selection` and the process-local active themes are two
owners, re-synced only on some write paths:
- **Reset to Defaults** (`ui/settings_dialog.py:1888-1900` → `SettingsManager.reset_to_defaults`,
  `core/settings/settings_manager.py:1712-1760`) rewrites both theme roots to canonical defaults. They are not in
  `PRESERVE_ON_RESET`, `core/settings/defaults.py:44-63`. Nothing re-activates either theme:
  - the Settings window keeps the old theme;
  - the replacement runtime after close builds cards from the old process-local Widget theme (cards resolve it at
    construction: `surface_material.py:61-68`, `display_manager.py:3351-3373`);
  - both snap to the defaults only at the next Settings open (`settings_dialog.py:626-646`) or app start.
- **Import** re-activates only through `apply_settings_theme_selection` (`ui/settings_import.py:109-122`), which
  re-activates the Widget theme only when `keep_synced` (`ui/settings_theme_selection.py:24`). An imported
  Independent Widget theme (for example a material theme) is persisted but not applied until restart.
- The Themes tab has no `reloads_with_settings` (`ui/settings_tabs.py:131`), so after either action its lists show
  the pre-reset or pre-import selection.

**Fix (owning boundary: `ui/widget_theme_selection.py` / `ui/settings_theme_catalog.py`):**
- One function re-derives both active themes from persistence: the existing `activate_persisted_settings_theme` +
  `activate_persisted_widget_theme` pair, without rebuilding the catalogs.
- `_reload_all_tab_settings` calls it, so reset and import share the edge.
- `ThemesTab` gains `reloads_with_settings=True` and a `load_from_settings` that repopulates from the same state.

**Regression bar (fails today):**
1. Activate an Independent Widget theme X and a non-default Settings theme.
2. Run the dialog's reset handler, with `StyledPopup.exec` patched.
3. `get_active_widget_theme()` equals `resolve_widget_theme_state(read_widget_theme_state(s),
   settings_theme_id=read_persisted_theme_id(s)).theme`, and `get_active_settings_theme()` equals the persisted
   selection.

Do the same for a "theme"-category import of a snapshot with `keep_synced: false`.

---

## SS-04 Particle, Blinds and Burn bypass the transition spec: a canonical default never applies (P2)

**Reward:** medium. The binding spec's promise holds for every transition ("the request resolver clamps numbers to
the same ranges", `rendering/transition_settings.py:6`). **Risk:** low. **Size:** M. **Depends on:** nothing.
**Merges with:** none.

**Evidence:** the three `custom=True` pages (`transition_settings.py:542, 576-578, 583`) declare their ranges three
times: the tab, the resolver and the renderer validation. They disagree:
- **Particle radius:**
  - canonical default 7.0 (`core/settings/default_settings.py:204`);
  - the resolver clamps `max(8.0, ...)` (`rendering/quick/transitions/parameter_resolution.py:219-226`);
  - introspected, `_resolve_particle({}, rng).parameters["particle_radius"] == 8.0`, so the default never runs;
  - the Settings spin offers 4-80 (`ui/tabs/transitions_tab.py:1060`), and 4-7 all resolve to 8.
- **Particle gloss:** Settings 10-200 (`:1100`) against the resolver's 16-128 (`parameter_resolution.py:248-256`).
  The ranges 10-15 and 129-200 do nothing.
- **The Particle save writes restated literals** for fields the page does not show (`transitions_tab.py:906-917`:
  `overlap: 4.0`, `swirl_strength: 1.0`, `trail_length: 0.15/0.0`, `trail_strength: 0.6/0.0`).
  - Any page save overwrites a stored or imported value, and silently diverges the day the operator edits those
    canonical defaults.
- **Blinds:** the resolver restates the UI slider's maximum (`ui_feather / 25.0`, `parameter_resolution.py:114`).
  The renderer re-validates Burn's ranges a third time (`rendering/quick/transitions/implementations/burn.py:70-95`).

**Fix (owning boundary: `rendering/transition_settings.py`):**
- Express the three pages' numeric and choice fields as spec controls. The spec's `Slider`/choice types cover all of
  them; Particle's mode-dependent visibility is what `custom` was kept for, and the visibility can stay custom while
  ranges move to the spec.
- The resolver then admits through the spec.
- Derive Particle's hidden fields from the stored value or the canonical default, never from literals.
- Resolve the 7-vs-8 radius by choosing one admitted low (a product call: the default or the clamp moves).

**Regression bar (fails today):**
- `_resolve_particle({}, rng).parameters["particle_radius"] == float(require_canonical_default(
  "transitions.particle.particle_radius"))`.
- For every numeric field of Particle, Blinds and Burn, the Settings control's range equals the spec range the
  resolver admits.
- Hydrating and saving the Particle page with a stored `overlap` different from canonical keeps it.

---

## SS-05 The shared Bar Appearance and Rainbow families sit outside the spec (P2)

**Reward:** medium. This finishes A-12: there is no hidden value-owner QWidget, one range per value, and the preset
guard covers the families. **Risk:** low-medium. Spectrum and Extruded Spectrum share the bar rows. **Size:** M.
**Depends on:** SS-02's pattern (the same shared-entries helper). **Merges with:** plan §3, "A-12 residue".

**Evidence:**
- **Ranges restated in four places:**
  - the Settings rainbow slider: `ui/tabs/visualizers_tab.py:416-417`, 1-100;
  - its save, `/100`: `ui/tabs/widgets_tab_media.py:1309-1312`;
  - the Studio admission: `ui/studio/technical.py:81-100`, 0.01-1.0;
  - the Studio's load back into hidden widgets: `ui/studio/settings_link.py:355`, `max(1, min(100, ...))`.
- **Border opacity** is declared on the widget only (`ui/tabs/media/shared_appearance_controls.py:90-96`).
- **The values live in one never-shown QWidget holder** (`visualizers_tab.py:333`, `visualizer_studio_family_values`).
  The Studio writes them by driving those widgets (`settings_link.py:336-372`).
- **Membership is registry-only** (`rainbow_controls`, `shared_bar_appearance`, `visualizer_mode_registry.py:103-113`).
  These keys are not spec controls, so `preset_artwork_keys` does not guard or fill them.

**Fix (owning boundary: `visualizer_mode_settings.py`):** declare the two families as shared spec entries per
owning mode, the same as SS-02. The page keeps them in a value cache like `_<prefix>_lazy_values`. The Studio's
`rainbow_properties`/`admit_rainbow` and `_load_families` read the spec entries and write the cache.

**Regression bar (fails today):**
- The page builds no hidden value-owner QWidget (the plan's own bar).
- The family keys are `<= preset_artwork_keys(mode)` for each owning mode.
- The Studio and Settings admit a test-owned out-of-range speed identically, via the spec control.

---

## SS-06 A second product-identity resolver inside Settings (P2)

**Reward:** medium (SMP readiness: the contract requires one predicate). **Risk:** low. **Size:** S.
**Depends on:** none. **Merges with:** AC-01's contract.

**Evidence:** `Docs/Architecture/Settings_Bucket_Persistence_Contract.md:30` says a new product profile "extends
that predicate, never a second resolver". But two Settings surfaces decide "is MC" from the store's application
name, compared to a literal:
- `ui/tabs/display_tab.py:63` (`settings.get_application_name() == "Screensaver_MC"`, used at `:376, :703, :852` to
  force interaction on);
- `ui/onboarding/state.py:68` (`is_media_center_profile`).

The runtime enforces the same rule ("MC forces interaction") through `is_mc_build()`
(`engine/display_manager.py:1492, 1667`). `default_contract.MC_PROFILE` (`core/settings/default_contract.py:26`)
exists and is unused at either site. The two agree in production, where both probe argv and `__main__`; they
disagree under injected managers and will disagree for any third profile.

**Fix:** both sites read `SettingsProfile.current().mc` (or one `core/mc.py` helper). The interaction-forcing rule
gets one owner that Settings and the runtime both call.

**Regression bar (fails today):** with `core.mc.is_mc_build` patched to True and a manager whose application name
is `Screensaver`, the Display tab and `is_media_center_profile` both report MC.

---

## SS-07 AC-01 residue: dead technical-widget code, dead Advanced plumbing, and a contradicting copy of a rule (P3)

**Reward:** low-medium. It removes about 600 dead lines and one trap. **Risk:** low, provided the bucket-state
schemas follow the bridge procedure. **Size:** S. **Depends on:** SS-02 (it deletes the rest of
`technical_controls.py`). **Merges with:** AC-14 (dead settings sweep) and the plan §3 "Dead after A-12" note.

**Evidence (production-reference counts from a repo grep):**
- **No production caller** for `build_per_mode_technical_group`, `register_per_mode_technical_controls`,
  `load_per_mode_technical_controls` and `collect_per_mode_technical_controls`
  (`ui/tabs/media/technical_controls.py:874-1151`). Only `tests/test_visualizer_settings_plumbing.py` calls them.
  The same goes for their helpers and `get/set_visualizer_tech_state`, `get/set_visualizer_tech_bucket_state` and
  `get/set_visualizer_adv_state` (`ui/tabs/visualizer_settings_context.py:437-475`).
- **`_VISUALIZER_ADVANCED_ROOT_ATTRS`** (`visualizer_settings_context.py:61-71`) names roots no mode builds, so
  `_auto_switch_preset_to_custom` (`:729-778`) returns at `if not adv_roots` on every Visualizers and Widgets save
  (`ui/tabs/visualizers_tab.py:780`, `ui/tabs/widgets_tab.py:1584`). The Studio switches to Custom through
  `_force_visualizer_preset_to_custom` instead.
- **A dead copy contradicts the live rule.** The tab's `_is_global_visualizer_key` (`visualizer_settings_context.py:
  630-644`) admits `monitor`, `bar_count`, the ghost keys and `rainbow_*` as global preset keys. The live rule
  (`core/settings/visualizer_presets.py:66-73, 107-108`) admits only `mode`, and documents why `monitor` must not be
  admitted: it rerouted the widget. The tab's `_is_key_for_mode` is also an unused duplicate.
- **The retired suffixes `energy_boost`/`use_raw_energy`** are listed four times:
  - `visualizer_settings_context.py:60`;
  - `core/settings/visualizer_settings_snapshot.py:52`;
  - `tools/visualizer_preset_author.py:27`;
  - `tools/visualizer_preset_repair.py:68-69`.
- **Three bucket-state schemas have no live disclosure:** `ui.visualizer_adv_states`, `ui.visualizer_tech_states`
  and `ui.visualizer_tech_bucket_states` (`core/settings/default_settings.py:267, 334, 350`;
  `core/settings/ui_bucket_state.py:277-304`; `core/settings/structured_roots.py:38`).

**Fix:**
- Delete the dead functions, the Advanced plumbing and the tab's two static copies. Point the one live caller of the
  retired suffixes at `visualizer_settings_snapshot`'s set.
- Retire the three schemas through `Docs/Architecture/Persisted_Input_Compatibility.md` "Removing a bridge
  safely": the normalizer keeps accepting old members at input; the canonical default stops declaring them.

**Regression bar (fails today):**
- AC-14's reachability scan, extended to symbol level for `technical_controls` and `visualizer_settings_context`.
- The canonical `ui` defaults declare no disclosure schema that no live builder constructs (derived from the
  registry and spec buckets).

---

## Addenda to existing checklist items (not new items)

- **AC-09 (card border width resolved once):** two more consumers restate the clamp.
  - The Studio's `card_style` (`ui/studio/settings_link.py:428-443`, `max(0.0, min(12.0, border))`).
  - The Settings General page admits an integer: the spin is 0-12 (`ui/tabs/widgets_tab_defaults.py:910`), the
    load clamps (`:1091`) and the save writes `int(border_width)` (`:1159`).

  The resolver AC-09 exports must also own the admitted type that Settings writes.
- **AC-07 (unchanged writes publish):** SS-03's re-derivation must hang off the existing `'*'` reset/import edge.
  It must not add a new subscription that fires on every unchanged write.

---

## Considered and rejected

- **A stored `widgets.global.surface_material: "normal"` overriding the theme.** This is a recorded no-bridge
  decision (`Persisted_Input_Compatibility.md` "Surface Material baseline default"). Both of the operator's profiles
  hold `theme` or absent, so it is not the cause of SS-01.
- **The Custom Widget theme losing its material.** `to_custom_snapshot` uses `dataclasses.replace`
  (`ui/widget_theme_runtime.py:146-153`), and `widget_theme_to_payload` writes `surface_material` when set
  (`ui/widget_theme_io.py:151-152`). Style Override colour edits keep it.
- **The v1/v2 Widget theme compat stripping the material.** It removes only the Sep 2026
  `card_material_override`/`default_card_material_mode` names (`core/settings/widget_theme_input_compat.py`).
- **A runtime that should poll the theme.** Construction-time resolution is the documented design. The runtime is
  rebuilt after Settings, and SS-03 covers the only gap: reset and import.
- **Hand-listed import categories (`_DISPLAY_ROOTS` and others, `core/settings/sst_io.py:54-104`).** Unclaimed
  roots fall to Misc, and "every category" equals a full import, so no value can be dropped.
- **Literal fallbacks in renderers.** The Extruded Bubble scene `knobs.get(..., literal)` and the
  `rendering/quick/visualizer/item.py` geometry fields are renderer-internal look and geometry values, not Settings
  keys. Settings keys are hard-indexed through `_p` (`rendering/gl_programs/extruded_bubble_scene.py:52-53`). The
  single Settings fallback there (`extruded_bubble_ray_path`, `:136`) equals canonical, and the key is always
  present after admission. `tools/check_defaults_authority.py` passes.
- **Guided Setup's raw dotted keys with `or "Rich"` / `or 0` (`ui/onboarding/setup_page.py:241, 371`).** The draft
  falls back to the seeded store (`ui/onboarding/draft.py:58-70`), so the literals fire only for an explicit `None`.
  Not worth an item.
- **`_LEGACY_GLOBAL_MIGRATION_BASELINES` and `_SCHEMA10_EXTRUDED_PROFILE` literal values
  (`visualizer_settings_contract.py:21-104`).** They are frozen migration signatures by design, never live
  defaults. Only the live membership tuples feed SS-02.
- **Technical keys missing from curated presets.** None are missing today (all 75 checked). The defect is the
  guard's blindness, inside SS-02.
- **Extruded Spectrum borrowing Spectrum's profile, and 2D/3D Bubble duplication.** Both are declared lender/owner
  designs (`technical_profile_mode`, `shared_bar_profile_mode`; "Extruded Bubble is its own mode"), not accidental
  copies. The camera split between modes is AC-11.
- **The Context Menu resolving its material in `DisplayManager` (`engine/display_manager.py:1388-1391`).** It calls
  the same `resolve_global_surface_material`, so there is no second rule.

## Could not verify

- **No live run.** SS-01's root cause is established from source, introspection and the stored profiles. Whether
  the operator clicked a "[Glass]" Settings theme (linked mirror, Normal) or tried one of the 15 material themes
  under Keep Synced (refused) is inferred from the profiles: both hold a linked "[Glass]" mirror with Keep Synced
  on. Both paths lead to Normal cards.
- **The installed (frozen) theme tree was not inspected.** The catalog used here is the repository's `themes/`.
  The MC build's own theme root could differ in which mirrors or material themes it ships.
- **The 10 mirrors that differ from generator output.** Whether those deviations are deliberate authoring or stale
  generations is the operator's or theme author's call. SS-01's fill-only fix is safe either way.
