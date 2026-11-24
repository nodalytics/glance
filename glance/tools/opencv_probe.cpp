// glance-opencv-probe: what can this host's imgcodecs actually do?
//
// CI has once failed the selftest with
//   cv::Exception ... loadsave.cpp:730: "could not find a writer for the
//   specified extension in function 'imwrite_'
// — findEncoder() returning null, i.e. NO encoder was registered for the
// requested extension. This probe prints the build info's "Image I/O" section
// (which codecs were compiled in) and then actually tries imwrite/imencode for
// several formats, so a failing host tells us exactly what it is missing.
//
// It is invoked by the CI workflow as a separate step (never from the
// selftest itself), so a host that cannot encode anything still produces the
// diagnostics before anything is assumed to work.

#include <cstdio>
#include <string>
#include <vector>

#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>

static void print_codec_lines() {
  // The codec list lives in different places depending on the OpenCV version:
  // 4.9+ has an "Image I/O" section; 4.6 (Ubuntu's distro build) carries the
  // entries as "  PNG:   /usr/lib/.../libpng.so (ver 1.6.43)" lines under
  // "General configuration". Print both: the section when present, the
  // keyword lines always — either way the answer is which codecs are linked.
  std::string info = cv::getBuildInformation();
  const char* needle = "Image I/O";
  size_t i = info.find(needle);
  if (i != std::string::npos) {
    std::printf("--- Image I/O section ---\n");
    i = info.rfind('\n', (i == 0) ? 0 : i - 1) + 1;  // start of that line
    size_t line = i;
    int blank = 0;
    while (line < info.size() && blank < 2) {
      size_t nl = info.find('\n', line);
      size_t end = (nl == std::string::npos) ? info.size() : nl;
      std::string l = info.substr(line, end - line);
      bool blankish = l.find_first_not_of(" \t\r") == std::string::npos;
      if (blankish) ++blank;
      std::printf("%s\n", l.c_str());
      if (nl == std::string::npos) break;
      line = nl + 1;
    }
  }
  std::printf("--- codec config lines ---\n");
  const char* keywords[] = {"JPEG", "PNG", "TIFF", "WEBP", "OpenEXR", "GIF", "OpenJPEG"};
  size_t start = 0;
  while (true) {
    size_t nl = info.find('\n', start);
    size_t end = (nl == std::string::npos) ? info.size() : nl;
    std::string l = info.substr(start, end - start);
    for (const char* kw : keywords) {
      if (l.find(kw) != std::string::npos) {
        std::printf("%s\n", l.c_str());
        break;
      }
    }
    if (nl == std::string::npos) break;
    start = nl + 1;
  }
}

int main() {
  std::printf("opencv_probe: OpenCV %s\n", CV_VERSION);
  print_codec_lines();

  cv::Mat img(16, 20, CV_8UC3, cv::Scalar(200, 100, 50));  // small solid image
  int fail = 0;
  const char* exts[] = {".png", ".jpg", ".bmp", ".ppm"};
  for (const char* ext : exts) {
    // imwrite to a real path
    try {
      std::string p = std::string("/tmp/glance_probe") + ext;
      bool ok = cv::imwrite(p, img);
      std::printf("  %s %-8s imwrite -> %s\n", ok ? "ok  " : "FAIL", ext,
                  ok ? "written" : "returned false");
      if (!ok) ++fail;
    } catch (const cv::Exception& e) {
      std::printf("  FAIL %-8s imwrite threw: %s\n", ext, e.what());
      ++fail;
    }
    // imencode (the memory-only path ScreenshotService uses)
    try {
      std::vector<unsigned char> buf;
      bool ok = cv::imencode(ext, img, buf);
      std::printf("  %s %-8s imencode -> %s (%zu bytes)\n", ok ? "ok  " : "FAIL", ext,
                  ok ? "encoded" : "returned false", buf.size());
      if (!ok) ++fail;
    } catch (const cv::Exception& e) {
      std::printf("  FAIL %-8s imencode threw: %s\n", ext, e.what());
      ++fail;
    }
  }

  std::printf("opencv_probe: %s\n", fail ? "FAIL (imgcodecs missing codecs)" : "PASS (all formats ok)");
  return fail ? 1 : 0;
}
