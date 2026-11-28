#include "gl_sampler_state.h"

#include <rhi/qrhi.h>

// Qt's OpenGL backend's own resource types (QGles2Texture::samplerState, QGles2Sampler::d). The module is built against
// the exact Qt it runs on (CMakeLists.txt refuses another SDK), so this private layout is the running one.
#include <QtGui/private/qrhigles2_p.h>

namespace srpss_core {

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

} // namespace srpss_core
