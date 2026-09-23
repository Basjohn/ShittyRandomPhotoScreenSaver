# 06 — Structure, Documentation Conflicts and Expandability

**Binding:** Documentation_Maintenance.md (contract/source disagreement rules), R-77 (move/retire whole caller
transactions), R-88 (no universal QML rewrites; stable role identity), R-26/U-09/R-79/R-85 (visualizer routing and
topology behaviour must not drift during refactors).

---

## ST-01 — `DisplayManager` is a 4.9k-line owner of ~12 concerns · P3 · R1 · Risk Medium

`engine/display_manager.py` (4,881 lines, 146 methods) owns: monitor detection/topology reconciliation; Quick
runtime wiring; context-menu entry building and action routing; visualizer mode/preset requests; visualizer
admission/routing/failover/transfer/app-volume; CUSTOM session/save/cancel/layout slots; product URL routing
(Reddit/Feeds/Steam); display creation/show/cleanup; transition batch state; startup desktop seed/reveal; image
presentation/accounting; lifecycle retirement roots. Several seams are already extracted
(`rendering/quick/{visualizer_admission,visualizer_failover_lifecycle,custom_layout_owner}.py`).

**Why it matters.** Every new family action (FEEDS Custom 2–4, NEWS), transition identity or menu entry edits this
file; review and regression surface grow with each change, and ownership questions (who may mutate batch state, who
routes a URL) are answered by reading 5k lines.

**Proposal (move-only, no new lifecycle owners).** Extract pure/stateless routers that `DisplayManager` composes:
context-menu entry building + action dispatch table; product-link routing (already funnels to
`core/windows/secure_url_launcher.py`); transition batch bookkeeping (`_quick_transition_*`, `set_transition_work_pending`).
Topology, generation and visualizer lifecycle stay in `DisplayManager`. One extraction per checkpoint, each with
its existing tests passing unchanged.

**Decision (operator 2026-09-23): Park.** Do a move-only extraction only when a real change already touches a clean
ownership seam; no standalone structural slice.

---

## ST-02 — Very large single files · P3 · R1 · Risk Medium

`rendering/quick/custom_layout_owner.py` (3,413), `qml/CustomLayoutOverlay.qml` (3,262), `rendering/widget_descriptors.py`
(3,129), `rendering/quick/scene_controller.py` (2,399). **Parked** (operator 2026-09-23): no standalone rewrite (R-88:
role identity and selected-delegate observers are fragile). Split only along a seam you are already changing,
move-only, with the R-88 retained-scene tests as the gate. Two small, concrete hygiene items found while reading:

- `CustomLayoutOverlay.qml:1088-1094` and `:1127-1133` declare the same `NumberAnimation on opacity` twice on
  `childRoleLayer`.
- `_int_state` is duplicated in `render/background_node.py:141-146` and `render/image_textures.py:17-22`; several
  modules carry their own "is this QObject alive" helper. Consolidate only when those files are touched.

---

## Documentation / source contradictions

### DC-04 — Guardrail vs source conflict (tracked where it is fixed)

Guardrails §"Qt Quick presentation-clock": "never add dormant per-frame Python … on `frameSwapped`". Source keeps one
(PR-02). The guardrail is correct: fix the source, do not relax the guardrail. PR-02 is parked (≈0.5–1.8 ms/s against
fragile R-63 reveal ordering), so this stays a documented known mismatch until PR-02 reopens.

---

## Expandability observations (no action required now)

- Family QML components and descriptors are registry-driven (`rendering/quick/widgets/registry.py`), which is the
  right shape for FEEDS Custom 2–4. PW-05 lands first so new members inherit cancellable, registry-owned deadlines;
  PW-04 (whole-model reset on a changed row) is a watch item that Custom 2–4 physical testing decides.
- Transition implementations share `MeshResources`; TX-01's packing fix belongs there so every new 3D transition
  inherits it.
- Visualizer modes are descriptor-resolved lazily; VZ-01/VZ-04 add an explicit "which modes consume the waveform"
  bar, which future modes must declare.

---

## Considered and rejected (do not re-propose without new evidence)

| Idea | Why rejected |
| --- | --- |
| Raise IO pool size to relieve PW-02 | hides the ownership problem; more concurrent network work; fix the owner lane instead |
| `swapInterval=1` / VSync-driven pacing | R-86 installed A/B materially worse |
| Python display-refresh timer or `frameSwapped → requestUpdate()` | R-87 forbidden regressions |
| Global GIL switch interval change | CHK18 worse, operator felt worse |
| Remove/merge inherited GL/clip state fences | CHK24–26 closed; protected optimizations |
| Bubble renderer micro-optimization | CHK29 closed; reactive work, not waste |
| Render-thread priority boost | CHK16: not runnable starvation |
| Coalesce or defer visualizer `update()` requests | R-62/R-61B/R-27: late, flatter Bubble |
| Skip visualizer draws on non-revision frames without an offscreen cache | impossible in Qt Quick (scene redraws fully); only PR-05's architecture route could |
| Lower visualizer cadence while paused | paused idle animation is authored product behaviour (Visualizer_Presentation §10) |
| GC threshold tuning / periodic `gc.collect()` | Performance contract §P2, R-53, R-71 |
| Remove the 200 ms display transition stagger | authored visible behaviour; needs product decision |
| A parallel "last applied presentation" cache for PR-01 | U-09/R-68 single geometry authority; use the retained item's own record |
| Lazy-construct `CustomLayoutOverlay` only in Edit | already dormant (`visible: editActive`, model-driven Repeaters); R-23/R-88 Edit risk for startup-only gain |
| Replace `DisplayScene.qml` per-tick transition counters | run only during transitions and feed PERF_HUD |
| Unslice the authored-clock sleep (VZ-07) | small unmeasured gain on the protected BTF clock; parked |
| LC-01: re-freeze GC after each runtime replacement | closed 2026-09-23 (08): after a real replacement gen-2 takes 1.2 ms (11,692 unfrozen objects); the freeze pins 748 retired objects, 0 MB; the D1 soak had no gen-2 stall. Scope is only the feared post-replacement gen-2 stall — the soak did record one 19.53 ms gen-1 collection |
| PR-05: offscreen-cache the visualizer to skip repeat draws | closed 2026-09-23: 2.81% of draws in the D1 soak (1,803 of 64,150), ≈5.8 ms/s idle; would change the selected custom-render composition (Compositor_Architecture §6) |
| PW-06: persistent supervisor heartbeat thread | closed 2026-09-23: 0.31 ms per 3 s ≈ 0.1 ms/s, OS timer handles steady at ≈13–14 through the soak; replacement risks R-30 exit behaviour |
| Treat the 22:58:31 prefetch "double batch" as a defect | closed 2026-09-23: `requested=2 retained=1` near-future keys — benign lookahead catch-up |
| PR-04: move the native upload earlier in the transition | relocates the stall into the transition or stacks it on the costly start frame |
| PR-04: make every `capture_qimage` output opaque | `capture_qimage` is a generic boundary; the opacity guarantee belongs at the background processing boundary (FILL perfect-fit) |
| PW-02: run Media queries/commands on the WinRT observation lane | teardown waits 2 s on that worker; a stuck WinRT await would fail the R-53 barrier. Use a separate Media-only lane |
| PW-03: one notify signal per property across every family | churn without evidence; a few semantic epochs, Clock first, Media only if measured material |