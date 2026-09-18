# CUSTOM Editable Child Geometry

Status: **active foundation work after operator validation of the 2026-09-18 ordinary-widget `content_extent` rollout**.

This feature extends the existing CUSTOM presentation/edit system to a small set of **major visual child roles** inside ordinary widgets. It is not a general-purpose visual designer and must not create a second layout, sizing, persistence, or runtime owner.

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
- Returning the widget to a non-CUSTOM placement restores Settings as the active geometry authority. Resetting a child while remaining in CUSTOM returns that child to the preserved authored baseline **but does not re-enable the conflicting Settings controls**; CUSTOM still owns the geometry surface.
- For artwork roles, disable every authored control that determines the artwork rectangle, including **size and shape** selectors. CUSTOM width/height becomes the rectangle truth. The image content itself still preserves native source aspect via the family’s existing fill/zoom/crop policy.
- Controls unrelated to the admitted child geometry remain usable. CUSTOM lock notices are widget/family scoped: reverting one warning must not dismantle unrelated CUSTOM widgets. Steam cards in particular use independent Achievement / Abandonment / Friend Pulse lock descriptors even though they share one Settings section/provider family.
- This is the same ownership principle as disabling stacking while global CUSTOM placement owns geometry.
- Media’s current **Allow Landscape Artwork** option becomes obsolete under this model. Retire that UI/runtime restriction when Media joins the child-role system and allow landscape geometry unconditionally; do not carry it forward as a competing CUSTOM-era authority.

## 3. Role-based opt-in only

Only important visual roles may opt in. Do **not** expose arbitrary labels, separators, metadata rows, buttons, or every QML child to freeform resizing.

Initial candidates:

- **Media:** main artwork, volume bar and seek bar. Media playback controls are admitted only as one grouped `transport_controls` role (previous / play-pause / next resize together); never persist or resize individual transport buttons. The existing system-mute control remains authored unless separately justified.
- **Achievement Pulse:** three deliberate roles: primary artwork, latest-achievement badge, and progress circle. The **artwork frame itself is freeform on X/Y**; the source image must never distort and continues to use the family's existing native-aspect fill/zoom/crop policy inside whatever rectangle CUSTOM creates. Badge and progress circle are intrinsic-shape roles and remain uniform/aspect-locked.
- **Abandonment Issues / future Steam cards where appropriate:** primary artwork role.
- **Friend Pulse:** avatar role, shared across **all avatars at once** so alignment, spacing, row/grid rhythm and clipping remain coherent.
- **Weather:** condition/hero icon if the final interaction remains useful after the shared implementation exists.
- **Clock analogue only:** separator role and Roman-numeral role are candidates. Each role changes as one grouped set: all analogue separators together, all Roman numerals together. Digital mode has no such child role and must not acquire hidden/dormant geometry state for one.

The framework should make future widgets opt in declaratively by role/axis/policy rather than requiring a new controller per family. Freeform artwork geometry uses the shared `freeform_artwork_child_role(...)` contract so Achievement, Abandonment/future Steam artwork and Media inherit the same X/Y frame semantics without sharing or waking their provider/image owners.

### Child-handle admission

Do **not** show every child handle merely because global Edit mode is active. The default interaction is two-stage: global Edit mode exposes the ordinary parent frame; clicking/selecting that parent enters child-edit focus for that widget and reveals only its admitted child-role handles. Clicking another parent transfers focus; leaving Edit mode clears it. This keeps dense widgets readable, bounds hit-testing to one family at a time, and avoids persistent overlay clutter/cost. Child handles should be visibly smaller than outer-widget handles while preserving a practical pointer target, preferably by separating the drawn handle size from its transparent hit target. No polling or hover scan is required; selection is event-owned retained state. Prefer one active child-handle layer/Loader for the selected parent rather than instantiating hidden child handles for every widget in Edit mode.

The shared parent-selection primitive is session-owned rather than display-QML-owned, so dual-display Edit cannot expose two unrelated focused parents at once. Focused edit chrome may fade **in** with a short event-triggered QML opacity animation. The animation driver runs only for that brief transition and then stops; do not use a Timer, recurring hover probe or per-frame Python publication to create the effect.

### Outer two-axis reflow affordance

Keep the established square outer corners exactly as authored: they remain uniform whole-widget scale, and side strips remain one-axis `content_extent`. A separate lighter-blue **diagonal** corner affordance may adjust horizontal + vertical `content_extent` together at constant uniform scale. It uses distinct semantic handle ids and the same Python CUSTOM geometry owner, never a QML-owned rect.

The diagonal is an **inside-corner bridge** between the two admitted blue side strips, not external edit chrome. Its visible line and hit wedge stay inside the selected card's corner breathing room. It is admitted only for the selected ordinary parent and only when both content axes are available. Suppress a corner when that inward wedge overlaps another widget, edit glyph, adjustable handle/child control, or another declared interactive exclusion; non-interactive headers are not exclusions. Collision admission is driven by edit selection/geometry changes only; never continuously scan the scene at render cadence. The shared exclusion mechanism should grow with child-role admission rather than introducing a scene-wide pointer probe.

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
- whether the role is singular or group-scoped (for example all Friend Pulse avatars, all analogue Clock Roman numerals, or all analogue Clock separators).
- the resize handle corner(s) that match the family's retained anchor. Do not show four decorative corners when only one can physically follow the pointer without introducing child-position state. The Python descriptor is the handle authority and the edit overlay queries it only for the selected parent.

Save/Cancel/slots must round-trip the same shared child-geometry payload. Reset Child Size restores only that role to the authored baseline. Existing Restore Size for the **outer widget** remains an outer-geometry action and must not silently erase child overrides; neither reset path should secretly mutate the other.

### Persistence / Settings SSOT

Child geometry does **not** get a new file, database or family-local Settings key. It rides inside the existing canonical `widgets.custom_layout` structured root persisted by `SettingsManager` to the profile `settings_v2.json` (`%APPDATA%\SRPSS\settings_v2.json` for the normal Screensaver profile; the MC profile uses its existing `SRPSS_MC` sibling). Each display/widget/geometry-variant CUSTOM entry already owns a `size_payload`; normalized child factors live under `size_payload.child_geometry`. The existing `custom_layout_restore` root continues to own authored route restoration metadata. This keeps one persisted Settings authority and lets Save/Cancel/layout slots/cross-display hydration use the same CUSTOM contract rather than inventing a second child-geometry store.

## 5. Reflow / overflow contract

The family must consume the child size through its existing layout flow. Do not implement a general collision engine or per-widget `if collision then move X by N` bureaucracy.

- If the resized child still fits inside the current card, neighboring content reflows/redistributes using the family's normal authored minimum padding/spacing.
- If the child grows beyond available room, the family may raise its required logical `content_extent`; the existing outer CUSTOM owner decides the outer geometry response.
- **Growth may expand the outer widget when required. Shrinking a child must not automatically shrink the outer widget.** The user can separately reclaim outer space. This avoids pointer/geometry feedback loops during editing.
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

## 8. Build order

1. **Done / operator-validated:** shared `content_extent` outer-growth semantics across current resizable ordinary families.
2. Establish session-owned parent selection + focused edit chrome once (done), then add shared role/session/persistence child geometry without a family-local owner (done for the foundation). Role descriptors now also own the physically valid resize handle corner(s); QML asks the selected parent's descriptor rather than assuming four corners.
3. **Achievement Pulse proof slice implemented, pending physical/Qt validation:** primary artwork is a freeform X/Y frame with native-aspect `PreserveAspectCrop`; the latest-achievement badge and progress circle are intrinsic uniform roles; all three publish one family-wide grow-only content requirement through a stable retained requirement target. Artwork/metric/title and progress/field rails reflow from the resolved child geometry. The family model batches child geometry behind a dedicated geometry signal so drag samples do not broadcast unrelated state changes.
4. **Steam Settings authority normalization implemented, pending Qt validation:** the old section-wide Steam CUSTOM lock is split into Achievement / Abandonment / Friend Pulse widget scopes. A warning now restores only the affected widget family, not every CUSTOM widget. Future Steam cards add their own lock descriptor rather than expanding a shared Steam blob.
5. **Friend Pulse grouped-avatar proof implemented, pending physical/Qt validation:** one `avatars` intrinsic role persists one scalar for every avatar in both Rows and Grid. Grid column admission and row/grid spacing consume the chosen footprint; no per-avatar state/provider path exists. Child drag samples emit one narrow geometry signal rather than the broad card state signal.
6. Next prove the mature multi-role case on Media: artwork + seek/volume + grouped transport controls. Media admission also retires `Allow Landscape Artwork` and applies CUSTOM-wide disabling to artwork size/shape controls without changing Media provider dormancy.
7. Add family roles incrementally only after the shared behavior is green and physically sane.
8. Add commit-time artwork quality escalation through existing image owners.
9. Extend to Clock analogue grouped roles and Weather only after their family-specific semantics are proven to fit the shared primitive without new ownership.
