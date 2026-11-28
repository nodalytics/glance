#pragma once

#include <cstddef>
#include <string_view>

#include <httplib.h>

#include "control_service.h"
#include "scraper.h"
#include "server.h"

namespace glance {

namespace web {

// One embedded dashboard file (glance/web/**, compiled in by
// cmake/embed_web.cmake). `path` is relative to glance/web ("index.html").
struct Asset {
  const char* path;
  const char* mime;
  const unsigned char* data;
  std::size_t size;
};

// Null-path-terminated table of every embedded file.
const Asset* assets();
// The asset at `path`, or nullptr.
const Asset* find_asset(std::string_view path);

}  // namespace web

// The web dashboard and its read-only helper routes, served by glance-server
// on the same port as the API:
//
//   GET  /                  the dashboard (embedded index.html)
//   GET  /assets/<file>     the dashboard's other embedded files
//   GET  /info              {"name","version","ocr_available","control_backend",
//                            "mapping":{"name","window_title","actions":[...]},
//                            "card_vision":{"configured","profile"?,
//                                           "suit_templates"?,"rank_templates"?}}
//   GET  /frame.png         the last frame POSTed to /capture, PNG; 404 when none
//   POST /recognize-card    raw PNG/JPEG bytes of ONE card crop, optional ?slot=
//                           200 CardReading::to_json(); 400 undecodable body;
//                           409 the mapping has no "card_vision" section
//
// Like ControlRoutes, the server and the webtest register the same object, so
// the handlers the test asserts are the ones the server runs. `control` may be
// nullptr (then "control_backend" is "none").
class DashboardRoutes {
 public:
  DashboardRoutes(ScreenshotService* service, TableScraper* scraper, ControlService* control);
  // Register every dashboard route on srv. Must only be called once per server.
  void install(httplib::Server& srv);

 private:
  ScreenshotService* service_;
  TableScraper* scraper_;
  ControlService* ctrl_;
};

}  // namespace glance
