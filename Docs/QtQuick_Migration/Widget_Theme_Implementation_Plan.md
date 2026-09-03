# Widget Theme — Current Implementation Plan

## 0. Scope

Widget Theme is a retained-runtime **semantic colour** system. It owns palette roles
for ordinary cards, Context Menu and specialized Widget visuals. It does not own
activation, geometry, cadence, providers, native Settings-window backdrop material,
or runtime compositor effects.

The abandoned runtime-card Glass/Acrylic work is recorded separately in
`Rejected_Card_Material_Experiments_2026-09-02.md` and must not be reintroduced as
ordinary theme work.

## 1. Identity and linking

- Widget Theme uses stable `theme_id` identity; display names are never link keys.
- `linked_settings_theme_id` is the explicit Settings counterpart identity.
- Linked mode is bidirectional: Settings selection moves Widget selection and Widget
  selection moves Settings selection when a counterpart exists.
- Selection never silently unlinks. Unpaired themes and Widget `Custom` require the
  user to choose Independent first.
- Widget catalogue display names remove trailing Settings-only `[Glass]`/`[Acrylic]`
  tags from both Widget display names and Widget filenames; stable IDs and explicit Settings link IDs remain unchanged.

## 2. Schema-v3

`.srwtheme` schema-v3 contains exactly:

```text
format
schema_version
stable theme_id
human name
linked_settings_theme_id
semantic colors
```

There is no card-material recommendation or Surface Style field. Shipped mirrors are
strict schema-v3. Settings-persisted Custom snapshots from the retired schema are
migrated once by dropping only the retired material field and preserving identity,
link metadata and every semantic colour.

## 3. Palette precedence

```text
explicit intentional family override
-> exact Widget Theme semantic role
-> semantic parent role
-> local/current semantic context
-> preserved fallback pixel
```

Global `card.background`, `card.border` and `card.text` are Widget Theme baselines.
Explicit existing `widgets.<family>.card.*` values remain higher precedence. Context
Menu has no family override and consumes Widget Theme roles directly.

`Widgets -> General -> Style Overrides` contains:

- Card Surface — theme-owned edit; forks named theme to persisted Widget `Custom`;
- Card Border — same ownership rule;
- Card Border Width — global styling outside Widget Theme schema.

No Surface Style/material control exists.

## 4. Sparse specialized semantics

`ui/widget_visual_roles.py` is the one inheritance authority. Do not create
family-local theme cascades or persist `local.*` presentation context. Mature shared
Media roles include transport, mute, volume and progress/seek. Abandonment's archive
accent uses `abandonment_issues.accent -> widget.accent`, while readable text remains
on the normal text semantic rather than accent-on-accent.

## 5. Theme Foundry / mirror generation

`tools/generate_widget_theme_mirrors.py` and Theme Foundry's `Save Widget
Counterpart…` use the same deterministic Settings->Widget semantic projection.
Settings-native backdrop mode is deliberately ignored by the Widget projection.
Mirrors retain explicit stable link IDs and materialize the mature shared semantic
roles required for readable light/dark/metal palettes.

## 6. Runtime publication

The active Widget Theme is one immutable process-local palette snapshot. Retained
presentation construction consumes that snapshot; no render-loop Settings read,
polling service or material owner is introduced. Theme publication remains
transactional and live Settings listeners must preserve deleted-QObject pruning and
rollback behavior.

## 7. Current acceptance

- physical bidirectional selection/recreation;
- Custom creation from Card Surface/Border edits;
- family override precedence;
- Context Menu semantic coverage and submenu crossing;
- Abandonment/BACKLOG readability;
- Reddit time-column parity;
- Theme Foundry counterpart export/reload;
- installed/frozen theme-root discovery;
- theme-switch responsiveness audit without weakening transaction correctness.

The broader theme-system fragility/edge-contract audit remains a separate next task
owned by `Current_Plan.md`.
