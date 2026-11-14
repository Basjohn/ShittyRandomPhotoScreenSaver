# QRhi swap chain read-back on Vulkan (2026-11-14)

Question: `tools/d1_run.py` `read_back_frame` (commit 667224c1) leaves the Vulkan window black on the compositor after the first grab.
Sources, Qt `dev` (6.12 line), read on GitHub: `qtbase/src/gui/rhi/{qrhi.cpp,qrhivulkan.cpp,qrhigles2.cpp}`,
`qtdeclarative/src/quick/items/qquickwindow.cpp`, `.../scenegraph/{qsgrhisupport.cpp,qsgthreadedrenderloop.cpp,qsgrenderloop.cpp}`
(https://github.com/qt/qtbase, https://github.com/qt/qtdeclarative). The doc text quoted is the `\fn` comments in those files, as published at
https://doc.qt.io/qt-6/qrhi.html, qrhiresourceupdatebatch.html, qquickwindow.html. "Inferred" marks anything not read directly. Nothing was run.

## 1. What `readBackTexture` with an empty description does
- qrhi.cpp, `QRhiReadbackDescription()`: "The source texture is set to null by default, which is still a valid readback: it specifies that the backbuffer of the current swapchain is to be read back (current meaning the frame's target swapchain at the time of committing the QRhiResourceUpdateBatch ...)."
- qrhi.cpp, `readBackTexture`: when the swap chain "was created with QRhiSwapChain::UsedAsTransferSource, it can also be the source of the readback."
  Qt Quick's render loops always create the window swap chain with that flag (`qsgthreadedrenderloop.cpp:923`, `qsgrenderloop.cpp:520`: "may be used in a grab").
- The `readBackTexture` call only queues an op. The work happens when the batch is committed (`cb->resourceUpdate` or `cb->endPass(u)`).
- Vulkan, `enqueueResourceUpdates` (qrhivulkan.cpp ~4930-5062), at commit:
  - rect = swap chain pixel size; format from `swapchainReadbackTextureFormat`;
  - if the image's `lastUse != ScImageUseTransferSource`: barrier PRESENT_SRC_KHR -> TRANSFER_SRC_OPTIMAL (MEMORY_READ -> TRANSFER_READ, COLOR_ATTACHMENT_OUTPUT -> TRANSFER), `lastUse = ScImageUseTransferSource`; it warns "Attempted to read back undefined swapchain image content ... (do a render pass first)" if `lastUse` is not Render;
  - records `CopyImageToBuffer` into a host-visible staging buffer, tagged `activeFrameSlot = currentFrameSlot`.
  So the copy is recorded at the commit point, after the render pass (its final layout is PRESENT_SRC), and the image is left in TRANSFER_SRC.
- `QRhiVulkan::endFrame` (~2940) puts it back: "was used in a readback as transfer source, go back to presentable layout" (TRANSFER_SRC -> PRESENT_SRC), then submits and `vkQueuePresentKHR`. Read-back plus present in one frame is a designed path.
- The bytes reach `result.data` in `finishActiveReadbacks()`: forced by `finish()`, or unforced in `prepareNewFrame` when `currentFrameSlot == activeFrameSlot` (two frames later; 2 frames in flight). qrhi.cpp: guaranteed complete when "finish() has been called; or, at least N frames have been submitted ... and the recording of a new frame has been started, where N is the resource limit value returned for QRhi::MaxAsyncReadbackFrames."

## 2. Is `resourceUpdate` valid in `afterRendering`?
- qquickwindow.cpp `renderSceneGraph`: `context->renderNextFrame(renderer); emit q->afterRendering();`. Doc: "the render pass (or passes) are already recorded at this point and it is not possible to add more commands within the scenegraph's pass ... This signal has therefore limited use in Qt 6."
- The frame is still open (`beginFrame` done, `endFrame` not yet), the pass is over, so a resource update on `currentFrameCommandBuffer()` is valid (QRhi only forbids it inside a pass; `QRhi::finish()` doc: "Can be called inside and outside of a frame, but not inside a pass"). Qt's own grab does the same (section 4).
- `afterRenderPassRecording` is inside the pass: resource updates there are not allowed.
- There is no `beforeEndFrame` signal in 6.12: qquickwindow.cpp has only `beforeFrameBegin`, `beforeRendering`, `beforeRenderPassRecording`, `afterRenderPassRecording`, `afterRendering`, `afterFrameEnd`. `afterFrameEnd` is "emitted when the scene graph has submitted a frame ... the last signal"; the frame is over, there is no current command buffer to read back into.

## 3. `QRhi::finish()` mid-frame on Vulkan
`QRhiVulkan::finish()` (qrhivulkan.cpp ~3290-3335), inside a swap chain frame:
1. `recordPrimaryCommandBuffer`, `resetCommands`, then `endAndSubmitPrimaryCommandBuffer(cb, no fence, waitSem = imageSem if still waitable, no signal)`. The acquire semaphore is consumed here (`imageSemWaitable = false`).
2. `vkQueueWaitIdle(gfxQueue)`.
3. `ensureCommandPoolForNewFrame()` and `startPrimaryCommandBuffer(&frameRes->cmdBuf)`: the frame continues on a fresh command buffer.
4. `executeDeferredReleases(true); finishActiveReadbacks(true);`.
`endFrame` then emits the TRANSFER_SRC -> PRESENT_SRC barrier on the new buffer, submits with the frame fence and `drawSem`, and presents. Doc: "Avoid this function. One case where it may be needed is when the results of an enqueued readback in a swapchain-based frame are needed at a fixed given point."
Reading this, I found no defect (layout tracking via `lastUse`, semaphore, fence are consistent). The source does not explain the black window by itself (inferred: it is a driver or compositor consequence of the split submission and layout round trip on this path).

## 4. How Qt Quick reads back a live window
- `QQuickWindow::grabWindow` -> `windowManager->grab(this)` (qquickwindow.cpp 2866-2915). Threaded loop `WM_Grab` (qsgthreadedrenderloop.cpp ~403-418): `beginFrame; syncSceneGraph; renderSceneGraph; grabAndBlockInCurrentFrame(rhi, swapchain->currentFrameCommandBuffer()); endFrame(swapchain, QRhi::SkipPresent)`. Basic loop (qsgrenderloop.cpp ~824) is the same.
- `grabAndBlockInCurrentFrame` (qsgrhisupport.cpp 1324): `QRhiReadbackDescription(src)` ("null src == read from swapchain backbuffer"), `nextResourceUpdateBatch`, `readBackTexture`, `cb->resourceUpdate`, `rhi->finish()`. This is exactly `read_back_frame`.
- The difference: Qt Quick does it in its own extra frame, never presented (`SkipPresent`), outside the normal frame. The saver does it in the frame that is then presented. Qt Quick never presents a frame that had `finish()` called in it. This is the one structural difference.
- Offscreen grabs (`grabOffscreen`) use `beginOffscreenFrame/endOffscreenFrame` into an own texture; readbacks are complete on return (qrhi.cpp doc of `beginOffscreenFrame`).

## 5. Safe form
- Documented swap chain read-back (qrhi.cpp `readBackTexture` example): enqueue the batch in the frame, with `cb->endPass(u)` (or `resourceUpdate` after the pass), no `finish()`, take the data when it completes, `endFrame` presents as normal. One submission per frame, Qt's tested barrier pair and present.
- Vulkan: completes about 2 frames later (above). OpenGL: `ReadPixels` is a recorded command executed with the swap chain command buffer (qrhigles2.cpp ~4386); `QRhiGles2::finish()` is `executeCommandBuffer` + `glFinish` (line 2927) and touches no image layout, so the layout problem does not exist there (inferred: GL is not affected; unchecked). The non-`finish` form works on both backends unchanged.
- PySide6 6.12.0 `QRhiReadbackResult` exposes only `data`, `format`, `pixelSize` (checked in `.venv`), not the `completed` callback, so the callback form is unavailable; poll in later frames.
- `afterFrameEnd` and `beforeEndFrame` are unusable (section 2). An offscreen copy (own render target) is a larger change and does not read what is presented.

## Likely root cause (partly inferred)
`rhi.finish()` inside a frame that is then presented. It is the one step Qt Quick's own grab never combines with a present (its grab frame uses `SkipPresent`), the docs say to avoid it, and it splits the presented frame into two submissions with a `vkQueueWaitIdle` and a transfer-layout round trip on the presented image. The readback recording itself matches Qt's code. Why the compositor then shows black cannot be derived from source.

## Recommended fix for `read_back_frame` (not applied)
1. Keep `nextResourceUpdateBatch`, `readBackTexture(QRhiReadbackDescription(), result)`, `currentFrameCommandBuffer().resourceUpdate(batch)`. Remove `rhi.finish()`.
2. Keep the `QRhiReadbackResult` alive in the grab object: Qt fills it later on the render thread.
3. Do not read `result.data` in the same frame. Keep `_after_rendering` connected and on each later frame treat `result.pixelSize` valid (width and height > 0) as completion (inferred from `finishActiveReadbacks` setting size and data together; prove with a negative control that an unfinished result has an empty size). Expect it 2 frames later on Vulkan; keep calling `window.update()` until then; the existing timeout covers a stall.
4. Then build the `RawFrame` as today (`QByteArray(result.data)` share is fine), disconnect, deliver. Grab latency becomes a couple of frames (acceptable; the grab already waits for the next frame).
5. Verify on a visible Vulkan window: the compositor still shows the saver after the first grab, and a later grab matches. Then check OpenGL.
6. If it still blacks out without `finish()`, the layout round trip itself is the cause; fall back to rendering grabs into an own offscreen target (needs separate evidence).
