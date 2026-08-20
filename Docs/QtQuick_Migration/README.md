# Qt Quick Production Migration — Technical Decomposition Index

Status: subordinate technical notes for `Current_Plan.md`
Last updated: 2026-08-20

These documents are **not independent plans**.

Sequence and work admission come only from:

```text
Current_Plan.md
```

Deferred deletion/accounting comes from:

```text
Future_Cleanup.md
```

## Documents

| File | Purpose |
|---|---|
| `01_Runtime_Host_Lifecycle.md` | QQuickWindow/runtime owner, display topology, lifecycle, input seams |
| `02_Scene_Renderer_Transitions.md` | QSGRenderNode/OpenGL scene, image/texture ownership, transitions, frame pacing |
| `03_Visualizer.md` | logical/runtime split, immutable render snapshots, five-mode Quick rendering, BTF |
| `04_Widget_Runtime_Presentation.md` | widget manager/model split, retained Quick components, shadows, family migration |
| `05_Custom_Layout_Input_Interaction.md` | CUSTOM Save/Cancel, edit overlays, cross-monitor transfer, interaction/context |
| `06_Build_Tooling_Validation.md` | Nuitka/QML packaging, tools, tests, compiled/runtime/perf gates |

## Off-rails rule

If a document suggests work that is not the active slice in `Current_Plan.md`, do not perform it yet.

If exact current source invalidates a technical assumption, update the smallest affected
decomposition and `Current_Plan.md` only if sequencing changes.

Do not create another migration roadmap document.
