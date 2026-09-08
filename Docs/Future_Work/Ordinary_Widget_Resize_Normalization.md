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
Weather temperature. Only the temperature is now 81% of the condition font size (two successive 10%
reductions); location/temperature glyph left edges are font-metric aligned;
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
- `weather_aligned_temperature_81`: final alignment and second temperature reduction; all 48 Weather
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
The shrink feature below is explicitly activated by the user and is being implemented.

## Non-CUSTOM auto-shrink — implemented, physical validation open

`build_display_auto_scale_plan` wraps the existing display packer. Full-size stacking
runs first and is returned unchanged whenever it fits. Otherwise the unresolved
eligible cards get descending 1% size trials down to 80%, each through the same
placement solver. If those cards alone cannot fit, all eligible cards participate.
Once a fit exists, individual cards are restored toward 100%, accepting growth only
with a newly proved collision-free placement. The deterministic search is bounded;
it does not assume greedy packing success is monotonic or claim global optimality.

The presenter applies accepted positions and dimensions together. Geometry is
recomputed from authored baselines on existing admission/size/topology/layout events;
no timer, Settings field, cadence owner or independent placement engine is added.
Clock remains ineligible, and fixed Media/Visualizer relationship obstacles retain
their geometry. Whole-card families use their existing transform, shadow and glow.

The automatic floor is 80%. When no complete fit above that floor is found, the
original full-size plan and its explicit unresolved diagnostic are retained rather
than shrinking unsuccessfully or clipping/hiding widgets. This limit needs operator
review against real crowded layouts; it is not a promise that every possible widget
set fits every screen.

Global CUSTOM disables the planner. First Edit captures the actual retained outer
rectangle (not the binding's authored-size cache), preserving both position and
shrunken footprint; the existing absolute CUSTOM scalar is inferred from that visible
rectangle. Explicit Save then authors the accepted working layout, while Cancel and
ordinary reflow preserve Settings-owned baseline values. More room restores full size.

Evidence: `tests/test_widget_auto_shrink.py` covers the full-size path, selective/joint
shrink, 10px clearance, largest tested fit, fixed obstacles, growth and impossible
floor. `tests/test_qtquick_resize_normalization.py` crosses the real presenter,
preferred-size reflow and Edit/Cancel boundary. The maintained packing companion
`tools/ordinary_widget_stack_capture.py` captures real Quick cards before/after
crowding and after restoration. `logs/widget_auto_shrink/packing_v1` has zero Qt
warnings: Abandonment stays 100%, Achievement fits at 83%, Weather at 88%; all return
to 100% when the budget grows. Resulting card proportions and clearance were visually
inspected. Mixed-DPR/live operator packing remains in the checklist above and Current_Plan.
