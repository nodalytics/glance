#include "scraper.h"

#include <algorithm>
#include <cctype>
#include <filesystem>
#include <regex>
#include <unordered_map>

#include <opencv2/core.hpp>

#include "mapping.h"
#include "ocr.h"
#include "state_validation.h"
#include "template_match.h"

namespace fs = std::filesystem;

namespace glance {

namespace {

std::string join(const std::string& base, const std::string& rel) {
  if (fs::path(rel).is_absolute()) return rel;
  return (fs::path(base) / rel).string();
}

// Slot-name grammar: "my<n>", "board<n>", "p<n>_hand<m>". Returns an empty
// string when the name does not match.
struct SlotKind {
  bool my = false;
  bool board = false;
  int seat = -1;  // 0-based seat for my/p slots
  int idx = 0;
};

bool parse_slot(const std::string& name, SlotKind& out) {
  static const std::regex my_re(R"(^my(\d+)$)");
  static const std::regex board_re(R"(^board(\d+)$)");
  static const std::regex opp_re(R"(^p(\d+)_hand(\d+)$)");
  std::smatch m;
  if (std::regex_match(name, m, my_re)) {
    out.my = true;
    out.seat = 0;
    out.idx = std::stoi(m[1].str()) - 1;
    return true;
  }
  if (std::regex_match(name, m, board_re)) {
    out.board = true;
    out.idx = std::stoi(m[1].str()) - 1;
    return true;
  }
  if (std::regex_match(name, m, opp_re)) {
    int p = std::stoi(m[1].str());
    if (p < 1) return false;
    out.seat = p - 1;
    out.idx = std::stoi(m[2].str()) - 1;
    return true;
  }
  return false;
}

// Parse a seat label ("p1") into a 0-based seat index; -1 when not a seat.
int seat_index_from_label(const std::string& label) {
  if (label.size() < 2 || label[0] != 'p') return -1;
  for (size_t i = 1; i < label.size(); ++i)
    if (std::isdigit(static_cast<unsigned char>(label[i])) == 0) return -1;
  int idx = std::stoi(label.substr(1)) - 1;
  return idx >= 0 ? idx : -1;
}

std::string game_stage_from_board_count(int n) {
  if (n == 0) return "PreFlop";
  if (n == 3) return "Flop";
  if (n == 4) return "Turn";
  if (n == 5) return "River";
  return "";
}

}  // namespace

nlohmann::json to_json(const TableState& state) {
  nlohmann::json j;
  j["max_players"] = state.max_players;
  nlohmann::json seats = nlohmann::json::array();
  for (const auto& s : state.seats) {
    nlohmann::json sj;
    sj["index"] = s.index + 1;  // seats numbered from 1 in the API; 1 is the bot
    if (!s.cards.empty()) sj["cards"] = s.cards;
    if (s.stack >= 0.0) sj["stack"] = s.stack;
    if (s.bet) sj["bet"] = *s.bet;
    if (s.in_hand) sj["in_hand"] = true;
    seats.push_back(sj);
  }
  j["seats"] = seats;
  if (state.dealer_position) j["dealer"] = *state.dealer_position + 1;
  if (state.total_pot) j["pot"] = *state.total_pot;
  j["my_turn"] = state.my_turn;
  if (state.call_value) j["call"] = *state.call_value;
  if (state.raise_value) j["raise"] = *state.raise_value;
  if (state.game_stage) j["stage"] = *state.game_stage;
  if (!state.board.empty()) j["board"] = state.board;
  if (!state.seats.empty() && !state.seats[0].cards.empty()) j["my_cards"] = state.seats[0].cards;
  // Sanity-check the state before it crosses the wire: impossible recognitions
  // (a card read twice, board gaps, stage/board mismatch, negative amounts)
  // surface here so clients can distrust a broken state.
  j["validation"] = validate_table_state(state).to_json();
  return j;
}

bool TableScraper::load_mapping(const std::string& mapping_path) {
  error_.clear();
  TableMapping m;
  if (!m.load(mapping_path)) {
    error_ = m.error();
    return false;
  }
  mapping_ = m;
  base_dir_ = m.base_dir();
  anchor_threshold_ = m.anchor_threshold();
  template_threshold_ = m.template_threshold();
  max_players_ = m.max_players();
  crop_w_ = m.crop().width();
  crop_h_ = m.crop().height();

  anchor_template_ = load_template(join(base_dir_, m.topleft_template_path()));
  if (anchor_template_.empty()) {
    error_ = "cannot load anchor template: " + m.topleft_template_path();
    return false;
  }

  for (const auto& b : m.buttons()) {
    ButtonRef r;
    r.name = b.name;
    r.x1 = b.area.x1;
    r.y1 = b.area.y1;
    r.x2 = b.area.x2;
    r.y2 = b.area.y2;
    r.template_img = load_template(join(base_dir_, b.template_path));
    if (r.template_img.empty()) {
      error_ = "cannot load button template: " + b.template_path;
      return false;
    }
    buttons_.push_back(std::move(r));
  }

  for (const auto& ct : m.card_templates()) {
    CardTemplateRef r;
    r.id = ct.id;
    r.img = load_template(join(base_dir_, ct.path));
    if (r.img.empty()) {
      error_ = "cannot load card template: " + ct.path;
      return false;
    }
    card_templates_.push_back(std::move(r));
  }

  for (const auto& cs : m.card_slots()) {
    CardSlotRef r;
    r.slot = cs.slot;
    r.x1 = cs.area.x1;
    r.y1 = cs.area.y1;
    r.x2 = cs.area.x2;
    r.y2 = cs.area.y2;
    SlotKind probe;
    if (!parse_slot(r.slot, probe)) {
      error_ = "cards: unknown slot name: " + r.slot;
      return false;
    }
    card_slots_.push_back(std::move(r));
  }

  for (const auto& s : m.stacks()) {
    StackRef r;
    r.key = s.key;
    r.x1 = s.area.x1;
    r.y1 = s.area.y1;
    r.x2 = s.area.x2;
    r.y2 = s.area.y2;
    stacks_.push_back(std::move(r));
  }

  has_dealer_ = false;
  if (m.dealer()) {
    dealer_.template_img = load_template(join(base_dir_, m.dealer()->template_path));
    if (dealer_.template_img.empty()) {
      error_ = "cannot load dealer template: " + m.dealer()->template_path;
      return false;
    }
    for (const auto& [label, area] : m.dealer()->areas) {
      int idx = seat_index_from_label(label);
      if (idx < 0 || idx >= max_players_) {
        error_ = "dealer.areas: unknown seat label: " + label;
        return false;
      }
      dealer_.areas.emplace_back(idx, cv::Rect(area.x1, area.y1, area.width(), area.height()));
    }
    has_dealer_ = !dealer_.areas.empty();
  }

  last_state_.reset();
  table_found_ = false;
  return true;
}

std::optional<TableState> TableScraper::scrape(const cv::Mat& screenshot) {
  table_found_ = false;
  if (screenshot.empty() || anchor_template_.empty()) return std::nullopt;

  auto anchor = find_template(screenshot, anchor_template_, anchor_threshold_);
  if (!anchor) return std::nullopt;
  table_origin_ = anchor->location;
  if (table_origin_.x + crop_w_ > screenshot.cols || table_origin_.y + crop_h_ > screenshot.rows)
    return std::nullopt;
  table_found_ = true;

  cv::Mat window = screenshot(cv::Rect(table_origin_.x, table_origin_.y, crop_w_, crop_h_)).clone();

  TableState state;
  state.max_players = max_players_;
  state.seats.resize(max_players_);
  for (int i = 0; i < max_players_; ++i) state.seats[i].index = i;

  for (const auto& b : buttons_) {
    if (has_template_in_area(window, b.template_img, template_threshold_, b.x1, b.y1, b.x2, b.y2)) {
      state.my_turn = true;
    }
  }

  for (const auto& cs : card_slots_) {
    SlotKind kind;
    if (!parse_slot(cs.slot, kind)) continue;
    std::string card_id;
    for (const auto& ct : card_templates_) {
      if (has_template_in_area(window, ct.img, template_threshold_, cs.x1, cs.y1, cs.x2, cs.y2)) {
        card_id = ct.id;
        break;
      }
    }
    if (card_id.empty() || card_id == "empty") continue;
    if (kind.board) {
      if (card_id != "covered") {
        while ((int)state.board.size() <= kind.idx) state.board.push_back("");
        state.board[kind.idx] = card_id;
      }
      continue;
    }
    Seat& s = state.seats[kind.seat];
    if (card_id == "covered") {
      // cards present but face down: in the hand, identity unknown
      s.in_hand = true;
      continue;
    }
    while ((int)s.cards.size() <= kind.idx) s.cards.push_back("");
    s.cards[kind.idx] = card_id;
    s.in_hand = true;
  }
  // Drop empty board holes in the middle (a board card missing is an OCR-less
  // gap; keep positions stable otherwise).
  int stage_n = 0;
  for (const auto& c : state.board)
    if (!c.empty()) stage_n++;
  std::string stage = game_stage_from_board_count(stage_n);
  if (!stage.empty()) state.game_stage = stage;

  std::unordered_map<std::string, cv::Rect> fields;
  for (const auto& s : stacks_) fields[s.key] = cv::Rect(s.x1, s.y1, s.x2 - s.x1, s.y2 - s.y1);

  for (const auto& [key, rect] : fields) {
    if (rect.width <= 0 || rect.height <= 0) continue;
    cv::Mat region = window(rect);
    auto value = ocr_number(region);
    if (!value) continue;
    if (key == "pot") {
      state.total_pot = *value;
    } else if (key == "call") {
      state.call_value = *value;
    } else if (key == "raise") {
      state.raise_value = *value;
    } else {
      int idx = seat_index_from_label(key);
      if (idx >= 0 && idx < max_players_) {
        state.seats[idx].stack = *value;
        state.seats[idx].in_hand = true;
      }
    }
  }
  for (const auto& s : stacks_) {
    const std::string& key = s.key;
    if (key.size() > 4 && key.compare(key.size() - 4, 4, "_bet") == 0) {
      int idx = seat_index_from_label(key.substr(0, key.size() - 4));
      if (idx >= 0 && idx < max_players_) {
        cv::Mat region = window(cv::Rect(s.x1, s.y1, s.x2 - s.x1, s.y2 - s.y1));
        auto value = ocr_number(region);
        if (value) state.seats[idx].bet = *value;
      }
    }
  }

  if (has_dealer_) {
    for (const auto& [idx, rect] : dealer_.areas) {
      if (has_template_in_area(window, dealer_.template_img, template_threshold_, rect.x, rect.y,
                               rect.x + rect.width, rect.y + rect.height)) {
        state.dealer_position = idx;
        break;
      }
    }
  }

  last_state_ = state;
  return state;
}

}  // namespace glance
