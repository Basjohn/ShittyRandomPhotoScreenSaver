# 09 — Ordinary Widget Quick Presentation Bridge

Status: **Phase-F current state/model/action/asset bridge**  
Last updated: 2026-08-24

## Destination

```text
provider/backend/runtime owner
-> normalized current state
-> stable presentation model
-> family Quick component
-> shared retained shell
```

Quick consumes presentation state and emits semantic actions.

Quick does not own credentials, providers, cache policy, refresh cadence, SettingsManager, persistence
or business side effects.

## Family component registry

The first family may establish a small static presentation registry:

```text
family id
QML component path
expected presentation model kind
```

Use the existing process-level Quick engine/component cache.

Do not put family `if/elif` dispatch into `DisplayScene.qml`, `QuickSceneController` or
`WidgetRuntimeManager`.

## Presentation models

Prefer stable explicit models/properties.

Clock candidate:

```text
timeText
calendar text/lines
timezoneText
displayMode
hour/minute/second angles
showSeconds
showNumerals
showSeparator
style
geometryVariant
```

Do not expose Clock QWidget, SettingsManager, ticker/provider objects or raw CUSTOM persistence to QML.

## Lists

Reddit/Gmail/Steam repeating content uses bounded stable semantic IDs and coherent update transactions.

Correct bounded resets are fine; do not invent heavyweight generic diff frameworks without need.

## State atomicity

Publish coherent current state. Avoid new title + old artwork + new playback + old provider mixtures.

Identical state should be a no-op where practical.

## Actions

```text
QML semantic action
-> Python action owner
-> business/external side effect
-> new current state
-> presentation model
```

QML does not persist settings or directly call providers.

## Dynamic images

```text
provider/worker
-> bytes or decoded QImage + stable identity
-> shared presentation image seam
-> retained Image/item
```

No QPixmap worker transport, base64 churn, tempfile-per-update or unchanged reupload.

Do not build dynamic-artwork infrastructure during Clock. Media is the likely first serious consumer.

## Geometry variants

Outer geometry remains session/Python-owned.

Known:

```text
Clock:
  digital
  analog
```

Phase F establishes semantics; Phase G owns final CUSTOM session persistence.

## Style bridge

QML receives final presentation values, not persistence semantics.

Conceptual:

```text
cardShadowEnabled/Alpha/Blur/OffsetX/Y
textShadowEnabled/Alpha/OffsetX/Y
headerShadowEnabled
```

Direction token and Extra Offset semantics remain Python-side.

No Text Blur.

No `shadowtuning.json`, legacy tuning dictionary or fallback constants table.

### Family-authored distinction

A family baseline must be deliberately authored by the destination style/family contract or represent a
visual relationship that family historically owned independently.

A global sidecar value does not become an authored family baseline by being copied into a family module.

## Temporary adapters

Allowed when they copy/normalize already-proven authored/logical results into a detached destination
contract and avoid needless reimplementation.

Forbidden when they:

- preserve old QWidget pixels as fallback;
- screenshot old presentation;
- make neutral runtime depend on old presenter;
- create another settings/style authority;
- exist only to keep the intermediate app visually usable.

Every adapter needs a retirement owner.

## Update/lifecycle

Static UI is event/state driven.

Presentation recreation rebinds current model without provider recreation.

Stale generation cannot update replacement item.

After family GREEN, old pixel presenter is deleted after caller proof.
