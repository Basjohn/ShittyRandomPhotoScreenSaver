# CUSTOM Editable Child Geometry

Scope: **current ordinary-widget CUSTOM child editor contract**. Existing family enrollment is source-complete; Windows/PySide and physical acceptance must be established separately. This file describes behavior and admission criteria, not the sequence of checkpoints that implemented them.

This feature extends the existing CUSTOM presentation/edit system into a **role-declared visual editor** for ordinary widgets. The role catalogue may grow aggressively as useful edit affordances are identified; the boundary is architectural, not a feature-count ceiling. Every adjustable element/group still enters through the shared descriptor/session/persistence owner rather than exposing arbitrary QML geometry or creating a second layout, sizing, persistence, or runtime owner.

## 1. Ownership model

```text
authored child-size setting / authored child geometry
-> optional CUSTOM child-geometry override
-> ordinary family layout/reflow
-> shared content_extent requirement when the child no longer fits
-> existing outer CUSTOM geometry/session owner
```

The presentation/edit layer owns drag affordances and transient CUSTOM child geometry. The family owns only its normal response to the resolved child size. The shared CUSTOM session/payload infrastructure owns Save/Cancel/slot persistence/reset semantics. No family may add a parallel Settings-backed CUSTOM width/height, timer, poller, layout solver, or per-frame geometry synchronization path.

Outside an active edit or a real geometry/state change, the feature must add **no recurring work**: no timer, polling, provider wake, per-frame Python/QML chatter, collision scan, normalization pass, or layout scheduler. Saved geometry is retained state consumed by normal bindings/layout.

## 2. Authority suppression in Settings

When a widget is in **CUSTOM**, presentation-layer child geometry is the active geometry authority for every admitted child role, even when that role still equals its authored baseline. The corresponding authored geometry controls in Settings must therefore be disabled rather than allowed to fight the presentation owner. Reuse and normalize the existing **"Disable Custom To Adjust!"** UI pattern so it is consistent wherever CUSTOM supersedes authored geometry.

- Authored Settings values remain preserved underneath as the non-CUSTOM/reset baseline; CUSTOM never destroys them.
- Returning the widget to a non-CUSTOM placement restores Settings as the active geometry authority. While remaining in CUSTOM, the shared **Restore Size** glyph is an authored-state reset for the widget: it restores the authored outer size/shape and clears every descriptor-owned child size/placement override while preserving the widget's current X/Y/display. It does **not** re-enable conflicting Settings controls because CUSTOM still owns the geometry surface.
- For artwork roles, disable every authored control that determines the artwork rectangle, including **size and shape** selectors. CUSTOM width/height becomes the rectangle truth. The image content itself still preserves native source aspect via the family’s existing fill/zoom/crop policy.
- Controls unrelated to the admitted child geometry remain usable. CUSTOM lock notices are widget/family scoped: reverting one warning must not dismantle unrelated CUSTOM widgets. Steam cards in particular use independent Achievement / Abandonment / Friend Pulse lock descriptors even though they share one Settings section/provider family.
- This is the same ownership principle as disabling stacking while global CUSTOM placement owns geometry.
- Media’s former **Allow Landscape Artwork** option is retired now that Media uses the child-role system. CUSTOM artwork geometry is unconditionally freeform X/Y; do not reintroduce a landscape permission as a competing authority.

## 3. Role-based opt-in only

Visual roles opt in deliberately through shared descriptors. The goal is rich edit-mode customization, so additional useful labels, groups, panels and controls may be admitted over time; do not bypass the role system by exposing arbitrary QML children directly or by giving each family its own geometry owner.

Admitted role patterns and future extensions:

- **Media:** full semantic rollout is now Header, one atomic title/artist/album metadata crossfade block, optional playback-state text, main artwork, seek bar, app-volume bar, grouped `transport_controls` surface, and a separate intrinsic/uniform `mute_button`. Previous/play-pause/next remain one grouped transport semantic and are never persisted individually. The mute button is separate specifically so the non-uniform control bar cannot squash it; it shrinks through one common fit factor when bar dimensions become restrictive. Transport↔mute authored containment bypasses only hard peer collision. All roles remain in the same `child_geometry` carrier.
- **Achievement Pulse:** three first-wave roles: primary artwork, latest-achievement badge, and progress circle. The **artwork frame itself is freeform on X/Y**; the source image must never distort and continues to use the family's existing native-aspect fill/zoom/crop policy inside whatever rectangle CUSTOM creates. Badge and progress circle are intrinsic-shape roles and remain uniform/aspect-locked. Additional Pulse Name, Achievement List and grouped Pills/Shelves roles require explicit descriptor admission; do not introduce family-local geometry controls.
- **Abandonment Issues:** primary artwork, BACKLOG/archive-status block, Game Name block, flavour text, Last Visit metric box, and one grouped shelf/ledger role. The shelf role resizes every shelf together; do not persist one geometry record per shelf. This proves the reusable **layout-block** role: the containing frame changes through shared CUSTOM geometry while family-authored internal typography/layout responds to the new frame.
- **Future Steam cards where appropriate:** reuse the same artwork/layout-block/group-role descriptors rather than cloning Abandonment-specific geometry code.
- **Friend Pulse:** six retained roles: singleton Header, Online Count and Separator plus three repeated shared roles for Friend Frames, Avatars and Usernames. Each repeated role has **one geometry record for the whole roster**, never one record per friend/delegate. Frame size remains family-positioned; avatar and username size/placement are shared across all repeated items so row/grid rhythm and clipping remain coherent.
- **Weather:** condition/hero icon if the final interaction remains useful after the shared implementation exists.
- **Clock analogue only:** `clock_face` is a single center-owned uniform child comprising ring, markers, Roman numerals and every hand. Independent numeral geometry was physically rejected and retired. Separator/calendar/timezone are distinct optional roles. Digital mode keeps only its visible digital-specific text and optional footer roles; no dormant analogue edit target.

The framework should make future widgets opt in declaratively by role/axis/policy rather than requiring a new controller per family. Freeform artwork geometry uses the shared `freeform_artwork_child_role(...)` contract so Achievement, Abandonment/future Steam artwork and Media inherit the same X/Y frame semantics without sharing or waking their provider/image owners.

### Child-handle admission

Do **not** show every child handle merely because global Edit mode is active. The default interaction is two-stage: global Edit mode exposes the ordinary parent frame; clicking/selecting that parent enters child-edit focus for that widget and reveals only its admitted child-role handles. Clicking another parent transfers focus; leaving Edit mode clears it. This keeps dense widgets readable, bounds hit-testing to one family at a time, and avoids persistent overlay clutter/cost. Child handles should be visibly smaller than outer-widget handles while preserving a practical pointer target, preferably by separating the drawn handle size from its transparent hit target. No polling or hover scan is required; selection is event-owned retained state. Prefer one active child-handle layer/Loader for the selected parent rather than instantiating hidden child handles for every widget in Edit mode.

The shared parent-selection primitive is session-owned rather than display-QML-owned, so dual-display Edit cannot expose two unrelated focused parents at once. Focused edit chrome may fade **in** with a short event-triggered QML opacity animation. The animation driver runs only for that brief transition and then stops; do not use a Timer, recurring hover probe or per-frame Python publication to create the effect.

### Outer two-axis reflow affordance

Keep the established square outer corners exactly as authored: they remain uniform whole-widget scale, and side strips remain one-axis `content_extent`. A separate lighter-blue **diagonal** corner affordance may adjust horizontal + vertical `content_extent` together at constant uniform scale. It uses distinct semantic handle ids and the same Python CUSTOM geometry owner, never a QML-owned rect.

The diagonal is an **inside-corner bridge** between the two admitted blue side strips, not external edit chrome. Its visible line literally joins the two 20 px-inset strip endpoints across the corner wedge; each corner uses the mirrored slash orientation required by those actual endpoints, rather than reusing the ordinary square-corner cursor diagonal. Its visible line and hit wedge stay inside the selected card's corner breathing room. It is admitted only for the selected ordinary parent and only when both content axes are available. Suppress a corner when that inward wedge overlaps another widget, edit glyph, adjustable handle/child control, or another declared interactive exclusion; non-interactive headers are not exclusions. Collision admission is driven by edit selection/geometry changes only; never continuously scan the scene at render cadence. The shared exclusion mechanism should grow with child-role admission rather than introducing a scene-wide pointer probe.

## 4. Geometry and normalization

Persist normalized logical child geometry, never raw device pixels. The exact representation may be a factor relative to the authored child baseline or another shared logical representation, but it must survive display/DPI/outer-widget changes without turning physical pixels into authority.

A role declares, at minimum:

- stable role id;
- geometry constraint (freeform X/Y for artwork frames, uniform for intrinsic shapes such as circles/square badges, axis-limited where appropriate for bars/groups);
- allowed axes;
- authored baseline geometry/size;
- bounded minimum/maximum policy;
- whether a single override applies to one item or a whole repeated group;
- whether overflow contributes to outer `content_extent`;
- whether the role is singular or group-scoped (for example all Friend Pulse avatars or all shared System Stats metric labels).
- resize handle admission remains descriptor-owned. **Foundation note superseded by the later placement phase:** now that normalized child X/Y placement is part of the same `child_geometry` authority, editable roles default to all four corners and left/top resize preserves the opposite edge through that existing carrier. A descriptor may still restrict corners for a concrete semantic reason. The edit overlay queries only the selected parent's descriptor.

Save/Cancel/slots round-trip the same shared `size_payload.child_geometry` carrier. The carrier now owns authored-relative child size **and optional X/Y placement**. Cancel restores the session-entry baseline. The existing bottom-left **Restore Size** glyph is deliberately broader: it is the widget's authored-state reset and atomically clears descriptor-owned child size/placement overrides plus the transient containment floor while restoring authored outer size/shape. It preserves the widget's current X/Y/display. There is no second per-child reset authority.

### Persistence / Settings SSOT

Child geometry does **not** get a new file, database or family-local Settings key. It rides inside the existing canonical `widgets.custom_layout` structured root persisted by `SettingsManager` to the profile `settings_v2.json` (`%APPDATA%\SRPSS\settings_v2.json` for the normal Screensaver profile; the MC profile uses its existing `SRPSS_MC` sibling). Each display/widget/geometry-variant CUSTOM entry already owns a `size_payload`; normalized child factors live under `size_payload.child_geometry`. The existing `custom_layout_restore` root continues to own authored route restoration metadata. This keeps one persisted Settings authority and lets Save/Cancel/layout slots/cross-display hydration use the same CUSTOM contract rather than inventing a second child-geometry store.

## 5. Reflow / overflow contract

The family must consume child geometry through its existing layout flow. Collision admission is a **shared selected-Edit interaction rule**, not a normal-runtime layout solver: declared editable peers and fixed painted obstacles may block move/resize samples while the selected child overlay exists, but no collision scan survives outside Edit and no family gets `if collision then move X by N` persistence logic.

- If the resized child still fits inside the current card, neighboring content reflows/redistributes using the family's normal authored minimum padding/spacing.
- If the child grows beyond available room, the family may raise its required logical `content_extent`; the existing outer CUSTOM owner decides the outer geometry response.
- The selected family exposes one retained child-content requirement target. The edit overlay observes that target only while selected and coalesces requirement changes to the next QML turn, so child-driven growth can apply **live during the gesture** without a timer/poller or scene-wide observer.
- The owner retains the latest requirement as a **transient session-only floor** for parent content side/corner gestures. Parent controls therefore cannot shrink the logical box back through already-customized children. If the child later needs less room, the floor lowers but the outer card does not auto-collapse.
- **Growth may expand the outer widget when required. Shrinking a child must not automatically shrink the outer widget.** The user can separately reclaim outer space. This avoids shrink/grow feedback loops during editing.
- Side-axis `content_extent`, optional diagonal two-axis content reflow, and square-corner/wheel whole-card scale remain gestures on the **same** outer CUSTOM sizing authority.

## 6. Artwork quality handoff

A committed CUSTOM artwork-size change may require a larger source than the currently retained texture. On **Save/commit** (not every drag tick), artwork-backed roles must be able to request the existing image/artwork owner to resolve an appropriately sized source and crossfade from the retained current image into the higher-quality replacement when it is ready.

Requirements:

- artwork **child rectangles are freeform** on X/Y; preserve the source image's native aspect ratio inside that rectangle using each family's accepted fill/crop/zoom semantics, never by distorting the image;
- in CUSTOM, a disabled authored portrait/square/wide selector is no longer allowed to dictate the live rectangle. If a family uses shape to choose among source variants, the commit-time quality resolver should use the **actual committed CUSTOM rectangle/aspect** as its sizing/source hint while preserving the family’s existing fallback order;
- keep the accepted current artwork visible until the replacement is ready;
- use the existing artwork owner/cache/request-generation path, never a second downloader/cache/provider;
- do not refetch/redecode continuously during drag;
- no downgrade flash, blank frame, or synchronous foreground processing;
- if the existing source is already sufficient, do nothing;
- Weather condition art should use the same commit-time quality escalation only if its real asset path benefits from it; packaged/source-resolution evidence decides this later rather than inventing unnecessary work.

## 7. Admission / performance gate

Before a family opts in, verify that the implementation adds no recurring runtime pressure when edit mode is inactive. Self-audit each slice for CPU/GPU work, allocations, provider wakes, extra model publications, cross-thread chatter, retained-layer/effect costs, and accidental outer-layout churn.

Prefer immutable/retained resolved state and event-owned updates. A child drag may naturally cause Quick relayout while the pointer moves; after the edit settles, rendering must consume the resolved geometry without a new cadence.

## 8. Current role admission and remaining proof

The shared child editor and `content_extent` owner serve Achievement Pulse, Abandonment Issues, Friend Pulse, Media, Weather, Clock, Reddit/Reddit2, Gmail and System Stats. Each family must declare stable editable role IDs, permissible axes, handle/placement semantics and painted occupied geometry through shared descriptors. Visualizer is deliberately excluded. Repeated roster/metric/row elements share a role-level geometry record; neither friend IDs nor metric identities are persistence keys.

The current source exposes descriptor-limited resize and movement, live selected-parent containment, shared Settings locks, Save/Cancel/Restore/slot round-trips and event-only edit input. Acceptance remains a separate **Windows/PySide plus physical gate**: test all admitted resize directions, role move/reflow, flip, collision on/off, parent growth, Save/Cancel/Restore/slots, cross-display transfer, Settings visibility and no runtime click-through while editing. Normal runtime must not gain a timer, polling, provider wake, collision scan or extra geometry-publishing cadence. See [CUSTOM Child Placement](Custom_Child_Placement_And_Headers.md) for the gesture and admission contracts.

Artwork quality escalation is conditional, not a mandatory refetch: resolve a larger source only on committed geometry when an existing image owner can actually supply better pixels. In particular, do not invent a Media artwork refetch when the present source has no higher-resolution variant.
