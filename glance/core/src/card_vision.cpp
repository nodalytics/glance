#include "card_vision.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <filesystem>
#include <regex>

#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>
// OpenCV 5 moved contour geometry (contourArea, boundingRect, matchShapes)
// out of imgproc into the new `geometry` module; 4.x has no such header.
#if __has_include(<opencv2/geometry.hpp>)
#include <opencv2/geometry.hpp>
#endif

#include "ocr.h"

namespace fs = std::filesystem;

namespace glance::vision {

// ------------------------------------------------------------------ basics

const std::vector<std::string>& rank_names() {
  static const std::vector<std::string> r = {"A", "K", "Q", "J", "10", "9", "8",
                                             "7", "6", "5", "4", "3", "2"};
  return r;
}

const std::vector<std::string>& suit_names() {
  static const std::vector<std::string> s = {"clubs", "diamonds", "hearts", "spades"};
  return s;
}

std::string suit_color(const std::string& suit) {
  if (suit == "hearts" || suit == "diamonds") return "red";
  if (suit == "clubs" || suit == "spades") return "black";
  return "";
}

std::string card_id(const std::string& rank, const std::string& suit) {
  if (rank.empty() || suit_color(suit).empty()) return "";
  return (rank == "10" ? std::string("T") : rank) + suit.substr(0, 1);
}

std::optional<std::string> normalize_rank_text(const std::string& raw) {
  std::string text;
  for (unsigned char c : raw)
    if (!std::isspace(c)) text.push_back(static_cast<char>(std::toupper(c)));
  if (text == "T" || text == "1O" || text == "IO") text = "10";
  for (const auto& r : rank_names())
    if (text == r) return text;
  static const std::regex token(R"(10|[AKQJ2-9])");
  std::optional<std::string> found;
  int n = 0;
  for (auto it = std::sregex_iterator(text.begin(), text.end(), token); it != std::sregex_iterator();
       ++it) {
    found = it->str();
    ++n;
  }
  if (n == 1) return found;
  return std::nullopt;
}

cv::Mat crop_relative(const cv::Mat& image, const RelRect& r) {
  if (image.empty()) return {};
  const int h = image.rows, w = image.cols;
  // int() truncation, exactly like the research `crop_region`.
  int x1 = std::clamp(static_cast<int>(w * r.x1), 0, w);
  int x2 = std::clamp(static_cast<int>(w * r.x2), 0, w);
  int y1 = std::clamp(static_cast<int>(h * r.y1), 0, h);
  int y2 = std::clamp(static_cast<int>(h * r.y2), 0, h);
  if (x2 <= x1 || y2 <= y1) return {};
  return image(cv::Rect(x1, y1, x2 - x1, y2 - y1));
}

cv::Mat extract_corner(const cv::Mat& card) {
  cv::Mat corner = crop_relative(card, {0.02, 0.02, 0.65, 0.65});
  if (corner.empty()) return {};
  cv::Mat out;
  cv::resize(corner, out, cv::Size(), 3.0, 3.0, cv::INTER_CUBIC);
  return out;
}

namespace {

cv::Mat to_gray(const cv::Mat& image) {
  if (image.channels() == 1) return image.clone();
  cv::Mat g;
  cv::cvtColor(image, g, image.channels() == 4 ? cv::COLOR_BGRA2GRAY : cv::COLOR_BGR2GRAY);
  return g;
}

cv::Mat to_bgr(const cv::Mat& image) {
  if (image.channels() == 3) return image;
  cv::Mat c;
  cv::cvtColor(image, c, image.channels() == 4 ? cv::COLOR_BGRA2BGR : cv::COLOR_GRAY2BGR);
  return c;
}

// Python's round(): half to even. Only matters at exact .5 sizes.
int py_round(double v) { return static_cast<int>(std::nearbyint(v)); }

// Fit a 0/255 mask (255 = glyph) into the 64x64 canvas, longest side
// kSymbolSize, centred; return black glyph on white.
cv::Mat fit_to_canvas(const cv::Mat& mask) {
  const int w = mask.cols, h = mask.rows;
  const double scale = static_cast<double>(kSymbolSize) / std::max(w, h);
  const int nw = std::max(1, py_round(w * scale));
  const int nh = std::max(1, py_round(h * scale));
  cv::Mat resized;
  cv::resize(mask, resized, cv::Size(nw, nh), 0, 0, cv::INTER_NEAREST);
  cv::Mat canvas = cv::Mat::zeros(kTemplateSize, kTemplateSize, CV_8UC1);
  resized.copyTo(canvas(cv::Rect((kTemplateSize - nw) / 2, (kTemplateSize - nh) / 2, nw, nh)));
  return 255 - canvas;
}

// Largest external contour of a black-on-white normalized symbol.
std::optional<std::vector<cv::Point>> symbol_contour(const cv::Mat& image) {
  if (image.empty()) return std::nullopt;
  cv::Mat binary;
  cv::threshold(to_gray(image), binary, 127, 255, cv::THRESH_BINARY_INV);
  std::vector<std::vector<cv::Point>> contours;
  cv::findContours(binary, contours, cv::RETR_EXTERNAL, cv::CHAIN_APPROX_SIMPLE);
  if (contours.empty()) return std::nullopt;
  auto best = std::max_element(contours.begin(), contours.end(), [](const auto& a, const auto& b) {
    return cv::contourArea(a) < cv::contourArea(b);
  });
  if (cv::contourArea(*best) < 20) return std::nullopt;
  return *best;
}

double dice(const cv::Mat& a, const cv::Mat& b) {
  cv::Mat ma = a < 128, mb = b < 128;
  const int total = cv::countNonZero(ma) + cv::countNonZero(mb);
  if (total == 0) return 0.0;
  return 2.0 * cv::countNonZero(ma & mb) / total;
}

std::vector<GlyphTemplate> load_glyph_dir(const std::string& dir,
                                          const std::vector<std::string>& labels,
                                          const std::map<std::string, std::string>& aliases) {
  std::vector<GlyphTemplate> out;
  std::error_code ec;
  if (dir.empty() || !fs::is_directory(dir, ec)) return out;
  std::vector<fs::path> files;
  for (const auto& e : fs::directory_iterator(dir, ec))
    if (e.is_regular_file() && e.path().extension() == ".png") files.push_back(e.path());
  std::sort(files.begin(), files.end());
  for (const auto& p : files) {
    const std::string stem = p.stem().string();
    const std::string head = stem.substr(0, stem.find('_'));
    std::string label;
    auto alias = aliases.find(head);
    if (alias != aliases.end()) {
      label = alias->second;
    } else if (std::find(labels.begin(), labels.end(), head) != labels.end()) {
      label = head;
    }
    if (label.empty()) continue;
    cv::Mat img = cv::imread(p.string(), cv::IMREAD_GRAYSCALE);
    if (img.empty()) continue;
    cv::resize(img, img, cv::Size(kTemplateSize, kTemplateSize), 0, 0, cv::INTER_NEAREST);
    cv::threshold(img, img, 127, 255, cv::THRESH_BINARY);
    const int fg = cv::countNonZero(255 - img);
    if (fg == 0 || fg == static_cast<int>(img.total())) continue;
    out.push_back({label, stem, img});
  }
  return out;
}

}  // namespace

// ------------------------------------------------------------ normalizing

cv::Mat normalize_suit_symbol(const cv::Mat& image) {
  if (image.empty()) return {};
  cv::Mat gray = to_gray(image);
  cv::resize(gray, gray, cv::Size(), 4.0, 4.0, cv::INTER_CUBIC);
  cv::GaussianBlur(gray, gray, cv::Size(3, 3), 0);
  cv::Mat binary;
  cv::threshold(gray, binary, 0, 255, cv::THRESH_BINARY_INV | cv::THRESH_OTSU);
  std::vector<std::vector<cv::Point>> contours;
  cv::findContours(binary, contours, cv::RETR_EXTERNAL, cv::CHAIN_APPROX_SIMPLE);
  if (contours.empty()) return {};
  auto largest = std::max_element(contours.begin(), contours.end(), [](const auto& a, const auto& b) {
    return cv::contourArea(a) < cv::contourArea(b);
  });
  if (cv::contourArea(*largest) < 20) return {};
  const cv::Rect box = cv::boundingRect(*largest);
  if (box.width == 0 || box.height == 0) return {};
  const double aspect = static_cast<double>(box.width) / box.height;
  if (aspect < 0.45 || aspect > 1.8) return {};
  cv::Mat mask = cv::Mat::zeros(binary.size(), CV_8UC1);
  cv::drawContours(mask, std::vector<std::vector<cv::Point>>{*largest}, -1, 255, cv::FILLED);
  return fit_to_canvas(mask(box));
}

cv::Mat normalize_rank_glyph(const cv::Mat& image) {
  if (image.empty() || image.rows < 4 || image.cols < 4) return {};
  cv::Mat gray = to_gray(image);
  cv::resize(gray, gray, cv::Size(), 4.0, 4.0, cv::INTER_CUBIC);
  cv::GaussianBlur(gray, gray, cv::Size(3, 3), 0);
  cv::Mat binary;
  cv::threshold(gray, binary, 0, 255, cv::THRESH_BINARY_INV | cv::THRESH_OTSU);

  cv::Mat labels, stats, centroids;
  const int n = cv::connectedComponentsWithStats(binary, labels, stats, centroids, 8, CV_32S);
  const int W = binary.cols, H = binary.rows;
  struct Comp {
    int label;
    cv::Rect box;
  };
  std::vector<Comp> comps;
  for (int i = 1; i < n; ++i) {
    cv::Rect b(stats.at<int>(i, cv::CC_STAT_LEFT), stats.at<int>(i, cv::CC_STAT_TOP),
               stats.at<int>(i, cv::CC_STAT_WIDTH), stats.at<int>(i, cv::CC_STAT_HEIGHT));
    const int area = stats.at<int>(i, cv::CC_STAT_AREA);
    // Glyph-sized, not background. The table felt, the card edge and a
    // neighbouring card are what reach the crop border — but they hug two or
    // more sides or span the crop, whereas a rank glyph that ACR draws flush in
    // the very corner touches at most ONE side (a "2" pressed against the left
    // card edge). So reject a component that touches two+ borders, and keep a
    // single-border touch as long as the size filters below still hold.
    const int touches = (b.x <= 0) + (b.y <= 0) + (b.x + b.width >= W) + (b.y + b.height >= H);
    if (touches >= 2) continue;
    if (area < 0.003 * W * H) continue;
    // Height ceiling: a rank glyph can be large (ACR's corner glyph nearly
    // fills a tight rank box), so accept up to 0.92*H; only a region-spanning
    // blob is rejected. The ceiling, with the width cap, still keeps out the
    // card body / a felt strip / a filled suit that would span the crop.
    if (b.height < 0.12 * H || b.height > 0.92 * H || b.width > 0.7 * W) continue;
    comps.push_back({i, b});
  }
  if (comps.empty()) return {};

  // Seed: the top-most component (the rank sits above the corner suit).
  const auto seed = *std::min_element(comps.begin(), comps.end(),
                                      [](const Comp& a, const Comp& b) { return a.box.y < b.box.y; });
  // Same text row: vertically overlapping the seed by half the smaller
  // height, and horizontally within one glyph height of the growing union
  // (so "10" merges, a far-away mark does not).
  cv::Rect uni = seed.box;
  std::vector<int> chosen = {seed.label};
  bool grew = true;
  while (grew) {
    grew = false;
    for (const auto& c : comps) {
      if (std::find(chosen.begin(), chosen.end(), c.label) != chosen.end()) continue;
      const int ov = std::min(uni.y + uni.height, c.box.y + c.box.height) - std::max(uni.y, c.box.y);
      if (ov < 0.5 * std::min(uni.height, c.box.height)) continue;
      const int gap = std::max(c.box.x - (uni.x + uni.width), uni.x - (c.box.x + c.box.width));
      if (gap > seed.box.height) continue;
      chosen.push_back(c.label);
      uni |= c.box;
      grew = true;
    }
  }
  cv::Mat mask = cv::Mat::zeros(binary.size(), CV_8UC1);
  for (int l : chosen) mask.setTo(255, labels == l);
  return fit_to_canvas(mask(uni));
}

double symbol_similarity(const cv::Mat& symbol, const cv::Mat& templ) {
  if (symbol.empty() || templ.empty() || symbol.size() != templ.size()) return 0.0;
  const double dice_score = dice(symbol, templ);
  if (dice_score == 0.0 && cv::countNonZero(symbol < 128) + cv::countNonZero(templ < 128) == 0)
    return 0.0;
  auto a = symbol_contour(symbol);
  auto b = symbol_contour(templ);
  if (!a || !b) return 0.0;
  const double dist = cv::matchShapes(*a, *b, cv::CONTOURS_MATCH_I1, 0.0);
  if (!std::isfinite(dist)) return 0.0;
  const double shape = 1.0 / (1.0 + 5.0 * dist);
  return std::clamp(0.40 * dice_score + 0.60 * shape, 0.0, 1.0);
}

double glyph_similarity(const cv::Mat& glyph, const cv::Mat& templ) {
  if (glyph.empty() || templ.empty() || glyph.size() != templ.size()) return 0.0;
  // Plain Dice. A blurred normalized-correlation variant was measured on the
  // research datasets and accepted wrong ranks (J->3 in other fonts) at every
  // gate that kept recall; Dice separates right from wrong reads cleanly.
  return dice(glyph, templ);
}

std::string detect_suit_color(const cv::Mat& bgr, bool strict) {
  if (bgr.empty() || bgr.channels() != 3) return "unknown";
  cv::Mat hsv;
  cv::cvtColor(bgr, hsv, cv::COLOR_BGR2HSV);
  const int s_min = strict ? 80 : 60;
  const int v_min = strict ? 60 : 50;
  cv::Mat r1, r2, dark;
  cv::inRange(hsv, cv::Scalar(0, s_min, v_min), cv::Scalar(12, 255, 255), r1);
  cv::inRange(hsv, cv::Scalar(165, s_min, v_min), cv::Scalar(180, 255, 255), r2);
  if (strict)
    cv::inRange(hsv, cv::Scalar(0, 0, 0), cv::Scalar(180, 70, 120), dark);
  else
    cv::inRange(hsv, cv::Scalar(0, 0, 0), cv::Scalar(180, 255, 125), dark);
  const int red = cv::countNonZero(r1 | r2);
  const int black = cv::countNonZero(dark);
  const int total = red + black;
  if (total < 10) return "unknown";
  const double ratio = static_cast<double>(red) / total;
  if (strict) {
    if (ratio >= 0.80) return "red";
    if (ratio <= 0.20) return "black";
    return "unknown";
  }
  if (ratio > 0.20) return "red";
  if (black > 0) return "black";
  return "unknown";
}

// --------------------------------------------------------------- occupancy

nlohmann::json Occupancy::to_json() const {
  return {{"state", state},
          {"reason", reason},
          {"white_ratio", white_ratio},
          {"green_ratio", green_ratio},
          {"edge_ratio", edge_ratio},
          {"mean_brightness", mean_brightness},
          {"brightness_std", brightness_std}};
}

Occupancy detect_occupancy(const cv::Mat& bgr, const OccupancyThresholds& t) {
  Occupancy o;
  if (bgr.empty() || bgr.channels() != 3 || bgr.rows < 10 || bgr.cols < 10) {
    o.reason = "Unusable card slot image";
    return o;
  }
  o.valid = true;
  const int mx = static_cast<int>(bgr.cols * 0.05), my = static_cast<int>(bgr.rows * 0.05);
  cv::Mat region = bgr(cv::Rect(mx, my, bgr.cols - 2 * mx, bgr.rows - 2 * my));
  cv::Mat hsv, gray, white, green, edges;
  cv::cvtColor(region, hsv, cv::COLOR_BGR2HSV);
  cv::cvtColor(region, gray, cv::COLOR_BGR2GRAY);
  cv::inRange(hsv, cv::Scalar(0, 0, 180), cv::Scalar(180, 65, 255), white);
  cv::inRange(hsv, cv::Scalar(35, 40, 20), cv::Scalar(100, 255, 200), green);
  cv::Canny(gray, edges, 50, 150);
  const double total = static_cast<double>(gray.total());
  o.white_ratio = cv::countNonZero(white) / total;
  o.green_ratio = cv::countNonZero(green) / total;
  o.edge_ratio = cv::countNonZero(edges) / total;
  cv::Scalar mean, sd;
  cv::meanStdDev(gray, mean, sd);
  o.mean_brightness = mean[0];
  o.brightness_std = sd[0];
  if (o.white_ratio >= t.occupied_white) {
    o.state = "occupied";
    o.reason = "Bright card background detected";
  } else if (o.green_ratio >= t.empty_green && o.white_ratio <= t.empty_white &&
             o.edge_ratio <= t.empty_edge) {
    o.state = "empty";
    o.reason = "Uniform green table background";
  } else {
    o.state = "unknown";
    o.reason = "Insufficient occupancy evidence";
  }
  return o;
}

// --------------------------------------------------------------- templates

std::vector<GlyphTemplate> load_suit_templates(const std::string& dir) {
  return load_glyph_dir(dir, suit_names(), {});
}

std::vector<GlyphTemplate> load_rank_templates(const std::string& dir) {
  return load_glyph_dir(dir, rank_names(), {{"T", "10"}});
}

std::vector<GlyphTemplate> synthesize_rank_templates() {
  std::vector<GlyphTemplate> out;
  const std::pair<int, const char*> fonts[] = {{cv::FONT_HERSHEY_SIMPLEX, "simplex"},
                                               {cv::FONT_HERSHEY_DUPLEX, "duplex"}};
  for (const auto& rank : rank_names()) {
    for (const auto& [font, fname] : fonts) {
      for (int thick : {2, 3}) {
        cv::Mat canvas(80, 120, CV_8UC3, cv::Scalar(255, 255, 255));
        cv::putText(canvas, rank, {12, 60}, font, 1.6, cv::Scalar(0, 0, 0), thick, cv::LINE_AA);
        cv::Mat g = normalize_rank_glyph(canvas);
        if (g.empty()) continue;
        out.push_back({rank, std::string("hershey_") + fname + std::to_string(thick), g});
      }
    }
  }
  return out;
}

// -------------------------------------------------------------- recognizer

std::vector<cv::Mat> rank_glyph_regions(const cv::Mat& card) {
  std::vector<cv::Mat> out;
  // 1. the tight rank box of the research RankFallback (simulator cards);
  // 2. a generously padded corner box. Some skins (e.g. ACR) draw a LARGE
  //    corner rank glyph that fills the tight box edge to edge, so it is
  //    clipped there and rejected (too tall / border contact). Anchoring at
  //    the crop's top-left and reaching 52% across / 36% down keeps the whole
  //    glyph with margin on its right and bottom, while the card edge and the
  //    felt around the slot stay out of the way of the glyph's own row;
  // 3. the corner's upper part (research primary rank region);
  // 4. the card's top-left 65% (research fallback; hero cards whose rank
  //    sits lower because the card is partly covered).
  for (const RelRect& r : {RelRect{0.03, 0.01, 0.43, 0.24}, RelRect{0.0, 0.0, 0.52, 0.36},
                           RelRect{0.02, 0.02, 0.65, 0.43}, RelRect{0.0, 0.0, 0.65, 0.65}}) {
    cv::Mat c = crop_relative(card, r);
    if (!c.empty()) out.push_back(c);
  }
  return out;
}

std::string CardReading::id() const {
  if (!recognized()) return "";
  return card_id(*rank.rank, *suit.suit);
}

nlohmann::json CardReading::to_json() const {
  auto opt = [](const std::optional<std::string>& v) -> nlohmann::json {
    return v ? nlohmann::json(*v) : nlohmann::json(nullptr);
  };
  nlohmann::json j;
  j["recognized"] = recognized();
  j["card"] = recognized() ? nlohmann::json(id()) : nlohmann::json(nullptr);
  j["rank"] = opt(rank.rank);
  j["rank_confidence"] = rank.confidence;
  j["rank_margin"] = rank.margin;
  j["rank_source"] = rank.source;
  j["rank_verification"] = rank_verification;
  if (glyph_rank != rank.rank) j["glyph_rank"] = opt(glyph_rank);
  j["suit"] = opt(suit.suit);
  j["suit_confidence"] = suit.confidence;
  j["suit_margin"] = suit.margin;
  j["suit_source"] = suit.source;
  j["suit_scores"] = suit.scores;
  j["suit_color"] = suit.color;
  j["occupancy"] = occupancy.to_json();
  j["skipped"] = skipped;
  return j;
}

bool CardRecognizer::load(const CardVisionConfig& config, const std::string& suit_dir,
                          const std::string& rank_dir) {
  config_ = config;
  error_.clear();
  if (config_.profile != "simulator" && config_.profile != "calibration") {
    error_ = "card_vision: unknown profile '" + config_.profile + "'";
    return false;
  }
  suit_templates_ = load_suit_templates(suit_dir);
  for (const auto& s : suit_names()) {
    bool have = std::any_of(suit_templates_.begin(), suit_templates_.end(),
                            [&](const GlyphTemplate& t) { return t.label == s; });
    if (!have) {
      error_ = "card_vision: no suit template for '" + s + "' in " + suit_dir;
      return false;
    }
  }
  rank_templates_ = rank_dir.empty() ? synthesize_rank_templates() : load_rank_templates(rank_dir);
  if (rank_templates_.empty()) {
    error_ = "card_vision: no rank templates in " + rank_dir;
    return false;
  }
  return true;
}

namespace {

// The suit-candidate crops (name + image) a profile/slot yields, shared by the
// recognizer's read_suit and by suit-template harvesting so the two cut the
// exact same regions.
std::vector<std::pair<std::string, cv::Mat>> suit_candidate_crops(const std::string& profile,
                                                                  const cv::Mat& card,
                                                                  const std::string& slot) {
  std::vector<std::pair<std::string, cv::Mat>> out;
  auto add = [&](const std::string& name, const cv::Mat& img) {
    if (!img.empty()) out.push_back({name, img});
  };
  if (profile == "simulator") {
    add("simulator_small_suit", crop_relative(card, {0.04, 0.24, 0.40, 0.46}));
    add("simulator_small_suit_wide", crop_relative(card, {0.02, 0.23, 0.43, 0.48}));
    add("simulator_center_suit", crop_relative(card, {0.23, 0.43, 0.77, 0.79}));
    return out;
  }
  // calibration profile
  if (slot == "hero_card_1" || slot == "my1") {
    add("hero_1_region_0", crop_relative(card, {0.08, 0.61, 0.35, 0.84}));
    add("hero_1_region_1", crop_relative(card, {0.07, 0.60, 0.37, 0.86}));
  } else if (slot == "hero_card_2" || slot == "my2") {
    add("hero_2_region_0", crop_relative(card, {0.22, 0.57, 0.44, 0.81}));
    add("hero_2_region_1", crop_relative(card, {0.20, 0.56, 0.46, 0.83}));
  } else {
    cv::Mat corner = extract_corner(card);
    cv::Mat suit_region = crop_relative(corner, {0.0, 0.40, 1.0, 1.0});
    const RelRect regions[] = {{0.04, 0.08, 0.50, 0.58}, {0.04, 0.10, 0.49, 0.64}, {0.03, 0.09, 0.45, 0.66}};
    int i = 0;
    for (const auto& r : regions) add("board_region_" + std::to_string(i++), crop_relative(suit_region, r));
  }
  return out;
}

}  // namespace

std::vector<cv::Mat> suit_symbol_regions(const std::string& profile, const cv::Mat& card,
                                         const std::string& slot) {
  std::vector<cv::Mat> out;
  if (card.empty()) return out;
  const cv::Mat bgr = to_bgr(card);
  for (const auto& [name, crop] : suit_candidate_crops(profile, bgr, slot)) {
    (void)name;
    cv::Mat s = normalize_suit_symbol(crop);
    if (!s.empty()) out.push_back(s);
  }
  return out;
}

std::vector<CardRecognizer::NamedCrop> CardRecognizer::suit_candidates(
    const cv::Mat& card, const std::string& slot) const {
  std::vector<NamedCrop> out;
  for (auto& [name, img] : suit_candidate_crops(config_.profile, card, slot))
    out.push_back({name, img});
  return out;
}

SuitRead CardRecognizer::read_suit(const cv::Mat& card, const std::string& slot) const {
  SuitRead res;
  const bool strict = config_.profile == "simulator";
  auto cands = suit_candidates(card, slot);
  struct Best {
    double score = -1;
    std::string source;
  };
  std::map<std::string, Best> best;
  for (const auto& c : cands) {
    cv::Mat normalized = normalize_suit_symbol(c.image);
    if (normalized.empty()) continue;
    // Simulator profile: compare only colour-compatible suits.
    const std::string color = strict ? detect_suit_color(c.image, true) : "unknown";
    for (const auto& t : suit_templates_) {
      if (color != "unknown" && suit_color(t.label) != color) continue;
      const double s = symbol_similarity(normalized, t.image);
      auto& b = best[t.label];
      if (s > b.score) b = {s, strict ? c.name + ":" + t.name : c.name};
    }
  }
  if (!best.empty()) {
    std::vector<std::pair<std::string, Best>> ranked(best.begin(), best.end());
    std::sort(ranked.begin(), ranked.end(),
              [](const auto& a, const auto& b) { return a.second.score > b.second.score; });
    res.confidence = ranked[0].second.score;
    res.source = ranked[0].second.source;
    res.margin = res.confidence - (ranked.size() > 1 ? ranked[1].second.score : 0.0);
    for (const auto& [s, b] : ranked) res.scores[s] = b.score;
    if (res.confidence >= config_.suit_threshold && res.margin >= config_.suit_margin)
      res.suit = ranked[0].first;
  }
  if (res.suit)
    res.color = suit_color(*res.suit);
  else if (!cands.empty())
    res.color = detect_suit_color(cands[0].image, strict);
  return res;
}

RankRead CardRecognizer::read_rank_glyph(const cv::Mat& card) const {
  RankRead res;
  static const char* names[] = {"rank_box", "rank_pad", "corner", "top_left"};
  std::map<std::string, std::pair<double, std::string>> best;  // rank -> (score, region)
  auto regions = rank_glyph_regions(card);
  for (std::size_t i = 0; i < regions.size(); ++i) {
    cv::Mat glyph = normalize_rank_glyph(regions[i]);
    if (glyph.empty()) continue;
    for (const auto& t : rank_templates_) {
      const double s = glyph_similarity(glyph, t.image);
      auto it = best.find(t.label);
      if (it == best.end() || s > it->second.first) best[t.label] = {s, names[i]};
    }
  }
  if (best.empty()) return res;
  std::vector<std::pair<std::string, std::pair<double, std::string>>> ranked(best.begin(), best.end());
  std::sort(ranked.begin(), ranked.end(),
            [](const auto& a, const auto& b) { return a.second.first > b.second.first; });
  res.confidence = ranked[0].second.first;
  res.source = ranked[0].second.second;
  res.margin = res.confidence - (ranked.size() > 1 ? ranked[1].second.first : 0.0);
  for (const auto& [r, v] : ranked) res.scores[r] = v.first;
  // Two ways to accept: a strong match with a small lead, or a clear lead
  // over the runner-up with a reasonable match (font variations score lower
  // overall but still separate).
  const bool strong = res.confidence >= config_.rank_threshold && res.margin >= config_.rank_margin;
  const bool clear = res.confidence >= config_.rank_floor && res.margin >= config_.rank_clear_margin;
  if (strong || clear) res.rank = ranked[0].first;
  return res;
}

namespace {

// Tesseract read of the rank: research RankFallback preparation (x4 cubic,
// 20px white border) on each rank region; best-confidence valid rank.
RankRead read_rank_ocr(const cv::Mat& card) {
  RankRead best;
  static const char* names[] = {"ocr:rank_box", "ocr:rank_pad", "ocr:corner", "ocr:top_left"};
  auto regions = rank_glyph_regions(card);
  for (std::size_t i = 0; i < regions.size(); ++i) {
    cv::Mat big;
    cv::resize(regions[i], big, cv::Size(), 4.0, 4.0, cv::INTER_CUBIC);
    cv::copyMakeBorder(big, big, 20, 20, 20, 20, cv::BORDER_CONSTANT, cv::Scalar(255, 255, 255));
    for (const auto& w : ocr_words(big, 8, "AKQJT0123456789")) {
      auto r = normalize_rank_text(w.text);
      if (!r || w.confidence <= best.confidence) continue;
      best.rank = r;
      best.confidence = w.confidence;
      best.source = names[i];
    }
  }
  return best;
}

}  // namespace

CardReading CardRecognizer::recognize(const cv::Mat& input, const std::string& slot) const {
  CardReading out;
  if (input.empty() || input.rows < 10 || input.cols < 10) {
    out.rank_verification = "unrecognized";
    return out;
  }
  cv::Mat card = to_bgr(input);

  if (config_.occupancy) {
    out.occupancy = detect_occupancy(card, config_.occupancy_thresholds);
    if (out.occupancy.state == "empty") {
      out.skipped = true;
      out.rank_verification = "empty";
      return out;
    }
  }

  out.suit = read_suit(card, slot);
  out.rank = read_rank_glyph(card);
  out.glyph_rank = out.rank.rank;

  const bool ocr = config_.ocr_verify && ocr_available();
  if (out.rank.rank && out.rank.confidence >= config_.verify_trigger) {
    out.rank_verification = "not_required";
  } else if (!ocr) {
    out.rank_verification = out.rank.rank ? "unverified" : "unrecognized";
  } else if (out.rank.rank) {
    RankRead o = read_rank_ocr(card);
    if (!o.rank) {
      out.rank_verification = "unverified";  // OCR saw nothing: keep the glyph read
    } else if (*o.rank == *out.rank.rank) {
      out.rank_verification = "confirmed";
      out.rank.confidence = std::max(out.rank.confidence, o.confidence);
      out.rank.source += "+" + o.source;
    } else if (o.confidence >= config_.verify_threshold) {
      out.rank_verification = "changed";
      out.rank = o;
    } else {
      out.rank_verification = "rejected";
      out.rank.rank.reset();
      out.rank.source = "verification_rejected";
    }
  } else if (out.suit.suit) {
    // Research rule: only try the rank fallback when the suit was read.
    RankRead o = read_rank_ocr(card);
    if (o.rank && o.confidence >= config_.ocr_threshold) {
      out.rank_verification = "ocr_recovered";
      out.rank = o;
    } else {
      out.rank_verification = "unrecognized";
    }
  } else {
    out.rank_verification = "unrecognized";
  }
  return out;
}

}  // namespace glance::vision
