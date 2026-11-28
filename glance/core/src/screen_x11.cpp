// X11 screen + input backend (Linux). The screen path uses XGetImage on the
// root window (full-desktop and region grabs; works on Xorg and on an
// XWayland X server). The input path uses the XTest extension — the standard
// protocol for synthetic input, the same calls xdotool makes.
//
// This file only compiles when GLANCE_X11 is defined: CMake looks for libX11
// + the XTest header at configure time, and on a machine without them the
// null backend (control.cpp) is used instead. At runtime, every call checks
// whether a display actually opened and degrades to false/no-op, so the
// backend is safe to select on headless hosts too — the server reports
// "no display" instead of refusing to start.

#if defined(__linux__) && defined(GLANCE_X11)

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <mutex>
#include <string>

#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/Xatom.h>
#include <X11/XKBlib.h>
#include <X11/keysym.h>
#include <X11/extensions/XTest.h>

// Legacy X11 header constants that collide with OpenCV identifiers:
// X.h `#define Complex 0` (a polygon-shape constant) and
// X11/extensions/XI.h `#define COUNT 0` (an XI event constant). If the
// OpenCV headers are parsed while either macro is live, cv::Complex<T> and
// cv::TermCriteria::Type (whose enumerators are named COUNT/EPS) are
// macro-mangled into garbage. Undefine both before control.h pulls in
// opencv2/core.hpp; nothing in this file uses the X constants.
#undef Complex
#undef COUNT

#include "control.h"

namespace glance::control {

namespace {

// One shared X connection per process, opened at first use. Xlib is not
// multithreaded: every call that touches the Display takes c->lock first; the
// lock is non-recursive, so the *_locked helpers never take it themselves.
struct XConn {
  Display* dpy = nullptr;
  int screen = 0;
  std::mutex lock;  // guards all dpy usage

  XConn() {
    dpy = ::XOpenDisplay(std::getenv("DISPLAY"));
    if (dpy) screen = DefaultScreen(dpy);
  }
  ~XConn() {
    if (dpy) XCloseDisplay(dpy);
  }
};

XConn* g_x() {
  static XConn conn;
  return conn.dpy ? &conn : nullptr;
}

// Visual channel layout: a channel's pixel bits start at `shift` and span
// `mask`. Derived from the image's actual red/green/blue masks, never assumed
// — 24-bit TrueColor on a little-endian Xorg (the usual case) comes out
// BGR-in-the-low-24-bits, but 15/16/30-bit visuals stay correct too. Channels
// wider or narrower than 8 bits are rescaled to 0..255.
struct Channel {
  int shift = 0;
  unsigned long mask = 0xff;
  unsigned char value(unsigned long px) const {
    const unsigned long v = (px >> shift) & mask;
    return mask == 0xff ? (unsigned char)v : (unsigned char)((v * 255ul) / mask);
  }
};

Channel channel_of(unsigned long m, int fallback_shift) {
  Channel c;
  if (m == 0) {
    c.shift = fallback_shift;
    return c;
  }
  while ((m & 1ul) == 0) {
    m >>= 1;
    c.shift++;
  }
  c.mask = m;
  return c;
}

// Decodes an XGetImage buffer into BGR 8UC3.
bool decode_image(XImage* img, cv::Mat& out) {
  const Channel cr = channel_of(img->red_mask, 16);
  const Channel cg = channel_of(img->green_mask, 8);
  const Channel cb = channel_of(img->blue_mask, 0);
  const int w = img->width;
  const int h = img->height;
  out.create(h, w, CV_8UC3);
  if (img->bits_per_pixel == 32 && img->byte_order == LSBFirst) {
    // Fast path (the overwhelming default on little-endian Xorg): 32-bit
    // pixels. Read them as uint32 — `unsigned long` is 64-bit on LP64 Linux.
    for (int yy = 0; yy < h; ++yy) {
      const auto* row = reinterpret_cast<const unsigned char*>(img->data) + (size_t)yy * img->bytes_per_line;
      auto* d = out.ptr<unsigned char>(yy);
      for (int xx = 0; xx < w; ++xx) {
        uint32_t px;
        std::memcpy(&px, row + (size_t)xx * 4, 4);
        d[xx * 3 + 0] = cb.value(px);
        d[xx * 3 + 1] = cg.value(px);
        d[xx * 3 + 2] = cr.value(px);
      }
    }
  } else {
    // Everything else (16-bit depths, other byte orders): per-pixel, slower
    // but always correct.
    for (int yy = 0; yy < h; ++yy) {
      auto* d = out.ptr<unsigned char>(yy);
      for (int xx = 0; xx < w; ++xx) {
        const unsigned long px = XGetPixel(img, xx, yy);
        d[xx * 3 + 0] = cb.value(px);
        d[xx * 3 + 1] = cg.value(px);
        d[xx * 3 + 2] = cr.value(px);
      }
    }
  }
  return true;
}

// Window title: _NET_WM_NAME (UTF-8) preferred, WM_NAME (Latin-1) fallback.
std::string window_title_of(XConn* c, Window win) {
  for (int i = 0; i < 2; ++i) {
    const Atom prop = i == 0 ? XInternAtom(c->dpy, "_NET_WM_NAME", False) : XA_WM_NAME;
    const Atom type = i == 0 ? XInternAtom(c->dpy, "UTF8_STRING", False) : XA_STRING;
    Atom actual = 0;
    int format = 0;
    unsigned long nitems = 0, bytes_after = 0;
    unsigned char* val = nullptr;
    // XGetWindowProperty returns Success (0) on success.
    if (XGetWindowProperty(c->dpy, win, prop, 0, 1024, False, type, &actual, &format, &nitems,
                           &bytes_after, &val) != Success)
      continue;
    std::string s;
    if (val && nitems > 0 && format == 8) {
      s.assign(reinterpret_cast<const char*>(val), nitems);
      const size_t nul = s.find('\0');
      if (nul != std::string::npos) s.erase(nul);
    }
    if (val) XFree(val);
    if (!s.empty()) return s;
  }
  return std::string();
}

std::string to_lower(std::string s) {
  for (char& ch : s) ch = (char)std::tolower((unsigned char)ch);
  return s;
}

// Depth-first search for a viewable window whose title contains `needle`
// (lower-case). Window managers reparent clients into frames, so the title
// usually lives one or two levels below the root's children.
bool find_window(XConn* c, Window win, const std::string& needle, int depth, Window& hit) {
  XWindowAttributes wa;
  // Xlib Status: nonzero on success.
  if (!XGetWindowAttributes(c->dpy, win, &wa)) return false;
  if (depth > 0 && wa.map_state == IsViewable) {
    const std::string nm = to_lower(window_title_of(c, win));
    if (!nm.empty() && nm.find(needle) != std::string::npos) {
      hit = win;
      return true;
    }
  }
  if (depth >= 4) return false;
  Window root_ret = 0, parent_ret = 0;
  Window* children = nullptr;
  unsigned int n = 0;
  if (!XQueryTree(c->dpy, win, &root_ret, &parent_ret, &children, &n)) return false;
  bool found = false;
  // Children come bottom-to-top in stacking order: search the top first.
  for (unsigned int i = n; i-- > 0 && !found;) found = find_window(c, children[i], needle, depth + 1, hit);
  if (children) XFree(children);
  return found;
}

}  // namespace

class X11Screen : public Screen {
  // Called with c->lock held. Out-of-bounds requests are clamped to the
  // display.
  bool grab_locked(XConn* c, int x, int y, int w, int h, cv::Mat& out) {
    const int sw = DisplayWidth(c->dpy, c->screen);
    const int sh = DisplayHeight(c->dpy, c->screen);
    if (x < 0) {
      w += x;
      x = 0;
    }
    if (y < 0) {
      h += y;
      y = 0;
    }
    w = std::min(w, sw - x);
    h = std::min(h, sh - y);
    if (w < 1 || h < 1) return false;
    XImage* img = XGetImage(c->dpy, RootWindow(c->dpy, c->screen), x, y, (unsigned)w, (unsigned)h,
                            AllPlanes, ZPixmap);
    if (!img) return false;
    const bool ok = decode_image(img, out);
    XDestroyImage(img);
    return ok;
  }

 public:
  bool grab(int x, int y, int w, int h, cv::Mat& out) override {
    auto* c = g_x();
    if (!c) return no_display();
    std::lock_guard<std::mutex> g(c->lock);
    return grab_locked(c, x, y, w, h, out);
  }
  bool grab_all(cv::Mat& out) override {
    auto* c = g_x();
    if (!c) return no_display();
    std::lock_guard<std::mutex> g(c->lock);
    return grab_locked(c, 0, 0, DisplayWidth(c->dpy, c->screen), DisplayHeight(c->dpy, c->screen),
                       out);
  }
  bool display_size(int& w, int& h) override {
    auto* c = g_x();
    if (!c) return false;
    std::lock_guard<std::mutex> g(c->lock);
    w = DisplayWidth(c->dpy, c->screen);
    h = DisplayHeight(c->dpy, c->screen);
    return true;
  }
  bool locate_window(const std::string& title, int& x, int& y, int& w, int& h) override {
    if (title.empty()) return false;
    auto* c = g_x();
    if (!c) return false;
    std::lock_guard<std::mutex> g(c->lock);
    const Window root = RootWindow(c->dpy, c->screen);
    Window hit = 0;
    if (!find_window(c, root, to_lower(title), 0, hit)) return false;
    XWindowAttributes wa;
    if (!XGetWindowAttributes(c->dpy, hit, &wa)) return false;
    // Window geometry is parent-relative; translate to root (screen) space.
    int ax = 0, ay = 0;
    Window child = 0;
    if (!XTranslateCoordinates(c->dpy, hit, root, 0, 0, &ax, &ay, &child)) return false;
    x = ax;
    y = ay;
    w = wa.width;
    h = wa.height;
    return true;
  }
  std::string backend_name() const override { return "x11"; }

 private:
  static bool no_display() {
    static bool warned = false;
    if (!warned) {
      std::fprintf(stderr, "glance: control: no display (DISPLAY=%s)\n",
                   std::getenv("DISPLAY") ? std::getenv("DISPLAY") : "(unset)");
      warned = true;
    }
    return false;
  }
};

class X11Input : public Input {
  static bool no_display() {
    static bool warned = false;
    if (!warned) {
      std::fprintf(stderr, "glance: control: no display (DISPLAY=%s)\n",
                   std::getenv("DISPLAY") ? std::getenv("DISPLAY") : "(unset)");
      warned = true;
    }
    return false;
  }

  // Press + release one keysym, holding Shift when the keysym sits on the
  // key's shifted level (e.g. 'A', '$'). Called with c->lock held.
  static bool tap_locked(XConn* c, KeySym sym) {
    const KeyCode code = XKeysymToKeycode(c->dpy, sym);
    if (code == 0) return false;
    const bool shift = XkbKeycodeToKeysym(c->dpy, code, 0, 0) != sym &&
                       XkbKeycodeToKeysym(c->dpy, code, 0, 1) == sym;
    const KeyCode shift_code = shift ? XKeysymToKeycode(c->dpy, XK_Shift_L) : 0;
    if (shift_code) XTestFakeKeyEvent(c->dpy, shift_code, True, CurrentTime);
    XTestFakeKeyEvent(c->dpy, code, True, CurrentTime);
    XTestFakeKeyEvent(c->dpy, code, False, CurrentTime);
    if (shift_code) XTestFakeKeyEvent(c->dpy, shift_code, False, CurrentTime);
    return true;
  }

 public:
  void move_to(int x, int y) override {
    auto* c = g_x();
    if (!c) return;
    std::lock_guard<std::mutex> g(c->lock);
    // dest_w = root makes the move absolute (None would move relatively).
    XWarpPointer(c->dpy, None, RootWindow(c->dpy, c->screen), 0, 0, 0, 0, x, y);
    XFlush(c->dpy);
  }
  void click(int x, int y, Button button = Left) override {
    auto* c = g_x();
    if (!c) return;
    const unsigned int idx = (button >= Left && button <= Right) ? (unsigned)button : (unsigned)Left;
    std::lock_guard<std::mutex> g(c->lock);
    XTestFakeMotionEvent(c->dpy, c->screen, x, y, CurrentTime);
    XTestFakeButtonEvent(c->dpy, idx, True, CurrentTime);
    XTestFakeButtonEvent(c->dpy, idx, False, CurrentTime);
    XSync(c->dpy, False);
  }
  bool press_key(const std::string& keysym) override {
    auto* c = g_x();
    if (!c) return no_display();
    const KeySym sym = XStringToKeysym(keysym.c_str());
    if (sym == NoSymbol) return false;
    std::lock_guard<std::mutex> g(c->lock);
    const bool ok = tap_locked(c, sym);
    XSync(c->dpy, False);
    return ok;
  }
  bool type_text(const std::string& text) override {
    auto* c = g_x();
    if (!c) return no_display();
    std::lock_guard<std::mutex> g(c->lock);
    bool ok = true;
    for (const char ch : text) {
      const unsigned char u = (unsigned char)ch;
      // Printable ASCII: the Latin-1 keysym value equals the character code
      // (XK_space = 0x20, XK_A = 0x41, XK_dollar = 0x24, ...).
      if (u >= 32 && u < 127) ok = tap_locked(c, (KeySym)u) && ok;
      else if (ch == '\n') ok = tap_locked(c, XK_Return) && ok;
      else if (ch == '\t') ok = tap_locked(c, XK_Tab) && ok;
    }
    XSync(c->dpy, False);
    return ok;
  }
};

Backend make_x11() {
  Backend b;
  b.name = "x11";
  b.screen = std::make_shared<X11Screen>();
  b.input = std::make_shared<X11Input>();
  return b;
}

}  // namespace glance::control

#endif  // __linux__ && GLANCE_X11
