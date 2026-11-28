// glance-acrtest: end-to-end proof that glance reads a REAL ACR Poker table.
//
// Loads the shipped ACR package mapping (packages/acr/mappings/6max.json) and
// runs it over research/test_images/ss.jpeg — a real 1600x899 ACR river grab —
// through the full TableScraper (anchor match, fixed crop, template-free card
// vision). Asserts the five community cards read A-hearts 8-spades J-hearts
// J-diamonds 2-hearts with no per-card templates, prints the whole parse, and
// checks the pot (OCR, CI only) and dealer button when they are available.
//
// The research tree is optional, so the test SKIPS cleanly (exit 0) when
// ss.jpeg is not present — exactly like the cardvision_* gates.

#include <cmath>
#include <cstdio>
#include <filesystem>
#include <optional>
#include <string>
#include <vector>

#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>

#include "ocr.h"
#include "scraper.h"
#include "template_match.h"

namespace fs = std::filesystem;

#ifndef GLANCE_ACR_PACKAGE_DIR
#define GLANCE_ACR_PACKAGE_DIR "packages/acr"
#endif
#ifndef GLANCE_RESEARCH_DIR
#define GLANCE_RESEARCH_DIR "../research"
#endif

static int failures = 0;
#define CHECK(cond, msg)                               \
  do {                                                 \
    if (cond) {                                        \
      std::printf("  ok: %s\n", msg);                  \
    } else {                                           \
      std::printf("  FAIL: %s\n", msg);                \
      ++failures;                                      \
    }                                                  \
    std::fflush(stdout);                               \
  } while (0)

int main() {
  const std::string mapping = std::string(GLANCE_ACR_PACKAGE_DIR) + "/mappings/6max.json";
  const std::string image = std::string(GLANCE_RESEARCH_DIR) + "/test_images/ss.jpeg";

  if (!fs::exists(image)) {
    std::printf("acrtest: SKIP (no %s; research image tree not present)\n", image.c_str());
    return 0;
  }
  std::printf("acrtest: mapping=%s image=%s ocr=%s\n", mapping.c_str(), image.c_str(),
              glance::ocr_available() ? "yes" : "no (numeric checks skipped)");

  glance::TableScraper scraper;
  if (!scraper.load_mapping(mapping)) {
    std::printf("acrtest: FAIL mapping load: %s\n", scraper.error().c_str());
    return 1;
  }
  CHECK(scraper.card_recognizer() != nullptr, "acr mapping loads with a card_vision recognizer");

  cv::Mat shot = cv::imread(image, cv::IMREAD_COLOR);
  CHECK(!shot.empty() && shot.cols == 1600 && shot.rows == 899, "ss.jpeg decodes at 1600x899");

  std::optional<glance::TableState> st = scraper.scrape(shot);
  CHECK(st.has_value(), "anchor found and the real table parsed");
  if (!st) {
    std::printf("acrtest: FAIL (table not found at anchor)\n");
    return 1;
  }
  CHECK(scraper.table_origin().x == 0 && scraper.table_origin().y == 0,
        "anchor matched at the window top-left (0,0)");

  // The bot's "exactly one top-left corner" rule: the star-icon anchor must be
  // a unique hit at the tight threshold, or the fixed crop is not trustworthy.
  cv::Mat anchor =
      glance::load_template(std::string(GLANCE_ACR_PACKAGE_DIR) + "/mappings/templates/anchor.png");
  CHECK(!anchor.empty(), "anchor template loads");
  const double at = scraper.mapping().anchor_threshold();
  const int hits = glance::count_template_hits(shot, anchor, at);
  char amsg[96];
  std::snprintf(amsg, sizeof(amsg), "anchor is a unique hit (count=%d at threshold %.3f)", hits, at);
  CHECK(hits == 1, amsg);

  std::printf("acrtest: parsed state:\n%s\n", glance::to_json(*st).dump(2).c_str());

  // The gated assertion: the whole community board read template-free. These
  // ranks have harvested ACR glyph templates (A,8,J,2) and the suits come from
  // the simulator + ACR suit set, so every card is checked in full.
  const std::vector<std::string> want = {"Ah", "8s", "Jh", "Jd", "2h"};
  std::string got;
  for (const auto& b : st->board) got += b + " ";
  char msg[160];
  std::snprintf(msg, sizeof(msg), "board reads Ah 8s Jh Jd 2h template-free (got: %s)",
                got.empty() ? "<none>" : got.c_str());
  CHECK(st->board == want, msg);
  CHECK(st->game_stage && *st->game_stage == "River", "stage River from 5 board cards");

  // Hero cards are greyed out at showdown and sit partly behind the time-bank
  // avatar / dealer chip, so they are reported but not gated.
  if (!st->seats.empty()) {
    std::string hero;
    for (const auto& c : st->seats[0].cards) hero += c + " ";
    std::printf("  (hero cards read: %s)\n", hero.empty() ? "<none>" : hero.c_str());
  }

  // Dealer button: print it; assert only that a matched chip lands on a real
  // seat (the button moves per hand, so the exact seat is not pinned here).
  if (st->dealer_position) {
    std::printf("  (dealer chip matched at seat p%d)\n", *st->dealer_position + 1);
    CHECK(*st->dealer_position >= 0 && *st->dealer_position < st->max_players,
          "dealer chip resolves to a valid seat");
  } else {
    std::printf("  (dealer chip not matched)\n");
  }

  // Pot is OCR, so it only runs where tesseract is installed (CI, never the lab).
  if (glance::ocr_available()) {
    if (st->total_pot) {
      std::printf("  (pot OCR: %.0f)\n", *st->total_pot);
      // Clean white italic "47,500"; allow a little slack for a glyph wobble,
      // but a digit-count error (a mis-placed field) still fails.
      CHECK(std::fabs(*st->total_pot - 47500.0) < 2000.0, "pot OCR reads ~47,500");
    } else {
      // OCR present but nothing parsed from the pot crop: report, don't fail.
      std::printf("  (pot not read by OCR)\n");
    }
  }

  // Second real frame: img.jpeg is a preflop action grab on another ACR table
  // (same client skin). It proves the anchor, crop and action-button templates
  // work on a different hand: the Fold/Call buttons are up, so my_turn is true.
  const std::string image2 = std::string(GLANCE_RESEARCH_DIR) + "/test_images/img.jpeg";
  if (fs::exists(image2)) {
    cv::Mat shot2 = cv::imread(image2, cv::IMREAD_COLOR);
    std::optional<glance::TableState> st2 = scraper.scrape(shot2);
    CHECK(st2.has_value(), "img.jpeg (preflop, second table) parses through the same mapping");
    if (st2) {
      std::printf("acrtest: img.jpeg state: stage=%s my_turn=%d hero=",
                  st2->game_stage ? st2->game_stage->c_str() : "-", st2->my_turn ? 1 : 0);
      if (!st2->seats.empty())
        for (const auto& c : st2->seats[0].cards) std::printf("%s ", c.c_str());
      std::printf("\n");
      CHECK(st2->my_turn, "Fold/Call button templates detected on img.jpeg -> my_turn");
      CHECK(st2->board.empty() && st2->game_stage && *st2->game_stage == "PreFlop",
            "img.jpeg has no board -> PreFlop");
    }
  }

  if (failures == 0) {
    std::printf("acrtest: PASS\n");
    return 0;
  }
  std::printf("acrtest: FAIL (%d check(s) failed)\n", failures);
  return 1;
}
