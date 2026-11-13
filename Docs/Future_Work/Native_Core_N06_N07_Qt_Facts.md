# N0.6 / N0.7 facts: our own Vulkan device under Qt Quick 6.12, and a job thread beside it

Prepared 12 Nov 2026 for the engineering agent who builds plan boxes N0.6 (D6's proof) and N0.7 (D9's proof) in the
P1 harness (`native/spike_p1/`). Facts only, from primary sources; nothing from the project was sent anywhere. Where
this file and `Native_Core_P3_Decisions.md` (D6, D9) disagree, this file is a finding for the lead, not an edit.

**How to read the tags.** `[DOC]` = doc.qt.io (Qt 6.12 documentation pages, which are generated from the same
comments as the source). `[SRC]` = Qt source at `code.qt.io`, branch `6.12` as fetched on 12 Nov 2026 (the branch head,
not the tag `v6.12.0`: re-read the cited function against the tag the module is built with before relying on a line
number; function names are what to search for). `[KHR]` = the Khronos Vulkan reference (`registry.khronos.org` now
redirects to `docs.vulkan.org`, the same specification). `[DERIVED]` = my reading of the cited source, not a sentence
Qt or Khronos wrote. `[3RD]` = a third-party dataset, named as such.

Source URL prefixes used below (append the file path):
- `QTBASE` = `https://code.qt.io/cgit/qt/qtbase.git/plain/` + path + `?h=6.12`
- `QTDECL` = `https://code.qt.io/cgit/qt/qtdeclarative.git/plain/` + path + `?h=6.12`

What the spike already does (`native/spike_p1/src/`): `gui_helpers.cpp::attachVulkanInstance` creates one
`QVulkanInstance` with `QRhiVulkanInitParams::preferredInstanceExtensions()` and sets it on the window;
`quick_offscreen.cpp::QuickOffscreenSession` drives a `QQuickRenderControl` with `initialize()`, an offscreen
`QQuickRenderTarget::fromRhiRenderTarget`, `beginFrame/sync/render/endFrame`, on its own render thread. At the time of writing nothing created a
`VkDevice`, a real swapchain window, a second queue or validation layers; N0.6 and N0.7 built them in the harness
the same day (merged 12 Nov; section I and `Native_Core_P3_Decisions.md` D6/D9 record what was measured).

---

## A. Bringing our own Vulkan device to Qt Quick

**A1. The call chain.** `QQuickGraphicsDevice::fromDeviceObjects(VkPhysicalDevice, VkDevice, int queueFamilyIndex,
int queueIndex = 0)` returns a value object; `QQuickWindow::setGraphicsDevice()` takes it.
- [DOC] https://doc.qt.io/qt-6/qquickgraphicsdevice.html : "suitable for Vulkan"; physical device, device and queue
  family "must always be provided"; queue index defaults to 0. "does not own any native resources, it merely
  contains references. It is the caller's responsibility to ensure that the native resource exists as long as
  necessary." Available since Qt 6.0.
- [SRC] QTDECL `src/quick/items/qquickgraphicsdevice.cpp`, `QQuickGraphicsDevice::fromDeviceObjects`: only stores the
  four values (type `DeviceObjects`). Sibling factories: `fromPhysicalDevice` (Qt creates device and queue, we choose
  the GPU), `fromRhi(QRhi*)` (since 6.6: hand Qt a QRhi we created; "the caller must be careful to only share a QRhi
  ... between QQuickWindows that are known to be compatible"), `fromRhiAdapter` (since 6.10, same as
  `fromPhysicalDevice` for Vulkan).
- [DOC] https://doc.qt.io/qt-6/qquickwindow.html (`setGraphicsDevice`, since 6.0): "can only be called before
  initializing the scenegraph and will have no effect if called afterwards"; with a window, before the first
  `show()`; with `QQuickRenderControl`, "right before `QQuickRenderControl::initialize()`".
- [DOC] same page, `setGraphicsConfiguration`: "The configuration is ignored when adopting existing graphics
  devices." Read this as: the device-creation parts are ignored (see A4); the source still reads pipeline-cache and
  debug-marker settings from it (A6).

**A2. What Qt does with the four values.** [SRC] QTDECL `src/quick/scenegraph/qsgrhisupport.cpp`,
`QSGRhiSupport::createRhi`: for `Type::DeviceObjects` it fills a `QRhiVulkanNativeHandles` (`physDev`, `dev`,
`gfxQueueFamilyIdx`, `gfxQueueIdx`) and calls `QRhi::create(QRhi::Vulkan, &rhiParams, flags, &importDev)`. It sets
`rhiParams.inst = window->vulkanInstance()` (warns "No QVulkanInstance set for QQuickWindow, this is wrong." if
none), `rhiParams.window = window` only when the window already has a native handle, and
`rhiParams.deviceExtensions = graphicsConfig.deviceExtensions()`. It does not set `importDev.vmemAllocator`, so Qt
creates its own allocator on our device (A7). The resulting QRhi is Qt's: `createRhi` returns `{rhi, true}` and
`QSGRhiSupport::destroyRhi` does `delete rhi` (calling `QSGRenderThread::cleanup` in `qsgthreadedrenderloop.cpp`).

**A3. The instance.**
- [DOC] https://doc.qt.io/qt-6/qvulkaninstance.html : every Vulkan `QWindow` needs a `QVulkanInstance` via
  `QWindow::setVulkanInstance()`; "typically a single instance constructed early on in main()".
- [SRC] QTDECL `qsgrhisupport.cpp`, `QSGRhiSupport::prepareWindowForRhi`: a `QQuickWindow` without an instance gets
  `QVulkanDefaultInstance` automatically, but "with `QQuickRenderControl`, no `QVulkanInstance` is created, because
  it must always be under the application's control". So for our windows we call `window->setVulkanInstance(ours)`
  before show; the spike already does this for render control.
- Two ways to have "the module owns the instance":
  (i) `QVulkanInstance::create()` with `setApiVersion`, `setLayers`, `setExtensions`, then use `vkInstance()` for
  our `vkCreateDevice`. [DOC] qvulkaninstance.html: unsupported layers and extensions are silently dropped; the
  surface extension for the platform is added automatically.
  (ii) We call `vkCreateInstance` ourselves and give it to Qt with `QVulkanInstance::setVkInstance()` before
  `create()`. [DOC]: "Makes QVulkanInstance adopt an existing VkInstance handle ... QVulkanInstance will not own the
  handle"; the instance needs `VK_KHR_surface` and `VK_KHR_win32_surface` (and `VK_EXT_debug_utils` for debug output
  redirection); "Qt has no means to enable layers and extensions on an already created VkInstance"; for QRhi, also
  enable `QRhiVulkanInitParams::preferredInstanceExtensions()`.
  [SRC] QTBASE `src/gui/vulkan/qbasicvulkanplatforminstance.cpp`, `QBasicPlatformVulkanInstance::initInstance`:
  when adopting, `m_enabledExtensions` and `m_enabledLayers` are simply what we told `QVulkanInstance` through
  `setExtensions()` / `setLayers()`; Qt does not query the instance. QRhi then tests `inst->extensions()` for
  `VK_KHR_get_physical_device_properties2` and `VK_EXT_debug_utils`, so when adopting we must pass the exact lists we
  enabled. `create()` is still called after `setVkInstance()`.
- [DERIVED] Route (ii) is the only route where the harness can chain structures onto `VkInstanceCreateInfo` (D, below),
  and it matches D6 point 1 ("the module creates the instance").

**A4. The API version must be set on the QVulkanInstance, even when adopting.** [DOC]
https://doc.qt.io/qt-6/qvulkaninstance.html `setApiVersion`: "By default vulkanVersion is 0, which maps to Vulkan 1.0."
[SRC] QTBASE `src/gui/rhi/qrhivulkan.cpp`, `QRhiVulkan::create`: `caps.apiVersion = inst->apiVersion()`, then clamped
to the physical device's version; the 1.1/1.2/1.3/1.4 feature structs are queried only when `caps.apiVersion` is at
least that version; the VMA allocator's `vulkanApiVersion` follows it. [DERIVED] with an unset `QVulkanInstance` API
version Qt runs the device as Vulkan 1.0 (no multiview, no shader-draw-parameters caps, 1.0 allocator) whatever our
`VkInstance` was created with. Call `setApiVersion(QVersionNumber(1, 2))` (the D6 baseline) in both routes.

**A5. What Qt requires of an imported device.**
- [DOC] https://doc.qt.io/qt-6/qrhivulkaninitparams.html ("Working with existing Vulkan devices"): the physical
  device is always set; to adopt a `VkDevice` set `dev` and "the graphics queue family index is required", queue
  index optional (0); an existing command pool or allocator is optional; "The QRhi does not take ownership of any of
  the external objects." Query `QRhiVulkanInitParams::preferredExtensionsForImportedDevice()` and enable the result on
  our `VkDevice`, "otherwise some QRhi features may be unavailable". Setting `window` in the init params is
  recommended: without it there is "no way to ensure presenting is supported while choosing a graphics queue" (for
  an imported device that choice is ours, below).
- [SRC] `QRhiVulkanInitParams::preferredExtensionsForImportedDevice()` in QTBASE `qrhivulkan.cpp` returns exactly:
  `VK_KHR_swapchain`, `VK_EXT_vertex_attribute_divisor`, `VK_KHR_create_renderpass2`, `VK_KHR_depth_stencil_resolve`,
  `VK_KHR_fragment_shading_rate`. `QRhiVulkanInitParams::preferredInstanceExtensions()` returns exactly
  `VK_KHR_get_physical_device_properties2` and `VK_EXT_swapchain_colorspace`. (Our create-time code should still
  intersect with what the device reports, as Qt's own path does with `devExts.contains(...)`.)
- [SRC] `QRhiVulkan::create`, imported branch: "Here we have no way to tell if the extensions got enabled or not.
  Pretend it's all there and supported": `caps.deviceFault`, `vertexAttribDivisor`, `renderPass2KHR`,
  `depthStencilResolveKHR` are set true without checking. It then resolves `vkCreateRenderPass2KHR` and clears
  `renderPass2KHR` if that fails to resolve. [DERIVED] if we leave out `VK_KHR_create_renderpass2` on our device the
  failure is graceful for that one, but `vertexAttribDivisor` and `deviceFault` stay claimed true.
- Queue: [SRC] `QRhiVulkan::create` does `vkGetDeviceQueue(dev, gfxQueueFamilyIdx, gfxQueueIdx)` and uses that one
  queue for all frame submits and presents (`endAndSubmitPrimaryCommandBuffer`, `vkQueuePresentKHR(gfxQueue, ...)`).
  Nothing checks the queue's flags for an imported device. Swapchain creation does check:
  `QVkSwapChain::ensureSurface` calls `inst->supportsPresent(physDev, gfxQueueFamilyIdx, window)` and fails with the
  warning "Presenting not supported on this window". So the queue must be graphics-capable (render passes) and
  present-capable. `caps.compute` is true only if that family has `VK_QUEUE_COMPUTE_BIT`.
- Present support can be found before any window exists: [KHR]
  https://docs.vulkan.org/refpages/latest/refpages/source/vkGetPhysicalDeviceWin32PresentationSupportKHR.html "can be
  called prior to creating a surface". [SRC] QTBASE `src/plugins/platforms/windows/qwindowsvulkaninstance.cpp`,
  `QWindowsVulkanInstance::supportsPresent` combines that call with `vkGetPhysicalDeviceSurfaceSupportKHR` on the
  window's surface (the window must already have a native handle for the second part).
- Features: see A6.

**A6. What changes between a Qt-created device and an imported one.**

| Aspect | Qt-created | Imported (`fromDeviceObjects`) | Source |
|---|---|---|---|
| Queues | one queue, `queueCount = 1`, priority 0, from the first family with graphics (and present for the window, and compute preferred) | whatever we created; Qt uses only the (family, index) we name | `QRhiVulkan::create` |
| Device extensions | swapchain, portability subset, vertex attribute divisor, renderpass2 (+ multiview/maintenance2 on 1.0), depth-stencil resolve, fragment shading rate, device fault, plus `QQuickGraphicsConfiguration::deviceExtensions()` and env `QT_VULKAN_DEVICE_EXTENSIONS`, each only if the device has it | exactly ours; `deviceExtensions` and the env var are **not read** (they are inside the `!importedDevice` branch) | `QRhiVulkan::create` |
| Features | "Enable all features that are reported as supported, except robustness": `robustBufferAccess` and, on 1.3, `robustImageAccess` off; the 1.0 to 1.4 feature structs are chained, so everything the device supports is on (timeline semaphores included on 1.2+) | exactly ours | `QRhiVulkan::create` (comment "Enable all features ... Enabling all features mainly serves third-party renderers that may use the VkDevice created here") |
| Capability flags | from the features it queried | **still from the features the physical device supports, not from what our device enabled**: `depthClamp`, `wideLines`, `tessellationShader`, `geometryShader`, `fillModeNonSolid`, `multiDrawIndirect` (becomes `QRhi::DrawIndirectMulti`), multiview and shader-draw-parameters (1.1+), `pipelineFragmentShadingRate` and `attachmentFragmentShadingRate` | `QRhiVulkan::create`, after "Choose queue and create device" |
| Allocator | VMA created by the QRhi, `VMA_ALLOCATOR_CREATE_EXTERNALLY_SYNCHRONIZED_BIT` (no internal mutex: "A QRhi is supposed to be used from one single thread only") | same, unless `vmemAllocator` is passed (Qt Quick does not pass one) | `QRhiVulkan::create` |
| Pipeline cache | `VkPipelineCache` created and owned by the QRhi; load/save of its data is Qt's own file logic driven by `QQuickGraphicsConfiguration` | identical; independent of who owns the device | `QSGRhiSupport::preparePipelineCache`, `finalizePipelineCache`; [DOC] https://doc.qt.io/qt-6/qquickgraphicsconfiguration.html (`setPipelineCacheSaveFile`, since 6.5) |
| Device destruction | QRhi calls `vkDestroyDevice` and `inst->resetDeviceFunctions(dev)` | QRhi does neither (`if (!importedDevice && dev)`) | `QRhiVulkan::destroy` |

[DERIVED] consequences:
1. D6 point 3's "Unverified" is now verified from source: Qt's own device enables every supported feature except two
   robustness ones, so "feature bits" is not a reason to own the device, and the record the plan box asks for is
   available without a runtime probe by reading `QRhiVulkan::create` (the runtime proof can still log
   `vkGetPhysicalDeviceFeatures2` against the enabled set on Qt's own device through a layer or the
   `QRhiVulkanNativeHandles` of a Qt-created QRhi to confirm).
2. **New requirement on our device.** Because QRhi derives its capability flags from supported features, our
   `VkDevice` must enable the same feature set Qt would have (simplest: everything the device reports supported,
   robustness off, as Qt does), or QRhi will report capabilities the device cannot use (a `drawIndirect` multi-draw
   without `multiDrawIndirect`, a wide-line pipeline without `wideLines`, a fragment-shading-rate request without
   the extension and feature). This is a build rule for the harness's device creation and a candidate gate: the
   enabled set equals the Qt-created device's set, logged.
3. After our own `vkDestroyDevice`, call `QVulkanInstance::resetDeviceFunctions(device)` ourselves ([DOC]
   https://doc.qt.io/qt-6/qvulkaninstance.html "this function must be called when a VkDevice, for which
   deviceFunctions() was called, gets destroyed while the application intends to continue running"; QRhi called
   `deviceFunctions(dev)` on it). A reused handle value would otherwise get the old cached function table.

**A7. Object lifetime and teardown order.**
- [DOC] qquickgraphicsdevice.html: the device must exist "as long as necessary"; qvulkaninstance.html: the instance is
  available "as long as this QVulkanInstance exists, or until destroy() is called".
- [SRC] QTDECL `src/quick/scenegraph/qsgthreadedrenderloop.cpp`, `QSGRenderThread::cleanup` (only reached when the
  scene graph is wiped: `window->isPersistentSceneGraph()` and `isPersistentGraphics()` both default true, so a
  hide alone keeps the QRhi): `sgrc->invalidate()`, then `releaseSwapchain(window)`, then `destroyRhi` (QRhi
  `destroy()` waits idle on its own queue only, `vkQueueWaitIdle(gfxQueue)`, destroys its pools, pipeline cache and
  allocator, never the device). The Windows `VkSurfaceKHR` is destroyed when the platform window is
  (`QWindowsWindow::invalidateSurface` / destructor in `qwindowswindow.cpp`, through the window's
  `QVulkanInstance`).
- [KHR] https://docs.vulkan.org/refpages/latest/refpages/source/vkDestroyDevice.html : all child objects must be
  destroyed first; "vkDeviceWaitIdle can be used to gate the destruction of the device"; host access to all
  `VkQueue` objects "must be externally synchronized".
- [DERIVED] order for a window: stop our own users of the device (job thread quiesced, D9 point 6) -> close/destroy
  the `QQuickWindow` so Qt's scene graph, swapchain and QRhi are gone (a window that is only hidden still holds the
  QRhi) -> `vkDeviceWaitIdle` (this also covers the job queue, which Qt's QRhi never waits on) -> destroy our own
  child objects -> `resetDeviceFunctions` -> `vkDestroyDevice` -> (after the last window) destroy the
  `QVulkanInstance`, then our `VkInstance` if we own it. The device must therefore outlive the `QQuickWindow`
  object, not just its visibility.

**A8. Threading of the instance.** [SRC] QTBASE `qvulkaninstance.cpp`, `QVulkanInstance::deviceFunctions` takes a
mutex around its per-device cache, so one `QVulkanInstance` shared by several render threads is supported for that
call (the threaded render loop is Qt's own use). We have not found a documented statement beyond this; Qt Quick's own
default instance is shared by all windows.

---

## B. `QRhi::setQueueSubmitParams` and gating Qt's frame from a second queue

**B1. The API.** [DOC] https://doc.qt.io/qt-6/qrhi.html (`setQueueSubmitParams`, since 6.9) and
[SRC] QTBASE `src/gui/rhi/qrhi.cpp`: "additional arguments to the next submission of commands to the graphics command
queue ... with Vulkan this allows passing in a list of Vulkan semaphore objects for vkQueueSubmit() to signal and
wait on. `params` must then be a `QRhiVulkanQueueSubmitParams`". "This function affects the next queue submission
only, which will happen in endFrame(), endOffscreenFrame(), or finish(). The enqueuing of present happens in
endFrame()." Struct (`qrhi_platform.h`): wait, signal and present-wait semaphore arrays with counts. No 6.12 change
found: the `\since 6.12` markers in `qrhi.cpp` are indirect draws, `ShaderDrawParameters`, depth-layer rendering and
nothing about submission.

**B2. What QRhiVulkan does with it.** [SRC] QTBASE `qrhivulkan.cpp`:
- `QRhiVulkan::setQueueSubmitParams` copies the three arrays into member lists.
- `QRhiVulkan::endAndSubmitPrimaryCommandBuffer` builds a plain `VkSubmitInfo` with **no `pNext`** (no
  `VkTimelineSemaphoreSubmitInfo`), sets `pWaitDstStageMask` to `VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT` for
  every wait semaphore, submits to `gfxQueue`, then **clears both lists**. The present-wait list is consumed and
  cleared in `endFrame`'s present.
- [KHR] https://docs.vulkan.org/refpages/latest/refpages/source/VkTimelineSemaphoreSubmitInfo.html : timeline values go
  in a `VkTimelineSemaphoreSubmitInfo` on the `pNext` of `VkSubmitInfo`; for a binary semaphore the value is ignored.
  Without that structure a timeline semaphore passed to `vkQueueSubmit` has no value to wait for.

[DERIVED] consequences for D9 point 4 and D6 point 6:
1. Binary semaphores only (confirmed from source, not just the header). Timeline semaphores can be used by the
   job thread's own submissions (we write those), never by Qt's frame submit.
2. **The wait is staged at `COLOR_ATTACHMENT_OUTPUT`.** [KHR] the second synchronization scope of a wait is limited by
   `pWaitDstStageMask`; vertex and fragment shader stages come before colour output in pipeline order, so a binary
   semaphore passed this way does not hold back a shader that samples the job's output. It is sound for work that
   only touches colour output (an attachment-only consumer) and unsound for "this frame samples the job's result".
   D9 point 4 ("Qt's frame submit waits on it") needs this caveat, or the exception needs a different gate (a
   submission we control; the latch, D9 point 3; or our own barrier recorded in the frame through
   `beginExternal`).
3. **One-shot.** The lists are cleared after each submit, so the call must be repeated before every frame that needs
   the gate, from the render thread that owns that QRhi (`QQuickWindow::beforeRendering` is the hook; the `QRhi` is
   `QQuickWindow::rhi()`, valid on the render thread after initialisation).
4. Each binary-semaphore signal can have only one wait ([KHR] vkQueueSubmit: "there must be no other queues waiting
   on the same semaphore"), and a wait must reference a signal already submitted. A job that signals for a frame
   that is dropped leaves an unconsumed signal; the harness must count signals and waits.
5. Queue family ownership: see C3.

---

## C. A second QRhi on the same VkDevice, on another queue, for the job thread

**C1. Is it allowed?** [DOC] https://doc.qt.io/qt-6/qrhi.html "Threading": "A QRhi instance and the associated
resources can be created and used on any thread but all usage must be limited to that one single thread. When
rendering to multiple QWindows ... having a dedicated thread and QRhi instance for each window is often advisable."
"Resources are not shareable between QRhi instances. This is an intentional choice ... Safe and efficient concurrent
use of graphics resources from multiple threads is ... currently out of scope." [DOC] qrhivulkaninitparams.html adds
that `vmemAllocator` can let "two QRhi instances share one Vulkan memory allocator" (Qt's own allocator has no
mutex, so a shared allocator used from two threads would need our own locking: do not share it).
[SRC] `QRhiVulkan::create` imported branch: nothing prevents it; each QRhi calls `vkGetDeviceQueue` on the family and
index in its own `QRhiVulkanNativeHandles`, creates its own command pools (`poolInfo.queueFamilyIndex =
gfxQueueFamilyIdx`), descriptor pool, query pool, VMA allocator and pipeline cache.
So: yes, a second `QRhi::create(QRhi::Vulkan, &params, flags, &handles)` with the same `physDev`/`dev` and a different
`gfxQueueFamilyIdx`/`gfxQueueIdx` is the supported import path, used from exactly one thread (the job thread).
Nothing in the documentation or source says two QRhis on one device is unsupported; nothing blesses it either: it is
a use the API's wording permits and that the harness must prove (E2).

**C2. What the job QRhi can and cannot do.**
- `rhiParams.window` is left null (no swapchain). It uses `beginOffscreenFrame` / `endOffscreenFrame`.
  [SRC] `QRhiVulkan::endOffscreenFrame` submits with a fence and **waits only when a readback is pending** (the
  spike comment "completes synchronously" is true because the spike reads back). Otherwise the fence is waited at the
  next `beginOffscreenFrame` for that slot (`waitCommandCompletion`). The completion edge a job thread wants is
  `QRhi::finish()`: [SRC] `QRhiVulkan::finish` submits what is recorded, then `vkQueueWaitIdle(gfxQueue)` (that
  QRhi's own queue only), then runs deferred releases. That is "the job thread waits for its own submission on its own
  thread" (D9 point 3) in one call, and it does not touch Qt's queue.
- A family without `VK_QUEUE_GRAPHICS_BIT` is not rejected by the import path; `caps.compute` follows
  `VK_QUEUE_COMPUTE_BIT`. [DERIVED] QRhi compute passes and copies should work on a compute-only or transfer-only
  family, graphics passes would not. **Unconfirmed in practice**, so the harness probes it on the development GPU
  (E2) before D9 relies on a dedicated family; on NVIDIA Windows the usual layout has many queues in the one
  universal family, in which case the job QRhi simply takes another index of the same family ([3RD] Vulkan
  database listings; the real answer is `vkGetPhysicalDeviceQueueFamilyProperties` on the machine, which the harness
  logs).
- The job must not use `QRhiCommandBuffer::beginExternal` on Qt's QRhi; raw Vulkan on the job thread uses our own
  command pool on the job queue, with the same device functions (`QVulkanInstance::deviceFunctions(dev)` is cached and
  mutex-protected, and Vulkan commands on a device may be called from any thread if the host-synchronised objects
  are respected).
- A QRhi texture from the job QRhi is not usable by Qt's QRhi ("not shareable between QRhi instances"). The
  hand-over is by native object: the job QRhi's `QRhiTexture::nativeTexture()` returns `{VkImage, layout}` and Qt's
  QRhi imports it with `QRhiTexture::createFrom(NativeTexture)` (format, size and flags set correctly first; "does not
  take ownership"), then `setNativeLayout()` after external work. [DOC] https://doc.qt.io/qt-6/qrhitexture.html .
  The importing QRhi tracks that image's access and stage from zero; it knows only the layout we tell it.

**C3. Queue family ownership, the part D9 point 3 omits.** [SRC] `qrhivulkan.cpp`: images and buffers are created
through VMA from zero-initialised create-info structs and no `sharingMode` is assigned anywhere except the swapchain
(`VK_SHARING_MODE_EXCLUSIVE`), and every barrier QRhi records uses `VK_QUEUE_FAMILY_IGNORED` for source and
destination family. [DERIVED] QRhi-created resources are exclusive and QRhi never records a queue family ownership
transfer. [KHR] https://docs.vulkan.org/refpages/latest/refpages/source/VkSharingMode.html : exclusive resources "must
only be accessed by queues in the queue family that has ownership", and moving them to another family requires an
ownership transfer; concurrent sharing "may result in lower performance". So:
- Job queue in the same family as Qt's graphics queue (another queue index): QRhi-created job outputs can be sampled by
  Qt's queue without a transfer. This is the case to prefer and the one the first proof should use.
- Job queue in a different family: the job's outputs must be raw Vulkan images/buffers created by us with
  `VK_SHARING_MODE_CONCURRENT` (or with explicit release/acquire barriers on both queues, which QRhi cannot
  record), imported into Qt's QRhi by `createFrom`.

**C4. Memory visibility behind the latch (unconfirmed, E4).** D9 point 3's route is: job queue work -> job thread
waits on its own fence/`finish()` -> publishes an atomic generation -> the frame driver reads it and uses the output on
Qt's queue. Whether "fence wait on the host, then submit work on another queue" is a complete memory dependency for
device writes from the first queue is a spec question I could not settle from the pages fetched (the long
synchronization chapter was truncated by the fetch). The Vulkan specification's rules on fence signal operations and
host-ordered submissions decide it. The harness's answer is the validator: Khronos synchronization validation (D3)
reports a missing dependency as a hazard. Do not assume it is clean; make the test (iv) of D9 the arbiter.

---

## D. Translucent Vulkan windows on Windows

**D1. Does QRhi's Vulkan swapchain ask for a non-opaque `compositeAlpha`?** Yes, when told the surface has alpha,
and with a deliberate fallback.
- [SRC] QTDECL `src/quick/scenegraph/qsgthreadedrenderloop.cpp` (swapchain creation in the render thread):
  "QQ is always premul alpha. Decide based on alphaBufferSize in requestedFormat()": `alphaBufferSize() > 0` adds
  `QRhiSwapChain::SurfaceHasPreMulAlpha`. So a `QQuickWindow` whose requested `QSurfaceFormat` has an alpha buffer
  (`QSurfaceFormat::setAlphaBufferSize(8)` on the window or the default format before the window is created) takes
  the premultiplied path. (The same logic is in QTDECL `src/quick/scenegraph/qsgrenderloop.cpp`, the basic loop; Qt Quick has no
  non-premultiplied mode.)
- [SRC] QTBASE `qrhivulkan.cpp`, `QRhiVulkan::recreateSwapChain`: `compositeAlpha` starts as `INHERIT` if
  `supportedCompositeAlpha` contains it, else `OPAQUE`; with `SurfaceHasPreMulAlpha` it becomes `PRE_MULTIPLIED` if
  supported, else `POST_MULTIPLIED` if supported, else stays as above. The in-source comment is the primary
  statement of the Windows situation: "On Windows with NVIDIA for example, the only supportedCompositeAlpha value
  reported is OPAQUE, nothing else. Yet transparency works regardless, as long as the native window is set up
  correctly, so that's not something we need to handle here."
- [KHR] https://docs.vulkan.org/refpages/latest/refpages/source/VkCompositeAlphaFlagBitsKHR.html : `OPAQUE` = "alpha
  component ... is ignored in the compositing process"; `INHERIT` = "the application is responsible for setting the
  composite alpha blending mode using native window system commands", otherwise "a platform-specific default will be
  used".

**D2. What the Windows platform plugin does for an alpha Vulkan window ("native window set up correctly").**
[SRC] QTBASE `src/plugins/platforms/windows/qwindowswindow.cpp`: `windowIsAccelerated()` is true for
`VulkanSurface`; in the style-update path (`setWindowFlags`-time code, the lines around `applyBlurBehindWindow`) when
`isAccelerated && format().hasAlpha()` Qt calls `DwmEnableBlurBehindWindow(hwnd, ...)` with an empty-region blur
(`DWM_BB_ENABLE | DWM_BB_BLURREGION`, `CreateRectRgn(0, 0, -1, -1)`), the long-standing way to make DWM honour
per-pixel alpha of a flip-model surface; the same call is repeated in `handleCompositionSettingsChanged`.
`setWindowLayered` adds `WS_EX_LAYERED` for frameless windows with alpha. So the translucent route Qt itself uses is:
requested format with alpha + (frameless) + that DWM call, with `compositeAlpha` as chosen in D1. The window class
creation also has a path with `WS_EX_NOREDIRECTIONBITMAP` for some flip-model cases (`qwindowswindow.cpp`, window
creation); I did not trace when it applies.
Everything above is Qt's code path for OpenGL, Vulkan and D3D alike. Whether the result is visibly see-through on
NVIDIA, AMD and Intel with Vulkan on the development machine is not a fact I can source: it is the proof's job
(N0.6's translucent box).

**D3. What drivers report on Windows.**
- [3RD] https://vulkan.gpuinfo.org/listsurfacecompositealphamodes.php?platform=windows (community-submitted
  reports, all vendors together, no vendor split on that page; read 12 Nov 2026): OPAQUE supported 94.55 percent,
  PRE_MULTIPLIED 33.27, INHERIT 19.92, POST_MULTIPLIED 6.77 of reported Windows devices. Announcement of the listing:
  https://saschawillems.de/blog/2023/03/04/new-surface-data-listings-for-the-vulkan-database/ .
- [SRC] Qt's NVIDIA statement above (OPAQUE only, transparency still works) is the only per-vendor primary
  statement found. No vendor document (NVIDIA, AMD, Intel) stating `supportedCompositeAlpha` on Windows was found.
  The harness should log `supportedCompositeAlpha` and the chosen mode per GPU, per window, as proof output.

**D4. Does Qt Quick on Vulkan support a `QSurfaceFormat` alpha at all?** By source, yes (D1: the premultiplied flag is
keyed on `requestedFormat().alphaBufferSize()` for every backend including Vulkan). The Qt Quick scenegraph
documentation pages fetched (https://doc.qt.io/qt-6/qtquick-visualcanvas-scenegraph-renderer.html) say nothing about
alpha with Vulkan. (Not checked here: that the window's clear colour must be transparent too; the Studio window's
existing setup, `ui/studio/surface.py:181`, is the project's reference.) Qt 6.12 has no system-backdrop API (plan text); Mica/Acrylic stays a project-owned
`DwmSetWindowAttribute`.

---

## E. Validation layers with an imported device

**E1. How Qt enables them.**
- [DOC] https://doc.qt.io/qt-6/qquickgraphicsconfiguration.html `setDebugLayer` (since 6.5): "With Vulkan, Qt tries
  to enable the standard validation layer on the VkInstance." "With Vulkan, the instance is created once and shared by
  all windows, so enabling validation affects every window." Equivalent to `QSG_RHI_DEBUG_LAYER`.
- [SRC] QTDECL `qsgrhisupport.cpp`, `QSGRhiSupport::createRhi`: `if (debugLayer)
  QVulkanDefaultInstance::setFlag(QVulkanDefaultInstance::EnableValidation, true)`. This flag only affects
  `QVulkanDefaultInstance`, which `prepareWindowForRhi` does **not** use when the application has set its own
  instance. [DERIVED] with our own instance `QQuickGraphicsConfiguration::setDebugLayer()` does nothing for Vulkan, and
  the config is ignored with an imported device anyway (A1). The layers are ours to enable on our instance.
- `QSG_RHI_DEBUG_LAYER` is an environment variable (QTDECL `qquickgraphicsconfiguration.cpp` reads it with
  `qEnvironmentVariableIntValue`). **The project forbids environment-variable flags, so the harness enables layers in
  code and never sets that variable.** Qt's other Vulkan environment variables (`QT_VULKAN_INSTANCE_LAYERS`,
  `QT_VULKAN_INSTANCE_EXTENSIONS`, `QT_VULKAN_DEVICE_EXTENSIONS`, `QT_VK_PHYSICAL_DEVICE_INDEX`) are likewise not to
  be used, and note that Qt reads them itself if they happen to be set in the shell: the harness records that none are
  set.

**E2. How the harness enables them in code.**
- Route (i), Qt creates the instance: `QVulkanInstance::setLayers({"VK_LAYER_KHRONOS_validation"})` before `create()`
  ([DOC] qvulkaninstance.html; unsupported layers are dropped silently, so the harness must check
  `layers()` after `create()` and fail closed if the validation layer did not load).
- Route (ii), we create the instance: put `VK_LAYER_KHRONOS_validation` in `enabledLayerNames`, then still call
  `QVulkanInstance::setLayers()` and `setExtensions()` with the same lists (A3) so Qt's redirect and `extensions()`
  match. Synchronization validation (needed by D9 test iv) is switched on in code with a `VkValidationFeaturesEXT`
  chained on `VkInstanceCreateInfo` carrying `VK_VALIDATION_FEATURE_ENABLE_SYNCHRONIZATION_VALIDATION_EXT`
  ([KHR] https://docs.vulkan.org/refpages/latest/refpages/source/VkValidationFeaturesEXT.html and
  https://docs.vulkan.org/refpages/latest/refpages/source/VkValidationFeatureEnableEXT.html , extension
  `VK_EXT_validation_features`), or with `VkLayerSettingsCreateInfoEXT` from `VK_EXT_layer_settings`
  ([KHR] https://docs.vulkan.org/refpages/latest/refpages/source/VkLayerSettingsCreateInfoEXT.html ). `QVulkanInstance`
  offers no `pNext` hook, so **only route (ii) can turn synchronization validation on without a settings file or an
  environment variable** (the layer's file-based settings are located through an environment variable).
- Messages: [DOC] qvulkaninstance.html: with `VK_EXT_debug_utils` enabled, debug output goes to `qDebug()` by default;
  `installDebugOutputFilter(DebugUtilsFilter)` (since 6.5) sees every message and can be used to count validation
  errors and fail the run; do not set `NoDebugOutputRedirect`. [SRC] Qt itself installs a filter in
  `QRhiVulkan::create` (`qvk_debug_filter`) hiding two known false positives: "Mapping an image with layout ..." and
  `VUID-VkDescriptorSetAllocateInfo-descriptorPool-00307`. The harness's counter must not hide more than that.
- The validation layer is part of the Vulkan SDK or a layer package, not of the OS driver. The GitHub-built module
  workflow (N0.9) is unlikely to have it installed, and the lead's machine must: record this as a precondition of
  the layer-clean gates, and have the harness report "layer not loaded" as a failure, not a pass.
- Debug markers and GPU timestamps: [SRC] `createRhi` reads `isDebugMarkersEnabled()` and `timestampsEnabled()` from
  the configuration (still honoured with an imported device, because `createRhi` reads them before the import
  branch), needed for D9's GPU-time medians (`QRhi::EnableTimestamps`).

---

## F. Findings that change the plan or D6 / D9

1. **D9 point 4 is unsound as written for sampling.** Qt's frame submit waits on our semaphores at
   `COLOR_ATTACHMENT_OUTPUT` only, with binary semaphores, and the list is one-shot (B2). A job result that the same
   frame's shaders sample is not protected by it. The exception route needs a different gate, or it is limited to
   consumers at colour output. (Does not touch the default route, point 3.)
2. **D6 needs one added requirement:** our `VkDevice` must enable the feature set Qt's capability flags are derived
   from (A6.2). With feature bits settled by source, point 3's "Unverified" can be closed and the proof's "record
   which features Qt's own device has enabled" becomes a log-and-compare.
3. **D6 point 1 gains two obligations:** `setApiVersion(1,2)` on the `QVulkanInstance` (without it QRhi treats the
   device as 1.0, A4) and `QVulkanInstance::resetDeviceFunctions()` after our `vkDestroyDevice` (A6.3).
4. **D9 point 3 needs the family rule:** job outputs created by QRhi are exclusive-ownership and QRhi never records
   a family transfer (C3), so the first proof uses a job queue in the same family; a different family forces raw
   concurrent resources.
5. **`QQuickGraphicsConfiguration::setDebugLayer` and `deviceExtensions` are inert** for our own instance and
   imported device (E1, A6): validation and extra device extensions are entirely ours.
6. **Teardown:** the device outlives the `QQuickWindow` object, not just visibility, and the job queue is invisible
   to Qt's wait-idle (A7). Both are consistent with D6 point 4's "windows, then devices, then the instance" and add
   the `vkDeviceWaitIdle` step plus the job quiesce before it.
7. `endOffscreenFrame` is not synchronous without a readback; `QRhi::finish()` is the completion edge (C2). The spike's
   comment should not be read as a rule.

## G. Unconfirmed (state each as unknown in the proof's output until measured)

- U1. Whether a second QRhi on the same VkDevice, own queue, own thread works without validation errors or Qt
  asserts (nothing forbids it; nothing documents it).
- U2. Whether the job QRhi works on a compute-only or transfer-only family (import does not check flags).
- U3. Memory visibility of job writes after a host fence wait, before Qt's queue samples them (C4); the answer is
  whichever synchronization validation reports, and may require an explicit barrier or a semaphore we control.
- U4. Whether the translucent Vulkan window is see-through on each vendor, and which `supportedCompositeAlpha` each
  reports on the development machine; Qt's statement covers NVIDIA only, and only as a code comment.
- U5. The Windows `WS_EX_NOREDIRECTIONBITMAP` path (when Qt uses it for Vulkan) and its interaction with the DWM
  backdrop call; D7 point 8's three routes decide it by trial.
- U6. Behaviour across sleep/wake and DPI change with an imported device (the lead's Display 1 run): `VK_ERROR_DEVICE_LOST`
  handling is Qt's (`QRhi::isDeviceLost`) but device re-creation on our side after a lost device is ours to design;
  not researched here.
- U7. Line-level behaviour of the exact `v6.12.0` tag; sources read were the `6.12` branch head.

---

## H. What to build first (the order for the harness; no code)

Principle: put the cheapest, most decisive unknowns first and keep each step's output a log line the next step reads.

1. **Capture facts without changing anything (hours).** Enumerate the GPU(s): device name, API version, queue
   families (flags, counts, `vkGetPhysicalDeviceWin32PresentationSupportKHR` per family), `supportedCompositeAlpha`
   per vendor once a surface exists, the feature set Qt's own device enables (from the `QRhiVulkanNativeHandles` of a
   Qt-created QRhi plus `vkGetPhysicalDeviceFeatures2`). Print `QT_VULKAN_*` and `QSG_*` environment variables found
   set (must be none). Resolves D3 and the "feature bits" record; settles whether a second queue exists (N0.6 box 3,
   with the forced-absence negative control as a command-line switch, not an environment variable).
2. **Instance and layers first, before any device.** Create the `VkInstance` in the module (route ii) with
   validation, synchronization validation and `VK_EXT_debug_utils`; adopt into `QVulkanInstance` with matching
   `setExtensions`/`setLayers`/`setApiVersion(1,2)`; install a debug filter that counts errors and fails the run;
   fail closed when the layer is not loaded. Nothing after this step is trusted without it. (Risk: layer
   availability on the lead's machine and the build workflow, E2.)
3. **Our device, feature set equal to Qt's.** One physical device, one family for graphics+present (found
   without a window), the extensions of A5 intersected with what exists, all supported features minus the two
   robustness ones, queue count: graphics queue plus the job queue (same family first). Compare the enabled set with
   the step-1 record and log both. (Risk: A6.2, wrong feature set gives wrong capability flags rather than a failure.)
4. **Qt Quick on our device, offscreen first.** Reuse `QuickOffscreenSession`: add `setGraphicsDevice(
   fromDeviceObjects(...))` before `initialize()`, same scene, readback, pixel-compare with the same session on Qt's own
   device (the spike already has `image_stats` checksums for this). Offscreen render control needs no present
   support, so this isolates the device import from the swapchain. Teardown in the order of A7, validation clean.
5. **A real hidden window next** (`QQuickWindow` with `setVulkanInstance`, `setGraphicsDevice`, shown only as far
   as the lead permits): swapchain create, resize, destroy, with the present queue check, then the translucent
   case (alpha format, `compositeAlpha` logged, DwmEnableBlurBehind as Qt does, then the project-owned backdrop
   call early as the plan says). Log each driver's `supportedCompositeAlpha` and whether the desktop shows through
   (this part needs a visible pixel sample, the lead's Display 1 run). (Risk: U4, U5.)
6. **The job thread, uploads first.** Job QRhi on the job queue (same family) with `beginOffscreenFrame` /
   `finish()`; one upload job and one compute job (the 4K edge-field body, same shader as the in-frame form);
   publish by atomic latch; render the fixed scene and read the generation at frame start. First prove correctness:
   hashed outputs identical in-frame vs job (D9 ii), no Python thread state (iii), synchronization validation clean
   (iv). (Risk: U1, U3.)
7. **Then the measurements.** GPU time median, p90, p99 and late frames, in-frame versus job (D9 i), with
   `QRhi::EnableTimestamps` on Qt's side and conditions recorded; retirement in the middle of a job (v); a minute at
   rest with a wake-up counter on the job thread (vi). (Risk: none beyond the verdict itself: if there is no gain the
   job thread stays for uploads, as D9 already says.)
8. **Only if needed, the semaphore exception.** Test `setQueueSubmitParams` with a job-signalled binary semaphore,
   including a case where the frame samples the job output, to confirm B2.2 under synchronization validation. Treat
   as optional: the default route does not need it.
9. **Last, the different-family case** (U2) if the machine has a compute-only family: concurrent-sharing raw resources
   imported by `createFrom`, and the ownership rule of C3.

Risks, summarised: validation layer availability (step 2); feature-set mismatch silently changing capability flags
(step 3); present-capable family choice (step 5); the host-fence visibility question (step 6); vendor-dependent
transparency (step 5); Qt behaviour not covered by documentation in step 6 (two QRhi on one device).

---

## I. Measured under validation: whose each finding is (N0.7, 12 Nov 2026; added by the N0.7 agent)

Measured with the Khronos validation layer and synchronisation validation (the lead's install, found through
`--layer-path`), Qt 6.12.0 (PySide6's), NVIDIA 617.42. Every message is kept with its phase, the instance that
reported it (ours, or the validated reference instance on which Qt creates its own device), the calling thread and
the caller's stack (module+offset); Qt's QRhi names its objects (debug markers) and ours are named. Evidence: build
round 2 (`71cac383`), `.artifacts/evidence/native_core/n06/20261112_n06_{device,lifecycle,translucent}_attrib/`
and `n07/20261112_n07_{jobs,rest,measure,retire}_validated/`. Sources read at the tag `v6.12.0` this time (the
module's Qt), and the `6.12` head where they differ. The harness classifies these four (`run_n06.py`
`QT_DEFECTS`, `classify_group`) and excuses them only where it says; anything else fails `validation_clean`.

**A. `VUID-VkImageCreateInfo-initialLayout-12478` (PREINITIALIZED with OPTIMAL tiling): Qt's QRhi, fixed after
6.12.0.** Every QRhi texture on Vulkan: callers `Qt6Gui.dll` (QRhi) from our `createOffscreenTarget`, from the job
service's bodies, on both devices alike. [SRC] `v6.12.0` `QVkTexture::create`: `imageInfo.tiling =
VK_IMAGE_TILING_OPTIMAL; imageInfo.initialLayout = VK_IMAGE_LAYOUT_PREINITIALIZED;` and `prepareCreate` tracks
`usageState.layout = VK_IMAGE_LAYOUT_PREINITIALIZED`; the `6.12` head has `UNDEFINED` with the comment "Must be
UNDEFINED (and not PREINITIALIZED) with optimal tiling". Harmless on NVIDIA (the content is undefined either way) but
invalid usage. Route: the next PySide6/Qt patch release that carries the head's line (D11's upgrade reruns every
gate); until then excused everywhere, by id and the Qt caller only. The native core does not work around it (it
would mean creating every image raw); D9's slots already read the true initial layout from `nativeTexture()`.

**B. `SYNC-HAZARD-WRITE-AFTER-WRITE` at `vkCmdBeginRenderPass` (a target rendered every frame): Qt's QRhi, triggered
by a target that does not keep its contents.** On Qt's own device and ours alike (device round, lifecycle round);
callers `Qt6Gui.dll` (QRhiVulkan's submit) from `Qt6Quick.dll`. [SRC] `QRhiVulkan::createOffscreenRenderPass`
(head and tag): without `PreserveColorContents` the colour attachment's `initialLayout` is `UNDEFINED` and no
`VK_SUBPASS_EXTERNAL` dependency is added (a comment says the barriers come from resource tracking and
`activateTextureRenderTarget`); the tracker's write-after-write barrier ends at `COLOR_ATTACHMENT_OUTPUT`, which does
not order the render pass's own layout transition. Harness: every host target now keeps its contents (the scene
covers it, pixel-identical); the device round keeps a pair of non-preserving hosts as evidence, where B must appear
on both devices and only there. Route for the native core: its own texture render targets are created with
`PreserveColorContents` and primed once (C); a target that must be cleared is cleared by the core's first draw or a
clear pass, not by `UNDEFINED`. Qt Quick's own layers (`layer.enabled`, `ShaderEffectSource`) would show B; none
exists in the native surfaces. Worth a Qt bug report with the one-line fix (an external dependency with
`srcAccessMask` `COLOR_ATTACHMENT_WRITE`).

**C. `SYNC-HAZARD-READ-AFTER-WRITE` at `vkCmdBeginRenderPass` with `loadOp LOAD` (the first frame of a preserving
target): Qt's QRhi.** On both devices, once per target. [SRC] `v6.12.0` `toVkAccess(TexColorOutput)` returns
`VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT` only, and `recordTransitionPassResources` sets `barrier.dstAccessMask` from it,
so any transition to `COLOR_ATTACHMENT_OPTIMAL` does not make the image visible to the pass's load (a read). It
happens on a target's first frame and again on the first frame after any other use of it: build round 3's device
round showed it once more on our device's host, on the frame after the negative control's readback (the readback
had moved the target to `TRANSFER_SRC_OPTIMAL`; the host on Qt's own device, which reads back only on its last
frame, stayed clean). Harness fix (ours, `quick_offscreen.cpp` `primeColorTargetForLoad`): at creation and after
every readback of the target, in an offscreen frame of the same QRhi, the harness records the transition itself
(`beginExternal`, a barrier to `COLOR_ATTACHMENT_OPTIMAL`, first scope `ALL_COMMANDS`/`MEMORY_WRITE`, second scope
`COLOR_ATTACHMENT_READ | WRITE`), then `setNativeLayout`. Never excused. The native core's route: each of its render
targets is primed at creation, and a target read back or sampled is primed again before its next loading pass (or
the readback reads a copy).

**D. `SYNC-HAZARD-WRITE-AFTER-PRESENT`, `SYNC-HAZARD-WRITE-AFTER-READ` and `UNASSIGNED-non-acquired-swapchain-image-used`
(real windows): Qt Quick's `grabWindow` on Vulkan, with Qt's QRhi.** Only in the translucent round's grab phases, on
Qt's own device and ours alike; every show, present, backdrop and teardown phase is clean. Callers `Qt6Gui.dll`
from `Qt6Quick.dll` on `QSGRenderThread`. [SRC] `QTDECL` `QSGRhiSupport::grabAndBlockInCurrentFrame` reads back the
swapchain image and calls `rhi->finish()` inside the frame; `v6.12.0` `QRhiVulkan::finish` submits the swapchain
frame's command buffer, which already rendered into the acquired image, with no wait semaphore
(`endAndSubmitPrimaryCommandBuffer(cb, VK_NULL_HANDLE, nullptr, nullptr)`), so the acquire semaphore is never waited
on before the image is written. Route: the product never grabs a Vulkan window (only tools and the hidden harness
do); the core reads pixels back from its own targets, never from the swapchain. Excused only in grab phases.

**E. `QRhiTexture::sRGB` is ignored by QRhi's OpenGL backend for uncompressed formats: Qt 6.12.0's (N0.3 run 1,
added 12 Nov by the N0.3 agent).** Not a validation message (OpenGL has none here) but a Qt behaviour the convention
scenes measured: an RGBA8 texture created with the `sRGB` flag samples on OpenGL as the raw byte over 255 (max
difference 3e-8 across all 256 values, identical to the unflagged copy), while Vulkan, D3D11 and D3D12 decode it
(bit-identical to each other, 8 significant bits; evidence
`.artifacts/evidence/native_core/n0_3/20261112_n03_scenes_reanalysed/`). A hidden probe through PySide6's QRhi read
`GL_TEXTURE_INTERNAL_FORMAT` = `GL_RGBA` (0x1908) for the flagged texture and for the unflagged one. [SRC] `v6.12.0`
`src/gui/rhi/qrhigles2.cpp`: `toGlTextureFormat(format, caps, ...)` takes no flags (RGBA8 gives `GL_RGBA8` or `GL_RGBA`),
and the flag is read only in `toGlCompressedTextureFormat` (the BC, ETC2 and ASTC sRGB variants); `QGles2Texture::create`
allocates uncompressed storage at once with that format. No excuse id is needed (nothing is reported); the route is
decision F4 (`Native_Core_P3_Decisions.md`, N0.3): the one sRGB asset is plain RGBA8 decoded in its shader by the
include's `srgbToLinear` on every backend, so nothing relies on the flag. Worth a Qt bug report (`GL_SRGB8_ALPHA8` for
RGBA8 with the flag, as the other backends do).

**F. Qt's thread pool started from the job thread (owners round): ours, through QPainter.** (Lettered E until 12 Nov,
when Qt's sRGB behaviour took E beside Qt's A to D.) The extra +4 handles and
+1 thread of the retire round were `Qt6Core.dll` threads named "Thread (pooled)" (+1 Thread, +1 IoCompletion,
Events), appearing in the step where the job thread generated a photo (service start: the edge field's photograph;
the upload job). Reproduced in a plain process: QPainter's antialiased fills of more than 2^17 pixels into a
non-premultiplied image (RGBA8888) start four pooled threads; aliased fills, small fills or premultiplied targets do
not. [SRC] `v6.12` `qdrawhelper.cpp` `QT_THREAD_PARALLEL_FILLS` (`blend_color_generic` and the other generic blends
split spans across `QGuiApplicationPrivate::qtGuiThreadPool()` from `MinParallelSolidPixels = 1 << 17`). The
threads persist while reused (QThreadPool's default expiry is 30 s idle), so the count plateaus at the pool's peak; not a leak, but a job
thread must use no other thread. Fix: the harness's photo generator writes pixels itself. Rule for the native core:
no QPainter and no QImage conversion on the job thread or the render thread.

**Conditions seen.** A third-party graphics hook, `we-graphics-hook64.dll`, is injected into the Python process and
sits in the call chain of `vkCmdBeginRenderPass` (it shows above `Qt6Gui.dll` in finding C's stacks); it owns none
of the findings, but it is part of every measurement on this machine and is recorded as such. `windhawk.dll` is
injected too (one thread). The one-time thread step in the first cycles of the owners and retire rounds (+23
threads) is numpy's OpenBLAS pool (`libscipy_openblas64_*.dll`), started by the harness's own census on its first
numpy use, plus one `WINMM.dll` timer thread; both before the baseline, neither ours in the product sense.

**U1 and U3 under validation.** No message names the second QRhi, the job queue or the latch path in the validated
jobs, rest, measure and retire rounds: a second QRhi on our VkDevice on the second queue is clean (U1), and the job's
writes followed by its host-side completion edge and Qt's queue reading the slot (copy and readback) raise no
synchronisation hazard (U3). Build round 3 (`3bd851cd`, C primed): the validated jobs, retire and rest rounds have
no message but A (10, 60 and 10, all QRhi texture creations).

---

## J. What a host's create-and-destroy cycle keeps, by owner (N2.2 lifecycle, 13 Nov 2026; added by the N2.2 agent)

Measured on the product module (`native/core`, build of `14b04b15`) through `rendering.native`, Qt 6.12.0, RTX 4090,
NVIDIA 617.42, one process per graphics API, counters after every cycle (`process_counters`: handles, USER objects,
threads, private bytes). Round 2 of `native/core/python/host_check.py` failed three lifecycle checks, each with an
absolute threshold and Qt-only windows as the only reference (`.artifacts/evidence/native_core/n2_2/20261113_n22_hosts/`).
Each was attributed with a per-API control doing the same thing without the core
(`.artifacts/evidence/native_core/n2_2/20261113_n22_lifecycle_attribution/`: `attrib.py` and one JSON per API, 24
cycles per kind). None is the core's.

**J1. OpenGL, Qt's threaded render control keeps 2 process handles and 1 USER object per create and destroy.** Qt alone,
with no native core in the process: a `QQuickRenderControl` prepared for a QThread, initialised there (QRhi on OpenGL
creates its context on that thread), invalidated there, its context handed back to the GUI thread and the control
deleted on the GUI thread (the order the threaded render-control pattern requires). Over 24 cycles handles rise +2.0 per
cycle and USER objects +1 per cycle, exactly linear, with or without frames (Qt alone threaded, no frames: 492 to 538;
with 5 frames: 550 to 596). The same render control on the GUI thread: 0 and 0 (481 flat). The core's hidden host
gives the same numbers (threaded: +2.0 and +1; with `threaded=False`: 0 and 0), and so do its no-frame, plain and full
cycles. Qt Quick windows with Qt's own threaded render loop keep no handle (0 per cycle) and the same +1 USER object
per window on OpenGL whether the core is attached or not. Whether the 2 handles and the USER object are Qt's or the
OpenGL driver's is not separated (a context made current on a thread that then exits, its fallback surface); neither is
the core's. Consequence: a hidden host on OpenGL is created once and kept (the product's hidden hosts are long-lived:
the Studio's preview, capture tools), never one per use; at 10,000 USER objects per process that is the bound.

**J2. D3D12, the runtime and driver commit private bytes in 8 MiB steps for the first render controls of a process, then
plateau.** Qt alone on the GUI thread, first in its process: 865 to 948 MiB over 16 cycles in 8 MiB steps, flat
afterwards; Qt's threaded control after it released about 145 MiB (to 803) and stayed flat; the core's plain hidden
host after that rose back to 960 to 968 MiB and stayed flat for its last 8 cycles; its full cycle then drifted down
(1007 to 984 over 24 cycles). Over 72 cycles of the core the process stayed within 1009 MiB. Handles and USER objects
flat throughout. Round 2's `hidden_host` failure (956 to 989.6 over 8 cycles, flattening at 989.2, 989.3, 989.6) was
this pool's first fill: the hidden host was the first render control in that process.

**J3. Vulkan, private bytes move by whole 32 and 64 MiB blocks, and NVIDIA keeps 3 handles per VkDevice.** Every kind,
the Qt-only window included: handles +3.0 per cycle (one device per cycle, ours or Qt's; N0.6 round 5's finding), and
private bytes alternating by about 64 MiB from one cycle to the next (Qt-only window over 24 cycles: 353, 419, 354,
419, ...; range 92 MiB, slope -0.35; `.artifacts/evidence/native_core/n2_2/20261113_n22_vulkan_lifecycle_24/`). The core's hidden host over 144 cycles of six kinds stays inside a band (about
1050 to 1250 MiB) and returns to its troughs (about 1080 MiB) after 130 cycles; no kind has a trend in its troughs.
Round 2's `window_with_core` failure was 8 cycles sampled from that alternation (first-third minimum 1114.6, last
1146.1); over 24 cycles its slope is +0.15 MiB per cycle against the control's -0.35. The resolution of process
counters on Vulkan is therefore one 32 MiB block: a smaller per-host leak would not show there, which is why the core's
own objects are counted exactly (the probe pass's live resources return to 0 at every release, checked in every cycle).

**J4. numpy's first import costs the harness about 750 MiB of private bytes and 23 threads** (12 to 759 MiB and 5 to
28 threads in a plain interpreter; N0.7's OpenBLAS pool note). Any harness that imports numpy partway through a series
sees it as one step; `host_check.py` imports it in its first round, before any lifecycle reading.

**The lifecycle check since (`host_check.py`, `round_lifecycle`).** Each kind of the core runs right after its control,
in the same process state, after 8 warm-up cycles, then 16 measured: the window with the core against the Qt-only
window; the hidden host against Qt's threaded render control in the same sequence (on Vulkan, where PySide6 has no
`QVulkanInstance` to give a render control, against the Qt-only window, which also makes one device per cycle). The
core may add no handle and no USER object per cycle over its control (tolerance 0.25), no trough growth of private bytes
over the control's (tolerance the control's own range on that API, at least 16 MiB), and no thread. Rerun on the same
build: PASS on OpenGL, Vulkan (validation clean, A excused 10 times), D3D11 and D3D12
(`.artifacts/evidence/native_core/n2_2/20261113_n22_hosts_controls/`).

**J5. D3D11 and D3D12 windows stop presenting while the display shows nothing; OpenGL and Vulkan windows do not (N2.6
build round 1, 13 Nov 2026; added by the N2.6 agent).** Every D3D window round of host_check, composite_check and
timer_check got 2 frame edges and no more. In a plain process with the native module never loaded, an off-screen Qt
Quick window (the harnesses' invisible pattern, content animating) presented 2 frames in 2 s on D3D11 and on D3D12 and
139 on OpenGL, on the same machine within the same minute (one monitor attached, desktop unlocked, no screen saver
running). The likely cause is DXGI reporting the output occluded (the display powered down) and Qt's D3D swapchains
then pausing (*unverified*: not read in Qt's source, the monitor's power state not queried); the other two backends keep
going. Either way it is the environment's, not the core's: the D3D window rounds passed on the N2.2 and N2.4 builds when
the display was on. Since then every window round is preceded by that control
(`host_check.qt_alone_window_frames`, at least 10 frames in 1 s); fewer puts "environment" first in the verdict
(`.artifacts/evidence/native_core/n2_2/20261113_n22_environment_recheck/`).
