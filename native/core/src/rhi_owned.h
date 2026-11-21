// How the core owns a QRhi resource (N3.6, Current_Plan.md item 8b, the release-timing box; research
// Docs/Future_Work/Native_Core_QRhi_Research_N3.md section 12): retirement calls deleteLater() at once, never delete.
//
// QRhiResource::deleteLater() deletes the C++ object now outside a frame and at the end of the current frame inside one,
// so an object retired while the frame's recorded commands may still name it (a content replaced or released at the
// item's sync or at the frame edge) outlives that frame's recording; destroy() and delete would free it under them. The
// native objects are QRhi's deferred releases either way: they die once the GPU is done with their last frame (two
// frames later on Vulkan, at the next frame on OpenGL; that lag is accepted, D5's budget counts it). Where no frame will
// follow (a window's scene graph invalidated, the hidden host's close, a saver exit), the frame driver calls
// QRhi::finish() at that edge, outside any frame (frame_driver.cpp), never mid-frame.
//
// RhiOwned<T> is std::unique_ptr<T> with that deleter, for every QRhiResource the core holds (QRhi itself is no
// resource and keeps std::unique_ptr). A raw Vulkan object the core makes itself is not QRhi's: it goes to the device's
// deferred queue (vulkan_context.h, deferRawVulkanDestroy).
#pragma once

#include <memory>

namespace srpss_core {

struct RhiDeleteLater
{
    template <typename Resource>
    void operator()(Resource *resource) const
    {
        if (resource)
            resource->deleteLater();
    }
};

template <typename Resource>
using RhiOwned = std::unique_ptr<Resource, RhiDeleteLater>;

} // namespace srpss_core
