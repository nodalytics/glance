#pragma once

// glance packages: installable support for operating one piece of software.
//
// The engine (core/) never knows what it is looking at; a PACKAGE teaches it
// one application: where its window is, what to look for and where (table
// mappings + template/glyph PNGs), which named actions exist. Packages are
// pure data, so they install the same way on Linux, Windows and macOS with no
// compiler. ACR Poker ships as the default package `acr`
// (glance/packages/acr/).
//
// A package is a directory holding `glance-package.json`:
//
//   {
//     "name": "acr",                       // [a-z0-9][a-z0-9._-]*, unique
//     "version": "0.1.0",
//     "description": "ACR Poker tables",
//     "glance": ">=0.2.0",                 // minimum engine version (optional)
//     "app": { "name": "ACR Poker",        // what it operates (optional)
//              "url": "https://www.acrpoker.eu/",
//              "window_title": "ACR" },
//     "mappings": { "6max": "mappings/6max.json" },  // name -> mapping file
//     "default_mapping": "6max"            // optional when only one mapping
//   }
//
// Mapping files are ordinary table mappings (core/include/mapping.h), with
// paths relative to the mapping file. Search path, first hit wins:
//   1. $GLANCE_PACKAGES_PATH (':'-separated; ';' on Windows)
//   2. the user package dir (user_package_dir(): `glance pkg install` target)
//   3. the built-in packages shipped with glance (GLANCE_BUILTIN_PACKAGES_DIR)

#include <optional>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

namespace glance::packages {

struct Package {
  std::string name;
  std::string version;
  std::string description;
  std::string min_glance;  // "" when unconstrained
  std::string app_name, app_url, window_title;
  std::vector<std::pair<std::string, std::string>> mappings;  // name -> abs path
  std::string default_mapping;
  std::string dir;     // absolute package directory
  std::string source;  // "builtin" | "user" | "env"
  // Absolute path of a mapping by name ("" = default). nullopt if unknown.
  std::optional<std::string> mapping_path(const std::string& name = "") const;
  nlohmann::json to_json() const;
};

// Parse and validate <dir>/glance-package.json (mapping files must exist).
// On failure returns nullopt and sets err.
std::optional<Package> load_package(const std::string& dir, std::string& err);

// Every package directory on the search path, in priority order (a name
// found earlier shadows later ones).
struct SearchDir {
  std::string path;
  std::string source;  // "env" | "user" | "builtin"
};
std::vector<SearchDir> search_path();
std::string user_package_dir();
std::string builtin_package_dir();

// All installed packages (shadowed duplicates dropped). Invalid package dirs
// are reported through `problems` (may be null).
std::vector<Package> list_packages(std::vector<std::string>* problems = nullptr);
std::optional<Package> find_package(const std::string& name);

// "acr" or "acr:6max" -> mapping file path. Sets err on failure.
std::optional<std::string> resolve_mapping(const std::string& spec, std::string& err);

// Install from a local directory (copied) or a git URL (shallow clone; needs
// `git` on PATH) into user_package_dir()/<name>. `force` replaces an
// existing install. Returns the installed package or nullopt + err.
std::optional<Package> install_package(const std::string& source, bool force, std::string& err);
// Remove a user-installed package (built-ins cannot be removed).
bool remove_package(const std::string& name, std::string& err);

// Dotted numeric version compare ("0.10.1" > "0.9"): <0, 0, >0.
int compare_versions(const std::string& a, const std::string& b);
bool valid_package_name(const std::string& name);

}  // namespace glance::packages
