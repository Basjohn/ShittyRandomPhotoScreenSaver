# CUSTOM Editable Child Geometry

Status: **planned next after the 2026-09-18 ordinary-widget `content_extent` rollout is validated; implementation has not started**.

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

When CUSTOM owns an opted-in child size, the corresponding authored size control in Settings must be disabled rather than allowed to fight the presentation override. Reuse and normalize the existing **"Disable Custom To Adjust!"** UI pattern so it is consistent wherever CUSTOM supersedes an authored size control.

- Authored Settings values remain preserved underneath as the baseline/fallback; CUSTOM never destroys them.
- Clearing/resetting that child override restores Settings as the active authority.
- Controls unrelated to the overridden child remain usable.
- This is the same ownership principle as disabling stacking while global CUSTOM placement owns geometry.

## 3. Role-based opt-in only

Only important visual roles may opt in. Do **not** expose arbitrary labels, separators, metadata rows, buttons, or every QML child to freeform resizing.

Initial candidates:

- **Media:** main artwork, volume bar and seek bar. Media playback controls are admitted only as one grouped `transport_controls` role (previous / play-pause / next resize together); never persist or resize individual transport buttons. The existing system-mute control remains authored unless separately justified.
- **Achievement Pulse / Abandonment Issues / future Steam cards where appropriate:** primary artwork role. Achievement Pulse badge/circle is also an explicit candidate role.
- **Friend Pulse:** avatar role, shared across **all avatars at once** so alignment, spacing, row/grid rhythm and clipping remain coherent.
- **Weather:** condition/hero icon if the final interaction remains useful after the shared implementation exists.
- **Clock analogue only:** separator role and Roman-numeral role are candidates. Each role changes as one grouped set: all analogue separators together, all Roman numerals together. Digital mode has no such child role and must not acquire hidden/dormant geometry state for one.

The framework should make future widgets opt in declaratively by role/axis/policy rather than requiring a new controller per family.

### Child-handle admission

Do **not** show every child handle merely because global Edit mode is active. The default interaction is two-stage: global Edit mode exposes the ordinary parent frame; clicking/selecting that parent enters child-edit focus for that widget and reveals only its admitted child-role handles. Clicking another parent transfers focus; leaving Edit mode clears it. This keeps dense widgets readable, bounds hit-testing to one family at a time, and avoids persistent overlay clutter/cost. Child handles should be visibly smaller than outer-widget handles while preserving a practical pointer target, preferably by separating the drawn handle size from its transparent hit target. No polling or hover scan is required; selection is event-owned retained state. Prefer one active child-handle layer/Loader for the selected parent rather than instantiating hidden child handles for every widget in Edit mode.

## 4. Geometry and normalization

Persist normalized logical child geometry, never raw device pixels. The exact representation may be a factor relative to the authored child baseline or another shared logical representation, but it must survive display/DPI/outer-widget changes without turning physical pixels into authority.

A role declares, at minimum:

- stable role id;
- allowed axes (uniform or X/Y as appropriate);
- authored baseline geometry/size;
- bounded minimum/maximum policy;
- whether a single override applies to one item or a whole repeated group;
- whether overflow contributes to outer `content_extent`;
- whether the role is singular or group-scoped (for example all Friend Pulse avatars, all analogue Clock Roman numerals, or all analogue Clock separators).

Save/Cancel/slots must round-trip the same shared child-geometry payload. Reset Child Size restores only that role to the authored baseline. Existing Restore Size for the **outer widget** remains an outer-geometry action and must not silently erase child overrides; neither reset path should secretly mutate the other.

## 5. Reflow / overflow contract

The family must consume the child size through its existing layout flow. Do not implement a general collision engine or per-widget `if collision then move X by N` bureaucracy.

- If the resized child still fits inside the current card, neighboring content reflows/redistributes using the family's normal authored minimum padding/spacing.
- If the child grows beyond available room, the family may raise its required logical `content_extent`; the existing outer CUSTOM owner decides the outer geometry response.
- **Growth may expand the outer widget when required. Shrinking a child must not automatically shrink the outer widget.** The user can separately reclaim outer space. This avoids pointer/geometry feedback loops during editing.
- Side-axis `content_extent` and corner/wheel whole-card scale remain the one outer sizing authority.

## 6. Artwork quality handoff

A committed CUSTOM artwork-size change may require a larger source than the currently retained texture. On **Save/commit** (not every drag tick), artwork-backed roles must be able to request the existing image/artwork owner to resolve an appropriately sized source and crossfade from the retained current image into the higher-quality replacement when it is ready.

Requirements:

- preserve the existing **original aspect-ratio rules** and each family's accepted crop/fit semantics;
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

1. Finish `content_extent` on all currently outstanding ordinary-widget families and validate its shared outer-growth semantics.
2. Add the shared role/session/persistence/edit-affordance primitive once.
3. Prove it on one or two mature families (Media is the strongest multi-role candidate: artwork + seek/volume bars; Friend Pulse proves grouped repeated roles).
4. Add family roles incrementally only after the shared behavior is green and physically sane.
5. Add commit-time artwork quality escalation through existing image owners.
6. Extend to Clock analogue grouped roles and Weather only after their family-specific semantics are proven to fit the shared primitive without new ownership.
