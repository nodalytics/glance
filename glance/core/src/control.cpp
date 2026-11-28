#include "control.h"

#include <algorithm>
#include <tuple>
#include <vector>

namespace glance::control {

namespace {

// ---- the null backend (headless machines, selftest) ------------------------

class NullScreen : public Screen {
 public:
  bool grab(int x, int y, int w, int h, cv::Mat& out) override {
    // A deterministic checkerboard so callers can still exercise plumbing:
    // it is NOT pixels of any real display (x/y are the requested screen
    // rectangle; the null backend serves the same emulated desktop for all).
    (void)x;
    (void)y;
    out.create(h, w, CV_8UC3);
    for (int yy = 0; yy < h; yy += 16)
      for (int xx = 0; xx < w; xx += 16)
        out(cv::Rect(std::max(0, xx), std::max(0, yy),
                     std::min(w - xx, 16), std::min(h - yy, 16))) =
            (((xx + yy) / 16) % 2 == 0) ? cv::Scalar(40, 40, 40) : cv::Scalar(60, 60, 60);
    return true;
  }
  bool grab_all(cv::Mat& out) override { return grab(0, 0, 1600, 900, out); }
  bool display_size(int& w, int& h) override {
    w = 1600;
    h = 900;
    return true;
  }
  std::string backend_name() const override { return "null"; }
};

class NullInput : public Input {
 public:
  void move_to(int x, int y) override {
    last_x_ = x;
    last_y_ = y;
  }
  void click(int x, int y, Button button = Left) override {
    last_x_ = x;
    last_y_ = y;
    clicks_.emplace_back(x, y, static_cast<int>(button));
  }
  bool press_key(const std::string& keysym) override {
    keys_.push_back(keysym);
    return true;
  }
  bool type_text(const std::string& text) override {
    typed_ += text;
    return true;
  }

  int last_x() const { return last_x_; }
  int last_y() const { return last_y_; }
  std::vector<std::tuple<int, int, int>> clicks() const { return clicks_; }
  std::vector<std::string> keys() const { return keys_; }
  std::string typed() const { return typed_; }

 private:
  int last_x_ = -1, last_y_ = -1;
  std::vector<std::tuple<int, int, int>> clicks_;
  std::vector<std::string> keys_;
  std::string typed_;
};

}  // namespace

Backend make_null() {
  Backend b;
  b.name = "null";
  b.screen = std::make_shared<NullScreen>();
  b.input = std::make_shared<NullInput>();
  return b;
}

Backend make_default() {
  // Exactly one platform backend can be compiled in (each is guarded by its
  // OS macro and its CMake option). Each fails its calls, not its
  // construction, when there is no usable display / permission, so selecting
  // it here costs nothing on headless hosts.
#if defined(__linux__) && defined(GLANCE_X11)
  return make_x11();
#elif defined(_WIN32) && defined(GLANCE_WIN32)
  return make_win32();
#elif defined(__APPLE__) && defined(GLANCE_MACOS)
  return make_macos();
#else
  return make_null();
#endif
}

// ---- action resolution ------------------------------------------------------

std::optional<ActionPoint> resolve_action(const TableMapping& mapping,
                                          const cv::Point& table_origin, bool table_found,
                                          const std::string& name) {
  std::string target;
  if (!mapping.action_target(name, target))
    return std::nullopt;
  if (target.rfind("button:", 0) == 0) {
    const std::string btn = target.substr(7);
    for (const auto& b : mapping.buttons())
      if (b.name == btn) {
        if (!table_found) return std::nullopt;
        ActionPoint p;
        p.kind = "button";
        p.x = table_origin.x + (b.area.x1 + b.area.x2) / 2;
        p.y = table_origin.y + (b.area.y1 + b.area.y2) / 2;
        return p;
      }
    return std::nullopt;  // unknown button name
  }
  if (target.rfind("stack:", 0) == 0) {
    const std::string key = target.substr(6);
    for (const auto& s : mapping.stacks())
      if (s.key == key) {
        if (!table_found) return std::nullopt;
        ActionPoint p;
        p.kind = "stack";
        p.x = table_origin.x + (s.area.x1 + s.area.x2) / 2;
        p.y = table_origin.y + (s.area.y1 + s.area.y2) / 2;
        return p;
      }
    return std::nullopt;  // unknown stack key
  }
  return std::nullopt;  // malformed target
}

}  // namespace glance::control
