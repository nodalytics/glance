#pragma once

#include <string>
#include <vector>

#include <nlohmann/json.hpp>

#include "scraper.h"

namespace glance {

// A single validation finding. Errors make the state invalid; warnings do not.
struct ValidationIssue {
  std::string code;
  std::string message;
  std::vector<std::string> slots;  // affected slot labels, if any
  bool is_error = true;
};

// The result of sanity-checking a parsed table state.
struct ValidationReport {
  bool valid = true;  // true when there are zero errors
  int error_count = 0;
  int warning_count = 0;
  std::vector<ValidationIssue> issues;  // errors and warnings, in check order

  // Serializes to the shape documented in docs/engine.md (repo root):
  //   {"valid":bool,"error_count":n,"warning_count":n,
  //    "errors":[{code,message,slots}],"warnings":[{code,message,slots}]}
  nlohmann::json to_json() const;
};

// Validate a parsed TableState for internal consistency. This is pure logic —
// no OCR, no pixels: it catches impossible recognitions (a card appearing twice,
// an impossible board count, a board gap, a negative stack/pot) before the state
// is handed to a client. It never modifies the state.
//
// Ported from the Python research prototype (research/poker_apis/validation/
// card_state_validator.py + vision/table_validation.py), adapted to glance's
// TableState and free-form card ids.
ValidationReport validate_table_state(const TableState& state);

}  // namespace glance
