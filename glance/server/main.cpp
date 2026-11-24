#include <cstdio>
#include <cstdlib>
#include <string>

#include <httplib.h>
#include <nlohmann/json.hpp>

#include "acr_scraper.h"
#include "scraper.h"
#include "server.h"

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
  glance::ScreenshotService service(acr.core_scraper());

  httplib::Server srv;

  srv.Get("/health", [](const httplib::Request&, httplib::Response& res) {
    nlohmann::json j;
    j["status"] = "ok";
    res.set_content(j.dump(), "application/json");
  });

  // POST /capture  body: raw PNG/JPEG bytes of the poker window.
  // Returns the parsed table state as JSON, or a 422 when the table is not
  // found in the image.
  srv.Post("/capture", [&service](const httplib::Request& req, httplib::Response& res) {
    nlohmann::json j;
    const std::vector<unsigned char> img(req.body.begin(), req.body.end());
    if (!service.update(img)) {
      j["error"] = "could not decode image or table not found";
      res.status = 422;
      res.set_content(j.dump(), "application/json");
      return;
    }
    res.set_content(service.state_json().dump(), "application/json");
  });

  // GET /state  the last successfully parsed state.
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
