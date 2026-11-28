#include "ocr.h"

#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <random>
#include <string>
#include <system_error>

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

// ---- shell portability ------------------------------------------------------
// tesseract is run as a child process through the platform shell: /bin/sh via
// popen on POSIX, cmd.exe via _popen on Windows. The two differ in quoting
// and in the null device, so every command line is assembled from these
// helpers. An argument that cannot be quoted safely for the shell (a single
// quote for sh; a double quote or '%' for cmd.exe, which expands %VAR% even
// inside quotes) is refused rather than escaped.

#ifdef _WIN32
constexpr const char* kNullDevice = "NUL";
#else
constexpr const char* kNullDevice = "/dev/null";
#endif

bool quote_arg(const std::string& arg, std::string& out) {
#ifdef _WIN32
  if (arg.find_first_of("\"%\r\n") != std::string::npos) return false;
  out += '"';
  out += arg;
  // A trailing backslash would escape the closing quote for the child's
  // argv parser (CommandLineToArgvW rules): double it.
  if (!arg.empty() && arg.back() == '\\') out += '\\';
  out += '"';
#else
  if (arg.find('\'') != std::string::npos) return false;
  out += '\'';
  out += arg;
  out += '\'';
#endif
  return true;
}

// The tesseract binary path baked in at configure time. CMake's find_program
// reports forward slashes; cmd.exe wants backslashes in the program path.
std::string tesseract_bin() {
  std::string bin = GLANCE_TESSERACT_BIN;
#ifdef _WIN32
  for (char& c : bin)
    if (c == '/') c = '\\';
#endif
  return bin;
}

// Build "<bin> <args...> <redirects>" for the platform shell. Returns false
// when an argument cannot be quoted.
bool build_command(const std::vector<std::string>& args, const std::string& redirects,
                   std::string& cmd) {
  cmd.clear();
  if (!quote_arg(tesseract_bin(), cmd)) return false;
  for (const auto& a : args) {
    cmd += ' ';
    if (!quote_arg(a, cmd)) return false;
  }
  cmd += ' ';
  cmd += redirects;
#ifdef _WIN32
  // _popen runs `cmd.exe /c <cmd>`; when the line starts with a quote and has
  // more than two of them, cmd strips the first and last quote character.
  // Wrapping the whole line in one extra pair makes that stripping harmless.
  cmd = "\"" + cmd + "\"";
#endif
  return true;
}

std::FILE* open_pipe(const std::string& cmd) {
#ifdef _WIN32
  return _popen(cmd.c_str(), "rb");
#else
  return popen(cmd.c_str(), "r");
#endif
}

int close_pipe(std::FILE* p) {
#ifdef _WIN32
  return _pclose(p);
#else
  return pclose(p);
#endif
}

}  // namespace

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
    std::string cmd;
    if (!build_command({"--version"}, std::string("1>") + kNullDevice + " 2>&1", cmd)) {
      cached = 0;
      return false;
    }
    std::FILE* p = open_pipe(cmd);
    if (!p) {
      cached = 0;
      return false;
    }
    cached = (close_pipe(p) == 0) ? 1 : 0;
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

// Create a fresh, uniquely named, empty file `<tmp>/glance_ocr_<random>.png`
// (exclusive create, so two concurrent OCR calls never share a path).
// Portable replacement for mkstemps: std::filesystem gives the platform temp
// dir (TMPDIR or /tmp on POSIX, GetTempPath on Windows) and fopen's C11 "x"
// mode fails if the file already exists.
bool make_temp_png(std::string& path) {
  std::error_code ec;
  const std::filesystem::path dir = std::filesystem::temp_directory_path(ec);
  if (ec) return false;
  static thread_local std::mt19937_64 rng{std::random_device{}()};
  for (int attempt = 0; attempt < 16; ++attempt) {
    char name[64];
    std::snprintf(name, sizeof(name), "glance_ocr_%016llx.png",
                  static_cast<unsigned long long>(rng()));
    const std::string candidate = (dir / name).string();
    if (std::FILE* f = std::fopen(candidate.c_str(), "wbx")) {
      std::fclose(f);
      path = candidate;
      return true;
    }
  }
  return false;
}

// Write `image` to a temp PNG, run tesseract with `args` and capture stdout.
// The temp path MUST end in a real image extension: cv::imwrite looks up its
// encoder by file extension (findEncoder in loadsave.cpp), and an extensionless
// name throws "could not find a writer for the specified extension" — the CI
// imwrite abort from run 45477292136. Each element of `args` is one argv
// entry; quoting for the platform shell happens in build_command.
bool run_tesseract(const cv::Mat& image, const std::vector<std::string>& args, std::string& text) {
  std::string in_path;
  if (!make_temp_png(in_path)) return false;
  std::error_code ec;
  if (!cv::imwrite(in_path, image)) {
    std::filesystem::remove(in_path, ec);
    return false;
  }
  bool ok = true;
  {
    std::vector<std::string> argv{in_path, "stdout"};
    argv.insert(argv.end(), args.begin(), args.end());
    std::string cmd;
    std::FILE* p = build_command(argv, std::string("2>") + kNullDevice, cmd) ? open_pipe(cmd) : nullptr;
    if (!p) {
      ok = false;
    } else {
      char buf[512];
      size_t n;
      while ((n = fread(buf, 1, sizeof(buf), p)) > 0) text.append(buf, n);
      ok = (close_pipe(p) == 0);
    }
  }
  std::filesystem::remove(in_path, ec);
  return ok;
}

}  // namespace

std::optional<double> ocr_number(const cv::Mat& region) {
  if (!ocr_available()) return std::nullopt;
  cv::Mat prep = prepare_for_ocr(region);
  if (prep.empty()) return std::nullopt;
  std::string text;
  if (!run_tesseract(prep, {"--psm", "7", "-c", "tessedit_char_whitelist=0123456789.,$,-B"}, text))
    return std::nullopt;
  return parse_ocr_number_text(text);
}

std::vector<OcrWord> ocr_words(const cv::Mat& image, int psm, const std::string& whitelist) {
  std::vector<OcrWord> out;
  if (!ocr_available() || image.empty()) return out;
  // The whitelist is quoted for the platform shell; a whitelist containing
  // a character that cannot be quoted there (a single quote for sh, a double
  // quote or '%' for cmd.exe) is refused by run_tesseract (empty result).
  std::vector<std::string> args{"--psm", std::to_string(psm)};
  if (!whitelist.empty()) {
    args.push_back("-c");
    args.push_back("tessedit_char_whitelist=" + whitelist);
  }
  args.push_back("tsv");
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
