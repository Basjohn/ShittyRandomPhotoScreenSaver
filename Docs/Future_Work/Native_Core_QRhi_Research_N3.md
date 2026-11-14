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

## Open items in one place
- D14 was not found (see the top); re-check this file against it.
- Q1: per-format Vulkan sample counts for the HDR format (check once per device).
- Q2: a depth-only format with the GL blit mask `DEPTH|STENCIL` (test D32F once, or use D24S8).
- Q3: depth `LOAD` hazard after a prior pass: a validated hidden-host run settles it.
- Q4: the device's real `maxDescriptorSetUniformBuffersDynamic`; log it.
- Q5: qsb compile of `gl_DrawID`/`gl_BaseInstance`/`gl_BaseVertex`; `firstInstance` in indirect commands on GL 4.0/4.1.
- Q6: no measurement made; D5.3's 0.05 ms gate still needs the product's ring sizes on both backends.
- Q7: write-after-read across a pass boundary (buffer read in a draw, written by the next compute pass).
