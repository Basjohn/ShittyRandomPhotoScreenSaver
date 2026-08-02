# 04 — Target Architecture and Ownership

## Core rule

Every mutable concern has one owner.

Sharing data is allowed. Sharing authority is not.

## Runtime domains

### 1. Application/runtime coordinator

Owns:

- creation and destruction order;
- Settings/Edit transition;
- display topology changes;
- high-level start/stop state.

Does not own:

- GL objects;
- animation cadence;
- visualizer equations;
- cache eviction details.

### 2. Image pipeline

Owns:

- source selection;
- decode request;
- crop/scale transform;
- bounded CPU image cache;
- prefetch policy;
- immutable upload-ready image description.

Does not own:

- GL texture handles;
- compositor state;
- transition time;
- QWidget/QPixmap creation on workers.

### 3. GPU resource store

Owns:

- texture/FBO/PBO metadata;
- exact byte accounting;
- leases/references;
- context/share-group generation;
- eviction eligibility;
- deletion scheduling to the GL owner.

Does not own:

- image sequencing;
- transition logic;
- visualizer simulation;
- application lifecycle.

### 4. Visualizer model/controller

Owns:

- audio input normalization;
- simulation state;
- mode-specific behavior;
- logical cadence;
- immutable latest render state;
- visibility and mode selection.

Does not own:

- compositor paint scheduling;
- GL context lifecycle;
- image transitions;
- Settings reconstruction.

### 5. Transition controller

Owns:

- source resource reference;
- destination resource reference;
- start time;
- duration;
- easing;
- local completion.

Does not own:

- worker threads;
- image decode;
- visualizer;
- paint acknowledgement.

### 6. Display compositor

Owns:

- one surface per display;
- GL context/surface usage on the GUI thread;
- shader programs used for scene composition;
- current immutable scene snapshot;
- draw order;
- request for another frame while local animation remains active.

Does not own:

- producer cadence;
- worker scheduling;
- Settings/Edit application lifecycle;
- image source selection;
- visualizer simulation;
- transition terminal transactions outside itself.

### 7. Diagnostics

Owns:

- sampled metrics;
- ring buffers;
- histograms;
- resource snapshots;
- phase benchmark output.

Does not become part of control flow.

Diagnostics must observe the architecture, not drive it.

## Data flow

```text
Audio source
    -> Visualizer controller/model
    -> immutable VisualizerState (latest only)
                              \
Image source -> decode/transform -> UploadDescriptor
                              -> GPU resource store -> TextureLease
                                                    \
Transition controller -------------------------------> SceneSnapshot
VisualizerState ------------------------------------> SceneSnapshot
Overlay state --------------------------------------> SceneSnapshot
                                                     |
                                                     v
                                             Display compositor
                                                     |
                                                     v
                                                   paint
```

No arrow returns from `paint` to a producer for ordinary animation.

## Scene snapshot

A scene snapshot should contain explicit, immutable references such as:

```text
SceneSnapshot
- context_generation
- base_texture_lease
- optional transition snapshot
- optional visualizer state
- overlay state
- viewport/display geometry
- scene_generation
```

The compositor may atomically replace the latest snapshot. It must not mutate producer-owned objects.

## Clock ownership

Use separate logical clocks:

- visualizer simulation clock;
- transition time based on monotonic time;
- Qt presentation opportunity.

These clocks interact only through snapshots.

A presentation stall does not rewind or block simulation. The next paint draws the current state. Critical state transitions are deterministic and local.

## Thread ownership

### GUI thread

Only owner of:

- QWidget/QOpenGLWidget lifecycle;
- `QOpenGLContext` currentness;
- texture/FBO/PBO/shader creation and deletion;
- `QPixmap`;
- scene presentation;
- compositor mutation.

### Worker threads

May perform:

- file I/O;
- image decode to safe non-GUI data types;
- expensive scaling if thread-safe;
- coarse CPU analysis;
- vectorizable visualizer computation if designed for deterministic handoff.

May not perform:

- QWidget access;
- QPixmap creation;
- GL calls;
- context currentness;
- direct compositor mutation.

### Cross-thread handoff

Use:

- immutable data;
- bounded queues or atomic/latest reference;
- generation checks;
- cancellation tokens.

Do not use:

- worker waits for GUI paint;
- mutable shared widget objects;
- callbacks into destroyed generations.

## Generation policy

Generations are allowed only where they represent a real lifetime boundary:

- runtime generation after full recreation;
- GL context generation;
- source request generation where stale worker results must be rejected.

Do not create separate dirty/requested/acknowledged/presented generations for every animation frame.

A generation should answer: “Does this object belong to the current lifetime?” It should not replace clear control flow.

## Target simplicity test

A new engineer should be able to answer these questions from one document and one diagnostic dump:

1. Who owns this texture?
2. Which context may delete it?
3. Why is the compositor painting?
4. Who advances the visualizer?
5. What happens if Qt misses ten paints?
6. What happens when Settings opens?
7. Why is this image still in RAM?
8. What prevents a stale worker result from being applied?

If the answer requires tracing five objects and three generations, the design has regressed.
