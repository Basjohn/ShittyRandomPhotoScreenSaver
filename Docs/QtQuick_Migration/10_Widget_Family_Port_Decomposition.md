# 10 — Ordinary Widget Family Port Decomposition

Status: **Phase F ACTIVE — F1–F5 CLOSED; F6 Gmail ACTIVE**
Last updated: 2026-08-27

This owns Phase-F family decomposition, not closed implementation narrative. `Current_Plan.md` owns exact
work admission.

## Mission / sequence

```text
neutral runtime/backend/model -> stable presentation model -> retained family QML
-> OverlayWidget/shared primitives -> one display QQuickWindow
```

```text
F1 Clock / Clock2 / Clock3                     CLOSED
F2 Weather                                     CLOSED
F3 Media core                                  CLOSED
F4 Media controls / volume / mute / progress   CLOSED
F5 Reddit / Reddit2                            CLOSED
F6 Gmail                                       ACTIVE / PARTIAL
F7 Achievement Pulse
F8 Abandonment Issues
```

Family retirement: inspect old reference -> reuse/extract neutral logic -> retained Quick family -> focused
+ eyes-on proof -> GREEN under current audit policy -> caller proof -> delete old family pixels/tests -> next.
No completed family fallback to H/I.

Common rules: no QWidget effect/shadow-fade choreography; root fade; QML no provider/cache/auth/persistence/
cadence; common Quick imports family-runtime dormant; preserve independently-authored family behavior; do
not copy retired tuning as family-authored; add shared primitive only when active family earns it.

## Closed families

F1 Clock proved shared GlobalClockTicker, stable independent Clock models, shared process engine/per-display
host, canonical shadow style, exact digital/analogue geometry, separator and retained analogue special
shadows. Old Clock pixels/tests deleted; permanent shadow contract doc 11.

F2 Weather keeps provider/cache/cadence/retry/request generations in WeatherRuntimeService with retained
model/QML + real manager/host proof. Old pixels deleted.

F3/F4 Media: one retained model/item covers core+controls+progress+app volume+system mute. Existing shared
Media/volume/mute owners remain business authorities; process-engine artwork provider; semantic seek uses
accepted playback state truth; soft glow landed. Old Media pixels/hit routing deleted; temporary non-painting
Media anchor remains only for old physical-host/Visualizer relationships until H.

F5 Reddit/Reddit2: one retained family component; independent stable model/runtime per configured member;
shared rate-limit policy; old pixels/caches/hit/hover presentation deleted.

Integrated F2–F5 independent review GREEN; see current audit under `Docs/audits/`.

## F6 Gmail — ACTIVE

Preserve existing shared Gmail backend/runtime owner.

Required retained product behavior: stable bounded message/thread identity, sender/subject/date cleanup and
grouping, loading/ready/cached/error/auth/empty, unread/read styling and envelope/header behavior, configured
capacity/dynamic height, explicit refresh and blank-space double-click refresh, current three-dot popup action
menu with icons, semantic open/auth/refresh/read-unread/archive/spam/delete, notification/sound Python-owned.

### Retained presentation — GREEN

- stable GmailPresentationModel + GmailRowListModel;
- GmailPresentation.qml with the old presenter as its visual/interaction oracle;
- RetainedGmailPresentation wrapper;
- semantic QML -> Python routing;
- floating three-dot popup with current icon/label identity and conditional Archive;
- popup state independent of committed row/card height and CUSTOM geometry;
- card-derived header border, real no-unread desaturation and blank-space double-click refresh;
- accepted-row dynamic height and retained item/model/list-model/engine identity;
- static registry admission and real `QuickSceneController` host creation;
- pre-activation dormant then display-generation-bound manager-owned `GmailRuntimeService` injection;
- runtime-shaped cache/live/error-fallback/auth and semantic inbox/open/auth/message-action gates;
- practical real-OpenGL eyes-on at effective DPR 1.0, 1.5 and 2.25, including grouped long text, popup,
  no-unread desaturation, auth/error and card/no-card cases.

### Shared Quick import dormancy — GREEN

`rendering.quick.widgets` now exports only the light retained host/style records and static family metadata.
Family tests/tools import their implementation modules directly, common `scene_controller` imports only host and
registry modules, Gmail runtime snapshot annotations are type-only, and the Gmail integration package initializer
no longer eagerly imports OAuth/IMAP/backend modules. Fresh-process gates prove common Quick scene import keeps
inactive Clock, Weather, Media, Reddit and Gmail presentation/runtime/backend trees dormant. No second registry
or plugin architecture was added.

### Complete F6

Caller proof -> delete old Gmail QWidget pixel/cache/input presentation/tests while preserving neutral
runtime/backend/preparation/settings/notification/sound.

## F7 Achievement Pulse

Use existing neutral achievement/runtime/preparation foundations and immutable card view model. Preserve
cache/privacy/provenance/selection; do not duplicate Steam data ownership. Predominantly presentation mapping/
fidelity. After GREEN+caller proof delete old pixels.

## F8 Abandonment Issues

Use substantive Abandonment runtime/data path. Preserve privacy/provenance/selection; unknown/private data
explicit. No provider/cache duplication. After GREEN+caller proof delete old pixels.

Steam Journey/Progress and Friend Pulse are future product scaffolds, not migration slices. If old scaffold
presenter blocks cleanup, retire scaffold rather than manufacture parity port.

## Shared primitive admission

Shared shell/text/separator and Media artwork/control/progress already provide proven patterns. Add reusable
primitive only when active family needs it now and API is presentation-only. Do not prebuild universal widget
framework.
