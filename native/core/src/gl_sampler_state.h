// N5.2h side defect (found by N5.6, 28 Nov 2026): Qt 6.12.0's OpenGL backend applies a combined sampler's state to its
// texture with glTexParameteri at the texture's first bind after create() (QRhiGles2::bindCombinedSampler: its cached
// samplerState differs from the sampler's). A multisampled texture (GL_TEXTURE_2D_MULTISAMPLE) has no sampler state, so
// every one of those calls is GL_INVALID_ENUM ("multisample textures targets doesn't support sampler state"). Every
// multisampled texture is a scene target's (scene_targets.cpp) and reaches shaders through many passes (the resolves,
// the captures, mode passes): so every pipeline set and every explicit shader-resource bind in the core goes through
// the helpers below (tests/test_native_post_stages.py holds that no cb->setGraphicsPipeline/setComputePipeline or
// explicit cb->setShaderResources(srb) bypasses them).
// Qt fixed it after 6.12.0 (isMultisampleTextureTarget in the 6.12 branch); the module builds against PySide6's exact
// Qt (CMakeLists.txt), so until then the core makes Qt's cache already hold the sampler's state on those textures.
#pragma once

class QRhi;
class QRhiCommandBuffer;
class QRhiComputePipeline;
class QRhiGraphicsPipeline;
class QRhiShaderResourceBindings;

namespace srpss_core {

// On OpenGL, every multisampled texture a sampled-texture binding of `bindings` reads takes its sampler's state into
// Qt's per-texture cache, so Qt sets no sampler state on it (none exists). Elsewhere, and for single-sampled textures,
// nothing. Called where such a pass records, after any create() of its textures (create() resets the cache). Returns how
// many textures it marked.
int adoptMultisampleSamplerState(QRhi *rhi, QRhiShaderResourceBindings *bindings);
// The same, with the bindings' own QRhi: before an explicit cb->setShaderResources(bindings, ...).
int adoptMultisampleSamplerState(QRhiShaderResourceBindings *bindings);
// cb->setGraphicsPipeline / setComputePipeline after adopting for the pipeline's own bindings (what a
// setShaderResources(nullptr, ...) after it binds). Every pipeline set in the core goes through these.
void setGraphicsPipelineAdopting(QRhiCommandBuffer *cb, QRhiGraphicsPipeline *pipeline);
void setComputePipelineAdopting(QRhiCommandBuffer *cb, QRhiComputePipeline *pipeline);

} // namespace srpss_core
