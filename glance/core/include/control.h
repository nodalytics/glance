#pragma once

#include <memory>
#include <optional>
#include <string>

#include "mapping.h"

#include <opencv2/core.hpp>

namespace glance::control {

// The platform screen: source of pixel grabs. A grab is a rectangular region
// in screen-absolute pixels (the top-left of the virtual desktop is 0,0)
// returned as BGR 8UC3. The implementation decides which display/window it
// comes from; the rest of glance only knows this interface (the layering rule
// is the same as for OCR: the backend is optional, found at configure time).
class Screen {
 public:
  virtual ~Screen() = default;
  // Grab a rectangular region (x,y,w,h are screen-absolute). Out of bounds
  // values are clamped by the backend.
  virtual bool grab(int x, int y, int w, int h, cv::Mat& out) = 0;
  // Grab the entire virtual desktop.
  virtual bool grab_all(cv::Mat& out) = 0;
  // The virtual desktop's dimensions. Default: unsupported.
  virtual bool display_size(int& w, int& h) {
    (void)w;
    (void)h;
    return false;
  }
  // Find a top-level window by title (case-insensitive substring) and report
  // its screen-absolute frame. Default: unsupported.
  virtual bool locate_window(const std::string& title, int& x, int& y, int& w, int& h) {
    (void)title;
    (void)x;
    (void)y;
    (void)w;
    (void)h;
    return false;
  }
  // Human-readable name of the backend ("null", "x11", "win32").
  virtual std::string backend_name() const = 0;
};

// The platform input: synthetic mouse/keyboard. Coordinates are
// screen-absolute, same space as Screen::grab.
class Input {
 public:
  enum Button { Left = 1, Middle = 2, Right = 3 };

  virtual ~Input() = default;
  virtual void move_to(int x, int y) = 0;
  virtual void click(int x, int y, Button button = Left) = 0;
  // Press one named key ("Return", "Tab", "F5", "9", ...). Names are the X
  // keysym names on X11; the same names map to their platform equivalents
  // elsewhere where they exist.
  virtual bool press_key(const std::string& keysym) = 0;
  // Type a short string of printable ASCII (chip amounts, chat) as key
  // presses.
  virtual bool type_text(const std::string& text) = 0;
};

// A backend = screen + input + name. make_default() returns the platform
// backend when one was compiled in, else the null backend (name "null",
// screen/input present but no-op) — the same configure-time-optional pattern
// as tesseract: the build never breaks, and a headless machine reports "no
// display" at runtime instead of refusing to start.
struct Backend {
  std::string name = "null";
  // shared_ptr, not unique_ptr: the selftest (and any host process) may share
  // one fake Screen/Input across several services, and the backend's
  // ownership is not exclusive to it.
  std::shared_ptr<Screen> screen;
  std::shared_ptr<Input> input;
};

Backend make_default();

// A no-op backend used when the platform has no display (selftest drives its
// own fakes; this is the factory's fallback on headless machines).
Backend make_null();

#if defined(__linux__) && defined(GLANCE_X11)
// The Linux/X11 backend (screen via XGetImage, input via XTest). Only present
// when CMake found the X development packages; every method degrades to
// false/no-op at runtime when there is no openable display.
Backend make_x11();
#endif

// The mapping's "actions" section: named click targets. A target is
// "button:<name>" (a rectangle from the mapping's "buttons") or
// "stack:<key>" (a rectangle from "stacks"). Resolving an action against the
// table's anchored origin in the last grab yields the screen-absolute centre
// of the target — nothing in this function knows what an action *means*, only
// where to click.
struct ActionPoint {
  int x = 0;  // screen-absolute centre
  int y = 0;
  std::string kind;  // "button" or "stack"
};

// nullopt for unknown actions, unknown target names, malformed targets, or a
// table whose anchor was not found in the grab being controlled from.
std::optional<ActionPoint> resolve_action(const glance::TableMapping& mapping,
                                          const cv::Point& table_origin, bool table_found,
                                          const std::string& name);

}  // namespace glance::control
