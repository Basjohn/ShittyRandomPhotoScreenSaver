# Project Overview

Last updated: 2026-08-18

## What SRPSS Is

SRPSS is a Windows screensaver/media runtime with multi-display image presentation,
accelerated transitions, a high-fidelity Spotify visualizer, configurable overlay widgets,
durable settings/profiles and Normal/Media Center runtime variants.

## Read Order

Do **not** read the whole documentation tree for every task.

For active engineering work:

1. Read the user's current instruction and exact current `main` source first.
2. Read `Current_Plan.md` when the task belongs to active work.
3. Use `Index.md` / `Docs/Contracts.md` to identify the current owner.
4. Read `Docs/Guardrails.md` plus the one focused guardrail for the subsystem.
5. Read `Spec.md` / focused architecture docs when a stable contract is involved.
6. Read the relevant current phase report only for accepted evidence and its limits.
7. Read historical bug/older phase records only for regression lessons or negative controls.

**Phase reports and historical bug records are commit/date-scoped evidence. Their class names,
owner maps and implementation diagrams do not become current architecture merely because they
are detailed.** Exact current `main` and the active plan win.

## Current Presentation Architecture

- Accelerated presentation is required for the modern compositor/visualizer runtime.
- Each active physical display owns one `GLCompositorWidget` presentation surface.
- The surface is `ExternalOpenGLRhiWidget` / `QRhiWidget.Api.OpenGL` using the top-level
  OpenGL QRhi.
- Existing PyOpenGL transition/visualizer renderers run inside the QRhi external-content pass.
- The visualizer is a compositor layer, not a second presented `QOpenGLWidget`/`QRhiWidget`.
- `SpotifyBarsGLOverlay` remains a logical state/geometry/GL-resource owner and never shows or
  paints as its own surface.
- Visualizer source/simulation cadence remains independent from physical presentation.
- One display-local presentation strategy owns physical frame opportunities for transition and
  visualizer liveness; paint acknowledgement is not admission.

See `Docs/Compositor_Architecture.md` and `Docs/Guardrails/Visualizer_Presentation.md`.

## Core Engineering Priorities

When goals conflict:

1. visualizer fidelity and reactivity;
2. lifecycle and GL safety;
3. frame pacing/perceived smoothness;
4. correct multi-display behaviour;
5. bounded RAM/VRAM;
6. CPU/task efficiency;
7. average FPS;
8. architecture elegance.

## Evidence And Repository Stability

Current `main` is implementation authority. Historical commits are forensic references or
negative controls only.

Runtime evidence belongs under `logs/evidence_chest/` when intentionally preserved.

Existing files/documents are updated in place. Do not rename or move an existing path unless
the user explicitly requests that exact rename/move.
