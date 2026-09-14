# R-86 — Forced VSync hypothesis for Qt Quick pacing

Status: **REJECTED / ROLLED BACK 2026-09-14**

## Symptom

A nominal 60 Hz Qt Quick display reported uneven pacing while ``frameSwapped`` counters sometimes exceeded panel refresh. Bubble and transitions both exposed the problem, so Bubble was treated as a canary rather than the owner.

## Hypothesis

Source history showed that the production Quick bootstrap inherited ``swapInterval=0`` from a pre-Qt-Quick QWidget/GL rendering decision. Qt documentation made ``swapInterval=1`` look like a plausible Quick-native correction, so a bounded production A/B was authored that changed only the Quick surface interval. Visualizer logical cadence, presets/reactivity, transition durations and shaders were not reduced.

## Installed result — hypothesis rejected

The operator tested the interval-1 build on two displays with mixed refresh rates. Performance became **significantly worse**: poorer frame pacing, poorer FPS/headroom, and ordinary interactions such as Context Menu/Edit entry became more visibly costly. This is decisive installed evidence against forcing interval 1 as SRPSS's generic Quick presentation policy.

The source was rolled back to the known-good release-era ``QUICK_SWAP_INTERVAL = 0`` behavior. Do not reopen interval 1 merely because generic Qt guidance favors synchronized presentation; SRPSS's multiple top-level Quick windows and mixed-refresh workload require installed evidence, not a single-window assumption.

## What remains useful

The investigation exposed a valid architecture question: ``QuickFramePacer`` and Qt's own multi-window render/animation scheduling may overlap. However, the pacer itself is unchanged from the first 5.0.0/5.0.1 Quick releases that performed very well, so it is not the primary fresh-regression suspect. Any future pacer/surface redesign must be a separate A/B against that known-good Quick baseline and must preserve transition/widget-animation liveness plus Visualizer freshness/reactivity.

## Guardrail

Do not carry pre-Quick assumptions forward blindly, but also do not replace a working installed Quick policy solely because documentation suggests a theoretically cleaner one. For multi-window/mixed-refresh presentation, physical operator evidence outranks a generic single-window model.
