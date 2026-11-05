# Future Work

The single router for **deferred** work. `Current_Plan.md` owns active sequencing. Implemented capability belongs in
`Spec.md` / Architecture / Guardrail / Guide / Reference documents; rejected mechanisms belong in Historical Bugs.

Nothing in this file is automatically admitted. The operator or `Current_Plan.md` must promote an item before implementation.

## 1. Admission rules

For any deferred feature that becomes active:

- record the visual/product contract and concrete acceptance gate before coding;
- join existing canonical registries/descriptors/defaults rather than creating a second catalog;
- use the retained Qt Quick presentation authority and existing lifecycle/resource owners;
- preserve lazy resolution, retirement and count-invariant dormancy;
- use deterministic inputs/seeds and bounded state where applicable;
- prove real Quick rendering, lifecycle and measured CPU/GPU/resource cost, not only an offline preview;
- remove rejected experiments cleanly rather than retaining dormant fallback architecture.

Transition and Visualizer membership is deliberately **count-neutral** here. Source registries own the current catalog; future
docs should not encode a cardinality that becomes stale when another effect is registered.

## 2. Graphics API horizon.

Audit, plan and advise when best to build a custom Vulkan backend with intentional support for FSR <=3 and DLSS <=4.5 where applicable.

## 3. Visual concepts

Accepted transition membership belongs to the canonical registry and `Docs/Reference/Transitions.md`.

The remaining Visualizer modes are **queued in `Current_Plan.md` §7** (Waveform Ribbon → Reactive Liquid / Melt Pool →
Concrete Rain → Usu Moonscape), built on the shared 3D primitives of `Current_Plan.md` §6. Their contracts:
`Docs/Future_Work/Waveform_Ribbon.md`, `Docs/Future_Work/Melt_Pool.md`, `Docs/Future_Work/Concrete_Rain.md`,
`Docs/Future_Work/Usu_Moonscape.md` (with `Usu_Blender_Work.md`). Other mode concepts were dropped on 2026-10-25; the
architecture they called for is the shared step in `Current_Plan.md` §6.

### Usu Moonscape: character/world foundations (deferred until §7.4)

Usu walks, runs, Naruto-runs, skids/falls/gets up and lies down across a round moon under a starscape, with orbit
framing and optional fuzz-tip bloom. Its missing foundations, proven one at a time in offscreen harnesses before
combining (no physics engine, no extra animation clock):

- **S19 → S20:** deterministic validated Blender/glTF bake with provenance-stamped packed assets, then shared
  material/instancing static-mesh rendering. Runtime consumes packed data, not Blender authoring graphs.
- **S21 → S22 → S23:** bounded GPU joint palettes/skinning; logical-time clip sampling/crossfades/masks/additive
  layers/root motion/eye tracks; deterministic secondary-motion springs. Usu static silhouette approval remains a
  separate hard gate.
- **S24:** opt-in felt/sheen/bounded fuzz shells and emitted tips; preserve existing shaders and measure tier costs.
- **S25:** the shared shadows of `Current_Plan.md` §6 (S3D-6). **S27 → S26:** prove world-view projection distinct from
  the photo-plane camera, then seeded sphere/crater/stars and logical travel. Bordered consumers use the shared framed
  camera input/persistence; unframed world travel may differ in projection, never duplicate framed-camera authority.

## 4. Deferred maintenance / product work

Keep these deferred unless new evidence or an explicit request promotes them:

- ImageWorker lean-spawn entry and residual memory-footprint follow-up;
- `--usage` observer-cost refinement and residual handle-slope attribution;
- migrate `main.py`'s `SRPSS_PROFILE_CPU` environment gate to an explicit profiling CLI/sidecar boundary; current CONFIG
  and RUN branches still read it directly, despite the project policy against environment-variable feature gates;
- remove `SounddeviceBackend`'s unreachable Windows WASAPI selection path after the factory's canonical PyAudioWPatch
  Windows routing; its non-Windows input-device policy also needs an explicit source-selection contract rather than
  silent first-device prioritization;
- Widgets-tab stale position estimates and overfull authored-display planning cost;
- Weather child-edit loading height and low-priority Settings FlowContainer polish;
- surface-preference SSOT cleanup and narrowing broad Qt-test slot-miss suppression;
- Spectrum extreme-viewport smoothness where physical evidence demonstrates a defect;
- installed GODZIP Foundry Windows-diff acceptance;
- wallpaper-feed consolidation only where shared normalization simplifies code without merging cache/scheduling authorities;
- direct live source reconfiguration outside Settings still discards its coordinator without generation retirement
  (`engine_handlers.on_sources_changed`). Audit that separate entry point before admitting external live source edits;
  the Settings resume path already uses the strict runtime/dialog destruction barriers.
- shared HTTP all-phase cancellation: `requests.get` can remain inside status/header parsing while a peer trickles
  bytes, despite per-socket timeouts. Body `read1` cancellation does not solve that phase. Prove it with a bounded local
  server before admitting a transport-level correction; retain strict runtime destruction barriers and refuse source
  cache-writer overlap. Do not add private socket cancellation, weaken retirement or claim a hard deadline from read timeouts;
- Steam asset-cache/catalog reconciliation if missing-image requests recur: the 2026-10-07 loaded RUN received HTTP 404 for
  asset hashes `4b349d51e996` and `3f5b734df3c5`. Resolve the source identities and verify failure backoff before changing asset admission;
- persistent shader/program cache only for a measured residual cold-compile hitch after gradual warm-up;
- bindless/sparse texture extension research only for a concrete consumer and without a permanent duplicate renderer path.
- optional long-tail test-oracle cleanup from the completed durability tranche: manually review remaining default-pin,
  source-string and exact-UI-copy advisory candidates only when touched or when they obscure a real contract. Preserve deliberate
  compatibility mappings, goldens, geometry/state oracles, architecture-negative bars and wording contracts; do not turn the
  advisory queues into a standing release blocker or a project-wide rewrite campaign.

### EB composition-lab clean. Clean up scratch and no longer needed files related to labs unless they explicitly help a future visualizer lab implementation.


### 2.5 SMP & Full Display 

Details can be found in "F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Future_Work\SRPSS_Expanded_Visualizer_and_SMP_Implementation_Plans_2026-11-05.zip". Decide on this or the Vulkan back end as the next series of large tasks after Waveform and Studios land cleanly.

### Remaining non-code organization

- [ ] Review dated `Docs/Audits` individually: durable rules into existing owners, significant forensic lessons
  into Historical Bugs, ordinary completed chronology into Git. Do not create another historical index/archive.
  Preserve operator source/reference assets and recovery backups; bulk scratch pruning is not a continuing
  deletion authority over new work.

## 5. Boundary

This is not a changelog or a completed-work register. When a deferred item lands, move its durable contract to the appropriate
current authority and remove it from this file. Retired/rejected work is routed through Historical Bugs and source control, not
kept here as a museum list.

### Shared widget glyph reveal / developer captures: R38 follow-up (not closed)

The physical action-handoff watch item lives in `Current_Plan.md` §5 (R38). The global Edit-only glyph handoff (existing session first, then existing command) remains required across all families; no new edit model or repaint/polling service. Diagnostic `\` capture is source/diagnostic only and requires native evidence of custom GL pixels before treating it as an accepted substitute for Snipping Tool. The UI presentation transition is not acceptance.

### Release catalogue/showcase work — explicit request only

Deferred by the operator on 28 October: animated catalogue reconciliation, visualizer showcases and catalogue
loop/metadata proof (formerly RM1–RM3), plus the Blinds Flat publication endpoint investigation (SC2). Do not maintain or regenerate these automatically after graphics changes.
Reopen only on an explicit request. Guided-setup stills are maintained per `Docs/Reference/Guided_Setup.md` (audited 2026-10-31).

### EB vectorised logical simulation (deferred by the operator, 2026-10-31)

The last measured lever on Extruded Bubble's frame age. Under the calibrated game-like load the logical tick is
~4.2 ms and holds the GIL ~38% of the time, which stalls the render and GUI threads. It is pure-Python per-bubble
motion, collision and wake work, and the bit-identical trims are exhausted
(`Docs/Audits/EB_Performance_Investigation_2026-10-29.md`). A NumPy structure-of-arrays rewrite is estimated at a
~2 ms tick and ~7-10 ms less frame age (22 → about 13-16 ms). It cannot be bit-identical: collisions are chaotic, so
it needs behavioural proof that reactivity, population, fusion and pop rates are unchanged on recorded music, plus
`tools/visualizer_live_check.py --load game60` evidence. The operator chose not to risk it now; reopen only on an
explicit request.

### Beyond the entire current backlog — optional EB Orthographic appearance parity

Explicitly deferred by the operator until **after everything currently listed in Current_Plan.md and this file**,
and only on a later explicit reopening. Orthographic projection itself passes geometry/depth/refraction checks;
EB's perspective-built water, lighting, near-field and composition need a separate visual target/parity effort.
Its Camera option stays visible but disabled. Preserve experimental authored values without rewriting presets.
Do not reopen this while wrapping EB, optimizing it, or building the queued modes. New 3D modes should be designed
for Orthographic by default with optional Perspective, using the shared camera primitives from the start.
