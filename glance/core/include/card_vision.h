#pragma once

// Card vision: read one playing card from a crop of its slot, with no
// per-card template library. Port of the research prototype's recognizers
// (research/poker_apis/vision/card_recognition.py, simulator_card_
// recognition.py, card_occupancy.py, rank_fallback.py and the enhanced /
// optimized / verified variants), with one deliberate change:
//
//   * Ranks are read by GLYPH TEMPLATES, not OCR. The prototype used
//     PaddleOCR; glance's only OCR is the optional tesseract binary, so an
//     OCR-only rank would never work on hosts without it. The rank glyph is
//     normalized exactly like the suit symbol and compared against one or
//     more templates per rank. Tesseract, when present, is an optional
//     cross-check (the prototype's "verified" recognizer): it confirms or
//     rejects low-confidence glyph reads and recovers ranks the glyph
//     matcher rejected.
//
// Pipeline per card crop:
//   1. occupancy (white / green / edge ratios) — an empty slot stops here;
//   2. suit: candidate regions -> normalized symbol -> best of
//      0.4*Dice + 0.6*Hu-shape against the suit templates (colour-gated in
//      the simulator profile) -> accept on confidence AND margin;
//   3. rank: glyph region -> normalized glyph -> best Dice against the rank
//      templates -> accept on confidence AND margin; then the optional
//      tesseract verification.
//
// Pure OpenCV; no tesseract needed except for step 3's verification.

#include <map>
#include <optional>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>
#include <opencv2/core.hpp>

namespace glance::vision {

inline constexpr int kTemplateSize = 64;  // normalized symbol canvas
inline constexpr int kSymbolSize = 52;    // longest symbol side on the canvas

// "A","K","Q","J","10","9",...,"2" and "clubs","diamonds","hearts","spades".
const std::vector<std::string>& rank_names();
const std::vector<std::string>& suit_names();
// "red" for hearts/diamonds, "black" for clubs/spades, "" otherwise.
std::string suit_color(const std::string& suit);
// glance's two-character card id: rank ("10" -> "T") + suit initial, e.g.
// ("10","hearts") -> "Th". Empty when either part is unknown.
std::string card_id(const std::string& rank, const std::string& suit);

// OCR text -> rank. "T"/"1O"/"IO" mean "10"; otherwise the text must hold
// exactly one rank token. nullopt when it does not.
std::optional<std::string> normalize_rank_text(const std::string& text);

// A rectangle in fractions of an image's width/height.
struct RelRect {
  double x1 = 0, y1 = 0, x2 = 1, y2 = 1;
};
// Crop by fractional rectangle (a view, not a copy). Empty when degenerate.
cv::Mat crop_relative(const cv::Mat& image, const RelRect& r);

// The card's top-left corner (2%..65% both ways), enlarged x3 (cubic).
cv::Mat extract_corner(const cv::Mat& card);

// Suit symbol -> 64x64 black-on-white canvas (largest external contour,
// filled, fitted to 52px). Empty Mat when no plausible symbol is found.
cv::Mat normalize_suit_symbol(const cv::Mat& image);

// Rank glyph -> 64x64 black-on-white canvas. Takes the top-most row of
// glyph components ("10" is two components on one row), keeps holes, and
// fits the union to 52px preserving aspect. Empty Mat when nothing found.
cv::Mat normalize_rank_glyph(const cv::Mat& image);

// Suit similarity in [0,1]: 0.4 * Dice(pixels) + 0.6 * 1/(1+5*Hu-I1).
double symbol_similarity(const cv::Mat& symbol, const cv::Mat& templ);
// Rank similarity in [0,1]: Dice of the glyph pixels.
double glyph_similarity(const cv::Mat& glyph, const cv::Mat& templ);

// "red" / "black" / "unknown" from the HSV pixels of a BGR suit crop.
// strict=false is the calibration rule (red share > 0.20 -> red, any dark
// -> black); strict=true the simulator rule (>=0.80 red, <=0.20 black).
std::string detect_suit_color(const cv::Mat& bgr, bool strict);

// ---------------------------------------------------------------- occupancy

struct OccupancyThresholds {
  double occupied_white = 0.55;
  double empty_green = 0.85;
  double empty_white = 0.05;
  double empty_edge = 0.03;
};

struct Occupancy {
  std::string state = "unknown";  // "occupied" | "empty" | "unknown"
  std::string reason;
  double white_ratio = 0, green_ratio = 0, edge_ratio = 0;
  double mean_brightness = 0, brightness_std = 0;
  bool valid = false;  // false: image unusable (empty / not BGR / < 10px)
  nlohmann::json to_json() const;
};

Occupancy detect_occupancy(const cv::Mat& bgr, const OccupancyThresholds& t = {});

// ---------------------------------------------------------------- templates

struct GlyphTemplate {
  std::string label;  // suit name or rank
  std::string name;   // file stem, e.g. "hearts_arial"
  cv::Mat image;      // 64x64 binary, black glyph on white
};

// Suits: "<suit>.png" and "<suit>_*.png" in dir. Each is resized to 64x64
// (nearest), thresholded at 127; blank/full images are skipped.
std::vector<GlyphTemplate> load_suit_templates(const std::string& dir);
// Ranks: "<rank>.png" and "<rank>_*.png" ("10", "T" both mean ten), loaded
// the same way. Files should already be normalized glyphs (see
// normalize_rank_glyph / `glance-cardvision harvest`).
std::vector<GlyphTemplate> load_rank_templates(const std::string& dir);
// Bootstrap rank templates rendered with OpenCV's Hershey fonts — no files
// needed; good for synthetic tests, weaker on real table fonts.
std::vector<GlyphTemplate> synthesize_rank_templates();

// ---------------------------------------------------------------- recognizer

struct CardVisionConfig {
  // "simulator" (several templates per suit, colour-gated, simulator suit
  // regions) or "calibration" (one template per suit, corner-relative
  // regions, special hero-card regions).
  std::string profile = "simulator";
  // Rank acceptance (glyph Dice): strong = >= rank_threshold with
  // >= rank_margin over the runner-up; clear = >= rank_floor with
  // >= rank_clear_margin. Chosen on the research datasets: every wrong read
  // there scored < 0.80 AND led by < 0.06 (glance-cardvision eval).
  double rank_threshold = 0.80;
  double rank_margin = 0.02;
  double rank_floor = 0.60;
  double rank_clear_margin = 0.06;
  double suit_threshold = 0.75;  // research default
  double suit_margin = 0.05;     // research default
  bool occupancy = true;         // skip slots detected as empty
  OccupancyThresholds occupancy_thresholds;
  // Tesseract cross-check (only when ocr_available()). Glyph reads below
  // verify_trigger are verified; a disagreeing OCR read rejects the rank
  // unless OCR itself reaches verify_threshold (then OCR wins: "changed").
  // A rejected glyph read is recovered by OCR at >= ocr_threshold.
  bool ocr_verify = true;
  double verify_trigger = 0.85;
  double verify_threshold = 0.95;
  double ocr_threshold = 0.75;
};

struct RankRead {
  std::optional<std::string> rank;
  double confidence = 0.0;
  double margin = 0.0;
  std::string source;  // region name / "ocr:<region>"
  std::map<std::string, double> scores;
};

struct SuitRead {
  std::optional<std::string> suit;
  double confidence = 0.0;
  double margin = 0.0;
  std::string source;  // "<region>:<template>"
  std::map<std::string, double> scores;
  std::string color = "unknown";
};

struct CardReading {
  Occupancy occupancy;
  bool skipped = false;  // empty slot: recognition not attempted
  RankRead rank;
  SuitRead suit;
  // "not_required" | "unverified" (no OCR) | "confirmed" | "changed" |
  // "rejected" | "ocr_recovered" | "unrecognized" | "empty"
  std::string rank_verification = "not_required";
  std::optional<std::string> glyph_rank;  // the glyph read before verification
  bool recognized() const { return rank.rank && suit.suit; }
  // e.g. "Th"; empty unless recognized().
  std::string id() const;
  nlohmann::json to_json() const;
};

class CardRecognizer {
 public:
  // Load templates. rank_dir may be empty: synthesized Hershey templates are
  // used then. Returns false with error() on missing/incomplete suit sets.
  bool load(const CardVisionConfig& config, const std::string& suit_dir,
            const std::string& rank_dir);
  const std::string& error() const { return error_; }
  const CardVisionConfig& config() const { return config_; }
  std::size_t suit_template_count() const { return suit_templates_.size(); }
  std::size_t rank_template_count() const { return rank_templates_.size(); }

  // Recognize one card crop (BGR). `slot` selects slot-specific suit
  // regions in the calibration profile ("my1"/"hero_card_1", "my2"/
  // "hero_card_2"). Never throws; unusable input gives an unrecognized
  // reading.
  CardReading recognize(const cv::Mat& card, const std::string& slot = "") const;

  // Steps exposed for tools/tests.
  RankRead read_rank_glyph(const cv::Mat& card) const;
  SuitRead read_suit(const cv::Mat& card, const std::string& slot) const;

 private:
  struct NamedCrop {
    std::string name;
    cv::Mat image;
  };
  std::vector<NamedCrop> suit_candidates(const cv::Mat& card, const std::string& slot) const;

  CardVisionConfig config_;
  std::vector<GlyphTemplate> suit_templates_;
  std::vector<GlyphTemplate> rank_templates_;
  std::string error_;
};

// The rank glyph crops tried for a card (most specific first). Exposed so
// template harvesting cuts exactly what recognition compares.
std::vector<cv::Mat> rank_glyph_regions(const cv::Mat& card);

}  // namespace glance::vision
