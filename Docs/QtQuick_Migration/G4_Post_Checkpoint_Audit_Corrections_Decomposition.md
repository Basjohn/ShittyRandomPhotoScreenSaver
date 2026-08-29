# G4 Post-Checkpoint Audit Corrections — Technical Decomposition

Status: **COMPLETE — all corrections (A committed/override ownership, B domain retry clamp, C contraction lifecycle,
D specular audit) plus the wording cleanup are landed, test-gated and pushed. Baseline byte-identical; goldens green
without retuning. Deterministic G4 closed; only the post-H eyes-on gate remains.**  
Basis: G4 core viewport-extent work is pushed; independent audit found bounded lifecycle/spatial omissions.  
Work admission: `Current_Plan.md`

This document owns only the post-checkpoint G4 correction batch. It is not permission to redesign CUSTOM, change Bubble
personality, revisit accepted BTF tuning, or start H.

The existing scale/extent architecture remains correct:

```text
wheel/corners -> uniform_visual_scale
edges         -> viewport_extent
```

and Bubble still consumes viewport extent as latest spatial configuration on its existing authored cadence.

## 1. Correction A — committed extent vs temporary CUSTOM working extent

### Problem

The current live route correctly allows a retained CUSTOM edge drag to publish `current_viewport_extent` toward the logical
Bubble runtime. However, the current seam conceptually conflates two different states:

```text
ordinary committed presentation viewport extent
CUSTOM temporary working viewport extent
```

They need deterministic precedence, especially at end-CUSTOM.

A naive clear path of:

```text
no active CUSTOM session
-> publish None
-> runtime resolves canonical (420,280)
```

is wrong for a saved non-baseline viewport. Example:

```text
committed 420x280
-> enter CUSTOM
-> edge-resize to 630x280
-> Save
-> committed layout is now 630x280
-> end CUSTOM
-> logical Bubble must remain 630x280
```

Likewise Cancel must restore the pre-edit committed extent rather than whatever transient working value was last pushed.

### Preferred ownership model

Do not add a third geometry authority. Prefer making the existing runtime-controller viewport configuration distinguish:

```text
committed_presentation_extent
optional_custom_working_extent_override

effective_extent = custom override when active
                   otherwise committed presentation extent
```

Equivalent implementation is acceptable if exact source has a smaller existing seam, but the two concepts must not remain
one mutable scalar that unrelated publishers overwrite.

Required precedence:

```text
ordinary runtime
    -> current committed presentation extent

CUSTOM active
    -> current working session extent overrides committed extent

CUSTOM Save
    -> persistence/committed presentation becomes the new committed extent
    -> CUSTOM override retires
    -> effective extent remains the newly committed value

CUSTOM Cancel
    -> committed presentation never changes
    -> CUSTOM override retires
    -> effective extent returns to the pre-edit committed value

canonical committed layout
    -> effective extent is canonical (420,280)
```

### Writer-conflict rule

An ordinary presentation publication must **not** overwrite a live CUSTOM working override while edit mode is active.
Likewise, retiring CUSTOM must not manufacture canonical baseline just because the edit session no longer exists.

Trace the current interaction between:

- `rendering/quick/scene_controller.py`
  - CUSTOM session bind/sync/clear;
  - viewport-config sink publication;
  - ordinary `ResolvedVisualizerPresentation` application.
- `widgets/spotify_visualizer/runtime_controller.py`
  - `presentation_viewport_extent`;
  - explicit viewport setter/override seam;
  - `commit_presentation_metrics()` / render publication.
- `rendering/custom_layout_manager.py`
  - Save/Cancel/committed payload lifecycle.

Do not make `QuickSceneController` a second persistence owner merely to remember the value.

### Required tests

Use actual owner-shaped tests rather than only testing a list `.append` sink.

Cover at minimum:

1. canonical committed -> CUSTOM wide -> Cancel -> effective canonical;
2. committed wide -> CUSTOM taller -> Cancel -> effective original wide;
3. canonical committed -> CUSTOM wide -> Save -> effective saved wide after session clear;
4. committed wide -> CUSTOM canonical -> Save -> effective canonical and no stale persisted key;
5. while CUSTOM is active, an ordinary committed-presentation publication cannot erase the working override;
6. geometry changes coalesce as state and create no Bubble step/timer/event;
7. generation/session retirement clears transient override without losing the correct committed value.

If current Save ordering does not publish the newly committed `ResolvedVisualizerPresentation` before the CUSTOM override is
retired, correct that at the existing commit/presentation seam. Do not solve it by retaining a dead session object as hidden
truth.

## 2. Correction B — remaining hardcoded overlap-retry unit-square clamp

### Problem

Bubble reflow generalized the major spatial bounds, but `_spawn_bubble_at()` still contains overlap-retry jitter clamping in
legacy unit-square coordinates:

```text
x -> [-0.25, 1.25]
y -> [-0.25, 1.25]
```

That is correct only for the baseline `1 x 1` world. In a wide/tall logical domain, a retry spawned in the newly available
region can be pulled back toward the old unit box.

### Required correction

Preserve the exact baseline behavior. For non-baseline domains, the retry bounds must use the actual logical world while
keeping the same logical off-world allowance, conceptually:

```text
x -> [-0.25, domain_w + 0.25]
y -> [-0.25, domain_h + 0.25]
```

Do not scale the `0.25` margin by aspect unless exact source proves that margin is a percentage rather than a baseline-world
distance. The current Bubble motion/radius/collision metric treats these authored constants as logical units.

Do not mechanically replace unrelated `1.0`/`1.25` values elsewhere. Audit literals by meaning.

### Required tests

- baseline forced-overlap retry produces exactly the legacy bounded result/random draw behavior;
- a forced-overlap retry in a wide domain may remain beyond logical `x=1.25` when valid;
- a forced-overlap retry in a tall domain may remain beyond logical `y=1.25` when valid;
- no change to authored counts or spawn RNG sequence on canonical baseline.

## 3. Correction C — contraction lifecycle for `reaches_surface=False`

### Problem

The new domain-aware head/tail exit path naturally reconciles surface-reaching bubbles when a viewport contracts. A
`reaches_surface=False` bubble is governed primarily by its age/pop lifecycle. If contraction places such a bubble outside
the new domain, it can remain invisible while still consuming an authored population slot until its ordinary lifetime
expires.

This must be explicit rather than accidentally untested.

### Required behavior

On a **domain contraction event**, a bubble which is now materially outside the new logical bounds must enter an existing
retirement lifecycle promptly:

- surface-reaching bubbles keep the existing exit/trail-drain path;
- non-surface bubbles should enter the existing pop/fade/death path (or a demonstrably equivalent existing lifecycle), so an
  invisible off-domain bubble does not consume population for seconds;
- do not teleport it back into view;
- do not percentage-rescale the field;
- do not change normal lifetime/pop behavior for bubbles which remain inside the contracted domain.

Use the previous domain dimensions to detect an actual contraction if needed; do not repeatedly re-trigger lifecycle merely
because a bubble is naturally a little off-card during ordinary entry/exit movement.

### Required tests

- wide -> baseline contraction with a surface-reaching out-of-domain bubble follows exit/trail drain;
- wide -> baseline contraction with a non-surface out-of-domain bubble enters bounded pop/death reconciliation;
- interior bubbles retain logical coordinates apart from ordinary simulation movement;
- target population is able to replenish after retired off-domain bubbles leave;
- baseline steady-state behavior remains unchanged.

## 4. Correction D — specular offset coordinate-space audit

### Problem

Bubble render projection now normalizes logical head/trail positions and radius for non-baseline domains. `spec_ox` and
`spec_oy` are still passed through unchanged. Their names/comments describe positional mutations, so their coordinate space
must be proven rather than assumed.

### Audit route

Trace the values from:

```text
BubbleState.spec_ox / spec_oy
-> snapshot extra payload
-> immutable Bubble frame/render payload
-> Quick Bubble implementation / shader math
```

Determine whether they are:

1. **viewport-normalized positional offsets** — then non-baseline projection must preserve physical displacement consistently
   with the relevant axis/domain; or
2. **dimensionless/local bubble-space mutations** — then they should remain unchanged and a test/comment must state that
   their local-space meaning is intentionally aspect-independent.

Do not change them merely because their names contain `x`/`y`. Let the shader math decide the coordinate contract.

### Required bars

- canonical baseline payload remains exact;
- wide/tall aspect does not create an unintended specular displacement stretch;
- no shader redesign or new material path;
- specular size mutation remains separate from position/radius authority.

If the values are local/dimensionless and no change is needed, close this item with a deterministic test or source-level
contract assertion rather than leaving it as oral knowledge.

## 5. Wording correction — no “baseline density” claim

The viewport reflow deliberately preserves:

```text
bubble_big_count
bubble_small_count
MAX_BUBBLES
```

A larger world therefore has lower particle density at the same authored counts. Remove comments/docstrings/tests which say
that Bubble “fills the extra space at baseline density.” Correct wording is closer to:

```text
the logical world expands while authored population and Bubble personality remain unchanged
```

Do not respond to this wording correction by scaling counts with area.

## 6. Baseline/BTF protection

The correction batch must not alter the accepted canonical Bubble path as collateral damage.

Hard gate:

```text
viewport extent absent
viewport extent None
viewport extent explicit (420,280)
```

must continue to resolve to the same accepted baseline simulation/snapshot behavior required by existing BTF/replay/golden
coverage.

Do not:

- regenerate a golden because a baseline result changed;
- loosen cadence/timing thresholds to make the correction pass;
- retune speed, bounce, collision, drift, pulse, trail, promotion, overdrive or smoothing;
- scale particle counts by viewport area;
- change the shader into anisotropic final-pixel stretching;
- introduce another Bubble clock or geometry timer.

If baseline changes, treat it as a defect in the correction until exact evidence proves otherwise.

## 7. Focused correction order

Recommended order:

1. fix committed-vs-CUSTOM viewport ownership/precedence and tests;
2. fix the overlap-retry domain clamp and tests;
3. add contraction lifecycle handling/tests for non-surface bubbles;
4. audit/resolve specular offset coordinate space;
5. remove “baseline density” wording;
6. run focused G4 manager/session/overlay/config-route/Bubble tests;
7. run the established Bubble BTF/cadence/replay/reactivity/transport regression bar;
8. self-audit diff for any tuning/golden/count changes;
9. commit/push the G4 correction checkpoint;
10. mark G4 deterministic implementation complete / physical acceptance deferred, then continue directly into G7.

Do not stop for independent audit after this correction checkpoint. `Current_Plan.md` owns the G-wide audit policy: the
independent audit stop occurs only after G4 corrections, G7 and G8 are all GREEN and checkpointed.

## 8. Correction GREEN definition

This audit batch is GREEN when:

- live CUSTOM extent has explicit precedence over committed extent only while CUSTOM is active;
- Save and Cancel retire the temporary override to the correct committed extent;
- no-session runtime never means “canonical” unless canonical is actually committed;
- ordinary presentation publication cannot fight the live CUSTOM override;
- Bubble overlap retry respects non-baseline domain bounds while canonical remains exact;
- contraction deterministically retires newly off-domain non-surface bubbles without rescaling the field;
- specular mutation coordinate semantics are proven and corrected if required;
- authored counts remain unchanged by extent;
- no “baseline density” promise remains;
- BTF/cadence/replay/golden baseline bars remain green without golden/threshold retuning;
- one retained scene/item/render owner and one authored Bubble clock remain intact.

Physical appearance is still deferred until the Quick production route exists. This GREEN definition closes deterministic
G4 only; it does not fabricate the post-H eyes-on acceptance gate.
