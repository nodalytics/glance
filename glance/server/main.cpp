// glance-server: compatibility entry point. `glance serve` (tools/glance_cli.cpp)
// is the full command; both run glance::serve().
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <string>

#include "app_server.h"

int main(int argc, char** argv) {
  if (argc < 2) {
    std::fprintf(stderr,
                 "usage: glance-server <table-mapping.json | package[:mapping]> [port]\n"
                 "  e.g. glance-server acr 8000   (the built-in ACR package)\n"
                 "  see also: glance serve --help\n");
    return 1;
  }
  glance::ServeOptions opts;
  const std::string target = argv[1];
  std::error_code ec;
  if (std::filesystem::is_regular_file(target, ec))
    opts.mapping_path = target;
  else
    opts.package_spec = target;
  if (argc >= 3) opts.port = std::atoi(argv[2]);
  return glance::serve(opts);
}
