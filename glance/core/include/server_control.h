#pragma once

#include <httplib.h>

#include "control_service.h"
#include "server.h"

namespace glance {

// The control surface as HTTP routes: POST /grab, POST /click, POST /key,
// POST /sequence, the /health extension (control backend + active grab
// source), and the /capture hook (a successful client POST becomes the
// control's input-space reference).
//
// The routes are exactly what server/main.cpp registers: main calls install()
// once at startup, and the selftest registers the same object in-process on an
// ephemeral port so the handler code the server actually runs is what the
// selftest asserts (the same pattern as the 413-regression round-trip).
//
// /capture is registered here, not in the server, so the externally_parsed
// hook cannot drift from the state handler — a process has exactly one
// /capture route.
class ControlRoutes {
 public:
  ControlRoutes(ScreenshotService* service, TableScraper* scraper, ControlService* control);
  // Register every control route on srv. Must only be called once per server.
  void install(httplib::Server& srv);

 private:
  ScreenshotService* service_;
  TableScraper* scraper_;
  ControlService* ctrl_;
};

}  // namespace glance
