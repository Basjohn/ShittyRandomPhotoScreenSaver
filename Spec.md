# Spec

Last updated: 2026-06-28

Canonical architecture and behavior contracts for SRPSS.

## 1. Product Intent
- Deliver a smooth, stable, multi-monitor screensaver with configurable overlays.
- Keep settings persistence deterministic and recoverable.
- Keep visualizer mode behavior isolated while sharing explicit neutral seams.

## 2. Runtime Topology
- `main.py` and `main_mc.py` bootstrap runtime variants.
- `ScreensaverEngine` owns source cycling, transition scheduling, and display lifecycle.
- `DisplayWidget` is the fullscreen rendering presenter.
- `WidgetManager` owns overlay widget lifecycle, staged startup coordination, and the narrow runtime-pause quiesce seam used before display teardown/settings entry.
- Factory-backed overlay widget family identity and setup metadata are centralized in `rendering/widget_descriptors.py`; `rendering/widget_setup_all.py` must consume that descriptor registry instead of hand-maintaining parallel per-widget setup branches. Spotify-dependent setup remains intentionally explicit and phased in this order: media-owned dependents, local visualizer, remote Custom visualizer reconcile, then final startup.
- During display setup/rebuild, `rendering/widget_setup_all.py` is the sole lifecycle-start authority for factory-created widgets. `rendering/display_setup.py` and follow-on display glue must not immediately run a second initialize pass over the same created set.
- Runtime diagnostics are CLI-first and family-scoped. `--perf`, `--viz`, `--geo`, `--set`, `--life`, and `--cache` are the primary operator surface for high-volume diagnostics. Dedicated sidecar families should keep `WARNING`/`ERROR`/`CRITICAL` visible in general logs while moving routine INFO/DEBUG family noise into the family log.
- Startup logging should advertise the available specific sidecars and the ones active for the current run so tracing can begin in the right file without diving into verbose logs first.
- Fallbacks are an explicit failure signal, not a success path. Prefer clean success or explicit clean failure over substitute behavior; any runtime fallback that changes ownership, geometry source, display target, or recovery path must log loudly at `WARNING` or higher through the relevant existing diagnostics family.

## 3. Centralized Ownership Contracts
- Async business work uses `ThreadManager`.
- Qt object lifecycle uses `ResourceManager`.
- Settings read/write/migration uses `SettingsManager`.
- Shared timeline/tick-driven runtime animations route through `AnimationManager`. Small widget-local effect animations may remain local when they are explicitly owned and cleaned up by the widget.
- Engine-owned `AnimationManager` is also the app-shared fallback manager for runtime leaf/widget animation paths that do not need their own display-scoped transition manager.
- Cross-module publish/subscribe events use `EventSystem`.
- Worker process orchestration uses `ProcessSupervisor`.
- `ProcessSupervisor` owns correlated worker-response waiting/buffering for shared response queues. Runtime callers must not reach into raw worker response queues directly, and the dormant callback-listener facade is not part of the live contract.
- Engine-owned `ThreadManager` and `ResourceManager` instances are also the app-shared fallback managers for leaf/runtime helper code. Do not create ad hoc leaf managers when the shared seam can supply the same ownership cleanly.
- When no app-shared `ThreadManager` is available, helper/UI fallbacks must stay intentionally narrow rather than silently creating another full-size compute-heavy manager.
- `ThreadManager` active-task bookkeeping is authoritative at submit/complete/cancel/shutdown time and must not depend on a queued UI-thread mutation drain to become visible.

## 4. Settings Architecture

### 4.1 Storage model
- Canonical persistence file: `%APPDATA%/SRPSS/settings_v2.json` (MC: `%APPDATA%/SRPSS_MC/settings_v2.json`).
- Structured roots: `widgets`, `transitions`, `ui`.
- Dotted-key API remains available via `SettingsManager`.
- Root `widgets` writes, widgets-map replacement helpers, and SST widget imports must all converge on the same widgets-map normalization/schema contract. Do not let `set("widgets", ...)`, `set_widgets_map(...)`, or import flows drift into different visualizer-schema or default-merge behavior.

### 4.2 Legacy global preset retirement
- Legacy top-level global preset keys are retired: `preset`, `custom_preset_backup`.
- Defaults and modern save paths do not emit those keys.
- Existing settings that contain them are cleaned/migrated safely.

### 4.3 Cache invalidation safety
- Section/root writes (`set('widgets', ...)`, `set('transitions', ...)`, `set_section(...)`) must invalidate descendant dotted-key cache entries.
- New settings APIs must preserve equivalent invalidation behavior.
- Public mutation APIs (`set`, `set_section`, `remove`, `clear`) must keep sync/change-notification behavior coherent enough that runtime/UI consumers do not need to guess which write paths emit `settings_changed` or flush critical roots.

### 4.4 Reset/import preservation
- Preserve-on-reset keys are centralized in `core/settings/defaults.py`.
- Reset/import logic must use that shared preservation contract.

### 4.5 Persisted visualizer schema migration
- Persisted visualizer-section migrations must be version-gated through settings metadata rather than rerunning full legacy normalization on every load forever.
- Legacy/global visualizer keys may still be normalized for imported or foreign payloads, but the main saved settings file should be upgraded once per schema version bump and then treated as current.

### 4.6 Active list-widget capacity policy
- Active row/list widgets currently covered by the shared capacity policy are `reddit`, `reddit2`, and `gmail`.
- Shared policy lives in `core/settings/widget_capacity_policy.py`:
  - minimum configured/visible capacity `5`
  - first-stage maximum capacity/fetch-cache envelope `25`
- Persisted `limit` remains the configured-capacity key. Runtime may still distinguish configured capacity from effective visible capacity when staged growth or future custom-height behavior needs that split.
- Reddit and Gmail may fetch/cache a wider candidate pool than they currently show. Do not re-couple visible row count directly to network fetch size when extending later vertical resize work.
- Under a committed `Custom` rect, `reddit`, `reddit2`, and `gmail` keep width authority on the saved rect, but runtime content may still adjust the committed height vertically to the real visible-row need. Any such vertical-only adjustment must persist back through the shared CUSTOM layout map so replay/ settings-close/startup do not restore stale height.
- Non-`Custom` authored widget stacking is owned by the explicit `widgets.global.stacking_enabled` contract and currently defaults `True` for new users. Runtime stacking and settings-side stack prediction must both respect that flag instead of silently mutating or promising authored-position collision handling.

## 5. Visualizer System Contract

### 5.1 Mode identity
Source of truth: `core/settings/visualizer_mode_registry.py`.

Active ids:
- `spectrum`
- `oscilloscope`
- `sine_wave`
- `bubble`
- `blob` (gated by `-devblob`)
- `devcurve` (display label: Spline Curve)

### 5.2 Naming contract
- Internal id and key namespace remain `devcurve`.
- User-facing label is Spline Curve.
- `--devcurve` remains accepted as compatibility no-op.

### 5.3 Shared seams
- Mapping normalization: `visualizer_settings_snapshot.py`
- Technical normalization / legacy migration contract: `visualizer_settings_contract.py`
- Settings-model field-spec source of truth: `core/settings/models/_spotify_visualizer.py`; grouped build specs, serializer specs, defaults, and ordered build/serialize section merges must be updated together so `from_settings()`, `from_mapping()`, and `to_dict()` remain one contract instead of drifting per entry point
- Canonical mode/preset activation payload: `visualizer_presets.resolve_visualizer_activation_payload()`
- Runtime config application: `widgets/spotify_visualizer/config_applier.py`
- GPU state handoff: `widgets/spotify_bars_gl_overlay.py`
- Shared common uniform upload and rainbow transport prep: `widgets/spotify_visualizer/overlay_uniforms.py`
- Mode-program resolution and renderer-owned uniform dispatch: `widgets/spotify_visualizer/overlay_render_dispatch.py`
- Shared GL frame shell for backbuffer clear, fade gating, and stencil-wrapped render execution: `widgets/spotify_visualizer/overlay_frame_shell.py`
- Outer visualizer card geometry policy: `widgets/spotify_visualizer/card_geometry.py`; mode/preset-owned outer height, blob-width reduction, and media-relative placement belong here rather than in the stencil shell or generic overlay-widget sizing
- Painted-card stencil-mask math: `widgets/spotify_visualizer/overlay_mask.py`
- Overlay runtime-state handoff: `widgets/spotify_visualizer/overlay_state.py`
- Runtime mode/preset resets may preserve the GL overlay object for performance, but they must still blank/hide the overlay, request a cold mode reset, and wait for the fresh activation/generation handoff before first visible bar authority returns.
- Engine config replay: `_replay_engine_config()` reads from authoritative mode config via `_get_mode_technical_config(...)`, not transient widget cache
- ThreadManager/engine hookup must not trigger authoritative engine replay until the visualizer has an authoritative settings model plus technical-config cache for the active mode. Cold startup must apply the resolved activation payload before any such replay is attempted.
- External runtime setters and bar-buffer resize must stay no-op safe when the shared beat engine is unavailable, and when authoritative mode config is ready they must prefer that replay path over ad hoc engine-local fallback state.
- Live audio block-size changes are capture-rebind boundaries: when mode-owned technical config changes the preferred block size at runtime, the active audio worker must restart capture instead of waiting for a full runtime rebuild or settings-dialog restart.
- Visualizer tick ownership is split by phase: the dedicated recurring timer owns steady runtime cadence, while AnimationManager assistance is transition-scoped only and must hand control cleanly back to the dedicated timer when the transition ends.
- Steady-state visualizer cadence has one owner: once transition handoff and fresh-frame gating are out of the way, the dedicated recurring timer is authoritative and `_on_tick` must not apply a second silent steady-state FPS throttle on top of that timer.
- Steady-state visualizer cadence must also stay deterministic for a given target: phase-offset or anti-alignment tricks must not become a sticky randomized interval penalty across startup, settings recreate, or mode/preset activation paths.
- Media-driven playback-state changes must be resilient to short controller wobble: quick paused/playing flaps may update media UI immediately, but the visualizer/capture path must not tear down reactivity or restart capture until a non-playing state survives a short confirmation window.
- Playback authority and capture lifecycle are separate seams: after a non-playing state is confirmed, the visualizer may enter its idle presentation immediately, but loopback capture should stay warm for a short grace window so quick real-world resumes do not pay a cold restart and 1.5s weak-reactivity ramp unless capture actually went cold.
- Post-audio silence decay is a playing-only cleanup path. Once playback is genuinely non-playing, idle-reveal modes must keep their shared beat-engine idle seed instead of letting stale last-audio timestamps decay the paused presentation back to zero.
- Startup playback seeding has trust levels: provisional shared-cache non-playing seeds may inform temporary state, but they must not become authoritative first-visible idle reveal truth until a live media update confirms them. Startup timers may act as watchdog diagnostics, but they must not become reveal authority in place of real readiness.
- If a wake request is deferred during staged startup, the hot-start path must replay a real engine wake once startup ownership transfers. Merely clearing a deferred-wake flag without executing the wake contract is forbidden because it strands startup on weak pre-wake Bubble/Sine/Devcurve behavior.
- Bubble startup/reactivity automation must cover the authored curated preset path, not only generic simulation or parity cases. The `Preset 1 (Deep Sea)` family is a required oracle because generic parity can stay green while live Bubble still feels dead, and Bubble regressions this deep should also be checked against the historical-good comparison harness before trusting newer proxy bars.
- Bubble's steady live motion must not ride on the shared control-normalized convenience lane alone. The beat engine owns a Bubble-specific continuous feed derived from raw band authority plus floor-pressure context so dynamic-floor expansion cannot silently flatten curated Bubble reactivity into a narrow plateau.
- Bubble's beat-engine feed is the continuous lane only. Dispatch adds transient/current pulse authority separately at the runtime handoff, so the beat-engine feed must not double-count those accents or it will ratchet Bubble upward and destroy contraction.
- Bubble's runtime pulse handoff must also stay live all the way through compute/render. If dispatch mixes current/transient pulse authority into the Bubble compute payload, that authority must measurably affect the rendered simulation output; dead `pulse_params` plumbing that stays green on feed-only tests is a regression.
- Bubble loud-path authority must preserve supra-unit loudness through the Bubble-owned dispatch/simulation seam. Do not clamp Bubble's incoming loudness snapshot back to a generic `0..1` band before the hero/small size lanes evaluate it, or restrained-hot and truly loud windows will collapse back into the same visual bucket.
- Bubble is a two-lane closure seam, not one generic motion bucket. The big-bubble hero lane must stay visibly active under both soft and loud authored phrases, must keep sustained-loud authority instead of starving after the initial hit, must not depend on dynamic-floor enablement to stay alive, and must not be visually flattened by hidden render-size multiplier/clamp saturation while the small/medium lane continues reacting underneath.
- Bubble hero anti-flicker is a display-only seam. Any soft-passage settling for the hero radius must stay local to the rendered-radius handoff, must not smooth audio/floor/feed authority, and must disengage in hotter sustained passages where direct size authority is the correct visual truth.
- `bubble_big_visual_smoothing` is the authored/preset-facing control for that display-only hero settling seam. It must remain big/hero-only, default to the current middle authored feel, and must not become a backdoor audio or loud-path authority control.
- Bubble visible size semantics must stay distinct from Bubble motion/accent semantics. Transient punch may still drive speed and accent strongly, but truly louder `1.3+` Bubble windows need their own Bubble-owned sustained-size lift instead of being flattened into the same visible body as restrained transient-heavy windows.
- Bubble drift loudness accent stays on the existing authored drift seam. Mild loud-passage drift lift may scale through the current `bubble_drift_amount` / `bubble_drift_speed` controls, but do not introduce a second dedicated loud-drift setting unless runtime evidence proves the shared authored controls cannot express the effect cleanly.
- `bubble_group_drift` is an authored/preset-facing motion-layout control. When enabled it may align non-swirl Bubble drift into one shared direction carrier with per-bubble force variation, but it must not affect swirl modes and must not turn Bubble into a rigid single-vector slab.
- Shared Bubble group-drift turns are a visual motion contract of their own:
  - `bubble_drift_frequency` owns grouped carrier cadence/reversal timing
  - `bubble_drift_amount` / `bubble_drift_speed` own grouped travel strength, not switch ownership
  - low-frequency grouped drift must not snap between carrier directions in one frame
  - swish variants must reverse deliberately on authored cadence instead of re-picking the same direction, should use a mild perpendicular arc so the turn reads as a gentle curve rather than a jerk, and should preserve a sparse signed lag spread so the field does not collapse into one rigid sweeping slab
  - random/diagonal grouped turns should ease between carriers rather than reading as abrupt jitter
  - Bubble specular size is relative to the rendered bubble body, not a second pulse-growth lane; do not double-count pulse growth into the highlight size or a few bubbles will balloon beyond the intended visual ratio
- Bubble's small/medium lane has its own sustained-loud obligation. It must not only react in quiet phrases; the same shared Bubble feed must keep the smaller field visibly alive through hot sustained passages without needing Preset-9-style authored rescue settings just to look awake.
- Bubble sustained-loud recovery must stay structurally separate from its soft transient feel. A fast fixed-threshold absolute loudness lane may drive movement semantics strongly and feed restrained big/small hold support, but it must not become a slow adaptive "loud mode", must not rely on dynamic floor, and must release quickly enough that drops still contract and breathe naturally.
- Bubble sustained-loud closure must be proven against a harsher runtime-loud oracle, not only against friendly bass-heavy helper phrases. The acceptance bar is: soft/transient feel stays good, real long hot sections with sparse onset help keep the small lane visibly alive, the big lane reaches a strong authored upper range without crude hard-clamp mode-switching, and ordinary hot passages still stay below a fake ceiling.
- Bubble runtime-loud bars must also model the exact late-window pathologies seen in bad runtime, not just generic weak motion: if the soft opening looks good but the hot window kills the small lane, freezes hero size to one visible value, pins hero clamp pressure, or makes size/clamp edits help only by collapsing the small lane, the Bubble contract is still broken.
- Bubble loud-path oracles must grade the actual Bubble worker snapshot path. Do not prove closure from a second helper-side `snapshot(...)` pass with neutral pulse params or from replay windows that accidentally mix soft and hot frames from the same repeated profile, because that turns a runtime-shaped bar back into a proxy and can hide the exact failure shape users still see live.
- Spectrum startup/reactivity automation must also use an authored curated preset path, not only generic parity helpers. `Preset 1 (Organs)` is the standing Spectrum oracle for first-visible authority and startup/mode-switch parity.
- Spectrum horizontal bar geometry has one shared contract. CPU helper math and shader layout must agree on the same slightly left-biased bar field so the mode does not reintroduce a visible left gutter or right-edge clipping through duplicate geometry calculations.
- Spectrum solid-bar anti-flicker behavior is a display-only seam. Any chatter suppression for `single_piece` belongs after continuous bar computation at the overlay/display quantization layer, must not modify FFT/shared beat-engine floor logic, and should prefer continuous display-state easing over robotic segment pinning.
- Idle-reveal modes must have a meaningful paused startup presentation without depending on a prior live audio frame. When playback is genuinely non-playing, the shared beat engine should still provide a low-energy idle waveform/bar seed so first visible startup does not collapse into a dead zero frame.
- Visualizer latency warnings are activation-aware: ordinary `[SPOTIFY_VIS][LATENCY]` warnings/errors must stay suppressed until the current activation has seen either live audio for that activation or a fresh engine frame for that activation. Explicit probe-triggered latency requests may still log before readiness so reset/transition investigations remain visible.

### 5.4 Mode isolation
- Mode-owned behavior belongs to mode-owned code.
- Shared seams must remain neutral and explicit.
- No hidden cross-mode dependency on authored mode keys.
- Technical settings are mode-owned at runtime and in canonical persistence. Shared/global technical keys are legacy migration inputs only and must not remain in normalized settings, custom snapshots, or preset payloads.
- Mode-owned technical values keep authored intent. In particular, valid low manual floors below `0.12` and authored `audio_block_size=0` automatic-selection requests must survive normalization, validation, startup, recreate, hot mode switch, and preset cycle unchanged; shared/global legacy technical keys may be stripped or migrated, but they must not poison current mode-owned values.
- Preset-varying runtime visuals that affect activation or renderer state, including bar fill/border styling and legacy ghost controls, are mode-owned too. They must not travel through shared/global authored keys after normalization.
- Startup create, settings refresh, context-menu mode switch, double-click cycle, preset cycle, and forced preset activation must all consume the same resolved mode/preset payload before touching widget, engine, or overlay state.
- Visualizer settings-model refactors must preserve ordered grouped section merges for both constructor assembly and persistence serialization. Do not reintroduce bespoke handwritten field families or entry-point-specific fallback paths once a group has been centralized.
- Live diagnostics for visualizer activation must report the resolved preset identity and the actual applied worker/widget technical state, not only raw settings payloads.
- High-frequency visualizer diagnostics (`BARS`, `FLOOR`, `TRANSIENT`, `DEVCURVE`, `GLOW`) must build their detailed payloads only on actual emit paths; guardrail warnings such as `LATENCY`, `FIRST_FRAME_GUARD`, and `MODE_RESET_ASSERT` stay loud.

### 5.5 Runtime card/shadow contract
- Runtime overlay card shadows are painter-owned, not `QGraphicsDropShadowEffect`-owned.
- `widgets.shadows.enabled`, `widgets.shadows.text_enabled`, and `widgets.shadows.header_enabled` are the runtime shadow controls for framed widgets.
- Framed widgets that use the painted shadow path must explicitly clear transparent backing regions before repainting cached shadow output so stale shadow pixels cannot accumulate in the gutter.
- Direct `QWidget` implementations that do not inherit `BaseOverlayWidget` but need framed-card parity, such as the Spotify visualizer, must mirror the same painted-frame contract explicitly rather than assuming inheritance.
- Spotify visualizer outer card sizing is intentionally special: presets and live mode settings own outer height, blob width may narrow the card independently of media width, and media-relative placement belongs to the visualizer card-geometry policy rather than the generic overlay-widget card-height path. Future custom edit/resizing work should extend that outer-geometry policy, not bypass it.
- When a committed visualizer CUSTOM rect already exists, startup creation must prime that rect before `startup_create`/prewarm work reads geometry, and later foreign outer-geometry writes must not be allowed to override that committed CUSTOM rect while CUSTOM authority remains active.
- Visualizer spawn ownership under `Custom` is a participating-display contract, not a media-follow shortcut: if the requested CUSTOM monitor is not currently part of the active compositor/display set, local/remote visualizer creation must choose a participating display instance instead of spawning into unseen territory.
- Multi-display startup must register the full allowed `DisplayWidget` set before the first display runs widget setup that performs participation-based owner selection, so a later requested CUSTOM monitor is seen as pending startup instead of being misclassified as absent.
- When the requested CUSTOM display still exists in runtime but is temporarily non-participating during display sleep/wake churn, remote reconcile must treat fallback as a last resort: schedule one cautious delayed recheck through `ThreadManager.single_shot`, and only then fall back if the requested display still has not resumed participation.
- Creator-time CUSTOM visualizer route repair must stay committed-layout-aware. If the visualizer is still in `Custom` but its monitor field reads as missing/`ALL` during recreate, recover that route only from matching saved visualizer screen-bucket evidence; do not let a broad authored-restore helper claim success unless the visualizer actually exits `Custom` onto a non-`ALL` authored route.
- Analog clock cache/paint geometry should stay explicit and shared: the analogue card ring is intentionally larger than the inner face, framed mode keeps extra outer-ring breathing room between numerals and the card edge, the numerals are intentionally smaller than the old digital-proportional fallback, and numeral placement uses an authored optical layout map rather than plain text centering so wide Roman numerals such as `VIII` remain visually balanced across future resizing work.
- Clock mode swaps under a committed CUSTOM rect are full outer-geometry swaps, not inner-content mutations. Switching between digital and analogue must rebuild the saved CUSTOM rect around the target mode's natural shape, preserve the authored scale, and persist the rebuilt rect as the new custom truth instead of cramming the target mode into the previous mode's outer box.

## 6. Preset Architecture Contract
- Authored curated source: `presets/visualizer_modes/`.
- Runtime shipped trees are generated artifacts.
- Repair tool must normalize schema without rewriting authored intent.
- Reindex mutates only slot filename numbering and `preset_index`.
- Tests must not require curated/authored preset files to have specific names, slots, or numeric visual values beyond schema/index/repair contracts. Authored preset content may be fixed, indexed, cleaned, or validated structurally, but exact creative values are not a runtime compatibility contract.

## 7. Startup Staging Contract
- Startup timing policy source: `rendering/overlay_startup_policy.py`.
- Spotify-related secondary-stage widgets must wait for anchor/position readiness before reveal.
- Spotify-related secondary-stage widgets must also recover cleanly if their first secondary-stage starter fires before the media anchor becomes visible; later anchor visibility sync must be allowed to release the staged reveal once the centralized manager deadline is satisfied.
- Mute button follows secondary-stage reveal contract.
- Cold startup should prioritize first useful display over eager GL compilation. Transition GL startup should compile only the minimal safe subset needed for immediate runtime. Deferred transition warmup should use a hidden/quiescent shared GL context when possible so the live compositor surface is not perturbed after the first image appears; only non-live surfaces may fall back to direct compositor-context warmup. That hidden deferred path should cover both remaining transition-program compilation and representative transition-resource warmup where safe, so first use does not pay avoidable visible-surface prep cost. Transition correctness must not depend on that deferred startup warmup succeeding: first-use transition startup must ensure/bind the needed compositor program in a real current GL context before animation begins. Spotify visualizer GL startup should compile the resolved startup mode first, seed the GL overlay with that mode before prewarm, and warm the remaining mode programs incrementally afterward.
- Multi-display GL transition pacing uses two shared seams: a small display-level image handoff stagger plus compositor-side desync at transition start. Compositor-side desync must remain effectively imperceptible and shared across compositor transition families, not only crossfade.
- Single-display runtime must bypass compositor-side desync entirely. Request acceptance, deferred/desync wait, and actual transition runtime are separate telemetry concerns; transition duration metrics should begin at the real compositor handoff, not at the earlier request timestamp.
- GL transition duration/completion remains owned by `AnimationManager`, but visible shader progress is refreshed from paint-time `FrameState` interpolation before shader dispatch. High-refresh visual smoothness must be judged from `GL PAINT` / render-timer cadence, not only the lower-frequency `GL ANIM` progress-sample callback cadence. If render-timer cadence is healthy while same-screen `GL PAINT` cadence collapses, the failure is paint/event-loop delivery starvation until proven otherwise; do not solve it by queueing more UI work.
- Cold visualizer construction must not invent a separate runtime truth. When a resolved startup mode is already known, the visualizer widget and GL overlay must be seeded with that mode at construction/prewarm time; when no resolved mode is available yet, the canonical product default is `bubble`.
- Cold/recreated display startup must also keep first-image recovery explicit. If the first immediate `_show_next_image()` call fails, the engine should perform a bounded immediate retry sequence rather than relying only on the long rotation timer.

## 7.1 Transition Registry Contract
- `rendering/transition_registry.py` is the canonical source of truth for ordinary transition identity and startup/runtime metadata.
- Descriptor metadata should own at least:
  - stable persisted transition names and legacy alias canonicalization,
  - UI order/labels for ordinary transition selectors,
  - cycle/random-pool participation,
  - hardware-gating metadata,
  - compositor program-key routing,
  - startup-safe transition-program warmup participation.
- `ui/tabs/transitions_tab.py`, `widgets/context_menu.py`, `engine/screensaver_engine.py`, `engine/engine_handlers.py`, `rendering/transition_factory.py`, `rendering/gl_compositor.py`, and `rendering/gl_compositor_pkg/gl_lifecycle.py` should consume that shared registry for ordinary transition identity/routing instead of keeping parallel handwritten lists.
- Keep transition-specific runtime behavior explicit in the transition implementations and factory creator methods. Do not flatten per-transition math or widget-local settings UI behavior into a giant opaque descriptor table just for neatness.

## 8. Widget Descriptor / Registry Contract
- `rendering/widget_descriptors.py` is the canonical registry for factory-backed overlay widgets.
- Descriptor metadata must own at least widget identity, parent attribute name, factory routing, startup-stage intent, environment gating, and any shared setup extras such as base-settings inheritance or shadow-config injection.
- `rendering/widget_setup_all.py` may orchestrate creation, reuse, expected-overlay tracking, and ThreadManager injection, but it must not reintroduce handwritten per-family registration truth that duplicates descriptor metadata.
- That orchestrator should keep its special Spotify phases explicit as one named setup plan rather than scattering ordering across incidental helper call sites. Future widget work may extend those phases, but should not hide new startup/reconcile dependencies behind ad hoc call order.
- `rendering/widget_descriptors.py` also owns the canonical `WidgetsTab` section registry for section order, labels, dev gating, and builder routing. `ui/tabs/widgets_tab.py` may orchestrate lazy/non-lazy mounting, but it must not keep a second handwritten family list for those same sections.
- `rendering/widget_descriptors.py` owns `WidgetsTab` standard-section load routing through descriptor-owned section and single-section helper seams, so build/load pairs do not drift back into handwritten imports and per-section dispatch chains inside `widgets_tab.py`.
- `rendering/widget_descriptors.py` owns `WidgetsTab` standard-section save routing and preserved-widget-key ownership, including single-section saver access for preview/live-config composition, so save/fallback behavior for lazily unbuilt sections does not drift back into handwritten per-section branches inside `widgets_tab.py`.
- `rendering/widget_descriptors.py` owns `WidgetsTab` section identity, lazy-bootstrap intent, and default-selection policy so fragile assumptions about numeric tab indices, fixed section order, or special “always build this last section” cases do not drift back into `widgets_tab.py`.
- `rendering/widget_descriptors.py` owns `WidgetsTab` CUSTOM size-lock metadata where a section's size controls become derived/no-op in `Custom`, so future widget additions do not have to reintroduce tab-local handwritten lock tables.
- Descriptor helpers may be numerous, but they should stay grouped around one canonical registry truth rather than turning back into parallel ownership. Active descriptor views and descriptor-index lookups may be cached, but that cache must remain environment-aware so dev-gated widget families do not become stale across settings/tests/build paths.
- WidgetsTab-specific descriptor metadata should not duplicate runtime routing truth unnecessarily. For example, a custom-position UI binding may own the combo attr and authored fallback label, but effective position-key ownership should still come from the runtime descriptor contract.
- When a lazy-built section cannot hydrate or save correctly without another section's controls, that inter-section dependency should be explicit in descriptor metadata rather than hidden in tab order or constructor side effects. Mutual dependencies are acceptable if the lazy builder treats "currently building" sections as in-progress rather than recursively re-entering them.
- The default selected `WidgetsTab` section is descriptor-owned so startup/reset behavior does not quietly depend on a hardcoded “section 0” assumption.
- The Defaults section now follows that same descriptor-owned builder/load/save path for shared widget shadow toggles and card-border-width persistence instead of remaining a special inline branch in `widgets_tab.py`.
- When standard widget sections already have descriptor-owned persisted-widget-key metadata, `widgets_tab.py` should prefer descriptor-owned save-result application helpers over manually reassigning those standard section payloads one key at a time. Keep genuinely special merges, such as visualizer mode-preserving persistence, explicit.
- For standard widget sections, `rendering/widget_descriptors.py` owns canonical `WidgetsTab` signal-block attribute membership so repeated load-time bookkeeping stays out of `widgets_tab.py`. Keep only genuinely special non-standard buckets such as visualizer-specific controls explicit when the descriptor layer would not improve clarity.
- `WidgetsTab` load-time signal blocking for standard sections should prefer descriptor-owned target collection helpers over repeating attribute scans inline. Keep only the genuinely special non-descriptor groups as explicit extras at the call site.
- When standard widget sections already have descriptor-owned build/load/save metadata, `widgets_tab.py` should prefer descriptor helper orchestration over keeping its own inline dispatch loops for those same sections.
- Programmatic/lazy settings entry should stay narrow and descriptor-owned too. If `SettingsDialog` or headless callers need a section surface such as Media/Visualizers, they should materialize only the descriptor-declared programmatic dependency set rather than eagerly building every WidgetsTab section.
- Descriptor-owned lazy/programmatic `WidgetsTab` hydration must also run under the same loading/save-suppression guard as full tab load. Building or hydrating a lazily materialized section must never save partial/default widget state back into settings just because constructor-time control sync emitted ordinary UI signals.
- Standard widget default-backed `WidgetsTab` attrs such as base colors, media artwork size, and card-border-width defaults should also prefer descriptor-owned init metadata when that replaces a second handwritten attr table without obscuring genuinely special settings behavior.
- Runtime capability ownership also belongs in `rendering/widget_descriptors.py`: startup stage, anchor dependence, service-backed status, descriptor-owned service-runtime contract participation, settings-section ownership, and live-refresh routing must not drift back into handwritten prefix checks inside `WidgetManager`.
- Canonical widget settings position options also belong in `rendering/widget_descriptors.py`. Widget settings builders must consume descriptor-owned position labels/capabilities instead of retyping the same 9-grid list in each tab module.
- Descriptor-owned stack-preview/settings-composition metadata should drive `WidgetsTab` preview/save truth for standard widget families instead of per-widget handwritten UI reads where the descriptor can express the same contract.
- Future custom layout/edit-mode capability metadata should extend the same descriptor layer rather than introducing a separate widget-position registry.
- CUSTOM resize must remain descriptor-owned and widget-logical: plain scroll wheel and corner-drag resize may adjust widget-owned size axes only where the widget can express that safely, both paths must feed the same widget-logical resize authority, and participating widgets must keep clear runtime/settings-side recovery affordances.
- Descriptor-owned CUSTOM runtime exceptions must stay explicit too. If a family such as `gmail`/`reddit` keeps committed width but needs content-owned vertical height after replay, that exception belongs in descriptor-owned CUSTOM capability metadata plus the shared custom-layout persistence seam, not in ad hoc widget-local settings writes.
- First meaningful CUSTOM edit-mode phase is now landed as a shell-driven global active-display session with explicit monitor-routing authority:
  - `rendering/custom_layout_contract.py` owns the normalized display-local rect contract and persistence helpers under `widgets.custom_layout`,
  - `rendering/custom_layout_manager.py` owns global session lifecycle across the active `DisplayWidget` set, temporary shell orchestration, save/cancel, runtime-update deferral, intentional Media-shell visualizer recovery, numbered-monitor ownership transfer between compositor-backed displays, and canonical post-save/revert rebuild across display instances,
  - `widgets/edit_shell_widget.py` owns the temporary display-owned shell surface, resize/restore affordances for participating families, and optional widget-specific recovery actions exposed by the session manager,
  - `rendering/widget_descriptors.py` now also owns the live widget attr name and first-phase resize-mode ownership for CUSTOM edit participation.
- First-phase CUSTOM precision editing is also descriptor/contract owned rather than mouse-handler ad hoc: live shells clamp to one display at a time and snap against the shared 12px grid scaffold, real display edges, peer widget shells, and destination-display live peers only while an edit session is active. The static overlay must reflect that primary snap scaffold truth rather than implying a separate guide system.
- Media-shell **Reset Visualizer** is an edit-session recovery action, not an authored-layout reset. It must create or restore an editable visualizer shell rectangle in the active session, may use a transparent placeholder when live capture is missing, and must not clear visualizer `Custom` authority, save settings, exit edit mode, or request a runtime rebuild by itself; the normal Save action remains the only commit path.
- Entering settings while a CUSTOM shell session is active must cancel the global shell session first, then proceed through the normal engine stop/settings-dialog startup path. Settings entry must not rely on later display teardown to clean up edit-session surfaces indirectly.
- Explicit `Custom` position-slot UX is also now part of the first-phase contract: participating widget families expose the `Custom` slot through descriptor-owned position labels, WidgetsTab disables that slot until a real saved custom layout exists, persisted widget position now accepts `custom` as a first-class runtime value, saving an edit session promotes the relevant widget-family settings position to `Custom`, and switching back to an authored position must stop runtime custom-rect authority without deleting the saved payload.
- The last known non-`Custom` authored route is also a first-class saved contract: participating widget families persist their most recent authored `position` + `monitor` route separately from CUSTOM geometry so edit mode can provide a global reset-to-authored action without guessing from live shell state.
- That authored-route restore mutation must be shared, not duplicated: runtime context-menu reset, invalid-route runtime recovery, and any settings-dialog “Disable Custom Mode” affordance should call the same pure settings-level helper to restore last-known authored routes and clear the targeted CUSTOM geometry payload.
- Canonical application-default position reset is a separate contract from authored-route restore. Settings affordances that promise “defaults” should reset widget position/monitor routes to the current profile's shipped defaults (Normal vs MC) while also clearing persisted CUSTOM geometry payloads.
- Base widget settings remain canonical even while `Custom` resize is active. For example, Media runtime refresh must still reapply authored `font_size`, `artwork_size`, and rounded-artwork-border settings; CUSTOM resize is an overlay scale contract, not a replacement settings section.
- WidgetsTab should visibly lock only those size-driving controls that lose live authority while a widget family is in `Custom`. The first disabled control in an affected section should surface the styled orange `Disable Custom Mode To Change!` affordance, and unrelated style/behavior controls such as font family, provider choice, or visualizer mode/preset controls should remain editable when they still affect the live result.
- CUSTOM uniform resize is now landed for the safe authored-size families that already expose real widget-logical hooks: `clock*`, `weather`, `media`, `reddit*`, `gmail`, `imgur`, and `spotify_volume`. `spotify_visualizer` now also treats its saved CUSTOM rect as authoritative outer-card geometry through the visualizer card-geometry contract instead of relying on shell-only behavior.
- `spotify_visualizer` now uses an explicit routing-mode contract:
  - while its effective slot is not `Custom`, `position` / `monitor`, authored placement, startup, fade/reveal, and visibility remain exact `Follow Media` parity,
  - while its effective slot is `Custom`, it owns its own `position` / `monitor`, may live on a different numbered display from Media, and runtime positioning must honor its saved per-display rect instead of re-anchoring to the media card,
  - even in `Custom`, it remains content-anchored to Media and still hides with the anchor media widget,
  - creator/setup paths must resolve a canonical media anchor across the active display set instead of requiring a local media widget.
- `spotify_volume` remains intentionally media-owned even after the visualizer routing split: it may persist its own per-display rect only under `media.position == Custom`, and runtime positioning must honor that rect and its saved scale contract instead of always forcing the slider back to the authored slider footprint.
- `spotify_visualizer` CUSTOM sizing preserves the committed outer width and top-left/display ownership. Saved CUSTOM width must not silently widen or narrow on runtime replay; only live height may be re-resolved from current mode/preset-authored card metrics plus the saved visualizer scale payload.
- Visualizer edit-mode participation should not snapshot only the QWidget shell or only the GL layer. Its edit shell must use the composited display-surface view of the current visualizer rect so the painted card, border, stencil-clipped GL content, and overlay shell remain visually coherent during CUSTOM editing.
- That composited visualizer edit-shell capture should be built from the visualizer card snapshot plus the GL overlay framebuffer, not by grabbing the whole display surface. Whole-display grabs are not a safe dependency for entering edit mode on a compositor-backed display.
- `monitor` remains the authoritative cross-display ownership field. CUSTOM layout geometry never replaces monitor routing; numbered-monitor widgets may change ownership through edit-shell transfer, while `ALL` widgets stay display-locked and surface an explicit blocked affordance instead of silently collapsing their routing semantics.
- CUSTOM edit mode itself is global to the active display set. Entering it from one display should activate shells on every live compositor-backed `DisplayWidget`, and cross-display handoff targets must come from that active display set rather than every raw OS screen.
- The normal visualizer runtime placement path must honor committed CUSTOM rect authority when the owning media slot is set to `Custom`; otherwise post-save/runtime rebuilds will silently re-anchor the visualizer back to the media card and fight saved geometry.
- Saved CUSTOM geometry must reapply through shared runtime seams, not one-off widget patches. `BaseOverlayWidget` therefore treats `_custom_layout_local_rect` as an authoritative local-geometry override, while `DisplayWidget`/`WidgetManager` reapply saved custom layouts after widget setup, resize, and live widget refreshes. Visualizer-specific startup stabilization may exist only as a cautious delayed verify/confirm seam on top of that shared contract, not as a blind next-turn geometry rewrite.
- Saved CUSTOM geometry must also survive live widget self-resize pressure. If a CUSTOM-positioned overlay recalculates its own minimum/maximum size from content, refresh, or typography changes, the saved `_custom_layout_local_rect` remains authoritative and must be reasserted through the shared overlay seam instead of letting the widget quietly grow/shrink itself out of the committed rect.
- Shared CUSTOM replay must reassert the committed outer rect after any descriptor-owned resize payload is applied, not only for special widget families. Font, artwork, icon, and track scaling may update internals, but they must not become a second outer-geometry authority during runtime replay.
- Shrinking a widget below its authored/default runtime size is a first-class CUSTOM contract too. Runtime replay must temporarily override any earlier authored minimum/maximum size constraints so a committed smaller CUSTOM rect can actually take effect after rebuild.
- CUSTOM layout screen ownership must use live display binding, not constructor-time guesses. `CustomLayoutManager` should re-sync against the owning `DisplayWidget` screen binding before session start, save, and runtime reapply so edit-mode persistence does not depend on whether `_screen` happened to be populated during `DisplayWidget.__init__`.
- During widget rebuild/setup, saved CUSTOM geometry should be applied before widget activation/fade startup so settings-entry and edit-mode rebuilds do not briefly expose authored-anchor positions before the real reveal path.
- Settings-entry and CUSTOM runtime-reload display recreation must also arm a short pointer-event suppression window on the newly recreated `DisplayWidget` set so the save/revert click that triggered the rebuild cannot be re-consumed as startup-time next-image/exit/context-menu input on the fresh displays.
- Edit-mode display ownership should mirror normal runtime: temporary grid and shells are display-owned child surfaces, and cross-display movement reassigns shell ownership by explicit reparenting to the target display instead of relying on independent top-level windows plus repeated desktop-stack correction.
- `EditShellWidget` speaks global geometry only, while `CustomLayoutManager` owns all live global-rect application and global-to-display-local translation. Live drag should not apply against an outdated parent/display first and "correct later."
- Live move drag should stay fluid: during drag, CUSTOM movement clamps to the active display set and updates alignment guides, but authoritative snap-to-grid / snap-to-peer position commits happen on drag finish rather than forcing sticky snap corrections on every mouse-move frame.
- Saved CUSTOM rect replay must clamp against the real target display bounds through the shared custom-layout contract. Denormalized saved width/height are not sacred if they would extend past the live display.
- Edit-mode stack ordering should also stay session-owned. Background clicks, shell menu requests, and menu show/hide should all funnel through one deferred restack seam, and active edit-mode context menus should suspend shell/grid restacks until the menu closes so popup ordering does not fight the display-owned grid/shell surfaces.
- CUSTOM save/reset now commits through the canonical widget rebuild path so reveal/fade behavior matches ordinary runtime setup instead of depending on per-widget live refresh seams.
- CUSTOM save/reset should not briefly restore the old live widgets or paused Spotify-dependent special widgets before rebuild. The old runtime layer stays hidden while the rebuild path becomes authoritative.
- Runtime CUSTOM rebuilds must explicitly re-prime fade coordination when the compositor is already ready; otherwise the cold-start one-shot compositor-ready signal will not refire and primary overlays can remain queued forever after edit-mode exit.
- Runtime CUSTOM rebuilds must also clear stale fade participants before registering the new widget set; otherwise compositor-ready rebuilds can keep waiting on overlays from the previous setup cycle and leave rebuilt widgets permanently queued.
- CUSTOM display bindings should resolve through canonical display identity first, but still recognize legacy saved buckets whose keys were identity-plus-geometry (`serial|...|geom:...`). Exact geometry equality is not a safe long-term match requirement for MC display persistence.
- Legacy authored widget stacking does not apply while any widget family is using the `Custom` slot. Once CUSTOM mode is active anywhere, shared stacking must fully stand down for that runtime/layout pass so committed CUSTOM geometry remains the sole positioning authority after rebuild.
- Legacy authored widget stacking is still valid for non-`Custom` anchor-based layouts and is not a general removal target yet. Only CUSTOM-positioned families are exempt from it.
- Global reset-to-authored from edit mode clears CUSTOM geometry payloads, restores the saved authored route, and then uses that same canonical rebuild path so all widget families return to their authored anchors deterministically.
- Local edit-shell resets are split by contract: `Reset Position` is a session-local geometry/ownership reset for that shell, while `Reset Size` is a session-local size-contract reset. Neither should masquerade as the global authored-layout reset.
- CUSTOM edit mode may render a temporary low-opacity grid overlay, but that overlay is an edit-session affordance only. It must stay above the compositor and below the edit shells, and it must not become part of the saved geometry contract.
- During an active CUSTOM edit session, `DisplayWidget` must suppress normal exit gestures and defer processed-image updates so the user edits against a stable scene instead of live transition churn.
- During an active CUSTOM edit session, the real system cursor is the sole cursor authority. Interaction-mode / Ctrl halo state must be suspended for the duration of the session and restored only by returning to the ordinary post-edit screensaver cursor policy, not by force-reviving the halo on exit.
- During an active CUSTOM edit session, runtime widgets represented by shells must also suppress ordinary visibility re-entry paths caused by live provider/media updates. Edit shells are the only visible authority until save/cancel/reset ends the session.
- `spotify_volume` session-volume truth should come from the real provider-owned mixer session without a high-frequency polling loop. Activation, provider retargeting, and hidden→visible transitions are valid resync boundaries; continuous polling is not.
- Narrow CUSTOM participants that still remain move-only must preserve their authored footprint during snap/clamp/save/reapply instead of inheriting the generic resizable-widget minimum edit rect. `spotify_volume` is no longer in that class because it now uses an authored resize-scale contract while remaining media-owned.
- Shared lifecycle mechanics for service-backed overlay widgets belong in `widgets/service_widget_runtime.py`: parent transition-busy probing, deferred single-shot timer ownership, deferred refresh/result staging, spinner suspend/resume, visible-fallback preservation for non-authoritative empty/error results, deferred-runtime timer/state reset, and timer-stop cleanup should extend that seam instead of being recopied into each widget. Provider logic, authored rendering, and widget-specific data semantics stay local.
- Shared fetch-in-progress begin/end guards for service-backed overlay widgets also belong in `widgets/service_widget_runtime.py` when Gmail/Reddit-style widgets share the same contract. Keep provider-specific fetch payload semantics local.
- Shared manual-refresh request flow for service-backed overlay widgets also belongs in `widgets/service_widget_runtime.py` when Gmail/Reddit-style widgets share the same contract: enabled checks, duplicate-fetch short-circuiting, transition deferral, and failure cleanup should not be recopied per widget.
- Automatic service-update policy is also shared contract work: Gmail, Reddit, and Weather must honor one process-wide `--noupdates` CLI flag that disables automatic retrieval work, including startup fetches and periodic timers, while preserving manual refresh affordances such as double-click and refresh spirals.
- Fresh cache is a separate startup-only contract from `--noupdates` for Gmail/Weather-style widgets: when those caches are newer than 15 minutes, startup should reuse that cache and skip the immediate startup refresh without disabling later periodic timers or manual refresh. Reddit is the intentional exception: it always reuses cached posts visibly, but automatic startup refresh runs only when updates are enabled, the shared Reddit blocked-cooldown gate is clear, and a persisted recent-startup-attempt cooldown is not active. Startup must stamp that recent-attempt gate before the fetch is submitted so rapid relaunches do not renegotiate immediately.
- Shared list-capacity policy belongs on the same kind of canonical seam: `reddit`, `reddit2`, and `gmail` should consume the shared `5..25` capacity contract rather than drifting into widget-local UI/runtime ranges. Dormant `imgur` remains excluded because it is grid-capacity, not row-capacity, work.
- Authored non-`Custom` widget stacking remains a shared runtime contract too: stack participants belong in the canonical display/widget-manager stack seam, and content-height-driven overlays must request a shared deferred restack there rather than relying on widget-local special cases.
- Non-`Custom` stacking is column-aware, not merely same-anchor-aware: `Top Left`, `Middle Left`, and `Bottom Left` share one authored left-column plan (likewise center/right). The planner must preserve authored `top` / `middle` / `bottom` band order while compressing inter-widget spacing as needed.
- That authored planner must measure real visible/runtime footprint, not inflated shadow/collision envelopes, or it will falsely conclude that a fitting column overflows.
- Companion/media-relative widgets such as `spotify_visualizer` remain excluded as independently movable authored stack participants, but their known follow-media runtime footprint should still block lane space through the same shared planner so later fade-in does not overlap already-stacked authored widgets. When the visualizer follows media, authored stacking should treat that media+visualizer occupancy as one fixed obstacle rather than something the planner is allowed to shove around. `Custom` families remain excluded from that authored planner.
- Which widget participates in which shared service-runtime contract now belongs in `rendering/widget_descriptors.py`, not in a vague `service_backed=True` assumption. Future widening should extend descriptor-owned contract metadata first, then consume that truth in code/tests/docs.
- Service-backed widgets that keep narrower contracts, such as Weather, should still funnel repeated local scheduling policy through one canonical widget helper path so lifecycle-entry drift does not reappear between `start()` and lifecycle activation hooks.
- Service-backed widgets that do not yet participate in the shared helper contract, such as Imgur in this checkout, should still keep timer ownership and live timer reschedule policy in one local canonical path rather than duplicating stop/start logic across setters and lifecycle hooks.
- Dependent media-adjacent widgets that keep their own local timer/debounce policy, such as the Spotify volume slider, should also centralize stop/deactivate/cleanup timer-reset behavior in one local helper instead of repeating slightly different flush-state teardown branches.
- Media-family widgets that keep richer widget-local polling semantics, such as `MediaWidget`, should also centralize smart-poll timer teardown and pending optimistic-state debounce teardown in canonical local helpers rather than keeping separate stop/deactivate/force-restart branches for the same timer state.
- Media metadata relayout identity should follow visible text/layout inputs only. Album/state/artwork/provider polling churn may still refresh the card, but it must not become a second font-sizing or formatting authority when the user-visible title/artist presentation is unchanged.
- Small media-adjacent dependent widgets with staged reveal state, such as `MuteButtonWidget`, should also centralize enable/disable/cleanup runtime reset behavior so poll state and secondary-stage reveal state do not leak across reuse paths.
- Keep stable widget ids and settings keys. New widget families should extend the descriptor registry instead of adding another ad hoc setup branch unless the runtime truly requires a special-case path (for example, Spotify-dependent secondary-stage widgets).
- Descriptor refactors are parity-first: monitor gating, expected-overlay truth, reuse behavior, factory kwargs, and startup-stage ownership must remain unchanged unless a deliberate migration is documented.

## 9. Rendering and Input Contract
- GL-first rendering path with safe fallback behavior.
- Input routing is centralized; no widget-specific ad hoc global key/mouse handlers.
- Focused keyboard transport shortcuts should travel through the same centralized input contract as the other runtime hotkeys. `Space` and `Home` are the focused play/pause hotkeys, while `Left` and `Right` are the focused previous/next track hotkeys; all four should route through the media widget's transport-command/feedback path rather than bypassing the input contract. Focused volume shortcuts stay on that same shared input seam too: `Up` / `Down` should reuse the Spotify volume slider step contract, while `PgUp` / `PgDn` and `End` should use the shared system-audio master volume / mute contract rather than widget-local ad hoc handlers.
- Runtime interaction mode behavior must not break settings launch or shutdown paths.
- Stop/settings-entry teardown must use the narrow quiesce boundary before displays are cleared or hidden: `ScreensaverEngine.stop(...)` should suppress new work through `DisplayManager.quiesce_all()` → `DisplayWidget.quiesce_for_runtime_pause()` → `WidgetManager.prepare_for_runtime_pause()` rather than relying on late cleanup side effects.
- In MC builds, Interaction Mode is runtime policy, not an optional session toggle: MC startup and runtime reads treat it as enabled, and MC settings/context-menu surfaces must not offer a disable path that can strand the user outside the intended interaction model.

## 10. Build Variants
- Standard saver and MC maintain separate settings profiles.
- Frozen preset resolution converges on shared ProgramData curated root.

## 11. Gmail Widget Architecture

### 10.1 Availability
- Gmail widget is a normal feature and must not be hidden behind a dev-gate or CLI flag.
- Widget factory registration, settings UI, expected-overlay checks, and rendering paths are always available; actual overlay display is controlled only by `widgets.gmail.enabled` and monitor selection.

### 10.2 Backend routing
- Unified backend (`core/gmail/gmail_backend.py`) routes to OAuth/REST or IMAP based on config
- OAuth mode: `core/gmail/gmail_oauth.py` (PKCE flow, DPAPI token storage)
- IMAP mode: `core/gmail/gmail_imap.py` (App Password authentication)
- REST client: `core/gmail/gmail_client.py` (metadata-only API calls)
- Deep-link helpers: `core/gmail/gmail_deeplinks.py` owns Gmail web URL construction
- IMAP/Gmail row links use `X-GM-THRID` decimal ids converted to lowercase hex for `#all/<thread_hex>` routes; RFC `Message-ID` search is the fallback when thread id is unavailable

### 10.3 Widget contracts
- Overlay widget: `widgets/gmail_widget.py` (email list, actions, paint events)
- Widget components: `widgets/gmail_components.py` (nine-position GmailPosition enum, relative-time formatting, sender/subject cleanup helpers, email cache)
- Settings UI: `ui/tabs/widgets_tab_gmail.py` (backend selector, credentials, widget settings, sender/subject cleanup controls)
- Gmail settings remain a flat dict under `gmail` in `core/settings/default_settings.py`; do not add a Gmail settings dataclass unless the whole widget settings architecture is deliberately migrated
- Gmail settings UI load/reset/import code must block signals for every Gmail control while values are being populated. `GMAIL_SIGNAL_BLOCK_ATTRS` is descriptor-owned in `rendering/widget_descriptors.py` and re-used by the Gmail settings module rather than duplicated there.
- Gmail settings panel/button visibility updates must avoid redundant `setVisible(...)` calls during construction and load, following the historical R-18 settings flicker guardrail. When the settings parent page is hidden, backend-specific child panels must compare desired state against explicit hidden state, not transient `isVisible()`, so OAuth-only text/buttons stay hidden for IMAP on fresh settings open.
- If the Gmail backend service is temporarily unavailable during settings construction/load, backend panel visibility must fall back to the UI backend selector value instead of showing both backend panels.
- Gmail settings construction must not synchronously load backend/auth credential state. The initial backend-specific UI should be derived from the combo/defaults, with credential/auth refresh queued after construction.
- Styled combo boxes must not force popup-view creation during settings construction; popup view styling belongs on popup open, not in constructors.
- Gmail IMAP Save & Test must not block the settings UI. Test supplied credentials on the IO pool first, save credentials only after a successful test, and return all UI label/button/popup updates to the UI thread.
- Gmail OAuth code exchange must also stay off the UI thread. The callback server may acknowledge the browser request immediately, but token exchange/network work must go through a real `ThreadManager` IO task and marshal Qt signal/UI updates back to the UI thread.
- Gmail user-facing settings UI defaults must be read from canonical widget defaults; missing Gmail defaults should fail loudly in tests instead of quietly introducing new hardcoded fallback drift.
- Settings-dialog cached widget defaults must be treated as an optimization only. WidgetsTab must merge cached defaults with fresh canonical defaults, and cache invalidation must include both `defaults.py` and `default_settings.py` so new Gmail defaults are not hidden by stale cache data.
- Gmail visual settings must keep geometry and hit rects aligned: display, position, single `gmail.width`, Media-style margins, header frame, and row click targets must be derived from measured widget layout. Gmail must not expose custom per-side padding controls unless the whole widget family gains the same concept.
- Gmail header styling must maintain visual parity with peer overlay headers (Media/Spotify/Reddit): comparable logo scale, frame border weight, radius, and top inset. Default Gmail header font/logo sizing follows Media's derived relationship (`font * 1.2`, then `header * 1.3`), with `gmail.header_logo_px_adjust` reserved for final visual nudging.
- Gmail row interaction must work in normal and MC modes: full row sender/subject hit rect opens the message URL through central input URL routing, while the vertical action-menu hit rect opens the menu and must not be consumed by row click handling
- Gmail secure-desktop/normal SCR URL clicks use the shared helper/task-scheduler bridge route. MC Reddit URL clicks keep the MC direct Qt/browser route. Where multiple eligible browser windows already exist, both paths may prefer a display-0 browser window first, but they must still fall back cleanly to the current first-match/direct-open behavior.
- Gmail MC action-menu popup handling must not immediately reclaim DisplayWidget focus in a way that steals input from the popup; the menu object must remain alive until it hides.
- Gmail action-menu operations must have real backend effects for the active backend. IMAP actions must use IMAP-safe identifiers such as UID, not only Gmail web/message ids.
- Gmail action menus must include Mark as Read/Unread, Spam, and Delete where the active backend can support them. Archive is hidden for IMAP because runtime testing repeatedly showed it accepts no reliable local behavior; the Archive code path may remain for OAuth/future diagnostics. Required Gmail action image assets must be present in the repo and covered by build-script asset tests; missing optional image assets must still fall back to simple generated icons rather than silently leaving important actions visually blank.
- Gmail display text cleanup is part of the widget contract: title casing must preserve contractions, sender cleanup must prefer RFC-style display names over raw addresses, subject/sender shortening must run before final pixel elision, and punctuation-only separator tokens such as `|` or `-` must not count as words
- Gmail row text columns must remain stable across visible rows: timestamp, sender, and subject slots should use shared widths so shorter senders leave blank space instead of moving the subject start position; the sender/subject boundary is user-adjustable via `gmail.sender_column_width`
- Gmail IMAP Inbox listing must preserve the active mailbox order returned from the selected label instead of over-fetching and date-sorting in the widget. Runtime evidence showed the over-fetch/date-sort mitigation mismatched Gmail's visible Inbox.
- Gmail cached mail must be stored and loaded in the same backend order used for visible display, so startup cache display does not visibly reorder a few seconds later when the live fetch completes.
- Gmail live fetches that come back empty must not displace valid cached or already-displayed mail. When Gmail has valid visible content, an empty live result is treated as non-authoritative and the existing display remains in place.
- Gmail IMAP partial per-message fetch failures must also be treated as non-authoritative. A degraded partial result must not overwrite a fuller cached/already-displayed list or poison the cache with a truncated mailbox snapshot.
- Gmail error completion should continue to use the shared `widgets/service_widget_runtime.py` visible-fallback contract when deciding whether an empty/error fetch is non-authoritative once valid content is already on screen.
- Gmail sender casing may apply conservative display capitalization for visual consistency, but must preserve established mixed/all-caps brand tokens such as `PayPal`, `ChatGPT`, `FNB`, and `AI`
- Gmail date display modes are `relative`, `numeric`, and `words`. Relative uses age labels such as `Yesterday`, `Last Week`, `Last Month`, and `Two Years Ago`; numeric uses numbered dates; words uses calendar labels such as `April 16th`.
- Gmail thread/duplicate display may collapse truly identical or Gmail-threaded entries only when `gmail.group_threads` is enabled. It defaults to off until grouping semantics match Gmail well enough in runtime, and read/unread groups must remain separate.
- Gmail IMAP Archive is considered unsupported/hidden for now. The retained code still attempts `-X-GM-LABELS` before hard-named All Mail MOVE for future diagnostics, but the IMAP menu must not present Archive as a working user action.
- Gmail may expose manual refresh through an optional, default-on quiet icon-only refresh control and blank-space double-click, but refresh must respect fetch-in-progress guards and must not animate or repaint continuously while idle. If a hand-drawn arrow reads ambiguously in runtime screenshots, prefer a neutral spiral or asset-backed icon over repeated arrow geometry tweaks.
- Gmail user-facing defaults must come from the settings/defaults system. Hardcoded Gmail values are acceptable only for private drawing constants or legacy migration fallbacks.
- Gmail settings buckets must not disable/re-enable whole-dialog updates or pre-polish hidden bucket bodies by temporarily showing them during settings construction. R-18 established constructor-time visibility calls as a settings flicker hazard, so bucket toggles should use ordinary guarded body visibility changes and keep runtime flicker validation open until proven.
- Gmail Text Limits settings should stay readable at normal settings widths: sender word and sender-column controls on one row, subject word and subject-character controls on a second aligned row/grid.
- Gmail must not do per-tick network work, pixmap scaling, lazy pixmap conversion, over-painting, or unnecessary `update()` calls when its data and animation state are unchanged.
- Gmail stable visual content may be cached in a DPR-aware transparent pixmap, but live dynamic controls such as the refresh spiral must be painted on top without invalidating the stable cache. Cache regeneration must not change widget graphics effects, hide/show widgets, reparent, resize, or call overlay-effect invalidation because Qt shadow/effect corruption is a known fragile area.
- Shared overlay-effect invalidation is now a narrow transient-opacity refresh seam only. It exists to repaint widgets that currently own a live `QGraphicsOpacityEffect` fade, not to perform broad menu/focus/display-change cache busting for painter-owned shadows. Do not attempt to detect shadow corruption by introspecting `QGraphicsEffect` state alone; the known failure was visual Qt pixmap/cache corruption and should be treated as a multi-monitor runtime validation problem if it ever reappears.
- Runtime widget card shadows are painter-owned and controlled by `widgets.shadows.enabled`, not by Qt drop-shadow effects. Framed overlay cards use cached DPR-aware painter output and explicitly clear each transparent backing region before painting so stale shadow pixels cannot accumulate in the card gutter. `widgets.shadows.text_enabled` controls painter-drawn text shadows and `widgets.shadows.header_enabled` controls painter-drawn header-frame shadows. The Spotify visualizer GL overlay uses a rounded-rect stencil mask in `paintGL()` whenever the painted card shadow path is active; the mask inset must include the 1-px painted-frame inset (`inset=1.0 * dpr`) plus `border_width_px * 0.5 * dpr` so GL content stays inside the inner edge of the centred card pen stroke without changing visualizer content size, amplitude, curve scale, or authored mode behavior.
- Gmail refresh must avoid visible UI churn during pending or active image transitions. If any parent display in the Qt parent chain reports accepted image-change work or a running transition, refresh start should be delayed and fetched mail/error results should be held briefly and applied once idle, so spinner animation, network task submission, cache writes, card-height recompute, unread signals, sound detection, and full widget repaints do not compete with transition frames. If a transition is requested after a refresh is already in flight, Gmail must suspend live refresh-spinner repainting immediately and keep result application deferred until idle.
- Gmail transition-aware refresh deferral, deferred fetch-result/error staging, and deferred single-shot timer ownership should continue to use the shared `widgets/service_widget_runtime.py` seam unless Gmail acquires a contract the shared helper truly cannot express.
- Gmail refreshes that return the same visible message list and unread count must not rewrite cache or repaint. Gmail cache writes should use the IO thread pool when available; the UI thread should only perform Qt-owned painting, state application, signals, and UI/media objects that require it.
- Gmail must participate in the shared widget performance logger when perf metrics are enabled, including at least paint, refresh dispatch, fetch result/error apply, and cache write buckets so regressions appear in `perf_widgets.log`.
- Shared browser foreground preference may prefer an already-open eligible browser window on display 0, but it must remain a narrow best-effort ranking policy over the existing launch paths. Do not add brittle browser automation, process injection, or window-moving behavior.
- Gmail build/release work must verify all Gmail image assets, notification sound assets, Qt multimedia dependencies, and generated/fallback asset dependencies are included in build scripts, frozen build config, resource copy steps, and installer/package outputs. Widget image lookup must not depend only on the launch cwd, because standard `.scr` launches can start outside the app directory. Frozen builds should prefer `%ProgramData%\SRPSS\sounds\tutuogg.ogg` for the default notification sound, with `resources/tutuogg.ogg` as the script/dev fallback. Build scripts must include only the default OGG, not the entire `resources` directory, so ignored local OAuth files are never bundled. Final packaged artifacts still require runtime validation.
- Gmail must not fade into view when there is no authenticated account information and no usable cache.
- Gmail worst-case empty-state copy such as `No unread emails` is a fallback-only surface and must render in the content area below the header frame, not centered across the entire card.

### 10.4 Security invariants
- OAuth tokens stored encrypted via DPAPI
- API calls are metadata-only (no body/snippet content)
- `EmailMetadata` may contain provider ids needed for links/deduping (`X-GM-THRID`, `X-GM-MSGID`, RFC `Message-ID`, IMAP UID), but must not contain bodies, snippets, or raw headers
- Secure-desktop/browser opening must use the correct runtime route: SCR/secure-desktop paths use the helper/secure launcher bridge, while MC-mode row/header URL clicks should reach central input routing and open directly via Qt rather than the Reddit helper bridge
- Display-0 browser preference must stay centralized in the shared Windows/browser routing seam. Gmail/Reddit widget click handlers must not grow their own monitor/window-enumeration logic.
- Reddit widget controls that consume a click without producing a URL, such as the refresh spiral, must not set the central `reddit_handled` URL flag. Only a resolved Reddit URL should request the normal-build helper/exit path.
- Reddit refresh spiral clicks must queue refresh through the existing Reddit fetch path, respect fetch-in-progress guards, and defer refresh start/result apply/cache regeneration while parent display transitions are pending or active when an existing cached pixmap can be reused. If a transition is requested after a Reddit refresh is already in flight, Reddit must suspend live refresh-spinner repainting immediately and keep result application deferred until idle.
- Reddit transition-aware refresh deferral and deferred single-shot timer ownership should continue through `widgets/service_widget_runtime.py` rather than reintroducing private parent-probe/timer helpers.
- Reddit empty/error fetches that arrive after valid content is already visible are non-authoritative by default and should continue to preserve the current display through the shared `widgets/service_widget_runtime.py` visible-fallback seam unless a future widget-specific rule explicitly overrides that behavior.
- Reddit post-source acquisition is an explicit provider seam owned by `core/reddit_post_provider.py`. The branded Reddit widget keeps card rendering, cache authority, cooldown UX, staged growth, and click routing local; swapping future external or authenticated sources must not duplicate or replace that card/runtime ownership.
- Reddit automatic retrieval uses a conservative periodic widget cadence: roughly every `15min` per Reddit widget, with `reddit2` phase-staggered from `reddit` on initial timer start rather than having a permanently longer repeat interval. Startup refresh gates may suppress the startup fetch, but they must not prevent the periodic timer from being armed when automatic updates are enabled.
- RSS image-source startup negotiation must use the real runtime pool target rather than an unrelated fixed disk-cache ceiling. When the on-disk RSS cache already satisfies the effective startup pool target derived from the queue/preload caps, startup should skip Bing/Flickr/NASA negotiation entirely; high-quality fallback feeds are only for real deficits below that target.

## 12. Spline Curve (`devcurve`) Visualizer

- `devcurve` is the runtime id for the Spline Curve visualizer.
- Spline Curve foreground specular uses the existing specular alpha path for idle/play behavior: runtime activity fades the specular multiplier down while paused/idle and back up when playback resumes.
- The idle specular fade must not introduce a new shader shape mode, full-width blob chaining, or preset value enforcement. Authored preset alpha remains the base value; runtime activity only multiplies it.
- No credential leakage in tests (all mocked with fake data)

## 13. Documentation Contract
- `Index.md`: module map.
- `Docs/Contracts.md`: short contract index for fast owner lookup.
- `Current_Plan.md`: active priorities only.
- `Docs/Guardrails.md`: policy/rules.
- `Docs/Historical_Bugs.md`: historical timeline and root-cause record.
