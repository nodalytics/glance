// Windows screen + input backend. The screen path BitBlts the virtual desktop
// (all monitors) from the screen DC into a 32-bit top-down DIB section; the
// input path uses SendInput (the documented API for synthetic mouse and
// keyboard input). Window lookup walks the top-level windows with
// EnumWindows.
//
// Coordinate space (same contract as control.h): physical pixels, with 0,0 at
// the top-left of the VIRTUAL desktop — the bounding box of all monitors,
// whose Win32 origin (SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN) is negative when
// a monitor sits left of / above the primary one. glance coordinates are
// translated by that origin at every Win32 call. The process is made
// per-monitor DPI aware when the backend is created, so GDI and SendInput
// both speak physical pixels rather than DPI-virtualized ones.
//
// Limits: SendInput is subject to UIPI — input into a window of a process
// running at a higher integrity level (e.g. an elevated client) is silently
// dropped; run glance at the same level as the target. Nothing here works
// from a non-interactive session (a service on session 0): grabs fail and
// the server reports it like "no display".
//
// This file only compiles when GLANCE_WIN32 is defined (CMake sets it on
// Windows unless -DGLANCE_WIN32=OFF); otherwise the null backend is used.

#if defined(_WIN32) && defined(GLANCE_WIN32)

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <mutex>
#include <string>
#include <vector>

// OpenCV (via control.h) before <windows.h>: the Win32 headers' macros must
// not leak into OpenCV's declarations.
#include "control.h"

#include <opencv2/imgproc.hpp>

#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <dwmapi.h>

namespace glance::control {

namespace {

// ---- process setup ----------------------------------------------------------

// Per-monitor DPI awareness, once per process. Resolved dynamically so the
// binary still starts on Windows versions without the newer entry points:
// SetProcessDpiAwarenessContext (Windows 10 1703+, user32) first, then the
// Vista-era SetProcessDPIAware. Failure (e.g. awareness already set by a
// manifest) is harmless.
void make_dpi_aware() {
  static std::once_flag once;
  std::call_once(once, [] {
    HMODULE user32 = ::GetModuleHandleW(L"user32.dll");
    if (!user32) return;
    using SetCtxFn = BOOL(WINAPI*)(HANDLE);
    // DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 == ((DPI_AWARENESS_CONTEXT)-4)
    auto set_ctx = reinterpret_cast<SetCtxFn>(
        reinterpret_cast<void*>(::GetProcAddress(user32, "SetProcessDpiAwarenessContext")));
    if (set_ctx && set_ctx(reinterpret_cast<HANDLE>(static_cast<intptr_t>(-4)))) return;
    using SetAwareFn = BOOL(WINAPI*)();
    auto set_aware = reinterpret_cast<SetAwareFn>(
        reinterpret_cast<void*>(::GetProcAddress(user32, "SetProcessDPIAware")));
    if (set_aware) set_aware();
  });
}

struct VirtualDesktop {
  int x = 0, y = 0, w = 0, h = 0;  // Win32 virtual-screen rectangle
};

VirtualDesktop virtual_desktop() {
  VirtualDesktop v;
  v.x = ::GetSystemMetrics(SM_XVIRTUALSCREEN);
  v.y = ::GetSystemMetrics(SM_YVIRTUALSCREEN);
  v.w = ::GetSystemMetrics(SM_CXVIRTUALSCREEN);
  v.h = ::GetSystemMetrics(SM_CYVIRTUALSCREEN);
  return v;
}

bool no_display() {
  static bool warned = false;
  if (!warned) {
    std::fprintf(stderr, "glance: control: no interactive desktop to grab (win32)\n");
    warned = true;
  }
  return false;
}

// ---- UTF-8 <-> UTF-16 -------------------------------------------------------

std::wstring widen(const std::string& s) {
  if (s.empty()) return std::wstring();
  const int n = ::MultiByteToWideChar(CP_UTF8, 0, s.data(), (int)s.size(), nullptr, 0);
  if (n <= 0) return std::wstring();
  std::wstring w((size_t)n, L'\0');
  ::MultiByteToWideChar(CP_UTF8, 0, s.data(), (int)s.size(), w.data(), n);
  return w;
}

void lower_in_place(std::wstring& w) {
  if (!w.empty()) ::CharLowerBuffW(w.data(), (DWORD)w.size());
}

// ---- window lookup -----------------------------------------------------------

struct FindCtx {
  std::wstring needle;  // lower-case
  HWND hit = nullptr;
};

bool is_cloaked(HWND hwnd) {
  // Windows 8+: UWP frames and windows on other virtual desktops are
  // "visible" but cloaked by DWM — never what a caller wants to grab.
  DWORD cloaked = 0;
  return SUCCEEDED(::DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, &cloaked, sizeof(cloaked))) &&
         cloaked != 0;
}

BOOL CALLBACK find_window_proc(HWND hwnd, LPARAM lparam) {
  auto* ctx = reinterpret_cast<FindCtx*>(lparam);
  // Visible, not minimized (X11's IsViewable), not cloaked.
  if (!::IsWindowVisible(hwnd) || ::IsIconic(hwnd) || is_cloaked(hwnd)) return TRUE;
  const int len = ::GetWindowTextLengthW(hwnd);
  if (len <= 0) return TRUE;
  std::wstring title((size_t)len + 1, L'\0');
  const int got = ::GetWindowTextW(hwnd, title.data(), len + 1);
  if (got <= 0) return TRUE;
  title.resize((size_t)got);
  lower_in_place(title);
  if (title.find(ctx->needle) != std::wstring::npos) {
    ctx->hit = hwnd;
    return FALSE;  // stop enumerating
  }
  return TRUE;
}

// ---- keyboard ----------------------------------------------------------------

// Keys that need KEYEVENTF_EXTENDEDKEY (they live on the E0-prefixed
// scancode page): without it, e.g. VK_LEFT is delivered as numpad 4.
bool is_extended(WORD vk) {
  switch (vk) {
    case VK_INSERT: case VK_DELETE: case VK_HOME: case VK_END: case VK_PRIOR: case VK_NEXT:
    case VK_LEFT: case VK_RIGHT: case VK_UP: case VK_DOWN:
    case VK_RCONTROL: case VK_RMENU: case VK_LWIN: case VK_RWIN: case VK_APPS:
    case VK_DIVIDE: case VK_NUMLOCK: case VK_SNAPSHOT:
      return true;
    default:
      return false;
  }
}

INPUT key_input(WORD vk, bool up) {
  INPUT in{};
  in.type = INPUT_KEYBOARD;
  in.ki.wVk = vk;
  // Fill the scancode too: some clients (games, DirectInput) read it.
  in.ki.wScan = (WORD)::MapVirtualKeyW(vk, MAPVK_VK_TO_VSC);
  in.ki.dwFlags = (up ? KEYEVENTF_KEYUP : 0) | (is_extended(vk) ? KEYEVENTF_EXTENDEDKEY : 0);
  return in;
}

INPUT unicode_input(wchar_t unit, bool up) {
  INPUT in{};
  in.type = INPUT_KEYBOARD;
  in.ki.wVk = 0;
  in.ki.wScan = (WORD)unit;
  in.ki.dwFlags = KEYEVENTF_UNICODE | (up ? KEYEVENTF_KEYUP : 0);
  return in;
}

bool send(std::vector<INPUT>& seq) {
  if (seq.empty()) return true;
  const UINT n = ::SendInput((UINT)seq.size(), seq.data(), (int)sizeof(INPUT));
  return n == (UINT)seq.size();
}

// Named (non-character) X keysyms -> virtual-key codes.
WORD named_vk(const std::string& k) {
  struct Entry {
    const char* name;
    WORD vk;
  };
  static const Entry table[] = {
      {"Return", VK_RETURN},    {"KP_Enter", VK_RETURN}, {"Tab", VK_TAB},
      {"Escape", VK_ESCAPE},    {"BackSpace", VK_BACK},  {"space", VK_SPACE},
      {"Delete", VK_DELETE},    {"Insert", VK_INSERT},   {"Home", VK_HOME},
      {"End", VK_END},          {"Prior", VK_PRIOR},     {"Page_Up", VK_PRIOR},
      {"Next", VK_NEXT},        {"Page_Down", VK_NEXT},  {"Left", VK_LEFT},
      {"Right", VK_RIGHT},      {"Up", VK_UP},           {"Down", VK_DOWN},
      {"Shift_L", VK_LSHIFT},   {"Shift_R", VK_RSHIFT},  {"Control_L", VK_LCONTROL},
      {"Control_R", VK_RCONTROL}, {"Alt_L", VK_LMENU},   {"Alt_R", VK_RMENU},
      {"Super_L", VK_LWIN},     {"Super_R", VK_RWIN},    {"Menu", VK_APPS},
      {"Caps_Lock", VK_CAPITAL}, {"Num_Lock", VK_NUMLOCK}, {"Scroll_Lock", VK_SCROLL},
      {"Print", VK_SNAPSHOT},   {"Pause", VK_PAUSE},
  };
  for (const auto& e : table)
    if (k == e.name) return e.vk;
  // F1..F24
  if (k.size() >= 2 && k.size() <= 3 && k[0] == 'F' &&
      std::all_of(k.begin() + 1, k.end(), [](char c) { return c >= '0' && c <= '9'; })) {
    const int n = std::stoi(k.substr(1));
    if (n >= 1 && n <= 24) return (WORD)(VK_F1 + (n - 1));
  }
  return 0;
}

// Character keysym names (the X11 Latin-1 names the X backend resolves via
// XStringToKeysym) -> the character they type. Single-character names
// ("a", "9", "$") are themselves.
wchar_t keysym_char(const std::string& k) {
  if (k.size() == 1 && (unsigned char)k[0] >= 0x20 && (unsigned char)k[0] < 0x7f)
    return (wchar_t)(unsigned char)k[0];
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
    if (k == e.name) return (wchar_t)(unsigned char)e.ch;
  return 0;
}

// Press + release the key that types `ch` on the active layout, holding the
// modifiers VkKeyScanW reports (e.g. Shift for 'A' or '$'). Characters with
// no key on the layout are injected as KEYEVENTF_UNICODE packets.
void append_char(std::vector<INPUT>& seq, wchar_t ch) {
  const SHORT scan = ::VkKeyScanW(ch);
  if (scan == -1) {
    seq.push_back(unicode_input(ch, false));
    seq.push_back(unicode_input(ch, true));
    return;
  }
  const WORD vk = (WORD)(scan & 0xff);
  const int mods = (scan >> 8) & 0xff;
  if (mods & 1) seq.push_back(key_input(VK_SHIFT, false));
  if (mods & 2) seq.push_back(key_input(VK_CONTROL, false));
  if (mods & 4) seq.push_back(key_input(VK_MENU, false));
  seq.push_back(key_input(vk, false));
  seq.push_back(key_input(vk, true));
  if (mods & 4) seq.push_back(key_input(VK_MENU, true));
  if (mods & 2) seq.push_back(key_input(VK_CONTROL, true));
  if (mods & 1) seq.push_back(key_input(VK_SHIFT, true));
}

}  // namespace

class Win32Screen : public Screen {
 public:
  Win32Screen() { make_dpi_aware(); }

  bool grab(int x, int y, int w, int h, cv::Mat& out) override {
    const VirtualDesktop v = virtual_desktop();
    if (v.w < 1 || v.h < 1) return no_display();
    // Clamp to the virtual desktop (glance space: 0,0 .. v.w,v.h).
    if (x < 0) {
      w += x;
      x = 0;
    }
    if (y < 0) {
      h += y;
      y = 0;
    }
    w = std::min(w, v.w - x);
    h = std::min(h, v.h - y);
    if (w < 1 || h < 1) return false;

    HDC screen = ::GetDC(nullptr);
    if (!screen) return no_display();
    HDC mem = ::CreateCompatibleDC(screen);
    if (!mem) {
      ::ReleaseDC(nullptr, screen);
      return false;
    }
    BITMAPINFO bi{};
    bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth = w;
    bi.bmiHeader.biHeight = -h;  // negative: top-down rows, like cv::Mat
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    void* bits = nullptr;
    HBITMAP bmp = ::CreateDIBSection(screen, &bi, DIB_RGB_COLORS, &bits, nullptr, 0);
    bool ok = false;
    if (bmp && bits) {
      HGDIOBJ old = ::SelectObject(mem, bmp);
      // CAPTUREBLT: include layered (WS_EX_LAYERED) windows in the copy.
      ok = ::BitBlt(mem, 0, 0, w, h, screen, v.x + x, v.y + y, SRCCOPY | CAPTUREBLT) != 0;
      ::GdiFlush();
      if (ok) {
        // 32-bit BI_RGB DIB rows are B,G,R,X with a stride of exactly 4*w.
        const cv::Mat bgra(h, w, CV_8UC4, bits);
        cv::cvtColor(bgra, out, cv::COLOR_BGRA2BGR);  // copies out of the DIB
      }
      ::SelectObject(mem, old);
    }
    if (bmp) ::DeleteObject(bmp);
    ::DeleteDC(mem);
    ::ReleaseDC(nullptr, screen);
    return ok;
  }

  bool grab_all(cv::Mat& out) override {
    const VirtualDesktop v = virtual_desktop();
    if (v.w < 1 || v.h < 1) return no_display();
    return grab(0, 0, v.w, v.h, out);
  }

  bool display_size(int& w, int& h) override {
    const VirtualDesktop v = virtual_desktop();
    if (v.w < 1 || v.h < 1) return false;
    w = v.w;
    h = v.h;
    return true;
  }

  // The matched window's CLIENT area (no title bar / borders), like the X11
  // backend, which reports the client window inside the WM frame. Falls back
  // to the DWM visible frame bounds (GetWindowRect without the invisible
  // resize borders), then GetWindowRect, if the client rect is unusable.
  bool locate_window(const std::string& title, int& x, int& y, int& w, int& h) override {
    if (title.empty()) return false;
    FindCtx ctx;
    ctx.needle = widen(title);
    if (ctx.needle.empty()) return false;
    lower_in_place(ctx.needle);
    // EnumWindows walks top-level windows in Z order, topmost first.
    ::EnumWindows(find_window_proc, reinterpret_cast<LPARAM>(&ctx));
    if (!ctx.hit) return false;

    RECT r{};
    POINT origin{0, 0};
    if (::GetClientRect(ctx.hit, &r) && r.right > r.left && r.bottom > r.top &&
        ::ClientToScreen(ctx.hit, &origin)) {
      r.right = origin.x + (r.right - r.left);
      r.bottom = origin.y + (r.bottom - r.top);
      r.left = origin.x;
      r.top = origin.y;
    } else if (FAILED(::DwmGetWindowAttribute(ctx.hit, DWMWA_EXTENDED_FRAME_BOUNDS, &r, sizeof(r))) &&
               !::GetWindowRect(ctx.hit, &r)) {
      return false;
    }
    const VirtualDesktop v = virtual_desktop();
    x = r.left - v.x;
    y = r.top - v.y;
    w = r.right - r.left;
    h = r.bottom - r.top;
    return w > 0 && h > 0;
  }

  std::string backend_name() const override { return "win32"; }
};

class Win32Input : public Input {
 public:
  Win32Input() { make_dpi_aware(); }

  void move_to(int x, int y) override {
    std::vector<INPUT> seq{move_input(x, y)};
    send(seq);
  }

  void click(int x, int y, Button button = Left) override {
    DWORD down = MOUSEEVENTF_LEFTDOWN, up = MOUSEEVENTF_LEFTUP;
    if (button == Middle) {
      down = MOUSEEVENTF_MIDDLEDOWN;
      up = MOUSEEVENTF_MIDDLEUP;
    } else if (button == Right) {
      down = MOUSEEVENTF_RIGHTDOWN;
      up = MOUSEEVENTF_RIGHTUP;
    }
    INPUT d{};
    d.type = INPUT_MOUSE;
    d.mi.dwFlags = down;
    INPUT u{};
    u.type = INPUT_MOUSE;
    u.mi.dwFlags = up;
    // One SendInput call: the three events are inserted atomically, so no
    // other input can interleave between the move and the press.
    std::vector<INPUT> seq{move_input(x, y), d, u};
    send(seq);
  }

  bool press_key(const std::string& keysym) override {
    if (keysym.empty()) return false;
    std::vector<INPUT> seq;
    if (const WORD vk = named_vk(keysym)) {
      seq.push_back(key_input(vk, false));
      seq.push_back(key_input(vk, true));
    } else if (const wchar_t ch = keysym_char(keysym)) {
      append_char(seq, ch);
    } else {
      return false;  // unknown keysym name (X11 parity: XStringToKeysym fails)
    }
    return send(seq);
  }

  bool type_text(const std::string& text) override {
    const std::wstring w = widen(text);
    std::vector<INPUT> seq;
    seq.reserve(w.size() * 2);
    for (const wchar_t ch : w) {
      if (ch == L'\n') {
        seq.push_back(key_input(VK_RETURN, false));
        seq.push_back(key_input(VK_RETURN, true));
      } else if (ch == L'\t') {
        seq.push_back(key_input(VK_TAB, false));
        seq.push_back(key_input(VK_TAB, true));
      } else if (ch >= 0x20 && ch != 0x7f) {
        // KEYEVENTF_UNICODE types the character itself, independent of the
        // keyboard layout and of modifier state (UTF-16 surrogate halves are
        // sent as consecutive packets, which Windows reassembles).
        seq.push_back(unicode_input(ch, false));
        seq.push_back(unicode_input(ch, true));
      }
    }
    return send(seq);
  }

 private:
  // Absolute move in normalized virtual-desktop coordinates: with
  // MOUSEEVENTF_VIRTUALDESK, 0..65535 spans the whole virtual desktop.
  // Windows maps a normalized value n back to pixel floor(n * size / 65536),
  // so n = ceil(p * 65536 / size) lands exactly on pixel p.
  static INPUT move_input(int x, int y) {
    const VirtualDesktop v = virtual_desktop();
    const int vw = std::max(v.w, 1), vh = std::max(v.h, 1);
    x = std::clamp(x, 0, vw - 1);
    y = std::clamp(y, 0, vh - 1);
    INPUT in{};
    in.type = INPUT_MOUSE;
    in.mi.dx = (LONG)std::min<int64_t>(((int64_t)x * 65536 + vw - 1) / vw, 65535);
    in.mi.dy = (LONG)std::min<int64_t>(((int64_t)y * 65536 + vh - 1) / vh, 65535);
    in.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK;
    return in;
  }
};

Backend make_win32() {
  Backend b;
  b.name = "win32";
  b.screen = std::make_shared<Win32Screen>();
  b.input = std::make_shared<Win32Input>();
  return b;
}

}  // namespace glance::control

#endif  // _WIN32 && GLANCE_WIN32
