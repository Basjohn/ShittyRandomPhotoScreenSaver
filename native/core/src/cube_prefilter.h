// The scene probe's prefilter (ABI 42, N5.6; N4.d's Extruded Bubble half): a cube target's mip chain (scene_targets.h),
// made by the core's own shader, never generateMips (a linear blit chain on Vulkan, the driver's box on OpenGL; the lead's
// N4.d decision) and never a geometry-shader gl_Layer (D3D has none).
//
// For each level L >= 1 and each face f: one render pass into the target's stage cube of level L, face f
// (scene_targets.h stageTarget), drawing shaders/cube_prefilter.frag (rendering/quick/scene3d/probe.py's filter, tap
// for tap) from the cube's level L - 1 through a samplerCube (trilinear, seamless across faces: Vulkan always, OpenGL
// where QRhi enables GL_TEXTURE_CUBE_MAP_SEAMLESS; the proof's lookup across a face edge); then, after the level's six
// faces, one copy a face from the stage into the cube's level L (QRhi tracks a texture whole, so the cube is never read
// and written in one pass: the plan's "per-level cubes copied into the one mipped cube").
//
// The block holds one slot per (level, face), written once per allocation (its values depend on the side alone), and
// the conventions block (fragPixel: the stage's rows are the face's OpenGL rows). The pipeline is built over the stages'
// render-pass descriptor (every level's is compatible: one RGBA16F attachment, no depth). Render thread only.
#pragma once

#include "rhi_owned.h"
#include "scene_targets.h"

#include <QtCore/QString>
#include <rhi/qrhi.h>

namespace srpss_core {

// GPU-free (tests): the cone (radians) and the level read for level `level` of a cube of `side` texels a face, as
// probe.py's _prefilter computes them; and a face's world-to-view rotation, row-major (rows right, up, -forward:
// probe.py scene3d_probe_face_rotation).
double cubePrefilterCone(int side, int level);
void cubeFaceRotation(int face, double out[9]);

class CubePrefilter
{
public:
    CubePrefilter() = default;
    ~CubePrefilter();
    CubePrefilter(const CubePrefilter &) = delete;
    CubePrefilter &operator=(const CubePrefilter &) = delete;

    // Render thread, outside any pass: every level of every face of `t` (a cube target, ready) from the level above,
    // then copied into the cube. `pending` (the record's uploads, if still held) goes with the first pass. False with
    // the reason when an object could not be made (the content's failure, latched by the caller).
    bool record(QRhi *rhi, QRhiCommandBuffer *cb, SceneTargets::Target &t, QRhiResourceUpdateBatch **pending,
                QString *error);
    // Objects held (lifecycle proofs).
    int liveObjects() const;
    // Every object goes (the content's release, another QRhi).
    void release();

private:
    bool ensure(QRhi *rhi, SceneTargets::Target &t, QString *error);

    const QRhi *m_rhi = nullptr;
    RhiOwned<QRhiGraphicsPipeline> m_pipeline;
    RhiOwned<QRhiShaderResourceBindings> m_bindings;
    RhiOwned<QRhiBuffer> m_block;
    RhiOwned<QRhiSampler> m_sampler;
    const QRhiRenderPassDescriptor *m_pass = nullptr; // the descriptor the pipeline was built over
    const QRhiTexture *m_cube = nullptr;              // the cube the bindings read
    quint64 m_generation = 0;                         // the target's allocation the block was written for
    quint32 m_slot = 0;                               // one (level, face) slot's aligned size
    bool m_written = false;
};

} // namespace srpss_core
