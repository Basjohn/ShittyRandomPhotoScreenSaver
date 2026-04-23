# Project Overview

Last updated: 2026-04-23

This is the top-level orientation for SRPSS documentation.

## What SRPSS Is
SRPSS is a Windows screensaver/media runtime with:
- image-source orchestration,
- GL transition/rendering pipeline,
- overlay widget system,
- settings architecture built for durability and migration.

## Documentation Boundaries
- `Spec.md`: architecture contracts and behavior rules.
- `Index.md`: where code lives and who owns what.
- `Current_Plan.md`: active work only.
- `Docs/Historical_Bugs.md`: dated bug narratives and lessons.
- `Docs/Visualizer_Change_Checklist.md`: required change sweep for visualizer settings.

## Core Engineering Principles
- Centralized manager ownership for threading/resource/settings/animation.
- Mode isolation with explicit shared seams.
- Runtime correctness over temporary compatibility shortcuts.
- Tests are required but visual/runtime behavior still needs runtime validation when the symptom is visual/timing-sensitive.

## Key Runtime Areas
- Engine/display lifecycle: `engine/`, `rendering/`.
- Settings and schema: `core/settings/`.
- Widgets and overlays: `widgets/`, `rendering/widget_manager.py`.
- Visualizer system: `widgets/spotify_visualizer*`, `core/settings/visualizer_*`.
- Source ingestion: `sources/rss/`.

## How to Navigate
1. Read `Spec.md` for current contract.
2. Use `Index.md` to locate ownership boundaries.
3. Use focused docs under `Docs/` for defaults, test policy, and visualizer specifics.
4. Use `Docs/Historical_Bugs.md` before reworking fragile areas.
