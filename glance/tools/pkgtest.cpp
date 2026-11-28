// Package manager checks: manifest validation, the built-in acr package,
// install/remove round-trip into a scratch user dir, search-path shadowing,
// mapping resolution and version comparison. No network, no display.

#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <random>
#include <string>

#include <nlohmann/json.hpp>

#include "packages.h"

#ifndef GLANCE_SOURCE_PACKAGES_DIR
#define GLANCE_SOURCE_PACKAGES_DIR "packages"
#endif

namespace fs = std::filesystem;
namespace pk = glance::packages;

static int failures = 0;
#define CHECK(cond, msg)                  \
  do {                                    \
    if (cond) {                           \
      std::printf("  ok: %s\n", msg);     \
    } else {                              \
      std::printf("  FAIL: %s\n", msg);   \
      ++failures;                         \
    }                                     \
    std::fflush(stdout);                  \
  } while (0)

static void set_env(const char* k, const std::string& v) {
#ifdef _WIN32
  _putenv_s(k, v.c_str());
#else
  setenv(k, v.c_str(), 1);
#endif
}

static void write(const fs::path& p, const std::string& s) {
  fs::create_directories(p.parent_path());
  std::ofstream(p) << s;
}

static void make_pkg(const fs::path& dir, const std::string& name, const std::string& version,
                     const std::string& extra = "") {
  write(dir / "maps" / "main.json", R"({"name":"t","crop":{"x":10,"y":10},"topleft":"a.png"})");
  write(dir / "glance-package.json", R"({"name":")" + name + R"(","version":")" + version +
                                         R"(","mappings":{"main":"maps/main.json"})" + extra + "}");
}

int main() {
  std::mt19937_64 rng{std::random_device{}()};
  const fs::path base = fs::temp_directory_path() / ("glance_pkgtest_" + std::to_string(rng()));
  fs::create_directories(base);
  set_env("GLANCE_USER_PACKAGES", (base / "user").string());
  set_env("GLANCE_BUILTIN_PACKAGES", GLANCE_SOURCE_PACKAGES_DIR);
  set_env("GLANCE_PACKAGES_PATH", "");
  std::string err;

  std::printf("versions:\n");
  CHECK(pk::compare_versions("0.10.0", "0.9.9") > 0, "0.10.0 > 0.9.9");
  CHECK(pk::compare_versions("1.2", "1.2.0") == 0, "1.2 == 1.2.0");
  CHECK(pk::compare_versions("1.2.3-beta", "1.2.4") < 0, "1.2.3-beta < 1.2.4");
  CHECK(pk::valid_package_name("acr") && pk::valid_package_name("my-app.v2"), "valid names");
  CHECK(!pk::valid_package_name("Acr") && !pk::valid_package_name("../x") && !pk::valid_package_name(""),
        "invalid names rejected");

  std::printf("built-in acr:\n");
  auto acr = pk::find_package("acr");
  CHECK(acr.has_value(), "acr is installed as a built-in package");
  if (acr) {
    CHECK(acr->source == "builtin", "acr source is builtin");
    CHECK(acr->default_mapping == "6max" && acr->mapping_path().has_value(), "acr default mapping 6max");
    CHECK(acr->window_title == "ACR", "acr window title");
  }
  auto m = pk::resolve_mapping("acr:6max", err);
  CHECK(m && fs::exists(*m), "resolve acr:6max to an existing file");
  CHECK(!pk::resolve_mapping("acr:nope", err), "unknown mapping rejected");
  CHECK(!pk::resolve_mapping("nope", err), "unknown package rejected");

  std::printf("manifest validation:\n");
  make_pkg(base / "src" / "good", "good", "1.0.0");
  CHECK(pk::load_package((base / "src" / "good").string(), err).has_value(), "valid manifest loads");
  make_pkg(base / "src" / "badname", "Bad Name", "1.0.0");
  CHECK(!pk::load_package((base / "src" / "badname").string(), err), "bad name rejected");
  make_pkg(base / "src" / "future", "future", "1.0.0", R"(,"glance":">=99.0")");
  CHECK(!pk::load_package((base / "src" / "future").string(), err), "too-new engine requirement rejected");
  write(base / "src" / "escape" / "glance-package.json",
        R"({"name":"escape","version":"1","mappings":{"m":"../good/maps/main.json"}})");
  CHECK(!pk::load_package((base / "src" / "escape").string(), err), "mapping outside the package rejected");
  write(base / "src" / "missing" / "glance-package.json",
        R"({"name":"missing","version":"1","mappings":{"m":"nope.json"}})");
  CHECK(!pk::load_package((base / "src" / "missing").string(), err), "missing mapping file rejected");
  write(base / "src" / "two" / "glance-package.json",
        R"({"name":"two","version":"1","mappings":{"a":"glance-package.json","b":"glance-package.json"}})");
  CHECK(!pk::load_package((base / "src" / "two").string(), err), "several mappings need default_mapping");

  std::printf("install / remove:\n");
  auto inst = pk::install_package((base / "src" / "good").string(), false, err);
  CHECK(inst && inst->source == "user", "install from a directory");
  CHECK(fs::exists(base / "user" / "good" / "glance-package.json"), "copied into the user dir");
  CHECK(pk::find_package("good").has_value(), "installed package is listed");
  CHECK(!pk::install_package((base / "src" / "good").string(), false, err), "reinstall without --force refused");
  make_pkg(base / "src" / "good2", "good", "2.0.0");
  auto up = pk::install_package((base / "src" / "good2").string(), true, err);
  CHECK(up && up->version == "2.0.0", "--force replaces (upgrade to 2.0.0)");
  CHECK(!pk::install_package((base / "src" / "badname").string(), false, err), "invalid package not installed");
  CHECK(!pk::remove_package("acr", err), "built-in package cannot be removed");
  CHECK(pk::remove_package("good", err) && !pk::find_package("good"), "remove a user package");

  std::printf("search path:\n");
  make_pkg(base / "env" / "acr", "acr", "9.9.9");
  set_env("GLANCE_PACKAGES_PATH", (base / "env").string());
  auto sh = pk::find_package("acr");
  CHECK(sh && sh->version == "9.9.9" && sh->source == "env", "$GLANCE_PACKAGES_PATH shadows the built-in");
  set_env("GLANCE_PACKAGES_PATH", "");
  nlohmann::json j = pk::find_package("acr")->to_json();
  CHECK(j["name"] == "acr" && j["mappings"].size() == 1, "package JSON");

  std::error_code ec;
  fs::remove_all(base, ec);
  std::printf(failures ? "pkgtest: FAIL (%d)\n" : "pkgtest: PASS\n", failures);
  return failures ? 1 : 0;
}
