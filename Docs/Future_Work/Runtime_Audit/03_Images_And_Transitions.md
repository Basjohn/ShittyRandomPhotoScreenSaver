# 03 — Images and Transitions

Owners audited: `engine/{screensaver_engine,image_pipeline,display_manager}.py`,
`rendering/quick/transitions/{controller,request_resolution,parameter_resolution,mesh_support,fracture_geometry}.py`,
`rendering/quick/transitions/implementations/*`, `rendering/quick/render/{background_node,image_textures}.py`,
`core/settings/{settings_manager,json_store}.py`.

**Binding:** Transitions.md, Transition_Change_Checklist.md, R-65 (admission before mutation), R-63, R-60, R-50,
R-51 (per-context GL ownership), Defaults_Canonical_Schema_Dedup (one canonical path per product setting).

## What is already healthy (do not re-audit)

- Image-change admission is transactional before queue/history mutation (`screensaver_engine.py:1452-1504`, R-65).
- Processing runs on COMPUTE through the ImageWorker; results publish detached `PresentationImage` state with
  generation fencing (`image_pipeline.py:1221-1580`); no GUI QPixmap round trip (R-84 repair).
- Transition runs are one-shot, monotonic, deadline-finalized by a single-shot QTimer (`transitions/controller.py`).
- Transition programs/VAOs are retained per render node and survive between runs (CHK21).

---

## Cross-reference

- PR-04 (transition-end native re-copy/re-upload) lives in 01 because its owner is the retained background node.
- Crumble complexity/debris and Melt gloss/detail strength are transition product work, owned by
  `Docs/Future_Work/Transition_Expansion.md` §Control rework, not by this audit.
