# H5c Performance / Pointer / Wake / Readiness Checkpoint — R5 (Outside Codex)

Date: 2026-08-31  
Status: **IMPLEMENTED / SOURCE-ONLY GREEN / AWAITING PHYSICAL VALIDATION**  
Authority: `Current_Plan.md` owns sequence. This document records the bounded R5 repair slice and its falsifiers.

## 1. Evidence admitted from the post-R4 run

The R4 operator run changed three performance questions from suspicion into concrete repair targets.

### Cursor Halo

- With retained Cursor Halo admitted, the slightest physical mouse movement devastates Visualizer presentation FPS.
- While the retained context menu is open, Halo is intentionally suppressed; moving the ordinary native cursor does **not** reproduce the FPS collapse.
- The operator also observes the native cursor and cursor-shaped Halo simultaneously.
- Source matched that control experiment: every mouse move crossed `QQuickWindow -> Python signal/QPointF -> QuickAuxiliaryController state publication -> QuickSceneController root-property publication`, while restarting a Python inactivity timer. Pointer position was being treated as application state at mouse-poll rate.

**Conclusion:** ordinary pointer ingress is not the demonstrated offender; the Halo's Python/state-bridge presentation architecture is.

### Bubble tall/wide comparison

New canonical, wide and tall screenshots physically reject the R4 compact-source repair as sufficient. The tall viewport is the clear visual outlier: it contains very large, dense, overlapping ripple structures while comparable wide/canonical views remain materially cleaner.

R4 correctly made the three stored trail **source centres** baseline-pixel authoritative when rendered. It did not make the ripple field emitted by each source baseline-pixel authoritative. The shader still derived ripple radius/cap/ring spacing from current-height-normalized geometry, so a tall card could keep compact source centres while each source rendered a much larger differently-aged wake structure.

**Conclusion:** preserve simulation/history and Bubble-head magnitude; repair the complete Quick wake presentation footprint instead.

### Natural transition / readiness

The new origin-aware logs show timer and manual Next enter the same `_show_next_image()` path, so there is no source-proven second natural-transition renderer. They also expose a separate lifecycle defect after Settings/CUSTOM runtime replacement:

- healthy exact-next prefetch scheduling/protection is present before recreation;
- after replacement, regular prefetch scheduling can disappear;
- cache misses and ImageWorker display prescales then rise into roughly the 200–500 ms range;
- a first-image completion can attempt prefetch while another display still owns pending image/transition batch work;
- direct replacement first-frame publication does not necessarily produce a later transition-complete event that rescues that lost attempt.

**Conclusion:** replacement runtime readiness needs a generation-fenced reseed through the existing prefetch owner. The residual operator-observed natural-vs-manual FPS delta remains a separate physical falsifier after cache readiness is healthy.

### GC remains an independent multiplicative axis

R4 `RuntimeGCPolicy` recorded four generation-2 pauses in this run at approximately 99.8, 118.6, 119.9 and 134.2 ms; one collected zero objects. The five-minute policy summary recorded `4754` gen-0, `226` gen-1 and `4` gen-2 collections. Because R5 removes a demonstrated mouse-poll-rate Python allocation/publication path, do **not** retune GC thresholds in the same slice and lose attribution. Re-measure GC count/max-pause/memory after R5 first.

## 2. R5 implementation

### 2.1 Cursor Halo: high-rate presentation stays in retained QML

Changed ownership:

```text
QuickInputState / Python
    -> semantic Halo admission / suppression / shape only

DisplayScene passive HoverHandler
    -> live pointer position
    -> native-cursor treatment
    -> retained CursorHalo item
        -> 2 s motion-inactivity Timer
```

Removed from the high-rate path:

- `QuickDisplayWindow.pointer_position_changed`;
- `QuickAuxiliaryController.update_halo_pointer`;
- Python `QPointF` copies for Halo motion;
- Python Halo inactivity `QTimer`;
- `haloX` / `haloY` root `setProperty()` churn;
- whole auxiliary-state republication on every physical mouse movement.

The retained QML handler is presentation-only/passive; Python remains the semantic input/admission owner. No mouse throttling, polling loop, new window or second semantic input owner was added.

Pointer visibility is now one coherent treatment:

- Halo admitted -> retained scene explicitly requests `Qt.BlankCursor`;
- intentional Halo suppression for retained context menu -> retained scene explicitly requests `Qt.ArrowCursor`;
- ordinary non-interaction screensaver state retains the window's existing blank-cursor policy.

O-037 is implementation-closed but still requires a physical cursor check.

### 2.2 Bubble: complete wake footprint uses authored-pixel authority

Quick layout now resolves two independent transfers:

- `trail_axis_scale`: existing R4 source-centre transfer;
- `trail_radial_scale = min(1, baseline_height / current_height)`: complete wake radial transfer.

The Quick shader branch applies the radial transfer to:

- ripple radius / Bubble-relative wake radius;
- maximum ripple radius cap;
- normalized ring frequency, reciprocally, so physical ring spacing remains stable;
- centre fade derived from the wake radius.

The legacy shader branch explicitly uses identity transfer because the legacy compositor does not upload these Quick-only uniforms. Bubble simulation, trail history, active Bubble population, head radius/reactivity, logical cadence and BTF timing are unchanged. Bubble Ghost/Decay remains a separate open product contract.

The R4 falsifier was strengthened: source-centre invariance alone can no longer pass. The contract now checks source displacement, ripple cap, ring spacing and representative ripple radius in physical pixels at canonical, wide, tall, `2x2`, and approximately `1.724x2.914`.

### 2.3 Runtime replacement: reseed the existing exact-next prefetch owner

`authoritative_first_frames_ready` is now the deterministic replacement-runtime seam. For non-cold-start generations it asks the existing image pipeline to reseed prefetch through one shared deferred-resume helper.

The helper:

- captures runtime generation/display ownership through the existing `_schedule_engine_delay` fence;
- rechecks only while concrete transition/image work or the existing post-transition cooldown prevents the pass;
- reuses the existing `_prefetch_resume_scheduled` cardinality bit;
- ultimately calls the existing `schedule_prefetch(engine)` owner;
- creates no cache owner, poller or recurring cadence.

`notify_transition_complete()` now uses the same deferred-resume helper, preserving one implementation for the existing cooldown path and the new replacement-readiness path.

Under `--perf`, replacement readiness logs `[PERF] [PREFETCH] runtime_ready_reseed generation=...`, making the new seam directly falsifiable.

## 3. Source-only validation

The checkpoint environment does not contain the project PySide6 runtime, so no physical/QML runtime claim is made here.

Focused source-only contracts:

```text
python -m pytest -q \
  tests/test_runtime_perf_policy_contracts.py \
  tests/test_visualizer_viewport_scaling_contracts.py
```

Result: **22 passed**.

The new contracts specifically prove in source that:

- mouse-poll-rate Halo coordinates no longer cross Python auxiliary state;
- retained QML owns pointer position and 2 s inactivity;
- one native-cursor treatment is encoded for Halo versus context-menu admission;
- replacement first frames reseed only the existing generation-fenced prefetch owner;
- the complete Bubble wake footprint, not merely source centres, is baseline-pixel authoritative across the required viewport matrix.

Changed Python files also pass `py_compile` in this checkpoint environment.

## 4. Required physical validation for the next run

Run with `--perf`; do not close the following gates from source-only evidence.

1. **Halo performance/control:** with Bubble or another visibly expensive mode active, move the mouse continuously with Halo admitted. Visualizer FPS must no longer collapse merely from pointer motion. Open the retained context menu and repeat as a control.
2. **One pointer:** Halo admitted must show the Halo without a native cursor. Context menu must suppress Halo and show exactly one usable ordinary cursor. Check dismissal/restoration and Ctrl/interaction-mode entry/exit.
3. **Bubble tall falsifier:** compare canonical, wide, tall, `2x2`, and approximately `1.724x2.914`. Tall must no longer multiply the complete ripple/wake footprint. Head size/reactivity and accepted outline thickness must remain intact.
4. **Replacement readiness:** enter/leave Settings and CUSTOM/edit flows, then let several natural timer transitions occur. Look for `runtime_ready_reseed`, resumed `[PREFETCH] scheduled ... protected_immediate=...`, and display consumption from `scaled_cache` rather than repeated ImageWorker prescale.
5. **Natural versus manual:** only after equivalent display-ready cache health, compare equivalent transition types under natural timer and manual Next. The previously observed natural-only ~8 FPS extra loss remains OPEN if it survives this controlled condition.
6. **GC:** compare gen-0/gen-1/gen-2 counts, max gen-2 pause, zero-object deep collections and memory growth against R4. R5 may reduce Python allocation pressure through the Halo repair, but that is a hypothesis until measured.

## 5. Deliberately still open

- GC policy/retained allocation pressure after R5 evidence; do not hide pauses by lowering visualizer cadence.
- Residual natural-vs-manual presentation difference after equivalent cache readiness.
- Full-screen transition rendering cost itself, separately from preparation/readiness.
- High-priority event-driven Media migration and its Windows reality harness; no silent high-frequency polling fallback.
- Bubble Ghost/Decay historical/product contract.

These remain explicit in `Current_Plan.md`; R5 is a safe bounded checkpoint, not a declaration that global presentation performance is solved.
