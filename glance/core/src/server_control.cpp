#include "server_control.h"

#include <memory>
#include <string>

namespace glance {

ControlRoutes::ControlRoutes(ScreenshotService* service, TableScraper* scraper, ControlService* control)
    : service_(service), scraper_(scraper), ctrl_(control) {}

namespace {

nlohmann::json error_res(const std::string& msg) {
  nlohmann::json j;
  j["error"] = msg;
  return j;
}

}  // namespace

void ControlRoutes::install(httplib::Server& srv) {
  // GET /health — server liveness plus the control surface's state: which
  // backend is compiled in, and which frame (if any) client input is
  // interpreted in right now.
  srv.Get("/health", [this](const httplib::Request&, httplib::Response& res) {
    nlohmann::json j;
    j["status"] = "ok";
    j["control"] = ctrl_->info();
    res.set_content(j.dump(), "application/json");
  });

  // POST /capture — raw PNG/JPEG bytes of the table. Returns the parsed state
  // (422 when the table is not found) and, on success, records the frame as
  // the control's input-space reference so later /click coordinates and
  // action clicks are interpreted against THIS capture.
  srv.Post("/capture", [this](const httplib::Request& req, httplib::Response& res) {
    const std::vector<unsigned char> img(req.body.begin(), req.body.end());
    if (!service_->update(img)) {
      res.set_content(error_res("could not decode image or table not found").dump(),
                      "application/json");
      res.status = 422;
      return;
    }
    ctrl_->externally_parsed(scraper_->table_found(), scraper_->table_origin());
    res.set_content(service_->state_json().dump(), "application/json");
  });

  // POST /grab — the server grabs the screen itself; the grabbed frame becomes
  // the input-space reference and is parsed. Body (all fields optional):
  //   {"region": {"x","y","w","h"}}   grab a screen rectangle
  //   {"title": "..."}                grab the window whose title matches
  //   {}                              grab the mapping's window_title window
  //                                    (400 when the mapping has none)
  // 200: {"table_found": bool, "state"?: {...}}  422: {"error": ...}
  srv.Post("/grab", [this](const httplib::Request& req, httplib::Response& res) {
    nlohmann::json j;
    try {
      j = req.body.empty() ? nlohmann::json::object() : nlohmann::json::parse(req.body);
    } catch (const std::exception& e) {
      res.set_content(error_res(std::string("invalid JSON body: ") + e.what()).dump(),
                      "application/json");
      res.status = 400;
      return;
    }
    bool found = false;
    std::string err;
    bool ok = false;
    if (j.contains("region") && j["region"].is_object()) {
      const auto& r = j["region"];
      ok = ctrl_->grab_region(r.value("x", 0), r.value("y", 0), r.value("w", 0), r.value("h", 0),
                              found, &err);
    } else if (j.contains("title")) {
      if (!j["title"].is_string() || j["title"].get<std::string>().empty()) {
        res.set_content(error_res("title must be a non-empty string").dump(),
                        "application/json");
        res.status = 400;
        return;
      }
      ok = ctrl_->grab_window(j["title"].get<std::string>(), found, &err);
    } else if (scraper_->mapping().window_title().empty()) {
      res.set_content(error_res("body needs \"region\", \"title\" or a mapping window_title")
                          .dump(),
                      "application/json");
      res.status = 400;
      return;
    } else {
      // No explicit region/title: grab the window the mapping names.
      ok = ctrl_->grab_window(scraper_->mapping().window_title(), found, &err);
    }
    if (!ok) {
      res.set_content(error_res(err).dump(), "application/json");
      res.status = 422;
      return;
    }
    nlohmann::json out;
    out["table_found"] = found;
    if (found && service_->has_state()) out["state"] = service_->state_json();
    res.set_content(out.dump(), "application/json");
  });

  // POST /click — one click. Body:
  //   {"action": "call"}                     a named action (mapping "actions")
  //   {"action": "button:call"}              a direct button:/stack: target
  //   {"click": {"x", "y", "button"?: 1..3}} raw point in the last frame's space
  // 200: {"x", "y", "kind", "action"?: ...}  400 bad body, 422 not resolvable.
  srv.Post("/click", [this](const httplib::Request& req, httplib::Response& res) {
    nlohmann::json j;
    try {
      j = req.body.empty() ? nlohmann::json::object() : nlohmann::json::parse(req.body);
      if (!j.is_object()) throw std::runtime_error("body must be a JSON object");
    } catch (const std::exception& e) {
      res.set_content(error_res(std::string("invalid JSON body: ") + e.what()).dump(),
                      "application/json");
      res.status = 400;
      return;
    }
    ControlService::ClickRequest cr;
    if (j.contains("action")) {
      if (!j["action"].is_string()) {
        res.set_content(error_res("action must be a name or a \"button:/stack:\" target").dump(),
                        "application/json");
        res.status = 400;
        return;
      }
      cr.target = j["action"].get<std::string>();
    } else if (j.contains("click")) {
      if (!j["click"].is_object()) {
        res.set_content(error_res("click must be an object with x and y").dump(),
                        "application/json");
        res.status = 400;
        return;
      }
      const auto& c = j["click"];
      cr.use_coords = true;
      cr.x = c.value("x", 0);
      cr.y = c.value("y", 0);
      cr.button = c.value("button", 1);
    } else {
      res.set_content(error_res("body needs \"action\" or \"click\"").dump(), "application/json");
      res.status = 400;
      return;
    }
    nlohmann::json detail;
    std::string err;
    if (!ctrl_->click(cr, detail, &err)) {
      res.set_content(error_res(err).dump(), "application/json");
      res.status = 422;
      return;
    }
    res.set_content(detail.dump(), "application/json");
  });

  // POST /key — one key press or a short typed string. Body:
  //   {"key": "Return"}   one keysym (X keysym names)
  //   {"type": "200"}     type printable text
  // 200: {}  400 bad body, 422 the backend rejected the key.
  srv.Post("/key", [this](const httplib::Request& req, httplib::Response& res) {
    nlohmann::json j;
    try {
      j = req.body.empty() ? nlohmann::json::object() : nlohmann::json::parse(req.body);
      if (!j.is_object()) throw std::runtime_error("body must be a JSON object");
    } catch (const std::exception& e) {
      res.set_content(error_res(std::string("invalid JSON body: ") + e.what()).dump(),
                      "application/json");
      res.status = 400;
      return;
    }
    ControlService::KeyRequest kr;
    if (j.contains("key")) {
      if (!j["key"].is_string()) {
        res.set_content(error_res("key must be a keysym string").dump(), "application/json");
        res.status = 400;
        return;
      }
      kr.keysym = j["key"].get<std::string>();
    } else if (j.contains("type")) {
      if (!j["type"].is_string()) {
        res.set_content(error_res("type must be a string").dump(), "application/json");
        res.status = 400;
        return;
      }
      kr.text = j["type"].get<std::string>();
    } else {
      res.set_content(error_res("body needs \"key\" or \"type\"").dump(), "application/json");
      res.status = 400;
      return;
    }
    std::string err;
    if (!ctrl_->key(kr, &err)) {
      res.set_content(error_res(err).dump(), "application/json");
      res.status = 422;
      return;
    }
    res.set_content("{}", "application/json");
  });

  // POST /sequence — a JSON array of steps, executed in order:
  //   {"action": "call"} {"click": {"x","y"}} {"key": "Return"} {"type": "200"}
  // Every step is reported (audit trail); 400 on a non-array body, 200
  // carries {"steps": [...]} on success.
  srv.Post("/sequence", [this](const httplib::Request& req, httplib::Response& res) {
    nlohmann::json j;
    try {
      j = req.body.empty() ? nlohmann::json::array() : nlohmann::json::parse(req.body);
    } catch (const std::exception& e) {
      res.set_content(error_res(std::string("invalid JSON body: ") + e.what()).dump(),
                      "application/json");
      res.status = 400;
      return;
    }
    if (!j.is_array()) {
      res.set_content(error_res("body must be a JSON array of steps").dump(),
                      "application/json");
      res.status = 400;
      return;
    }
    auto results = ctrl_->sequence(j);
    nlohmann::json out = nlohmann::json::object();
    nlohmann::json steps = nlohmann::json::array();
    for (const auto& r : results) {
      nlohmann::json s;
      s["request"] = r.request;
      s["ok"] = r.ok;
      if (!r.error.empty()) s["error"] = r.error;
      if (!r.detail.empty()) s["detail"] = r.detail;
      steps.push_back(std::move(s));
    }
    out["steps"] = std::move(steps);
    res.set_content(out.dump(), "application/json");
  });
}

}  // namespace glance
