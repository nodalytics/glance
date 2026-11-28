#pragma once

#include <string>
#include <vector>
#include <optional>
#include <nlohmann/json.hpp>
#include <opencv2/core.hpp>

#include "card_vision.h"
#include "mapping.h"

namespace glance {

struct Seat {
  int index = 0;  // 0 is the bot's own seat
  std::vector<std::string> cards;  // hole cards, e.g. {"Ah"}
  double stack = -1.0;  // -1 when unread
  std::optional<double> bet;
  bool in_hand = false;
};

struct TableState {
  std::vector<Seat> seats;
  int max_players = 6;
  std::optional<int> dealer_position;  // seat index holding the button
  std::optional<double> total_pot;
  bool my_turn = false;
  std::optional<double> call_value;
  std::optional<double> raise_value;
  std::optional<std::string> game_stage;  // PreFlop / Flop / Turn / River
  std::vector<std::string> board;
};

// TableState::to_json serializes the state for the API; empty optionals and
// unread values are omitted.
nlohmann::json to_json(const TableState& state);

// The scraper: given a table mapping and a screenshot, produce a TableState.
//
// A screenshot is a full desktop grab (or anything else). The scraper first
// locates the table's top-left corner (anchor template match; must be found
// exactly once), crops the mapping-sized window at that corner, then resolves
// every field relative to the corner: buttons (action state) by template
// match, cards by trying the whole card template library against each slot,
// and the numbers (stacks, bets, pot, call, raise) via OCR.
class TableScraper {
 public:
  // Load templates for the mapping. Returns false on error (see error()).
  bool load_mapping(const std::string& mapping_path);
  const std::string& error() const { return error_; }

  // Parse a screenshot into a TableState. Returns nullopt when the table
  // anchor is not found (uniquely) in the screenshot.
  std::optional<TableState> scrape(const cv::Mat& screenshot);

  const TableState* last_state() const { return last_state_ ? &*last_state_ : nullptr; }
  bool table_found() const { return table_found_; }
  const cv::Point& table_origin() const { return table_origin_; }
  // The loaded table mapping (the control layer resolves its "actions" and
  // "window_title" against this). Valid after a successful load_mapping.
  const TableMapping& mapping() const { return mapping_; }
  // The mapping's optional "card_vision" recognizer (template-free card
  // reading, core/card_vision.h); nullptr when the mapping has no
  // "card_vision" section. Used for slots no card template matched, and by
  // the HTTP layer for POST /recognize-card.
  const vision::CardRecognizer* card_recognizer() const {
    return has_card_vision_ ? &card_vision_ : nullptr;
  }

 private:
  int crop_w_ = 0;
  int crop_h_ = 0;
  int max_players_ = 6;
  std::string base_dir_;
  double anchor_threshold_ = 0.01;
  double template_threshold_ = 0.07;
  cv::Mat anchor_template_;

  struct ButtonRef {
    std::string name;
    cv::Mat template_img;
    int x1 = 0, y1 = 0, x2 = 0, y2 = 0;
  };
  struct CardTemplateRef {
    std::string id;
    cv::Mat img;
  };
  struct CardSlotRef {
    std::string slot;
    int x1 = 0, y1 = 0, x2 = 0, y2 = 0;
  };
  struct StackRef {
    std::string key;
    int x1 = 0, y1 = 0, x2 = 0, y2 = 0;
  };
  struct DealerRef {
    cv::Mat template_img;
    std::vector<std::pair<int, cv::Rect>> areas;  // (seat_index, area)
  };
  bool has_dealer_ = false;
  bool has_card_vision_ = false;
  vision::CardRecognizer card_vision_;

  std::vector<ButtonRef> buttons_;
  std::vector<CardTemplateRef> card_templates_;
  std::vector<CardSlotRef> card_slots_;
  std::vector<StackRef> stacks_;
  DealerRef dealer_;

  bool table_found_ = false;
  cv::Point table_origin_{0, 0};
  TableMapping mapping_;
  std::optional<TableState> last_state_;
  std::string error_;
};

}  // namespace glance
