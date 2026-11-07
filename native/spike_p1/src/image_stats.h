#pragma once

#include <QtGui/QImage>

namespace srpss_spike {

struct ImageStats
{
    int width = 0;
    int height = 0;
    int litPixels = 0;        // pixels clearly brighter than the clear colour
    quint64 checksum = 0;     // FNV-1a over RGBA8 rows, informational only
};

ImageStats imageStats(const QImage &image);

// Builds a top-down RGBA image from a QRhi texture readback.
QImage imageFromReadback(const QByteArray &data, const QSize &size, bool yUp);

} // namespace srpss_spike
