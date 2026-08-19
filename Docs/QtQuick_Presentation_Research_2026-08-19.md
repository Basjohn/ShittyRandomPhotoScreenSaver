# Qt Quick Physical Presentation Research — 2026-08-19

## Question

Can Qt Quick provide the missing architectural lever for SRPSS by moving physical frame rendering and
presentation away from the overloaded QWidget GUI paint/event-loop path?

## Conclusion

**Yes, it is credible enough to become the next active architecture spike.**

This is not a recommendation to rewrite the whole application in QML.

The candidate is specifically:

```text
one standalone QQuickWindow per physical display
+
threaded scene-graph render loop
+
custom full-display renderer on the render thread
```

The application shell, Settings UI, data providers, media control, and logical visualizer runtime can
remain Python/QWidget-based.

---

## Official Qt findings

### Qt Quick's scene graph is retained and can render on a dedicated thread

Qt's current scene-graph documentation says the scene graph is retained independently from item state
and, on many platforms, rendered on a dedicated render thread while the GUI thread prepares later
state.

The threaded render loop exists to increase multicore parallelism and make use of stall time such as
blocking swap/present work.

During the actual rendering portion, the GUI thread is released and can process events while the
render thread records/renders/presents.

This directly targets the boundary SRPSS's installed evidence keeps naming.

### Multiple QQuickWindows use multiple render threads

Qt's documentation explicitly discusses multiple synchronization points with multiple render threads
— one per window.

The GUI thread still participates in synchronization, so Qt Quick does not make GUI state irrelevant.

But physical rendering/present ownership is no longer ordinary QWidget paint execution on that same GUI
thread.

### No-vsync is supported

Qt Quick supports swap interval 0 / `QSG_NO_VSYNC`.

The threaded render loop recognizes unthrottled windows and changes animation-driving behavior rather
than simply assuming vsync.

Multiple visible QQuickWindows also already require timer-based GUI animation advancement.

Starting with Qt 6.5, `QSG_USE_SIMPLE_ANIMATION_DRIVER=1` provides elapsed-time animation advancement
that is independent of vsync, primary-screen refresh, and multi-window fallback infrastructure.

SRPSS should still keep its own logical time authoritative.

### QQuickWidget is the wrong architecture

Qt's own documentation says `QQuickWidget`:
- adds an extra offscreen render pass and texture-quad composition;
- disables the threaded render loop on all platforms.

It would therefore deliberately remove the property SRPSS needs to test.

### QQuickRhiItem exists and PySide exposes it

Qt 6.7+ provides `QQuickRhiItem` and `QQuickRhiItemRenderer`.

Qt describes it as the Qt Quick counterpart of QRhiWidget and says rendering normally happens on the
scene-graph render thread.

The item/renderer split has an explicit `synchronize()` step called on the render thread while the GUI
thread is blocked, after which render and GUI work can continue in parallel.

PySide's QtQuick type system exposes both classes, and its QtGui RHI bindings expose QRhi classes as
private bindings.

SRPSS currently pins PySide6 6.9.1, so the class generation is available.

However `QQuickRhiItem` targets an offscreen texture which is then composited. That is useful for
embedded custom items but not necessarily the cheapest full-screen compositor path.

### QSGRenderNode / direct scene-graph rendering is the high-performance route

Qt's official custom render-node example states:
- QSGRenderNode can inject rendering inline into the main scene-graph render pass;
- no extra render target or texture-composition pass is required;
- this can be excellent for performance but is the most complicated integration option.

Qt also supports custom graphics API calls from QQuickWindow render-stage signals such as
`beforeRendering`/`afterRendering`.

For the first SRPSS spike, direct native OpenGL on a QQuickWindow render thread is the shortest route
to test the scheduling architecture while preserving current shader code.

---

## Python/GIL caveat

Moving a Python renderer onto a Qt render thread does not remove Python's GIL.

When Qt invokes a Python override/callback, Python code still requires the GIL.

Therefore Qt Quick may:
- remove QWidget event-loop/paint ownership;
- move native render/present work to another thread;
- allow C++/driver work to overlap GUI event processing;

while still leaving contention between Python logical/render/UI callbacks.

This is why a representative vertical slice must be benchmarked before committing to a full migration.

If the Quick render loop is clearly better even with the current Python/OpenGL renderer, the
architecture is strongly validated.

If not, the next candidate is a small native/C++ renderer implementation rather than another QWidget
scheduler redesign.

---

## `15099d3` source audit

Historical commit:

```text
15099d389e5091942a0ce3d6e6311d33b6043d3d
```

There are no retained raw benchmark logs for this exact state.

Source shows:

```text
GLCompositorWidget(QOpenGLWidget)
SpotifyBarsGLOverlay(QOpenGLWidget)
```

The visualizer's frame request is essentially:

```python
self.update()
```

after accepted state handoff.

This is a much shorter presentation path than today's generation-fenced logical mailbox/compositor
coordination.

It also carries the old costs:
- second independently presented GL surface;
- extra context/FBO/composition ownership;
- more resource retention;
- worse cleanup/lifecycle complexity.

Later repository evidence established:
1. single-display transition stalls still existed even with the visualizer absent, so the old
   QOpenGLWidget compositor itself was not a clean foundation;
2. replacing the main compositor with QRhiWidget(OpenGL) eliminated the severe >50 ms no-visualizer
   class in the corresponding installed acceptance;
3. adding a second QRhi visualizer surface made severe gaps much worse even though the visualizer GPU
   shader became cheaper;
4. this promoted one accelerated presentation surface per display.

Therefore `15099d3` should be mined for directness, not restored.

---

## Recommended spike

Build a separate local architecture harness, not production migration.

### Windows

```text
QQuickWindow A -> 165 Hz target
QQuickWindow B -> 60 Hz target
```

### Renderer

Initially:
- OpenGL backend;
- current swap-interval-0 policy;
- prove `threaded` render loop through `qt.scenegraph.general`;
- custom render-thread callback;
- existing representative PyOpenGL transition/visualizer shader code;
- synthetic immutable input;
- no QML animations as logical authority;
- no QWidget embedding.

Representative content:
- retained base image;
- Blockspin;
- Bubble;
- Spectrum.

### Benchmark

Three repeats each:
- low external load;
- controlled heavy load.

Compare to worker+push.

### Success

Quick must show:
- deterministic startup;
- materially higher high-refresh presentation;
- lower p95/max frame gaps;
- better load resilience;
- acceptable 60 Hz visualizer delivery;
- no fidelity reduction.

Only after this result should runtime overlay migration begin.

---

## Likely final architecture if the spike wins

```text
QWidget application/configuration shell
        |
        +-- providers / media / settings / lifecycle models
        |
        +-- dedicated logical visualizer worker
                        |
                        v
                immutable latest state

QQuickWindow per display
        |
        +-- render-thread full-display compositor
        |      base image
        |      transition
        |      visualizer
        |
        +-- scene-graph runtime overlay presentation
```

Runtime overlays should migrate presentation without necessarily migrating their Python model logic.

Do not solve the window-model mismatch by stacking multiple animated transparent native windows over
each QQuickWindow.
