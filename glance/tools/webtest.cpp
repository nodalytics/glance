// Dashboard route test: registers the SAME DashboardRoutes (and ControlRoutes,
// for POST /capture) that glance-server installs on an in-process server bound
// to an ephemeral port, then drives it over HTTP:
//
//   * GET /                 embedded HTML
//   * GET /assets/...       embedded CSS/JS with the right content types, 404
//                           for unknown names
//   * GET /info             name/version/ocr/control/mapping/card_vision fields
//   * GET /frame.png        404 before a capture, a PNG after one
//   * POST /recognize-card  400 on garbage bytes, 409 without card_vision
//
// The mapping is a minimal one synthesized into a temp dir (just an anchor
// template), so the test needs no fixtures and no tesseract.

#include <cstdio>
#include <filesystem>
#include <fstream>
#include <string>
#include <thread>
#include <vector>

#include <unistd.h>

#include <httplib.h>
#include <nlohmann/json.hpp>
#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

#include "control_service.h"
#include "scraper.h"
#include "server.h"
#include "server_control.h"
#include "server_dashboard.h"

namespace fs = std::filesystem;

static int failures = 0;

#define CHECK(cond, msg)                \
  do {                                  \
    if (cond) {                         \
      std::printf("  ok: %s\n", msg);   \
    } else {                            \
      std::printf("  FAIL: %s\n", msg); \
      ++failures;                       \
    }                                   \
    std::fflush(stdout);                \
  } while (0)

static bool starts_with(const std::string& s, const std::string& p) {
  return s.rfind(p, 0) == 0;
}

static nlohmann::json parse_or_null(const std::string& body) {
  return nlohmann::json::parse(body, nullptr, /*allow_exceptions=*/false);
}

int main() {
  const fs::path base = fs::temp_directory_path() / ("glance-webtest-" + std::to_string(::getpid()));
  fs::create_directories(base / "templates");

  // A noisy anchor that will not be found in a flat grey frame.
  cv::Mat anchor(24, 24, CV_8UC3);
  cv::randu(anchor, cv::Scalar::all(0), cv::Scalar::all(255));
  cv::imwrite((base / "templates" / "anchor.png").string(), anchor);
  nlohmann::json m;
  m["name"] = "webtest";
  m["crop"] = {{"x", 200}, {"y", 100}};
  m["topleft"] = "templates/anchor.png";
  m["actions"] = {{"call", "button:call"}};
  m["window_title"] = "webtest-table";
  {
    std::ofstream out(base / "mapping.json");
    out << m.dump(2) << "\n";
  }

  glance::TableScraper scraper;
  const bool loaded = scraper.load_mapping((base / "mapping.json").string());
  CHECK(loaded, "minimal mapping loads");
  if (!loaded) {
    std::printf("  mapping error: %s\n", scraper.error().c_str());
    fs::remove_all(base);
    return 1;
  }

  glance::ScreenshotService service(&scraper);
  glance::ControlService control(&scraper);
  glance::ControlRoutes control_routes(&service, &scraper, &control);
  glance::DashboardRoutes dashboard(&service, &scraper, &control);

  httplib::Server srv;
  srv.set_payload_max_length(16u * 1024 * 1024);
  control_routes.install(srv);
  dashboard.install(srv);
  const int port = srv.bind_to_any_port("127.0.0.1");
  CHECK(port > 0, "test server binds an ephemeral port");
  if (port <= 0) {
    fs::remove_all(base);
    return 1;
  }
  std::thread serve([&srv]() { srv.listen_after_bind(); });
  srv.wait_until_ready();
  httplib::Client cli("127.0.0.1", port);

  std::printf("webtest: static dashboard\n");
  {
    auto r = cli.Get("/");
    CHECK(r && r->status == 200, "GET / is 200");
    CHECK(r && starts_with(r->get_header_value("Content-Type"), "text/html"),
          "GET / is text/html");
    CHECK(r && r->body.find("<!doctype html>") != std::string::npos,
          "GET / carries the dashboard document");
    CHECK(r && r->body.find("/assets/app.js") != std::string::npos,
          "the dashboard references its embedded script");

    auto js = cli.Get("/assets/app.js");
    CHECK(js && js->status == 200 &&
              starts_with(js->get_header_value("Content-Type"), "text/javascript"),
          "GET /assets/app.js is served as JavaScript");
    // The web dashboard is view/analysis only: input injection (grab, click,
    // key, sequence) belongs to the desktop app, never to the browser. No
    // embedded file may call those routes or link a control page.
    {
      bool clean = true;
      for (const auto* a = glance::web::assets(); a->path; ++a) {
        const std::string body(reinterpret_cast<const char*>(a->data), a->size);
        for (const char* route : {"\"/grab\"", "\"/click\"", "\"/key\"", "\"/sequence\"",
                                  "#/control"}) {
          if (body.find(route) != std::string::npos) {
            std::printf("  (%s references %s)\n", a->path, route);
            clean = false;
          }
        }
      }
      CHECK(clean, "no embedded dashboard file calls a control (input) route");
    }
    auto css = cli.Get("/assets/app.css");
    CHECK(css && css->status == 200 &&
              starts_with(css->get_header_value("Content-Type"), "text/css"),
          "GET /assets/app.css is served as CSS");
    auto missing = cli.Get("/assets/nope.js");
    CHECK(missing && missing->status == 404, "unknown asset is 404");
    auto traversal = cli.Get("/assets/../mapping.json");
    CHECK(!traversal || traversal->status == 404 || traversal->status == 400,
          "a path-traversal asset name is not served");
  }

  std::printf("webtest: GET /info\n");
  {
    auto r = cli.Get("/info");
    CHECK(r && r->status == 200, "GET /info is 200");
    const auto j = r ? parse_or_null(r->body) : nlohmann::json();
    CHECK(j.is_object() && j.value("name", "") == "glance", "/info name is glance");
    CHECK(j.contains("version") && j["version"].is_string() &&
              j["version"].get<std::string>() == GLANCE_VERSION,
          "/info carries the compiled GLANCE_VERSION");
    CHECK(j.contains("ocr_available") && j["ocr_available"].is_boolean(),
          "/info reports ocr_available");
    CHECK(j.contains("control_backend") && j["control_backend"] == control.backend_name(),
          "/info reports the control backend name");
    CHECK(j.contains("mapping") && j["mapping"].value("name", "") == "webtest",
          "/info reports the mapping name");
    CHECK(j.contains("mapping") && j["mapping"]["actions"].is_array() &&
              j["mapping"]["actions"].size() == 1 &&
              j["mapping"]["actions"][0].value("name", "") == "call",
          "/info lists the mapping's named actions");
    CHECK(j.contains("card_vision") && j["card_vision"]["configured"] == false,
          "/info card_vision.configured is false without a card_vision section");
  }

  std::printf("webtest: GET /frame.png\n");
  {
    auto r = cli.Get("/frame.png");
    CHECK(r && r->status == 404, "GET /frame.png is 404 before any capture");

    cv::Mat shot(120, 160, CV_8UC3, cv::Scalar(90, 90, 90));
    std::vector<unsigned char> buf;
    cv::imencode(".png", shot, buf);
    auto c = cli.Post("/capture", std::string(buf.begin(), buf.end()), "image/png");
    CHECK(c && c->status == 422, "a frame without the table is a 422 capture");
    auto f = cli.Get("/frame.png");
    CHECK(f && f->status == 200 && f->get_header_value("Content-Type") == "image/png",
          "GET /frame.png serves the last captured frame as PNG");
    if (f && f->status == 200) {
      std::vector<unsigned char> png(f->body.begin(), f->body.end());
      cv::Mat back = cv::imdecode(png, cv::IMREAD_COLOR);
      CHECK(back.cols == 160 && back.rows == 120, "the served frame has the captured size");
    }
  }

  std::printf("webtest: POST /recognize-card\n");
  {
    auto e = cli.Post("/recognize-card", "", "application/octet-stream");
    CHECK(e && e->status == 400, "empty body is 400");
    auto g = cli.Post("/recognize-card", std::string("definitely not an image"),
                      "application/octet-stream");
    CHECK(g && g->status == 400, "garbage bytes are 400");
    CHECK(g && parse_or_null(g->body).contains("error"), "the 400 carries a JSON error");

    cv::Mat card(80, 56, CV_8UC3, cv::Scalar(250, 250, 250));
    cv::putText(card, "A", {6, 26}, cv::FONT_HERSHEY_SIMPLEX, 0.8, cv::Scalar(0, 0, 0), 2);
    std::vector<unsigned char> buf;
    cv::imencode(".png", card, buf);
    auto n = cli.Post("/recognize-card?slot=board1", std::string(buf.begin(), buf.end()),
                      "image/png");
    CHECK(n && n->status == 409, "a valid crop without card_vision is 409");
    CHECK(n && parse_or_null(n->body).contains("error"), "the 409 carries a JSON error");
  }

  srv.stop();
  serve.join();
  fs::remove_all(base);
  std::printf("webtest: %s (%d failure%s)\n", failures ? "FAILED" : "passed", failures,
              failures == 1 ? "" : "s");
  return failures ? 1 : 0;
}
