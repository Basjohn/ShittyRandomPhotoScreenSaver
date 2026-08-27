# 10 — Ordinary Widget Family Port Decomposition

Status: **Phase F ACTIVE — F1–F7 CLOSED; F8 Abandonment Issues ACTIVE**
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
F6 Gmail                                       CLOSED
F7 Achievement Pulse                          CLOSED
F8 Abandonment Issues                         ACTIVE
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

F6 Gmail keeps its runtime-generation shared Gmail owner/backend and display lease, with a stable retained
model/list model, static QML family, semantic actions and real manager/host ownership. The real-OpenGL matrix
proved grouped/popup/auth/error/card variants at effective DPR 1.0, 1.5 and 2.25. Old Gmail QWidget pixels,
cache/input seams and presentation-only tests are caller-proven retired; neutral runtime/backend/preparation/
cache/settings/notification/sound contracts remain.

F7 Achievement Pulse keeps its neutral Steam runtime/preparation/cache/selection and immutable card-model
authority. One stable retained model/QML item owns accepted image sources, fields/unlocks, semantic settings/
refresh actions and family-authored capsule geometry. The threaded-OpenGL matrix proved card/no-card,
portrait/square/wide/no-art/connect/unavailable/connection-attention states at effective DPR 1.0, 1.5 and
2.25. Old Achievement QWidget factory/input/runtime bridge, scaled-image caches and painter branches are
caller-proven retired; reusable Steam models/services and the F8/shared scaffold helpers remain.

Integrated F2–F5 independent review GREEN; see current audit under `Docs/audits/`. F6 completed under the
current self-audit policy.

## F8 Abandonment Issues — ACTIVE

Use substantive Abandonment runtime/data path. Preserve privacy/provenance/selection; unknown/private data
explicit. No provider/cache duplication. After GREEN+caller proof delete old pixels.

Current admission order:

- exact runtime/data/cache/rotation/action/presentation ownership and reuse audit — GREEN;
- stable retained config/model/image projection — GREEN;
- retained card/action fidelity — GREEN;
- static registry, real manager/host injection and runtime-shaped gates — ACTIVE;
- effective-DPR 1.0/1.5/2.25 eyes-on evidence — PENDING;
- caller proof and old pixel/cache/input retirement — PENDING.

The F8 audit keeps the existing cardinality and responsibility split: one neutral runtime per enabled card/
display owns cache-first startup, refresh, cache-only rotation cadence, request/generation admission and the
prepared semantic model plus decoded source image. The retained model will own only accepted presentation
state and semantic action routing. Shared Steam reuse is deliberately bounded to stable field-list/image-source
and ordinary card-style projection plus existing Quick card/text primitives; Abandonment archive/ledger
geometry, evidence rules, desaturation and rotation policy remain family-authored. Any future shared visual
shelf primitive must expose archive-ledger versus capsule treatment explicitly rather than erasing either style.

Steam Journey/Progress and Friend Pulse are future product scaffolds, not migration slices. If old scaffold
presenter blocks cleanup, retire scaffold rather than manufacture parity port.

## Shared primitive admission

Shared shell/text/separator and Media artwork/control/progress already provide proven patterns. Add reusable
primitive only when active family needs it now and API is presentation-only. Do not prebuild universal widget
framework.
