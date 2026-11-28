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

std::optional<double> parse_ocr_number_text(const std::string& text) {
  if (text.find('-') != std::string::npos) return std::nullopt;

  std::string raw;
  for (unsigned char uc : text) {
    char c = static_cast<char>(uc);
    if ((c >= '0' && c <= '9') || c == '.' || c == ',') raw.push_back(c);
  }
  if (raw.empty()) return std::nullopt;

  const auto last_dot = raw.rfind('.');
  const auto last_comma = raw.rfind(',');
  std::string digits;
  if (last_dot != std::string::npos && last_comma != std::string::npos) {
    const bool comma_decimal = last_comma > last_dot;
    for (char c : raw) {
      if (comma_decimal) {
        if (c == '.') continue;
        digits.push_back(c == ',' ? '.' : c);
      } else if (c != ',') {
        digits.push_back(c);
      }
    }
  } else if (last_comma != std::string::npos) {
    bool thousands = true;
    int groups = 0;
    std::size_t start = 0;
    for (std::size_t i = 0; i <= raw.size(); ++i) {
      if (i != raw.size() && raw[i] != ',') continue;
      const std::size_t len = i - start;
      if (len == 0 || (groups == 0 && len > 3) || (groups > 0 && len != 3)) thousands = false;
      start = i + 1;
      ++groups;
    }
    if (groups < 2) thousands = false;
    for (char c : raw) {
      if (c == ',') {
        if (!thousands) digits.push_back('.');
      } else {
        digits.push_back(c);
      }
    }
  } else {
    digits = raw;
  }

  int dots = 0;
  for (char c : digits)
    if (c == '.') ++dots;
  if (dots > 1) return std::nullopt;

  const char* start = digits.c_str();
  while (*start && (*start < '0' || *start > '9')) ++start;
  if (*start == '\0') return std::nullopt;
  char* end = nullptr;
  const double val = std::strtod(start, &end);
  if (end == start || *end != '\0' || val < 0.0) return std::nullopt;
  return val;
}


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

namespace {

// Write `image` to a temp PNG, run tesseract with `args` and capture stdout.
// The temp path MUST end in a real image extension: cv::imwrite looks up its
// encoder by file extension (findEncoder in loadsave.cpp), and an extensionless
// name throws "could not find a writer for the specified extension" — the CI
// imwrite abort from run 45477292136.
bool run_tesseract(const cv::Mat& image, const std::string& args, std::string& text) {
  char tmpl[] = "/tmp/glance_ocr_XXXXXX.png";
  int fd = mkstemps(tmpl, 4);
  if (fd < 0) return false;
  ::close(fd);
  std::string in_path = tmpl;
  if (!cv::imwrite(in_path, image)) {
    unlink(in_path.c_str());
    return false;
  }
  bool ok = true;
  {
    std::string cmd = std::string("'") + GLANCE_TESSERACT_BIN + "' '" + in_path + "' stdout " + args +
                      " 2>/dev/null";
    std::FILE* p = popen(cmd.c_str(), "r");
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
  return ok;
}

}  // namespace

std::optional<double> ocr_number(const cv::Mat& region) {
  if (!ocr_available()) return std::nullopt;
  cv::Mat prep = prepare_for_ocr(region);
  if (prep.empty()) return std::nullopt;
  std::string text;
  if (!run_tesseract(prep, "--psm 7 -c 'tessedit_char_whitelist=0123456789.,$,-B'", text))
    return std::nullopt;
  return parse_ocr_number_text(text);
}

std::vector<OcrWord> ocr_words(const cv::Mat& image, int psm, const std::string& whitelist) {
  std::vector<OcrWord> out;
  if (!ocr_available() || image.empty()) return out;
  // The whitelist is single-quoted for the shell; refuse quotes in it.
  if (whitelist.find('\'') != std::string::npos) return out;
  std::string args = "--psm " + std::to_string(psm);
  if (!whitelist.empty()) args += " -c 'tessedit_char_whitelist=" + whitelist + "'";
  args += " tsv";
  std::string tsv;
  if (!run_tesseract(image, args, tsv)) return out;
  // TSV columns: level page block par line word left top width height conf text
  std::size_t pos = 0;
  bool header = true;
  while (pos < tsv.size()) {
    std::size_t end = tsv.find('\n', pos);
    if (end == std::string::npos) end = tsv.size();
    std::string line = tsv.substr(pos, end - pos);
    pos = end + 1;
    if (header) {
      header = false;
      continue;
    }
    std::vector<std::string> cols;
    std::size_t s = 0;
    while (true) {
      std::size_t t = line.find('\t', s);
      cols.push_back(line.substr(s, t == std::string::npos ? std::string::npos : t - s));
      if (t == std::string::npos) break;
      s = t + 1;
    }
    if (cols.size() < 12 || cols[0] != "5") continue;
    std::string text = cols[11];
    while (!text.empty() && (text.back() == '\r' || text.back() == ' ')) text.pop_back();
    if (text.empty()) continue;
    const double conf = std::strtod(cols[10].c_str(), nullptr);
    if (conf < 0) continue;
    out.push_back({text, conf / 100.0});
  }
  return out;
}

}  // namespace glance
