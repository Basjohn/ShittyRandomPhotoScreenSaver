# Project Overview

Last updated: 2026-08-11

## What SRPSS Is

SRPSS is a Windows screensaver and media runtime with:

- multi-display image presentation;
- OpenGL transitions and visual effects;
- Spotify visualizers;
- configurable overlay widgets;
- durable settings, profiles, imports, and migrations;
- Normal and Media Center runtime variants.

## Documentation Read Order

Do **not** read the entire documentation tree for every task.

1. Read `Index.md` to identify the owning subsystem.
2. Read the short relevant section of `Docs/Guardrails.md`.
3. Use `Docs/Contracts.md` to find the canonical code and focused document.
4. Read `Spec.md` only when changing stable architecture or product behaviour.
5. Read `Current_Plan.md` only when working on active planned work.
6. Read focused documents only for the subsystem being changed.
7. Read `Docs/Historical_Bugs/README.md` when touching a fragile area with prior regressions.

For compositor/architecture work, also read:

- `Docs/Compositor_Architecture.md`
- `Docs/TestSuite.md`
- the relevant section of `Docs/Harness_Index.md`

## Document Roles

| File | Role |
|---|---|
| `Index.md` | Navigation and ownership map |
| `Docs/Guardrails.md` | Durable cross-cutting safety rules |
| `Docs/Contracts.md` | Fast task-to-owner routing |
| `Spec.md` | Stable architecture and behaviour contracts |
| `Current_Plan.md` | Unfinished active work only |
| `Docs/Compositor_Architecture.md` | Compositor architecture and target design |
| `Docs/TestSuite.md` | Testing levels and release bars |
| `Docs/Harness_Index.md` | Commands for recurring investigations |
| `Docs/Historical_Bugs/README.md` | Historical incident index and full standalone records |
| `Docs/Historical_Bugs.md` | Compact historical status/navigation map |
| `Docs/Documentation_Maintenance.md` | Documentation drift and size control |

## Core Engineering Priorities

When goals conflict:

1. visualizer fidelity and reactivity;
2. lifecycle and GL safety;
3. frame pacing and perceived smoothness;
4. correct multi-display behaviour;
5. bounded RAM and VRAM;
6. CPU and task efficiency;
7. average FPS;
8. code elegance.

## Current Architecture Authority

Current `main` is the implementation authority. Historical baseline/candidate branches
and commits are forensic references or negative controls only; they are not design
owners, merge targets, or implementation starting points.

Runtime evidence belongs under:

```text
logs/evidence_chest/
```

## Repository Stability Rule

Existing files and documents are updated in place.

Do not rename or move any existing file, directory, or document unless the user explicitly requests that exact rename or move.
