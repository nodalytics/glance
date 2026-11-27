#include "control_service.h"

#include "control.h"

namespace glance {

ControlService::ControlService(TableScraper* scraper)
    : ControlService(scraper, std::make_shared<control::Backend>(control::make_default())) {}

ControlService::ControlService(TableScraper* scraper, std::shared_ptr<control::Backend> backend)
    : scraper_(scraper), backend_(std::move(backend)) {}

// -- capture -------------------------------------------------------------

bool ControlService::parse_and_note(const cv::Mat& img, bool& table_found) {
  table_found = false;
  if (!scraper_) return false;
  if (!scraper_->scrape(img)) return false;
  table_found = true;
  note_parse(scraper_->table_found(), scraper_->table_origin());
  return true;
}

bool ControlService::grab_desktop(bool& table_found, std::string* err) {
  if (!backend_ || !backend_->screen) {
    if (err) *err = "no control backend available";
    return false;
  }
  cv::Mat img;
  if (!backend_->screen->grab_all(img) || img.empty()) {
    if (err) *err = "platform grab failed (no display?)";
    return false;
  }
  {
    std::lock_guard<std::mutex> g(mu_);
    src_ = InputSource{InputSource::Kind::Desktop, "(desktop)", 0, 0};
  }
  parse_and_note(img, table_found);
  return true;
}

bool ControlService::grab_region(int x, int y, int w, int h, bool& table_found, std::string* err) {
  if (!backend_ || !backend_->screen) {
    if (err) *err = "no control backend available";
    return false;
  }
  cv::Mat img;
  if (!backend_->screen->grab(x, y, w, h, img) || img.empty()) {
    if (err) *err = "platform grab failed (no display?)";
    return false;
  }
  {
    std::lock_guard<std::mutex> g(mu_);
    src_ = InputSource{InputSource::Kind::Desktop, "(region)", x, y};
  }
  parse_and_note(img, table_found);
  return true;
}

bool ControlService::grab_window(const std::string& title, bool& table_found, std::string* err) {
  if (!backend_ || !backend_->screen) {
    if (err) *err = "no control backend available";
    return false;
  }
  auto& screen = *backend_->screen;
  if (title.empty()) {
    if (err) *err = "no window title given and no mapping window_title";
    return false;
  }
  int wx = 0, wy = 0, ww = 0, wh = 0;
  if (!screen.locate_window(title, wx, wy, ww, wh)) {
    if (err) *err = "window not found: " + title;
    return false;
  }
  cv::Mat img;
  if (!screen.grab(wx, wy, ww, wh, img) || img.empty()) {
    if (err) *err = "window grab failed";
    return false;
  }
  {
    std::lock_guard<std::mutex> g(mu_);
    src_ = InputSource{InputSource::Kind::Window, title, wx, wy};
  }
  parse_and_note(img, table_found);
  return true;
}

void ControlService::externally_parsed(bool table_found, const cv::Point& origin) {
  std::lock_guard<std::mutex> g(mu_);
  src_.kind = InputSource::Kind::External;
  found_ = table_found;
  origin_ = table_found ? origin : cv::Point(0, 0);
}

std::string ControlService::backend_name() const { return backend_ ? backend_->name : "null"; }

// -- input -----------------------------------------------------------------

void ControlService::note_parse(bool found, const cv::Point& origin) {
  std::lock_guard<std::mutex> g(mu_);
  found_ = found;
  origin_ = origin;
}

bool ControlService::table_found() const {
  std::lock_guard<std::mutex> g(mu_);
  return found_;
}

cv::Point ControlService::table_origin() const {
  std::lock_guard<std::mutex> g(mu_);
  return origin_;
}

ControlService::InputSource ControlService::input_source() const {
  std::lock_guard<std::mutex> g(mu_);
  return src_;
}

void ControlService::to_screen(int& x, int& y) const {
  // Client coordinates are expressed in the last captured frame's space.
  // Frames grabbed from a screen region carry that region's top-left as the
  // offset (a whole-desktop grab is at 0,0, so already screen-absolute) and
  // window grabs carry the window frame; frames POSTed by clients are used
  // as given (see externally_parsed).
  if (src_.kind == InputSource::Kind::Window || src_.kind == InputSource::Kind::Desktop) {
    x += src_.window_x;
    y += src_.window_y;
  }
}

bool ControlService::click(const ClickRequest& req, nlohmann::json& out_detail, std::string* err) {
  if (!backend_ || !backend_->input) {
    if (err) *err = "no control backend available";
    return false;
  }
  int x = req.x, y = req.y;
  std::string kind = "raw";
  if (!req.use_coords) {
    if (!scraper_) {
      if (err) *err = "no scraper to resolve the action";
      return false;
    }
    bool found;
    cv::Point origin;
    {
      std::lock_guard<std::mutex> g(mu_);
      found = found_;
      origin = origin_;
    }
    auto p = control::resolve_action(scraper_->mapping(), origin, found, req.target);
    if (!p) {
      if (err)
        *err = found
                    ? "unknown or unresolvable action '" + req.target + "'"
                    : "cannot resolve action '" + req.target + "': table not anchored";
      return false;
    }
    x = p->x;
    y = p->y;
    kind = p->kind;
  }
  {
    // Both raw client coordinates and a resolved action point are expressed
    // in the last captured frame's space: resolve_action's anchor is the
    // FRAME-RELATIVE table origin (scraper::TableScraper only sees the frame),
    // so the re-basing with the frame origin applies to both.
    std::lock_guard<std::mutex> g(mu_);
    to_screen(x, y);
  }
  backend_->input->click(x, y, static_cast<control::Input::Button>(req.button));
  out_detail["x"] = x;
  out_detail["y"] = y;
  out_detail["kind"] = kind;
  if (!req.target.empty()) out_detail["action"] = req.target;
  return true;
}

bool ControlService::key(const KeyRequest& req, std::string* err) {
  if (!backend_ || !backend_->input) {
    if (err) *err = "no control backend available";
    return false;
  }
  bool ok = false;
  if (!req.keysym.empty()) {
    ok = backend_->input->press_key(req.keysym);
    if (!ok && err) *err = "key not recognised: " + req.keysym;
  } else if (!req.text.empty()) {
    ok = backend_->input->type_text(req.text);
  } else if (err) {
    *err = "empty key request";
  }
  return ok;
}

std::vector<ControlService::StepResult> ControlService::sequence(const nlohmann::json& steps) {
  std::vector<StepResult> out;
  if (!steps.is_array()) {
    StepResult r;
    r.error = "body must be a JSON array of steps";
    out.push_back(std::move(r));
    return out;
  }
  for (const auto& step : steps) {
    StepResult r;
    r.request = step;
    if (!step.is_object()) {
      r.error = "step is not an object";
      out.push_back(std::move(r));
      continue;
    }
    if (step.contains("action")) {
      ClickRequest req;
      req.target = step["action"].get<std::string>();
      r.ok = click(req, r.detail, &r.error);
    } else if (step.contains("click")) {
      ClickRequest req;
      req.use_coords = true;
      const auto& c = step["click"];
      req.x = c.value("x", 0);
      req.y = c.value("y", 0);
      req.button = c.value("button", 1);
      r.ok = click(req, r.detail, &r.error);
    } else if (step.contains("key")) {
      KeyRequest req;
      req.keysym = step["key"].get<std::string>();
      r.ok = key(req, &r.error);
    } else if (step.contains("type")) {
      KeyRequest req;
      req.text = step["type"].get<std::string>();
      r.ok = key(req, &r.error);
    } else {
      r.error = "step needs \"action\", \"click\", \"key\" or \"type\"";
    }
    out.push_back(std::move(r));
  }
  return out;
}

nlohmann::json ControlService::info() const {
  nlohmann::json j;
  j["backend"] = backend_name();
  const InputSource src = input_source();
  if (src.kind == InputSource::Kind::Window) {
    nlohmann::json win;
    win["title"] = src.window_title;
    win["x"] = src.window_x;
    win["y"] = src.window_y;
    j["window"] = std::move(win);
  }
  return j;
}

}  // namespace glance
