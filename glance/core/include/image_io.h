#pragma once

// image_io — glance's PNG/JPEG decode/encode surface.
//
// glance only ever reads and writes PNG and JPEG (POST /capture,
// /recognize-card, GET /frame.png, template/glyph PNGs, the tesseract temp
// PNG). OpenCV's imgcodecs module can do those, but it also drags in decoders
// for TIFF, WebP, OpenEXR, GDAL, ... — ~130 runtime shared libraries for
// formats we never touch. These wrappers replace the four imgcodecs calls
// (imread/imdecode/imwrite/imencode) with single-header stb decoders, so
// glance_core links only OpenCV core + imgproc (+ geometry on OpenCV 5).
//
// The in-memory image type stays cv::Mat everywhere; only the file/bytes
// boundary changes. Colour images are 3-channel BGR (OpenCV's convention),
// matching the old cv::IMREAD_COLOR behaviour: alpha is dropped, grayscale
// sources are expanded to BGR. Grayscale loads are 1-channel (IMREAD_GRAYSCALE).

#include <cstddef>
#include <string>
#include <vector>

#include <opencv2/core.hpp>

namespace glance {

// Decode a PNG or JPEG file from disk.
//   color == true  -> 3-channel BGR  (like cv::imread(path, IMREAD_COLOR))
//   color == false -> 1-channel gray (like cv::imread(path, IMREAD_GRAYSCALE))
// Returns an empty cv::Mat on any failure (missing file, unsupported or
// corrupt data), exactly as cv::imread did.
cv::Mat load_image(const std::string& path, bool color);

// Decode PNG or JPEG bytes already in memory (what a client POSTs). Same
// colour/channel contract as load_image(). Returns an empty cv::Mat on
// failure.
cv::Mat decode_image(const unsigned char* data, std::size_t size, bool color);
cv::Mat decode_image(const std::vector<unsigned char>& data, bool color);

// Encode a BGR (3-channel) or grayscale (1-channel) 8-bit cv::Mat as a PNG.
// encode_png appends the bytes to `out` (cleared first); write_png writes
// them to `path`. Both return false on failure.
bool encode_png(const cv::Mat& image, std::vector<unsigned char>& out);
bool write_png(const std::string& path, const cv::Mat& image);

}  // namespace glance
