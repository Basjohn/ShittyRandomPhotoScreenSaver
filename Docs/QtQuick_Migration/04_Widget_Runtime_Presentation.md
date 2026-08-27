# 04 — Retained Quick Runtime Widgets

Status: **landed ordinary-widget presentation architecture; Phase F closed**  
Last updated: 2026-08-28

## Core rule

```text
provider / backend / runtime / settings / actions
-> coherent presentation state/model
-> retained Quick family pixels
```

Do not rewrite widget ecosystem as QML business logic.

## Landed host

```text
QuickSceneController
-> ordinaryWidgetHost
-> OrdinaryWidgetPresentationHost
-> retained family component
-> OverlayWidget -> OverlayCard -> family content
```

Shared primitives include `OverlayWidget.qml`, `OverlayCard.qml`, `ShadowedText.qml`, `Separator.qml`.
One process Quick engine/component cache; no engine/window per widget.

Host owns retained item creation/retirement, assigned rect, whole-widget root fade and shell/card style.
It does not own providers, persistence, SettingsManager, network, refresh cadence or global business effects.

## Common import dormancy

Common host/package stays lightweight. Importing common scene/host infrastructure does not import every
family presentation/runtime/backend module. Family implementation resolves at caller/activation; static
presentation-only metadata may stay eagerly available.

## Stable retained model

Normal accepted-state/config/style changes mutate existing family model/list model/item. Do not recreate
provider/runtime/engine/window for ordinary presentation changes. Presentation recreation may bind current
accepted state without recreating neutral owner. Stale generation/request state cannot update replacement.

## Geometry

Outer geometry is Python/session-owned; family QML lays out inside rect. Stable variants exist only for
materially different shapes, e.g. `(widget_id, display_identity, variant)` with Clock digital/analog.
Transient popup/menu state is not a geometry variant.

## Fade / shadows

Whole-widget fade is `OverlayWidget` root opacity. Do not port effect carriers, dummy shadow widgets or
staged QGraphicsOpacityEffect/`ShadowFadeProfile` choreography.

Card: `OverlayCard -> cached RectangularShadow`; no Python/QPixmap ordinary-card cache around it.
Text: duplicate shadow Text at signed offset + visible Text; no ordinary blur/MultiEffect/layer capture.

Canonical shadow user state: Card enabled/frame opacity/blur/extra offset; Text enabled/opacity/extra offset;
Header enabled; global direction NW/N/NE/W/E/SW/S/SE. No old offset pair, Intense or shadowtuning sidecar.
Python resolves final signed style before QML. Ordinary base distances in retained host are deliberate
destination policy unless family owns a real distinction.

Family-authored means independently authored. Clock analogue special relationships qualify; retired shared
card/text/header/icon/control/volume sidecar values do not.

## Actions / interaction

QML emits semantic actions. Python resolves admission and executes/persists business behavior. No backend,
URL policy, auth, cache mutation or Settings persistence in QML.

## Update cost

Do not add Python callback per physical frame for static content, QML provider timer, hidden always-running
animation, full component rebuild for ordinary property change, unchanged-image upload, static-widget custom-
GL frame demand, or eager inactive-family runtime imports.

## Retirement

After family GREEN under current audit policy, caller-proof and delete old QWidget pixels promptly. Git is
historical visual reference.
