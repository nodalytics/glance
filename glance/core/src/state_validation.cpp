#include "state_validation.h"

#include <algorithm>
#include <cctype>
#include <unordered_map>

namespace glance {

namespace {

// Split a glance card id ("Ah", "10c") into rank "A".."10" and suit "h/d/c/s".
// Returns false for the sentinels ("empty", "covered"), short/empty strings, and
// ids with no suit letter.
bool parse_card(const std::string& id, std::string& rank, char& suit) {
  if (id.size() < 2) return false;
  char s = static_cast<char>(std::tolower(static_cast<unsigned char>(id.back())));
  if (s != 'h' && s != 'd' && s != 'c' && s != 's') return false;
  std::string r = id.substr(0, id.size() - 1);
  if (r.empty()) return false;
  suit = s;
  rank = std::move(r);
  return true;
}

// True for the 52 card faces; false for "empty"/"covered" or malformed ids.
bool is_card_face(const std::string& id) {
  std::string rank;
  char suit;
  return parse_card(id, rank, suit);
}

nlohmann::json issue_json(const ValidationIssue& i) {
  nlohmann::json j;
  j["code"] = i.code;
  j["message"] = i.message;
  j["slots"] = i.slots;
  return j;
}

int stage_board_count(const std::string& stage) {
  if (stage == "PreFlop") return 0;
  if (stage == "Flop") return 3;
  if (stage == "Turn") return 4;
  if (stage == "River") return 5;
  return -1;
}

}  // namespace

nlohmann::json ValidationReport::to_json() const {
  nlohmann::json j;
  j["valid"] = valid;
  j["error_count"] = error_count;
  j["warning_count"] = warning_count;
  nlohmann::json errs = nlohmann::json::array();
  nlohmann::json warns = nlohmann::json::array();
  for (const auto& i : issues)
    (i.is_error ? errs : warns).push_back(issue_json(i));
  j["errors"] = errs;
  j["warnings"] = warns;
  return j;
}

ValidationReport validate_table_state(const TableState& state) {
  ValidationReport rep;
  auto add_error = [&](const std::string& code, const std::string& msg,
                       std::vector<std::string> slots) {
    ValidationIssue i{code, msg, std::move(slots), true};
    rep.issues.push_back(std::move(i));
  };
  auto add_warning = [&](const std::string& code, const std::string& msg,
                         std::vector<std::string> slots) {
    ValidationIssue i{code, msg, std::move(slots), false};
    rep.issues.push_back(std::move(i));
  };

  const int board_count = static_cast<int>(state.board.size());

  // --- board cards --------------------------------------------------------
  for (int i = 0; i < board_count; ++i) {
    const std::string& c = state.board[i];
    if (c.empty()) continue;
    if (c == "covered") continue;  // face-down board card is not readable
    if (!is_card_face(c))
      add_error("INVALID_BOARD_CARD", "Board slot " + std::to_string(i + 1) +
                                          " is not a valid card face: " + c,
                {"board" + std::to_string(i + 1)});
    if (i > 4)
      add_error("BOARD_OVERFLOW", "More than five board cards were read", {});
  }

  // The board fills left-to-right; an empty slot after the first card is a gap
  // (a card went unread in a hole the others are not).
  bool seen_card = false;
  for (int i = 0; i < board_count; ++i) {
    const bool empty = state.board[i].empty() || state.board[i] == "covered";
    if (empty) {
      if (seen_card)
        add_error("BOARD_GAP", "Board slot " + std::to_string(i + 1) +
                                    " is empty after a filled board slot",
                  {"board" + std::to_string(i + 1)});
    } else {
      seen_card = true;
    }
  }

  // --- duplicate faces ----------------------------------------------------
  // A face may occupy at most one slot: the board is community (no repeat in a
  // single hand) and two identical rank+suit cards cannot both be at the table.
  // A pocket PAIR (A♠ + A♥) is legal — only identical rank+suit is flagged.
  std::unordered_map<std::string, std::vector<std::string>> locations;
  for (int i = 0; i < board_count; ++i) {
    const std::string& c = state.board[i];
    if (!c.empty() && c != "covered")
      locations[c].push_back("board" + std::to_string(i + 1));
  }
  for (const auto& s : state.seats)
    for (int j = 0; j < static_cast<int>(s.cards.size()); ++j) {
      if (s.cards[j].empty()) continue;
      std::string label = s.index == 0 ? "my" + std::to_string(j + 1)
                                       : "p" + std::to_string(s.index + 1) + "_hand" +
                                             std::to_string(j + 1);
      locations[s.cards[j]].push_back(label);
    }
  for (const auto& [face, slots] : locations)
    if (slots.size() > 1)
      add_error("DUPLICATE_CARD", "Card " + face + " recognized in more than one slot", slots);

  // --- hands --------------------------------------------------------------
  // A seated player shows 0 or 2 hole cards; exactly one readable card means a
  // card went unread (warning, not error: the slot is simply not covered).
  for (const auto& s : state.seats) {
    int faces = 0;
    for (const auto& c : s.cards)
      if (!c.empty()) ++faces;
    if (faces == 1)
      add_warning("INCOMPLETE_HAND", "Seat " + std::to_string(s.index + 1) +
                                         " has exactly one readable hole card",
                  {});
  }

  // --- numbers ------------------------------------------------------------
  // OCR (tesseract) only returns non-negative values, so a negative amount is a
  // contradiction, not a miss. Absent values are the no-OCR mode: not an issue.
  auto check_amount = [&](const char* what, const std::optional<double>& v) {
    if (v && *v < 0.0) add_error("NEGATIVE_AMOUNT", std::string(what) + " is negative", {});
  };
  check_amount("pot", state.total_pot);
  check_amount("call", state.call_value);
  check_amount("raise", state.raise_value);
  for (const auto& s : state.seats) {
    // Seat::stack uses -1 as the "unread" sentinel; a value below zero that is
    // not the sentinel is impossible and indicates corruption.
    if (s.stack < 0.0 && s.stack != -1.0)
      add_error("NEGATIVE_STACK", "Seat " + std::to_string(s.index + 1) + " has a negative stack",
                {});
    if (s.bet && *s.bet < 0.0)
      add_error("NEGATIVE_BET", "Seat " + std::to_string(s.index + 1) + " has a negative bet", {});
  }

  // --- stage / board consistency ------------------------------------------
  // game_stage is derived from the board count, so the two must agree.
  if (state.game_stage) {
    int expected = stage_board_count(*state.game_stage);
    if (expected >= 0 && expected != board_count)
      add_error("STAGE_BOARD_MISMATCH", "Stage '" + *state.game_stage + "' implies " +
                                           std::to_string(expected) + " board cards, found " +
                                           std::to_string(board_count),
                {});
  }

  rep.error_count = static_cast<int>(
      std::count_if(rep.issues.begin(), rep.issues.end(),
                    [](const ValidationIssue& i) { return i.is_error; }));
  rep.warning_count = static_cast<int>(
      std::count_if(rep.issues.begin(), rep.issues.end(),
                    [](const ValidationIssue& i) { return !i.is_error; }));
  rep.valid = rep.error_count == 0;
  return rep;
}

}  // namespace glance
