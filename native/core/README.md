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
    ints as int32 (uints and bools as uint32), floats as float32 rounded to nearest. An unknown name, a wrong size, a
    value without a defined conversion (not finite, beyond its int type) or a write past the block is refused with a
    reason and writes nothing; `unfilled()` names every member nobody set, and always a member it cannot pack (mat2,
    mat3, a struct, a multi-dimensional array: audit 14 Nov, L2). `packRecordField` packs a frame record's field into
    the member of the same name (N2.9). A port therefore writes:
    (A new mode skips the port entirely: "How a new mode is built" below.)
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
    `rendering/quick/visualizer/native_route.py`. Its settings are packed once when they change and kept across a new
    program (refused when they do not fit it).
  - `mode_schema.*` (N2.9): a mode's frame schema handed over at run time (`RuntimeSchema`): the Python table in the
    compiled table's row shape (`rendering/native/mode.py` `schema_table_entry`), validated (a native id, aligned and
    non-overlapping fields inside the record, range rules on u32 scalars only), its fingerprint recomputed, never
    replacing a compiled schema. The packet reader admits it beside `frame_abi_generated.h`'s table, which keeps only
    the schemas a hand-written consumer reads.
  - `mode_content.*` (N2.9): **generic mode content**, a mode drawn from data alone. `ModeProgram`: one to eight
    full-target passes, each a fragment pack and a blend (replace, alpha, premultiplied, add), drawn in order after a
    clearing draw with the core's input-free triangle (`shaders/mode.vert`). A pass declares `ModeSettings` (packed
    when the settings change), `ModeFrame` (packed from the record by name per accepted frame) and the conventions
    block; anything else is refused. `ModeSource` and `ModeContent` follow Spectrum's stream, admission and rest rules
    on a composite item (one content per item). Python face: `rendering/native/mode.py`.
  - `vulkan_context.*`: D6, the process's Vulkan instance and one device per window, given to Qt Quick.
  - `thread_probe.*`, `process_counters.*`: the D5.4 probe and the lifecycle counters.
  - No STL container, lock or function wrapper: their code is in `msvcp140.dll`, which the module never imports (the
    loader's runtime rule); Qt's types instead.
- `shaders/`: GLSL 440 sources (`.vert`, `.frag`, `.comp`), each baked by PySide6's `qsb` for every shipped backend
  and embedded in the module; the workflow's staging requires one `.qsb` per source. `srpss_conventions.glsl` is the
  production conventions include (`rendering/gl_programs/conventions.py`), spliced in at `//@srpss_conventions` by
  `cmake/compose_shader.cmake` before the bake.
- `python/import_check.py`: the GPU-free check the workflow runs after the compile, through `rendering.native`.
- `python/frozen_probe.py`: N2.1's frozen probe, the entry of a separate Nuitka build
  (`scripts/venv/build_native_core_probe.ps1`) that loads the module the way the frozen product will.
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
- `python/generic_mode_check.py`: N2.9's proof on the harness-only mode `python/probe_rings/` (blocks against an
  independent packer with the unknown and unfilled refusals, the reader by the runtime schema, the draw on OpenGL and
  Vulkan with shader, spec and simulation changes and no rebuild, nothing at rest, GPU time per pass).
- `python/timer_check.py`: N2.6's proof (off is free by count, a known-cost pass scaled N times and its empty-bracket
  control, QRhi's frame figure, latched reads in a real window with the waiting read as control, the frame trace and
  its report, the two forms against each other, validation; `timer_analysis.py`).

## How a new mode is built (N2.9; decision D12 in `Native_Core_P3_Decisions.md`)

No C++ and no module build while the mode is iterated to its mock and reactivity goals. `python/probe_rings/` is the
worked example (harness-only); a product mode does the same in the product's places:

1. **Its code.** Append the mode id to `core/visualizer_engine/packet_abi.py` `MODE_CODES` (append-only; run
   `tools/native_frame_abi_header.py`). A module built before keeps working: it reads the mode by its runtime schema
   and the face tolerates codes appended after it (`schema_table_differences`).
2. **Its simulation and record.** A Python simulation in the engine worker publishing one fixed-layout record per frame
   (`native_schema.NativeLayout.build` of `(name, kind, count)`; kinds u32, f64, f64x4; range rules on u32 fields).
   Its `NativeSchema` is handed to the core at bind (`NativeMode.bind(mapping, schema)`); it is never added to the
   compiled table (`native_schema._SCHEMA_MODULES` is for schemas a hand-written consumer reads).
3. **Its passes.** One fragment shader per pass (GLSL 440, `#define SRPSS_CONVENTIONS_FRAGMENT` and
   `//@srpss_conventions`; the pixel from `fragPixel`, no input), each declaring `ModeSettings` and `ModeFrame`
   (std140, any bindings but 17). Every record field is a `ModeFrame` member of some pass, named exactly as the field
   (an f64 a float, an f64x4 a vec4, a u32 an int, uint, bool or float, an array the same length). Baked by
   `tools/regen_qrc.py --shaders` beside the source (the harness bakes with the same baker at run time), handed over as
   bytes with the pass's blend (`ModePass`).
4. **Its spec and settings.** The controls in its spec (`core/settings/visualizer_mode_settings.py`), and one Python
   function giving every `ModeSettings` member by name from the spec and the card (target size, fade, ...), sent with
   the program (`NativeMode.program(passes, settings)`) and again when Settings or the card change
   (`NativeMode.settings`).
5. **What is refused, with its reason:** a setting no pass declares and a record field no pass's `ModeFrame` declares
   (unknown); a `ModeSettings` member no setting fills and a `ModeFrame` member no field names (unfilled); a value of the
   wrong size or without a defined conversion; a pass that declares a texture, a sampler, storage, a push constant,
   another block or an input; a schema that is not a valid fixed layout. A program that does not take the current
   settings is refused and the drawn one stays.

A new GPU technique (sampling an earlier pass, depth, more targets, compute, a new resource) is a primitive with its own
C++ and harness, then used by every mode as data. Hand-written C++ for a mode's simulation is admitted only after its
goals are met and a measurement shows the hot path (Transitions.md, "Where a mode's work lives on the native core").

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
