#include "gl_sampler_state.h"

#include <rhi/qrhi.h>

// Qt's OpenGL backend's own resource types (QGles2Texture::samplerState, QGles2Sampler::d). The module is built against
// the exact Qt it runs on (CMakeLists.txt refuses another SDK), so this private layout is the running one.
#include <QtGui/private/qrhigles2_p.h>
#include <QtGui/QOpenGLContext>
#include <QtGui/QOpenGLExtraFunctions>

#ifndef GL_TEXTURE_2D_MULTISAMPLE
#define GL_TEXTURE_2D_MULTISAMPLE 0x9100
#endif
#ifndef GL_TEXTURE_BINDING_2D_MULTISAMPLE
#define GL_TEXTURE_BINDING_2D_MULTISAMPLE 0x9104
#endif

namespace srpss_core {

bool createTexture(QRhiTexture *texture)
{
    if (!texture)
        return false;
    QRhi *rhi = texture->rhi();
    const QRhiTexture::Flags shaped = QRhiTexture::CubeMap | QRhiTexture::MipMapped | QRhiTexture::ThreeDimensional
        | QRhiTexture::TextureArray | QRhiTexture::OneDimensional;
    if (!rhi || rhi->backend() != QRhi::OpenGLES2 || texture->sampleCount() <= 1 || texture->flags().testAnyFlags(shaped))
        return texture->create();
    if (!rhi->makeThreadLocalNativeContextCurrent())
        return texture->create();
    QOpenGLContext *context = QOpenGLContext::currentContext();
    if (!context)
        return texture->create();
    QOpenGLExtraFunctions *gl = context->extraFunctions();
    GLuint name = 0;
    gl->glGenTextures(1, &name);
    if (!name)
        return texture->create();
    // createFrom runs Qt's prepareCreate (releases a previous object, resolves target, sized format and the effective
    // sample count, resets the sampler-state cache) and touches no GL state of `name`.
    if (!texture->createFrom({ quint64(name), 0 })) {
        gl->glDeleteTextures(1, &name);
        return false;
    }
    auto *glTexture = static_cast<QGles2Texture *>(texture);
    if (glTexture->target != GL_TEXTURE_2D_MULTISAMPLE || glTexture->samples <= 1) {
        // Not multisampled after all (no multisampled-texture support, or one effective sample): Qt's own path.
        gl->glDeleteTextures(1, &name);
        return texture->create();
    }
    const QSize size = texture->pixelSize().isEmpty() ? QSize(1, 1) : texture->pixelSize();
    GLint previous = 0;
    gl->glGetIntegerv(GL_TEXTURE_BINDING_2D_MULTISAMPLE, &previous);
    gl->glBindTexture(GL_TEXTURE_2D_MULTISAMPLE, name);
    gl->glTexStorage2DMultisample(GL_TEXTURE_2D_MULTISAMPLE, glTexture->samples, glTexture->glsizedintformat,
                                  size.width(), size.height(), GL_TRUE);
    gl->glBindTexture(GL_TEXTURE_2D_MULTISAMPLE, GLuint(previous));
    glTexture->owns = true;               // Qt's destroy() queues its release, as for a texture it created
    return true;
}

int adoptMultisampleSamplerState(QRhi *rhi, QRhiShaderResourceBindings *bindings)
{
    if (!rhi || !bindings || rhi->backend() != QRhi::OpenGLES2)
        return 0;
    int marked = 0;
    for (auto it = bindings->cbeginBindings(), end = bindings->cendBindings(); it != end; ++it) {
        const QRhiShaderResourceBinding::Data *d = QRhiImplementation::shaderResourceBindingData(*it);
        if (d->type != QRhiShaderResourceBinding::SampledTexture)
            continue;
        for (int i = 0; i < d->u.stex.count; ++i) {
            QRhiTexture *texture = d->u.stex.texSamplers[i].tex;
            QRhiSampler *sampler = d->u.stex.texSamplers[i].sampler;
            if (!texture || !sampler || texture->sampleCount() <= 1)
                continue;
            auto *glTexture = static_cast<QGles2Texture *>(texture);
            const QGles2SamplerData &state = static_cast<QGles2Sampler *>(sampler)->d;
            if (!(glTexture->samplerState == state)) {
                glTexture->samplerState = state;
                ++marked;
            }
        }
    }
    return marked;
}

int adoptMultisampleSamplerState(QRhiShaderResourceBindings *bindings)
{
    return bindings ? adoptMultisampleSamplerState(bindings->rhi(), bindings) : 0;
}

void setGraphicsPipelineAdopting(QRhiCommandBuffer *cb, QRhiGraphicsPipeline *pipeline)
{
    if (pipeline)
        adoptMultisampleSamplerState(pipeline->shaderResourceBindings());
    cb->setGraphicsPipeline(pipeline);
}

void setComputePipelineAdopting(QRhiCommandBuffer *cb, QRhiComputePipeline *pipeline)
{
    if (pipeline)
        adoptMultisampleSamplerState(pipeline->shaderResourceBindings());
    cb->setComputePipeline(pipeline);
}

} // namespace srpss_core
