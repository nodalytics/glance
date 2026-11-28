#include "image_io.h"

#include <cstdint>
#include <fstream>
#include <iterator>
#include <limits>

#include <opencv2/imgproc.hpp>

// Single-header PNG/JPEG decoders, vendored via CMake FetchContent and pinned
// in glance/CMakeLists.txt (nothings/stb). They are added as a SYSTEM include
// dir so their own -Wall/-Wextra noise does not trip glance's zero-warning
// gate; glance's code in this file is still compiled with warnings on.
//
// The implementations are emitted in THIS translation unit only (the two
// IMPLEMENTATION macros below), so every other glance TU just sees the small
// header. We decode from memory and write through a callback, so stb never
// touches stdio: no fopen, no platform path quirks (NO_STDIO drops that code).
#define STB_IMAGE_IMPLEMENTATION
#define STBI_NO_STDIO
#define STBI_NO_LINEAR
#define STBI_NO_HDR
#define STBI_ONLY_PNG
#define STBI_ONLY_JPEG
#include <stb_image.h>

#define STB_IMAGE_WRITE_IMPLEMENTATION
#define STBI_WRITE_NO_STDIO
#include <stb_image_write.h>

namespace glance {

namespace {

// Build a BGR/gray cv::Mat that OWNS its pixels from a tightly packed stb
// buffer. For colour we swap stb's RGB into OpenCV's BGR (cvtColor allocates a
// fresh buffer); for gray we clone. Either way the result survives
// stbi_image_free.
cv::Mat adopt_stb_pixels(unsigned char* pixels, int w, int h, bool color) {
  cv::Mat out;
  if (color) {
    const cv::Mat rgb(h, w, CV_8UC3, pixels);  // wraps stb's buffer, no copy
    cv::cvtColor(rgb, out, cv::COLOR_RGB2BGR);
  } else {
    const cv::Mat gray(h, w, CV_8UC1, pixels);
    out = gray.clone();
  }
  return out;
}

// stb write callback: append the encoded bytes to the std::vector in `ctx`.
void append_bytes(void* ctx, void* data, int size) {
  auto* out = static_cast<std::vector<unsigned char>*>(ctx);
  const auto* bytes = static_cast<const unsigned char*>(data);
  if (size > 0) out->insert(out->end(), bytes, bytes + size);
}

}  // namespace

cv::Mat decode_image(const unsigned char* data, std::size_t size, bool color) {
  if (data == nullptr || size == 0) return {};
  // stb takes an int length; refuse anything that would overflow it.
  if (size > static_cast<std::size_t>(std::numeric_limits<int>::max())) return {};

  int w = 0, h = 0, channels_in_file = 0;
  const int desired = color ? 3 : 1;
  unsigned char* pixels =
      stbi_load_from_memory(data, static_cast<int>(size), &w, &h, &channels_in_file, desired);
  if (pixels == nullptr || w <= 0 || h <= 0) {
    if (pixels != nullptr) stbi_image_free(pixels);
    return {};
  }
  cv::Mat out = adopt_stb_pixels(pixels, w, h, color);
  stbi_image_free(pixels);
  return out;
}

cv::Mat decode_image(const std::vector<unsigned char>& data, bool color) {
  return decode_image(data.data(), data.size(), color);
}

cv::Mat load_image(const std::string& path, bool color) {
  std::ifstream f(path, std::ios::binary);
  if (!f) return {};
  const std::vector<unsigned char> buf((std::istreambuf_iterator<char>(f)),
                                       std::istreambuf_iterator<char>());
  return decode_image(buf.data(), buf.size(), color);
}

bool encode_png(const cv::Mat& image, std::vector<unsigned char>& out) {
  out.clear();
  if (image.empty() || image.depth() != CV_8U) return false;

  // stb wants RGB/gray, tightly rows-first; OpenCV holds BGR and may be a
  // non-contiguous ROI. Produce a continuous buffer in stb's channel order.
  cv::Mat src;
  int comp = 0;
  if (image.channels() == 3) {
    cv::cvtColor(image, src, cv::COLOR_BGR2RGB);  // result is continuous
    comp = 3;
  } else if (image.channels() == 1) {
    src = image.isContinuous() ? image : image.clone();
    comp = 1;
  } else {
    return false;  // only BGR and gray are produced/consumed by glance
  }

  const int rc = stbi_write_png_to_func(append_bytes, &out, src.cols, src.rows, comp, src.data,
                                        static_cast<int>(src.step));
  if (rc == 0) {
    out.clear();
    return false;
  }
  return !out.empty();
}

bool write_png(const std::string& path, const cv::Mat& image) {
  std::vector<unsigned char> buf;
  if (!encode_png(image, buf)) return false;
  std::ofstream f(path, std::ios::binary | std::ios::trunc);
  if (!f) return false;
  f.write(reinterpret_cast<const char*>(buf.data()), static_cast<std::streamsize>(buf.size()));
  return static_cast<bool>(f);
}

}  // namespace glance
