# CUSTOM Child Placement, Header Roles and Text Fit

Scope: **current shared CUSTOM child-editor contract** for ordinary retained families. Achievement Pulse, Abandonment Issues, Friend Pulse, Weather, Clock, Reddit/Reddit2, Gmail, Media and System Stats consume its descriptor/session owner. Visualizer does not participate. Source enrollment does not substitute for Windows/PySide and physical acceptance.

## Why this exists

The child editor must satisfy these visible and ownership requirements:

- customized children must remain inside a truthful parent even when the **parent** content controls are used afterward;
- child gestures must never resize the outer card; outer side/corner controls alone own parent dimensions;
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

The actual painted parent/card (or an explicitly declared existing accessory lane)
sets the hard boundary for **every** child gesture. Child move and resize clamp
inside it even with sibling collision OFF, and may never publish parent growth.
Only the parent's outer side/corner handles change its dimensions. Parent
resizing must preserve painted-child containment and existing explicit CUSTOM
geometry without treating a one-time authored width as an unconditional CUSTOM
minimum. A too-large legacy child is handled at the existing bounded owner,
not by repeated inside-out growth, hidden clipping or resetting user settings.
Family padding and authored margins are mild snap hints, not hard movement bounds.
No parent-child feedback/catch-up loop, timer, worker or extra persistence owner.

## 3. Extend `child_geometry`, do not create `child_position`

Persisted role entries are additive; saved size-only entries remain valid.

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

The existing carrier and its compatibility contract are:

- size factors remain authored-relative;
- placement is always persisted as an authored-relative normalized offset, never an absolute screen coordinate;
- child geometry is an independent normalized X/Y delta on top of the family’s live authored rails; an X edit cannot disable Y reflow, and a Y edit cannot disable X reflow;
- first-move compensation may preserve legacy saved offsets, but must only affect the edited axis, never sever the opposite-axis parent or sibling rail;
- child resize changes that child only. A parent content extent never grows from child edits and cannot become a recursive placement baseline;
- a zero-motion press/release does not fold compensation or create placement state;
- offsets are normalized against stable authored parent geometry, never raw device pixels;
- outer-handle content extent is separate from child geometry and cannot be changed by a child gesture;
- old size-only payloads imply zero authored-relative offset and no semantic anchor;
- unknown role data continues to be preserved by the existing forward-compatible mapping update path;
- user-authored CUSTOM state is never rewritten merely to adopt the new fields.

A child edit retains the ordinary family’s live row/column reflow on untouched axes. An intentional offset on one axis remains a bounded delta on that axis rather than a permanent detachment from unrelated live parent geometry. The existing `child_geometry` carrier remains the only saved child authority.

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

Declared child roles and declared fixed obstacles must not be allowed to create new committed overlap during move/resize. Existing legacy/corrupt overlap must remain escapable rather than trapping the user. Collision admission is selected-parent/Edit-only and uses the already-retained role targets; it must not become a normal-runtime scene scan. Family-authored reflow may explicitly exempt a downstream sibling during resize only while both the source reflow gate and that downstream peer remain on their authored rails, and only on the axis that the family explicitly declares. Explicit child placement remains a normal collision surface, but it cannot suspend unrelated-axis family reflow. The shared editor also predicts that declared same-axis secondary translation before commit, clamps it against off-rail peers/fixed obstacles, and clamps that predicted result against the current parent instead of asking it to grow or repairing overlap one frame later.

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

Role semantics:

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

Required interaction:

- larger acquisition zone than ordinary child snapping;
- hysteresis/release threshold so a snapped header does not jitter in and out of the corner;
- clear visual guide/state when a corner anchor is acquired;
- drag decisively away from the release threshold to clear the semantic anchor and return to free placement.

The corner margin comes from the family's/shared header-safe inset contract, not a hard-coded screen coordinate.

## 6. Abandonment Issues role mapping and shared header

Abandonment declares these movable roles:

1. `artwork`
2. `backlog_block`
3. `game_name`
4. `flavour_text` — the subtitle/rediscovery line beneath the game title
5. `last_visit`
6. `shelf_group`

Grouped shelves remain one group, never one persisted position per shelf. The family keeps authored dependencies only while a role remains on its authored rail; once a role has an explicit CUSTOM displacement, that displacement is respected rather than overwritten by a later unrelated sibling resize.

The same shared role contract admits:

7. `header` — the existing shared `BrandedHeader` instance, using the semantic sticky-corner contract in §5 rather than a family-local header implementation. Header implementation uses shared corner semantics; physical acceptance remains a separate gate.

## 7. Text preservation contract

Editable text frames need a non-destructive overflow policy: a narrowed Game Name role must not degrade to right-elided text when the content could instead shrink and/or wrap.

For title/name/metadata roles where the full string is meaningful:

1. preserve the authored preferred point size when it fits;
2. shrink toward a family-declared readable minimum;
3. where the role semantics allow it, use an additional line before giving up more size;
4. use `Text.Fit`/equivalent against both width and height for multi-line roles;
5. default to `Text.ElideNone` for these editable primary-text roles;
6. only use elision where the product deliberately defines the text as disposable/preview content.

Do not globally change `ShadowedText` defaults and accidentally rewrite every existing widget. Apply the non-destructive text-fit policy at the admitting family/role binding; reuse a shared adaptive-role primitive only where multiple families demonstrably share identical semantics. Media, Achievement Pulse and Friend Pulse title/name/metadata roles require fit checks when narrowed or moved.

## 8. Settings conflict locking

CUSTOM geometry must not fight authored Settings controls.

Keep UI lock metadata in the widget descriptor/Settings layer, not inside the rendering role descriptor. Rendering should not learn Qt Widgets control attribute names.

When a widget admits placement or role scaling, extend its widget-scoped CUSTOM lock descriptor to include only controls that would otherwise author the same property, for example:

- artwork authored size/shape when artwork geometry is CUSTOM-owned;
- authored alignment/position controls if a later family exposes them and CUSTOM owns that role's placement;
- role-specific size controls when a CUSTOM role scale owns the same visible result.

Do **not** disable unrelated appearance/content controls merely because the widget has CUSTOM placement.

Steam families remain independently scoped. Editing Abandonment must not disable Achievement or Friend Pulse controls.

For families such as FEEDS, alignment flip may be a widget-wide semantic orientation: header/content order and family rails mirror together in QML while image and text pixels themselves remain unmirrored. The persisted intent stays one family-level alignment state, not per-delegate geometry.

## 9. Reset / Save / Cancel semantics

Keep existing transaction behavior:

- Save commits size + placement through the existing CUSTOM payload;
- Cancel returns both size and placement to the last committed state;
- layout slots round-trip both through the existing `custom_layout` snapshot, with no second slot schema;
- the existing bottom-left **Restore Size** glyph is the authored-state reset for the whole widget: it restores the outer authored size/shape **and clears every descriptor-owned child size/placement override**, while preserving widget position/display;
- an interrupted child gesture must retire only transient pointer origins, never partially commit a second geometry authority;
- deleting/reverting CUSTOM for a widget returns to the canonical authored Settings layout.

A snapped semantic header anchor is part of that same child-role committed state and therefore obeys Save / Cancel / Restore Size / slots as one transaction.

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

During final acceptance and every future family admission, measure CPU/GPU allocation, signal rate, delegate churn, provider dormancy and render-node/effect count with Edit mode off. Source inspection cannot substitute for live Windows/Qt and operator physical evidence.

## 11. Current editor behavior

**Role declaration and containment.** Placement-capable child roles expose four corner handles and, only where non-uniform axes permit it, invisible one-axis side zones. Size-only roles cannot advertise left/top resize unless the shared placement carrier can preserve the opposite edge. Intrinsic/uniform elements remain uniformly resized. All child controls act on the selected parent; visualizers have no ordinary child roles. A child may not be committed outside its real parent; every attempted overflow is clamped at the existing painted boundary. The outer side/corner controls alone change the parent size. There is no child-triggered growth threshold, child-content growth floor or catch-up publication.

**Reflow and alignment.** The first genuine free move preserves the existing authored-rail compensation on the edited axis only; zero-motion press/release creates no placement state. A child retains live parent/sibling reflow on every axis except a specifically authored semantic constraint on that same edited axis. An X-only child edit cannot freeze later Y reflow, including after a flip or Save/reopen. Only a declared on-rail, same-axis reflow peer may receive the narrowly declared collision exemption. Predict that peer’s secondary translation and bounded containment before commit; do not accept a one-turn overlap and fix it afterward. Selected-parent parent/sibling edge-and-centre guides use light acquisition and hysteresis; headers use stronger family-inset corner anchors. Descriptor-declared left/right flip is stored in the same `child_geometry` entry, with absence of an override representing authored alignment. Centered/no-alignment roles have no flip unless they explicitly mirror asymmetric decoration; BACKLOG may retain centred text while mirroring its decoration.

**Child Collision preference.** `widgets.global.child_collision_enabled` is the only shared editable-peer collision preference and defaults OFF. It is surfaced once in Widgets -> General -> Layout and is not stored in `child_geometry` or a layout slot. OFF permits editable-child overlap, but never disables real-parent containment, fixed obstacles, alignment guides, anchors or Edit input ownership. With collision enabled, editable-child crossing is possible only by a complete, admitted 14-logical-pixel pressure pass to the other side; fixed obstacles and all resize collisions remain hard. The unselected role does not move.

**Edit controls and input.** The selected parent exposes an explicit, session-local HIDE CONTROLS / SHOW CONTROLS wedge for parent glyph visibility, with a short finite opacity transition; controls start visible on a newly selected/re-entered widget. Do **not** revive automatic gesture-driven 1000-ms/3000-ms fading, a delayed return, a timer or a persisted visibility flag. Hiding parent glyphs leaves child edit controls and guides active. Edit-only QML blockers prevent normal family actions under editable cards; the Quick display window suppresses runtime pointer actions while forwarding QQuickWindow/QML pointer delivery to the editor. A short runtime-recreation guard must not preempt CUSTOM pointer ownership. Right-click retains the editor context-menu command. Empty-background double-click commits through the same canonical Save route instead of cycling the slideshow. Save/Cancel/slot changes, role disappearance, selection transfer and loader teardown retire gesture and containment state before a stale delegate can commit.

**Bounded work.** Pointer samples stay on the Qt GUI thread: selected-parent role/obstacle admission, descriptor-bounded Python preview/commit, narrow session notification and retained display projection. Each sample admits a bounded child rectangle inside the already-existing parent, with no deferred growth/coalesced containment catch-up and no redundant no-op publication. Stable remote displays do not receive every local child pointer sample. Settings I/O occurs only at explicit Save/reset/slot boundaries. Outside Edit, no collision/snap scanner, pointer listener, per-frame Python publication, extra provider wake, timer, worker, or deferred Edit coalescer remains. New families with many independently editable roles require measured admission rather than silently expanding the selected-parent scan into a scene-wide solver.

## 12. Family admission and physical acceptance

For each new ordinary family, declare the stable widget ID, Settings-section ID, semantic role IDs, axes, movement/handle policy, actual painted occupancy, layout rails, downstream reflow exemptions, collision obstacles, text fit/wrap and any alignment/semantic header anchor. Repeated elements use one semantic role per repeated category, not one CUSTOM record per data identity. Widget-scoped CUSTOM Settings locks add to normal family dependency locks; removing CUSTOM must not re-enable a control that another family rule still disables. Use existing `BrandedHeader`, not a forked header renderer. Preserve author-selected X/Y/display when Restore Size clears the entire descriptor-owned child carrier.

The acceptance matrix must cover all applicable corners/side zones, child move -> resize -> move, parent resize after child movement, guide acquisition/release, sibling crossing with Child Collision both ON and OFF, fixed obstacles, header anchor detachment and parent-resize stability, text fit rather than accidental ellipsis, Save/re-entry, Cancel, Restore Size, layout-slot replay, visibility/Settings changes, dual-display transfer and exit, HIDE/SHOW controls, background double-click Save, right-click menu, and deliberate attempts to activate normal widget actions while editing. Retest Visualizer's existing parent viewport handles after any shared input-gate change, although Visualizer is not enrolled in the child editor.

Media requires an explicit artwork Restore Size round trip and inspection of actual seek-track width versus invisible layout reservation: retain the authored 75%-width seek baseline unless the rendered track itself proves faulty. Do not add Media-local reset or padding workarounds to conceal a shared geometry defect. Live Qt/PySide, installed visual and Edit-off resource acceptance remain separate from static source inspection; source enrollment alone is not that proof.

## 13. Repeated-list semantic column rails (current implementation)

Reddit/Reddit2 expose three semantic columns (`age`, `ago`, `title`); Gmail exposes
`timestamp`, `sender`, `subject`. While a parent is selected and child-editing is
unlocked, the existing overlay draws an Edit-only vertical guide and grip for each
currently visible first-row target. Dragging a grip across another column commits
**one swap upon release**, not a sequence of per-pointer or per-row position updates.
The QML renders one widget-wide semantic order across **every** retained row.

`QuickCustomLayoutOwner` alone owns the discrete change and bounded three-action
Undo history. It persists a validated permutation as `size_payload.column_rails`
in the ordinary CUSTOM layout entry, never in provider data, per-row records,
family Settings defaults or a parallel schema. The model projects that key into
existing retained QML at a session-change, Save/reopen and layout-slot hydration.
When absent, authored header orientation supplies the existing default order.
An explicit CUSTOM order is an explicit override, independent of later header
flips; Restore Size clears that override while preserving authored mode's
baseline. Wheel/corner gestures retain live order, not a stale baseline.

AGE and AGO retain their normal 2 logical px gap when adjacent; a title-adjacent
rail uses Reddit's scale-aware legibility gap. Gmail retains the configured
sender/subject width ratio and the fixed menu/envelope controls. The title/subject
can elide within their own assigned widths, never bleed into another column.
Swapping never mirrors image/text glyphs, changes the parent size, detaches X/Y
reflow or rebuilds provider models and repeated QML row delegates.

Admission requires a Windows retained-scene check on **every** row, both header
orientations, compact X/Y, a real drag/reverse, Ctrl+Z, Cancel, Restore, Save,
slot replay and fresh display generation. Tests that see only a changed Python
payload or a blue guide without changed painted rows do not establish acceptance.
A normal-runtime column observer, timer, polling loop, new persistence owner or
one saved geometry record per repeated row is forbidden.
