# R-118 | 3D Edit geometry and activation lifecycle audit

**STRONG RETENTION VALUE DOCUMENT**

**Scope:** complete source-level review of the G17–G21 implementation and adjacent runtime contracts after the R-116 green 757-test gate exposed a physical Extruded → Shockwave hidden-target failure and Edit-exit corruption. This is NOT a product acceptance certificate; real Windows Qt 6.11 / GL 4.6 physical tests remain required.

**Baseline:** superseding R-117 Godzip, anchored to `8448717216`. Do not migrate to another repo or infer a missing mode from an unrelated prior Godzip. Operator's authoritative `presets/visualizer_modes/spectrum/preset_1_organs.json` is copied unchanged.

## Ownership graph (must remain singular)

| Surface | Authoritative owner | Other systems may do | Forbidden |
| --- | --- | --- | --- |
| Eligible Visualizer modes + interaction mechanics | `core/settings/visualizer_mode_registry.py`: descriptor `geometry_kind` | Query mode capability | Separate mode-specific Edit engines |
| Persisted stage rect / logical viewport by display + compatible mode group | `custom_layout` map, descriptor `layout_profile`, `CustomLayoutSession` drafts | Retained scene consumes projected working geometry | Renderer-owned saved stage, current-mode-to-next-mode borrowing |
| View turn/tilt/orbit | Mode-qualified persistent settings + live controller presentation state | Edit/gesture authors one canonical mode-qualified value | Curated/Custom presets switching angle or changing preset index on orbit |
| Preset/material/response | `visualizer_presets.py` + normalized mode-owned sources | Model activation resolves immutable values | Presets controlling stage, camera, viewport or turn/tilt |
| Live scene/render admission | One `QuickDisplayVisualizerOwner`, controller, logical runtime, snapshot bridge and retained Qt scene | Edit projects temporary overrides | Additional scene cadence, GL/QQuick presentation authority or stale snapshot relabeling |
| Read-only cage + north marker | `edit_content_envelope.py` production-projection mirror -> `CustomLayoutOverlay.qml` Canvas | Paint on structural Edit/mode/pose edges | Cage setting stage, snapping, Fit Scene, audio footprint or persistence |
| Windows runtime re-creation | Existing generation/manager-identity-fenced `custom_layout_reload_requested` lane | One fail-closed reload if partial activation unrecoverable | Self-owned replacement timers, repeated retries, background worker |

## Request → hidden activation → reveal audit

1. `DisplayManager._request_quick_visualizer_mode` validates active/enabled descriptor, forms detached activation config and admits through ONE retained owner. Second requests are rejected while a transition is pending. No setting changes at request time.
2. The existing scene fade is `fading_out` → `waiting_target` → `fading_in` → `idle`, with one logical runtime and one engine transaction per activation. R-117 preflights Edit projection before stopping the outgoing logical runtime; if that **preflight** fails, the old mode stays running.
3. **R-118 correction: provisional Edit admission was not fully reversible.** A first-ever mode profile could be `add_item`-ed to `CustomLayoutSession` and to derived descriptor/scalar maps before its Qt projection failed; only the visible/parked flags were rolled back. The resulting phantom sibling could survive into Save. `CustomLayoutSession.discard_provisional_item` and Edit rollback now remove the new draft and derived caches and reproject the outgoing peer overlays. Existing authored sibling drafts are never deleted.
4. **R-118 correction: latent infinite hidden target.** `waiting_target` can return indefinitely when no fresh target logical frame arrives. `_PREPARED_REVEAL_DEADLINE_S` only bounds *renderer preparation after a frame*, NOT absence of a frame. A single 6s GUI-thread `QTimer.singleShot` is now admitted once per requested activation, generation/serial-fenced and weak-referenced. There is no timer per logical frame, polling or render driver. A fade-out stall still holding the old runtime is cancelled and the old visual restored. A post-teardown/target stall takes the existing fenced generation-recreation lane; it NEVER pretends an old scene frame is a valid target.
5. **R-118 correction: exceptions after teardown.** A failure in engine begin/configure/end, mode mutation, render-source binding or logical restart could leave `_mode_transition_phase='failed'` with Edit Save and Cancel permanently refused. `sync_present` now detects and logs the transaction exception and asks for precisely one existing owner-fenced reconstruction. Subsequent wakes in `failed` are inert, not an exception storm. This is a failure response, NOT a claim that all downstream effects are rolled back in-place.
6. **R-118 correction: completion boundary.** `on_complete` previously executed after phase was marked `idle`. Persistence exceptions escaped without recoverable phase ownership. Completion failure now requests the same one-time fenced reconstruction. Successful completion still persists only after a fully presented target.
7. **R-118 correction: retirement.** Retirement disarms any queued activation-deadline callback **before** detaching Qt/engine routes, even when a logical join subsequently fails. Weak-reference/serial checks and normal `_retired` checks additionally prevent stale owner callbacks from resurrecting a generation.

## Edit, Arrange, Save/Cancel, other adjacent contracts

- `CustomLayoutSession` retains one **live** Visualizer; other named profiles are parked siblings. Its per-profile draft survives repeated mode switches, and one Save/Cancel owns the whole session. A provisional profile **failed during admission** is not an authored draft and must disappear. No extra canonical Settings/geometry map was added.
- `QuickCustomLayoutOwner.save` and `cancel` refuse while activation is not `idle`; this prevents persisting a half-switched working stage or projecting the saved baseline into a mismatched retained renderer. A failed owner takes runtime reconstruction; it does not silently turn Save into success.
- Existing `commit_live_custom_layout` validates scene viewport, exact half-pixel stage envelope, content rotation and active CUSTOM override. The snapshot bridge discards stale unread frames **without changing their presentation identity**. This remains strict.
- Existing Save intentionally persists primitives before its final live-promotion/reconciliation attempt so a dead QQuick owner can be reconstructed from committed truth. This is a **remaining lifecycle exposure**, not equivalent to a validated atomic in-memory commit; its failover must be exercised under a forced retained-object loss. Do not weaken the check to make pytest green.
- Arrange reads active `layout_profile` through the canonical settings/layout map and does not create duplicate visible Visualizer objects. Cross-display transfer is one retained admission, with route ownership migrated via `set_presentation_runtime` and rollback on target-route exceptions.
- `freeform_3d` stage aspect is independently authored; it need not match renderer world aspect. Planar remains single uniform-scale semantics. The transient integer-rounding wheel reference belongs to the working Edit item/Undo, never Settings.
- Turn/tilt are mode-qualified authored state, not preset fields. The existing curated-preset filter deliberately ignores legacy view keys. No change to this filter or to Organs was made in R-118.
- The 3D cage remains one derived eight-corner / twelve-edge Canvas. Its *line stroke* increases 1.5 → **2.5 px** and the face-aligned `N` black stroke 6.2 → **8.6 px**, doubling the visible black outline around the unchanged 3.8 px white body. Letter size and pose are otherwise unchanged. No image, timer or new renderer is used for the cage.

## Failure outcome matrix

| Where failure occurs | Desired resulting state | R-118 guard |
| --- | --- | --- |
| Rejected invalid/disabled/request-overlap | No mutation; current mode visible | Existing admission gate |
| First-use Edit-QML projection | Outgoing mode live; no phantom profile or persisted partial | Provisional cleanup + peer reprojection |
| Fade out with no GUI publication | Outgoing mode remains live, full opacity; pending request abandoned | One-shot timeout abort |
| Old logical join fails / engine transaction cannot begin | Save/Cancel not allowed to commit partial target; reconstruct from Settings | Exception-to-recovery callback |
| Failure after controller mode or engine state changed | Never fake a successful rollback; reconstruct from last committed Settings | Same one-shot fenced recovery |
| Target logical frame never arrives | No indefinite hidden target or permanently unexitable Edit | Single 6s deadline, fenced recovery |
| Completion settings write throws | Not treated as a healthy idle activation | Completion failure recovery |
| Owner retirement / generation change with pending one-shot | No old callback touches Qt or starts new owner | Serial invalidation + weakref + manager identity fence |
| Valid activated mode + Edit Save | Promote same displayed rect/extent, siblings survive | Strict existing retained coherence check |

## Required Windows proof before physical acceptance

Run the expanded grouped Qt tests, including new failure injection. After green: enter Edit in Extruded, switch to Shockwave and back; include fast exit during half-hidden fade and delayed first frame; Save then repeat Cancel. Validate independent sizes/angles across Extruded/Shockwave/Sphere, legacy planar and Arrange, both displays and transfer. The generated failure-injection tests cover the owner’s transition deadline, stale callbacks and failed provisional projection, but **cannot prove native GL resource retirement or application recovery after forced thread-stop failure**. Continue to monitor `--geo` and actual process exit codes. Do not declare the physical crash fixed merely because these tests pass.

## Deferred/remaining audit risks, explicitly NOT accepted

- The Windows Qt scene may still fail GL context/renderer retirement independent of Python callback ownership. A previous physical log had non-joined Python runtime owners after a corrupt Save; root cause of process exit code 1 was not established at the native level.
- A Settings-owned recreation may supersede an activation-failure reload. The engine's existing handler correctly ignores reloads while Settings already owns replacement, but this composite scenario needs real Windows lifecycle verification.
- The mode profile resolver is called after Edit preflight during engine transaction. R-118 now makes unhandled failure fail-closed via reconstruction, but a future refactor should extract a **pure preflight profile record** and commit that exact record once to avoid a second fallible read after stopping the source. Do not add a shadow persisted geometry authority.
- Failure-driven runtime reconstruction loses unsaved Edit drafts. That is preferable to corrupt Settings or a frozen process, but does not equal successful in-place rollback. A future transactional mode activation could snapshot reversible engine/controller state and recover without reconstruction only if testable without duplicate owners.
- A successful 6s timer returning in the background is inert; its presence is bounded. No periodic ticker, QML infinite animator, frameSwapped request loop, or enabled-only-on-demand gate is permitted.

**Status:** R-118 static audit and corrective implementation complete; Windows focused/retained/physical tests pending. G17–G21 remains OPEN. E8 missing Extruded directional shadow remains OPEN and must not be folded into this lifecycle tranche.
