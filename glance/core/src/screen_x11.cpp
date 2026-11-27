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
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <mutex>
#include <string>

#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/Xatom.h>
#include <X11/extensions/XTest.h>

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

// Visual channel layout: a channel's pixel bits start at `shift` and are
// contiguous. Derived from the screen's actual red/green/blue masks, never
// assumed — 24-bit TrueColor on a little-endian Xorg (the usual case) comes
// out BGR-in-the-low-24-bits, but 15/16/32-bit visuals stay correct too.
struct Channel {
  int shift = 0;
  unsigned long mask = 0xff;
};

Channel channel_of(unsigned long m) {
  Channel c;
  if (m == 0) return c;
  while ((m & 1) == 0) {
    m >>= 1;
    c.shift++;
  }
  unsigned long bits = 1;
  while (m >>= 1)
    bits++;
  c.mask = (1ul << bits) - 1ul;
  return c;
}

// Decodes an XGetImage buffer into BGR 8UC3. `w`, `h` must match img.
bool decode_image(const XImage* img, const Channel& cr, const Channel& cg, const Channel& cb,
                  cv::Mat& out) {
  const int w = img->width;
  const int h = img->height;
  out.create(h, w, CV_8UC3);
  if (img->bits_per_pixel == 32 && img->byte_order == LSBFirst && img->bitmap_bit_per_pixel == 32) {
    // Fast path (the overwhelming default on little-endian Xorg): 32-bit
    // words, channel bits taken straight out of the word.
    for (int yy = 0; yy < h; ++yy) {
      const unsigned long* src =
          reinterpret_cast<const unsigned long*>(img->data + (size_t)yy * img->bytes_per_line);
      auto* d = out.data + (size_t)yy * w * 3;
      for (int xx = 0; xx < w; ++xx) {
        const unsigned long px = src[xx];
        d[xx * 3 + 0] = (unsigned char)((px >> cb.shift) & cb.mask);  // B
        d[xx * 3 + 1] = (unsigned char)((px >> cg.shift) & cg.mask);  // G
        d[xx * 3 + 2] = (unsigned char)((px >> cr.shift) & cr.mask);  // R
      }
    }
  } else {
    // Everything else (16-bit depths, other byte orders): per-pixel, slower
    // but always correct.
    for (int yy = 0; yy < h; ++yy)
      for (int xx = 0; xx < w; ++xx) {
        const unsigned long px = XGetPixel(img, xx, yy);
        auto* d = out.data + (size_t)yy * w * 3 + (size_t)xx * 3;
        d[0] = (unsigned char)((px >> cb.shift) & cb.mask);  // B
        d[1] = (unsigned char)((px >> cg.shift) & cg.mask);  // G
        d[2] = (unsigned char)((px >> cr.shift) & cr.mask);  // R
      }
  }
  return true;
}

// Window title: _NET_WM_NAME (UTF-8) preferred, WM_NAME (Latin-1) fallback.
std::string window_title_of(XConn* c, Window win) {
  for (int i = 0; i < 2; ++i) {
    const char* atom_name = i == 0 ? "_NET_WM_NAME" : "WM_NAME";
    const Atom type = i == 0 ? XA_UTF8_STRING : XA_STRING;
    Atom actual = 0;
    unsigned long nitems = 0, bytes_after = 0;
    unsigned char* val = nullptr;
    Bool got = False;
    if (XGetWindowProperty(c->dpy, win, XInternAtom(c->dpy, atom_name, False), 0, 1024, False,
                           type, &actual, &nitems, &bytes_after, &val, &got) != Success)
      continue;
    std::string s;
    if (val && nitems > 0) {
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

}  // namespace

class X11Screen : public Screen {
  // Called with c->lock held. Out-of-bounds requests are clamped to the
  // display.
  bool grab_locked(XConn* c, int x, int y, int w, int h, cv::Mat& out) {
    const int sw = DisplayWidth(c->dpy, c->screen);
    const int sh = DisplayHeight(c->dpy, c->screen);
    x = std::clamp(x, 0, sw - 1);
    y = std::clamp(y, 0, sh - 1);
    w = std::min(w, sw - x);
    h = std::min(h, sh - y);
    if (w < 1 || h < 1) return false;
    XImage* img = XGetImage(c->dpy, RootWindow(c->dpy, c->screen), x, y, w, h, AllPlanes, ZPixmap);
    if (!img) return false;
    XWindowAttributes wa;
    const Channel cr =
        XGetWindowAttributes(c->dpy, RootWindow(c->dpy, c->screen), &wa) == Success
            ? channel_of(wa.red_mask)
            : Channel{16, 0xff};
    const Channel cg =
        XGetWindowAttributes(c->dpy, RootWindow(c->dpy, c->screen), &wa) == Success
            ? channel_of(wa.green_mask)
            : Channel{8, 0xff};
    const Channel cb =
        XGetWindowAttributes(c->dpy, RootWindow(c->dpy, c->screen), &wa) == Success
            ? channel_of(wa.blue_mask)
            : Channel{0, 0xff};
    const bool ok = decode_image(img, cr, cg, cb, out);
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
    // grab_locked takes the lock itself.
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
    Window root = RootWindow(c->dpy, c->screen);
    Window root_ret = 0, parent_ret = 0;
    Window* children = nullptr;
    unsigned int n = 0;
    if (XQueryTree(c->dpy, root, &root_ret, &parent_ret, &children, &n) != Success) return false;
    bool found = false;
    const std::string tl = to_lower(title);
    for (unsigned int i = 0; i < n && !found; ++i) {
      Window win = children[i];
      unsigned long bx = 0, by = 0, bw = 0, bh = 0, bborder = 0;
      Window child = 0;
      if (XGetGeometry(c->dpy, win, &bx, &by, &bw, &bh, &bborder, &child) != Success) continue;
      const std::string nm = to_lower(window_title_of(c, win));
      if (nm.empty() || tl.size() > nm.size()) continue;
      if (nm.find(tl) != std::string::npos) {
        x = (int)bx;
        y = (int)by;
        w = (int)bw;
        h = (int)bh;
        found = true;
      }
    }
    if (children) XFree(children);
    XSync(c->dpy, False);
    return found;
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

 public:
  void move_to(int x, int y) override {
    auto* c = g_x();
    if (!c) return;
    std::lock_guard<std::mutex> g(c->lock);
    XWarpPointer(c->dpy, None, None, 0, 0, 0, 0, x, y);
    XFlush(c->dpy);
  }
  void click(int x, int y, Button button = Left) override {
    auto* c = g_x();
    if (!c) return;
    const int idx = (button >= Left && button <= Right) ? (int)button : (int)Left;
    std::lock_guard<std::mutex> g(c->lock);
    XTestFakeMotionEvent(c->dpy, c->screen, x, y, CurrentTime);
    XTestFakeButtonEvent(c->dpy, idx, True, CurrentTime);
    XTestFakeButtonEvent(c->dpy, idx, False, CurrentTime);
    XFlush(c->dpy);
    XSync(c->dpy, False);
  }
  bool press_key(const std::string& keysym) override {
    auto* c = g_x();
    if (!c) return no_display();
    const KeySym sym = XStringToKeysym(keysym.c_str());
    if (sym == NoSymbol) return false;
    std::lock_guard<std::mutex> g(c->lock);
    const unsigned int code = XKeysymToKeycode(c->dpy, sym);
    if (code == 0) return false;
    XTestFakeKeyEvent(c->dpy, code, True, CurrentTime);
    XTestFakeKeyEvent(c->dpy, code, False, CurrentTime);
    XFlush(c->dpy);
    XSync(c->dpy, False);
    return true;
  }
  bool type_text(const std::string& text) override {
    for (const char ch : text)
      if ((unsigned char)ch >= 32 && (unsigned char)ch < 127) {
        if (!press_key(std::string(1, ch))) return false;
      }
    return true;
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
