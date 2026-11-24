#pragma once

#include <optional>
#include <string>
#include <utility>
#include <vector>
#include <nlohmann/json.hpp>

namespace poker {

// A rectangle of pixels, used for both the crop origin and the search areas
// in a table mapping.
struct Rect {
  int x1 = 0;
  int y1 = 0;
  int x2 = 0;
  int y2 = 0;
  int width() const { return x2 - x1; }
  int height() const { return y2 - y1; }
};

// A table mapping: what to look for (template PNGs) and where to look for it
// (search areas relative to the table's top-left corner). JSON format:
//
//   {
//     "name": "acr-6max",
//     "crop": {"x": 1600, "y": 900},
//     "topleft": "templates/anchor.png",
//     "anchor_threshold": 0.01,
//     "template_threshold": 0.07,
//     "card_templates": ["cards/Ah.png", ..., "cards/covered.png"],
//     "cards": {"my1": [x1,y1,x2,y2], "board1": [..], "p3_hand1": [..]},
//     "buttons": {"call": {"template": "templates/call.png", "area": [.., .., .., ..]}},
//     "dealer": {"template": "templates/dealer.png", "areas": {"p1": [..], "p2": [..]}},
//     "stacks": {"p1": [..], "p1_bet": [..], "pot": [..], "call": [..], "raise": [..]}
//   }
//
// All template paths are relative to the mapping file's directory.
//
// "cards" maps slot names to the fixed screen area where that card sits. Slot
// names starting with "my" (<n>) are the bot's own hole cards, "board<n>" the
// community cards, "p<n>_hand<m>" an opponent's hole cards. At scrape time
// every "card_templates" entry is tried against each slot's area and the
// first template that matches identifies the card (the template's file stem
// is the card id, e.g. "Ah"; "covered" means no card).
//
// "stacks" maps number fields to their screen areas. Keys: "pot", "call",
// "raise" and per-seat stacks/bets "p<n>" / "p<n>_bet" (p1 is the bot's own
// seat). Values are read with OCR.
//
// Optionally: "max_players" (default 6), and "dealer": {"template": path,
// "areas": {"p1": [..], ...}} to locate the button.
class TableMapping {
 public:
  struct Dealer {
    std::string template_path;
    std::vector<std::pair<std::string, Rect>> areas;  // seat label ("p1") + area
  };
  bool load(const std::string& path);
  bool loaded() const { return loaded_; }
  std::string error() const { return error_; }
  const std::string& name() const { return name_; }
  const Rect& crop() const { return crop_; }
  const std::string& topleft_template_path() const { return topleft_template_path_; }
  const std::string& base_dir() const { return base_dir_; }
  double anchor_threshold() const { return anchor_threshold_; }
  double template_threshold() const { return template_threshold_; }
  int max_players() const { return max_players_; }
  const std::optional<Dealer>& dealer() const { return dealer_; }

  struct Button {
    std::string name;
    std::string template_path;
    Rect area;
  };

  struct CardSlot {
    std::string slot;  // "my1", "board3", "p2_hand1", ...
    Rect area;
  };

  struct CardTemplate {
    std::string id;  // file stem, e.g. "Ah", "2c", "covered"
    std::string path;
  };

  struct StackArea {
    std::string key;  // "pot", "call", "raise", "p1", "p1_bet", ...
    Rect area;
  };

  const std::vector<Button>& buttons() const { return buttons_; }
  const std::vector<CardSlot>& card_slots() const { return card_slots_; }
  const std::vector<CardTemplate>& card_templates() const { return card_templates_; }
  const std::vector<StackArea>& stacks() const { return stacks_; }
  bool has_button(const std::string& name) const;

 private:
  std::string base_dir_;
  bool loaded_ = false;
  std::string error_;
  std::string name_;
  Rect crop_;
  std::string topleft_template_path_;
  double anchor_threshold_ = 0.01;
  double template_threshold_ = 0.07;
  int max_players_ = 6;
  std::optional<Dealer> dealer_;
  std::vector<Button> buttons_;
  std::vector<CardSlot> card_slots_;
  std::vector<CardTemplate> card_templates_;
  std::vector<StackArea> stacks_;
};

}  // namespace poker
