// glance — the command-line front end.
//
//   glance serve [--package SPEC | --mapping FILE] [--host H] [--port N]
//   glance pkg list [--json] | info NAME | install SRC [--force] | remove NAME
//             | validate DIR | paths
//   glance health | info | state | packages              [--url URL]
//   glance capture IMAGE                                  [--url URL]
//   glance read-card IMAGE [--slot NAME]                  [--url URL]
//   glance version
//
// Client commands talk to a running server over the HTTP API (default URL
// http://127.0.0.1:8000, or $GLANCE_URL) and print its JSON. Admin input
// injection (/click, /key, ...) is deliberately not exposed here: that is the
// Qt admin app's job (or plain HTTP for integrations).

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <map>
#include <string>
#include <vector>

#include <httplib.h>
#include <nlohmann/json.hpp>

#include "app_server.h"
#include "packages.h"

#ifndef GLANCE_VERSION
#define GLANCE_VERSION "0.0.0"
#endif

namespace pk = glance::packages;

namespace {

struct Args {
  std::vector<std::string> pos;
  std::map<std::string, std::string> opt;
  bool flag(const std::string& k) const { return opt.count(k) > 0; }
  std::string get(const std::string& k, const std::string& d = "") const {
    auto it = opt.find(k);
    return it == opt.end() ? d : it->second;
  }
};

// Flags that take no value.
bool is_switch(const std::string& k) { return k == "json" || k == "force" || k == "help"; }

Args parse(int argc, char** argv, int from) {
  Args a;
  for (int i = from; i < argc; ++i) {
    std::string s = argv[i];
    if (s.rfind("--", 0) == 0) {
      std::string k = s.substr(2);
      const auto eq = k.find('=');
      if (eq != std::string::npos) {
        a.opt[k.substr(0, eq)] = k.substr(eq + 1);
      } else if (is_switch(k) || i + 1 >= argc) {
        a.opt[k] = "1";
      } else {
        a.opt[k] = argv[++i];
      }
    } else {
      a.pos.push_back(s);
    }
  }
  return a;
}

int usage(int code = 2) {
  std::fprintf(code == 0 ? stdout : stderr,
               "glance %s — screen-reading + control engine\n\n"
               "usage:\n"
               "  glance serve [--package SPEC | --mapping FILE] [--host H] [--port N]\n"
               "  glance pkg list [--json]        installed packages (built-in + user + $GLANCE_PACKAGES_PATH)\n"
               "  glance pkg info NAME\n"
               "  glance pkg install DIR|GIT-URL [--force]\n"
               "  glance pkg remove NAME\n"
               "  glance pkg validate DIR\n"
               "  glance pkg paths                the package search path\n"
               "  glance health|info|state|packages [--url URL]\n"
               "  glance capture IMAGE [--url URL]\n"
               "  glance read-card IMAGE [--slot NAME] [--url URL]\n"
               "  glance version\n\n"
               "SPEC is a package name, optionally with a mapping: acr, acr:6max.\n"
               "URL defaults to $GLANCE_URL or http://127.0.0.1:8000.\n",
               GLANCE_VERSION);
  return code;
}

// ---------------------------------------------------------------- serve

int cmd_serve(const Args& a) {
  if (a.flag("help")) return usage(0);
  glance::ServeOptions o;
  o.package_spec = a.get("package");
  o.mapping_path = a.get("mapping");
  if (!a.pos.empty() && o.package_spec.empty() && o.mapping_path.empty()) o.package_spec = a.pos[0];
  if (o.package_spec.empty() && o.mapping_path.empty()) o.package_spec = "acr";  // the default package
  if (!o.package_spec.empty() && !o.mapping_path.empty()) {
    std::fprintf(stderr, "glance serve: give --package or --mapping, not both\n");
    return 2;
  }
  o.host = a.get("host", o.host);
  if (a.flag("port")) o.port = std::atoi(a.get("port").c_str());
  return glance::serve(o);
}

// ---------------------------------------------------------------- pkg

int cmd_pkg(const Args& a) {
  if (a.pos.empty()) return usage();
  const std::string sub = a.pos[0];
  std::string err;
  if (sub == "list") {
    std::vector<std::string> problems;
    const auto list = pk::list_packages(&problems);
    if (a.flag("json")) {
      nlohmann::json j = nlohmann::json::array();
      for (const auto& p : list) j.push_back(p.to_json());
      std::printf("%s\n", j.dump(2).c_str());
    } else {
      if (list.empty()) std::printf("no packages installed\n");
      for (const auto& p : list)
        std::printf("%-16s %-9s %-8s %s\n", p.name.c_str(), p.version.c_str(), p.source.c_str(),
                    p.description.c_str());
    }
    for (const auto& pr : problems) std::fprintf(stderr, "warning: %s\n", pr.c_str());
    return 0;
  }
  if (sub == "info" && a.pos.size() == 2) {
    auto p = pk::find_package(a.pos[1]);
    if (!p) {
      std::fprintf(stderr, "glance: no installed package named '%s'\n", a.pos[1].c_str());
      return 1;
    }
    nlohmann::json j = p->to_json();
    nlohmann::json maps = nlohmann::json::object();
    for (const auto& [n, path] : p->mappings) maps[n] = path;
    j["mappings"] = maps;
    std::printf("%s\n", j.dump(2).c_str());
    return 0;
  }
  if (sub == "install" && a.pos.size() == 2) {
    auto p = pk::install_package(a.pos[1], a.flag("force"), err);
    if (!p) {
      std::fprintf(stderr, "glance: install failed: %s\n", err.c_str());
      return 1;
    }
    std::printf("installed %s %s into %s\n", p->name.c_str(), p->version.c_str(), p->dir.c_str());
    return 0;
  }
  if (sub == "remove" && a.pos.size() == 2) {
    if (!pk::remove_package(a.pos[1], err)) {
      std::fprintf(stderr, "glance: %s\n", err.c_str());
      return 1;
    }
    std::printf("removed %s\n", a.pos[1].c_str());
    return 0;
  }
  if (sub == "validate" && a.pos.size() == 2) {
    auto p = pk::load_package(a.pos[1], err);
    if (!p) {
      std::fprintf(stderr, "invalid: %s\n", err.c_str());
      return 1;
    }
    std::printf("ok: %s %s (%zu mapping(s), default '%s')\n", p->name.c_str(), p->version.c_str(),
                p->mappings.size(), p->default_mapping.c_str());
    return 0;
  }
  if (sub == "paths") {
    for (const auto& sd : pk::search_path()) std::printf("%-8s %s\n", sd.source.c_str(), sd.path.c_str());
    return 0;
  }
  return usage();
}

// ---------------------------------------------------------------- client

std::string base_url(const Args& a) {
  std::string u = a.get("url");
  if (u.empty()) {
    const char* e = std::getenv("GLANCE_URL");
    u = e ? e : "http://127.0.0.1:8000";
  }
  while (!u.empty() && u.back() == '/') u.pop_back();
  return u;
}

int print_response(const httplib::Result& r, const std::string& what) {
  if (!r) {
    std::fprintf(stderr, "glance: %s: cannot reach server (%s)\n", what.c_str(),
                 httplib::to_string(r.error()).c_str());
    return 1;
  }
  const auto j = nlohmann::json::parse(r->body, nullptr, false);
  if (!j.is_discarded())
    std::printf("%s\n", j.dump(2).c_str());
  else
    std::printf("%s\n", r->body.c_str());
  return r->status >= 200 && r->status < 300 ? 0 : 1;
}

bool read_file(const std::string& path, std::string& out) {
  std::ifstream in(path, std::ios::binary);
  if (!in) return false;
  out.assign(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
  return true;
}

std::string content_type_for(const std::string& path) {
  auto ends = [&](const char* e) {
    const std::string s(e);
    return path.size() >= s.size() && path.compare(path.size() - s.size(), s.size(), s) == 0;
  };
  return ends(".jpg") || ends(".jpeg") || ends(".JPG") || ends(".JPEG") ? "image/jpeg" : "image/png";
}

int cmd_client(const std::string& cmd, const Args& a) {
  httplib::Client cli(base_url(a));
  cli.set_connection_timeout(5);
  cli.set_read_timeout(60);
  if (cmd == "health" || cmd == "info" || cmd == "state" || cmd == "packages")
    return print_response(cli.Get("/" + cmd), cmd);
  if ((cmd == "capture" || cmd == "read-card") && a.pos.size() == 1) {
    std::string body;
    if (!read_file(a.pos[0], body)) {
      std::fprintf(stderr, "glance: cannot read %s\n", a.pos[0].c_str());
      return 1;
    }
    std::string path = cmd == "capture" ? "/capture" : "/recognize-card";
    if (cmd == "read-card" && a.flag("slot")) path += "?slot=" + httplib::encode_uri_component(a.get("slot"));
    return print_response(cli.Post(path, body, content_type_for(a.pos[0])), cmd);
  }
  return usage();
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) return usage();
  const std::string cmd = argv[1];
  const Args a = parse(argc, argv, 2);
  if (cmd == "-h" || cmd == "--help" || cmd == "help") return usage(0);
  if (cmd == "version" || cmd == "--version") {
    std::printf("glance %s\n", GLANCE_VERSION);
    return 0;
  }
  if (cmd == "serve") return cmd_serve(a);
  if (cmd == "pkg") return cmd_pkg(a);
  if (cmd == "health" || cmd == "info" || cmd == "state" || cmd == "packages" || cmd == "capture" ||
      cmd == "read-card")
    return cmd_client(cmd, a);
  return usage();
}
