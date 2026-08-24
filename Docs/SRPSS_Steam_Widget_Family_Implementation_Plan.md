# SRPSS Steam Widget Family — Quick-Era Reference Index

Status: **CURRENT WRAPPER — two substantive migration families; two deferred stubs**  
Updated: 2026-08-24

## Current source reality

The Steam family contains four registered identities, but they are not four implemented product widgets.

Current source explicitly treats:

```text
steam_progress / Steam Journey -> unfinished dev-gated scaffold
friend_pulse                  -> unfinished dev-gated scaffold
```

Both are dev-gated prototype/scaffold presentation and have no substantive product/runtime behavior that
needs a Qt Quick pixel port.

Current substantive implemented families are:

```text
achievement_pulse   -> Achievement Pulse
abandonment_issues  -> Abandonment Issues
```

Achievement Pulse has dedicated cache-first runtime/resolution/preparation behavior.
Abandonment Issues has its own substantive runtime/widget/data path.

Therefore the Qt Quick migration has only two Steam presentation slices:

```text
F7 Achievement Pulse
F8 Abandonment Issues
```

Steam Journey/Progress and Friend Pulse are **not Phase-F work**.

Do not manufacture Quick versions of placeholder cards just because their ids exist in descriptors,
settings, mock visuals or old plans.

## Deferred stub policy

The existing Steam Journey/Progress and Friend Pulse stubs may remain dev-gated during migration if they
do not obstruct cleanup.

Do not:

- fill in their missing product/data semantics;
- create provider/runtime architecture for them;
- create retained Quick components for them;
- treat mock/scaffold presentation as a fidelity target;
- expand migration scope merely to make the four-family catalog symmetrical.

Their actual product implementation belongs to future feature work after the migration or to an explicit
operator-requested product slice.

If their old scaffold pixels later block removal of a shared QWidget presentation owner, caller-proof
and retire the scaffold rather than porting it for parity.

## Why this file is short

The original 2026-07 Steam plan was ~123 KB and mixed:

1. useful Steam product/data/privacy/security/visual decisions;
2. obsolete QWidget/`BaseOverlayWidget`/QPainter presentation architecture;
3. speculative designs for the unfinished Steam Journey and Friend Pulse concepts.

The full historical plan remains available in Git history for targeted lookup. It is not current
presentation architecture.

## Current implementation authority

For substantive Steam migration work read:

- `Current_Plan.md`
- `Docs/QtQuick_Migration/10_Widget_Family_Port_Decomposition.md`
- `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`
- `Docs/QtQuick_Migration/09_Widget_Quick_Presentation_Bridge.md`
- `Docs/10_WIDGET_GUIDELINES.md`
- current source under `core/steam/`, `widgets/steam_*`, and `widgets/steam_card_models.py`

`widgets/steam_card_models.py` is preferred neutral presentation-state evidence over old painter code.

## Product/data rules retained from historical planning

For implemented Steam features:

- no Steam password/Steam Guard handling;
- no globally bundled developer API key;
- no authenticated Store scraping/session-cookie/browser-automation fallback;
- no fabricated last-played/session/rarity/ownership/completion facts;
- unknown/private/unavailable source state remains explicit;
- cache/provider work is bounded and privacy-safe;
- secrets never enter exports/logs/tests/screenshots/repository;
- shared data must not become duplicate provider/fetch streams per Quick component;
- presentation must not silently invent a fallback data source.

Current source/contracts outrank historical planning where implementation deliberately changed product
semantics.

## Current presentation rule

Substantive Steam runtime pixels migrate to retained Quick presentation.

Do not deepen or reproduce:

- `BaseOverlayWidget` as destination;
- QPainter card/text/header shadow architecture;
- QGraphics effects;
- old widget-factory pixel ownership as final presentation;
- separate provider/runtime ownership per Quick component.

Use the shared retained shell, explicit presentation model, semantic action routing and existing Quick
engine/window.

## Historical visual reference

For Achievement Pulse and Abandonment Issues, old implemented QWidget pixels may be consulted for:

- actual content hierarchy;
- labels/fields;
- artwork placement;
- spacing;
- interaction intent;
- empty/error/private states.

That reference does not make painter mechanics authoritative.

For Steam Journey/Progress and Friend Pulse, scaffold/mock visuals are concept evidence only, not a
migration fidelity contract.

After each substantive Steam Quick port is GREEN, caller-proof and delete that family's old runtime
pixels. Git remains historical reference.
