# CUSTOM Child Placement, Header Roles, and Text-Fit Phase

Date captured: 2026-09-18
Status: **ACTIVE / foundation landed in the current checkpoint candidate.** Physical Qt validation is still required before broad rollout. Placement was pulled forward because the Abandonment/Media closeout exposed containment, reset and collision failures that could not be treated as a later cosmetic phase. Shared headers remain the next major slice.

## Why this exists

The first dense Abandonment Issues physical pass proved that child-size control is useful enough to expose the next architectural layer rather than a one-off family tweak:

- customized children must remain inside a truthful parent even when the **parent** content controls are used afterward;
- child-driven outer growth should be visible during the edit, not appear only after release;
- major children need optional **placement**, not only size, because resizing exposes authored spacing that is sensible at the default but unnecessarily rigid in CUSTOM;
- Abandonment's flavour/subtitle text should become an editable role as part of that fuller layout control;
- the shared `BrandedHeader` should be eligible as a per-widget role without forking its theme/appearance implementation;
- header placement needs deliberately strong corner/margin stickiness so free placement cannot casually produce a visibly crooked header;
- text-bearing editable roles must keep adaptive shrink/wrap behaviour. CUSTOM resizing must not turn a previously legible title into `...` truncation merely because the user narrowed its frame.

The goal is a **shared role-declared visual-layout editor**, not a second layout engine and not family-local drag code.

## 1. Preserve the existing ownership boundary

Keep the current authority chain:

```text
widget descriptor / family role declaration
        -> global CUSTOM session
        -> one shared pointer gesture owner
        -> existing size_payload.child_geometry carrier
        -> existing Save / Cancel / slots / reset / hydration
```

Do not add:

- family-local CUSTOM JSON;
- a second persistence file/root;
- a QML-owned committed rectangle;
- a placement timer or polling loop;
- a background collision scan;
- a provider/runtime wake merely because a widget is in CUSTOM;
- a second Settings authority;
- per-frame Python/QML position synchronization.

The current child-size work remains the foundation. Placement extends the same role identity and session state.

## 2. Parent containment is a hard invariant

A customized child may never become stranded outside the visible parent because a later parent-side or two-axis content resize ignored the child requirement.

The current validation fix introduces the correct primitive: while a parent is selected, the retained family reports one **transient current child-content requirement**. The shared Python owner records that requirement as the live floor for parent `content_extent` side/corner gestures. A smaller later child requirement lowers the *floor* but does not auto-collapse the parent.

Phase 2 must extend that requirement to placement as well as size:

```text
required extent = family authored/reflow requirement
                + customized child size overflow
                + customized child placement overflow
```

Rules:

- child growth/movement may request outer growth through the existing `content_extent` owner;
- the requirement may update live during the edit through event-driven retained bindings;
- shrinking/moving inward updates the transient floor but never auto-shrinks the outer card;
- parent side/diagonal controls may reclaim space only down to the current child floor;
- uniform whole-widget scale remains a different operation and scales the already-valid logical box as one unit;
- display clamping remains owned by the existing Python parent geometry owner;
- do not solve containment by clipping children or silently resetting their CUSTOM state.

Free placement uses the **real parent bounds**, not the family padding/margins, as its hard boundary. Padding and authored margins may act only as mild snap hints. A move that would cross the real parent edge is clipped there; child resize may request grow-only right/bottom parent expansion through the existing owner. Do not smuggle padding back in as a movement constraint.

## 3. Extend `child_geometry`, do not create `child_position`

The persisted role entry should evolve additively. Existing saved size-only entries must remain valid.

Conceptually:

```text
size_payload.child_geometry.<role_id> = {
    width_scale:  ...,
    height_scale: ...,
    x_offset:     ... optional,
    y_offset:     ... optional,
    anchor:       ... optional semantic anchor for roles that support it
}
```

Exact names may change during implementation, but the contract is:

- size factors remain authored-relative;
- placement is always persisted as an authored-relative normalized offset, never an absolute screen coordinate;
- while a role is still on its authored rail, family reflow may temporarily displace its retained target; on the first real free-move sample that current reflow displacement is folded once into the persisted offset and the role detaches from later sibling reflow without a visual jump;
- **parent reflow obeys the same authored/off-rail boundary:** if a child is freely placed, a later parent side-resize must reclaim/close empty space around that stable child, never keep translating the child with the parent's authored edge. Any live authored-parent displacement required for the first move must be exposed through the existing placement-compensation hook and folded exactly once;
- a role must also stop following a parent rail on an axis when the role's own resize on that axis would make admitted parent growth feed back into the same child position. Parent `content_extent` is never allowed to become a recursive child-position baseline;
- a zero-motion press/release does not fold compensation or create placement state;
- offsets are normalized against stable authored parent geometry, never raw device pixels;
- a parent `content_extent` growth must not become the next placement baseline;
- old size-only payloads imply zero authored-relative offset and no semantic anchor;
- unknown role data continues to be preserved by the existing forward-compatible mapping update path;
- user-authored CUSTOM state is never rewritten merely to adopt the new fields.

This lets ordinary family reflow continue to do useful work until the user deliberately places a role. After that first real move, the saved offset preserves the role's current visual position against its stable authored anchor and later unrelated sibling resize cannot drag it elsewhere. The compensation is folded into the existing `child_geometry` record; there is no second anchor store or absolute-position authority.

## 4. Shared gesture model for child movement

A selected child role gains a move surface distinct from its resize handle(s). Keep the current click-in model: only the selected parent exposes child chrome, and only the focused role should receive the active move affordance.

The shared owner should receive at gesture begin:

- role id;
- pointer position;
- current rendered target rectangle;
- current rendered parent/content rectangle or equivalent stable normalization reference.

Python/session then owns normalized displacement. QML may report retained geometry and map coordinates, but does not own persisted offset math.

Movement is pointer-event driven only. No idle hover scan is needed.

### Collision invariant

Declared child roles and declared fixed obstacles must not be allowed to create new committed overlap during move/resize. Existing legacy/corrupt overlap must remain escapable rather than trapping the user. Collision admission is selected-parent/Edit-only and uses the already-retained role targets; it must not become a normal-runtime scene scan. Family-authored reflow may explicitly exempt a downstream sibling during resize only while both the source reflow gate and that downstream peer remain on their authored rails, and only on the axis that the family explicitly declares. Once a role has explicit placement, it becomes an ordinary collision surface and is no longer silently displaced by later sibling resize. The shared editor also predicts that declared same-axis secondary translation before commit, clamps it against off-rail peers/fixed obstacles, and includes the predicted edge in the same live parent-growth request so indirect reflow cannot create a new overlap or a one-turn containment catch-up.

**Editable-child crossing:** move gestures may cross another declared editable child with modest resistance rather than trapping the selected role forever on one side. First contact stays hard. After 14 logical px of additional pressure into the peer, the selected role may snap to that peer's far side only if the complete occupied rectangle fits inside the real parent and does not deepen overlap with any other peer/obstacle. The active gesture then rebases transiently onto the admitted far-side coordinate, preventing the next raw pointer sample from immediately asking for the pre-pass side again; the crossing bias resets at the gesture boundary and is never persisted. The unselected peer never moves or changes persistence. Fixed family obstacles and all resize collisions stay hard. This is deliberately not a generic swap/reorder engine and introduces no second-child transaction or normal-runtime cadence.

**Global Child Collision preference:** all widgets with more than one declared editable child consume one standard circular **Enable Child Widget Collisions** preference at `widgets.global.child_collision_enabled`, surfaced only in **Widgets -> General -> Layout**. Default is OFF. Turning it off disables only editable-child peer collision admission: children may overlap and move/resize through one another directly. Parent-bound clipping/containment, fixed family obstacles, snapping, sibling/parent alignment guides, semantic header anchors and all Edit ownership rules remain active. The preference never belongs to a family mapping and never enters `child_geometry`, so Save/Cancel/Restore/layout slots do not rewrite it. An active CUSTOM session consumes Settings changes through the existing event-driven Settings notification; no timer, polling or render-cadence check is permitted. Future multi-role families inherit this global preference automatically and must not add another collision setting.

### Mild snapping for ordinary roles

Useful but intentionally gentle:

- authored anchor position;
- parent safe margins;
- parent horizontal/vertical center;
- optionally sibling role edges/centers when already available from the selected parent's retained role list.

Use a small acquisition distance and hysteresis so snapping feels like a light snag rather than magnetic rails. Reuse the existing CUSTOM guide publication concepts where practical instead of creating a parallel guide layer.

Do not run scene-wide collision/snap discovery. Only the selected parent's already-declared roles participate.

## 5. Header role: shared presentation, widget-local geometry

`BrandedHeader.qml` remains the single theming/presentation primitive. Do **not** fork `MediaHeader`, `SteamHeader`, etc. to make headers editable.

Each participating widget may expose a stable `header` child role targeting its existing `BrandedHeader` instance.

Recommended semantics:

- placement enabled;
- optional **uniform** role scale only, so logo/text/pill proportions remain intact;
- no free X/Y distortion of the header frame;
- theme, color, border, logo and text semantics stay under the existing shared header inputs;
- if a header is disabled/absent for that widget, no ghost edit target exists.

### Heavy corner stickiness

Headers are intentionally different from ordinary child movement. They should strongly prefer the four parent **margined corners**:

```text
top-left      top-right
bottom-left   bottom-right
```

Use a semantic anchor when snapped rather than merely saving the incidental pixel offset. That way a snapped header stays correctly margined when the parent later changes size.

Recommended interaction:

- larger acquisition zone than ordinary child snapping;
- hysteresis/release threshold so a snapped header does not jitter in and out of the corner;
- clear visual guide/state when a corner anchor is acquired;
- drag decisively away from the release threshold to clear the semantic anchor and return to free placement.

The corner margin comes from the family's/shared header-safe inset contract, not a hard-coded screen coordinate.

## 6. Abandonment Issues placement and shared-header proof

Abandonment is now the active dense placement proof. The current checkpoint candidate admits movement for:

1. `artwork`
2. `backlog_block`
3. `game_name`
4. `flavour_text` — the subtitle/rediscovery line beneath the game title
5. `last_visit`
6. `shelf_group`

Grouped shelves remain one group, never one persisted position per shelf. The family keeps authored dependencies only while a role remains on its authored rail; once a role has an explicit CUSTOM displacement, that displacement is respected rather than overwritten by a later unrelated sibling resize.

The same pre-rollout proof now also admits:

7. `header` — the existing shared `BrandedHeader` instance, using the semantic sticky-corner contract in §5 rather than a family-local header implementation. Header source implementation is landed; Windows/physical acceptance remains open.

## 7. Text preservation contract

Editable text frames need a non-destructive overflow policy. The current Abandonment validation exposed why: a narrowed Game Name role must not degrade to right-elided text when the content could instead shrink and/or wrap.

For title/name/metadata roles where the full string is meaningful:

1. preserve the authored preferred point size when it fits;
2. shrink toward a family-declared readable minimum;
3. where the role semantics allow it, use an additional line before giving up more size;
4. use `Text.Fit`/equivalent against both width and height for multi-line roles;
5. default to `Text.ElideNone` for these editable primary-text roles;
6. only use elision where the product deliberately defines the text as disposable/preview content.

Do not globally change `ShadowedText` defaults and accidentally rewrite every existing widget. Prove the policy on Abandonment, then either:

- reuse the same explicit bindings in Media/Pulse if only a few sites need them; or
- introduce one narrowly-scoped shared adaptive-role text primitive after at least a second family demonstrates identical semantics.

The future Media and Achievement/Friend Pulse placement passes must explicitly audit title/name/metadata fit while roles are narrowed and moved.

## 8. Settings conflict locking

CUSTOM geometry must not fight authored Settings controls.

Keep UI lock metadata in the widget descriptor/Settings layer, not inside the rendering role descriptor. Rendering should not learn Qt Widgets control attribute names.

When a widget admits placement or role scaling, extend its widget-scoped CUSTOM lock descriptor to include only controls that would otherwise author the same property, for example:

- artwork authored size/shape when artwork geometry is CUSTOM-owned;
- authored alignment/position controls if a later family exposes them and CUSTOM owns that role's placement;
- role-specific size controls when a CUSTOM role scale owns the same visible result.

Do **not** disable unrelated appearance/content controls merely because the widget has CUSTOM placement.

Steam families remain independently scoped. Editing Abandonment must not disable Achievement or Friend Pulse controls.

## 9. Reset / Save / Cancel semantics

Keep existing transaction behavior:

- Save commits size + placement through the existing CUSTOM payload;
- Cancel returns both size and placement to the last committed state;
- layout slots round-trip both through the existing `custom_layout` snapshot, with no second slot schema;
- the existing bottom-left **Restore Size** glyph is the authored-state reset for the whole widget: it restores the outer authored size/shape **and clears every descriptor-owned child size/placement override**, while preserving widget position/display;
- an interrupted child gesture must retire only transient pointer origins, never partially commit a second geometry authority;
- deleting/reverting CUSTOM for a widget returns to the canonical authored Settings layout.

A future snapped semantic header anchor is part of that same child role committed state and must therefore obey Save / Cancel / Restore Size / slots as one transaction.

## 10. Runtime-performance admission gate

This phase is allowed to be rich in **Edit mode** and must remain boring outside it.

Required steady-state result for normal runtime, including saved CUSTOM layouts:

- no new timer;
- no polling;
- no additional provider/service activation;
- no new worker/thread;
- no scene-wide collision scan;
- no pointer/hover observer left running;
- no Python publication each frame;
- no Settings reads on render cadence;
- no repeated allocation of role descriptors or role models because a saved offset exists.

Normal retained runtime should consume resolved geometry through ordinary QML bindings exactly as it consumes today's saved child size factors. A static saved `x_offset`/`y_offset` is data, not a cadence.

Edit-only movement may naturally cause QML relayout and narrow `customGeometryChanged`/CUSTOM-session updates at pointer cadence. That work must disappear when the gesture/edit overlay disappears.

Before broad rollout, audit CPU/GPU allocation, signal rate, delegate churn, provider dormancy, and render-node/effect count with Edit mode off.

## 11. Current implementation state / next order

1. **Landed in checkpoint candidate:** additive `x_offset` / `y_offset` fields inside the existing `size_payload.child_geometry` carrier; old size-only payloads remain valid.
2. **Landed:** one shared Python-owned child move gesture; selected-parent-only mild edge/centre snapping; real-parent clipping; edit-only sibling/fixed-obstacle collision admission.
3. **Landed:** Abandonment artwork, BACKLOG, Game Name, flavour text, Last Visit and grouped shelves are movable. Reflow is now authored-rail-aware so an explicitly moved role no longer drags unrelated siblings.
4. **Landed:** Media artwork, seek, volume and the **whole** transport/mute band are movable; edit mapping invalidates on nested reflow and accessory-side changes.
5. **Landed:** Restore Size clears the whole child-geometry carrier atomically with the session child cache; Cancel remains baseline restore; layout slots retain nested placement via the existing deep-copied CUSTOM root.
6. **Landed:** live child overflow uses the existing parent `content_extent` owner during pointer updates and the retained family requirement remains the transient floor for later parent content resize.
7. **Landed in the lifecycle closeout:** child resize preview + commit share one descriptor-bounded Python resolver, so raw pointer overshoot cannot create a larger provisional parent floor than the geometry that can actually commit; diagonal collision admission resolves horizontal and vertical axes independently; selection change retires prior child gestures/containment by stable session-item identity rather than relying on a QML delegate row during teardown. QML destruction remains only the selected-parent fallback for same-row Settings/role changes.
8. **Landed in the reflow-detachment checkpoint:** on-rail family displacement is snapshotted/folded exactly once on the first real move, then the role detaches to its stable authored-relative offset; a zero-motion click remains a no-op; off-rail peers lose resize-reflow collision exemption. Move and resize each use a pure shared geometry resolver so normalized math is testable without a Qt scene.
9. **Landed in the indirect-reflow collision checkpoint:** reflow exemptions are axis-specific; an on-rail peer that will be translated by an upstream resize is predicted against every non-reflow peer/fixed obstacle before commit, and the source resize is clamped at the first hard surface. The same predicted peer edge participates in immediate parent growth, so secondary reflow cannot wait a scene turn before containment catches up.
10. **Landed in the Media nested-reflow detachment checkpoint:** seek and transport no longer inherit future ancestor-band movement after explicit placement. While still on-rail, each target reports the current `Column`/band displacement as the existing first-real-move compensation; once its normalized offset becomes nonzero, the retained target binding cancels later ancestor displacement. Off-rail transport also stops qualifying as the seek-resize reflow peer. This remains one `child_geometry` authority and retained arithmetic only; no background synchronizer exists.
11. **Landed in the pre-rollout editor-polish checkpoint, still requiring Windows/PySide + physical proof:** descriptor-owned child roles now default to all four corner handles; child movement publishes visible selected-parent-only parent/sibling edge/centre guides with light acquisition + hysteresis; descriptor-gated left/right alignment flip is admitted inside the existing `child_geometry` record and proved first on Abandonment Game Name/flavour text; close/Restore chrome fades only from child gesture begin/end state using finite QML animation. No new timer/poller/provider/worker or normal-runtime scene scan was admitted.
12. **Test-red reconciliation landed:** the real Steam CUSTOM-lock registry bug is fixed by filtering synthetic widget-scoped lock descriptors against active runtime widget ids rather than the single Settings section id. Three WidgetsTab failures were stale global-revert assertions and now protect the intended widget/family-scoped revert contract instead: reverting Media leaves unrelated Visualizer/Gmail CUSTOM state intact.
13. **Still required before acceptance:** run Windows/PySide Qt tests and operator physical validation across all four child resize corners, sibling/parent guide acquisition + release hysteresis, alignment flip Save/Cancel/Restore/slot round-trip, gesture chrome fade, repeat resize/move, settings/visibility changes and parent-resize-after-child-edit. Re-test Media artwork Restore Size and apparent seek right-side spacing before introducing any Media-local reset or changing the accepted 75% authored seek baseline.
14. **Next major feature slice only after that proof:** add `header` using the existing `BrandedHeader`, semantic margined-corner anchors, strong snap + hysteresis.
15. **Broad rollout remains blocked until the header slice is also proven.** Only then roll the same placement primitive into Achievement Pulse / Friend Pulse and other dense widgets, adding roles only through the shared descriptor/session owner.

## 12. Physical acceptance checklist

At minimum:

- resize a child toward every edge, then use parent side/diagonal controls; no child may be cut outside the parent;
- child-driven outer growth is visible while dragging where the display can admit it;
- move each Abandonment role and verify its saved position survives re-entry;
- exercise all four resize corners on at least artwork + one text/layout role, including left/top anchoring;
- move roles through parent and sibling edge/centre guide acquisition, verify the guide appears, and verify hysteresis releases without magnetic rails or collision-induced false guides;
- flip eligible Abandonment Game Name/flavour alignment left ↔ right and prove Save / Cancel / Restore Size / layout-slot behavior through the same child transaction;
- begin/cancel/release child move and resize gestures and verify parent close/Restore chrome fades out/in from gesture state only, with no delayed timer behavior;
- shrink the Game Name frame aggressively with long titles: text shrinks/wraps and does not right-elide;
- move/resize the flavour text independently without breaking title fit;
- Save and re-enter; moved/resized child geometry must return exactly without a delayed correction jump;
- Cancel after repeated move/resize gestures and confirm the committed baseline returns cleanly;
- Restore Size must clear all child size/placement overrides and the transient containment floor while preserving widget X/Y/display;
- apply a layout slot containing child placement and confirm geometry rehydrates without aliasing/stale edit state;
- Settings controls that conflict with CUSTOM ownership are disabled only for that widget/family;
- exit Edit mode and verify no ongoing geometry signal chatter, polling, provider wake or measurable presentation cost.

### Header-slice acceptance after the current checkpoint is green

When `header` is actually implemented, then additionally verify:

- move the header near each corner and verify strong, stable margin snapping;
- resize the parent after snapping the header and confirm the semantic corner anchor remains correctly margined;
- drag the header decisively away and confirm the semantic anchor releases cleanly;
- Save / Cancel / Restore Size / layout slots round-trip the header anchor through the same child geometry transaction.

## 12. Operator follow-up requirements captured after dense physical testing

These are **required follow-ups**, not permission to fork the geometry owner. They must reuse the same selected-parent child editor, `child_geometry` persistence carrier, Settings lock metadata, and event-driven guide/chrome surfaces.

### Child alignment guides and light snapping

**Source implementation landed in the pre-rollout editor-polish checkpoint; Windows/physical acceptance remains open.** Child movement needs the same kind of visual confidence as whole-widget movement. The earlier simple parent-edge/centre snag was insufficient because some dense roles, notably artwork and title/name blocks, did not visibly align-snap against useful sibling geometry.

Landed contract:

- publish child-local guide metadata from the already-declared selected-parent role rectangles only;
- allow light acquisition against parent centre/margins plus sibling left/right/top/bottom edges and centres;
- display the corresponding guide while acquired;
- preserve the existing gentle feel for ordinary roles, with small acquisition distance and hysteresis;
- do not introduce scene-wide discovery, polling, or a normal-runtime geometry scanner;
- header roles remain the deliberate exception and use the stronger semantic corner stickiness described above.

### Alignment flip affordance

**Source implementation landed; Abandonment Game Name + flavour text are the first proof roles and physical acceptance remains open.** Text/content roles whose authored semantics are meaningfully left/right aligned can flip alignment from Edit mode using a deliberately tiny affordance at the element centre. The action is binary left ↔ right; centre/no-alignment roles do not expose it.

This is descriptor-declared capability, not inferred from arbitrary QML text. The pre-rollout checkpoint formally admits the optional `alignment` override inside the existing per-role `child_geometry` record; the authored value is represented by no override, so flipping back cleans the field instead of manufacturing sticky state. Do not create a family-local alignment store. Settings controls that author the same alignment must be widget-scoped locked while CUSTOM owns that role field.

### Superseded: automatic edit-chrome fading during child gestures

The earlier proposal to fade parent glyphs automatically on child gesture begin/end (approximately 1000 ms out / 3000 ms back) was physically rejected before rollout because the controls returned too aggressively and the editor should not guess when the operator wants them visible. It is **not** the current implementation.

Do not restore `childGestureActive`, a delayed return, Timer, single-shot, or other guessed visibility lifecycle. Parent glyph visibility is explicit session-local operator state through the attached HIDE CONTROLS / SHOW CONTROLS wedge; only a short finite opacity transition accompanies that explicit toggle.

### All-corner child resize handles

**Source implementation landed as the shared descriptor default for placement-capable roles; Windows/physical proof remains open.** Editable child rectangles expose all four corner handles unless a descriptor has a concrete semantic reason not to. One-corner-only handles unnecessarily restrict layout construction and also hide left/top anchoring bugs. Media and Abandonment placement roles now inherit the four-corner default. Achievement/Friend's older size-only authored-rail roles are deliberately exempt until their later placement migration because they do not yet consume persisted X/Y offsets; a top/left handle there would falsely imply opposite-edge anchoring across commit. This exception must disappear when those roles become placement-capable, not grow into family-local resize logic.

### Edit-mode input ownership

**Source implementation landed after operator physical testing exposed a universal leak; Windows/physical proof remains open.** While CUSTOM Edit is active, clicking/pressing an editable widget must never activate its normal runtime product action underneath the editor. The first concrete failure was editable Steam artwork opening its store page. The fix is shared and layered:

- every ordinary `OverlayWidget` loads an Edit-only full-root input blocker above family content but below the scene-level CUSTOM overlay;
- the ordinary host also projects interaction-disabled input state to current, newly-created and transferred retained families;
- `QuickDisplayWindow` bypasses normal runtime pointer semantics while CUSTOM owns the pointer but still forwards pointer events into QQuickWindow/QML, so editor drag/resize continues to function;
- scene-level glow/popup/double-click/middle-click routes fail closed while a CUSTOM session is bound;
- clearing CUSTOM retires the editor first, then restores family/native runtime input, preventing the terminating release from leaking through;
- keys remain on their existing runtime authority; no timer, polling guard or family-specific Steam patch is introduced.

Physical proof must include clicking artwork, text, seek/transport/control surfaces and ordinary card regions while Edit is active and confirming no store/web/action/refresh/context-menu/image-cycle/preset-cycle behavior fires beneath the editor.

### Media-specific physical reports to re-check

- The seek bar appears to retain excessive right-side authored spacing during some adjustment layouts. Re-test after the invisible structural-reservation/ghost-obstacle corrections before changing the accepted authored 75%-width baseline; distinguish actual track width from stale slot/collision footprint first.
- Media artwork did not reliably return to its authored geometry on Restore Size in one physical run. The shared reset contract now clears descriptor-owned child size + placement, but Media must receive an explicit physical regression pass after the full contract lands. Do not paper over a failed shared reset with Media-local reset code.


## 13. Live-edit paranoia audit: performance, I/O and ordering contract

Audit performed after the Media structural-reservation checkpoint. The live child editor remains a GUI-thread, selected-Edit transaction. Pointer samples do not save Settings, write layout slots, wake providers, submit worker work, or start timers/threads.

### Pointer-sample path

```text
QML pointer event
  -> bounded local collision/snap scan over selected parent's declared roles
  -> Python descriptor-bounded preview (resize only)
  -> Python in-memory child_geometry mutation
  -> synchronous session notification
  -> display-local retained presentation projection
  -> QML retained geometry change
  -> one coalesced Qt.callLater exact containment reconciliation
```

Important closeout corrections from this audit:

- stable **remote-display** session changes no longer republish an unrelated display's same-family presentation on every pointer sample; actual membership/transfer changes still take the explicit refresh path;
- pointer motion no longer runs both an immediate full exact containment scan *and* the retained-geometry coalesced scan. Same-event right/bottom overflow still uses the narrow provisional grow path, while exact reconciliation is coalesced once from retained geometry;
- child containment growth uses `ceil`, not nearest rounding, because it is a minimum floor. This prevents fractional under-admission from provoking repeated retries;
- when display bounds make a requested grow impossible and the admitted outer rectangle/content extent is already identical, the owner keeps the transient floor but returns a no-op instead of republishing unchanged geometry on every sample.

### Threading/race posture

- QML invokes the overlay model in Qt GUI-thread affinity.
- `CustomLayoutSession` change/selection listeners are synchronous; there is no child-editor worker or cross-thread mutation queue.
- provider/service updates may interleave only as ordinary GUI event-loop events; role disappearance cancels transient gesture state and queued containment reconciliation is selection/loader guarded.
- Save/Cancel/session close retires selection-owned child origins and containment before Python owner state is dropped. A queued `Qt.callLater` callback from an old layer cannot republish because it verifies the still-selected loader instance.
- Settings persistence remains at explicit Save/reset/slot transaction boundaries, never pointer cadence.

### Bounded work / rollout caveat

Collision and indirect-reflow admission are intentionally simple scans over the selected parent's declared roles and fixed obstacles. Dense cards currently contain only a handful of roles, so the per-sample work is small and allocation is short-lived Edit-only JS data. This is not a scene-wide solver. If a future widget wants dozens of independently editable roles, benchmark that family before admission rather than silently turning this contract into a large general-purpose layout engine.

Outside Edit, collision/snapping/mapping delegates and their `Qt.callLater` coalescer do not exist. Saved `child_geometry` values are consumed as retained model/QML bindings only.

## 14. Header / explicit-controls / Edit-input implementation update

The first shared-header proof is now source-landed on Abandonment. The existing `BrandedHeader` instance is exposed as `header`; the shared descriptor admits movement, uniform scale, alignment flip and semantic corner anchoring. The optional semantic `anchor` is additive state inside `size_payload.child_geometry.<role>`, so Save / Cancel / Restore Size / slots remain one transaction and old payloads remain valid.

Header corner acquisition is intentionally stronger than ordinary child snapping. It uses the family's safe insets, distinct guide treatment and larger acquire/release hysteresis. While anchored, parent resize recomputes placement from the semantic corner. A collision-clamped attempted drag does not detach the anchor; only admitted movement does.

The originally proposed automatic 1000 ms fade-out / 3000 ms fade-in for parent glyphs has been superseded by an explicit session-local attached control wedge. It reads HIDE CONTROLS / SHOW CONTROLS, chooses the side with more display room, hides only parent glyph buttons and leaves child move/resize/flip/guides live. It is not persisted and defaults to controls visible for a newly selected/re-entered widget. No Timer/single-shot/poller is used.

Edit input ownership is also split by semantic intent. Runtime content actions stay suppressed under CUSTOM, but right-click remains an editor/context-menu command. A full-screen CUSTOM background surface behind edit frames owns empty-background double-click and requests the existing canonical Save transaction, so the same gesture cannot leak to slideshow transition behavior.

Abandonment alignment-flip proof roles now include Header, Game Name, flavour text, Backlog, Last Visit and Shelf Group. Backlog keeps its authored centred text and mirrors its asymmetric decorative/status orientation rather than inventing left-aligned copy.

**Gate:** no broad family rollout until this header/interaction slice is Windows/PySide and physically green.

## 15. One-axis child edges and stepped containment growth

The shared child editor now supports side-only resize without adding visible handle chrome. A role's descriptor is still the authority: non-uniform horizontal/vertical axes admit invisible side hit zones; movable roles may use left/top because normalized placement can preserve the opposite edge, while size-only roles admit only right/bottom. Uniform/intrinsic roles stay corner-only because a one-axis cursor would falsely advertise distortion that the role contract forbids. Python's canonical resolver admits these edge handle ids and zeros the orthogonal pointer delta before applying descriptor bounds.

The child-to-parent containment path also has deliberate resistance. Once a right/bottom child edge reaches the current parent boundary, the active pointer must travel another 12 physical pixels before one 6-pixel parent-growth step is admitted. The same admitted point clamps the child, preserving the hard containment invariant. This is per-gesture state on the selected Edit delegate only; it has no persistence or steady-state cadence.

CUSTOM pointer delivery is explicitly higher priority than the short runtime-recreation suppression guard. That guard exists to prevent leaked runtime actions during replacement and must never suppress editor chrome. Runtime actions remain independently blocked underneath Edit.

## 16. Rollout admission guardrails

The Abandonment/Media proof exposed enough edge cases that broad rollout must be treated as **descriptor admission**, not copy/paste. Every new widget family must pass this checklist before its first placement-capable checkpoint:

1. **Identity and ownership:** stable runtime widget id, stable role ids, and a real Settings-section id are declared separately. Never reuse a synthetic lock-scope id as a lazy Settings page id. One `CustomLayoutSession`, one `child_geometry` carrier, no family-local persistence.
2. **Input ownership:** entering Edit must suppress ordinary family/runtime actions without suppressing editor chrome. Explicitly test left click, double click, middle click, right click/context menu, wheel, move, parent resize, child resize and transfer. The transient runtime-recreation pointer guard must never outrank CUSTOM ownership.
3. **Role geometry semantics:** declare axes, movable vs size-only, uniform vs non-uniform, resize handles, invisible side edges, alignment flip and semantic anchor capabilities. Left/top edge resize is admitted only where placement authority can preserve the opposite edge. Uniform/intrinsic roles do not get misleading axis cursors.
4. **Real target vs occupied target:** edit chrome targets the retained adjustable frame; collision/containment uses the real painted footprint. Invisible layout reservation/placeholder bands are not collision obstacles and must stop acting as geometry authorities after free placement.
5. **Reflow contract:** identify authored-rail dependencies, first-real-move compensation, per-axis downstream reflow peers and off-rail detachment. With Child Collision enabled, off-rail roles become ordinary hard collision surfaces. Predict indirect reflow collision before commit rather than fixing overlap one scene turn later.
6. **Collision preference:** any widget with multiple editable roles consumes the shared global `widgets.global.child_collision_enabled` contract, default OFF and surfaced once in **Widgets -> General -> Layout**. Off disables editable-peer collision only; fixed obstacles, snapping/guides and parent containment stay active. It must not enter `child_geometry`, layout slots, or create a family-local persistence path.
7. **Containment:** child move/resize may never strand painted content outside the parent. Right/bottom child-driven growth uses the shared stepped containment admission; shrinking/moving inward lowers only the transient floor and never silently auto-shrinks the outer card.
8. **Text semantics:** primary names/titles/metadata that carry meaning must preserve full content through fit/shrink/wrap according to the family contract; do not reintroduce accidental right elision.
9. **Alignment semantics:** flip capability is explicit, not inferred from arbitrary text. Define exactly what left/right means for composite roles; centred/no-alignment roles expose no flip unless the family intentionally mirrors an asymmetric decorative structure.
10. **Header semantics:** use the existing `BrandedHeader`; no family fork. If admitted, corner anchors use family/shared safe insets, stronger hysteresis and the same child transaction.
11. **Transactions:** Save, Cancel, Restore Size and layout slots must round-trip all admitted child state (size, placement, alignment, anchor) together. Restore Size clears descriptor-owned child state but preserves parent X/Y/display. Widget Settings such as Child Collision are intentionally outside this transaction.
12. **Settings locks:** CUSTOM locks are an additional disable layer, never a replacement for family dependency state. Releasing CUSTOM must not resurrect controls that the family itself has disabled. Locks are widget-scoped even when several families share one Settings page.
13. **Visibility/lifecycle:** role disappearance, selection change, Settings rebuild, transfer, slot load and teardown retire transient gesture/floor state deterministically. No stale delegate row may mutate a newly indexed selection.
14. **Performance:** outside selected Edit there is no collision/snap scanner, pointer observer, Timer/QTimer, polling, worker/thread, provider wake, per-frame Python publication or repeated descriptor allocation. In Edit, work remains bounded to the selected parent's declared roles/obstacles. The Settings collision preference is event-driven and must never become a cadence read.
15. **Physical matrix before the next family:** all corners + admitted side edges, move → resize → move, collision escape, Child Collision on/off, child-driven growth, parent resize after child edit, alignment flip, header anchor if present, HIDE/SHOW controls, right-click context menu, background Save + Apply, Save/re-enter, Cancel, radical Restore, slot load, Settings visibility changes, dual-display exit/transfer, and deliberate attempts to activate normal widget actions underneath Edit.
16. **Checkpoint discipline:** dense families land one at a time. Do not enroll the next dense family until the previous family's focused Qt tests and physical matrix are green. Visualizer remains outside child-role rollout and its existing parent viewport handles are a protected regression check for every input-gate change.

These guardrails are part of the rollout contract, not optional documentation. A family that cannot state its answer for one of the above stays out of rollout until the missing semantic is defined.
## 17. Pre-rollout debris / duplication / performance-neutral audit closeout

The audit after the child-edge/input/growth checkpoint deliberately looked for duplicated gesture authority, stale Edit-only state, normal-runtime cadence and rollout traps before admitting another family. It made two source cleanups and retained one apparently-duplicated pair by design:

- corner resize and invisible one-axis edge resize now enter the same `beginChildResizeGesture` / `updateChildResizeGesture` / `cancelChildResizeGesture` pipeline. Preview, collision admission, stepped containment growth, immediate overflow protection and canonical Python commit therefore cannot drift between handle shapes;
- unused CUSTOM context-menu press timestamp/position bookkeeping and its dedicated release shim are removed. Edit right-click is an immediate context command, not the beginning of the normal runtime press/move/release gesture state machine;
- the native display-window Edit gate and ordinary-widget QML blocker remain intentionally separate. The first suppresses global/runtime pointer semantics (transition/image-cycle/preset-cycle/context dispatch ordering); the second prevents family-local QML actions from firing underneath the scene-level editor. Removing either one would reopen a class of click-through bug.

The shared QML resize path contains one `previewChildResize` callsite and one `resizeChild` callsite. Live pointer samples still rely on retained occupied-geometry notification to coalesce exact containment reconciliation; explicit `syncRequirementNow()` is kept only behind the final gesture boundary. No Timer/QTimer, polling loop, provider wake, worker/thread or normal-runtime scene scanner was added.

Section 16 is therefore the mandatory family-admission gate. In particular, every future input-gate change must physically re-test the existing Visualizer parent side/corner handles even though Visualizer is not part of child-role rollout. Every dense family must close its own focused Qt + physical matrix before the next dense family is admitted.

