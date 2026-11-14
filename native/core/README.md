# The native core: `_srpss_native_core`

The product's native module (`Current_Plan.md` item 8b, N2; decision D5.7 in
`Docs/Future_Work/Native_Core_P3_Decisions.md`). `native/spike_p1/` beside it stays the harness and evidence and
never ships.

- `CMakeLists.txt`, `build.cmd`: the build. Compiled only by `.github/workflows/native-module.yml` on GitHub (its
  default source); never on this machine. `build.cmd` is the workflow's one CMake invocation.
- `src/`: the C++ module. `abi.h` holds the ABI that `rendering/native/loader.py` speaks (`EXPECTED_ABI`).
  - `host_adapter.*`: the host adapter (D5.1): the Qt Quick window host and the hidden host (a render control on the
    core's own render thread) behind one interface.
  - `frame_driver.*`: the frame driver (D5.2), connected in C++ to each window's `beforeRendering` with a direct
    connection; it records the core's work for the frame there and releases on the render thread.
  - `conventions.*`: N0.3's decided conventions (F1 to F3): the upload correction of a core-owned target, the matrix
    corrected exactly once, the front-face rule on the corrected matrix, the target's conventions block.
  - `targets.*`: the core's render targets and Qt 6.12.0's rules for them (preserving, primed on Vulkan).
  - `probe_pass.*`: the trivial core pass a harness switches on (the frame edge, the correction and the readback
    orientation end to end); nothing creates it otherwise.
  - `composite.*` (N2.4, D5.2): what the core draws reaches the window as a scene-graph texture node with a material of
    ours: texels one to one (texelFetch at the item's integer device pixel), the card's coverage (the clip path Python
    resolves, tested at each texel's centre; skipped only for an admitted overflow), the quarter turn, Qt's opacity.
    Its geometry comes from `rendering/native/composite.py`.
  - `surfaces.*`: the composite's target (owned by its node, on the render thread) and the per-window registry the
    frame driver records from; a surface records only when its content changed (nothing at rest).
  - `gpu_timer.*` (N2.6, D8 plus 2): the per-pass GPU timer in the frame driver: each pass bracketed whole, outside
    any render pass, through `beginExternal` (raw timestamps on Vulkan, `GL_TIME_ELAPSED` on OpenGL), QRhi's
    whole-frame figure where the host's QRhi has timestamps (the only figure on D3D11 and D3D12); results read latched,
    never waited for. Off, the driver holds no timer and no query object. `rendering/native/gpu_timing.py` writes the
    figures into the frame trace.
  - `load_pass.*`: the timer's known-cost pass (N full-target draws of a fixed fragment loop), a harness's only.
  - `packet_reader.*` (N2.3, D1 and D2): the core's one consuming reader of a Visualizer frame stream, on its own view
    of the named mapping (retire never waits; the last pin unmaps), the accept-edge acknowledgement, the non-consuming
    head read, the drop edge's watermark, the transport rule's refusal at the slot head. `frame_abi_generated.h` is its
    layout, mode codes and record tables, generated from `core/visualizer_engine/packet_abi.py` and `native_schema.py`
    by `tools/native_frame_abi_header.py` (never edited by hand). Its first consumer is N2.5's Spectrum, at the item's
    sync on the render thread; `pause_in_copy` is D1's "close during copy" hook (a harness's only).
  - `program_blocks.*` (N2.5 round 4, **the standing port rule for every mode**): a runtime shader's uniform block,
    reflected by name (`BlockLayout::reflect`) and packed generically (`BlockValues`): `set(name, numbers)` from any
    name -> value source (a Python settings dict through `setJson` now; a record's named fields later, N2.9), at the
    member's reflected offset, type and array stride (std140: a scalar array's stride is 16 when the reflection says 0),
    ints as int32, floats as float32 rounded to nearest. An unknown name or a wrong size is refused with a reason;
    `unfilled()` names every member nobody set (a harness error). A port therefore writes:
    1. its fragment shader once, in `widgets/spotify_visualizer/shaders/` (the Python renderer and the core draw the same
       file), baked by `tools/regen_qrc.py --shaders` into `<file>.qsb` beside it (the conventions splice included; the
       same staleness check as the Qt Quick packs) and handed to the core as bytes at run time
       (`rendering/native/program_values.py` `mode_fragment_pack`): **no module build for a shader change**;
    2. one Python function giving every Settings- and card-derived member by name, from the spec and the card, with the
       Python renderer's own arithmetic (Spectrum: `spectrum_settings_values`), sent when it changes (nothing per frame at
       rest);
    3. C++ only for the per-frame or simulation arithmetic, setting its members by name through the same `BlockValues`
       (Spectrum: `kSpectrumFrameMembers`).
    A new Settings-only uniform is a shader line, a spec entry, a line in step 2 and a bake: no C++, no build round.
  - `spectrum.*` (N2.5): Spectrum on a composite's surface, the first port under that rule. Its program
    (`SpectrumProgram`) is the product's `spectrum.frag` pack handed over at run time (`composite_spectrum_program`; the
    module's compiled-in copy remains only as the harness's negative control) and its Settings-derived members by name
    (`composite_spectrum_settings`); the C++ fills the per-frame members from the record (bars, peaks, the bar layout that
    follows the bar count, the clock's hues, the play state), ported line for line from the Python renderer
    (`spectrum_block`, GPU-free, for the byte-for-byte test). The stream is bound by its mapping name from the GUI thread,
    read at the item's sync on the render thread, and a retired stream is released there (the render-thread retire job,
    also at the node's deletion). Python face: `rendering/native/spectrum.py`; the product route:
    `rendering/quick/visualizer/native_route.py`.
  - `vulkan_context.*`: D6, the process's Vulkan instance and one device per window, given to Qt Quick.
  - `thread_probe.*`, `process_counters.*`: the D5.4 probe and the lifecycle counters.
  - No STL container, lock or function wrapper: their code is in `msvcp140.dll`, which the module never imports (the
    loader's runtime rule); Qt's types instead.
- `shaders/`: GLSL 440 sources (`.vert`, `.frag`, `.comp`), each baked by PySide6's `qsb` for every shipped backend
  and embedded in the module; the workflow's staging requires one `.qsb` per source. `srpss_conventions.glsl` is the
  production conventions include (`rendering/gl_programs/conventions.py`), spliced in at `//@srpss_conventions` by
  `cmake/compose_shader.cmake` before the bake.
- `python/import_check.py`: the GPU-free check the workflow runs after the compile, through `rendering.native`.
- `python/host_check.py`: N2.2's proof (hosts, frame driver, probe, lifecycle, validation; `probe_analysis.py`,
  `vk_validation.py`). `Docs/Reference/Harness_Index.md` has the command.
- `python/composite_check.py`: N2.4's proof (texels one to one, plan 1C.4's clip contract on the native item in every
  display style, overflow held to the display rect, the window round, validation; `composite_analysis.py` and
  `tools/card_clip_contract.py`, the contract's one reading).
- `python/packet_reader_check.py`: N2.3's proof (bit-for-bit parity with the reference decoder on the shipped clip,
  the adversarial table with each case's negative controls, the in-place race, D1 and D2; GPU-free).
- `python/spectrum_check.py`: N2.5's proof of the native Spectrum item (uniform parity with the Python renderer at the
  widened run set, the item's contract with D1's close during copy, pixels against the Python renderer on OpenGL and
  against native OpenGL on Vulkan).
- `python/timer_check.py`: N2.6's proof (off is free by count, a known-cost pass scaled N times and its empty-bracket
  control, QRhi's frame figure, latched reads in a real window with the waiting read as control, the frame trace and
  its report, the two forms against each other, validation; `timer_analysis.py`).

The guards: CMake refuses a Qt SDK other than `requirements.txt`'s PySide6 pin; the module refuses to import under
any Qt but the one it was compiled for; `rendering.native` refuses a module whose Qt, ABI or MSVC runtime arrangement
does not match this process (`rendering/native/runtime_check.py`: no `msvcp140` import, the loaded `vcruntime140` at
least as new as the compiler), the MSVC runtime rule read from the module file before it is imported. Tests:
`tests/test_native_core_*.py`.

Build and fetch it (the lead; agents never build):

```
.venv\Scripts\python.exe tools\build_runner.py --mode github --run --select native_module
```

The module lands in `release\native_module\` of the checkout the command runs from; `rendering.native.load(Path(
"release/native_module"))` loads it from there. `Docs/Guides/GitHub_Remote_Build.md`, "The native modules", has the
rest.
