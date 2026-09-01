# 09 — Ordinary Widget Quick Presentation Bridge

Status: **landed state/model/action/image bridge**  
Last updated: 2026-08-26

## Destination

```text
provider/backend/runtime owner
-> coherent accepted current state
-> stable presentation model
-> retained family QML
-> shared ordinary-widget host/shell
```

Quick consumes presentation state and emits semantic actions. It does not own credentials, providers, cache
policy, refresh cadence, SettingsManager, persistence or business side effects.

## Static family component registry

Registry is presentation metadata: family ID, QML filename, presentation model kind. Canonical product
membership/activation remains neutral capability catalog. No family if/elif dispatch in DisplayScene,
QuickSceneController or WidgetRuntimeManager.

Registry/package remains import-light: static metadata may load eagerly; family implementation modules are
not dragged in by common Quick scene/host import.

## Presentation models

Stable explicit QObject/list models with bounded config/style, coherent accepted revision, semantic scalar
properties, stable item/model/list-model identity and no raw SettingsManager/provider/QWidget/CUSTOM
persistence in QML.

Clock proves scalar/geometry/angle state; Weather runtime status/icon state; Media coherent metadata/control/
artwork; Reddit bounded stable rows; Gmail extends row/action pattern.

## Lists / atomicity

Repeating content uses bounded semantic IDs and coherent updates. Correct bounded resets are fine; no heavy
universal diff framework without need. Delegate index is presentation position, not identity.

Avoid mixed revisions (new title + old artwork, new provider + old capabilities). Identical state no-op where
practical. Reject stale revision/request/generation before presentation mutation.

## Actions

```text
QML semantic action
-> Python presentation/action admission
-> neutral business owner
-> accepted state
-> presentation update
```

QML does not persist settings/call providers directly. Transient visual press/menu feedback may be local;
accepted business state stays Python truth.

## Dynamic images — landed Media pattern

```text
runtime-owned decoded QImage + stable key
-> process-engine image provider
-> retained image:// identity
```

Provider retention is bounded/identity-based. No QPixmap worker transport, base64 churn, tempfile-per-update
or unchanged-image reupload. Packaged icons may use stable file identity.

## Geometry / natural size

Outer geometry Python/session-owned; family QML lays out inside assigned rect. Known variant: Clock digital/
analog. Content-driven natural/dynamic height may derive from accepted presentation state. Transient popup/
menu state must not become committed geometry. G owns final CUSTOM persistence/session semantics.

## Style bridge

QML receives final presentation values, not persistence semantics: card shadow enabled/colour/blur/signed
offset, text shadow enabled/colour/signed offset, header gates/style, family colours/geometry. Direction and
Extra Offset remains Python-side. Frame Extra Offset projects to directional card-shadow edge growth (not whole-shadow translation); Text Extra Offset remains glyph displacement. No Text Blur or hidden legacy tuning.

## Retained wrappers

Small `Retained<Family>Presentation` wrapper may create registered family item, connect semantic QML signals,
apply geometry/fade/input/config/style and register model/service retirement. It must not become second
provider/runtime owner.

## Temporary adapters

Allowed only to normalize already-proven logical/authored output into destination contract with explicit
retirement owner. Forbidden if preserving QWidget pixels as fallback, screenshotting old presentation,
making neutral runtime depend on old presenter, creating second settings/style authority or only keeping
intermediate old pixels visible.

## Update / lifecycle

Static UI is event/state driven. Presentation recreation rebinds accepted state without provider recreation.
Stale generation cannot update replacement. After family GREEN + caller proof, old pixel presenter deleted.
