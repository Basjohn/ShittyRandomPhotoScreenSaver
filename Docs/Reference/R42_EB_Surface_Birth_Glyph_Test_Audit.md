# R42 | EB Surface EOL, grouped births, Bounce and UI regression gates

**Status:** all new source repairs are `[~]` and remain unaccepted; Bounce is `[ ]` and has not been changed. No change to authored presets, Settings values or light/ray projection. The visible water screenshot and the 3D editor view cannot be compared by pixel position without the production camera matrix. R41 interface/source authority work remains live.

## 1. Premature upper-water disappearance

The R37 logical transport placed EOL behind the authored End plane for every light mode. Source `widgets/spotify_visualizer/extruded_bubble_simulation.py`: before R42, `sum((position-end) * stream_direction) >= 0` set `leaving=True`, regardless of `WATER_SURFACE_Y=9`. A manually authored End could be well below the visible surface, particularly when travelling diagonally. The renderer's Sunlit Surface is a water plane at fixed world Y. The R42 candidate passes the already admitted `extruded_bubble_light_type` into `ExtrudedBubbleControls.surface_scene` without creating an alternate geometry authority. For upward streams in Sunlit Surface only, EOL is based on the logical bubble's upper displayed radius approaching `WATER_SURFACE_Y`. The 0.9 s fade and wake owner remain unchanged; Deep Light and other paths keep authored End. Tests distinguish the modes explicitly.

**Still unproved:** actual native pixel position of the bubble and water surface from that camera pose, false early fade due extreme inflation, movement through the plane before alpha is gone, end-plane vs water-plane preference for custom diagonal layouts, and fade interaction with shell depth/refraction. Instrument per-ID world Y/radius, surface scene flag, leaving edge and camera projection in one recorded snapshot; do not infer height from the oblique editor alone.

## 2. Dense bubble bands at high Spread

The authored Source spawn used to clamp each transverse sample into the fixed scene box, and special-cased Source coordinates exactly on a face by holding those coordinates fixed. At Source on floor, ceiling or wall, that quantizes many candidates to the exact same location or edge. It is a direct source-level explanation for strong narrow clusters despite a high Spread slider.

R42 tries up to 32 bounded true inside-domain samples, never clamping high-spread candidates to the same edge. It also rejects a candidate too close to already admitted bubbles near the inlet; it skips and retries on later logical captures instead of incrementing the number of overlapping IDs or retaining a spawn-credit backlog. Stable identities, default spread, canonical presets, MAX_BUBBLES and the separate intentional Columns control remain intact.

**Still unproved:** whether the perceived bands in screenshots are due mainly to clamping, startup admission cadence, camera perspective, intentional Columns, or alpha/wake synchrony. High target counts could make an especially narrow Source inlet capacity-limited. Distinguish births versus established drifting bands by stable ID, sample min/median separations for new births at Spread 0/1/4, and test Source face/corner, long and short angled streams with music slower/faster/softer transitions. Compare the original 2D Bubble accepted startup seeding only for *algorithmic lessons*, not by resuming forbidden halfway initial population.

## 3. Bounce still insufficient, no unsafe impulse patch

The bounce correction is explicitly overdamped and per-step capped: `move = min(overlap * (1 - exp(-dt/.35)), WORLD_UNIT*.2*dt)`. There is no retained outward velocity to keep the pair separating after the overlap correction. That can result in apparent vibrating recontacts when the underlying stream keeps pushing two bubbles together. Do not multiply that cap blindly or solve contacts in the shader; it risks jumps and breaks physics SSOT. Propose dt-independent contact impulse with smooth logical damping for standalone bubbles and clusters, conserving pairwise separation and using the existing physical radius. Verify recoil through *post-contact relative velocity and signed overlap* per stable pair over several frames, not from a single still image. Fuse/Pop are separate behavior with untouched shares.

## 4. Native test and glyph-specific UI

R41 native result: 2 fail / 10 pass. QML visibility test failed on `findChild` even after its top-level chrome admitted and showed. R42 keeps the actual physical delegate requirement and inspects QQuick `childItems()` recursively after replacing mixed JS-object Repeater data with stable string delegate actions; Lock eligibility remains independent of selection. The EB tooltip failure was a stale raw-text assertion after R41 introduced HTML wrapping. R42 uses Qt `QTextDocument` to verify normalized human-readable text matches the spec for every control and row; does not delete HTML/newlines or audit labels. `WidgetHoverEditGlyphs.qml` re-scales only artwork: Close -10%, Lock -10%, Restore +10%, with unchanged 24px buttons and anchor alignment. The glyph captions are all uppercase, especially CLOSE & DISABLE WIDGET. Event-owned glyph tooltip reveal retains its 1008 ms transparent initial dwell; no Timer/poller/new worker/window.

**Native command from extracted Windows Godzip root** (no full suite, no environment manipulation):

```powershell
& '.\.venv\Scripts\python.exe' -m pytest --noconftest -p tools.pytest_qt_noenv -q tests/test_r39_hover_edit_qml_native.py tests/test_extruded_bubble_lazy_bucket_ui.py
```

If this remains red, preserve the exact Qt warning and component error; do not relax the native tree or hydration or reset all Settings as a workaround.
