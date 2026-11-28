#pragma once

#include <string>

namespace glance {

// Everything `glance serve` / `glance-server` needs to run the HTTP API.
struct ServeOptions {
  // Exactly one of: a table-mapping JSON file, or an installed package spec
  // ("acr" or "acr:6max", see core/include/packages.h).
  std::string mapping_path;
  std::string package_spec;
  std::string host = "0.0.0.0";
  int port = 8000;
};

// Load the mapping, build the services and serve the full HTTP API (state,
// capture, control, dashboard, packages) until the server stops. Returns the
// process exit code; errors are printed to stderr.
int serve(const ServeOptions& opts);

}  // namespace glance
