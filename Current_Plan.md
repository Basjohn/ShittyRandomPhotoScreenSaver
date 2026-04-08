# Current Plan

Update this after every significant change.

## Guardrails (always active)

- Keep this aligned with [Index.md](Index.md), [Spec.md](Spec.md), [Docs/Defaults_Guide.md](Docs/Defaults_Guide.md), and [Docs/Visualizer_Debug.md](Docs/Visualizer_Debug.md).
- Do not mark runtime or visual-feel issues as fixed without user confirmation.
- Treat `presets/visualizer_modes` as the only authored visualizer preset source tree.
- Treat `release/main_mc.dist/presets/visualizer_modes*` as generated artifacts only.
- Do not introduce Curve again (for Spectrum).
- Do not change render methods or move Spectrum to a non-GL path.
- Do not treat passing tests as visual sign-off.
- Do not make global/shared math changes unless explicitly requested.
- Do not reduce FPS caps below current configured values.
- Whenever dead/dirty/messy/violating/architecturally poor code is discovered during unrelated work, note it here for later cleanup.
- Keep checkboxes honest:
  - `[x]` landed and validated
  - `[~]` partially proven / still needs runtime eyes
  - `[ ]` not done

---

## Snapshot

- **Date:** `2026-04-08`
- **Status:** Spectrum cleanup through 3.1 remains complete. Bubble now has the same shared bucketing treatment as Spectrum, Blob, Oscilloscope, and Sine Wave, and the bucket work has runtime user validation for logic, neatness, and persistence. Reddit Helper remains a real runtime validation problem, while authored planning focus has now shifted back to Spectrum Energy Arrows and related Spectrum cleanup.
- **Organs synthetic:** Green against current authored `Preset 1` (user-modified version).
- **Preset pipeline:** Source tree -> repair tool -> shipped regeneration -> all green.

---

## Completed Work (Historical Summaries)

### H1. Baseline Stabilization (§0)
Preset source tree recovered after revert damage. `core/settings/defaults.py` now returns a normalized visualizer section; `SettingsManager._ensure_widgets_defaults()` canonicalizes fresh insertion. Fresh startup is repair-free. `--fresh` switch clears logs before `setup_logging()`. Commits: baseline recovery + `--fresh` switch.

### H2. Preset / Schema Guardrails (§1)
Documented hard-won lessons: authored source tree vs generated artifacts, AppData drift, baseline commit checklist. `tools/visualizer_preset_repair.py` stays flexible. Curated preset names not hardcoded in tests. Runtime cache is generated state.

### H3. Spectrum Width Reclaim (§2.1)
Reclaimed wasted horizontal side space for BARS and SEGMENTS without overshooting into borders. Regression coverage in `tests/test_spectrum_shaping.py`.

### H4. Replace Single Piece Mode (§2.2)
Removed `Single Piece Mode`, replaced with explicit `SEGMENTS` / `BAR` toggle buttons. `spectrum_render_mode` is canonical key. Runtime bridge translates to older widget boolean. `spectrum_unique_colors` remains the canonical unique-colour key.

### H5. Spectrum Buckets (§2.3)
Replaced loose section headings with real collapsible buckets. Normal: `Appearance`, `Shape`. Advanced: `Render`, `Audio`, `Ghost`. Commit: `ad63b29`.

### H6. Border Colour Participation (§3.1)
Audited why borders were excluded from rainbow. Added `spectrum_rainbow_border` (bool, default `False`) with UI checkbox `Rainbow Borders` in Render bucket. Wired through all 8 layers + shader uniform `u_rainbow_border` in both SINGLE PIECE and SEGMENTED paths. Tests: 92 passed in plumbing suite.

---

## Active Tasks

### 1. Spectrum Energy Arrows (was §3.2)

**Status:** `[ ]` Not started
**Priority:** Medium

Replace redundant Spectrum energy-strength sliders with vertical strength arrows above the energy lanes in the Spectrum Shaper.

- [ ] Write down the exact problem being solved: Spectrum currently splits one mental model across two surfaces
- [ ] Keep the node/notch editor as the owner of spatial placement and lane ownership
- [ ] Move only lane-contribution authoring into the editor; do not smuggle timing/smoothing controls into it
- [ ] Define the 0–100% lane-power contract so arrow travel maps directly to real lane contribution strength
- [ ] Decide whether arrow values are stored by lane label, by normalized lane center, or by layout-specific slot
- [ ] Make mirrored and non-mirrored arrow semantics equivalent even though the visible lane count differs
- [ ] Preserve Organs behavior by measuring against the synthetic fence before and after
- [ ] Record the interaction rationale and mental model in docs
- [ ] Review adjacent Spectrum controls at the same time and feed overlap/redundancy findings into Task 2

Current diagnosis:
- Spectrum shaping is still doing two different jobs in two different places:
  - the editor owns contour and lane boundaries
  - sliders own lane contribution / overall motion feel
- That split is why Spectrum feels partially spatial and partially abstract compared with Blob shaping
- The current runtime contract is not yet a true per-lane arrow contract; it still revolves around scalar fields such as `spectrum_bass_emphasis`, `spectrum_mid_suppression`, and `spectrum_wave_amplitude`
- There is also still a stale legacy seam in runtime apply code around `spectrum_vocal_position`, even though vocal ownership is supposed to come from notch layout now
- That means Energy Arrows is not just a widget swap; it needs a small but explicit authored/runtime contract cleanup

Recommended interaction model to prototype first:
- Put one vertical arrow above each active lane region, visually centered over the current lane span derived from the notch layout
- Arrows should move only on the Y axis
- Arrow travel should map directly to real lane power on a `0–100%` scale
- `0%` should mean the lane can collapse away if its source energy is absent
- `100%` should mean full lane power, not just a cosmetic editor hint
- Arrow length should represent contribution strength only; it must not silently absorb `drop_speed`, smoothing, or floor behavior
- Moving notch boundaries should move the arrow anchors with the lane, but the stored meaning should stay attached to the lane identity rather than the old pixel position

Explicit control-boundary decision:
- `drop_speed` stays outside the editor
- `profile_floor` stays outside the editor
- `Card Height`, glow, ghost, colour, and render-style controls stay outside the editor
- The editor should only own:
  - silhouette nodes
  - lane boundaries / notch splits
  - lane contribution arrows
- First implementation should treat `spectrum_wave_amplitude` carefully rather than assuming it belongs in the editor just because it affects feel

Current best-fit migration direction:
- Replace `spectrum_bass_emphasis` with a lane-native Bass arrow
- Replace `spectrum_mid_suppression` with lane-native mid/vocal attenuation authored directly where the user sees those regions
- Remove redundant lane-power sliders once true lane arrows are in place; do not leave the user with two authored surfaces for the same concept
- Keep only controls that still own a genuinely different concept after the arrow upgrade
- Treat `spectrum_wave_amplitude` as removable only if the arrow contract genuinely subsumes it; otherwise keep it explicitly as a separate global reactivity control

Implementation planning that should happen before code:
- [ ] Audit the current runtime math in `bar_computation.py` and identify exactly how bass, mids, vocal-center hinting, and global reactivity are mixed today
- [ ] Decide whether the new persisted contract should be mirrored/linear-specific or label-driven across both layouts
- [ ] Decide whether non-mirrored needs five arrows (`Bass`, `Low-Mid`, `Vocal`, `Hi-Mid`, `Treble`) while mirrored keeps four (`Mid`, `Vocal`, `Low-Mid`, `Bass`)
- [ ] Confirm how lane identity should survive notch dragging and label migration
- [ ] Specify how untouched legacy presets/settings are promoted into initial arrow values without flattening Organs
- [ ] Remove or formally retire the stale `spectrum_vocal_position` runtime seam during the same cleanup, not later
- [ ] Define whether arrows visually grow upward only or use a centered stem while still storing a strict `0–100%` value
- [ ] Decide whether arrows need text/value affordances or whether hover/selection feedback is enough

Testing / validation fence:
- [ ] Add structural tests for arrow persistence, mirrored/non-mirrored save/load, and notch-motion ownership
- [ ] Add runtime math tests proving lane arrows actually affect the intended lanes instead of acting like a renamed global slider
- [ ] Keep `Preset 1 (Organs)` synthetic baselines in the loop before and after migration
- [ ] Manually validate that a user can understand and edit the feature without needing the old scalar sliders beside it
- [ ] Treat passing tests as schema/math proof only, not interaction sign-off

Decision notes to preserve:
- This is not a Blob-shaper transplant
- The goal is a cleaner Spectrum mental model, not feature symmetry for its own sake
- Spatial ownership stays in the Spectrum editor
- Time-behavior controls still belong outside the editor
- If the first pass cannot clearly beat the existing scalar controls, stop and reassess instead of forcing arrows in because the idea sounds elegant

Design guardrails:
- This is not a Blob-shaper transplant
- Spatial ownership stays in the Spectrum editor
- Time-behavior controls still belong outside the editor

### 2. Spectrum Consolidation Pass (was §3.3)

**Status:** `[ ]` Not started
**Priority:** Medium

- [ ] Prepare an exact proposed list of Spectrum control merges, removals, and deprecations
- [ ] Confirm each merge/removal with the user before editing
- [ ] Preserve Organs behavior directly or through automatic remapping
- [ ] Keep shimmer-at-mid-height as a defined tuning target rather than a vibe-based cleanup
- [ ] Defer shimmer assessment/fix until the rest of this plan has landed cleanly, but do not defer ordinary consolidation work that can proceed safely now

Captured tuning notes:
- Mid-height shimmer is not the same problem as quiet-floor jitter
- The target is steadier mid-height motion at 60 fps without flattening large high/low movements
- Compare behavior on `<=60 Hz` displays versus `165 Hz` displays and decide whether the eventual fix should improve one, both, or both differently
- `drop_speed` alone is too blunt; Spectrum needs room for large rises and large falls

User guidance to preserve:
- Research whether optional interpolation, motion blur, or related display-side presentation techniques are standard for reducing shimmer on lower-refresh displays
- The problem is most noticeable on Spectrum because it is visually rigid, but some shimmer is still visible even at `165 Hz`
- A promising direction is per-lane hysteresis once a lane reaches a materially stable height, requiring more visual movement before it visibly shifts again
- Important guardrail: do not further smooth the underlying music/math signal; only improve the visual motion presented to the user
- Drops should be encouraged through a less flickery presentation method than simply increasing `drop_speed`
- Higher internal resolution appears to reduce shimmer but increases latency and does not eliminate the issue

### 3. Reddit Helper Reliability / Link Handoff

**Status:** `[~]` In progress / awaiting runtime validation
**Priority:** Medium-High

Reddit Helper link opening is still unreliable and has reportedly been "fixed" multiple times without holding. Treat this as a real reliability task, not a cosmetic cleanup. The major breakthrough remains real: packaged screensaver-runtime link opening has been observed working. The sharper diagnosis now is this: queue writing works, the helper EXE can consume the queue, but **launch authority from the active saver desktop keeps dragging the flow back into black-screen / dead-Winlogon regressions**. The current direction is no longer saver-owned preload at all. The saver now owns only queueing plus a benign ProgramData session ticket, while Windows Task Scheduler is the launch authority for an on-demand interactive helper task in the logged-in user's desktop session.

Strategy now explicitly locked:
- The screensaver and helper are separate responsibilities
- Saver-side Reddit flow must remain: queue URL -> request normal saver exit -> continue normal teardown
- Saver exit must never wait on helper state, shell-readiness state, browser state, or helper success/failure
- Helper responsibilities begin only after launch: poll for shell readiness, open queued payload when safe, foreground browser best-effort, then self-exit
- Do not spawn the helper directly from the active saver desktop again; use a pre-registered on-demand interactive scheduled task instead
- The saver may refresh a ProgramData session ticket while active, but that ticket must never gate or delay saver exit
- The helper should prefer simple shell-native launch from the real user desktop; do not overcomplicate helper launch with GUI-framework baggage unless it is clearly proven necessary
- Clipboard copy is only a last-resort recovery aid and must stay non-blocking
- Green tests are useful contract coverage only; they do **not** count as proof that real SCR / Winlogon runtime is fixed

- [ ] Audit the current secure-desktop -> helper -> browser handoff flow end to end
- [ ] Review `C:\\ProgramData\\SRPSS\\` state, queues, and related runtime clues before changing behavior
- [ ] Re-read the Winlogon / session-handoff assumptions that justified the current design
- [ ] Validate the scheduled-task authority path in a rebuilt/reinstalled package, not only in repo tests
- [ ] Evaluate whether the helper can safely wait/poll for confirmed screensaver shutdown before launching URLs
- [ ] Keep MC direct-open logic separate from helper launch logic instead of trying to force both environments through one shell path
- [ ] Reduce needless complexity only if it does not weaken cleanup, security posture, or AV trust
- [ ] Investigate whether screensaver closure itself can be made faster without risking threads, memory cleanup, or shutdown ordering
- [ ] Validate with repeated real-world link launches, not a single happy-path test

Progress landed so far:
- [x] Removed the app-driven shutdown race that could kill the session helper before deferred URLs were eligible to open
- [x] Tightened helper logging so launch requests are not overstated as proven user-visible success
- [x] Switched real non-script `RUN` bootstrap toward a saver-owned session-scoped watcher instead of a persistent background watcher
- [x] Kept MC and script-environment runs off the helper bootstrap path
- [x] Added regression coverage for session-scoped owner-pid bootstrap and the updated watcher queue-processing contract
- [x] Real packaged screensaver-runtime link opening has now been observed working for a Reddit URL
- [x] Reduced the secure-desktop handoff timing slightly (`12.0s -> 11.0s`) and shell-settle timing slightly (`1.5s -> 1.0s`) to trim delay without getting reckless
- [x] Removed the installer-driven helper startup path and replaced it with explicit cleanup of the legacy `HKCU\\Run` entry
- [x] Added legacy ownerless-watcher self-exit behavior so old startup-launched helpers do not linger forever once their queue is empty
- [x] Confirmed by live manual execution that the installed helper EXE can drain queued URLs, open them, clean the queue, and write heartbeat/log files
- [x] Confirmed by live log evidence that click-time helper bootstrap was the wrong place to launch: it could leave the user trapped on a black/dark-grey screen while the helper waited for shell readiness
- [x] Retired the click-time bootstrap experiment and moved to a settled post-start preload tied to the shared startup fade policy instead
- [x] Added ProgramData breadcrumb logging for helper bootstrap attempts/skips/failures so packaged SCR runs can be diagnosed even when frozen main logs are disabled
- [x] Replaced the banned raw-`QTimer` preload experiment with a `ThreadManager`-scheduled preload path
- [x] Proved from fresh ProgramData evidence that saver-owned preload still violated the intended separation in practice: helper launch accepted, helper began processing, then real runtime still black-screened and never completed browser handoff
- [x] Retired saver-desktop helper preload as an architectural dead end for this bug family
- [x] Replaced direct helper spawn from secure-desktop runtime with an on-demand interactive scheduled-task authority model
- [x] Added a saver-owned ProgramData session ticket so the helper can stay session-lived without becoming a 24/7 startup process
- [x] Switched the helper back toward shell-native open behavior (`os.startfile` first) instead of depending primarily on Qt shell helpers inside the packaged helper EXE
- [x] Shortened secure-desktop queue delay (`11.0s -> 3.0s`) and helper shell-settle wait (`1.0s -> 0.75s`) under the new authority model

Latest real-user validation snapshot:
- A packaged real screensaver run successfully opened a Reddit link back in normal Windows
- The launch still feels slightly slower than ideal, but is now functional rather than broken
- An old startup path still caused the helper to run at Windows login and never close; this has now been removed in code and installer logic, but still needs validation on a rebuilt/reinstalled copy
- Fresh live ProgramData evidence later showed queued `scr_click` entries with `session: "Console"` and no helper artefacts until the helper EXE was launched manually
- Manual execution of the installed helper EXE then opened all queued Reddit URLs, drained the queue, and created both `reddit_helper.log` and `reddit_helper_heartbeat.json`
- That proves the helper binary itself is healthy; the unresolved piece was automatic bootstrap from the real screensaver path
- A later click-time bootstrap experiment regressed badly: the helper did launch, but the saver could strand the user on a black/dark-grey cursor-only screen while the helper logged repeated `shell not ready` deferrals
- A later settled-preload attempt exited cleanly but still produced no browser handoff, no helper heartbeat, and no helper breadcrumbs even after the user waited ~20 real seconds before clicking
- A later run finally produced `scr_helper.log` preload breadcrumbs showing the preload *did* schedule, but the callback crashed before handoff with a `settled preload callback exception`
- The latest black-screen regression proved something deeper: even detached saver-owned preload was still the wrong authority. Fresh logs showed preload accepted and the helper watcher started, but the real run black-screened and `reddit_helper.log` stopped at `Launching deferred URL:` with the queue entry still untouched. That means "launch accepted" was only process-creation success, not real user-visible handoff success.
- Recent helper log from the working handoff:
  - `2026-04-08 19:31:11,407 [helper] INFO - Launching deferred URL: ...`
  - `2026-04-08 19:31:12,942 [helper] INFO - Shell launch request accepted via os.startfile: ...`
  - `2026-04-08 19:31:12,943 [helper] INFO - Launch request completed (1535.81 ms): ...`
  - `2026-04-08 19:31:13,946 [helper] INFO - Browser foregrounded after helper launch: ...`
  - `2026-04-08 19:31:13,946 [helper] INFO - Watcher cycle: processed 1 entries`

Current hypothesis from live ProgramData evidence:
- Real installed/runtime queue writes are happening reliably
- The helper EXE is capable of consuming those entries when launched directly
- Therefore the remaining failure was not "URL launch is broken" but "automatic helper launch authority was in the wrong place"
- Launching the helper on the same click that requests saver exit is too invasive for the real runtime path
- Launching the helper earlier from the active saver desktop also proved wrong in practice, even when detached
- The new working rule is stricter now: the saver may request helper startup, but the helper must be created by a separate Windows authority in the real user desktop session
- The chosen authority is a pre-registered on-demand interactive scheduled task, requested at saver startup
- The saver now refreshes only a benign ProgramData session ticket while active; when that refresh stops, the helper is free to self-expire after queue idle
- The remaining unknown is no longer "will preload fire" but "will the installed scheduled task reliably start the helper in the correct user desktop without prompts, black screens, or lingering processes"

Fallback note under consideration:
- [x] Added a best-effort click-time clipboard copy of the clicked Reddit URL as a last-resort recovery path
- [x] This remains explicitly secondary to real helper/browser handoff; it is not a strategy pivot
- [x] The copy is best-effort only and must not block SCR queueing or exit if clipboard access fails

Validation still needed on the next rebuilt/reinstalled package:
- [ ] The installed scheduled task is created correctly during install/reinstall for the logged-in user
- [ ] Saver startup now requests the helper task without causing any black-screen / dead-Winlogon regression
- [ ] The scheduled task launches the helper into the real user desktop/session with no repeated UAC prompts and no suspicious AV behavior
- [ ] The helper still exits itself after successful deferred handoff
- [ ] No no-click session leaves a lingering helper behind after the session ticket expires and idle timeout passes
- [ ] `scr_helper.log` breadcrumb lines now make scheduled-task requests and accept/fail states obvious in packaged runtime if anything still fails
- The old installed/login helper path was one real source of bad behavior: it could start the helper at Windows login and keep it alive outside actual screensaver use
- Script/preview logs can also mislead because they may exercise MC-style direct open or session-scoped watcher behavior instead of the true shipped SCR path

Design guardrails:
- Avoid solutions likely to look suspicious to antivirus or OS trust systems
- Do not replace robust shutdown guarantees with a race-prone "seems fast enough" handoff
- Prefer the simplest proven launch path once session ownership and shutdown timing are genuinely understood
- Do not treat "URL opened" log lines or preview/script-environment success as proof; only real screensaver-runtime user success counts

Still awaiting validation:
- [ ] Confirm the rebuilt/reinstalled product no longer starts `SRPSS_RedditHelper` at Windows login
- [ ] Confirm the helper now closes itself after a successful link handoff in real screensaver runtime
- [ ] Confirm the helper does not linger forever after a no-click screensaver session
- [ ] Decide whether the current shaved delay is good enough or whether another conservative ~`1000ms` reduction is still safe after more live testing
- [ ] Validate with repeated real-world link launches, not a single happy-path test

### 4. Oscilloscope UI Bucket Cleanup

**Status:** `[x]` Landed and user-validated
**Priority:** Medium-High

The Oscilloscope builder (`ui/tabs/media/oscilloscope_builder.py`, 438 lines) uses a flat `_normal_layout` / `_adv_layout` split with no collapsible buckets. Controls are interleaved without clear grouping.

**Current flat layout:**
- Normal: Glow (toggle, intensity, reactivity, reactive), Ghost (toggle, intensity), Amplitude, Smoothing, Speed
- Advanced: Dim Lines, Line Offset Bias, Vertical Shift, Line/Glow Color, Multi-line (count, line 2/3 colors, ghost per-line), Card Height

**Proposed bucket structure:**

Normal surface:
- **Appearance** - Line Color, Glow Color, Glow toggle + intensity + reactivity + reactive checkbox
- **Behavior** - Amplitude, Smoothing, Speed, Ghost toggle + intensity

Advanced surface:
- **Multi-Line** - Multi-line toggle, Line Count, Line 2/3 colors + glow colors + ghost per-line, Dim Lines 2/3
- **Layout** - Line Offset Bias, Vertical Shift, Card Height

Landed:
- [x] Refactored `oscilloscope_builder.py` onto the shared collapsible-bucket helper path
- [x] Grouped controls into `Appearance`, `Behavior`, `Multi-Line`, and `Layout`
- [x] Kept control attribute names unchanged so existing bindings still work
- [x] Normal buckets default expanded; Advanced buckets default collapsed
- [x] Validated: `python -m pytest tests/test_widgets_tab.py tests/test_visualizer_settings_plumbing.py -k "osc" -q`

### 5. Sine Wave UI Bucket Cleanup

**Status:** `[x]` Landed and user-validated
**Priority:** Medium-High

The Sine Wave builder (`ui/tabs/media/sine_wave_builder.py`, 706 lines) uses a flat layout with many controls. It has the most controls of any waveform mode and benefits most from bucketing.

**Current flat layout:**
- Normal: Glow section (toggle, intensity, reactivity, color, reactive), Ghost section (toggle, opacity, decay), Line Color, Sensitivity, Speed, Travel, Wave Effect, Micro Wobble, Crawl, Width Reaction
- Advanced: Density, Heartbeat, Displacement, Vertical Shift, Line 1 Shift, Multi-line (count, line 2/3 colors + glow + travel + ghost + shift), Line Offset Bias, Card Adaptation, Card Height

**Proposed bucket structure:**

Normal surface:
- **Appearance** - Line Color, Glow (toggle + intensity + reactivity + color + reactive), Ghost (toggle + opacity + decay)
- **Motion** - Speed, Travel, Wave Effect, Crawl, Micro Wobble (legacy; review whether it should stay visible)
- **Response** - Sensitivity, Width Reaction, Heartbeat (candidate to promote from Advanced because it is a user-facing feel control)

Advanced surface:
- **Multi-Line** - Multi-line toggle, Line Count, Line 2/3 colors + glow colors + travel + ghost + horizontal shift, Displacement
- **Layout** - Density, Vertical Shift, Line 1 Shift, Line Offset Bias, Card Adaptation, Card Height

Landed:
- [x] Refactored `sine_wave_builder.py` onto the shared collapsible-bucket helper path
- [x] Grouped controls into `Appearance`, `Motion`, `Response`, `Multi-Line`, and `Layout`
- [x] Promoted `Heartbeat` from Advanced into the Normal `Response` bucket
- [x] Left `Micro Wobble` visible for now as a legacy control; do not treat that deprecation decision as settled
- [x] Kept control attribute names unchanged
- [x] Validated: `python -m pytest tests/test_widgets_tab.py tests/test_visualizer_settings_plumbing.py -k "sine" -q`

### 6. Bucket State Persistence (was IDEA BOX #1)

**Status:** `[x]` Landed and user-validated
**Priority:** Medium

Bucket collapsed/open state does not persist across settings dialog open/close.

Landed:
- [x] Replaced ad-hoc per-builder bucket wiring with a shared collapsible-bucket helper in `builder_scaffold.py`
- [x] Extended `WidgetsTab` with persisted per-mode bucket state storage in settings
- [x] Implemented save-on-collapse/expand and restore-on-build
- [x] Applied the shared solution to Spectrum, Blob, Oscilloscope, and Sine Wave
- [x] Preserved existing UX defaults where they were already established instead of forcing a surprise global-collapse reset
- [x] Validated via targeted widget/plumbing suites for `osc`, `sine`, `spectrum`, and `blob`

### 7. Non-Mirrored Spectrum Shaper Vocal Lane (was IDEA BOX #2)

**Status:** `[~]` Reworked after failure / awaiting visual validation
**Priority:** Low

Non-mirrored Spectrum Shaper currently lacks a vocal lane. In mirrored mode, the center region naturally maps to vocals and is fully adjustable. In linear mode, there is no equivalent.

Decision already captured:
- [x] Linear mode should auto-insert a vocal region rather than require manual placement

Remaining tasks:
- [x] Determine the default vocal position in linear mode (`0.46` normalized) so it sits in the editable mid/vocal band without hard-centering it
- [x] Keep the auto-inserted vocal region user-adjustable after insertion; that flexibility is the point of adding it automatically rather than hard-locking placement
- [x] Ensure the notch label system supports `Vocal`
- [x] Update the Spectrum Shaper editor and runtime contract accordingly
- [x] Promote untouched legacy linear defaults into the new vocal-lane layout without overriding user-customized notch layouts
- [x] Update docs / plan notes through the live plan
- [x] Validate: `python -m pytest tests/test_visualizer_settings_plumbing.py tests/test_spectrum_shaping.py tests/test_widgets_tab.py -k "spectrum" -q`

Runtime validation failure:
- [x] User confirmed the non-mirrored UI still does not show a visible vocal lane in practice
- [x] The currently shown notch set still reads like `Bass / Low / Mid / Hi-Mid / Treble`, with no visible `Vocal` lane
- [x] Re-check whether the editor/runtime is still rendering legacy linear notch labels/positions despite the migration logic
- [x] Found the likely leak: only the exact stock old linear notch list was being promoted, so drifted old `Bass / Low / Mid / Hi-Mid / Treble` layouts could survive forever; a stale runtime/widget default also still carried the old labels
- [x] Broadened the migration so old five-lane linear families without `Vocal` are promoted even when the user previously nudged the boundaries
- [x] Preserve user boundary positions during that promotion when the saved layout is legacy-shaped but no longer byte-for-byte equal to the old stock default
- [x] Updated stale widget/model defaults so fresh/runtime paths no longer reintroduce `Low` / `Mid`
- [x] Added focused regression coverage for both exact legacy defaults and drifted legacy linear labels
- [x] Latest available visualizer log review was inconclusive because the live vis logs did not emit notch labels/families directly
- [x] A later saved-settings spot-check was taken from the normal runtime/settings context, but the user's actual validation run was done from the MC build, so that evidence is not strong enough to close this task
- [x] Explicit rule: do not validate/remove this task until the emitted notch family is confirmed from the same build context the user actually tested
- [ ] Verify whether the lane is now visibly correct in the real editor UI and whether runtime behavior also follows the upgraded layout

### 8. Settings Shell Outer Border Radius

**Status:** `[ ]` Not started
**Priority:** Low

Explore a very light rounded outer edge for the settings shell without introducing corner bleed, masking regressions, or collateral QSS breakage.

- [ ] Fully understand the current custom styling stack before attempting changes, including QSS, SVG assets, frame layering, clipping, and any mask behavior
- [ ] Investigate whether a radius of `2` or `3` is safer/easier; prefer `3` only if it is genuinely equal-risk
- [ ] Prototype the outermost shell rounding only
- [ ] Validate specifically for corner bleed, border artifacts, and theme regressions
- [ ] Do not proceed to "done" until user validation confirms no bleed

Design guardrails:
- This is a polish task, not a styling-system rewrite
- Do not endanger any other custom styling behavior to gain rounded corners
- Analysis must be deep before implementation; this task is deliberately risk-averse

### 9. Settings Dialog Close / Teardown Polish

**Status:** `[ ]` Not started
**Priority:** Low

When closing the settings dialog, some elements visibly deconstruct before the shell is gone. The goal is for the close to feel atomic, or at least visually shell-first.

- [ ] Audit current shutdown ordering for the settings dialog shell and child elements
- [ ] Determine whether the visible deconstruction comes from fade timing, layout teardown, QWidget destruction order, or delayed shell close
- [ ] Prefer a solution where everything appears to vanish together; second-best is shell-first disappearance
- [ ] Confirm no cleanup, memory, or shutdown correctness regressions are introduced

### 10. Blob Energy Balance / Glow Drive Follow-up

**Status:** `[ ]` Not started
**Priority:** Low

Blob `Constant Energy` reportedly overpowers reactive/vocal energy in the non-shaped Blob path and likely needs retuning there only. There is also a product question around Glow Drive inputs.

- [ ] Audit the current non-shaped `Body Response` balance for constant, reactive, and vocal energy
- [ ] Confirm the shaped Blob path is unaffected before making any tuning changes
- [ ] Try a first tuning pass on the non-shaped path that halves constant energy and increases reactive/vocal energy by roughly `20%`
- [ ] Validate whether that ratio is directionally right rather than assuming the first guess is final
- [ ] Review the `Glow Drive` selection list for useful additions such as `Transient`
- [ ] Preserve Blob identity and do not accidentally make it behave like another mode
- [ ] Keep shaped and non-shaped behavior isolated so no cross-over tuning is introduced

### 11. Bubble UI Bucket Cleanup

**Status:** `[x]` Landed and user-validated
**Priority:** Low

The Bubble builder (`ui/tabs/media/bubble_builder.py`) previously had no collapsible buckets. Lower priority since Bubble is newer and less control-dense, but it still needed the same consistency treatment.

Landed:
- [x] Audited the Bubble builder layout and replaced raw text-section headings with shared collapsible buckets
- [x] Grouped Bubble into `Appearance`, `Motion`, `Reactivity`, `Population`, `Layout`, and `Ghost`
- [x] Implemented Bubble using the shared bucket helper/persistence path
- [x] Validated: `python -m pytest tests/test_widgets_tab.py tests/test_visualizer_settings_plumbing.py -k "bubble" -q`

---

## Runtime / Log Watchlist

**Status:** `[~]` Ongoing

Keep watching for:
- [ ] Roaming AppData visualizer normalization repair line repeating indefinitely
- [ ] Creator bridge drift between canonical settings model and widget kwargs
- [ ] Source curated tree vs generated shipped tree drift
- [ ] Stale defaults snapshot drift
- [ ] UI preview/live-config helper paths throwing misleading exceptions
- [ ] Reddit Helper queue/heartbeat/state drift that could mask the actual link-handoff failure mode
- [ ] Settings dialog shutdown logs that indicate shell/child teardown ordering regressions

Known items:
- [~] `%APPDATA%/SRPSS/settings_v2.json` may contain older visualizer-era state that `SettingsManager` heals on load. Confirm whether a user-side save permanently clears the repair path.
- [~] Blob `Preset 1` synthetic drift is expected because the user personally modified Blob Preset 1. That baseline test should only run immediately before/after Blob work, not continuously.
- [ ] Spectrum runtime still carries a stale `spectrum_vocal_position` apply/config seam even though notch layout is supposed to own vocal placement now; resolve that as part of Energy Arrows / Spectrum consolidation rather than letting it drift longer

---

## Idea Box

> Raw ideas that have not yet been shaped into active tasks. Promote them once they have a concrete goal, scope, and guardrails.

- Empty for now. New raw ideas should be captured here before they become numbered tasks above.
