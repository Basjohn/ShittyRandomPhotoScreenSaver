# Ordinary Widget Resize Normalization

Implementation complete; physical validation remains open. The durable authoring
contract is [Ordinary Widget Authoring Guide](../10_WIDGET_GUIDELINES.md).

## Landed contract and acceptance

Abandonment Issues, Achievement Pulse and Weather now use the shared whole-card
`uniformScaleTransform`. CUSTOM captures geometry only; replay of older current-format
per-value payloads cannot rewrite product Settings or the preferred baseline.
Clock remains the justified variant-aware per-value exception; Visualizer retains its
independent viewport/visual-scale contract. New ordinary cards use `ordinary_uniform`.

Steam retains its authored model dimensions. Weather width is the maximum of its
600px floor and intrinsic primary text/icon width plus shell/horizontal/text insets;
height is intrinsic ready-column height plus shell and symmetric vertical insets.
Separator layout height stays 1px while its painted stroke remains scale-aware,
removing scale feedback through preferred height. `readyContentFitScale` is unchanged.

The user explicitly accepted Steam whole-card sizing and the shown Weather result,
confirmed no excessive side/top blank space, and requested a slightly smaller
Weather temperature. Only the temperature is now 90% of the condition font size;
the condition text remains full size on the same wrapped, baseline-aligned line.
That requested normal-size typography change is intentional, superseding the
original strict unchanged-pixel gate for this label.

## Evidence

The maintained [capture/compare harness](../Ordinary_Widget_Resize_Capture.md) is
retained for long-term use. Evidence under `logs/widget_resize_normalization/`:

- `settled_before`, `settled_repeat`: 112 cases, identical geometry; all 14 normal
  cases within measured 2-channel rendering variation.
- `uniform_candidate`: reviewed whole-card proposal; Steam normal cases within
  that variation. Weather long-location had a repeatable 4-channel text-edge delta
  at identical geometry, disclosed during review before user acceptance.
- `weather_temperature_richtext`: final requested temperature size; all 48 Weather
  states/envelopes captured at DPR 1.5 with zero Qt warnings. Normal, 75% and long
  location results visually inspected; no added card padding.
- `tests/test_qtquick_resize_normalization.py`: real retained host stale replay,
  repeated resize, two live Saves/Cancel, current-format serialized stale entry,
  hydration, untouched Save/reconstruction twice, numbered-slot replay; all three
  families preserve Settings, preferred baseline and absolute ~40% geometry.
  The adapter deliberately reports synchronous size during `bind_families`.

## Awaiting Validation — operator topology and interaction

- [ ] Aggressive live Weather CUSTOM resize/reposition, cross-display movement and
  runtime recreation: confirm no preferred-height binding-loop warnings.
- [ ] Check transformed tooltip/info-icon hit targets, hover/click actions and
  interaction glow/external shadow alignment at small and large scales.
- [ ] Mixed-DPR Windows displays (~100/125/150/200% where available): inspect thin
  borders, clipping, half-pixel centring, edit handles and dead-axis envelope replay.
  DPR 1.5 automated captures do not replace this physical gate.

No timers, polling, additional geometry owners or Settings defaults were introduced.
The deferred shrink feature below remains separate and unimplemented.

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

Operator clarification (2026-09-08): stacking must get the first opportunity to
fit authored-size cards. Only unavoidable post-stacking collisions admit shrink.
Every trial must re-run placement with its new footprints, and apply the resulting
positions together with the accepted scales; shrinking at old stacked positions
wastes the space it freed. Validate clearance as well as intersection so cards do
not touch. Prefer the largest fitting cards and avoid shrinking unaffected cards
unnecessarily. Recompute from authored sizes on each layout event, never from a
previously shrunken result. Bound the search deterministically; a greedy placement
solver need not have monotonic success as scale changes, so do not assume an
unchecked binary search proves the best fit. No polling or second placement owner.

The auto-scale must be **presentation state, not authored state**: non-CUSTOM only;
transient/derived from the current logical display budget; never persisted as
family font/artwork/icon Settings or as CUSTOM-authored geometry. Entering Edit
must preserve the visible position/footprint while transferring authority; do not
reset to 1.0 before capture and cause another entry jump. Define explicit conversion
of the visible footprint into session geometry when this feature is implemented.
Auto-scale is recomputed only on real layout/topology/preferred-size
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
