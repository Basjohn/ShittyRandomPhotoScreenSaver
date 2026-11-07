#include "image_stats.h"

namespace srpss_spike {

ImageStats imageStats(const QImage &source)
{
    ImageStats s;
    if (source.isNull())
        return s;
    const QImage image = source.convertToFormat(QImage::Format_RGBA8888);
    s.width = image.width();
    s.height = image.height();
    quint64 hash = 1469598103934665603ull;
    for (int y = 0; y < image.height(); ++y) {
        const uchar *row = image.constScanLine(y);
        for (int x = 0; x < image.width(); ++x) {
            const uchar *p = row + x * 4;
            if (p[0] + p[1] + p[2] > 3 * 48)
                ++s.litPixels;
            for (int c = 0; c < 4; ++c) {
                hash ^= p[c];
                hash *= 1099511628211ull;
            }
        }
    }
    s.checksum = hash;
    return s;
}

QImage imageFromReadback(const QByteArray &data, const QSize &size, bool yUp)
{
    if (data.isEmpty() || size.isEmpty())
        return {};
    const QImage wrapped(reinterpret_cast<const uchar *>(data.constData()), size.width(),
                         size.height(), QImage::Format_RGBA8888_Premultiplied);
    return yUp ? wrapped.flipped(Qt::Vertical) : wrapped.copy();
}

} // namespace srpss_spike
