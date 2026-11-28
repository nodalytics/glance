#include "app_server.h"

#include <cstdio>

#include <httplib.h>
#include <nlohmann/json.hpp>

#include "control_service.h"
#include "packages.h"
#include "scraper.h"
#include "server.h"
#include "server_control.h"
#include "server_dashboard.h"
#include "server_slumbot.h"

namespace glance {

int serve(const ServeOptions& opts) {
  std::string mapping_path = opts.mapping_path;
  std::string active_package;
  if (!opts.package_spec.empty()) {
    std::string err;
    auto path = packages::resolve_mapping(opts.package_spec, err);
    if (!path) {
      std::fprintf(stderr, "glance: %s\n", err.c_str());
      return 1;
    }
    mapping_path = *path;
    active_package = opts.package_spec.substr(0, opts.package_spec.find(':'));
  }
  if (mapping_path.empty()) {
    std::fprintf(stderr, "glance: nothing to serve (give a mapping file or --package)\n");
    return 1;
  }

  TableScraper scraper;
  if (!scraper.load_mapping(mapping_path)) {
    std::fprintf(stderr, "glance: failed to load mapping %s: %s\n", mapping_path.c_str(),
                 scraper.error().c_str());
    return 1;
  }

  // The services live as long as this stack frame: every route handler only
  // runs while listen() below is active.
  ScreenshotService service(&scraper);
  ControlService control(&scraper);
  ControlRoutes routes(&service, &scraper, &control);
  DashboardRoutes dashboard(&service, &scraper, &control);
  SlumbotRoutes slumbot(&scraper, &control);
  std::fprintf(stderr, "glance control backend: %s\n", control.backend_name().c_str());

  httplib::Server srv;
  // Bound the request body: 16 MB covers realistic window screenshots
  // (a 1920x1080 capture is ~1-2 MB) while still protecting memory. The
  // form-urlencoded path (httplib's default content type for curl
  // --data-binary) carries its own 8 KB default limit; CMakeLists raised it.
  srv.set_payload_max_length(16u * 1024 * 1024);

  // Control surface: /health, POST /capture, /grab, /click, /key, /sequence.
  routes.install(srv);
  // Web dashboard (GET /, /assets/...) + GET /info, /frame.png,
  // POST /recognize-card. Embedded at build time (cmake/embed_web.cmake).
  dashboard.install(srv);
  // Slumbot-mirroring control plane (POST /login, /new_hand, /act): a thin
  // control + translation surface over the services above, under glance's
  // plain flat paths (never /slumbot/... or /api/...).
  slumbot.install(srv);

  // GET /state — the last successfully parsed state.
  srv.Get("/state", [&service](const httplib::Request&, httplib::Response& res) {
    if (!service.has_state()) {
      nlohmann::json j;
      j["error"] = "no state yet, POST a screenshot to /capture first";
      res.status = 404;
      res.set_content(j.dump(), "application/json");
      return;
    }
    res.set_content(service.state_json().dump(), "application/json");
  });

  // GET /packages — installed packages and the active one. Read-only:
  // installing/removing is the `glance pkg` CLI's job, never the network's.
  srv.Get("/packages", [active_package](const httplib::Request&, httplib::Response& res) {
    std::vector<std::string> problems;
    nlohmann::json list = nlohmann::json::array();
    for (const auto& p : packages::list_packages(&problems)) list.push_back(p.to_json());
    nlohmann::json j;
    j["active"] = active_package.empty() ? nlohmann::json(nullptr) : nlohmann::json(active_package);
    j["packages"] = list;
    j["problems"] = problems;
    res.set_content(j.dump(), "application/json");
  });

  std::fprintf(stderr, "glance listening on %s:%d (dashboard at http://localhost:%d/)\n", opts.host.c_str(),
               opts.port, opts.port);
  return srv.listen(opts.host, opts.port) ? 0 : 1;
}

}  // namespace glance
