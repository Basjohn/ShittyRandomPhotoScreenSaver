# QRhi research for N3 (scene targets, meshes and buffers, compute)

Prepared 15 Nov 2026. Research only; no product code. Answers come from Qt's own source at the tag `v6.12.0` (the
module's Qt), fetched from `code.qt.io/cgit/qt/qtbase.git/plain/src/gui/rhi/<file>?h=v6.12.0`. The local SDK cache
(`D:\Temp\Scratch\SRPSS\native_spike\qt\include`) and the venv's PySide6 hold only the 6.11.2 headers, no QRhi
`.cpp`, so the tag was read from code.qt.io. Line numbers are of that tag's files and can shift in a patch release:
search the named function when re-checking. Tags: `[SRC]` source read; `[DOC]` the doc comments inside that source;
`[DERIVED]` my reading, not a sentence Qt or Khronos wrote; UNSETTLED where source could not decide it.

Files: `qrhi.cpp` (front end and docs), `qrhi.h`, `qrhivulkan.cpp` (`VK`), `qrhigles2.cpp` (`GL`).

Note on D14: no `D14` exists in `Docs/` (main checkout or this worktree) as of this date, so nothing here is checked
against it. D5 (D5.3 stream ring, D5.6 rows 9 and 7) was read. Re-check this file against D14 when it lands.

---

## N3.1 scene targets

**Q1. Vulkan `supportedSampleCounts()`: colour only, or colour and depth?** Colour AND depth AND stencil.
`VK qrhivulkan.cpp:4952-4970`: it ANDs `framebufferColorSampleCounts`, `framebufferDepthSampleCounts` and
`framebufferStencilSampleCounts` for each of 1..64. OpenGL (`GL qrhigles2.cpp:1351-1358`, `947-948`) returns every
power of two up to one `GL_MAX_SAMPLES` (min 1; on ES 2.0 it assumes 4, `:955`), with no per-format query.
`QRhiImplementation::effectiveSampleCount` (`qrhi.cpp:9043-9075`) never fails: an unsupported request is rounded UP
to the next supported count, else down to the largest, and only logged on the `QRHI_LOG_INFO` category.

What this means for N3.x:
- One list serves colour and depth on Vulkan; a request of 8x on a 4x device silently yields 4x. The sampling-policy
  owner must read `supportedSampleCounts()` itself and record the count it actually got (the achieved count decides
  every resolve, memory figure and parity check), not trust the requested one.
- The Vulkan list is the framebuffer limit for non-integer colour formats. QRhi does not query the per-format limit
  for RGBA16F. UNSETTLED whether the HDR intermediate can ever be offered fewer counts than the list says;
  `vkGetPhysicalDeviceImageFormatProperties` for the HDR format on the machine settles it. On OpenGL the one
  `GL_MAX_SAMPLES` is a single number, so a 3D Detail tier set from it is a ceiling, not a per-format fact.

**Q2. OpenGL resolve of multisampled colour and depth, and the feature flags.**
Resolve is `glBlitFramebuffer`, recorded at `endPass`, never inside the pass (`GL qrhigles2.cpp:5094-5232`).
- Colour: for each colour attachment with a `resolveTexture`, `endPass` queues `BlitFromRenderbuffer` (MSAA
  renderbuffer source, `:5110-5135`) or `BlitFromTexture` (MSAA texture source, `:5139-5173`). The executor
  (`:4083-4160` for textures, the renderbuffer twin just above) generates two temporary FBOs, attaches source and
  destination, runs `glBlitFramebuffer(0,0,w,h -> 0,0,w,h, COLOR_BUFFER_BIT, GL_NEAREST)` (`:4075-4078`,
  `:4153-4156`, comment "Qt 5 used Nearest when resolving samples"), then deletes both FBOs (`:4080`, `:4158`). One
  FBO pair is created and destroyed per resolve per pass.
- Depth: `depthResolveTexture` takes the same path with `isDepthStencil = true`: the blit mask is
  `DEPTH_BUFFER_BIT | STENCIL_BUFFER_BIT` (`:4077`, `:4155`), source from the depth-stencil renderbuffer or the
  multisample depth texture (`:5177-5213`), `GL_NEAREST` (a depth blit must be nearest).
- GLES with `GL_EXT_multisampled_render_to_texture` (`caps.glesMultisampleRenderToTexture`, `:1204`): the resolve is
  implicit through `glFramebufferTexture2DMultisampleEXT` (`:6644-6670`, depth `:6709-6719`) and `endPass` records
  nothing. Not our path (desktop GL).
- Flags. GL `MultisampleTexture` = GL 3.0 or ES 3.1 (`:1076-1078`, `:1635`); `MultisampleRenderBuffer` =
  `FramebufferMultisample` and `FramebufferBlit` extensions (`:958-959`, `:1637`); `ResolveDepthStencil` = always
  true (`:1724-1725`). Vulkan: `MultisampleTexture` and `MultisampleRenderBuffer` always true (`VK :5526-5529`);
  `ResolveDepthStencil` = `caps.renderPass2KHR && caps.depthStencilResolveKHR` (`:5610-5611`). Vulkan resolves in the
  render pass (a second attachment set, `:2151-2218`), depth with `VK_RESOLVE_MODE_SAMPLE_ZERO_BIT` (`:1848`) (so the
  resolved depth is the sample-0 depth, not min or max).
- Doc rules (`qrhi.cpp:2876-2894`, `:5569-5574`): the resolve target must be a 2D texture or array with the same
  format as the depth texture; a set depthResolveTexture makes `DoNotStoreDepthStencilContents` irrelevant (behaves
  as if set: the MSAA depth is discarded and only the resolved depth survives). Vulkan code agrees
  (`storeDs` excludes the resolve case, `:8260`). Colour: `storeOp` is DONT_CARE when a resolve texture is set and
  `PreserveColorContents` is not (`:2101`).
- Qt says depth resolve is not universally available and designs must not assume it (`qrhi.cpp:1064-1076`, `2884-2888`).

What this means for N3.x:
- The core must test `ResolveDepthStencil` at run time. On Vulkan it is false unless our imported device enabled
  `VK_KHR_create_renderpass2` and `VK_KHR_depth_stencil_resolve` (the N06/N07 facts doc A5: for an imported device Qt
  assumes they are enabled and sets the flags true without checking, `qrhivulkan.cpp:945`), so our device creation
  must enable both or `setDepthResolveTexture` will hit a missing function.
- On both backends, a multisampled depth that must be sampled afterwards (Extruded Bubble's sampled depth) needs the
  resolve texture; the MSAA depth itself is not sampleable by QRhi shaders (D5.3 already treats per-sample reads as
  out of scope). Depth resolve gives sample 0 on Vulkan and the NEAREST blit result on GL; they are not guaranteed to
  be pixel-identical to each other at edges. Parity gates for MSAA depth must be tolerance-based. UNSETTLED
  whether a GL depth-only format (no stencil) tolerates the `DEPTH|STENCIL` blit mask: GL's blit rule is that a mask
  bit is ignored when neither framebuffer has that buffer, but I could not confirm that for QRhi's D16/D32F paths from
  source. Make the sampled depth a depth-stencil format (D24S8) on GL, or test D32F once.
- On GL the resolve costs two glGenFramebuffers/glDeleteFramebuffers per resolve per frame: count them in the
  per-frame budget for any MSAA pass that resolves colour and depth (4 FBO creations). A mode that does not need
  MSAA does not pay it.

**Q3. Depth reused across passes and render-target splits on Vulkan: does depth loaded after a pass need handling
like colour's rule C?** Probably yes for a depth TEXTURE with `PreserveDepthStencilContents`; UNSETTLED until
validation shows it. Source facts (`VK qrhivulkan.cpp`):
- Offscreen render passes have no external subpass dependency; the comment says barriers come from resource tracking
  (`:2258-2261`). Depth attachment: `loadOp = LOAD` and `initialLayout = DEPTH_STENCIL_ATTACHMENT_OPTIMAL` when
  `PreserveDepthStencilContents`, else `CLEAR` and `UNDEFINED` (`:2130-2140`).
- Before the pass, `recordTransitionPassResources` (`:5381-5441`) emits one image barrier per tracked texture:
  `oldLayout` = last tracked layout, `srcStage/srcAccess` = last use, `dstStage/dstAccess` from the new use. For a
  depth texture the new use is `TexDepthOutput`: layout `DEPTH_STENCIL_ATTACHMENT_OPTIMAL`, access
  `DEPTH_STENCIL_ATTACHMENT_WRITE` ONLY (no READ bit, `:5288-5289`), stage `LATE_FRAGMENT_TESTS` (`:5322-5323`).
  Tracked at `:3283-3289`. A write-to-write reuse always gets a barrier (`:5417-5420`, `:5371-5374`), a read-to-same-read
  does not.
- Sampling the depth later uses `TexSample`: `SHADER_READ_ONLY_OPTIMAL`, `SHADER_READ`, stage vertex/fragment
  (`:5257-5258`, descriptor layout `:3807`), so depth-written-then-sampled is a normal tracked transition
  (`LATE_FRAGMENT_TESTS`/DS write to fragment/SHADER_READ). Depth-resolve target: tracked as `TexDepthResolveOutput`
  with `COLOR_ATTACHMENT_WRITE` at `COLOR_ATTACHMENT_OUTPUT` stage but layout `DEPTH_STENCIL_ATTACHMENT_OPTIMAL`
  (`:5262`, `:5290-5293`, `:3290-3296`); its render-pass attachment is `UNDEFINED -> DS_ATTACHMENT_OPTIMAL`, always
  discarded on entry (`:2205-2215`).
- Depth RENDERBUFFERS are not tracked; Qt adds an explicit barrier for the write-after-write hazard
  (`depthStencilExplicitBarrier`, `:3272-3282`). They keep nothing across passes anyway.
- [DERIVED] A `LOAD` of depth is a read of the attachment at the start of the pass. Vulkan's rule for load ops is, as I
  recall it, `DEPTH_STENCIL_ATTACHMENT_READ` in `EARLY_FRAGMENT_TESTS` (a CLEAR is a WRITE there). I could not confirm
  the stage and access wording from docs.vulkan.org within this task (the fetch truncated the render pass chapter).
  Qt's barrier above makes the data visible to `LATE_FRAGMENT_TESTS` with WRITE only, so the early-stage read of a
  preserved depth image is not in its second scope. This is the same class as finding C for colour in
  `Native_Core_N06_N07_Qt_Facts.md` section I (colour: `toVkAccess(TexColorOutput)` has no READ bit, so a `LOAD` after
  a prior use raises `SYNC-HAZARD-READ-AFTER-WRITE`). I did not see Qt emit a depth equivalent, and I did not run
  validation. What settles it: one hidden-host run with synchronization validation, depth texture
  `PreserveDepthStencilContents`, two passes in one frame on the same depth texture.

What this means for N3.x:
- Treat depth like colour. Either avoid `PreserveDepthStencilContents` (render the depth once per frame in one pass;
  the Extruded Bubble scene has one scene pass), or prime/transition the depth texture ourselves in `beginExternal`
  with a barrier whose second scope includes `EARLY_FRAGMENT_TESTS` and `DEPTH_STENCIL_ATTACHMENT_READ|WRITE`, then
  `setNativeLayout` (the harness's `primeColorTargetForLoad` pattern). Decide by the validation run, not by assumption.
- A depth texture needs `QRhiTexture` flags `RenderTarget` plus sampled use; its tracked layout flips between
  `DEPTH_STENCIL_ATTACHMENT_OPTIMAL` and `SHADER_READ_ONLY_OPTIMAL` for free through the tracker. Never sample the
  depth texture inside a pass that also renders to it (a feedback loop; QRhi does not forbid it).
- Splitting one scene into two passes on the same target (for example a depth pre-pass, or OIT after opaque) means the
  second pass uses `PreserveColorContents` and `PreserveDepthStencilContents` on a SECOND `QRhiTextureRenderTarget`
  with its own render-pass descriptor (`QRhiRenderPassDescriptor` compatibility). Colour rule C already applies to it.
- On GL none of this exists: FBO attachments and sampling need no barrier (`BarriersForPass` only emits
  `glMemoryBarrier` for shader-written resources, `GL qrhigles2.cpp:4174-4202`). A depth that works on GL can still
  fail on Vulkan; the validated Vulkan run is the gate.

---

## N3.2 meshes and buffers

**Q4. Dynamic uniform buffers with dynamic offsets.**
Vulkan: `QRhiShaderResourceBinding::uniformBufferWithDynamicOffset` becomes `VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC`
(`qrhivulkan.cpp:3776-3777`). Alignment is `minUniformBufferOffsetAlignment` (`:979`, `ubufAlignment()` `:5462-5465`,
"typically 256"); an asserted precondition, not a runtime check (`:3787`). Offsets are passed per
`setShaderResources(srb, count, {binding, offset}...)` and bound with `vkCmdBindDescriptorSets` and the dynamic offset
array in binding-number order, missing bindings defaulting to 0 (`:6159-6193`, executed `:5095-5106`). An srb with any
dynamic-offset binding is REBOUND on every `setShaderResources` call (`:6153-6154`: "dynamic offsets always need a
bind"). The descriptor pool reserves `QVK_UNIFORM_BUFFERS_PER_POOL` = 256 dynamic uniform descriptors per pool and 128
sets (`:1292-1307`, `qrhivulkan_p.h:32-33`). `maxDescriptorSetUniformBuffersDynamic` is never queried or enforced
(search finds no use); the Vulkan specification's minimum for it is 8, as I recall it (not confirmed from a fetched
page). `QRhi::MaxUniformBufferRange` reports `maxUniformBufferRange` (`:5662-5663`). `NonDynamicUniformBuffers` is true
(`:5540`).

OpenGL has no real uniform buffers. `GL ubufAlignment()` returns 1 (`qrhigles2.cpp:1377-1382`). A `UniformBuffer`
`QRhiBuffer` is a CPU `QByteArray` (`:5908-5915`; combining UniformBuffer with any other usage fails,
"multiple usages specified, this is not supported by the OpenGL backend"). Updates are `memcpy` into that array
(`:2845-2846`). `BindShaderResources` reads `data + viewOffset` and calls `glUniform*` for each uniform in the
pipeline's reflected uniform list (`:4576-4850`); the dynamic offset only changes `viewOffset` (`:4578-4583`).
Offsets are limited to `MAX_DYNAMIC_OFFSET_COUNT` = 8 per bind call (`qrhigles2_p.h:315`, warning at `:2154-2157`) and
an srb with dynamic offsets re-issues its uniforms every bind (`:2129`). `MaxUniformBufferRange` is
`maxUniformVectors * 16` (`:1777-1778`). Storage buffers (any backend) have no dynamic offset: a fixed `offset,size`
at binding time (`qrhi.h:490-495`, GL `glBindBufferRange` `:4912-4916`).

What this means for N3.x:
- A "ring slot" on a uniform buffer is a dynamic offset into ONE Dynamic uniform buffer, with the stride rounded up
  to `rhi->ubufAlignment()` (use `QRhi::ubufAligned`). The same code works on both backends; on GL the alignment is 1
  so a Vulkan-aligned stride only wastes CPU memory.
- On GL a dynamic uniform "buffer" costs `glUniform*` calls per bind, proportional to the number of uniforms in the
  block, not a buffer bind. Many small draws with per-draw dynamic offsets are cheap on Vulkan and call-heavy on GL;
  keep per-draw uniform blocks small, and prefer per-instance data in a vertex buffer or storage buffer.
- Keep a binding's dynamic-offset count at or below 8 per draw (GL hard cap; Vulkan's spec minimum limit is 8 as I
  recall it, which this core does not confirm at run time). One dynamic uniform binding per pass-level block is fine.
- A uniform buffer cannot double as a storage or vertex buffer on GL. Anything shared with compute is a
  `StorageBuffer` (Q7), never a `UniformBuffer`.
- UNSETTLED: the actual `maxDescriptorSetUniformBuffersDynamic` of the RTX 4090 and of other drivers. Log it once from
  the physical-device properties at device creation; QRhi will not warn.

**Q5. Instancing, per-instance inputs, `ShaderDrawParameters`, indirect draws.**
- Instancing: `QRhi::Instancing` true on Vulkan (`VK :5534`), GL 3.3+ or ES 3.0 (`GL :1026-1029`, `:1643`).
  `QRhiVertexInputBinding(stride, PerInstance, stepRate)` (`qrhi.cpp:1643-1662`): a step rate other than 1 requires
  `QRhi::CustomInstanceStepRate`: Vulkan only with `VK_EXT_vertex_attribute_divisor` (`VK :5536-5537`; for an imported
  device Qt assumes it is enabled, `:943`), GL always false (`GL :1645-1646`).
- `BaseVertex`: Vulkan true, GL 3.2+ (`GL :1031`). `BaseInstance` (`firstInstance`): Vulkan true, GL ALWAYS false,
  "all versions of OpenGL" (`GL :1667-1673`, doc `qrhi.cpp:840-849`): on GL the `firstInstance` argument is ignored and
  the instance ID starts at 0. `InstanceIndexIncludesBaseInstance`: Vulkan true, GL false (`GL :1735-1736`,
  `VK :5620`).
- `ShaderDrawParameters` (`gl_BaseInstance`, `gl_BaseVertex`, `gl_DrawID`), new in 6.12 (`qrhi.cpp:1150-1153`): Vulkan
  reports the physical device's `shaderDrawParameters` feature (1.1/1.2 feature structs, `VK :997-1009`, `:5628-5629`);
  GL: GL 4.6 or `GL_ARB_shader_draw_parameters`, never on ES (`GL :1276-1281`, `:1743-1744`).
- Indirect draws ARE in 6.12 QRhi: `QRhiCommandBuffer::drawIndirect` / `drawIndexedIndirect(indirectBuffer, offset,
  drawCount, stride)` (`qrhi.cpp:10715-10790`, `\since 6.12`), buffers of usage `QRhiBuffer::IndirectBuffer`
  (`qrhi.cpp:4019-4026`), command structs `QRhiIndirectDrawCommand` (16 bytes) and `QRhiIndexedIndirectDrawCommand`
  (20 bytes) (`qrhi.h:1705-1724`). Feature `QRhi::DrawIndirect`: Vulkan always true (`VK :5624-5625`), GL desktop 4.0+
  or `GL_ARB_draw_indirect` (`GL :1238-1243`). `QRhi::DrawIndirectMulti` (a `drawCount` above 1 in one native call):
  Vulkan = the device's `multiDrawIndirect` feature (`VK :995`), GL 4.3+ or `ARB/EXT_multi_draw_indirect` with the
  entry points resolved (`GL :1245-1274`). Without it QRhi loops one draw per command on the CPU (`VK :6540-6551`,
  GL `:3705-3711`). `IndirectBuffer` may be combined with `StorageBuffer` (compute writes the commands). It is
  Static or Immutable only for use with `StorageBuffer`. Offset and stride must be multiples of 4; `drawCount > 1`
  is native only "if stride is the default".
- Qt never queries or enables the Vulkan `drawIndirectFirstInstance` feature (search finds none), yet
  `QRhiIndirectDrawCommand::firstInstance` is passed through; on Vulkan a non-zero value in an indirect command is
  invalid unless that feature is enabled on the device.

What this means for N3.x:
- Instanced quads are portable: use a PerInstance vertex binding with step rate 1. Do not use a step rate other than 1
  (GL cannot, and an imported Vulkan device must have enabled the divisor extension).
- Never rely on `firstInstance` for per-batch instance offsets: on GL it is ignored. Offset the instance data (a buffer
  offset in `setVertexInput`) or add an offset uniform instead.
- `gl_DrawID`, `gl_BaseInstance`, `gl_BaseVertex` in shaders: gate every use on `QRhi::ShaderDrawParameters` and ship
  a variant without them (desktop GL below 4.6 without the extension lacks them). UNSETTLED: whether `qsb` compiles
  these built-ins to our GLSL target correctly; one compile test settles it.
- Indirect draws: use `drawIndexedIndirect` where `DrawIndirect` is reported; use `DrawIndirectMulti` to decide
  whether one call draws many (if false, QRhi loops, so no gain from "many draws in one buffer"). Our imported Vulkan
  device must enable `multiDrawIndirect` AND `drawIndirectFirstInstance` (D6 rule: the device enables what Qt's would)
  or QRhi's flag and the legal use diverge. `firstInstance` in an indirect command should stay 0 on GL < 4.2
  (not confirmed from source: UNSETTLED; keep it 0 everywhere).

**Q6. `QRhiBuffer::Dynamic` mapping and the cost D5.3's pair must beat.**
Vulkan: `Dynamic` = TWO buffers, one per frame slot (`QVK_FRAMES_IN_FLIGHT = 2`, `qrhivulkan_p.h:30`), each
`VMA_MEMORY_USAGE_CPU_TO_GPU` created with `VMA_ALLOCATION_CREATE_MAPPED_BIT` (persistently mapped; not on macOS)
(`qrhivulkan.cpp:7271-7283`, `:7291-7300`). So the buffers are host-visible memory (on a discrete GPU, system memory or
the 256 MB BAR window; VMA picks). A non-Dynamic buffer is GPU-only with a staging buffer and a GPU copy
(`:7280-7283`, `:4283-4320`). `Dynamic` cannot combine with `StorageBuffer` on Vulkan ("StorageBuffer cannot be
combined with Dynamic", `:7257-7260`). Update paths:
1. `QRhiResourceUpdateBatch::updateDynamicBuffer`: stores a copy of the data (a QByteArray in the batch) and queues a
   `pendingDynamicUpdates` entry on BOTH slots (`:4275-4282`). When the buffer is next used in a frame of that slot
   (setShaderResources, setVertexInput, draws), `executeBufferHostWritesForSlot` `memcpy`s each pending update into
   that slot's mapped memory and flushes (`:4765-4795`, `:5975-5976`, `:6223-6224`). The same bytes are therefore
   copied once into the batch, then once per slot (twice in total, in two consecutive frames).
2. The fast path `beginFullDynamicBufferUpdateForCurrentFrame` / `endFull...` / `fullDynamicBufferUpdateForCurrentFrame`
   (`qrhi.h:898-900`, `VK :7331-7359`): map the current slot, write directly, flush. No batch copy, one write per
   frame, but "unexpected results when combined with batch updates" (Qt's comment `:7333-7337`) and the whole buffer
   changes each frame.
OpenGL: `Dynamic` = ONE `GL_DYNAMIC_DRAW` buffer, no per-frame copies (`GL :5930`; UniformBuffer usage is a CPU array,
`:5908-5915`). A batch update retains a copy of the data and issues `glBufferSubData` at command execution
(`:2842-2856`, `:3806-3810`, `retainBufferData`), preceded by a barrier if the buffer was shader-written
(`trackedBufferBarrier`, `:2848`). The fast path is `glMapBufferRange(WRITE | INVALIDATE_BUFFER)` plus `glUnmapBuffer`
when `MapBufferRange` exists, else a CPU array and `glBufferSubData` (`:5949-5977`), or `glBufferSubData` directly
(`:5979-5989`). OpenGL's "persistent" mapping (`GL_MAP_PERSISTENT_BIT`) is not used anywhere in QRhi.

Cost model D5.3's pair has to beat: on Vulkan, per dynamic buffer and per frame, one (batch) or zero (fast path) host
copy into the batch, plus one memcpy and one `vmaFlushAllocation` into already-mapped host-visible memory. The mapping
cost is already zero (persistent). The only things a persistently mapped pair can remove are the batch copy and the
second slot's duplicate write, and the flush on coherent memory. On GL the baseline is `glBufferSubData` (driver
copy into the buffer, possibly a stall/orphan) or an invalidating `glMapBufferRange` per update. A persistent-mapped
GL buffer (`GL_MAP_PERSISTENT_BIT | COHERENT`, triple-buffered) removes a driver copy and the retained batch copy.

What this means for N3.x:
- On Vulkan, QRhi's Dynamic is already "host-visible, persistently mapped, double-buffered". D8 row 8's pair can only win
  on the batch copy, the double write and `vmaFlushAllocation` (a no-op on coherent memory, but QRhi calls it).
  Measure those (the fast path first) before building anything: the fast path already removes the batch copy.
- On GL the pair is a real difference (`glBufferSubData` against persistent mapping). The measurement must be done on
  the OpenGL backend with the fast path as the baseline, not the batch path.
- A Dynamic buffer holds 2 copies of its size (Vulkan): D5.3's ring sizes are doubled in memory under QRhi; the pair
  at one copy per frame in flight is the same 2 copies, so memory is not a differentiator at 2 frames in flight.
- A `Dynamic` buffer cannot be a compute storage buffer (Vulkan). Compute-fed data (Q7) is Static, GPU-resident.
  UNSETTLED: nothing here measures bandwidth; D5.3's 0.05 ms threshold needs the product's ring sizes.

---

## N3.3 compute

**Q7. Storage buffers shared by compute and draws; barriers from binding access types; read-after-write inside one
pass; OpenGL's compute support and barriers.**
Support: `QRhi::Compute` = Vulkan: the graphics queue's family has `VK_QUEUE_COMPUTE_BIT` (`VK :976`, `:5550-5551`);
GL: desktop 4.3+ or ES 3.1 (`GL :1033-1036`, `:1659-1660`). GL caps (`maxThreadsPerThreadGroup`, group limits)
come from `GL_MAX_COMPUTE_*` (`:1038-1048`). Binding types `bufferLoad`, `bufferStore`, `bufferLoadStore` need
`StorageBuffer` usage, Static or Immutable only (`qrhi.cpp:4011-4017`, `VK :7257`). `IndirectBuffer`, `VertexBuffer`
and `IndexBuffer` can be added to the same buffer for compute-generated draw data (`qrhi.cpp:4019-4026`). The compute
pass: `beginComputePass` ... `setComputePipeline`, `setShaderResources`, `dispatch` ... `endComputePass`.

Vulkan barriers are derived from the tracked access on each binding (`VK qrhivulkan.cpp`):
- Per pass: `beginPass`/`beginComputePass` enqueue a tracker (`:3525`), every binding use registers an access
  (`:5969-6118`: UniformBuffer -> `UNIFORM_READ`; bufferLoad -> `SHADER_READ`; bufferStore -> `SHADER_WRITE`;
  bufferLoadStore -> both, `toVkAccess` `:5196-5218`; vertex buffer -> `VERTEX_ATTRIBUTE_READ`/`VERTEX_INPUT`;
  index; indirect -> `INDIRECT_COMMAND_READ`/`DRAW_INDIRECT`, `:6244-6246`, `:6513-6515`; stage from the binding's
  stage flags, earliest of vertex/tess/fragment/compute/geometry, `qrhi.cpp:12179-12196`). At the start of the NEXT
  pass `recordTransitionPassResources` emits one `VkBufferMemoryBarrier` per tracked buffer from its last state to
  its first use in that pass (`:5386-5409`; skipped if the state has not changed and the new access is a read,
  `:5393-5396`). So compute write -> later draw (vertex input, fragment `bufferLoad`, indirect) is covered across the
  pass boundary, with the right destination stage and access, as long as the use is declared through QRhi (a binding,
  `setVertexInput`, or `drawIndirect`).
- Inside one compute pass, dispatch-to-dispatch hazards: `dispatch()` keeps a `writtenResources` set (`:3600-3686`).
  A resource written in an earlier dispatch of the pass and touched again by this dispatch gets a
  `VkBufferMemoryBarrier`/image barrier `COMPUTE -> COMPUTE`, `SHADER_WRITE -> (this dispatch's SHADER_READ and/or
  WRITE)` before the dispatch (`:3645-3709`). So read-after-write and write-after-write between two dispatches
  in one compute pass ARE handled. A resource that was written and is only read now is removed from the set (that
  barrier covered it). In addition `setShaderResources` adds a `SHADER_READ|WRITE` memory barrier when a binding
  was registered with a store access earlier in the same pass (`:6055-6064`, `:6098-6107`, `:6125-6145`).
- Gaps. (a) The barrier is keyed on SHADER_WRITE, so write-after-READ (dispatch N reads, dispatch N+1 writes the
  same buffer) gets no barrier: the second write is a "new" write (`isNew`, `:3596-3597`, `:3648`). (b) Registering one
  buffer with different access types in one pass makes the pass tracker print "used with different accesses within
  the same pass, this is not allowed" and ignore the later one (`qrhi.cpp:12111-12116`; textures merge only
  load/store pairs, `:12156-12163`). (c) Buffer barriers use `VK_WHOLE_SIZE`: no sub-range tracking. (d) Dynamic
  buffers cannot be storage buffers.
- `DoNotTrackResourcesForCompute` pass flag exists (`qrhi.h:1735-1736`, doc `qrhi.cpp:8526`); it is read by GL
  (`GL :5088`), and its effect is only to skip tracking for passes that do not use compute.

OpenGL (`GL qrhigles2.cpp`): `beginPass` and `beginComputePass` enqueue `BarriersForPass` (`:5062`, `:5251`). When
that command runs it issues `glMemoryBarrier(buffer set)` for any tracked buffer whose last access was a write
(storage write, update), and `glMemoryBarrier(texture set)` for any such texture; because it cannot know which kind
of write came before, it sets ALL bits of the class: buffers `VERTEX_ATTRIB_ARRAY | ELEMENT_ARRAY | UNIFORM |
BUFFER_UPDATE | SHADER_STORAGE | COMMAND` (`:2623-2631`), textures `TEXTURE_FETCH | SHADER_IMAGE_ACCESS | PIXEL_BUFFER |
TEXTURE_UPDATE | FRAMEBUFFER` (`:2633-2640`, `:4174-4202`). Inside a compute pass `dispatch()` runs the same
`writtenResources` logic and emits `glMemoryBarrier(GL_SHADER_STORAGE_BARRIER_BIT)` (buffers) or
`GL_SHADER_IMAGE_ACCESS_BARRIER_BIT` (images) before a dispatch that touches an earlier-dispatch write (`:5312-5379`).
`beginExternal` while a compute pass has written resources emits `glMemoryBarrier(GL_ALL_BARRIER_BITS)`
(`:2415-2421`). Storage buffers bind with `glBindBufferBase/Range` at SRB bind time (`:4912-4916`); there is no dynamic
offset. The same write-after-read gap applies.

What this means for N3.x:
- Declare every use through QRhi: bind compute-written buffers with `bufferStore`/`bufferLoadStore` in the compute
  pass, and use them in the draw as `setVertexInput` (usage `StorageBuffer | VertexBuffer`), `bufferLoad` in the
  vertex or fragment stage, or `drawIndirect` (usage `StorageBuffer | IndirectBuffer`). Then the pass-boundary barriers
  on Vulkan and the `glMemoryBarrier` calls on GL come for free. Never reach the buffer by a raw handle without a
  matching QRhi declaration, or the tracker never sees the write.
- Write all dispatches of one compute step in ONE compute pass only when each buffer is used with a single access
  type per pass; a ping-pong needs two buffers, or two passes. A "write, read, write the same buffer" sequence in one
  pass has no write-after-read barrier: use two buffers or split the pass.
- Compute buffers are Static or Immutable and GPU-resident, so CPU data enters through staging
  (`uploadStaticBuffer` through a batch). Per-frame CPU-written data for compute is a Dynamic buffer read by a
  non-storage path, or a Static buffer re-uploaded (Vulkan staging copy, GL `glBufferSubData` with a barrier).
- GL pays a barrier per pass boundary for every shader-written resource used by the next pass; it is a full class-wide
  barrier, so avoid interleaving many compute and draw passes per frame on the OpenGL backend (batch compute, then draw).
- Vulkan compute needs the queue family compute bit: with our own device (D6) the graphics queue family must be a
  graphics+compute family (true for NVIDIA's universal family). `QRhi::Compute` false means N3.3 is absent on that
  device; the product must degrade by feature flag, never by assumption.
- UNSETTLED: that the pass-boundary barriers have the correct source stage when the last user was a draw reading the
  buffer as vertex input and the next pass writes it in compute (write-after-read across passes). The tracker emits a
  barrier because the access changes, but I did not prove its stage/access pairing for that direction; one validated
  run (draw reads buffer, then compute writes it, next frame) settles it.

---

## Round 2

Same sources (Qt 6.12.0 tag; `qtdeclarative` files for Qt Quick: `qsgrhisupport.cpp` `QSGR`, `qsgthreadedrenderloop.cpp`
`TRL`, `qquickwindow.cpp`, `qquickgraphicsconfiguration.cpp`, `qsgdefaultrendercontext.cpp`) and the same tags and marks.
Sections 8 to 12 continue the numbering of the question list.

## N3.4 transparency and post-processing

**Section 8. Weighted-blended OIT on QRhi: per-attachment blending, mixed-format MRT, blend factors and ops.**
- Per-attachment blend state exists: `QRhiGraphicsPipeline::setTargetBlends`, one `TargetBlend` per colour attachment
  (`qrhi.cpp:7240-7251`: "there needs to be a TargetBlend structure per render target"). Each carries `enable`,
  `colorWrite`, `srcColor/dstColor/opColor`, `srcAlpha/dstAlpha/opAlpha` (`qrhi.cpp:7069-7114`).
- Feature `QRhi::PerRenderTargetBlending` (since 6.9; `qrhi.cpp:1110-1114`). Vulkan: always true (`VK qrhivulkan.cpp:5617-5619`);
  the pipeline fills one `VkPipelineColorBlendAttachmentState` per `TargetBlend` (`:8920-8943`). Qt never checks or
  enables the device feature `independentBlend`, which Vulkan requires when attachments differ (search finds no use): a
  Qt-created device enables all features, an imported device (D6) must. OpenGL: true on desktop GL 4.0+ and ES 3.2+
  (`GL qrhigles2.cpp:1223-1226`, `:1731-1732`); applied with `glColorMaski`, `glBlendFuncSeparatei`,
  `glBlendEquationSeparatei` per draw buffer (`:4269-4317`). When the flag is false, OpenGL applies ONLY the first
  `TargetBlend` to every draw buffer (`:4279-4313`: `break` after buffer 0, plain `glBlendFuncSeparate`).
- Blend factors: Zero, One, Src/OneMinusSrc Color and Alpha, Dst/OneMinusDst Color and Alpha, Constant/OneMinusConstant
  Color and Alpha, SrcAlphaSaturate, and the four `Src1*` (dual-source) factors (`qrhi.cpp:6987-7010`). Ops: Add,
  Subtract, ReverseSubtract, Min, Max (`:7012-7021`). Vulkan maps all of them (`VK :7001-7039`; `Src1*` need the
  device feature `dualSrcBlend`, not checked or enabled by QRhi). OpenGL maps all but the four `Src1*` factors, which
  warn "Unsupported blend factor" and become `GL_ZERO` (`GL :3057-3099`). No logic ops, no advanced blend.
- MRT with mixed formats: the limit is `QRhi::MaxColorAttachments` (GL `maxDrawBuffers` `:1757-1758`; Vulkan
  `maxColorAttachments` `VK :5642-5643`). A `QRhiTextureRenderTarget` takes one `QRhiColorAttachment` per target, each
  with its own texture, so RGBA16F plus R16F/R8 in one target is expressed directly. Texture format support:
  RGBA16F, R16F need `floatFormats` (GL 3.0+/ES 3.0, `GL :994`, `:1614-1620`); `R8` needs `TextureRGFormats`
  (`caps.r8Format`, `:981`, `:1605`). Vulkan's `isTextureFormatSupported` only tests that the format can be sampled
  (`VK :5517-5520`): QRhi never asks whether the format is colour-attachment-blendable.
- Clears: `beginPass` takes ONE `colorClearValue`, written into every colour attachment's clear value (`VK :3445-3458`,
  GL: one `glClearColor` then a clear of the draw buffers, `GL :5080-5083`). There is no per-attachment clear value.

What this means for N3.x:
- WBOIT (accumulation RGBA16F with `One,One,Add` for colour and alpha; revealage R16F or R8 with
  `Zero,OneMinusSrcColor,Add`, which uses only factors both backends have) is expressible on both backends with
  `PerRenderTargetBlending` true. Gate the OIT stage on that flag: on a GL below 4.0 only one blend state applies
  to all attachments and WBOIT is off.
- The two attachments need different clears (accumulation 0, revealage 1). With one clear value for all, store the
  revealage inverted instead (clear 0, blend `One,One,Add` of coverage, resolve with `1 - r`), or clear it with a
  fullscreen draw. Decide in the OIT design; this is a QRhi limit, not a backend one.
- Do not use `Src1*` factors: GL has none.
- UNSETTLED: that RGBA16F, R16F and R8 are blendable colour attachments on every device. QRhi does not check. Vulkan
  guarantees blend support for the common 16-bit-float and 8-bit-UNORM colour formats by specification (from the
  Vulkan format-requirements tables; not fetched here); GL 3.0+ makes float colour buffers renderable and blendable.
  A one-time device probe (`vkGetPhysicalDeviceFormatProperties` blend bit) settles it.
- The WBOIT transparent pass needs the OPAQUE pass's depth as a loaded, depth-test-only attachment. QRhi has no
  read-only depth attachment, so this is a `PreserveDepthStencilContents` load on the same depth texture: the
  depth-load hazard of section Q3 applies to the OIT stage.

**Section 9. Bloom and HDR chains: a render target per mip level, sampling one level while rendering another.**
- Rendering to a non-base level: `QRhiColorAttachment::setLevel` (`qrhi.cpp:2474`, example `:2639`), feature
  `RenderToNonBaseMipLevel` (`qrhi.cpp:872-876`): Vulkan always true (`VK :5568`); GL true on desktop, ES 3.0+
  (`GL :1066-1069`, `:1682-1683`). Vulkan creates a one-level image view per attachment (`VK :8315-8316`).
- QRhi tracks usage per TEXTURE, not per subresource: one `UsageState` {layout, access, stage} per `QVkTexture`
  (`VK :5367-5379`) and its barriers cover `baseMipLevel 0`, `VK_REMAINING_MIP_LEVELS` (`:5424-5425`). A sampled
  binding uses the whole-image view (`levelCount = mipLevelCount`, `VK :7647`) with `SHADER_READ_ONLY_OPTIMAL`
  (`:3807`).
- Consequence: a pass that renders to level N of texture T and samples level N-1 of the same T registers T both as
  `TexColorOutput` and `TexSample` in one pass. The pass tracker rejects that: "Texture used with different accesses
  within the same pass, this is not allowed" (`qrhi.cpp:12151-12164`; only load/store image pairs merge). [DERIVED] The
  Vulkan image would also have to be in `COLOR_ATTACHMENT_OPTIMAL` and `SHADER_READ_ONLY_OPTIMAL` at once; QRhi
  holds one layout per image. So QRhi cannot do "write level N while reading level N-1" in one texture on Vulkan.
- A sampler cannot pick one level: QRhi samplers carry `mipmapMode` and filters but no LOD range
  (`VK :7881`: `maxLod = 1000` with mipmaps, `0.25` without); `QRhiSampler::mipmapMode = None` samples level 0 only.
  A shader picks a level with `textureLod` or `texelFetch(tex, ivec2, lod)` (`QRhi::TexelFetch`: Vulkan true,
  GL 3.0+ `GL :1680-1681`, `:1071`).
- OpenGL: sequential passes are legal; the FBO attaches `glFramebufferTexture2D(..., level)` (`GL :6655-6656`). QRhi
  never sets `GL_TEXTURE_BASE_LEVEL`/`MAX_LEVEL` (search finds none in `qrhigles2.cpp`), so a mip-filtered sampler
  covers all levels while one level is attached: [DERIVED] a rendering feedback loop by GL's definition, which is
  undefined behaviour. With a non-mipmapped sampler only level 0 is sampled. UNSETTLED: driver behaviour on the
  RTX 4090 for sampling level N-1 while attached to N; it may work and still be undefined.
- Barriers between sequential passes: the tracker emits one image barrier per texture per pass start
  (`VK :5381-5441`): for a texture that was `ColorOutput` in the last pass and is `TexSample` now, colour-output write
  to fragment-shader read plus the layout change for the WHOLE image. Writing a different level of an image that was
  just sampled forces the whole image back to `COLOR_ATTACHMENT_OPTIMAL`, preserving contents (the old layout is
  tracked, so no discard).
- `QRhiResourceUpdateBatch::generateMips` (Vulkan: a `vkCmdBlitImage` chain with `VK_FILTER_LINEAR` per level, with
  per-level `subresourceBarrier`s, restoring the original layout, `VK :4669-4740`, `:4028-4050`; GL: `glGenerateMipmap`
  `GL :4161-4164`) needs `UsedWithGenerateMips`, runs outside a render pass, and is a 2x2 box-like filter.

What this means for N3.x:
- Build the bloom pyramid as one TEXTURE PER LEVEL (or two ping-pong textures) with each level a normal single-level
  render target and a plain sampled binding. This is portable, has no feedback-loop risk, and QRhi tracks each
  texture separately. A single mipped texture with per-level targets works only when each pass reads from a different
  texture than it writes, which defeats the point.
- Use `generateMips` for a plain box downsample chain if its filter is acceptable (it is linear 2x2 blits, not a
  13-tap bloom filter); a quality downsample needs the per-level-texture form.
- Do not count on `textureLod` into a texture while that texture is a render target on GL.
- Layout and barriers are QRhi's for the chain: each pass start emits one whole-image barrier per texture; a chain of
  K levels in separate textures costs K barriers, no more.

---

## N3.6 lifetime

**Section 10. Pipeline cache: format, validity, what Qt Quick stores, whether the core can share it.**
- API: `QRhi::pipelineCacheData()` / `setPipelineCacheData()` (`qrhi.cpp:11304-11390`), feature
  `PipelineCacheDataLoadSave` (Vulkan true; GL `caps.programBinary` = GL 4.1+/ES 3.0 with the binary-format query,
  `GL :1082-1091`, `:1690-1691`). `pipelineCacheData()` returns empty unless the `QRhi::EnablePipelineCacheDataSave`
  create flag was set (`qrhi.cpp:677-696`, `VK :5757`). `releaseCachedResources()` may clear what was collected.
  The blob is for the Qt version and backend, and "QRhi takes care of adding the appropriate header and safeguards"
  (`qrhi.cpp:11322-11328`); a mismatch is ignored with a debug print only (category `qt.rhi.general`).
- Vulkan format (`VK :5740-5862`): a 32-byte header {`rhiId` (Qt version and backend), pointer size, `driverVersion`,
  `vendorID`, `deviceID`, `dataSize`, UUID size, reserved}, then the 16-byte `pipelineCacheUUID`, then the raw
  `vkGetPipelineCacheData` bytes. `setPipelineCacheData` rejects on any mismatch of Qt version/backend, architecture,
  driver version, vendor, device or pipeline cache UUID, or a short blob; on success it destroys the current
  `VkPipelineCache` and creates a new one with the data as initial data (`:5851-5861`). One `VkPipelineCache` per QRhi
  (created at the first pipeline, `ensurePipelineCache`, `VK :3733-3748`).
- OpenGL format (`GL :1838-1958`): a 256-byte header {`rhiId`, pointer size, binary count, data size, 240-byte
  renderer string}, then, per program, {key length, key, binary length, binary, binary format}. The key is a hash of
  the shader source plus the vertex input names and locations (`:5764-5805`). Load checks Qt version/backend,
  architecture, and `strncmp` of the renderer/version string; the driver's own `glProgramBinary` and link status are
  the final check, and a failure falls back to a normal compile (`:5810-5828`). A program binary is also stored in
  Qt's older OpenGL disk cache when the pipeline-cache flag is NOT set (`:7032-7040`, `:7154-7161`, `lcOpenGLProgramDiskCache`).
- What Qt Quick stores (`QSGR qsgrhisupport.cpp:950-1117`, `qquickgraphicsconfiguration.cpp:236-322`): the AUTOMATIC cache
  is on unless `Qt::AA_DisableShaderDiskCache`, `QT_DISABLE_SHADER_DISK_CACHE`, `QSG_RHI_DISABLE_DISK_CACHE` (the doc
  text names `QSG_RHI_DISABLE_SHADER_DISK_CACHE`; the code reads the first spelling, `:842-844`) or
  `setAutomaticPipelineCache(false)`. One file per application and per backend:
  `<QStandardPaths::CacheLocation>/qtpipelinecache-<buildAbi>/qqpc_<backend>` (`:950-984`). It is read at QRhi creation
  (`preparePipelineCache` -> `setPipelineCacheData`, called from `createRhi`, `:1296-1298`) and written ONCE, in
  `destroyRhi`, only if the QRhi is not device-lost (`:1306-1315`); windows with Dialog/Popup flags do not save
  (`:991-995`). The save flag `EnablePipelineCacheDataSave` is set on the QRhi only when saving is enabled for the
  window (`:1137-1161`). Explicit file names win: `setPipelineCacheLoadFile` / `SaveFile`, or the env vars
  `QSG_RHI_PIPELINE_CACHE_LOAD/SAVE` (not allowed by the project's no-env-flag rule; use the API). The writes use
  `QSaveFile` (atomic). With several windows the single automatic file holds the data of whichever QRhi finalizes last
  (doc `qquickgraphicsconfiguration.cpp:309-319`).
- Imported device: the config's pipeline-cache settings are still read (the N06/N07 facts doc A6: they sit outside the
  `!importedDevice` branch of device creation and Qt's own file logic is independent of device ownership).

What this means for N3.x:
- Pipelines the core creates on Qt Quick's QRhi (the frame driver's `window->rhi()`) go into that QRhi's one
  `VkPipelineCache`, and Qt Quick saves them automatically at window teardown, as long as saving is enabled. The core
  need not own a file for those; it must not disable Qt's automatic cache, and a window the saver kills hard writes
  nothing (the save happens only in an orderly `destroyRhi`; a device loss never saves). Decide whether a screensaver
  exit is orderly enough; if not, set an explicit `pipelineCacheSaveFile` per window and the core can write earlier
  itself through `rhi->pipelineCacheData()`.
- The core's own raw Vulkan pipelines (D5.3 services) are NOT in that cache. Raw pipelines need their own
  `VkPipelineCache` and file, with the same checks as Qt's header (driver version, vendor, device, UUID, our own
  version). The job-thread QRhi (N2b) is a second QRhi with its own `VkPipelineCache`; it saves nothing unless the core
  calls `pipelineCacheData()` on it and writes a file of its own.
- The automatic file is one per backend and not per window: the multi-display saver (one QRhi per window) saves only
  the last window to close. Give each window an explicit file (`setPipelineCacheSaveFile`/`LoadFile` through
  `QQuickGraphicsConfiguration`), per display or one shared and merged by us. UNSETTLED: whether a file loaded by two QRhis
  of different windows is safe; each calls `setPipelineCacheData` independently with `QSaveFile` atomic writes, so
  reading is safe, but the last writer wins.
- A Qt, driver or GPU change silently drops the cache (a rebuild with a cold compile): warm-up (N3.6) must not rely on
  the cache having data.
- `releaseCachedResources()` can clear collected pipeline data on some backends; do not call it before the save.

**Section 11. Device loss: reporting, what Qt Quick does, what the core rebuilds.**
- Reporting. `QRhi::isDeviceLost()` and `FrameOpDeviceLost` (`qrhi.cpp:11296-11302`, `:11860-11866`: "may also be
  recoverable by releasing all resources, including the QRhi itself, and then recreating all resources").
  Vulkan: `VK_ERROR_DEVICE_LOST` from `vkAcquireNextImageKHR` (`VK qrhivulkan.cpp:2728-2733`), submit, present and
  fence waits (`:2888-3058`) sets `deviceLost` and returns `FrameOpDeviceLost`; it logs `VK_EXT_device_fault` detail
  when the device has it (`printDeviceLossErrorInfo`, `:4184-4267`, flag `caps.deviceFault`). After loss, QRhi skips
  `vkQueueWaitIdle` and fence waits (`:1189`, `:2605-2612`). OpenGL: `contextLost` is set only when
  `QOpenGLContext::makeCurrent` fails and the context is no longer valid (`GL qrhigles2.cpp:706-742`,
  `:1833-1836`); `beginFrame`/`endFrame` then return `FrameOpDeviceLost` (`:2467-2468`). QRhi never queries
  `glGetGraphicsResetStatus` or robustness (search finds none), so a GL driver reset that leaves the context current is
  not detected by QRhi.
- Qt Quick, threaded loop (`TRL qsgthreadedrenderloop.cpp:591-599`, `:659`, `:694-702`, `:774-781`): on loss in
  `beginFrame`, `endFrame` or swapchain creation it logs "Graphics device lost, cleaning up scenegraph and releasing
  RHI", runs `teardownGraphics` (`:579-589`: `cleanupNodesOnShutdown`, `sgrc->invalidate()`, release the swapchain,
  `destroyRhi` if Qt owns it), sets `rhiDeviceLost`, and posts a `FullUpdateRequest`. The next frame calls
  `ensureRhi` (`:879-899`), which creates a new QRhi (no `rhiDoomed` while `rhiDeviceLost` is set) and re-initialises the
  scene graph. `sgrc->invalidate` (`qsgdefaultrendercontext.cpp:147-221`) deletes textures, depth-stencil buffers,
  atlases and glyph caches and emits `invalidated`, which is connected to `QQuickWindow::sceneGraphInvalidated`
  (`qquickwindow.cpp:841-842`), emitted on the render thread ("all user resources tied to that context should be
  released", `qquickwindow.cpp:2571-2586`; with OpenGL the context is NOT current on a real context loss). The
  window-sized `sceneGraphInitialized` then fires again after the rebuild.
- `QRhi::create` on rebuild reuses `wd->customDeviceObjects` (`QSGR :1124`, `:1202-1210`): the same adopted
  `VkDevice`/queue handles. `QQuickWindow::setGraphicsDevice` only stores the value (`qquickwindow.cpp:4480-4484`).
  [DERIVED] after a true `VK_ERROR_DEVICE_LOST` on our device the rebuild would re-adopt a dead device unless the core
  replaces it. UNSETTLED: whether `setGraphicsDevice` called from the `sceneGraphInvalidated` slot (render thread)
  takes effect for the rebuild (it is a plain store, and the docs say it must precede scene graph initialisation, which
  has been undone), and the threading of that call. A hidden-host loss test (forced via a layer or TDR) settles it.

What this means for N3.x:
- Qt rebuilds: its QRhi, swapchain, scene graph, textures, atlases, glyph caches, its own pipelines and Quick items'
  resources, on the window (render) thread, with no core involvement, once the device itself is usable.
- The core rebuilds, on the `sceneGraphInvalidated` / `sceneGraphInitialized` edges: everything in its Window and Job
  scopes (D5 lifetime table): all QRhi resources it created (scene targets, meshes, buffers, pipelines, compute
  resources, SRBs), all raw Vulkan objects (they die with the device), the job-thread QRhi and its device-scope objects,
  and any texture wrapped from a native image. QRhi resources of a destroyed QRhi must not be touched (QRhi's
  deferred-release queue is cleared in `destroy`); use `QRhi::addCleanupCallback` (`qrhi.cpp:9673-9684`) to learn that a
  QRhi is going away.
- Detect loss yourself on the core's own frame edges: `QRhi::isDeviceLost()` after every `beginFrame` the core relies
  on, and a failing `QRhi::finish()`/submit on the job queue. On OpenGL expect false negatives (see above), so a
  GL "loss" arrives as a context-invalid makeCurrent only.
- Log `VK_EXT_device_fault` once (N3.6 already plans it); it needs the extension enabled on our device and Qt must
  see `caps.deviceFault` (assumed true for an imported device, N06/N07 facts A5).
- The rebuild must come from the last packet (N3.6): keep CPU-side copies of everything needed; GPU-held history
  (N3.9) is lost on a loss unless mirrored.

**Section 12. Release timing: `deleteLater` against `destroy`, and when the GPU object really dies.**
- `destroy()` releases or "requests deferred releasing of" the native objects; the C++ object stays valid and can
  `create()` again (`qrhi.cpp:3718-3736`). Every backend's `destroy()` moves the native handles into a release queue
  rather than deleting them (e.g. `QVkBuffer::destroy`, `VK :7225-7250`).
- `deleteLater()` adds the C++ object to a list that `QRhi::endFrame` (and the offscreen equivalent) deletes when the
  frame ends (`qrhi.cpp:3776-3782`, `:11877-11882`); outside a frame it is `delete` now. It only keeps the C++ instance
  alive until the end of the current frame; the native object's safety is the backend's deferred release, the same for
  both ("the underlying native graphics objects are never destroyed until ... not used by the GPU in an still in-flight
  frame", `qrhi.cpp:3749-3755`).
- Vulkan: `QVK_FRAMES_IN_FLIGHT = 2` (`qrhivulkan_p.h:30`, `resourceLimit(FramesInFlight)` `VK :5644-5645`). An
  entry records `lastActiveFrameSlot` (the slot of the last frame that recorded a use) and is destroyed in
  `executeDeferredReleases` when `currentFrameSlot == lastActiveFrameSlot`, or when it was never used
  (`lastActiveFrameSlot < 0`), or when forced (`VK :4829-4885`). `executeDeferredReleases` runs from `prepareNewFrame`
  at `beginFrame` and `beginOffscreenFrame` (`:2762`, `:3083`, `:2923`), after that slot's fence has been waited. So an
  object last used in frame N dies at the start of frame N+2 (the next time slot N%2 comes round) and not before the GPU is done
  with frame N; an unused one dies at the next `beginFrame`. Forced: `QRhi::finish()` does `vkQueueWaitIdle` then
  `executeDeferredReleases(true)` (`:3176-3222`); `QRhi::destroy` does the same (`:1184-1193`).
- OpenGL: no slots (`FramesInFlight` = 1, `GL :1759-1761`). `destroy()` appends to `releaseQueue`; `executeDeferredReleases`
  deletes EVERYTHING in it, unconditionally, at the next `beginFrame`, `beginOffscreenFrame` or at `QRhi::destroy`
  (`GL :1321-1349`, `:2474`, `:2534`, `:1296`). The GL driver orders its own commands, so a delete one frame later is
  safe.
- Dynamic buffers hold per-slot buffers: a destroyed Dynamic buffer releases both (`VK :7229-7240`).

What this means for N3.x:
- A resource the core stops using this frame can be `destroy()`ed or `deleteLater()`ed at once, with the same GPU
  safety; use `deleteLater()` whenever the C++ object may still be touched by recorded commands of the CURRENT frame
  (it must not be deleted before `endFrame`). The native object dies 2 frames after its last use on Vulkan, next frame
  on GL (never earlier than GPU completion).
- Memory is not returned at the moment of retirement: a retired scene target (N3.1, N3.7) keeps its VRAM for up to two
  further Qt frames on Vulkan. Budget peaks as live + retired-within-2-frames. If no frame comes (nothing is
  animating, the saver is idle) the release waits: call `QRhi::finish()` from the owner of the QRhi (the render thread)
  to force it, which also costs a full queue idle, so use it only at lifecycle edges, never per frame.
- On Qt Quick's QRhi we do not choose when `beginFrame` runs; a window that stops presenting leaves the queue
  undrained. For the core's job-thread QRhi it owns `beginOffscreenFrame`/`finish()` itself.
- Raw Vulkan objects the core creates (D5.3 services) get no deferred release: the core must apply the same "last used
  slot" rule itself, or wait idle.

---

## Open items in one place
- D14 was not found (see the top); re-check this file against it.
- Round 2: section 8, device probe for blend support of the OIT formats and enabling `independentBlend`, `dualSrcBlend`
  not needed. Section 9, GL feedback loop on a sampled level behaviour on the 4090. Section 10, two-window cache
  sharing. Section 11, `setGraphicsDevice` after loss and its threading, GL loss detection. Section 12, nothing open.
- Q1: per-format Vulkan sample counts for the HDR format (check once per device).
- Q2: a depth-only format with the GL blit mask `DEPTH|STENCIL` (test D32F once, or use D24S8).
- Q3: depth `LOAD` hazard after a prior pass: a validated hidden-host run settles it.
- Q4: the device's real `maxDescriptorSetUniformBuffersDynamic`; log it.
- Q5: qsb compile of `gl_DrawID`/`gl_BaseInstance`/`gl_BaseVertex`; `firstInstance` in indirect commands on GL 4.0/4.1.
- Q6: no measurement made; D5.3's 0.05 ms gate still needs the product's ring sizes on both backends.
- Q7: write-after-read across a pass boundary (buffer read in a draw, written by the next compute pass).
