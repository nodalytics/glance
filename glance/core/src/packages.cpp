#include "packages.h"

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <random>
#include <set>

#ifndef GLANCE_BUILTIN_PACKAGES_DIR
#define GLANCE_BUILTIN_PACKAGES_DIR ""
#endif
#ifndef GLANCE_INSTALLED_PACKAGES_DIR
#define GLANCE_INSTALLED_PACKAGES_DIR ""
#endif
#ifndef GLANCE_VERSION
#define GLANCE_VERSION "0.0.0"
#endif

namespace fs = std::filesystem;

namespace glance::packages {

namespace {

constexpr const char* kManifest = "glance-package.json";

#ifdef _WIN32
constexpr char kPathSep = ';';
#else
constexpr char kPathSep = ':';
#endif

std::string env(const char* name) {
  const char* v = std::getenv(name);
  return v ? std::string(v) : std::string();
}

std::string str_field(const nlohmann::json& j, const char* key) {
  return j.contains(key) && j[key].is_string() ? j[key].get<std::string>() : std::string();
}

std::vector<int> version_parts(const std::string& v) {
  std::vector<int> out;
  int cur = 0;
  bool any = false;
  for (char c : v) {
    if (c >= '0' && c <= '9') {
      cur = cur * 10 + (c - '0');
      any = true;
    } else if (c == '.') {
      out.push_back(cur);
      cur = 0;
      any = false;
    } else {
      break;  // "1.2.3-beta": compare the numeric prefix only
    }
  }
  if (any || out.empty()) out.push_back(cur);
  return out;
}

// Quote one argument for the platform shell.
std::string shell_quote(const std::string& s) {
#ifdef _WIN32
  std::string out = "\"";
  for (char c : s) out += (c == '"') ? std::string("\\\"") : std::string(1, c);
  return out + "\"";
#else
  std::string out = "'";
  for (char c : s) out += (c == '\'') ? std::string("'\\''") : std::string(1, c);
  return out + "'";
#endif
}

bool looks_like_git_url(const std::string& s) {
  auto starts = [&](const char* p) { return s.rfind(p, 0) == 0; };
  return starts("https://") || starts("http://") || starts("git@") || starts("ssh://") ||
         starts("git://") || (s.size() > 4 && s.compare(s.size() - 4, 4, ".git") == 0);
}

}  // namespace

bool valid_package_name(const std::string& name) {
  if (name.empty() || name.size() > 64) return false;
  auto ok_first = [](char c) { return (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9'); };
  if (!ok_first(name[0])) return false;
  return std::all_of(name.begin(), name.end(),
                     [&](char c) { return ok_first(c) || c == '.' || c == '_' || c == '-'; });
}

int compare_versions(const std::string& a, const std::string& b) {
  auto pa = version_parts(a), pb = version_parts(b);
  const size_t n = std::max(pa.size(), pb.size());
  pa.resize(n, 0);
  pb.resize(n, 0);
  for (size_t i = 0; i < n; ++i)
    if (pa[i] != pb[i]) return pa[i] < pb[i] ? -1 : 1;
  return 0;
}

std::optional<std::string> Package::mapping_path(const std::string& name) const {
  const std::string want = name.empty() ? default_mapping : name;
  for (const auto& [n, p] : mappings)
    if (n == want) return p;
  return std::nullopt;
}

nlohmann::json Package::to_json() const {
  nlohmann::json j;
  j["name"] = name;
  j["version"] = version;
  j["description"] = description;
  if (!min_glance.empty()) j["glance"] = min_glance;
  nlohmann::json app = nlohmann::json::object();
  if (!app_name.empty()) app["name"] = app_name;
  if (!app_url.empty()) app["url"] = app_url;
  if (!window_title.empty()) app["window_title"] = window_title;
  j["app"] = app;
  nlohmann::json maps = nlohmann::json::array();
  for (const auto& [n, p] : mappings) maps.push_back(n);
  j["mappings"] = maps;
  j["default_mapping"] = default_mapping;
  j["source"] = source;
  j["dir"] = dir;
  return j;
}

std::optional<Package> load_package(const std::string& dir_in, std::string& err) {
  std::error_code ec;
  const fs::path dir = fs::absolute(dir_in, ec);
  const fs::path manifest = dir / kManifest;
  std::ifstream in(manifest);
  if (!in) {
    err = "no " + std::string(kManifest) + " in " + dir.string();
    return std::nullopt;
  }
  nlohmann::json j;
  try {
    in >> j;
  } catch (const std::exception& e) {
    err = manifest.string() + ": invalid JSON: " + e.what();
    return std::nullopt;
  }
  if (!j.is_object()) {
    err = manifest.string() + ": must be a JSON object";
    return std::nullopt;
  }
  Package p;
  p.dir = dir.string();
  p.name = str_field(j, "name");
  p.version = str_field(j, "version");
  p.description = str_field(j, "description");
  p.min_glance = str_field(j, "glance");
  if (!valid_package_name(p.name)) {
    err = manifest.string() + ": \"name\" must match [a-z0-9][a-z0-9._-]* (got '" + p.name + "')";
    return std::nullopt;
  }
  if (p.version.empty()) {
    err = manifest.string() + ": missing \"version\"";
    return std::nullopt;
  }
  if (!p.min_glance.empty()) {
    std::string need = p.min_glance;
    if (need.rfind(">=", 0) == 0) need = need.substr(2);
    if (compare_versions(GLANCE_VERSION, need) < 0) {
      err = p.name + " needs glance " + p.min_glance + " (this is " + GLANCE_VERSION + ")";
      return std::nullopt;
    }
  }
  if (j.contains("app") && j["app"].is_object()) {
    p.app_name = str_field(j["app"], "name");
    p.app_url = str_field(j["app"], "url");
    p.window_title = str_field(j["app"], "window_title");
  }
  if (!j.contains("mappings") || !j["mappings"].is_object() || j["mappings"].empty()) {
    err = manifest.string() + ": \"mappings\" must be a non-empty object name -> file";
    return std::nullopt;
  }
  for (auto it = j["mappings"].begin(); it != j["mappings"].end(); ++it) {
    if (!it.value().is_string()) {
      err = manifest.string() + ": mappings." + it.key() + " must be a path string";
      return std::nullopt;
    }
    const fs::path rel = it.value().get<std::string>();
    // Mapping files must stay inside the package.
    const fs::path abs = fs::weakly_canonical(dir / rel, ec);
    const std::string base = fs::weakly_canonical(dir, ec).string();
    if (rel.is_absolute() || abs.string().rfind(base, 0) != 0) {
      err = manifest.string() + ": mappings." + it.key() + " must be a path inside the package";
      return std::nullopt;
    }
    if (!fs::is_regular_file(abs, ec)) {
      err = manifest.string() + ": mappings." + it.key() + " -> missing file " + abs.string();
      return std::nullopt;
    }
    p.mappings.emplace_back(it.key(), abs.string());
  }
  p.default_mapping = str_field(j, "default_mapping");
  if (p.default_mapping.empty()) {
    if (p.mappings.size() != 1) {
      err = manifest.string() + ": several mappings, so \"default_mapping\" is required";
      return std::nullopt;
    }
    p.default_mapping = p.mappings[0].first;
  }
  if (!p.mapping_path()) {
    err = manifest.string() + ": default_mapping '" + p.default_mapping + "' is not in mappings";
    return std::nullopt;
  }
  return p;
}

std::string user_package_dir() {
  const std::string over = env("GLANCE_USER_PACKAGES");
  if (!over.empty()) return over;
#ifdef _WIN32
  std::string base = env("APPDATA");
  if (base.empty()) base = env("USERPROFILE");
  return (fs::path(base) / "glance" / "packages").string();
#elif defined(__APPLE__)
  return (fs::path(env("HOME")) / "Library" / "Application Support" / "glance" / "packages").string();
#else
  std::string base = env("XDG_DATA_HOME");
  if (base.empty()) base = (fs::path(env("HOME")) / ".local" / "share").string();
  return (fs::path(base) / "glance" / "packages").string();
#endif
}

std::string builtin_package_dir() {
  const std::string over = env("GLANCE_BUILTIN_PACKAGES");
  if (!over.empty()) return over;
  // Installed copy first (share/glance/packages), then the source tree the
  // binary was built from (development builds).
  std::error_code ec;
  for (const char* d : {GLANCE_INSTALLED_PACKAGES_DIR, GLANCE_BUILTIN_PACKAGES_DIR})
    if (*d && fs::is_directory(d, ec)) return d;
  return "";
}

std::vector<SearchDir> search_path() {
  std::vector<SearchDir> out;
  const std::string extra = env("GLANCE_PACKAGES_PATH");
  size_t start = 0;
  while (start <= extra.size() && !extra.empty()) {
    size_t end = extra.find(kPathSep, start);
    if (end == std::string::npos) end = extra.size();
    if (end > start) out.push_back({extra.substr(start, end - start), "env"});
    start = end + 1;
  }
  out.push_back({user_package_dir(), "user"});
  if (!builtin_package_dir().empty()) out.push_back({builtin_package_dir(), "builtin"});
  return out;
}

std::vector<Package> list_packages(std::vector<std::string>* problems) {
  std::vector<Package> out;
  std::set<std::string> seen;
  for (const auto& sd : search_path()) {
    std::error_code ec;
    if (!fs::is_directory(sd.path, ec)) continue;
    std::vector<fs::path> dirs;
    for (const auto& e : fs::directory_iterator(sd.path, ec))
      if (e.is_directory() && fs::exists(e.path() / kManifest)) dirs.push_back(e.path());
    std::sort(dirs.begin(), dirs.end());
    for (const auto& d : dirs) {
      std::string err;
      auto p = load_package(d.string(), err);
      if (!p) {
        if (problems) problems->push_back(err);
        continue;
      }
      if (!seen.insert(p->name).second) continue;  // shadowed by an earlier dir
      p->source = sd.source;
      out.push_back(*p);
    }
  }
  return out;
}

std::optional<Package> find_package(const std::string& name) {
  for (auto& p : list_packages())
    if (p.name == name) return p;
  return std::nullopt;
}

std::optional<std::string> resolve_mapping(const std::string& spec, std::string& err) {
  const size_t colon = spec.find(':');
  const std::string name = spec.substr(0, colon);
  const std::string mapping = colon == std::string::npos ? "" : spec.substr(colon + 1);
  auto p = find_package(name);
  if (!p) {
    err = "no installed package named '" + name + "' (see `glance pkg list`)";
    return std::nullopt;
  }
  auto path = p->mapping_path(mapping);
  if (!path) {
    err = "package '" + name + "' has no mapping '" + mapping + "'";
    return std::nullopt;
  }
  return path;
}

std::optional<Package> install_package(const std::string& source, bool force, std::string& err) {
  std::error_code ec;
  fs::path staging;
  bool cloned = false;
  if (fs::is_directory(source, ec)) {
    staging = source;
  } else if (looks_like_git_url(source)) {
    std::mt19937_64 rng{std::random_device{}()};
    staging = fs::temp_directory_path() / ("glance_pkg_" + std::to_string(rng()));
    const std::string cmd = "git clone --depth 1 --quiet " + shell_quote(source) + " " +
                            shell_quote(staging.string());
    if (std::system(cmd.c_str()) != 0) {
      err = "git clone failed for " + source;
      fs::remove_all(staging, ec);
      return std::nullopt;
    }
    cloned = true;
  } else {
    err = "not a directory or git URL: " + source;
    return std::nullopt;
  }
  auto cleanup = [&] {
    if (cloned) fs::remove_all(staging, ec);
  };
  auto pkg = load_package(staging.string(), err);
  if (!pkg) {
    cleanup();
    return std::nullopt;
  }
  const fs::path dest = fs::path(user_package_dir()) / pkg->name;
  if (fs::exists(dest, ec)) {
    if (!force) {
      err = "package '" + pkg->name + "' is already installed at " + dest.string() + " (use --force)";
      cleanup();
      return std::nullopt;
    }
    fs::remove_all(dest, ec);
  }
  fs::create_directories(dest.parent_path(), ec);
  fs::copy(staging, dest, fs::copy_options::recursive, ec);
  cleanup();
  if (ec) {
    err = "copy into " + dest.string() + " failed: " + ec.message();
    return std::nullopt;
  }
  fs::remove_all(dest / ".git", ec);
  auto installed = load_package(dest.string(), err);
  if (installed) installed->source = "user";
  return installed;
}

bool remove_package(const std::string& name, std::string& err) {
  if (!valid_package_name(name)) {
    err = "invalid package name: " + name;
    return false;
  }
  const fs::path dest = fs::path(user_package_dir()) / name;
  std::error_code ec;
  if (!fs::exists(dest / kManifest, ec)) {
    auto p = find_package(name);
    err = p && p->source == "builtin" ? "'" + name + "' is a built-in package and cannot be removed"
                                      : "'" + name + "' is not installed in " + user_package_dir();
    return false;
  }
  fs::remove_all(dest, ec);
  if (ec) {
    err = ec.message();
    return false;
  }
  return true;
}

}  // namespace glance::packages
