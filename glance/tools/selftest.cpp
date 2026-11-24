// End-to-end selftest: synthesizes a fictional 6-max table window (anchor,
// cards, button, dealer chip, number regions) as in-memory images, writes the
// templates + a table mapping JSON out to disk, then runs the real scraper
// stack (mapping loader, template matching, OCR, to_json, ScreenshotService)
// and asserts the parsed state.
//
// Numeric fields (stacks, pot) are only checked when tesseract is available;
// the rest of the pipeline (anchor, cards, turn, stage, dealer) must always
// pass, so this works on machines without OCR.
//
// Usage:
//   glance-selftest                      run checks, clean up after
//   glance-selftest --fixtures <dir>     same, but leave the generated mapping
//                                       + screenshot in <dir> for smoke tests
//                                       (e.g. feed <dir>/screenshot.png to the
//                                       server started with <dir>/mapping.json)

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <optional>
#include <random>
#include <string>
#include <vector>

#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

#include "ocr.h"
#include "scraper.h"
#include "server.h"

namespace fs = std::filesystem;

static int failures = 0;

#define CHECK(cond, msg)                                    \
  do {                                                      \
    if (cond) {                                             \
      std::printf("  ok: %s\n", msg);                       \
    } else {                                                \
      std::printf("  FAIL: %s\n", msg);                     \
      ++failures;                                           \
    }                                                       \
  } while (0)

// Deterministic grayscale-noise pattern. Random enough that template matching
// only scores at/below a tight threshold at the pattern's exact placement.
cv::Mat make_pattern(int w, int h, unsigned seed) {
  cv::Mat m(h, w, CV_8UC3);  // Mat ctor takes (rows, cols) — keep w/h upright!
  std::mt19937 rng(seed);
  std::uniform_int_distribution<int> d(0, 255);
  for (int y = 0; y < h; ++y)
    for (int x = 0; x < w; ++x) {
      int v = d(rng);
      m.at<cv::Vec3b>(y, x) = cv::Vec3b(v, v, v);
    }
  return m;
}

// Low-amplitude noisy dark background for the "screenshot".
cv::Mat make_background(int w, int h, unsigned seed) {
  cv::Mat m(h, w, CV_8UC3);  // Mat ctor takes (rows, cols) — keep w/h upright!
  std::mt19937 rng(seed);
  std::uniform_int_distribution<int> d(12, 28);
  for (int y = 0; y < h; ++y)
    for (int x = 0; x < w; ++x) {
      int v = d(rng);
      m.at<cv::Vec3b>(y, x) = cv::Vec3b(v, v, v);
    }
  return m;
}

static void write_img(const fs::path& p, const cv::Mat& m) {
  fs::create_directories(p.parent_path());
  if (!cv::imwrite(p.string(), m)) {
    std::printf("  FAIL: could not write %s\n", p.c_str());
    ++failures;
  }
}

int main(int argc, char** argv) {
  fs::path fixture_dir;
  for (int i = 1; i + 1 < argc; ++i)
    if (std::string(argv[i]) == "--fixtures") fixture_dir = argv[i + 1];

  char tmpl[] = "/tmp/glance_selftest_XXXXXX";
  char* dir = mkdtemp(tmpl);
  fs::path base = dir ? dir : std::string("/tmp/glance_selftest");
  fs::create_directories(base);

  // --- geometry -------------------------------------------------------------
  constexpr int shot_w = 1000, shot_h = 700;
  constexpr int crop_w = 600, crop_h = 400;
  cv::Point anchor_at(120, 80);
  const cv::Mat anchor = make_pattern(48, 32, 101);

  const cv::Mat card_ah = make_pattern(36, 48, 201);
  const cv::Mat card_2c = make_pattern(36, 48, 202);
  const cv::Mat card_7d = make_pattern(36, 48, 203);
  const cv::Mat card_ks = make_pattern(36, 48, 204);
  const cv::Mat card_qh = make_pattern(36, 48, 205);
  const cv::Mat covered = make_pattern(36, 48, 206);
  const cv::Mat call_btn = make_pattern(80, 40, 301);
  const cv::Mat dealer_chip = make_pattern(28, 28, 401);

  // --- compose the screenshot ----------------------------------------------
  cv::Mat shot = make_background(shot_w, shot_h, 7);
  // NOTE: paste with copyTo — `shot(cv::Rect(...)) = m` is a no-op (it only
  // reassigns the temporary Mat's header, the image data is never touched).
  anchor.copyTo(shot(cv::Rect(anchor_at.x, anchor_at.y, anchor.cols, anchor.rows)));
  // Cards (window-relative positions; the window starts at anchor_at).
  auto paste = [&](const cv::Mat& m, int wx, int wy) {
    m.copyTo(shot(cv::Rect(anchor_at.x + wx, anchor_at.y + wy, m.cols, m.rows)));
  };
  paste(card_ah, 60, 300);   // my1
  paste(card_2c, 110, 300);  // my2
  paste(card_7d, 240, 200);  // board1
  paste(card_ks, 286, 200);  // board2
  paste(card_qh, 332, 200);  // board3
  paste(covered, 60, 60);    // p2_hand1
  paste(covered, 110, 60);   // p2_hand2
  paste(call_btn, 250, 340);  // call button -> my turn
  paste(dealer_chip, 160, 60);  // button on p3
  // Number regions (white text on the dark background for OCR).
  cv::putText(shot, "243.50", cv::Point(anchor_at.x + 420, anchor_at.y + 46),
              cv::FONT_HERSHEY_SIMPLEX, 0.7, cv::Scalar(255, 255, 255), 2);
  cv::putText(shot, "1200", cv::Point(anchor_at.x + 158, anchor_at.y + 370),
              cv::FONT_HERSHEY_SIMPLEX, 0.7, cv::Scalar(255, 255, 255), 2);
  write_img(base / "screenshot.png", shot);

  // --- templates + mapping ---------------------------------------------------
  write_img(base / "templates" / "anchor.png", anchor);
  write_img(base / "templates" / "call.png", call_btn);
  write_img(base / "templates" / "dealer.png", dealer_chip);
  write_img(base / "cards" / "Ah.png", card_ah);
  write_img(base / "cards" / "2c.png", card_2c);
  write_img(base / "cards" / "7d.png", card_7d);
  write_img(base / "cards" / "Ks.png", card_ks);
  write_img(base / "cards" / "Qh.png", card_qh);
  write_img(base / "cards" / "covered.png", covered);

  nlohmann::json m;
  m["name"] = "selftest";
  m["crop"] = nlohmann::json{{"x", crop_w}, {"y", crop_h}};
  m["topleft"] = "templates/anchor.png";
  m["anchor_threshold"] = 0.01;
  m["template_threshold"] = 0.07;
  m["max_players"] = 6;
  nlohmann::json cards = nlohmann::json::object();
  cards["my1"] = {60, 300, 96, 348};
  cards["my2"] = {110, 300, 146, 348};
  cards["board1"] = {240, 200, 276, 248};
  cards["board2"] = {286, 200, 322, 248};
  cards["board3"] = {332, 200, 368, 248};
  cards["p2_hand1"] = {60, 60, 96, 108};
  cards["p2_hand2"] = {110, 60, 146, 108};
  m["cards"] = cards;
  m["card_templates"] = {"cards/Ah.png", "cards/2c.png", "cards/7d.png", "cards/Ks.png",
                         "cards/Qh.png", "cards/covered.png"};
  nlohmann::json buttons = nlohmann::json::object();
  buttons["call"] = {{"template", "templates/call.png"}, {"area", {250, 340, 330, 380}}};
  m["buttons"] = buttons;
  nlohmann::json stacks = nlohmann::json::object();
  stacks["pot"] = {400, 20, 560, 60};
  stacks["p1"] = {150, 340, 250, 380};
  m["stacks"] = stacks;
  nlohmann::json dealer = nlohmann::json::object();
  dealer["template"] = "templates/dealer.png";
  dealer["areas"] = nlohmann::json::object();
  dealer["areas"]["p1"] = {20, 60, 48, 88};
  dealer["areas"]["p2"] = {100, 60, 128, 88};
  dealer["areas"]["p3"] = {160, 60, 188, 88};
  m["dealer"] = dealer;
  {
    std::ofstream out(base / "mapping.json");
    out << m.dump(2) << "\n";
  }

  // --- run the scraper --------------------------------------------------------
  std::printf("selftest: mapping at %s, ocr=%s\n", (base / "mapping.json").c_str(),
              glance::ocr_available() ? "yes" : "no (numeric checks skipped)");

  glance::TableScraper scraper;
  CHECK(scraper.load_mapping((base / "mapping.json").string()), "mapping loads");
  if (failures) {
    std::printf("  mapping error: %s\n", scraper.error().c_str());
  }

  cv::Mat blank = make_background(shot_w, shot_h, 99);
  CHECK(!scraper.scrape(blank).has_value(), "anchor not found in blank image");

  // OpenCV sanity: a template pasted verbatim MUST be the unique best match at
  // its planted position.
  //
  // Exactness caveat (measured, not assumed): matchTemplate's SQDIFF variant
  // is built on OpenCV's integral images, which are float32. For a real
  // (hundreds-of-thousands-of-pixels, d2 sum ~1e8) random pattern, float32
  // rounding alone leaves dozens of d2 units of "error" at a byte-identical
  // plant — verified with a manual per-pixel reference (0 diff, kernel
  // agrees to float32 precision on every neighbouring cell). After
  // TM_SQDIFF_NORMED's N/(I2+T2) rescaling that residual is ~1e-7, far
  // below the 0.01 anchor threshold, and the plant is still the unique grid
  // minimum (second-best d2 is ~5e7). So the guard asserts: the planted cell
  // is the grid minimum AT the planted position, its value is tiny (< 1e-4),
  // and minMaxLoc agrees with the grid. (matchTemplate results are CV_32F —
  // always read with .at<float>: reading them as doubles puns float pairs and
  // yields ~1e60 "corrupted" values.)
  {
    cv::Mat res;
    cv::matchTemplate(shot(cv::Rect(0, 0, 400, 300)), anchor, res, cv::TM_SQDIFF_NORMED);
    double mn = 0, mx = 0;
    cv::Point mnl, mxl;
    cv::minMaxLoc(res, &mn, &mx, &mnl, &mxl);
    float plant = res.at<float>(anchor_at.y, anchor_at.x);
    CHECK(mnl == anchor_at, "matchTemplate scores its minimum at the planted position");
    CHECK(plant < 1e-4 && std::fabs(mn - double(plant)) < 1e-9,
          "exact match is a tiny, unique minimum (OpenCV sanity)");
  }

  std::optional<glance::TableState> state = scraper.scrape(shot);
  CHECK(state.has_value(), "table anchor found in screenshot");
  if (state) {
    CHECK(scraper.table_origin().x == anchor_at.x && scraper.table_origin().y == anchor_at.y,
          "table origin matches planted anchor");
    const auto& s = *state;
    CHECK(s.my_turn, "call button detected -> my_turn");
    CHECK(static_cast<int>(s.board.size()) == 3 && s.board[0] == "7d" && s.board[1] == "Ks" &&
              s.board[2] == "Qh",
          "board cards 7d Ks Qh");
    if (s.game_stage)
      CHECK(*s.game_stage == "Flop", "stage Flop from 3 board cards");
    else
      CHECK(false, "stage Flop from 3 board cards");
    int my_i = 0;
    CHECK(static_cast<int>(s.seats.size()) == 6 && s.seats[my_i].cards.size() == 2 &&
              s.seats[my_i].cards[0] == "Ah" && s.seats[my_i].cards[1] == "2c",
          "my hole cards Ah 2c");
    CHECK(s.seats[1].in_hand, "opponent p2 in hand (covered cards)");
    if (s.dealer_position)
      CHECK(*s.dealer_position == 2, "button on p3");
    else
      CHECK(false, "button on p3");

    auto check_value = [&](const char* what, std::optional<double> v, double expected) {
      if (!v) {
        std::printf("  FAIL: %s not read\n", what);
        ++failures;
        return;
      }
      bool ok = std::fabs(*v - expected) <= std::max(0.51, expected * 0.02);
      std::printf("  %s: %s = %.2f (expected ~%.2f)\n", ok ? "ok" : "FAIL", what, *v, expected);
      if (!ok) ++failures;
    };
    if (glance::ocr_available()) {
      check_value("pot", s.total_pot, 243.5);
      check_value("p1 stack", s.seats[0].stack >= 0 ? std::optional<double>(s.seats[0].stack)
                                                    : std::nullopt,
                  1200.0);
    }

    // --- to_json -------------------------------------------------------------
    nlohmann::json j = glance::to_json(s);
    CHECK(j.contains("my_cards") && j["my_cards"][0] == "Ah" && j["my_cards"][1] == "2c",
          "json my_cards Ah 2c");
    CHECK(j["stage"] == "Flop", "json stage Flop");
    CHECK(j["my_turn"] == true, "json my_turn true");
    CHECK(j["dealer"] == 3, "json dealer is seat 3 (1-based)");
    CHECK(j["seats"][0]["cards"][0] == "Ah", "json seats are 1-based with bot at seat 1");
    if (glance::ocr_available()) {
      if (j.contains("pot") && std::fabs(j["pot"].get<double>() - 243.5) < 1.0)
        std::printf("  ok: json pot %s\n", j["pot"].dump().c_str());
      else {
        std::printf("  FAIL: json pot missing or wrong\n");
        ++failures;
      }
    }

    // --- ScreenshotService (the HTTP layer's state holder) ---------------------
    std::vector<unsigned char> buf;
    cv::imencode(".png", shot, buf);
    glance::ScreenshotService service(&scraper);
    CHECK(service.update(buf), "service accepts an encoded screenshot");
    CHECK(service.has_state(), "service holds the parsed state");
    CHECK(service.state_json()["stage"] == "Flop", "service state matches");
    std::vector<unsigned char> junk{1, 2, 3};
    CHECK(!service.update(junk), "service rejects undecodable bytes");
  }

  // --- fixture mode ------------------------------------------------------------
  if (!fixture_dir.empty()) {
    fs::create_directories(fixture_dir);
    fs::copy(base, fixture_dir,
             fs::copy_options::recursive | fs::copy_options::skip_existing);
    std::printf("fixtures left in %s (mapping: %s, screenshot: %s)\n", fixture_dir.c_str(),
                (fixture_dir / "mapping.json").c_str(), (fixture_dir / "screenshot.png").c_str());
  } else {
    fs::remove_all(base);
  }

  if (failures == 0) {
    std::printf("selftest: PASS\n");
    return 0;
  }
  std::printf("selftest: FAIL (%d check(s) failed)\n", failures);
  return 1;
}
