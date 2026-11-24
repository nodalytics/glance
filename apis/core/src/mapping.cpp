#include "mapping.h"

#include <filesystem>
#include <fstream>
#include <sstream>

namespace fs = std::filesystem;

namespace poker {

namespace {

bool read_rect_array(const nlohmann::json& j, Rect& out) {
  if (!j.is_array() || j.size() != 4) return false;
  for (size_t i = 0; i < 4; ++i) {
    if (!j[i].is_number()) return false;
  }
  out.x1 = j[0].get<int>();
  out.y1 = j[1].get<int>();
  out.x2 = j[2].get<int>();
  out.y2 = j[3].get<int>();
  return true;
}

std::string file_stem(const std::string& path) {
  fs::path p(path);
  return p.stem().string();
}

}  // namespace

bool TableMapping::load(const std::string& path) {
  loaded_ = false;
  error_.clear();

  base_dir_ = fs::path(path).parent_path().string();
  if (base_dir_.empty()) base_dir_ = ".";

  std::ifstream in(path);
  if (!in) {
    error_ = "cannot open mapping file: " + path;
    return false;
  }
  std::ostringstream ss;
  ss << in.rdbuf();

  nlohmann::json j;
  try {
    j = nlohmann::json::parse(ss.str());
  } catch (const std::exception& e) {
    error_ = std::string("invalid JSON in ") + path + ": " + e.what();
    return false;
  }
  if (!j.is_object()) {
    error_ = "mapping file must be a JSON object";
    return false;
  }

  auto need_str = [&](const char* key, std::string& out) -> bool {
    if (!j.contains(key) || !j[key].is_string()) {
      error_ = std::string("missing string field: ") + key;
      return false;
    }
    out = j[key].get<std::string>();
    return true;
  };

  if (!need_str("name", name_)) return false;

  if (!j.contains("crop")) {
    error_ = "missing field: crop (expected {\"x\":W,\"y\":H} or [W,H])";
    return false;
  }
  const auto& cropj = j["crop"];
  if (cropj.is_object() && cropj.contains("x") && cropj.contains("y")) {
    if (!cropj["x"].is_number() || !cropj["y"].is_number()) {
      error_ = "crop.x and crop.y must be numbers";
      return false;
    }
    crop_.x1 = 0;
    crop_.y1 = 0;
    crop_.x2 = cropj["x"].get<int>();
    crop_.y2 = cropj["y"].get<int>();
  } else if (cropj.is_array() && cropj.size() == 2) {
    if (!cropj[0].is_number() || !cropj[1].is_number()) {
      error_ = "crop [w,h] values must be numbers";
      return false;
    }
    crop_.x1 = 0;
    crop_.y1 = 0;
    crop_.x2 = cropj[0].get<int>();
    crop_.y2 = cropj[1].get<int>();
  } else {
    error_ = "crop must be {\"x\":W,\"y\":H} or [W,H]";
    return false;
  }
  if (crop_.x2 <= 0 || crop_.y2 <= 0) {
    error_ = "crop size must be positive";
    return false;
  }

  if (!need_str("topleft", topleft_template_path_)) return false;

  if (j.contains("anchor_threshold") && !j["anchor_threshold"].is_number()) {
    error_ = "anchor_threshold must be a number";
    return false;
  }
  if (j.contains("template_threshold") && !j["template_threshold"].is_number()) {
    error_ = "template_threshold must be a number";
    return false;
  }
  anchor_threshold_ = j.value("anchor_threshold", anchor_threshold_);
  template_threshold_ = j.value("template_threshold", template_threshold_);

  if (j.contains("max_players")) {
    if (!j["max_players"].is_number()) {
      error_ = "max_players must be a number";
      return false;
    }
    max_players_ = j["max_players"].get<int>();
    if (max_players_ < 2) {
      error_ = "max_players must be >= 2";
      return false;
    }
  }

  if (j.contains("dealer")) {
    if (!j["dealer"].is_object()) {
      error_ = "dealer must be an object {\"template\":...,\"areas\":{...}}";
      return false;
    }
    const auto& dj = j["dealer"];
    if (!dj.contains("template") || !dj["template"].is_string()) {
      error_ = "dealer.template must be a string";
      return false;
    }
    Dealer d;
    d.template_path = dj["template"].get<std::string>();
    if (dj.contains("areas") && dj["areas"].is_object()) {
      for (auto it = dj["areas"].begin(); it != dj["areas"].end(); ++it) {
        Rect r;
        if (!read_rect_array(it.value(), r)) {
          error_ = "dealer.areas." + it.key() + " must be an area [x1,y1,x2,y2]";
          return false;
        }
        d.areas.emplace_back(it.key(), r);
      }
    }
    dealer_ = std::move(d);
  }

  if (j.contains("buttons") && j["buttons"].is_object()) {
    for (auto it = j["buttons"].begin(); it != j["buttons"].end(); ++it) {
      if (!it.value().is_object()) {
        error_ = "buttons." + it.key() + " must be an object";
        return false;
      }
      Button b;
      b.name = it.key();
      if (!it.value().contains("template") || !it.value()["template"].is_string()) {
        error_ = "buttons." + b.name + " missing template string";
        return false;
      }
      b.template_path = it.value()["template"].get<std::string>();
      if (!it.value().contains("area") || !read_rect_array(it.value()["area"], b.area)) {
        error_ = "buttons." + b.name + " missing/invalid area [x1,y1,x2,y2]";
        return false;
      }
      buttons_.push_back(std::move(b));
    }
  }

  if (j.contains("card_templates")) {
    if (!j["card_templates"].is_array()) {
      error_ = "card_templates must be an array of template paths";
      return false;
    }
    for (const auto& t : j["card_templates"]) {
      if (!t.is_string()) {
        error_ = "card_templates entries must be strings";
        return false;
      }
      CardTemplate ct;
      ct.path = t.get<std::string>();
      ct.id = file_stem(ct.path);
      card_templates_.push_back(std::move(ct));
    }
  }

  if (j.contains("cards") && j["cards"].is_object()) {
    for (auto it = j["cards"].begin(); it != j["cards"].end(); ++it) {
      CardSlot c;
      c.slot = it.key();
      if (!read_rect_array(it.value(), c.area)) {
        error_ = "cards." + c.slot + " must be an area [x1,y1,x2,y2]";
        return false;
      }
      card_slots_.push_back(std::move(c));
    }
  }

  if (j.contains("stacks") && j["stacks"].is_object()) {
    for (auto it = j["stacks"].begin(); it != j["stacks"].end(); ++it) {
      StackArea s;
      s.key = it.key();
      if (!read_rect_array(it.value(), s.area)) {
        error_ = "stacks." + s.key + " must be an area [x1,y1,x2,y2]";
        return false;
      }
      stacks_.push_back(std::move(s));
    }
  }

  loaded_ = true;
  return true;
}

bool TableMapping::has_button(const std::string& name) const {
  for (const auto& b : buttons_) {
    if (b.name == name) return true;
  }
  return false;
}

}  // namespace poker
