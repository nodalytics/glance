#include <cstdio>
#include <cstdlib>
#include <string>

#include <httplib.h>
#include <nlohmann/json.hpp>

#include "acr_scraper.h"
#include "scraper.h"
#include "server.h"
#include "server_control.h"
#include "control_service.h"

namespace {

void usage() {
  std::fprintf(stderr,
                "usage: glance-server <table-mapping.json> [port]\n"
                "  <table-mapping.json>  path to the ACR table mapping JSON\n"
                "  [port]                HTTP port (default 8000)\n");
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) {
    usage();
    return 1;
  }
  const std::string mapping_path = argv[1];
  int port = 8000;
  if (argc >= 3) port = std::atoi(argv[2]);

  glance::acr::AcrScraper acr;
  if (!acr.load_mapping(mapping_path)) {
    std::fprintf(stderr, "failed to load mapping: %s\n", acr.error().c_str());
    return 1;
  }

  // The services live as long as this stack frame: every route handler only
  // runs while listen() below is active, i.e. before main returns.
  glance::ScreenshotService service(acr.core_scraper());
  glance::ControlService control(acr.core_scraper());
  glance::ControlRoutes routes(&service, acr.core_scraper(), &control);
  std::fprintf(stderr, "glance control backend: %s\n", control.backend_name().c_str());

  httplib::Server srv;
  // Bound the request body: 16 MB covers realistic window screenshots
  // (a 1920x1080 capture is ~1-2 MB) while still protecting memory. The
  // form-urlencoded path (httplib's default content type for curl
  // --data-binary) carries its own 8 KB default limit; CMakeLists raised it
  // to match, since POST /capture is the only POST route and takes raw
  // image bytes.
  srv.set_payload_max_length(16u * 1024 * 1024);

  // The control surface registers its own routes: /health (extended with the
  // control backend info), POST /capture (parse + record the frame as the
  // control's input-space reference), POST /grab, /click, /key, /sequence.
  routes.install(srv);

  // GET /state — the last successfully parsed table state.
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

  std::fprintf(stderr, "glance server listening on :%d\n", port);
  return srv.listen("0.0.0.0", port) ? 0 : 1;
}
