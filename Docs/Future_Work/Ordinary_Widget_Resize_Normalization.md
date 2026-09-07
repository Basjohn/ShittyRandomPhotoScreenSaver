# Ordinary Widget Resize Normalization → one uniform-transform seam

Live-checklist plan. Delete items as they land; this is not a changelog.

Verified against current source (post settings-migration / dark.qss-plan era,
`rendering/quick/custom_layout_size.py`, `rendering/widget_descriptors.py`, the
family QML in `rendering/quick/qml/`). Where an older handoff cited a bare commit
hash, it has been replaced by the named owners below so the plan does not rot.

## Purpose (and the point of doing it)

Three ordinary-widget families still resize under CUSTOM by *manufacturing a
per-value size payload* (font/icon/artwork sizes) that temporarily behaves like a
second Settings authority. The rest of the ordinary families already resize as a
single whole-card geometric transform. This plan moves the stragglers onto that
one seam so **CUSTOM resize is geometry-only for every ordinary widget**.

The reason this is worth doing is not tidiness. The uniform seam is what makes a
**new ordinary widget almost free to add**: declare a truthful authored baseline
in QML, opt into the shared transform, classify the descriptor as geometry-only,
and the widget gets correct whole-card CUSTOM scaling, correct shadow/glow bounds,
and a 40% floor **for free**, with no payload handler, no `_PAYLOAD_MINIMUMS`
entry, and no risk of CUSTOM editing silently rewriting product Settings. The
per-value path is the thing that makes every new widget expensive and every resize
bug subtle. The end state (C4) is: **uniform transform is the default path; the
per-value payload path is explicitly legacy and shrinking toward Clock alone.**

This is a normalization tranche, not a redesign. Accepted normal (1.0) visuals
are the baseline and must not change.

## The single seam (current architecture, as it actually exists)

One place decides whether a family's CUSTOM resize is geometry-only:

- `rendering/quick/custom_layout_size.py`
  - `UNIFORM_TRANSFORM_RESIZE_MODES` — the frozenset of geometry-only modes.
    **Currently `{reddit_font, media_scale, gmail_font}`.** This is the switch.
  - `is_uniform_transform_resize_mode(mode)` — membership test used everywhere.
  - `capture_quick_size_payload(...)` — returns `{}` for uniform modes; returns a
    per-value dict (`font_size`, `icon_size`, `artwork_size`, …) for the legacy
    modes. **This is where a per-value family stops being one.**
  - `scale_quick_size_payload(...)` — for uniform modes returns the baseline
    unchanged (scale lives in geometry, not values); legacy modes multiply each
    value by scale against `_PAYLOAD_MINIMUMS`.
  - `quick_custom_payload_minimum_scale(...)` — legacy families get a
    value-driven floor; uniform families return `0.0` (the shared 40% floor from
    the R-67 absolute-scale contract governs them instead).
- `rendering/widget_descriptors.py` — each descriptor's
  `custom_layout_resize_mode` string selects the branch above.
- `rendering/quick/qml/OverlayWidget.qml` — `uniformScaleTransform`,
  `preferredContentWidth/Height`, derived `presentationScale`. When enabled the
  authored root stays at its baseline coordinates and the whole card is scaled and
  centred (letterboxed on aspect mismatch); external shadow and interaction glow
  track the transformed card.

### Current classification (verified)

| Family | descriptor mode | QML `uniformScaleTransform` | resize path |
|---|---|---|---|
| Reddit / Reddit2 | `reddit_font` | yes | **uniform (done)** |
| Media | `media_scale` | yes | **uniform (done)** |
| Gmail | `gmail_font` | yes | **uniform (done, R-70)** |
| Abandonment Issues | `steam_card_scale` | **no** (local `contentScale`) | per-value → **C1** |
| Achievement Pulse | `steam_card_scale` | **yes** (already) | per-value → **C2** |
| Weather | `weather_scale` | no | per-value → **C3** |
| Clock | `clock_font` | no | **legacy, keep** (variant-aware) |
| Visualizer | `visualizer_rect` | n/a | **rect resize, keep** |

Two facts an earlier handoff missed, both load-bearing:

1. **Abandonment and Achievement share the `steam_card_scale` mode string.**
   `capture_quick_size_payload` tells them apart only by
   `hasattr(config, "square_artwork_size")` (Achievement) vs `artwork_size`
   (Abandonment). You cannot flip `steam_card_scale` into the uniform set for one
   without the other. C1 and C2 therefore either **land together**, or the mode is
   **split into two distinct strings first** (recommended — see C1/C2). They are
   not independently sequenceable as written.
2. **Achievement is already half-migrated**: its QML has
   `uniformScaleTransform: true` and authored-baseline `preferredContent*`, yet its
   descriptor is still `steam_card_scale`, so it still captures/replays a per-value
   payload. C2 is mostly a descriptor + payload-path change, not a QML rebuild.

## Invariants (binding for this tranche)

- Accepted normal (1.0) visuals are the baseline; this is not a redesign.
- No timers/polling merely to observe geometry or layout state.
- No fallback presenter and no second scale owner. One Python/session
  outer-geometry owner; one presentation-scale owner.
- Global CUSTOM is a hard boundary: ordinary stacking is dormant while CUSTOM is
  active.
- Geometry-only CUSTOM resize must **not** rewrite genuine family product
  Settings, and must not add defaults just because an old payload key disappeared.
- The persisted CUSTOM layout payload is layout-transaction state, **not**
  canonical-default/schema authority. Removing/reclassifying a payload key
  requires proving every current consumer and replay path — do not repeat the
  defaults-sanitization mistake of deleting a live contract without an owner.
- Live geometry-only Save stays in-generation; explicit topology/slot transactions
  still use the existing fenced reconciliation path.
- Visualizer cadence/reactivity/viewport scaling is sacred and out of scope.
- Do not normalize Clock for symmetry; do not touch widget on/off, monitor
  routing, Follow Media, or unrelated defaults.

## Feasibility of visual parity (assessment)

- **Normal 1.0 parity — high confidence, all three.** At 1.0 the uniform transform
  is identity, and Abandonment's local `contentScale = min(w/aw, h/ah)` is the same
  ratio the shared transform computes, so removing the local scale is a no-op at
  1.0. Achievement already renders through the transform. Weather at 1.0 is its
  authored layout unchanged. 1.0 identity is the mandatory gate and is achievable.
- **New whole-card CUSTOM (non-1.0) — high confidence.** This is the intended new
  behaviour and matches the already-migrated families.
- **Exact *historical* resized-CUSTOM pixels — variable, and not always a
  requirement.** Old saves scaled *selected* model values while fixed insets
  stayed put; whole-card scaling scales the whole relationship. So:
  - Abandonment: closest, because it is already one authored canvas under one
    local scale. Any visible delta needs explanation.
  - Achievement: old payload scaled `font_size` / `square_artwork_size` /
    `capsule_font_size`, which feed authored height/capsule/artwork formulas — old
    saves may differ. Measure, do not auto-bless or auto-reject.
  - Weather: `readyContentFitScale` plus fixed `legacy*Inset` constants mean old
    0.75× and new 0.75× are **not guaranteed** identical even when both look good.
    Exact historical parity is explicitly *not* required for Weather (Gate D); a
    coherent, user-accepted whole-card result is.
- **The real per-family hazard is the truthful baseline rectangle (R-70).** Whole-
  card scaling is only correct if `preferredContentWidth/Height` are truthful per
  axis. Gmail needed `preferredContentHeight = contentHeight + shellInset` while
  width was already the outer width; naive `+2*padding` on both axes double-counted.
  Each family below must state where its truthful baseline comes from **before**
  flipping the mode.

## Work plan

### C0 — Baseline evidence harness (do first)

- [ ] Stand up a deterministic retained-Quick capture (QuickSceneFactory / retained
      host, fixed family model fixture, fixed `QQuickWindow` logical geometry,
      `grabWindow()`/`grabToImage()` → PNG). If PySide6/Qt is unavailable in the
      agent environment, mark visual acceptance **OWED** rather than pretending
      static checks prove pixels.
- [ ] Capture matrix per family at `1.00, 0.75, 0.50, 1.40, 2.00` and aspect
      envelopes `0.75w×1.00h, 1.00w×0.75h, 1.25w×0.80h`.
- [ ] Record the geometry/property ledger (see Verification protocol) for each.

### C1 + C2 — Abandonment Issues + Achievement Pulse (joint, `steam_card_scale`)

Because both families share `steam_card_scale`, do this as one slice. Recommended
first step is to **split the mode** so the classification is honest and each family
can carry a truthful baseline:

- [ ] Split `steam_card_scale` into distinct descriptor modes (e.g.
      `abandonment_card` and `achievement_card`) in `rendering/widget_descriptors.py`,
      or confirm both are ready to flip in the same commit. Prove the
      `hasattr(...square_artwork_size...)` branch in `capture_quick_size_payload`
      has no other caller before removing it.
- [ ] **Abandonment (C1):** remove the local `contentScale` scale/centre on the
      authored canvas in `AbandonmentIssuesPresentation.qml`; opt into
      `uniformScaleTransform: true`; keep `preferredContentWidth/Height =
      authoredWidth/authoredHeight` (already symmetric/truthful). Retain a scale
      value for `scaleAwareStrokeWidthForScale` — prefer the shared
      `presentationScale`, or a mathematically identical derived value only if
      unchanged code needs it. Do **not** mutate family Settings to compensate.
- [ ] **Achievement (C2):** keep the existing QML transform; reclassify the
      descriptor to geometry-only; stop capturing/applying the per-value payload;
      retain all authored model formulas, QML coordinates, border/crop/interaction
      behaviour. Confirm its `preferredContent*` baseline is truthful per axis.
- [ ] Move the family mode(s) into `UNIFORM_TRANSFORM_RESIZE_MODES`; confirm
      `capture_quick_size_payload` now returns `{}` and `scale_quick_size_payload`
      returns geometry-only for them.
- [ ] Do **not** delete the real product config keys (`font_size`,
      `square_artwork_size`, `capsule_font_size`, `artwork_size`) from canonical
      family Settings. Only CUSTOM geometry stops scaling/replaying them.
- [ ] Prove stale historical `steam_card_scale` payloads cannot perturb the
      preferred baseline on committed replay (Verification §7).
- [ ] Gates A/B/C + non-1.0 delta inspection; user acceptance of any non-1.0 delta.

### C3 — Weather (`weather_scale`)

- [ ] Confirm the truthful baseline: Weather's `preferredContentWidth` floors at
      `600` and includes `legacyHorizontalInset`/`legacyTextInset`;
      `preferredContentHeight` includes `legacyVerticalInset`. State the exact
      per-axis source before flipping (R-70 lesson).
- [ ] Opt the complete retained Weather card into `uniformScaleTransform`; preserve
      all accepted QML constants/formulas; **leave `readyContentFitScale` exactly as
      is for the first slice.**
- [ ] Move `weather_scale` into `UNIFORM_TRANSFORM_RESIZE_MODES`; make the per-value
      handler (`font_size`/`icon_size`/`detail_icon_size`) inert for geometry-only
      resize; preserve genuine Weather product Settings keys and normal projection.
- [ ] Gate D decision: if 1.0 is exact but old resized-CUSTOM output differs,
      document the measured delta, get user acceptance, and **revert C3** (keep
      Weather on its existing path) if rejected. Do not fake parity with a second
      compensating scale, and do not contaminate C1/C2 acceptance with a Weather
      exception.

### C4 — Make new widgets easy (the point) + demote legacy

This phase is what turns the migration into a durable capability rather than three
one-off ports. Do not skip it — without it the ease-of-new-widgets outcome is
implicit and will erode.

- [ ] Make uniform-transform the **documented default** for new ordinary widgets:
      add the New-widget checklist below to the widget-authoring reference, with a
      minimal QML skeleton (authored baseline + `uniformScaleTransform: true`) and
      a descriptor example whose mode is a member of
      `UNIFORM_TRANSFORM_RESIZE_MODES`.
- [ ] Rename `UNIFORM_TRANSFORM_RESIZE_MODES`'s docstring/comment to state it is the
      default path and that per-value modes are the shrinking legacy exception.
- [ ] After C1–C3 land, the only per-value modes left should be `clock_font`
      (legitimate variant-aware) and the `visualizer_rect` special case. Add a
      focused test that asserts no *new* per-value mode is introduced without an
      explicit legacy justification (guard against regression to per-value).
- [ ] Cleanup (Gate E only): remove the now-dead `steam_card_scale`/`weather_scale`
      per-value branches and their `_PAYLOAD_MINIMUMS` entries **only** after all
      migrated callers are proven, stale-payload replay is proven safe, focused
      coverage owns the new contract, and no unrelated family shares the branch.
      No cleanup-by-symmetry.

## New-widget checklist (what the normalization unlocks)

Once C4 lands, adding a new ordinary widget with correct CUSTOM resize is:

1. QML: give the presentation a truthful authored baseline —
   `preferredContentWidth/Height` set to the real outer card size **per axis**
   (R-70: inspect what your model already includes on each axis; do not blanket-add
   padding), lay out authored children in those baseline coordinates, and set
   `uniformScaleTransform: true`. Do **not** add a local content-scale transform.
2. Descriptor: set `custom_layout_resize_mode` to a geometry-only mode that is a
   member of `UNIFORM_TRANSFORM_RESIZE_MODES`.
3. Strokes: use `scaleAwareStrokeWidthForScale(..., presentationScale)` for thin
   strokes so they stay legible at small scale.
4. Nothing else. No `capture_quick_size_payload` branch, no `_PAYLOAD_MINIMUMS`
   entry, no payload handler, no Settings coupling. Whole-card CUSTOM scaling,
   centred letterboxing, shadow/glow bounds, and the 40% floor come for free.

A widget only leaves this path if it genuinely needs per-value behaviour (Clock's
variant-aware `clock_font`) or rect resize (`visualizer_rect`) — and that is a
deliberate, justified exception, not the default.

## Risk / decision gates

- **Gate A — architecture legitimacy** (before touching a family): one outer-geometry
  owner remains; one presentation-scale owner remains; family has a stable
  authored/preferred baseline; no service/runtime/provider behaviour changes; no
  Settings/default schema change is required. Fail → do not normalize.
- **Gate B — normal parity** (at 1.0): pixel identity; authored coordinates,
  preferred size, shadows/glow/hit bounds unchanged. Fail → revert the slice.
- **Gate C — CUSTOM replay:** synthetic old payload + saved-layout replay must not
  compound scale, mutate family Settings from geometry editing, shift the preferred
  baseline repeatedly, create a second geometry authority, or require a fallback.
- **Gate D — user-visible old-CUSTOM difference** (Achievement/Weather): a measured
  non-1.0 delta is neither automatically a bug nor automatically acceptable —
  user decides; if they want the exact old partial-scale look, keep that family on
  its existing payload path; never fake parity with a compensating scale.
- **Gate E — cleanup admission:** remove old branches only after all migrated
  callers are proven, stale replay is safe, focused coverage owns the contract, and
  **no unrelated family shares the branch** (directly relevant: `steam_card_scale`
  is shared by two families).

## Visual-parity verification protocol (mandatory evidence for C0–C3)

**Baseline must exist before edits**, captured with the same fixture data, Qt
build, fonts, logical dimensions, DPR, theme/shadow config, and enabled state.
Never regenerate/bless a baseline merely because output differs.

- **Scale-1 rule:** normal/non-CUSTOM 1.0 output must be visually identical — same
  dimensions, zero changed pixels on the same machine. Only if repeated
  unchanged-baseline captures prove AA nondeterminism, permit a narrowly
  demonstrated tiny edge tolerance — never a broad threshold that could hide a
  1–3 px geometry regression.
- **Geometry/property ledger per capture:** outer x/y/w/h;
  `preferredContentWidth/Height`; `uniformScaleTransform`; `presentationScale`;
  card shadow visual x/y/w/h; interaction glow x/y/w/h; authored canvas
  x/y/w/h/scale; header/logo geometry; artwork geometry; major text block
  geometry/font size; visible border/stroke widths. Weather also:
  `legacyHorizontalInset`, `legacyTextInset`, `legacyVerticalInset`,
  `readyContentFitScale`, ready-column geometry/scale, primary-row geometry,
  condition-icon geometry. At 1.0 geometry must match within ~0.01 logical px;
  intentional differences need explicit explanation and approval.
- **Family state matrix:** exercise the authored-height/fit formulas —
  Abandonment (artwork on/off, portrait/non-portrait, connection icon, tooltip,
  text-heavy, transition settled); Achievement (square/portrait/off artwork,
  recent badge, enough capsule fields, connection icon); Weather (long
  location/condition, condition icon, details row, forecast, missing/config state,
  loading/error/cached, descenders exercising `readyContentFitScale`). Use
  deterministic snapshots; no live network data.
- **Historical CUSTOM replay (§7):** build synthetic *current-format* CUSTOM
  entries carrying the old per-value shapes plus `_custom_resize_scale`
  (Achievement: `font_size`, `square_artwork_size`, `capsule_font_size`;
  Abandonment: `font_size`, `artwork_size`; Weather: `font_size`, `icon_size`,
  `detail_icon_size`). For each: hydrate → verify outer placement → prove stale
  per-value payload cannot mutate the geometry-only family's baseline/preferred
  size → enter CUSTOM → Save untouched → reconstruct → repeat twice → prove no
  `0.4 → 0.16 → 0.064` compounding (R-67 absolute-scale contract) → Cancel restores
  pre-session state → numbered saved-layout load follows the same canonical replay.
  Do **not** turn old payload members into canonical defaults just because a replay
  fixture contains them.
- **CUSTOM boundary:** global CUSTOM disables ordinary stacking; entering CUSTOM
  changes no pixels before user action; the edit frame follows actual visible card
  bounds; geometry-only Save does not rewrite family Settings; Cancel is exact;
  live Save stays retained when topology does not require reconstruction; no
  timer/poller added.
- **Shadows/glow/interaction:** external shadow follows the actual
  letterboxed/scaled card and is not clipped; interaction glow matches the visible
  card; hover/click targets and info icons/tooltips follow transformed
  coordinates; thin strokes stay within the scale-aware visible-thickness contract.
- **DPR / logical display:** use `QScreen.geometry()` / logical layout space; never
  branch on physical labels like "4K". Test effective scales ~100/125/150/200% for
  1 px border rounding, shadow clipping, baseline shifts, half-pixel centring,
  dead-axis envelope persistence, glow/hit-bound mismatch. Real mixed-DPR Windows
  validation is separate from synthetic `QT_SCALE_FACTOR` runs.
- **Checkpoint GREEN** only when: focused current-owner tests pass; scale-1
  geometry/pixels unchanged; non-1.0 deltas inspected; stale-payload replay tested;
  repeated Save/recreate does not compound; no Settings/default ownership
  regression; no polling/timer introduced; user physical acceptance recorded when
  pixels cannot be proven in the agent environment.

Prior art: `Docs/Historical_Bugs/R-70_Gmail_Custom_Uniform_Scale_Preferred_Dimension_Split.md`
(truthful per-axis baseline; do not treat shell inset as generic `+2*padding`) and
`Docs/Historical_Bugs/R-67_Custom_Resize_Reentry_Absolute_Scale.md` (absolute
`_custom_resize_scale` / 40% floor, no compounding).

## Deferred follow-up — bounded non-CUSTOM stacker auto-shrink (NOT C1–C4)

Separate future feature; do not start with the tranche above. But it is the reason
C1–C4 are worth doing: normalization produces the whole-card transform, and this
feature is the consumer that makes that transform pay off. The two are a matched
pair — a widget is only *eligible* to shrink cleanly once it scales as one whole
card (C1–C4); shrinking a per-value family would distort fixed insets/rows.

### The trigger already exists — this is a consumer, not a new solver

The non-CUSTOM display packer is `build_display_stack_plan(...)` in
`rendering/widget_stacking.py`. It is already deterministic and event-edge driven:
each widget tries its authored canonical slot, then nearby slots (same column
before cross-column spill), then a bounded set of edge-derived free-space
candidates. It returns `DisplayStackPlan(placements, all_fit, unresolved)`, and
when **no** collision-free rectangle exists it *keeps the authored rectangle and
records the widget in `unresolved`* (never overlaps, never shrinks today). That
`unresolved` tuple is the exact, existing signal to hang shrink on.

Desired later algorithm (a wrapper around the existing solver — add no second
placement engine, no polling):

1. Run `build_display_stack_plan` at scale 1.0.
2. If `all_fit` (i.e. `unresolved` is empty), stop. **Shrink is gated strictly on
   post-placement collision; never shrink for aesthetics.**
3. If `unresolved` is non-empty, re-run the *same* solver with the eligible
   participants' `DisplayStackParticipant.width/height` multiplied by a trial
   presentation scale (ineligible widgets and obstacles keep their size).
4. Take the largest trial scale that yields `all_fit`, down to a conservative
   product floor (~`0.75–0.80`, subject to physical validation).
5. If still unresolved at the floor, keep the current explicit
   `unresolved`/fail-loud behaviour rather than crushing cards indefinitely.

The auto-scale must be **presentation state, not authored state**: non-CUSTOM only;
transient/derived from the current logical display budget; never persisted as
family font/artwork/icon Settings or as CUSTOM-authored geometry; reset to 1.0
before entering CUSTOM edit; recomputed only on real layout/topology/preferred-size
events. No timer, no polling.

Recompute on the existing event edges that already drive a placement pass:
family admission/removal; preferred-content-size publication; screen
topology/geometry change; authored position change; Media/Visualizer relationship
change; leaving/entering global CUSTOM. **Eligibility = a proven whole-card retained
transform** (the C1–C4 output), which is why the tranche above is the prerequisite.
Do not force Weather/Clock normalization solely to make the stacker symmetrical.
Preserve the stronger Media/Visualizer adjacency contract as a combined obstacle,
and do not alter Visualizer viewport/reactivity to solve display crowding. Use
logical geometry (`QScreen.geometry()`); useful test budgets: 3840×2160, 2560×1440,
2048×1152, 1920×1080, 1707×960, 1600×900, 1536×864, 1280×720, 3440×1440.

Acceptance: 1.0 always preferred; no overlap when a solution above floor exists;
deterministic placement for identical inputs; no Settings pollution; no CUSTOM
pollution; no Visualizer reactivity/cadence change; mixed-DPR user validation.
