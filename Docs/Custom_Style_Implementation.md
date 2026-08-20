# Custom Style Implementation

Last updated: 2026-08-20

Guidance for SRPSS Settings UI and runtime visual styling.

## 1. Goals

- preserve SRPSS custom chrome and dark settings language;
- preserve all runtime customization during the Qt Quick migration;
- keep shared style decisions in shared owners;
- fix focus/startup/visibility/render bugs at their owner rather than deleting visuals.

## 2. Settings UI sources

Settings remain QWidget-based unless a separate future product decision changes that.

Current settings style sources remain:

- `ui/settings_dialog.py`
- `ui/settings_theme.py`
- `ui/tabs/shared_styles.py`
- `ui/styled_popup.py`
- `ui/widgets/`

Do not rewrite them merely because runtime presentation migrates to Quick.

## 3. Runtime presentation architecture

Runtime widget pixels are migrating to the display's retained Qt Quick scene.

Migration details:

- `Current_Plan.md`
- `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`

Keep provider/model/settings authority in Python.

## 4. Runtime style contract

Quick runtime must preserve:

- font family/size;
- text color/opacity;
- background show/color/opacity;
- border width/color/opacity;
- corner radius;
- margin/padding;
- card shadows;
- text/header shadows;
- per-widget/global opacity/fade;
- artwork/progress/special family styling.

Do not remove a control because the exact QWidget implementation no longer exists.

## 5. Shadow history

The historical multi-monitor shadow corruption involved QWidget `QGraphicsEffect`/effect cache
behaviour.

Relevant records:

- `Docs/Historical_Bugs/U-06_MC_Shadow_Cache_Corruption.md`
- `Docs/Historical_Bugs/R-24_Retired_Overlay_Effect_Cache_Busting.md`

Painter-owned shadows were the correct QWidget-era response.

Qt Quick must **not** reintroduce `QGraphicsEffect`.

For the Quick runtime:

- prefer a retained rectangular/card shadow shader/item for rounded cards;
- use bounded Quick effects only where an arbitrary-shaped source requires them;
- do not use broad focus/menu/display cache-busting;
- do not toggle effect topology to animate fade;
- explicitly stress multi-monitor focus/context/hide/recreate.

## 6. Settings styling safety

Continue to avoid:

- broad visibility/focus recursion;
- constructing every settings section at startup;
- styling work that triggers provider/network activity;
- changing settings chrome as a workaround for runtime rendering issues.

## 7. Change process

Shared runtime style change:

1. update shared presentation style owner;
2. update affected retained Quick components;
3. run shared style/shadow gallery tests;
4. run focused family tests;
5. check focus/context/Settings/CUSTOM;
6. commit + push the landed slice.

No visual-fidelity downgrade as a performance fix.
