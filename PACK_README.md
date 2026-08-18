# SRPSS Documentation Reconciliation Pack — 2026-08-18 v2

This pack reconciles documentation with the landed OpenGL-QRhi / single-surface presentation
architecture and **also replaces `Current_Plan.md` and `Future_Cleanup.md`** so the next Opus session
can use a short task prompt instead of reconstructing three days of chat archaeology.

Generated against current `main` at:

```text
b5ff451efd452780dc4b87dbc1f64d539ff4e6d3
P2-CARD-GL fix - card region state boundary and card texture lifecycle
```

The two accepted installed runs after that commit are summarized in the replacement Current Plan.

Delete this document once you have read it.

## What changed conceptually

- one accelerated OpenGL QRhi compositor surface per physical display is **current**, not future;
- visualizer/card pixels render inside that compositor;
- `SpotifyBarsGLOverlay` is a logical/geometry/GL-resource owner, not a presented surface;
- the display compositor owns physical presentation; visualizer logical/source cadence remains
  separate;
- AdaptiveTimer is forbidden as a visualizer simulation/second-surface hack, but the compositor's
  own presentation strategy is allowed to present its one scene while visualizer liveness is active;
- paint acknowledgement / pending-until-paint admission remains forbidden;
- hardware acceleration is required; no CPU visualizer fallback;
- CUSTOM edit must snapshot compositor-owned pixels rather than an obsolete visualizer framebuffer;
- P5 physical monitor topology/wake lifecycle remains mandatory and is preserved in detail.

## Intentional pruning

The old roadmap `00`-`06` live-planning/architecture documents and its JSON manifest are deleted
rather than maintained in parallel. Their current useful content now has one owner.

Phase reports are **kept** as historical evidence and explicitly marked as checkpoint-scoped.
