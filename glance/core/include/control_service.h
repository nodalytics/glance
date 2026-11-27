#pragma once

#include <memory>
#include <mutex>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>
#include <opencv2/core.hpp>

#include "control.h"
#include "scraper.h"

namespace glance {

// The control service: platform screen-grab + synthetic input (milestone M2).
//
// It pairs the ScreenshotService's parsing with the platform's Screen/Input
// backend (control.h):
//
//   1. the backend is selected at construction — make_default(), so the X11
//      backend on a machine with X development packages, the null backend
//      elsewhere (the configure-time-optional pattern OCR uses); the HTTP
//      layer in server/ just exposes the methods below;
//   2. every capture — a server-side platform grab, a window the server
//      found itself, or a frame a client POSTed to /capture — is recorded as
//      the INPUT-SPACE reference: input coordinates from clients are
//      interpreted in the last captured frame's space and converted to
//      screen-absolute with that frame's origin (a whole-desktop grab is
//      already screen-absolute; a POSTed frame is used as given);
//   3. "action" requests are resolved against the table mapping's "actions"
//      (control.h: resolve_action) using the ANCHORED TABLE ORIGIN of the
//      last capture — the same coordinates the parser used, so a click
//      lands exactly where the mapping's button/stack rectangle is.
//
// Thread-safe (httplib runs handlers on a pool); the platform backends add
// their own locking on top.
class ControlService {
 public:
  struct InputSource {
    enum class Kind { None, Desktop, Window, External };
    Kind kind = Kind::None;
    std::string window_title;  // set for Kind::Window
    int window_x = 0, window_y = 0;  // the frame's screen-absolute origin
  };

  struct ClickRequest {
    std::string target;      // action / button / stack name; "" for raw
    bool use_coords = false; // click (x,y) from the last frame's space
    int x = 0, y = 0;
    int button = static_cast<int>(control::Input::Left);
  };

  struct KeyRequest {
    std::string keysym;  // "Return", "Tab", "F5", "9", "a", ...
    std::string text;    // ...or type this string
  };

  struct StepResult {
    nlohmann::json request;  // the step, verbatim (audit in /sequence output)
    bool ok = false;
    std::string error;
    nlohmann::json detail;   // e.g. {"x":..., "y":..., "kind":"button"}
  };

  explicit ControlService(TableScraper* scraper);
  ControlService(TableScraper* scraper, std::shared_ptr<control::Backend> backend);

  // -- capture ---------------------------------------------------------------
  // Platform grabs: parse the grabbed frame and record it as the input-space
  // reference. All return false (with *err) when the platform has no display
  // or the window was not found; table_found reports the parse.
  bool grab_desktop(bool& table_found, std::string* err);
  bool grab_region(int x, int y, int w, int h, bool& table_found, std::string* err);
  bool grab_window(const std::string& title, bool& table_found, std::string* err);
  // /capture path: a client POSTed the frame; the parser (run elsewhere)
  // found the table at `origin` in that frame's space — record it. Frames
  // from /capture are treated as screen-absolute (clients are expected to
  // POST whole-desktop grabs; window-relative input goes through
  // POST /grab with a window title instead).
  void externally_parsed(bool table_found, const cv::Point& origin);
  std::string backend_name() const;

  // -- input -------------------------------------------------------------------
  // One named action / button / stack name, or a raw coordinate in the last
  // frame's space. Resolved to screen-absolute, injected by the platform.
  bool click(const ClickRequest& req, nlohmann::json& out_detail, std::string* err);
  bool key(const KeyRequest& req, std::string* err);
  // A /sequence body: a JSON array of {"action":...} /
  // {"click":{"x","y","button"}} / {"key":...} / {"type":...} steps,
  // executed in order; every step is reported regardless of failures.
  std::vector<StepResult> sequence(const nlohmann::json& steps);

  // -- state -------------------------------------------------------------------
  InputSource input_source() const;
  bool table_found() const;
  cv::Point table_origin() const;
  nlohmann::json info() const;  // {"backend":..., "window":...} for /health

 private:
  void note_parse(bool found, const cv::Point& origin);  // mu_ NOT held
  void to_screen(int& x, int& y) const;  // mu_ HELD
  bool parse_and_note(const cv::Mat& img, bool& table_found);

  TableScraper* scraper_ = nullptr;
  std::shared_ptr<control::Backend> backend_;

  mutable std::mutex mu_;
  InputSource src_;
  bool found_ = false;
  cv::Point origin_{0, 0};
};

}  // namespace glance
