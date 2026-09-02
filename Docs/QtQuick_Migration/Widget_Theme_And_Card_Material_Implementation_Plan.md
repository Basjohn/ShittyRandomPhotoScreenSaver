# Widget Theme + Card Material — Implementation Plan

Date: 2026-09-02

Consolidated, source-grounded execution plan for the committed J+ Widget Theme /
Glass / Acrylic work. This document sequences the build; it does **not** restate
or override the durable design. The design authorities are, in precedence order:

- `Docs/Contracts.md` (Widget Theme + material contract);
- `Docs/Settings_Theme_Architecture.md` (shared theme root, `.srwtheme`, fallback);
- `Docs/Custom_Style_Implementation.md` (two axes, Custom snapshot, Context Menu);
- `Future_Work.md` §10 (card-material architecture, shared/lazy backdrop);
- `Docs/QtQuick_Migration/J_ParityPlus_Historical_Visual_Interaction_Reference_2026-08-30.md` §10 (admission checklists + recommended order).

If this plan and those docs ever disagree, the docs win and this plan is corrected.

---

## 0. Non-negotiable invariant — Dark is the guaranteed default

Exactly like Settings' compiled `DEFAULT_DARK_SETTINGS_THEME`, the Widget Theme
system must have a **compiled built-in Default Dark Widget Theme** that is the
unconditional fallback. The runtime can never reach a state where "nothing works":

- no `themes/widgets/*.srwtheme` on disk, an unreadable/invalid file, a missing
  persisted selection, or a corrupt `Custom` snapshot all resolve to Default Dark;
- Default Dark recommends `default_card_material_mode = normal` and reproduces the
  current translucent `OverlayCard` appearance as closely as practical;
- the material resolver always returns a valid `effective_card_material_mode`
  (falling back to `normal`), so a runtime card always has a coherent surface;
- persistence resolves + validates the Widget Theme selection **before** first
  runtime widget composition; never deliberately flash Default Dark before a valid
  saved theme.

This is the safety spine of the whole feature and is proven first (Phase 1).

---

## 1. Reconciliation with current source (2026-09-02)

**Already exists (reuse the pattern, do not fork it):**

- Settings theme stack: `ui/settings_theme_spec.py` (schema-v5 frozen dataclasses:
  `Rgba`, `NativeBackdropStyle`, `ShadowStyle`, `Gradient*`, `SettingsThemeSpec`,
  compiled `DEFAULT_DARK_SETTINGS_THEME`), `ui/settings_theme_io.py` (whole-or-reject
  load), `ui/settings_theme_catalog.py`, `ui/settings_theme_runtime.py`
  (`get_active_settings_theme` / `set_active_settings_theme` + notify),
  `ui/settings_theme_paths.py` (placeholder path authority), `ui/settings_theme_qss.py`.
- `ui/tabs/themes_tab.py` already has a **Widget Themes** nav pill and an
  intentionally-empty `_build_widget_themes_page()` to populate.
- `ui/tabs/widgets_tab.py` owns **General → Appearance** (the `widgets.shadows.*`
  controls) — the home of the new **Surface Style** control.
- Runtime appearance snapshot pattern: `DisplayManager.initialize_displays` already
  snapshots per-generation appearance state (`_shadow_values_snapshot = asdict(
  ShadowSettings.from_settings(...))` + resolved direction) and feeds retained QML.
  Widget Theme palette + `effective_card_material_mode` follow this exact pattern —
  resolved once per generation, no per-tick settings polling.
- Retained consumers: `rendering/quick/qml/OverlayCard.qml` (card fill/border/shadow,
  already translucent `#b3101010`), the host's `OverlayCardStyle` projection, and the
  retained Context Menu (`rendering/quick/context_menu.py` + `ContextMenu.qml`).
- Shared theme root: **not yet** the final contract — `settings_theme_paths.py` is a
  placeholder; the plan resolves one theme root with a `widgets/` child.

**Does not exist yet (to build):** everything in §3–§9 below — the `WidgetThemeSpec`
/ `.srwtheme` schema, its IO/catalog/runtime, `Custom` persistence, Keep Synced, the
Surface Style preference, the `effective_card_material_mode` resolver, the runtime
palette/material wiring, and (Phases 2+) the scene-local blur material.

---

## 2. The model (consolidated — one sentence per rule)

Two orthogonal axes, never one overloaded selector:

- **Keep Synced (default ON)** links Settings-theme *identity* to a mirrored Widget
  Theme by explicit stable link metadata (not display-name heuristics). It never
  clears an explicit Surface Style override.
- **Surface Style** (`Settings → Widgets → General → Appearance`) is one
  mutually-exclusive choice `Theme Default / Normal / Glass / Acrylic`, persisted as
  `card_material_override = theme | normal | glass | acrylic`.

Resolution (the only runtime material authority):

```text
effective_card_material_mode = (
    widget_theme.default_card_material_mode      # theme's recommendation
    if card_material_override == "theme"         # "Theme Default" = no override
    else card_material_override
)
```

`Custom`: manually editing any Widget-Theme-owned swatch/border/shadow snapshots the
full resolved named theme into a user-owned `Custom` (in normal SRPSS Settings data,
**not** a `.srwtheme` file), applies the edit there, selects `Custom`, and turns Keep
Synced OFF — near-silent. Changing only Surface Style does none of that. Re-enabling
Keep Synced may reselect the linked named theme but must not destroy the Custom
snapshot. A real `.srwtheme` is produced only by explicit export/authoring.

Runtime surfaces owned by Widget Theme: ordinary card palette/border/shadow values
**and the retained Context Menu**. The Context Menu draws its palette AND its surface
material from the selected Widget Theme through the *same* `effective_card_material_mode`
resolver and under the *same* conditions as ordinary cards — it is not a separate
material/palette owner. Glass/Acrylic are **scene-local Qt Quick materials**, never the
Settings HWND AccentPolicy path. Widget Themes never own activation, provider/account
state, geometry, cadence or business logic.

---

## 3. Phase 1 — semantic + serialization + UX layer (NO rendering; ships Normal only)

This is the first and highest-value slice: it makes the whole model real and safe
while every card stays on the current cheap Normal path. Only `Theme Default` and
`Normal` are effectively selectable; Glass/Acrylic are named but disabled until their
material path is admitted (Phase 5+).

New/changed source:

- **`ui/widget_theme_spec.py`** (new) — mirror `settings_theme_spec.py`:
  `WIDGET_THEME_SCHEMA_VERSION`, a frozen `WidgetThemeSpec` (stable `theme_id`,
  link metadata to a Settings theme id, `default_card_material_mode`, the semantic
  card/text/accent/border/shadow/Context-Menu palette that mirrors the mature
  Settings/Widgets appearance authorities — **not** a parallel palette invention),
  and a compiled `DEFAULT_DARK_WIDGET_THEME` (recommends `normal`).
- **`ui/widget_theme_io.py`** (new) — whole-or-reject `.srwtheme` load/save; unknown/
  missing roles or wrong schema reject the whole file; Default Dark is the fallback.
- **`ui/widget_theme_catalog.py`** (new) — discover `.srwtheme` under the resolved
  theme root's `widgets/` child; always include the built-in Default Dark; portable
  ids, no absolute paths encoded.
- **`ui/widget_theme_runtime.py`** (new) — active Widget Theme + `Custom` snapshot +
  the `effective_card_material_mode` resolver + synchronous notify, mirroring
  `settings_theme_runtime.py`. This is the single resolver consumers read.
- **Theme root path authority** — extend the shared root resolution so both
  `.srtheme` (root) and `.srwtheme` (`widgets/` child) come from one resolved root
  (`settings_theme_paths.py` replacement or a small shared module). Do not duplicate
  path policy into renderers or merge ProgramData + repo roots simultaneously.
- **Persistence** — new Settings keys/model (e.g. `core/settings/models/` +
  `default_settings.py`): `widget_theme.selected_id`, `widget_theme.keep_synced`
  (default True), `widget_theme.card_material_override` (default `theme`),
  `widget_theme.custom` (the snapshot payload). Reuse the existing settings model +
  atomic persistence; regenerate defaults artifacts through the audited tooling.
- **`ui/tabs/themes_tab.py`** — populate the Widget Themes page: theme list + the
  **Keep Synced** toggle (default ON) + the mirror behavior (selecting a Settings
  theme selects its linked Widget Theme and vice-versa while synced). No colour
  swatches are hidden by theme selection.
- **`ui/tabs/widgets_tab.py`** (General → Appearance) — add the single **Surface
  Style** control (`Theme Default / Normal / Glass / Acrylic`; Glass/Acrylic disabled
  with a "coming soon" affordance until Phase 5). No `Override Theme Background`
  checkbox, no independent Glass/Acrylic booleans.
- **Runtime wiring** — snapshot the resolved Widget Theme palette + effective material
  into the generation the same way `_shadow_values_snapshot` is snapshotted, and feed
  it to `OverlayCardStyle` and the Context Menu style. With effective = `normal`, this
  only changes colours/opacity/border (the palette), not the render path.

Phase 1 acceptance (all non-visual / focused tests, plus eyes-on palette):

- Default Dark resolves with zero files present; invalid `.srwtheme` rejects whole;
  corrupt `Custom` falls back to Default Dark.
- `effective_card_material_mode` resolution table (theme/normal, override survival
  across theme changes, Keep Synced identity-only sync).
- Named-theme → `Custom` snapshot + auto-unsync on a theme-owned edit; Surface Style
  change does **not** create Custom/dirty/unsync; Custom preserved on reselect/relink.
- No new steady-state cost: no timer/poll/capture; runtime still on the Normal path.

---

## 4. Phases 2–7 — scene-local material (deferred; measured, not pre-optimized)

Exactly the J Parity+ §10 order; each gate is `Docs/Guardrails/Performance_Optimization_Contract.md`-bound and must not regress Visualizer freshness/R-69/R-63 `black=0`:

2. Prototype **one** per-display reduced-resolution `ShaderEffectSource` over the
   background presentation only + one shared bounded blur, consumed by one test card.
3. Prove temporal/geometry correctness during transitions + CUSTOM move/resize/pixel
   shift (same `TransitionRun`/frame sample; UVs from final display space; rounded
   mask card-local) before widening family coverage.
4. Add the Glass card-local recipe; measure.
5. Add Acrylic as the same shared backdrop + stronger cheap local treatment; measure;
   then enable Glass/Acrylic as selectable Surface Style overrides + valid theme
   defaults through the **same** resolver (no parallel path).
6. Only if the Quick capture/effect route is measurably too expensive, move shared
   backdrop production beside `BackgroundRenderNode` from the same frame state.
7. Retire shared backdrop resources when the last material consumer disappears;
   return to Normal-path cost.

Hard rules carried in (do not relax): one shared lazy backdrop/blur per display (or a
tiny measured tier set), sourced from the scene **below** ordinary widgets only (never
capture cards/Visualizer/CUSTOM/Halo/menu); all material work GPU/render-thread native
(no Python readback/CPU blur); no per-card FBO/capture/blur; one production
`QQuickWindow`; Context Menu reuses the same scene-local material, never AccentPolicy.

---

## 5. What must remain true

- Normal stays the default and essentially free; a card that is not Glass/Acrylic adds
  no capture/blur/offscreen/timer cost.
- One resolver (`effective_card_material_mode`); one theme root; one `Custom` snapshot;
  no per-property override cascade; no second material renderer.
- Settings HWND AccentPolicy is evidence only — never ported onto the `QQuickWindow`.
- Widget Theme palette reuses the mature Settings/Widgets appearance authorities; it
  does not invent a parallel palette.
- No env flags / A/B toggles; ship one real resolver, not a configurable experiment.

---

## 6. Open questions to confirm before Phase 1 coding

1. **Default Dark Widget Theme provenance:** compile it in `widget_theme_spec.py`
   (mirror Settings) and ALSO ship a `themes/widgets/Default Dark.srwtheme` bootstrap,
   or compiled-only with catalogue files purely optional? (Recommend: compiled is the
   fallback authority; a bootstrap file is optional catalogue convenience.)
2. **Palette source of truth for Phase 1:** derive the Widget Theme card palette by
   mirroring the existing `widgets.shadows.*` + card swatch settings (so a Widget Theme
   is a named bundle over current authorities), rather than adding new colour roles now.
   Confirm this keeps Phase 1 to serialization + selection with no new visual authority.
3. **Link metadata:** store the Settings↔Widget link as an explicit id pair in each
   spec's metadata; pack tooling may pair by name but runtime resolves by id.
