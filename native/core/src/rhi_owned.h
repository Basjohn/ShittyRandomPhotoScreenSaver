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
// The contract (checkpoint audit 11 L1): a wrapper is retired before its QRhi, always. In Qt 6.12 a resource registers
// with its QRhi only in its backend's create(), and ~QRhiImplementation forgets only registered ones; deleteLater() calls
// its QRhi. So a wrapper that was never created, or whose create() failed (a failed partial build kept until its owner's
// retirement), and is retired after its QRhi went dereferences the freed QRhi: a use-after-free (a plain delete was safe
// there, deleteLater is not). Every owner releases what it holds on a QRhi at that QRhi's scene graph invalidation (its
// node's destruction or the frame driver's release), so nothing outlives it; an owner that keeps objects across a node
// (decided by QRhi pointer) must release them at the invalidation too. The count below proves it: the wrappers live per
// QRhi, read by the hidden host right after its scene graph's invalidation (device_loss_check.py: zero).
//
// RhiOwned<T> owns one QRhiResource like std::unique_ptr<T> (get, ->, *, bool, reset, release, move, swap) and retires it
// with deleteLater(), for every QRhiResource the core holds (QRhi itself is no resource and keeps std::unique_ptr). A
// raw Vulkan object the core makes itself is not QRhi's: it goes to the device's deferred queue (vulkan_context.h,
// deferRawVulkanDestroy).
#pragma once

#include <rhi/qrhi.h>

#include <cstddef>

namespace srpss_core {

// L1's count (rhi_owned.cpp): the wrappers live per QRhi (the one their resource was made on). Any thread, under one
// mutex, at a resource's adoption and retirement only (never per frame at rest).
void rhiOwnedAdopted(const QRhi *rhi);
void rhiOwnedRetired(const QRhi *rhi);
int rhiOwnedLive(const QRhi *rhi); // the wrappers live on `rhi`
int rhiOwnedLiveTotal();           // on every QRhi

template <typename Resource>
class RhiOwned
{
public:
    RhiOwned() noexcept = default;
    RhiOwned(std::nullptr_t) noexcept {}
    explicit RhiOwned(Resource *resource) { adopt(resource); }
    RhiOwned(RhiOwned &&other) noexcept : m_resource(other.m_resource), m_rhi(other.m_rhi)
    {
        other.m_resource = nullptr;
        other.m_rhi = nullptr;
    }
    RhiOwned &operator=(RhiOwned &&other) noexcept
    {
        if (this != &other) {
            retire();
            m_resource = other.m_resource;
            m_rhi = other.m_rhi;
            other.m_resource = nullptr;
            other.m_rhi = nullptr;
        }
        return *this;
    }
    RhiOwned &operator=(std::nullptr_t) noexcept
    {
        retire();
        return *this;
    }
    RhiOwned(const RhiOwned &) = delete;
    RhiOwned &operator=(const RhiOwned &) = delete;
    ~RhiOwned() { retire(); }

    Resource *get() const noexcept { return m_resource; }
    Resource *operator->() const noexcept { return m_resource; }
    Resource &operator*() const noexcept { return *m_resource; }
    explicit operator bool() const noexcept { return m_resource != nullptr; }

    // The resource held goes (deleteLater) and `resource` is held instead (none: nullptr).
    void reset(Resource *resource = nullptr)
    {
        if (resource == m_resource)
            return;
        retire();
        adopt(resource);
    }
    // No longer held (nor counted): the caller owns it.
    Resource *release() noexcept
    {
        Resource *resource = m_resource;
        if (resource)
            rhiOwnedRetired(m_rhi);
        m_resource = nullptr;
        m_rhi = nullptr;
        return resource;
    }
    void swap(RhiOwned &other) noexcept
    {
        Resource *resource = m_resource;
        QRhi *rhi = m_rhi;
        m_resource = other.m_resource;
        m_rhi = other.m_rhi;
        other.m_resource = resource;
        other.m_rhi = rhi;
    }

    friend bool operator==(const RhiOwned &owned, std::nullptr_t) noexcept { return owned.m_resource == nullptr; }
    friend bool operator==(std::nullptr_t, const RhiOwned &owned) noexcept { return owned.m_resource == nullptr; }
    friend bool operator!=(const RhiOwned &owned, std::nullptr_t) noexcept { return owned.m_resource != nullptr; }
    friend bool operator!=(std::nullptr_t, const RhiOwned &owned) noexcept { return owned.m_resource != nullptr; }

private:
    void adopt(Resource *resource)
    {
        m_resource = resource;
        m_rhi = resource ? resource->rhi() : nullptr; // read now: the resource's QRhi may forget it later
        if (resource)
            rhiOwnedAdopted(m_rhi);
    }
    void retire() noexcept
    {
        Resource *resource = m_resource;
        if (!resource)
            return;
        const QRhi *rhi = m_rhi;
        m_resource = nullptr;
        m_rhi = nullptr;
        rhiOwnedRetired(rhi);
        resource->deleteLater();
    }

    Resource *m_resource = nullptr;
    QRhi *m_rhi = nullptr; // the QRhi the resource was made on (the count's key)
};

} // namespace srpss_core
