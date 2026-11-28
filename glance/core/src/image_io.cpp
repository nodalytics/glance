#include "image_io.h"

#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <limits>
#include <new>

#include <opencv2/imgproc.hpp>

// ---------------------------------------------------------------------------
// stb decode allocation budget — defence in depth for the untrusted path.
//
// dims_ok() (below) bounds the FINAL image from the header, but stb allocates
// while it inflates the zlib stream and, for 16-bit PNGs, in 2-bytes-per-channel
// buffers, so peak memory during decode can exceed the final size even when the
// header looks sane. We hand stb a custom allocator that tracks a thread-local
// running total for the current decode and refuses once it passes a hard
// per-decode budget: a crafted file then fails early (stb returns null -> empty
// Mat) instead of allocating gigabytes. stb is single-threaded per call, so a
// thread_local counter suffices. Each block carries its size in a max-aligned
// header so realloc/free keep the total honest. (stb_image_write keeps its own
// STBIW_* allocators — plain malloc — which is fine: encode runs on our own
// trusted Mats, not on untrusted bytes.)
namespace {

constexpr long long kStbDecodeByteBudget = 96LL * 1024 * 1024;  // ~96 MB per decode
constexpr std::size_t kStbHeader = alignof(std::max_align_t) > sizeof(std::size_t)
                                       ? alignof(std::max_align_t)
                                       : sizeof(std::size_t);

thread_local long long g_stb_live_bytes = 0;

void reset_stb_budget() { g_stb_live_bytes = 0; }

void* stb_budget_malloc(std::size_t size) {
  if (size == 0) size = 1;
  if (size > static_cast<std::size_t>(kStbDecodeByteBudget)) return nullptr;
  if (g_stb_live_bytes + static_cast<long long>(size) > kStbDecodeByteBudget) return nullptr;
  void* raw = std::malloc(size + kStbHeader);
  if (raw == nullptr) return nullptr;
  *static_cast<std::size_t*>(raw) = size;
  g_stb_live_bytes += static_cast<long long>(size);
  return static_cast<char*>(raw) + kStbHeader;
}

void stb_budget_free(void* ptr) {
  if (ptr == nullptr) return;
  void* raw = static_cast<char*>(ptr) - kStbHeader;
  g_stb_live_bytes -= static_cast<long long>(*static_cast<std::size_t*>(raw));
  std::free(raw);
}

void* stb_budget_realloc(void* ptr, std::size_t new_size) {
  if (ptr == nullptr) return stb_budget_malloc(new_size);
  if (new_size == 0) new_size = 1;
  void* raw = static_cast<char*>(ptr) - kStbHeader;
  const std::size_t old_size = *static_cast<std::size_t*>(raw);
  const long long projected =
      g_stb_live_bytes - static_cast<long long>(old_size) + static_cast<long long>(new_size);
  if (new_size > static_cast<std::size_t>(kStbDecodeByteBudget) || projected > kStbDecodeByteBudget)
    return nullptr;
  void* new_raw = std::realloc(raw, new_size + kStbHeader);
  if (new_raw == nullptr) return nullptr;
  *static_cast<std::size_t*>(new_raw) = new_size;
  g_stb_live_bytes = projected;
  return static_cast<char*>(new_raw) + kStbHeader;
}

}  // namespace

// Single-header PNG/JPEG decoders, vendored via CMake FetchContent and pinned
// in glance/CMakeLists.txt to an exact nothings/stb commit (stb_image v2.34,
// well past the heap-overflow CVE fixes of the v2.27/2.28 era). They are added
// as a SYSTEM include dir so their own -Wall/-Wextra noise does not trip
// glance's zero-warning gate; glance's code in this file is still compiled with
// warnings on.
//
// stb runs on UNTRUSTED input here: POST /capture and /recognize-card decode
// bytes straight off the network, and the server may bind 0.0.0.0. stb_image
// is memory-unsafe on malformed input and will allocate whatever a header
// claims (a decompression bomb). The mitigation is layered, not stb itself:
// (1) a format-signature check, (2) a header dimension/pixel cap, both before
// decoding; (3) STBI_MAX_DIMENSIONS and (4) a per-decode allocation budget that
// bound the worst case DURING inflation; and (5) a try/catch backstop so any
// std::bad_alloc / cv::Exception becomes an empty Mat, never a crash.
//
// The implementations are emitted in THIS translation unit only (the two
// IMPLEMENTATION macros below), so every other glance TU just sees the small
// header. We decode from memory and write through a callback, so stb never
// touches stdio: no fopen, no platform path quirks (NO_STDIO drops that code).
//
// STBI_MAX_DIMENSIONS makes stb refuse >4096-per-side mid-decode (not just at
// the header), and STBI_MALLOC/REALLOC/FREE route stb_image's allocations
// through the budget allocator above — the two internal backstops behind the
// header check in decode_image().
#define STBI_MALLOC(sz) stb_budget_malloc(sz)
#define STBI_REALLOC(p, newsz) stb_budget_realloc(p, newsz)
#define STBI_FREE(p) stb_budget_free(p)
#define STBI_MAX_DIMENSIONS 4096
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

// Upper bounds on the geometry when decoding UNTRUSTED image bytes, checked
// from the header before stb allocates anything. Real ACR grabs are ~1600x899
// and card crops are tiny, so 4096 per side / 16 Mpx is already generous while
// refusing absurd dimensions. The per-decode byte budget above accounts for
// channel count and bit depth (the part geometry alone can't see); this cap and
// stb's own STBI_MAX_DIMENSIONS keep the two in agreement.
constexpr int kMaxImageDim = 4096;                            // per side
constexpr long long kMaxImagePixels = 16LL * 1024 * 1024;     // 16 Mpx total

// Accept only the formats glance handles, by signature, before handing bytes to
// stb: PNG (\x89PNG\r\n\x1a\n) or JPEG (SOI \xFF\xD8 + a marker \xFF). Anything
// else is rejected fast, so stb never parses a format we did not intend.
bool has_png_or_jpeg_magic(const unsigned char* d, std::size_t n) {
  static const unsigned char kPng[8] = {0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A};
  if (n >= sizeof(kPng) && std::memcmp(d, kPng, sizeof(kPng)) == 0) return true;
  if (n >= 3 && d[0] == 0xFF && d[1] == 0xD8 && d[2] == 0xFF) return true;  // JPEG
  return false;
}

// True if (w, h) is a sane, decodable size within the untrusted-input bounds.
bool dims_ok(int w, int h) {
  return w > 0 && h > 0 && w <= kMaxImageDim && h <= kMaxImageDim &&
         static_cast<long long>(w) * h <= kMaxImagePixels;
}

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
  // Fresh budget for this decode (stb frees as it goes, so this is normally
  // already zero — belt and suspenders against a prior aborted decode).
  reset_stb_budget();
  if (data == nullptr || size == 0) return {};
  // stb takes an int length; refuse anything that would overflow it.
  if (size > static_cast<std::size_t>(std::numeric_limits<int>::max())) return {};
  // Untrusted input: reject by format signature, then by header dimensions,
  // before stb allocates anything.
  if (!has_png_or_jpeg_magic(data, size)) return {};

  const int len = static_cast<int>(size);
  int info_w = 0, info_h = 0, info_c = 0;
  if (!stbi_info_from_memory(data, len, &info_w, &info_h, &info_c)) return {};
  if (!dims_ok(info_w, info_h)) return {};

  const int desired = color ? 3 : 1;
  try {
    int w = 0, h = 0, channels_in_file = 0;
    unsigned char* pixels = stbi_load_from_memory(data, len, &w, &h, &channels_in_file, desired);
    if (pixels == nullptr) return {};
    // Re-check against the real decoded size (defence in depth: the header and
    // the decoder must agree, and neither may exceed the bound).
    if (!dims_ok(w, h)) {
      stbi_image_free(pixels);
      return {};
    }
    cv::Mat out = adopt_stb_pixels(pixels, w, h, color);
    stbi_image_free(pixels);
    return out;
  } catch (const std::bad_alloc&) {
    return {};
  } catch (const cv::Exception&) {
    return {};
  }
}

cv::Mat decode_image(const std::vector<unsigned char>& data, bool color) {
  return decode_image(data.data(), data.size(), color);
}

cv::Mat load_image(const std::string& path, bool color) {
  // Reads our own template/glyph PNGs, so lower risk than the network path, but
  // it funnels through decode_image() and so inherits the same signature check,
  // dimension/pixel caps and try/catch for free.
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
