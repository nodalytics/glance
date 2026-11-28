#include "server_dashboard.h"

#include <string>
#include <vector>

#include <nlohmann/json.hpp>

#include "card_vision.h"
#include "image_io.h"
#include "ocr.h"

#ifndef GLANCE_VERSION
#define GLANCE_VERSION "0.0.0-dev"
#endif

namespace glance {

DashboardRoutes::DashboardRoutes(ScreenshotService* service, TableScraper* scraper,
                                 ControlService* control)
    : service_(service), scraper_(scraper), ctrl_(control) {}

namespace {

void json_error(httplib::Response& res, int status, const std::string& msg) {
  nlohmann::json j;
  j["error"] = msg;
  res.status = status;
  res.set_content(j.dump(), "application/json");
}

void serve_asset(httplib::Response& res, const web::Asset& a) {
  res.set_content(reinterpret_cast<const char*>(a.data), a.size, a.mime);
  // The dashboard is compiled into the binary: a rebuilt server is the only
  // way it changes, so let the browser revalidate on every load.
  res.set_header("Cache-Control", "no-cache");
}

}  // namespace

void DashboardRoutes::install(httplib::Server& srv) {
  // GET / — the dashboard shell.
  srv.Get("/", [](const httplib::Request&, httplib::Response& res) {
    const web::Asset* a = web::find_asset("index.html");
    if (!a) {
      json_error(res, 404, "dashboard not embedded in this build");
      return;
    }
    serve_asset(res, *a);
  });

  // GET /assets/<file> — the other embedded dashboard files. The path is a
  // lookup key into a compiled-in table, never a filesystem path.
  srv.Get(R"(/assets/(.+))", [](const httplib::Request& req, httplib::Response& res) {
    const web::Asset* a = web::find_asset(req.matches[1].str());
    if (!a) {
      json_error(res, 404, "no such dashboard asset");
      return;
    }
    serve_asset(res, *a);
  });

  // GET /info — what this server is and what it was built/configured with.
  srv.Get("/info", [this](const httplib::Request&, httplib::Response& res) {
    nlohmann::json j;
    j["name"] = "glance";
    j["version"] = GLANCE_VERSION;
    j["ocr_available"] = ocr_available();
    j["control_backend"] = ctrl_ ? ctrl_->backend_name() : std::string("none");

    // The control surface, so a client can discover it without reading the
    // docs: the backend name plus every flat control endpoint this server
    // installs (the plain-path control plane + the Slumbot-mirroring one).
    nlohmann::json control;
    control["backend"] = ctrl_ ? ctrl_->backend_name() : std::string("none");
    control["endpoints"] = nlohmann::json::array({"/grab", "/click", "/key", "/sequence", "/login",
                                                  "/new_hand", "/act"});
    j["control"] = std::move(control);

    nlohmann::json m;
    const TableMapping& mapping = scraper_->mapping();
    m["name"] = mapping.name();
    m["window_title"] = mapping.window_title();
    nlohmann::json actions = nlohmann::json::array();
    for (const auto& [name, target] : mapping.actions()) {
      actions.push_back({{"name", name}, {"target", target}});
    }
    m["actions"] = std::move(actions);
    j["mapping"] = std::move(m);

    nlohmann::json cv;
    const vision::CardRecognizer* rec = scraper_->card_recognizer();
    cv["configured"] = rec != nullptr;
    if (rec) {
      cv["profile"] = rec->config().profile;
      cv["suit_templates"] = rec->suit_template_count();
      cv["rank_templates"] = rec->rank_template_count();
    }
    j["card_vision"] = std::move(cv);
    res.set_content(j.dump(), "application/json");
  });

  // GET /frame.png — the last frame POSTed to /capture (kept even when the
  // table was not found in it, so the dashboard can show what failed).
  srv.Get("/frame.png", [this](const httplib::Request&, httplib::Response& res) {
    // Take a header copy first; the frame buffer is refcounted, so a
    // concurrent /capture swapping frame_ does not free what we encode.
    const cv::Mat frame = service_->last_frame();
    if (frame.empty()) {
      json_error(res, 404, "no frame yet, POST a screenshot to /capture first");
      return;
    }
    std::vector<unsigned char> png;
    if (!encode_png(frame, png)) {
      json_error(res, 500, "could not encode the last frame as PNG");
      return;
    }
    res.set_content(reinterpret_cast<const char*>(png.data()), png.size(), "image/png");
    res.set_header("Cache-Control", "no-store");
  });

  // POST /recognize-card — read one card crop with the mapping's card_vision
  // recognizer. The body is decoded first so a bad upload is reported as
  // such (400) whatever the mapping holds.
  srv.Post("/recognize-card", [this](const httplib::Request& req, httplib::Response& res) {
    if (req.body.empty()) {
      json_error(res, 400, "empty body, POST the PNG/JPEG bytes of one card crop");
      return;
    }
    const std::vector<unsigned char> bytes(req.body.begin(), req.body.end());
    // decode_image returns an empty Mat on any bad/undecodable input (it does
    // not throw), so a garbage upload falls straight through to the 400 below.
    cv::Mat card = decode_image(bytes, /*color=*/true);
    if (card.empty()) {
      json_error(res, 400, "could not decode the body as a PNG/JPEG image");
      return;
    }
    const vision::CardRecognizer* rec = scraper_->card_recognizer();
    if (!rec) {
      json_error(res, 409,
                 "card vision is not configured: add a \"card_vision\" section to the mapping");
      return;
    }
    const std::string slot = req.has_param("slot") ? req.get_param_value("slot") : "";
    nlohmann::json j = rec->recognize(card, slot).to_json();
    j["slot"] = slot;
    j["width"] = card.cols;
    j["height"] = card.rows;
    res.set_content(j.dump(), "application/json");
  });
}

}  // namespace glance
