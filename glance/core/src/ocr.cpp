#include "ocr.h"

#include <cstdio>
#include <cstdlib>
#include <string>
#include <unistd.h>

#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

#ifndef GLANCE_OCR
#define GLANCE_OCR 0
#endif

#if !GLANCE_OCR
#define GLANCE_TESSERACT_BIN ""
#elif !defined(GLANCE_TESSERACT_BIN)
#define GLANCE_TESSERACT_BIN ""
#endif

namespace glance {

namespace {

// Build the tesseract command for a prepared single-line region: PSM 7 with
// a digits + currency whitelist. Single quotes keep the shell from expanding
// the '$' in the whitelist.
std::string tesseract_cmd(const std::string& in_path) {
  return std::string("'") + GLANCE_TESSERACT_BIN + "' '" + in_path +
         "' stdout --psm 7 -c 'tessedit_char_whitelist=0123456789.,$,-B' 2>/dev/null";
}

}  // namespace

bool ocr_available() {
#if GLANCE_OCR
  static int cached = -1;
  if (cached < 0) {
    std::string cmd = std::string("'") + GLANCE_TESSERACT_BIN + "' --version 1>/dev/null 2>&1";
    std::FILE* p = popen(cmd.c_str(), "r");
    if (!p) {
      cached = 0;
      return false;
    }
    cached = (pclose(p) == 0) ? 1 : 0;
  }
  return cached == 1;
#else
  return false;
#endif
}

cv::Mat prepare_for_ocr(const cv::Mat& region) {
  if (region.empty()) return region;
  cv::Mat out;
  // Enlarge to a fixed width for stable OCR across table skins.
  if (region.cols != 300) {
    double scale = 300.0 / static_cast<double>(region.cols);
    cv::resize(region, out, cv::Size(300, cvRound(region.rows * scale)), 0, 0, cv::INTER_CUBIC);
  } else {
    out = region.clone();
  }
  if (out.channels() > 1) cv::cvtColor(out, out, cv::COLOR_BGR2GRAY);
  cv::Mat bin;
  cv::threshold(out, bin, 76, 255, cv::THRESH_BINARY_INV);
  // Fallback for low-contrast text regions.
  if (cv::mean(bin).val[0] < 10.0) cv::threshold(out, bin, 125, 255, cv::THRESH_BINARY_INV);
  return bin;
}

std::optional<double> ocr_number(const cv::Mat& region) {
  if (!ocr_available()) return std::nullopt;
  cv::Mat prep = prepare_for_ocr(region);
  if (prep.empty()) return std::nullopt;

  // The temp path MUST end in a real image extension: cv::imwrite looks up
  // its encoder by file extension (findEncoder in loadsave.cpp), and an
  // extensionless name throws "could not find a writer for the specified
  // extension" — the CI imwrite abort from run 45477292136.
  char tmpl[] = "/tmp/glance_ocr_XXXXXX.png";
  int fd = mkstemps(tmpl, 4);
  if (fd < 0) return std::nullopt;
  ::close(fd);
  std::string in_path = tmpl;
  if (!cv::imwrite(in_path, prep)) {
    unlink(in_path.c_str());
    return std::nullopt;
  }

  std::string text;
  bool ok = true;
  {
    std::FILE* p = popen(tesseract_cmd(in_path).c_str(), "r");
    if (!p) {
      ok = false;
    } else {
      char buf[512];
      size_t n;
      while ((n = fread(buf, 1, sizeof(buf), p)) > 0) text.append(buf, n);
      ok = (pclose(p) == 0);
    }
  }
  unlink(in_path.c_str());
  if (!ok) return std::nullopt;

  // Keep digits, decimal points, comma; drop currency marks ($ B) and junk.
  std::string cleaned;
  for (char c : text) {
    if (c >= '0' && c <= '9') cleaned.push_back(c);
    else if (c == '.' || c == ',' || c == ' ') cleaned.push_back(c);
  }
  for (char& c : cleaned)
    if (c == ',') c = '.';
  // collapse spaces
  std::string digits;
  for (char c : cleaned)
    if (c != ' ') digits.push_back(c);
  if (digits.empty()) return std::nullopt;

  const char* start = digits.c_str();
  while (*start && (*start < '0' || *start > '9')) ++start;
  if (*start == '\0') return std::nullopt;
  char* end = nullptr;
  double val = std::strtod(start, &end);
  if (end == start) return std::nullopt;
  if (val < 0.0) return std::nullopt;
  return val;
}

}  // namespace glance
