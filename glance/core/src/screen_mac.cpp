// macOS screen + input backend, plain C++ over the CoreGraphics C API (no
// Objective-C). The screen path captures the on-screen window list
// composited over a rectangle (CGWindowListCreateImage) and draws it into a
// BGRA bitmap context; window lookup uses CGWindowListCopyWindowInfo; input
// is CGEvent mouse/keyboard events posted at the HID tap.
//
// Coordinate space (same contract as control.h: screen-absolute PIXELS):
//   Quartz global coordinates are POINTS with the origin at the top-left of
//   the main display (y grows down; displays left of / above it are
//   negative). glance space = (quartz_point - desktop_origin) * scale, where
//   desktop_origin is the top-left of the union of all active displays (so
//   glance's 0,0 is the virtual desktop's top-left, as on X11/Win32) and
//   scale is the MAIN display's backing scale factor (2 on Retina). A grab
//   therefore returns a w x h image at native Retina resolution, and the
//   same numbers fed back to click()/move_to() land on the same pixels. On a
//   multi-display setup with mixed scale factors, secondary displays are
//   resampled to the main display's scale (glance space stays uniform).
//
// Permissions (System Settings > Privacy & Security), granted to the binary
// or to the terminal that launches it:
//   * Screen Recording — without it grabs come back with only the desktop
//     and glance's own windows, and other apps' window titles are hidden from
//     CGWindowListCopyWindowInfo (locate_window then matches owner names only).
//   * Accessibility — without it CGEventPost is silently dropped.
//
// Deprecation: CGWindowListCreateImage / CGDisplayCreateImageForRect are
// deprecated since macOS 14 and marked obsoleted in the macOS 15 SDK
// (compile error when the deployment target is >= 15). They are therefore
// resolved at RUNTIME with dlsym, so this file compiles against any SDK; on
// an OS where neither symbol exists any more, grabs fail with a message.
// The replacement is ScreenCaptureKit (SCScreenshotManager, macOS 14+, an
// Objective-C/Swift async API) — future work for a screen_mac.mm.
//
// This file only compiles when GLANCE_MACOS is defined (CMake sets it on
// Apple platforms unless -DGLANCE_MACOS=OFF); otherwise the null backend is
// used.

#if defined(__APPLE__) && defined(GLANCE_MACOS)

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <mutex>
#include <string>
#include <vector>

// OpenCV (via control.h) before the Apple headers, so no Apple macro can leak
// into OpenCV's declarations. AssertMacros.h (pulled in by some Apple
// umbrella headers) would otherwise define lower-case check()/verify()
// macros.
#include "control.h"

#include <opencv2/imgproc.hpp>

#ifndef __ASSERT_MACROS_DEFINE_VERSIONS_WITHOUT_UNDERSCORES
#define __ASSERT_MACROS_DEFINE_VERSIONS_WITHOUT_UNDERSCORES 0
#endif
#include <CoreFoundation/CoreFoundation.h>
#include <CoreGraphics/CoreGraphics.h>
#include <dlfcn.h>

namespace glance::control {

namespace {

// ---- desktop geometry --------------------------------------------------------

struct Desktop {
  double ox = 0, oy = 0;  // top-left of the union of active displays (points)
  double pw = 0, ph = 0;  // union size (points)
  double scale = 1;       // main display backing scale factor (pixels/point)
  bool ok = false;
};

Desktop desktop() {
  Desktop d;
  CGDirectDisplayID ids[32];
  uint32_t n = 0;
  if (CGGetActiveDisplayList(32, ids, &n) != kCGErrorSuccess || n == 0) return d;
  double x0 = 1e18, y0 = 1e18, x1 = -1e18, y1 = -1e18;
  for (uint32_t i = 0; i < n; ++i) {
    const CGRect b = CGDisplayBounds(ids[i]);
    x0 = std::min(x0, (double)b.origin.x);
    y0 = std::min(y0, (double)b.origin.y);
    x1 = std::max(x1, (double)(b.origin.x + b.size.width));
    y1 = std::max(y1, (double)(b.origin.y + b.size.height));
  }
  d.ox = x0;
  d.oy = y0;
  d.pw = x1 - x0;
  d.ph = y1 - y0;
  if (CGDisplayModeRef mode = CGDisplayCopyDisplayMode(CGMainDisplayID())) {
    const size_t px = CGDisplayModeGetPixelWidth(mode);
    const size_t pt = CGDisplayModeGetWidth(mode);
    if (px > 0 && pt > 0) d.scale = (double)px / (double)pt;
    CGDisplayModeRelease(mode);
  }
  d.ok = d.pw > 0 && d.ph > 0;
  return d;
}

int desktop_px_w(const Desktop& d) { return (int)std::lround(d.pw * d.scale); }
int desktop_px_h(const Desktop& d) { return (int)std::lround(d.ph * d.scale); }

// glance pixel -> Quartz global point.
CGPoint to_quartz(const Desktop& d, int x, int y) {
  return CGPointMake((CGFloat)(d.ox + x / d.scale), (CGFloat)(d.oy + y / d.scale));
}

// ---- deprecated capture entry points, resolved at runtime ---------------------

using WindowListCreateImageFn = CGImageRef (*)(CGRect, CGWindowListOption, CGWindowID,
                                               CGWindowImageOption);
using DisplayCreateImageForRectFn = CGImageRef (*)(CGDirectDisplayID, CGRect);

struct CaptureFns {
  WindowListCreateImageFn window_list = nullptr;
  DisplayCreateImageForRectFn display_rect = nullptr;
};

const CaptureFns& capture_fns() {
  static CaptureFns fns;
  static std::once_flag once;
  std::call_once(once, [] {
    fns.window_list =
        reinterpret_cast<WindowListCreateImageFn>(dlsym(RTLD_DEFAULT, "CGWindowListCreateImage"));
    fns.display_rect = reinterpret_cast<DisplayCreateImageForRectFn>(
        dlsym(RTLD_DEFAULT, "CGDisplayCreateImageForRect"));
  });
  return fns;
}

bool warn_once(const char* msg) {
  static std::once_flag once;
  std::call_once(once, [msg] { std::fprintf(stderr, "glance: control: %s\n", msg); });
  return false;
}

// Capture the Quartz-point rectangle `r` and render it into a w x h BGR
// image (CGContextDrawImage resamples when the capture's pixel size differs,
// e.g. a non-Retina secondary display).
bool capture(CGRect r, int w, int h, cv::Mat& out) {
  const CaptureFns& fns = capture_fns();
  CGImageRef img = nullptr;
  if (fns.window_list) {
    img = fns.window_list(r, kCGWindowListOptionOnScreenOnly, kCGNullWindowID,
                          kCGWindowImageDefault);
  } else if (fns.display_rect) {
    // Fallback: main display only (rect is display-local for this call).
    const CGRect mb = CGDisplayBounds(CGMainDisplayID());
    img = fns.display_rect(CGMainDisplayID(),
                           CGRectMake(r.origin.x - mb.origin.x, r.origin.y - mb.origin.y,
                                      r.size.width, r.size.height));
  } else {
    return warn_once(
        "no CoreGraphics screen-capture entry point on this macOS (ScreenCaptureKit backend "
        "not implemented yet)");
  }
  if (!img)
    return warn_once("screen capture failed (grant Screen Recording permission to glance)");

  cv::Mat bgra(h, w, CV_8UC4, cv::Scalar(0, 0, 0, 255));
  CGColorSpaceRef cs = CGColorSpaceCreateDeviceRGB();
  // Premultiplied-first alpha + 32-bit little-endian = bytes B,G,R,A in
  // memory, i.e. OpenCV's BGRA. Row 0 of the buffer is the TOP of the image.
  const uint32_t info = (uint32_t)kCGImageAlphaPremultipliedFirst | (uint32_t)kCGBitmapByteOrder32Little;
  CGContextRef ctx = CGBitmapContextCreate(bgra.data, (size_t)w, (size_t)h, 8, bgra.step[0], cs,
                                           static_cast<CGBitmapInfo>(info));
  CGColorSpaceRelease(cs);
  if (!ctx) {
    CGImageRelease(img);
    return false;
  }
  CGContextSetInterpolationQuality(ctx, kCGInterpolationHigh);
  CGContextDrawImage(ctx, CGRectMake(0, 0, (CGFloat)w, (CGFloat)h), img);
  CGContextRelease(ctx);
  CGImageRelease(img);
  cv::cvtColor(bgra, out, cv::COLOR_BGRA2BGR);
  return true;
}

// ---- CoreFoundation helpers ------------------------------------------------------

CFStringRef cfstr(const std::string& s) {
  return CFStringCreateWithCString(kCFAllocatorDefault, s.c_str(), kCFStringEncodingUTF8);
}

bool cf_contains(const void* hay, CFStringRef needle) {
  if (!hay || CFGetTypeID((CFTypeRef)hay) != CFStringGetTypeID()) return false;
  const CFRange r = CFStringFind((CFStringRef)hay, needle, kCFCompareCaseInsensitive);
  return r.location != kCFNotFound;
}

int cf_int(const void* v, int fallback) {
  int out = fallback;
  if (v && CFGetTypeID((CFTypeRef)v) == CFNumberGetTypeID())
    CFNumberGetValue((CFNumberRef)v, kCFNumberIntType, &out);
  return out;
}

// ---- keyboard ------------------------------------------------------------------

// Hardware virtual key codes (HIToolbox/Events.h kVK_*, stable across
// layouts for the non-character keys).
int named_keycode(const std::string& k) {
  struct Entry {
    const char* name;
    int code;
  };
  static const Entry table[] = {
      {"Return", 0x24},   {"KP_Enter", 0x4C},  {"Tab", 0x30},       {"space", 0x31},
      {"BackSpace", 0x33}, {"Escape", 0x35},   {"Delete", 0x75},    {"Home", 0x73},
      {"End", 0x77},      {"Prior", 0x74},     {"Page_Up", 0x74},   {"Next", 0x79},
      {"Page_Down", 0x79}, {"Left", 0x7B},     {"Right", 0x7C},     {"Down", 0x7D},
      {"Up", 0x7E},       {"Shift_L", 0x38},   {"Shift_R", 0x3C},   {"Control_L", 0x3B},
      {"Control_R", 0x3E}, {"Alt_L", 0x3A},    {"Alt_R", 0x3D},     {"Super_L", 0x37},
      {"Super_R", 0x36},  {"Caps_Lock", 0x39}, {"Help", 0x72},
      {"F1", 0x7A},       {"F2", 0x78},        {"F3", 0x63},        {"F4", 0x76},
      {"F5", 0x60},       {"F6", 0x61},        {"F7", 0x62},        {"F8", 0x64},
      {"F9", 0x65},       {"F10", 0x6D},       {"F11", 0x67},       {"F12", 0x6F},
      {"F13", 0x69},      {"F14", 0x6B},       {"F15", 0x71},       {"F16", 0x6A},
      {"F17", 0x40},      {"F18", 0x4F},       {"F19", 0x50},       {"F20", 0x5A},
  };
  for (const auto& e : table)
    if (k == e.name) return e.code;
  return -1;
}

// ANSI-layout key codes for letters and digits (kVK_ANSI_*). Used so apps
// that read key codes (shortcuts) see the expected key; the typed character
// itself is always attached as the event's Unicode string.
int ansi_keycode(char c) {
  static const char* const by_code =
      "asdfhgzxcv\0bqweryt123465=97-80]ou[ip\0lj'k;\\,/nm.";  // index = key code
  const char lc = (c >= 'A' && c <= 'Z') ? (char)(c - 'A' + 'a') : c;
  if (!((lc >= 'a' && lc <= 'z') || (lc >= '0' && lc <= '9'))) return -1;
  for (int i = 0; i < 48; ++i)
    if (by_code[i] == lc) return i;
  return -1;
}

// X11 Latin-1 keysym names -> character (single-character names are
// themselves), mirroring XStringToKeysym on the X11 backend.
char keysym_char(const std::string& k) {
  if (k.size() == 1 && (unsigned char)k[0] >= 0x20 && (unsigned char)k[0] < 0x7f) return k[0];
  struct Entry {
    const char* name;
    char ch;
  };
  static const Entry table[] = {
      {"exclam", '!'},      {"quotedbl", '"'},    {"numbersign", '#'}, {"dollar", '$'},
      {"percent", '%'},     {"ampersand", '&'},   {"apostrophe", '\''}, {"parenleft", '('},
      {"parenright", ')'},  {"asterisk", '*'},    {"plus", '+'},       {"comma", ','},
      {"minus", '-'},       {"period", '.'},      {"slash", '/'},      {"colon", ':'},
      {"semicolon", ';'},   {"less", '<'},        {"equal", '='},      {"greater", '>'},
      {"question", '?'},    {"at", '@'},          {"bracketleft", '['}, {"backslash", '\\'},
      {"bracketright", ']'}, {"asciicircum", '^'}, {"underscore", '_'}, {"grave", '`'},
      {"braceleft", '{'},   {"bar", '|'},         {"braceright", '}'}, {"asciitilde", '~'},
  };
  for (const auto& e : table)
    if (k == e.name) return e.ch;
  return 0;
}

CGEventSourceRef event_source() {
  // Process-lifetime source; never released.
  static CGEventSourceRef src = CGEventSourceCreate(kCGEventSourceStateHIDSystemState);
  return src;
}

// Post one key down+up. `units` (UTF-16), when non-empty, is attached as the
// typed text so the receiving app gets exactly that character regardless of
// the keyboard layout. Flags are set explicitly so held physical modifiers
// do not leak into synthetic keys.
bool post_key(int keycode, const std::vector<UniChar>& units, CGEventFlags flags) {
  for (int down = 1; down >= 0; --down) {
    CGEventRef ev = CGEventCreateKeyboardEvent(event_source(), (CGKeyCode)keycode, down != 0);
    if (!ev) return false;
    CGEventSetFlags(ev, flags);
    if (!units.empty()) CGEventKeyboardSetUnicodeString(ev, (UniCharCount)units.size(), units.data());
    CGEventPost(kCGHIDEventTap, ev);
    CFRelease(ev);
  }
  return true;
}

bool post_char(char32_t cp) {
  std::vector<UniChar> units;
  if (cp >= 0x10000) {
    cp -= 0x10000;
    units.push_back((UniChar)(0xD800 + (cp >> 10)));
    units.push_back((UniChar)(0xDC00 + (cp & 0x3FF)));
  } else {
    units.push_back((UniChar)cp);
  }
  int code = -1;
  CGEventFlags flags = static_cast<CGEventFlags>(0);
  if (cp < 0x80) {
    code = ansi_keycode((char)cp);
    if (cp >= 'A' && cp <= 'Z') flags = kCGEventFlagMaskShift;
    if (cp == ' ') code = 0x31;
  }
  // No layout key for it: key code 0 carrying the Unicode string (what Cocoa
  // text input consumes).
  return post_key(code >= 0 ? code : 0, units, flags);
}

// Minimal UTF-8 decoder (invalid bytes are skipped).
std::vector<char32_t> utf8_decode(const std::string& s) {
  std::vector<char32_t> out;
  for (size_t i = 0; i < s.size();) {
    const unsigned char c = (unsigned char)s[i];
    int len = c < 0x80 ? 1 : (c >> 5) == 0x6 ? 2 : (c >> 4) == 0xE ? 3 : (c >> 3) == 0x1E ? 4 : 0;
    if (len == 0 || i + (size_t)len > s.size()) {
      ++i;
      continue;
    }
    char32_t cp = len == 1 ? c : len == 2 ? (c & 0x1F) : len == 3 ? (c & 0x0F) : (c & 0x07);
    bool ok = true;
    for (int k = 1; k < len; ++k) {
      const unsigned char cc = (unsigned char)s[i + (size_t)k];
      if ((cc >> 6) != 0x2) ok = false;
      cp = (cp << 6) | (cc & 0x3F);
    }
    i += ok ? (size_t)len : 1;
    if (ok) out.push_back(cp);
  }
  return out;
}

}  // namespace

class MacScreen : public Screen {
 public:
  bool grab(int x, int y, int w, int h, cv::Mat& out) override {
    const Desktop d = desktop();
    if (!d.ok) return warn_once("no active display (macos)");
    const int dw = desktop_px_w(d), dh = desktop_px_h(d);
    if (x < 0) {
      w += x;
      x = 0;
    }
    if (y < 0) {
      h += y;
      y = 0;
    }
    w = std::min(w, dw - x);
    h = std::min(h, dh - y);
    if (w < 1 || h < 1) return false;
    const CGPoint p = to_quartz(d, x, y);
    const CGRect r = CGRectMake(p.x, p.y, (CGFloat)(w / d.scale), (CGFloat)(h / d.scale));
    return capture(r, w, h, out);
  }

  bool grab_all(cv::Mat& out) override {
    const Desktop d = desktop();
    if (!d.ok) return warn_once("no active display (macos)");
    return grab(0, 0, desktop_px_w(d), desktop_px_h(d), out);
  }

  bool display_size(int& w, int& h) override {
    const Desktop d = desktop();
    if (!d.ok) return false;
    w = desktop_px_w(d);
    h = desktop_px_h(d);
    return true;
  }

  // Front-to-back over on-screen, normal-layer windows; matches the window
  // title (kCGWindowName, visible to us only with Screen Recording
  // permission) first, else the owning app's name (kCGWindowOwnerName). The
  // frame is kCGWindowBounds — the whole window including its title bar
  // (macOS has no separate client-area rectangle in this API).
  bool locate_window(const std::string& title, int& x, int& y, int& w, int& h) override {
    if (title.empty()) return false;
    CFStringRef needle = cfstr(title);
    if (!needle) return false;
    CFArrayRef list = CGWindowListCopyWindowInfo(
        kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements, kCGNullWindowID);
    if (!list) {
      CFRelease(needle);
      return false;
    }
    bool found = false;
    CGRect bounds = CGRectZero;
    for (int pass = 0; pass < 2 && !found; ++pass) {
      const CFIndex n = CFArrayGetCount(list);
      for (CFIndex i = 0; i < n && !found; ++i) {
        auto info = (CFDictionaryRef)CFArrayGetValueAtIndex(list, i);
        if (!info || cf_int(CFDictionaryGetValue(info, kCGWindowLayer), -1) != 0) continue;
        const void* name = CFDictionaryGetValue(info, pass == 0 ? kCGWindowName : kCGWindowOwnerName);
        if (!cf_contains(name, needle)) continue;
        auto bdict = (CFDictionaryRef)CFDictionaryGetValue(info, kCGWindowBounds);
        if (bdict && CGRectMakeWithDictionaryRepresentation(bdict, &bounds) &&
            bounds.size.width > 0 && bounds.size.height > 0)
          found = true;
      }
    }
    CFRelease(list);
    CFRelease(needle);
    if (!found) return false;
    const Desktop d = desktop();
    if (!d.ok) return false;
    x = (int)std::lround((bounds.origin.x - d.ox) * d.scale);
    y = (int)std::lround((bounds.origin.y - d.oy) * d.scale);
    w = (int)std::lround(bounds.size.width * d.scale);
    h = (int)std::lround(bounds.size.height * d.scale);
    return true;
  }

  std::string backend_name() const override { return "macos"; }
};

class MacInput : public Input {
 public:
  void move_to(int x, int y) override {
    const Desktop d = desktop();
    if (!d.ok) return;
    post_mouse(kCGEventMouseMoved, to_quartz(d, x, y), kCGMouseButtonLeft);
  }

  void click(int x, int y, Button button = Left) override {
    const Desktop d = desktop();
    if (!d.ok) return;
    const CGPoint p = to_quartz(d, x, y);
    CGEventType down = kCGEventLeftMouseDown, up = kCGEventLeftMouseUp;
    CGMouseButton b = kCGMouseButtonLeft;
    if (button == Right) {
      down = kCGEventRightMouseDown;
      up = kCGEventRightMouseUp;
      b = kCGMouseButtonRight;
    } else if (button == Middle) {
      down = kCGEventOtherMouseDown;
      up = kCGEventOtherMouseUp;
      b = kCGMouseButtonCenter;
    }
    post_mouse(kCGEventMouseMoved, p, kCGMouseButtonLeft);
    post_mouse(down, p, b);
    post_mouse(up, p, b);
  }

  bool press_key(const std::string& keysym) override {
    if (keysym.empty()) return false;
    const int code = named_keycode(keysym);
    if (code >= 0) {
      // Return/Tab/space carry their character too, like a real keystroke.
      std::vector<UniChar> units;
      if (keysym == "Return" || keysym == "KP_Enter") units.push_back('\r');
      else if (keysym == "Tab") units.push_back('\t');
      else if (keysym == "space") units.push_back(' ');
      return post_key(code, units, static_cast<CGEventFlags>(0));
    }
    if (const char ch = keysym_char(keysym)) return post_char((char32_t)(unsigned char)ch);
    return false;  // unknown keysym name (X11 parity)
  }

  bool type_text(const std::string& text) override {
    bool ok = true;
    for (const char32_t cp : utf8_decode(text)) {
      if (cp == U'\n') ok = post_key(0x24, {'\r'}, static_cast<CGEventFlags>(0)) && ok;
      else if (cp == U'\t') ok = post_key(0x30, {'\t'}, static_cast<CGEventFlags>(0)) && ok;
      else if (cp >= 0x20 && cp != 0x7f) ok = post_char(cp) && ok;
    }
    return ok;
  }

 private:
  static void post_mouse(CGEventType type, CGPoint p, CGMouseButton b) {
    CGEventRef ev = CGEventCreateMouseEvent(event_source(), type, p, b);
    if (!ev) return;
    if (type != kCGEventMouseMoved) CGEventSetIntegerValueField(ev, kCGMouseEventClickState, 1);
    CGEventPost(kCGHIDEventTap, ev);
    CFRelease(ev);
  }
};

Backend make_macos() {
  Backend b;
  b.name = "macos";
  b.screen = std::make_shared<MacScreen>();
  b.input = std::make_shared<MacInput>();
  return b;
}

}  // namespace glance::control

#endif  // __APPLE__ && GLANCE_MACOS
