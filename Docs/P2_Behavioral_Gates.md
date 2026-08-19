# P2 Behavioral Gates — Third-Run Architecture Recovery

Installed behavior remains authoritative.

---

## Gate 1 — Spectrum paused idle

Real renderer produces perceptible resting bars without fake source authority.

Status: GREEN. Retain permanently.

---

## Gate 2 — all visualizer modes reveal and remain reactive

All five modes:
- reveal;
- switch;
- react;
- survive Pause/Play;
- survive Settings/recreate.

No mode-specific cadence cuts.

---

## Gate 3 — logical cadence

Ordinary authored visualizer cadence:
- ~90 Hz class;
- >=88 Hz average;
- <=2% skipped deadlines;
- no recurring unexplained >33 ms holes.

No FIFO/catch-up.

---

## Gate 4 — worker logical code remains GUI/GL-free

No QWidget/QPixmap/QPainter/GL/QRhi mutation from worker-callable logical paths.

---

## Gate 5 — exactly one logical clock

`VisualizerLogicalRuntime` remains the sole mode-general simulation owner.

No replacement GUI logical timer.

---

## Gate 6 — generation/activation fencing

Generation zero remains valid.

Stale generation/activation state cannot become visible after replacement.

---

## Gate 7A — transport commands do not block GUI

Slice K property:

- mouse command submission returns immediately;
- backend executes on IO owner;
- no GUI wait;
- no duplicate command pileup.

Status: source property GREEN.

This does not imply perceptual Pause/Play acceptance.

---

## Gate 7B — Pause/Play perceptual acceptance across input methods and modes

Must pass through:
- mouse control;
- physical media key.

Must pass in:
- Bubble;
- Spectrum;
- Devcurve;
- remaining visualizer modes.

No visible freeze/hitch.
No visualizer recreate.
No playback debounce.

Current status: RED.

---

## Gate 7C — feedback production paint cost

One ordinary animated feedback event must not produce frame-count-scale expensive parent-card painting.

The existing “five named subpainters skipped” gate is insufficient by itself.

A production-shaped gate must measure/observe the real parent paint ownership under ordinary Qt update/coalescing behavior.

Current status: RED.

---

## Gate 8 — steady-state logical publication does not marshal one GUI callback per state

Drive many dedicated-runtime logical publications.

Prove:
- mailbox revision advances;
- ordinary publications do not enqueue one `present_logical_frame`/equivalent GUI callback each;
- no replacement 90 Hz GUI timer exists;
- no backlog forms.

Negative control must reproduce the old callback-per-publication behavior and fail.

---

## Gate 9 — physical presentation samples latest logical state

When logical producer is faster than physical consumer:

- presentation applies newest current-generation revision;
- intermediate stale revisions are not replayed;
- no FIFO/catch-up;
- state age remains bounded;
- generation/activation fences apply.

---

## Gate 10 — two-display independence

Controlled 60 Hz visualizer + 165 Hz other display:

- logical producer does not impose ~90 GUI callbacks/s;
- 60 Hz visualizer samples freshest state at its opportunities;
- 165 Hz display remains independently serviceable;
- no shared queue/lock couples display cadence.

---

## Gate 11 — explicit edge handoffs remain correct

Mode reveal/hide, Pause/Play state edges, Settings/recreate and lifecycle changes may marshal bounded GUI work.

Prove:
- required edge GUI mutation still occurs;
- no continuous callback stream is reintroduced;
- no stale reveal;
- no second logical clock.

---

## Gate 12 — slow-tick diagnostics cannot fail the logical runtime

Force slow-tick logging.

No `NameError`.
No exception.
No logical-runtime failure increment.

---

## Gate 13 — Bubble Temporal Fidelity

Use `Docs/Guardrails/Bubble_Temporal_Fidelity.md`.

Bubble remains a canary, not special-cased optimization target.

---

## Gate 14 — 165 Hz shared presentation

Installed target remains recovery toward the historically accepted low/mid-150 FPS class.

The current ~65–130 FPS collapse and ~55–80% request-acceptance class is RED.

Do not lower target.

---

## Gate 15 — 60 Hz visualizer presentation

No visible stepping.

No recurring rejected-class frame gaps.

---

## Gate 16 — lifecycle

Settings/recreate/shutdown:
- quiesce/join logical runtime;
- preserve one compositor surface/display;
- preserve fences;
- leave no orphan producer;
- preserve Spectrum idle.

---

# Current state

Green/retained:
- Spectrum idle;
- generation zero;
- dedicated logical-clock ownership;
- K non-blocking transport submission.

Red/open:
- Pause/Play perception;
- all-mode visualizer smoothness;
- feedback production cost;
- steady-state callback pressure;
- 165 Hz delivery;
- 60 Hz tails;
- BTF tails;
- diagnostic exception path.
