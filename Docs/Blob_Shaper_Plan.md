# Blob Shaper Plan

Living plan for Blob Shaper work. This version is aligned with the post-extraction visualizer architecture landed on `2026-03-27`.

If we later move the visualizer seams again, this doc should be updated with them instead of preserving stale implementation paths.

---

## 1. Goal

Blob Shaper should add a high-value Blob-specific creative system without:
- re-bloating `ui/tabs/widgets_tab_media.py`
- bypassing the shared `widgets.spotify_visualizer` normalization path
- introducing one-off preset/save/SST behavior
- pushing Blob-specific state back into unrelated visualizer modes

The right architectural target is:
- Blob-owned UI and load/save translation
- shared visualizer persistence/normalization
- Blob-owned runtime/shader behavior
- behavior tests first, source-inspection tests only where runtime surfaces are impractical

---
## 1.5 Blob Shaper Concept Clarification (Critical)

Blob Shaper is NOT a graph, curve editor, or spectrum visualizer.

Blob Shaper is a **spatial energy routing system**.

It defines:
- where energy is applied (position)
- what energy drives that location (bass, vocals, etc.)
- how strongly it affects the blob

This is implemented as:
- draggable energy source nodes
- placed in a square editor
- mapped internally to polar space

Non-negotiable rules:

- Do NOT replace this with:
  - radial graphs
  - sector systems
  - sliders representing frequency bands

- Do NOT defer complexity:
  - all energy types (bass, mid, vocals, treble, transient) must be supported immediately
  - node duplication (copy-on-drag) is required
  - both base and reaction systems must be implemented

If complexity arises:
→ solve it, do not simplify or skip it

--------
## 2. Architecture Fit

### 2.1 Current seams we must respect

Blob Shaper now has to fit into these existing ownership boundaries:

- UI construction:
  - `ui/tabs/media/blob_builder.py`
  - `ui/tabs/media/builder_scaffold.py`
- Blob load/save binding:
  - `ui/tabs/media/blob_settings_binding.py`
- Shared visualizer mode/preset/rainbow plumbing:
  - `core/settings/visualizer_mode_registry.py`
  - `core/settings/visualizer_preset_indices.py`
  - `ui/tabs/media/visualizer_mode_binding.py`
- Shared visualizer persistence/normalization:
  - `core/settings/visualizer_settings_contract.py`
  - `core/settings/visualizer_settings_snapshot.py`
  - `core/settings/defaults.py`
  - `core/settings/models.py`
- Widget/runtime config application:
  - `widgets/spotify_visualizer/config_applier.py`
- Overlay/runtime handoff:
  - `widgets/spotify_bars_gl_overlay.py`
  - `widgets/spotify_visualizer/renderers/blob.py`
  - `widgets/spotify_visualizer/shaders/blob.frag`

### 2.2 What must not happen

Do not implement Blob Shaper by:
- reintroducing direct Blob save/load logic in `ui/tabs/widgets_tab_media.py`
- making SST/preset/default flows each handle Blob Shaper keys separately
- hiding Blob-only migrations in random callers
- storing the feature through ad-hoc sidecar sections outside `widgets.spotify_visualizer`

### 2.3 Correct persistence rule

Blob Shaper keys should be ordinary Blob-owned visualizer keys under:

- `widgets.spotify_visualizer.blob_<key>`

They should round-trip through:
- `SpotifyVisualizerSettings.from_mapping()` / `.to_dict()`
- `normalize_visualizer_section_mapping()`
- `normalize_visualizer_mode_payload()`
- custom visualizer payload generation in `WidgetsTab.build_visualizer_preset_payload()`
- SST import/export/preview

Blob Shaper should also inherit the newer preset-selection contract automatically:
- mode/preset UI ownership comes from `core/settings/visualizer_mode_registry.py`
- missing preset slot fallback comes from `core/settings/visualizer_preset_indices.py`
- `WidgetsTab` custom preset payload/export paths now resolve preset indices through that shared contract instead of sparse-key guesses

That means Blob Shaper is a Blob mode feature, not a special persistence system.

---

## 3. Recommended Shape Of The Feature

### 3.1 Scope that fits the current codebase well

Blob Shaper should be split into four feature slices:

1. Base shape profile
   - radial profile that changes Blob resting silhouette
   - defines the Blob’s authored resting form
   - is always applied, independent of audio
   - remains the single source of truth for the Blob silhouette

2. Reaction limit profile
   - radial profile that caps or shapes deformation by angle
   - defines how strongly the Blob may react at different positions
   - modulates incoming signal energy spatially rather than replacing the existing Blob response system

3. Spatial energy routing
   - replaces the older “sector routing” idea with explicit node-based routing
   - directional weighting is determined by authored draggable energy nodes rather than fixed sectors or graph curves
   - controls which energy content dominates which Blob region
   - must support multiple placements of the same energy source so that more than one area can respond to Bass, Vocals, Mid, Treble, or Transient / Beat

4. Optional ring topology
   - hollow-center Blob mode using the same shaping/routing system
   - modifies how the base shape is rendered, not how it is authored
   - the same base shape data must work for both Circle and Ring modes

This is still one coherent Blob feature because all four slices terminate in the same Blob shader/runtime path.

Additional conceptual rule:

Blob Shaper is NOT a graph editor, curve editor, or spectrum graph.

Blob Shaper is a visual spatial routing system:
- where energy is applied
- what energy drives that location
- how strongly it affects the Blob

It must be treated as an authored spatial system, not a collection of procedural fallback knobs.

Non-negotiable routing rule:

Energy sources must exist as draggable source items, not implicit hidden bands.

Those sources should include immediately, not as deferred future work:
- Bass
- Mid
- Vocals
- Treble
- Transient / Beat, if derivable from the existing shared signal pipeline

Dragging an energy source must create a COPY, not consume or move the original item.

That means:
- the source palette always retains the original energy labels
- the user can place multiple Bass nodes
- the user can place multiple Vocals nodes
- multiple areas of the Blob may intentionally respond to the same energy class

This copy-on-drag behavior is required because Blob is radial and continuous, and a one-instance-only routing model would be artificially restrictive.

Base shape and topology relationship:

The Base Shape profile defines the Blob silhouette.

Topology modifies how that same silhouette is rendered:

- Circle mode
  - filled Blob
  - ordinary outer silhouette behavior

- Ring mode
  - hollow Blob
  - inner radius controlled by ring thickness
  - same shaping logic applies to both inner and outer edges

Topology must not become a second independent shape system.


### 3.2 Best implementation model

Use authored profile data, not procedural one-off knobs.

More specifically:
- keep the authored base shape concept
- keep the authored reaction shape concept
- replace old fixed “sector” thinking with authored spatial routing nodes
- do not collapse routing into generic sliders, simple left/right weighting, or curve-only controls

Recommended persisted model:
- `blob_shaper_enabled`
- `blob_shape_base_nodes`
- `blob_shape_reaction_nodes`
- `blob_shape_energy_nodes`
- `blob_shaper_base_strength`
- `blob_shaper_react_strength`
- `blob_topology`
- `blob_ring_thickness`

Keep these Blob-owned and mode-specific from the start.

Recommended node semantics:

`blob_shape_base_nodes`
- authored shape control points / samples for the resting silhouette

`blob_shape_reaction_nodes`
- authored shape control points / samples for deformation limits / deformation shaping

`blob_shape_energy_nodes`
- authored placed energy-routing nodes
- each node should carry at minimum:
  - energy_type
  - position_x
  - position_y
  - strength

Optional future-safe field if needed, but not required for first pass:
- falloff / influence radius

Important data-model correction:

The previous `blob_shape_sectors` wording invites agents to regress the feature into fixed angular partitions.
That is not the intended model anymore.

Routing should instead be persisted as explicit authored node placement.

Important topology correction:

Use:
- `blob_topology` with values like `"circle"` / `"ring"`

instead of:
- `blob_ring_mode`

because a topology enum is less ambiguous and keeps the concept tied to shape interpretation rather than a loose boolean mode toggle.

Strength model:

Blob Shaper should preserve both:
- global strength controls
  - `blob_shaper_base_strength`
  - `blob_shaper_react_strength`

and
- per-node strength for placed energy sources

This allows:
- overall shape intensity control
- local per-energy emphasis within the routing field

Anti-simplification rule for the implementation model:

Do NOT simplify this into:
- one generic “audio energy” source
- one node per energy type
- fixed sectors
- sliders standing in for placement
- deferred support for treble / transient / beat because they are “complex”

If complexity is encountered, solve it rather than reducing scope.


### 3.3 UI rule

Blob Shaper belongs in Blob’s mode-owned UI, not in shared technical controls.

That means:
- editor widget and controls live under `blob_builder.py`
- repeated preset/advanced/technical chrome should keep flowing through `builder_scaffold.py`
- save/load lives under `blob_settings_binding.py`
- technical controls remain for genuinely shared visualizer concerns

The Blob Shaper UI must include, within Blob-owned UI:
- the shape editor surface
- energy source palette
- node selection/editing controls
- topology selector
- ring thickness control when topology is Ring

The editor must behave like an authored visual spatial tool, not a graph.

That means:
- do not present it as a line chart
- do not present it as a spectrum graph
- do not expose raw polar math directly to the user
- do not regress it into a pure sector editor

Recommended editor behavior:

- use square editor surfaces for the authored shapers
- Base Shape and Reaction Shape should each have their own square shaper when enabled
- if screen space becomes an issue they may be tabbed/toggled, but they remain conceptually separate editors
- the energy source palette should sit nearby in a dedicated box or source area
- dragging from the palette creates copies of source items into the editor
- users must be able to place multiple nodes of the same type
- users must be able to select, adjust, and remove placed nodes
- each placed node should expose at least strength editing
- topology control should expose Circle / Ring
- ring thickness control should only appear when Ring is selected

Control gating rule:

When Blob Shaper is enabled, hide, disable, or de-emphasize Blob controls that become redundant or conflicting.

Likely candidates:
- `blob_reactive_deformation`
- `blob_stretch_tendency`
- `blob_stretch_inner`
- `blob_stretch_outer`

Keep orthogonal controls live:
- colors
- glow
- ghosting
- stage controls
- pulse strength
- width / size
- wobble character unless it proves semantically redundant in practice

Final UI rule:

The UI must not quietly skip the hard parts.
Specifically, it must not:
- reduce the routing system to a placeholder
- omit copy-on-drag duplication
- defer non-bass energy sources
- replace authored routing with a simplified graph because it is easier to build

## 4. File Ownership Plan


- Key Note: Avoiding making existing monoliths or mini-monoliths larger where possible!

### 4.1 UI layer

Primary owners:
- `ui/tabs/media/blob_builder.py`
- `ui/tabs/media/blob_settings_binding.py`

Recommended new UI file:
- `ui/tabs/media/blob_shape_editor.py`

Why:
- builder stays responsible for Blob-specific UI composition
- binding handles Qt <-> config translation
- editor widget encapsulates node-based interaction system

Blob Shape Editor responsibilities:
- render square editor space
- manage node placement and selection
- handle drag-and-drop from energy palette
- support copy-on-drag behavior
- expose node editing (strength, delete)

Builder responsibilities:
- layout integration
- control grouping
- enable/disable gating


### 4.2 Persistence layer

Primary owners:
- `core/settings/defaults.py`
- `core/settings/models.py`
- `core/settings/visualizer_settings_snapshot.py`
- `core/settings/default_settings.py`
- `core/settings/defaults_snapshot.json`

Rule:
- Blob Shaper keys must be added once to canonical schema
- no sidecar persistence systems
- no Blob-only storage paths

All data must flow through:
- `SpotifyVisualizerSettings`
- normalization functions
- preset payload system
- SST import/export


### 4.3 Runtime layer

Primary owners:
- `widgets/spotify_visualizer/config_applier.py`
- `widgets/spotify_bars_gl_overlay.py`
- `widgets/spotify_visualizer/renderers/blob.py`
- `widgets/spotify_visualizer/shaders/blob.frag`

Responsibilities:

- config_applier:
  - map Blob Shaper settings to runtime attributes

- overlay:
  - hold node data and topology state

- renderer:
  - convert node data into uniform arrays

- shader:
  - apply shaping and routing per fragment

Rule:
- Blob Shaper must consume the existing shared signal pipeline
- no Blob-specific signal duplication
- no alternate energy sourcing system

Node evaluation must happen in shader/runtime, not UI or binding layers
---

## 5. Data Flow We Should Preserve

The intended end-to-end flow is:

1. Blob UI edits values in:
   - `blob_builder.py`
   - `blob_shape_editor.py`

2. `blob_settings_binding.py` serializes them into:
   - `widgets.spotify_visualizer.blob_*` keys

3. Shared normalization:
   - `SpotifyVisualizerSettings.from_mapping()`
   - `normalize_visualizer_section_mapping()`
   - `normalize_visualizer_mode_payload()`

4. Config application:
   - `config_applier.py` maps settings to runtime attributes

5. Overlay handoff:
   - `spotify_bars_gl_overlay.py` stores runtime state

6. Renderer:
   - uploads node arrays + topology + strengths

7. Shader:
   - evaluates base shape
   - applies reaction shaping
   - applies node-based energy routing


### Signal-source rule (non-negotiable)

Blob Shaper must:
- use the shared visualizer signal pipeline
- not introduce Blob-specific signal extraction
- not bypass normalization

All energy types (bass, mid, vocals, treble, transient) must:
- come from the shared signal contract
- be routed spatially via nodes only


### Stage interaction rule

Blob stage system remains unchanged:

- stage 1:
  - responds to general support
  - must not stall visually

- stage 2/3:
  - must remain reachable
  - must respond to vocals as well as bass

Blob Shaper must:
- shape within this system
- not introduce a competing stage system


### Anti-simplification rule

Any implementation that:

- replaces node routing with sliders
- removes copy-on-drag duplication
- collapses energy types into one signal
- reintroduces sector routing
- defers energy types as “future”

is incorrect and must be rejected.


### Preset / payload rule

Blob Shaper must remain fully compatible with:

- preset system
- SST import/export
- normalization pipeline

Must NOT introduce:
- custom preset formats
- Blob-only payload exceptions
- legacy keys or compatibility hacks

All data must live under:
- `widgets.spotify_visualizer`
---

## 6. UI Design Guidance

### 6.1 Keep the editor mode-owned and deliberate

A dedicated Blob editor still makes sense, but it must be treated as an authored spatial tool, not a graph, chart, or spectrum display.

Blob Shaper is NOT:
- a radial graph
- a curve editor
- a polar chart
- a sector wheel
- a spectrum-like plotting surface

Blob Shaper IS:
- a square authored editor surface
- used to define spatial behavior for a Blob that is rendered in polar/radial space
- a placement tool for shape and energy-routing data

That means the UI should present:
- deliberate authored editing
- explicit node placement
- clear shape-vs-reaction separation
- visible energy source routing

Do not dump every concept into the first pass, but do not simplify away core interaction rules either.

Non-negotiable interaction rule:
- dragging from the energy source palette must create a COPY, not move the original
- users must be able to place multiple instances of the same energy type
- Bass, Mid, Vocals, Treble, and Transient / Beat must all be treated as current supported sources if the shared signal path can provide them
- do not defer complex routing behavior merely because it is harder to implement

If complexity arises:
- solve it in the editor/runtime design
- do not fall back to a graph or sector simplification


### 6.2 Control grouping

Recommended first-pass grouping:

- `Blob Shaper` checkbox
- `Shape Strength`
- `Reaction Strength`
- `Topology` (`Circle` / `Ring`)
- `Ring Thickness` when ring is enabled

Primary editor area:
- `Base Shape`
- `Reaction Shape`

Supporting routing area:
- `Energy Sources`
- placed-node editing controls

This is important:

The first-pass grouping should not imply that Blob Shaper is one single graph with mode tabs.
It should communicate that there are two authored shapers plus a routing system.

Recommended grouping more explicitly:

#### Blob Shaper enable/group
- `Blob Shaper` checkbox
- `Shape Strength`
- `Reaction Strength`

#### Topology group
- `Topology` (`Circle` / `Ring`)
- `Ring Thickness` when topology is Ring

#### Base Shape editor group
- square Base Shape editor
- authored resting silhouette controls/data editing

#### Reaction Shape editor group
- square Reaction Shape editor
- authored deformation-limit / reaction-shaping controls/data editing

#### Energy Routing group
- boxed draggable source palette
- source items:
  - Bass
  - Mid
  - Vocals
  - Treble
  - Transient / Beat
- placed node inspection/edit controls
- node delete/remove control
- per-node strength editing

If space constraints require a more compact presentation:
- Base Shape and Reaction Shape may be shown in tabs or a mode toggle
- but they must remain conceptually separate editors
- do not merge them into one overloaded graph-like surface

The palette should sit near the editor, ideally in a nearby boxed source area, so the drag-copy interaction is visually obvious.


### 6.3 Gating rule

When Blob Shaper is enabled, disable or de-emphasize only the Blob controls it truly replaces.

Likely candidates:
- `blob_reactive_deformation`
- `blob_stretch_tendency`
- `blob_stretch_inner`
- `blob_stretch_outer`

Keep orthogonal controls live:
- colors
- glow
- ghosting
- stage controls
- pulse strength
- width/size
- wobble character unless it becomes semantically redundant in practice

Additional gating clarification:

When Blob Shaper is enabled:
- hide or disable controls that would directly fight authored shape placement
- do not hide controls merely because they are visually nearby
- do not hide shared controls that remain orthogonal to Blob Shaper behavior

Blob Shaper-specific UI must also avoid redundant/conflicting subcontrols inside the shaper area itself.

That means:
- if a normal Blob slider becomes redundant once authored shape/routing is active, remove or suppress it in the Blob Shaper path
- do not present users with two different controls that both claim to own the same deformation behavior

Critical anti-regression rule:

When Blob Shaper is enabled, the UI must not regress into:
- a generic graph editor
- a fallback sector editor
- a simplified one-node-per-band system
- a placeholder that only supports Bass while pretending other energy sources are “future”

The enabled state should expose the real authored system, not a reduced temporary substitute.
---

## 7. Shader / Runtime Design Guidance

### 7.1 Uniform strategy

Uniform arrays are still a good fit here.

Recommended shape:

- base profile samples
- reaction profile samples

- energy node array:
  - energy_type
  - position (polar or pre-mapped)
  - strength

- strengths/toggles
- topology controls (circle/ring + thickness)

This avoids:
- reintroducing sectors
- encoding routing as fixed angular partitions

The shader must consume explicit node data, not inferred band weights.


### 7.2 Blob runtime rule

Blob Shaper must modulate the existing Blob system, not replace it.

That means:
- stage progression still matters
- pulse still matters
- wobble still matters
- ghost should inherit the shaped silhouette naturally

Blob Shaper specifically controls:
- spatial distribution of energy influence
- deformation limits per region
- base silhouette shaping

It must NOT:
- introduce a second signal system
- bypass shared signal normalization
- collapse multiple energy sources into a single value


### 7.3 Energy routing model (Critical)

Energy must be routed spatially using authored nodes.

Each node:
- samples from a specific energy source (bass, vocals, mid, treble, transient)
- contributes influence based on position
- combines additively with other nodes

Important rules:

- multiple nodes of the same type must stack correctly
- no limit to one node per energy type
- routing must not fallback to sector partitioning
- routing must not be approximated using a simple angular gradient

The shader should evaluate:
- energy contribution per node
- blended spatial influence
- final deformation weighting


### 7.4 Ring mode

Ring mode remains:

- Blob-only
- shader-owned
- controlled by standard Blob settings

Additional rule:

Ring mode must:
- reuse the same base shape and routing data
- apply shape to both inner and outer edges
- not introduce a second independent shape system

---

## 8. Presets / Defaults / SST Rules

### 8.1 Defaults

Canonical defaults are reached through:
- `core/settings/defaults.py`

Authoritative authored visualizer/default payloads still live in:
- `core/settings/default_settings.py`

Derived/default artifacts may also need updating:
- `core/settings/defaults_snapshot.py`
- `core/settings/defaults_snapshot.json`

Rule:
- treat `core/settings/defaults.py` as the canonical entrypoint other code should read from
- update the underlying authored/default schema once, then keep the mirrored artifacts in parity

### 8.2 Presets

Blob Shaper preset behavior should come from existing visualizer preset paths:
- curated visualizer mode presets
- `normalize_visualizer_mode_payload()`
- `tools/visualizer_preset_repair.py`
- `WidgetsTab.build_visualizer_preset_payload()`

That means:
- no separate Blob Shaper preset format
- no manual side-path for custom save
- no special SST exceptions

### 8.3 SST

Blob Shaper must be treated as ordinary `widgets.spotify_visualizer` data.

If it persists cleanly through:
- reset/defaults
- model load/save
- preset payload generation
- SST import/export/preview

then the architecture is correct.

---

## 9. Testing Strategy

### 9.1 First fences

Before adding a brand new dedicated suite, extend the current visualizer fences:

- `tests/test_visualizer_settings_plumbing.py`
  - binding roundtrip
  - config applier handoff
  - overlay/runtime kwargs
  - normalization/preset repair interactions
- `tests/test_visualizer_presets.py`
  - curated payload filtering
  - SST roundtrip
  - preset payload normalization
- `tests/test_widgets_tab.py`
  - Blob UI roundtrip where practical

### 9.2 When to add a new suite

Add `tests/test_blob_shaper.py` only when there is enough Blob-Shaper-specific behavior to justify it, such as:
- profile interpolation correctness
- sector routing semantics
- ring-mode behavior
- shape gating interactions

### 9.2.1

- node duplication behavior (copy-on-drag)
- multiple nodes of the same energy type influencing different regions
- correct routing of multiple energy types simultaneously

### 9.3 What to avoid

Do not rely mainly on source-text tests for this feature.

A few static contract checks are fine for:
- shader uniform registration
- required file ownership wiring

But the main fence should stay behavior-first.

---

## 10. Recommended Implementation Order

### Phase 1: Persistence contract

1. Add Blob Shaper keys to canonical defaults/model/schema
2. Route them through `blob_settings_binding.py`
3. Prove reset/defaults/SST/preset payload roundtrip

Why first:
- it keeps the feature inside the shared settings architecture from day one

### Phase 2: Runtime plumbing

1. Add widget attributes
2. add config-applier handoff
3. add overlay storage
4. add renderer uniform upload
5. compile Blob shader with no visual change when disabled

Why second:
- it gives us a stable no-op runtime path before the editor exists

### Phase 3: Shader behavior

1. Add base profile support
2. add reaction-limit support
3. add sector routing
4. add ring topology

Why third:
- it lets us validate each visual slice independently

### Phase 4: Editor UI

1. build `blob_shape_editor.py`
2. integrate into `blob_builder.py`
3. wire enable/disable and control gating

Why fourth:
- editor work is safer once persistence/runtime are already real

### Phase 5: Curation and tuning

1. add or update curated Blob presets
2. run preset repair/audit
3. tune defaults and authored examples

### Phase 6: Cleanup

1. remove any redundant tests created during migration
2. update docs:
  - `Current_Plan.md`
  - `Index.md`
  - `Spec.md`
  - `Docs/Defaults_Guide.md`
  - `Docs/TestSuite.md`

---

## 11. Architecture Risks To Watch

### 11.1 Builder growth

`blob_builder.py` can still bloat if the editor UI, gating logic, and helper rows all pile in at once.

Mitigation:
- use `blob_shape_editor.py`
- keep builder focused on layout/composition
- extract any nontrivial editor serialization helpers if needed

### 11.2 Binding sprawl

`blob_settings_binding.py` should remain the Blob Qt translation seam, not become a mini runtime engine.

Mitigation:
- keep it to type coercion, widget hydration, and payload collection

### 11.3 Preset/schema drift

Blob Shaper adds enough keys that drift is a real risk.

Mitigation:
- add defaults/model/snapshot updates together
- add preset/SST tests in the same change
- use the existing normalization seam instead of side logic

### 11.4 Runtime overreach

It would be easy to fold too much DSP logic into Blob Shaper.

Mitigation:
- keep signal extraction shared
- keep Blob Shaper focused on how Blob consumes those signals spatially

---

## 12. Success Criteria

- [ ] Blob Shaper remains a Blob-owned feature in UI, settings, and runtime
- [ ] `widgets_tab_media.py` does not regain Blob-specific translation blocks
- [ ] Blob Shaper keys round-trip through defaults, reset, SST, presets, and custom save
- [ ] Blob behaves unchanged when Blob Shaper is disabled
- [ ] default Blob Shaper payload produces no visible regression when enabled with neutral data
- [ ] ring mode works without creating a separate visualizer mode
- [ ] ghost/glow continue to work with shaped Blob output
- [ ] curated Blob presets can author Blob Shaper intentionally without schema drift
- [ ] tests cover behavior, not just file contents

---

## 13. Open Questions For The Future

These are not blockers now, but future Blob updates may require this doc to expand:

- whether sector routing should be discrete or smoothly blended at authored boundaries
- whether the editor should support templates/import/export independently of presets
- whether ring mode should eventually gain inner-edge-specific glow or color controls
- whether Blob Shaper warrants its own math/helper module once the shader/runtime path stabilizes
- whether any of the Blob controls replaced by Blob Shaper should be retired entirely instead of merely gated

For now, the right move is to keep Blob Shaper additive, mode-owned, and fully compatible with the shared visualizer persistence architecture already in the repo.
