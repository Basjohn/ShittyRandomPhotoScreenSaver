# SRPSS Steam Widget Family — Quick-Era Reference Index

Status: **CURRENT WRAPPER — pre-Quick implementation plan archived in Git history**  
Updated: 2026-08-24

## Why this file is short now

The original 2026-07 Steam plan was ~123 KB and mixed two kinds of information:

1. valuable Steam product/data/privacy/security/visual decisions;
2. now-obsolete QWidget/`BaseOverlayWidget`/QPainter runtime-presentation architecture.

During the Qt Quick migration, feeding that entire old plan to coding agents is actively dangerous.
Its old presenter map must not override current Phase-F architecture.

The full historical plan remains available in Git at:

```text
a586801d2ffe0868710fc23da1a649df1d122d29
Docs/SRPSS_Steam_Widget_Family_Implementation_Plan.md
```

Use targeted `git show`/history inspection only when a detailed historical product/visual decision is
needed.

## Current implementation authority

For F7–F10 read:

- `Current_Plan.md`
- `Docs/QtQuick_Migration/10_Widget_Family_Port_Decomposition.md`
- `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`
- `Docs/QtQuick_Migration/09_Widget_Quick_Presentation_Bridge.md`
- `Docs/10_WIDGET_GUIDELINES.md`
- current source under `core/steam/`, `widgets/steam_*`, and `widgets/steam_card_models.py`

`widgets/steam_card_models.py` is already a Qt-free immutable semantic/presentation-state seam and is
preferred evidence over old painter architecture.

## Stable family identities

```text
steam_progress       -> Steam Journey
achievement_pulse    -> Achievement Pulse
abandonment_issues   -> Abandonment Issues
friend_pulse         -> Friend Pulse
```

They remain independently configurable/movable cards while sharing appropriate Steam data/cache/runtime
ownership.

## Product/data rules retained from the historical plan

Keep these as durable constraints:

- no Steam password/Steam Guard handling;
- no globally bundled developer API key;
- no authenticated Store scraping/session-cookie/browser-automation fallback;
- no fabricated last-played/session/rarity/ownership/completion facts;
- unknown/private/unavailable source state remains explicit;
- cache/provider work is bounded and privacy-safe;
- secrets never enter settings exports/logs/tests/screenshots/repository;
- shared data does not become four duplicate provider/fetch streams;
- presentation must not invent a fallback data source silently;
- Steam cards remain separately identified and separately enabled;
- useful cached state may remain visible with clear stale/connection status where product semantics
  already define that behavior.

Current source/contracts outrank this summary if a later product implementation deliberately changed one
of these rules.

## Current presentation rule

Runtime Steam pixels are Phase-F retained Quick presentation.

Do not implement or deepen:

- `BaseOverlayWidget` as destination;
- QPainter card/text/header shadow architecture;
- QGraphics effects;
- old widget-factory pixel ownership as final presentation;
- old Custom QWidget pixels as destination;
- separate provider/runtime ownership per Quick component.

Use the shared retained shell, explicit presentation model, semantic action routing and existing Quick
engine/window.

## Historical visual reference

The old plan and current QWidget Steam pixels may be consulted for:

- card content hierarchy;
- labels/fields;
- silhouettes;
- artwork placement;
- spacing;
- interaction intent;
- empty/error/private states.

That visual reference does not make the old painter mechanics authoritative.

After each Steam family's Quick port is GREEN, caller-proof and delete that family's old runtime pixels;
Git remains the detailed historical reference.

## Relative implementation complexity

Achievement Pulse currently has especially strong neutral foundations (`SteamCardViewModel` plus
dedicated Achievement resolution/runtime/preparation paths), so its presentation port should not rebuild
provider/business logic.

Steam Progress/Steam Journey must not gain unsupported data semantics merely to make its presentation
port appear complete; verify current source/data-feasibility authority before changing its product state.
