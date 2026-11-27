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
#include <thread>
#include <vector>

#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

#include <httplib.h>

#include "control.h"
#include "control_service.h"
#include "ocr.h"
#include "scraper.h"
#include "server.h"
#include "server_control.h"
#include "state_validation.h"

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
    std::fflush(stdout);                                    \
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

// Fake platform for the control checks: a Screen that returns a fixed region
// (the composed screenshot) and an Input that records every call. The selftest
// never touches a real display; the server's real backend is X11 or null.
class FakeScreen : public glance::control::Screen {
 public:
  cv::Mat region;  // what grab() returns for any (x,y,w,h)
  bool grab(int x, int y, int w, int h, cv::Mat& out) override {
    (void)x;
    (void)y;
    (void)w;
    (void)h;
    out = region;
    return !region.empty();
  }
  bool grab_all(cv::Mat& out) override { return grab(0, 0, region.cols, region.rows, out); }
  bool locate_window(const std::string&, int& x, int& y, int& w, int& h) override {
    x = 500;
    y = 100;
    w = region.cols;
    h = region.rows;
    return true;
  }
  std::string backend_name() const override { return "fake"; }
};
class FakeInput : public glance::control::Input {
 public:
  std::vector<std::tuple<int, int, int>> clicks;
  std::vector<std::string> keys;
  std::string typed;
  void move_to(int, int) override {}
  void click(int x, int y, Button b) override { clicks.emplace_back(x, y, static_cast<int>(b)); }
  bool press_key(const std::string& k) override {
    keys.push_back(k);
    return true;
  }
  bool type_text(const std::string& t) override {
    typed += t;
    return true;
  }
};

static void write_img(const fs::path& p, const cv::Mat& m) {
  fs::create_directories(p.parent_path());
  bool ok = false;
  try {
    ok = cv::imwrite(p.string(), m);
  } catch (const cv::Exception& e) {
    std::printf("  imwrite %s threw: %s\n", p.c_str(), e.what());
  }
  if (!ok || !fs::exists(p)) {
    std::printf("  FAIL: could not write %s\n", p.c_str());
    ++failures;
  }
}

int main(int argc, char** argv) {
  // CHECK (and the line below) fflush(stdout) after every print: printf
  // buffers stdout when piped (as ctest runs us), and an abort mid-run would
  // otherwise lose every line printed before it — which is exactly how the
  // CI imwrite abort stayed silent for one diagnostic round.
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
  const cv::Mat card_ad = make_pattern(36, 48, 207);  // same rank as Ah, other suit
  const cv::Mat card_empty = make_pattern(36, 48, 208);
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
  paste(covered, 110, 60);      // p2_hand2
  paste(card_ad, 400, 60);      // p4_hand1 — suit must not collapse into Ah
  paste(card_empty, 460, 60);   // p5_hand1 — "empty" sentinel, not a card
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
  write_img(base / "cards" / "Ad.png", card_ad);
  write_img(base / "cards" / "empty.png", card_empty);

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
  cards["board4"] = {378, 200, 414, 248};  // defined, nothing planted
  cards["p2_hand1"] = {60, 60, 96, 108};
  cards["p2_hand2"] = {110, 60, 146, 108};
  cards["p4_hand1"] = {400, 60, 436, 108};
  cards["p5_hand1"] = {460, 60, 496, 108};
  m["cards"] = cards;
  m["card_templates"] = {"cards/Ad.png", "cards/Ah.png", "cards/2c.png", "cards/7d.png",
                         "cards/Ks.png", "cards/Qh.png", "cards/covered.png", "cards/empty.png"};
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
  nlohmann::json actions = nlohmann::json::object();
  actions["call"] = "button:call";      // maps to a real button -> resolvable
  actions["fold"] = "button:fold";      // target name has no button entry
  actions["pot_label"] = "stack:pot";   // maps to a real stack area
  actions["bogus"] = "weird:whatever";  // malformed target scheme
  m["actions"] = actions;
  m["window_title"] = "selftest-table";
  {
    std::ofstream out(base / "mapping.json");
    out << m.dump(2) << "\n";
  }

  // --- run the scraper --------------------------------------------------------
  std::printf("selftest: mapping at %s, ocr=%s\n", (base / "mapping.json").c_str(),
              glance::ocr_available() ? "yes" : "no (numeric checks skipped)");
  std::fflush(stdout);

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
    CHECK(static_cast<int>(s.board.size()) == 3, "unpainted board4 does not invent a 4th card");
    CHECK(s.seats[3].cards.size() == 1 && s.seats[3].cards[0] == "Ad",
          "Ad template does not match as Ah");
    CHECK(s.seats[0].cards[0] == "Ah", "Ah template does not match as Ad");
    CHECK(!s.seats[4].in_hand && s.seats[4].cards.empty(),
          "empty card id is not a dealt card");
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

    // --- preflop frame ---------------------------------------------------------
    cv::Mat preflop = make_background(shot_w, shot_h, 8);
    anchor.copyTo(preflop(cv::Rect(anchor_at.x, anchor_at.y, anchor.cols, anchor.rows)));
    card_ah.copyTo(preflop(cv::Rect(anchor_at.x + 60, anchor_at.y + 300, card_ah.cols, card_ah.rows)));
    card_2c.copyTo(preflop(cv::Rect(anchor_at.x + 110, anchor_at.y + 300, card_2c.cols, card_2c.rows)));
    auto pre = scraper.scrape(preflop);
    CHECK(pre.has_value() && pre->board.empty(), "preflop board is empty");
    if (pre && pre->game_stage)
      CHECK(*pre->game_stage == "PreFlop", "no board cards -> PreFlop");
    else
      CHECK(false, "no board cards -> PreFlop");
    CHECK(pre.has_value() && pre->seats[0].cards.size() == 2 && pre->seats[0].cards[0] == "Ah" &&
              pre->seats[0].cards[1] == "2c",
          "preflop hole cards still Ah 2c");

    // --- state validation (port of the Python researcher's validators) --------
    // The live parsed state is a valid river-of-3 hand: it must report clean.
    auto vrep = glance::validate_table_state(s);
    CHECK(vrep.valid, "parsed state passes state validation");
    CHECK(vrep.error_count == 0, "parsed state has zero validation errors");
    CHECK(j.contains("validation") && j["validation"]["valid"] == true,
          "state JSON carries a clean validation block");
    CHECK(j["validation"].contains("errors") && j["validation"].contains("warnings"),
          "validation block has errors+warnings arrays");
  }

  // --- HTTP round-trip (the 413 regression) -----------------------------------
  // A multi-MB screenshot must survive POST /capture. httplib enforces a
  // SEPARATE, tiny (8 KB default) budget for bodies labeled
  // application/x-www-form-urlencoded — the content type curl --data-binary
  // sends by default — so a naive client once got a silent 413 on a 1.3 MB
  // screenshot even though the generic payload limit wasn't near it. The
  // #define in CMakeLists raises that limit to match the 16 MB runtime cap set
  // in server/main.cpp; POST with the same curl-style content type so a
  // removed define fails this check.
  {
    std::printf("selftest: http round-trip\n");
    std::vector<unsigned char> http_buf;
    cv::imencode(".png", shot, http_buf);
    glance::TableScraper http_scraper;
    if (!http_scraper.load_mapping((base / "mapping.json").string())) {
      std::printf("  FAIL: http round-trip: mapping loads for the test server\n");
      ++failures;
    } else {
      glance::ScreenshotService http_service(&http_scraper);
      httplib::Server srv;
      srv.Post("/capture", [&http_service](const httplib::Request& req, httplib::Response& res) {
        std::vector<unsigned char> img(req.body.begin(), req.body.end());
        if (!http_service.update(img)) {
          nlohmann::json j;
          j["error"] = "could not decode image or table not found";
          res.status = 422;
          res.set_content(j.dump(), "application/json");
          return;
        }
        res.set_content(http_service.state_json().dump(), "application/json");
      });
      int port = srv.bind_to_any_port("127.0.0.1");
      CHECK(port > 0, "test server binds an ephemeral port");
      if (port > 0) {
        // listen_after_bind() runs the accept loop on its thread; serve on a
        // dedicated one so the test thread can drive the client.
        std::thread serve([&srv]() { srv.listen_after_bind(); });
        srv.wait_until_ready();
        httplib::Client cli("127.0.0.1", port);
        httplib::Headers headers;
        headers.emplace("Content-Type", "application/x-www-form-urlencoded");
        headers.emplace("Expect", "100-continue");
        std::string req_body(http_buf.begin(), http_buf.end());
        auto res = cli.Post("/capture", headers, req_body, "application/x-www-form-urlencoded");
        CHECK(res && res->status == 200,
              "screenshot >8 KB is accepted as application/x-www-form-urlencoded (413 regression)");
        if (res && res->status == 200) {
          nlohmann::json rj = nlohmann::json::parse(res->body);
          CHECK(rj.contains("stage") && rj["stage"] == "Flop",
                "POST /capture returns the parsed state over HTTP");
          CHECK(rj.contains("validation") && rj["validation"]["valid"] == true,
                "HTTP state carries a clean validation block");
        }
        srv.stop();
        serve.join();
      }
    }
  }

  // --- HTTP round-trip: the control surface ------------------------------------
  // The SAME ControlRoutes the server registers, installed on an ephemeral
  // in-process server and driven with a fake platform backend: /capture must
  // record the frame as the input-space reference (the externally_parsed seam),
  // /click /key /sequence must work through HTTP, and /health must carry the
  // control info. A server without the X11 backend still serves every one of
  // these (the null backend records nothing, returns nothing).
  {
    std::printf("selftest: control http round-trip\n");
    std::vector<unsigned char> http_buf;
    cv::imencode(".png", shot, http_buf);
    glance::TableScraper ctrl_scraper;
    if (!ctrl_scraper.load_mapping((base / "mapping.json").string())) {
      std::printf("  FAIL: control http: mapping loads for the test server\n");
      ++failures;
    } else {
      glance::ScreenshotService ctrl_service(&ctrl_scraper);
      auto fake_screen = std::make_shared<FakeScreen>();
      fake_screen->region = shot;
      auto fake_input = std::make_shared<FakeInput>();
      auto backend = std::make_shared<glance::control::Backend>();
      backend->name = "fake";
      backend->screen = fake_screen;
      backend->input = fake_input;
      glance::ControlService ctrl(&ctrl_scraper, backend);
      glance::ControlRoutes routes(&ctrl_service, &ctrl_scraper, &ctrl);

      httplib::Server srv;
      srv.set_payload_max_length(16u * 1024 * 1024);
      routes.install(srv);
      srv.Get("/state", [&ctrl_service](const httplib::Request&, httplib::Response& res) {
        if (!ctrl_service.has_state()) {
          nlohmann::json j;
          j["error"] = "no state yet, POST a screenshot to /capture first";
          res.status = 404;
          res.set_content(j.dump(), "application/json");
          return;
        }
        res.set_content(ctrl_service.state_json().dump(), "application/json");
      });
      int port = srv.bind_to_any_port("127.0.0.1");
      CHECK(port > 0, "control test server binds an ephemeral port");
      if (port > 0) {
        std::thread serve([&srv]() { srv.listen_after_bind(); });
        srv.wait_until_ready();
        httplib::Client cli("127.0.0.1", port);
        // /health carries the control surface's state up front.
        auto hres = cli.Get("/health");
        CHECK(hres && hres->status == 200 && nlohmann::json::parse(hres->body)["status"] == "ok",
              "GET /health is ok");
        if (hres && hres->status == 200) {
          auto hj = nlohmann::json::parse(hres->body);
          CHECK(hj.contains("control") && hj["control"]["backend"] == "fake",
                "/health reports the control backend name");
        }
        // /capture: the parsed frame becomes the input-space reference.
        std::string body(http_buf.begin(), http_buf.end());
        auto cres = cli.Post("/capture", body, "application/x-www-form-urlencoded");
        CHECK(cres && cres->status == 200, "POST /capture returns the parsed state");
        auto gres = cli.Post("/grab", "{}", "application/json");
        CHECK(gres && gres->status == 200 &&
                  nlohmann::json::parse(gres->body)["table_found"] == true,
              "POST /grab (default: the mapping's window_title) finds the table");
        // A grab that mis-locates the window still parses the frame it gets but
        // the anchor is offset — the table is found in frame space only; the
        // re-base for raw clicks tracks the window's new origin.
        auto gres2 = cli.Post("/grab",
                              R"({"region": {"x": 40, "y": 40, "w": )" + std::to_string(shot_w) +
                              R"(, "h": )" + std::to_string(shot_h) + R"(}})", "application/json");
        CHECK(gres2 && gres2->status == 200, "POST /grab with an explicit region is 200");
        // /click: a named action from the mapping's "actions" section. The
        // resolved point is in the last FRAME's space (the region grab at
        // (40,40)), so the re-base applies to it exactly like raw coords.
        nlohmann::json click_req;
        click_req["action"] = "call";
        auto c1 = cli.Post("/click", click_req.dump(), "application/json");
        CHECK(c1 && c1->status == 200, "POST /click with a named action is 200");
        if (c1 && c1->status == 200) {
          auto dj = nlohmann::json::parse(c1->body);
          CHECK(dj["kind"] == "button" && dj["x"] == anchor_at.x + 290 + 40 &&
                    dj["y"] == anchor_at.y + 360 + 40,
                "/click resolves the named action, re-based by the frame origin");
        }
        // /click: raw coordinates in the last frame's space.
        nlohmann::json raw;
        raw["click"] = {{"x", 10}, {"y", 20}};
        auto c2 = cli.Post("/click", raw.dump(), "application/json");
        CHECK(c2 && c2->status == 200, "POST /click with raw coordinates is 200");
        if (c2 && c2->status == 200) {
          auto dj = nlohmann::json::parse(c2->body);
          CHECK(dj["kind"] == "raw", "/click reports the click kind");
        }
        // /click: an unknown action is a 422, not a crash.
        nlohmann::json bad;
        bad["action"] = "no_such_action";
        auto c3 = cli.Post("/click", bad.dump(), "application/json");
        CHECK(c3 && c3->status == 422, "POST /click with an unknown action is 422");
        // /key: a key press and a typed string both land.
        nlohmann::json k1;
        k1["key"] = "Return";
        auto kr1 = cli.Post("/key", k1.dump(), "application/json");
        CHECK(kr1 && kr1->status == 200, "POST /key (one keysym) is 200");
        nlohmann::json k2;
        k2["type"] = "200";
        auto kr2 = cli.Post("/key", k2.dump(), "application/json");
        CHECK(kr2 && kr2->status == 200, "POST /key (typed text) is 200");
        // /sequence: mixed steps, each reported.
        nlohmann::json seq = nlohmann::json::array();
        seq.push_back({{"action", std::string("call")}});
        seq.push_back({{"key", std::string("Return")}});
        seq.push_back({{"action", std::string("bogus")}});
        auto s1 = cli.Post("/sequence", seq.dump(), "application/json");
        CHECK(s1 && s1->status == 200, "POST /sequence is 200");
        if (s1 && s1->status == 200) {
          auto sj = nlohmann::json::parse(s1->body);
          CHECK(sj["steps"].size() == 3, "/sequence reports every step");
          CHECK(sj["steps"][0]["ok"] && sj["steps"][1]["ok"] && !sj["steps"][2]["ok"],
                "each /sequence step is reported on its own merits");
        }
        // /sequence: a non-array body is rejected.
        auto s2 = cli.Post("/sequence", "42", "application/json");
        CHECK(s2 && s2->status == 400, "POST /sequence rejects a non-array body");
        // A bad /click body is a 400.
        auto c4 = cli.Post("/click", "not json", "application/json");
        CHECK(c4 && c4->status == 400, "POST /click rejects a malformed body");
        srv.stop();
        serve.join();
      }
    }
  }

  // --- validate_table_state: unit checks on hand-built states ------------------
  // Impossible states must be caught; a legal pocket pair must NOT be.
  {
    std::printf("selftest: state validation unit checks\n");
    auto code_of = [](const glance::ValidationReport& r, const std::string& want) {
      for (const auto& i : r.issues)
        if (i.code == want) return true;
      return false;
    };

    glance::TableState dup;
    dup.seats.resize(2);
    dup.seats[0].cards = {"Ah", "Ah"};               // identical face twice
    dup.seats[0].index = 0;
    auto vd = glance::validate_table_state(dup);
    CHECK(!vd.valid && code_of(vd, "DUPLICATE_CARD"),
          "duplicate identical card is an error");

    glance::TableState pair;
    pair.seats.resize(1);
    pair.seats[0].index = 0;
    pair.seats[0].cards = {"Ah", "As"};             // pocket pair: distinct faces
    auto vp = glance::validate_table_state(pair);
    CHECK(vp.valid && !code_of(vp, "DUPLICATE_CARD"),
          "a pocket pair (different suits) is legal");

    glance::TableState gap;
    gap.seats.resize(1);
    gap.seats[0].index = 0;
    gap.seats[0].cards = {"Ah", "Ks"};
    gap.board = {"7d", "", "Qh", "2c", "Js"};      // hole in the middle
    gap.game_stage = "River";
    auto vg = glance::validate_table_state(gap);
    CHECK(!vg.valid && code_of(vg, "BOARD_GAP"), "a board gap is an error");

    glance::TableState mismatch;
    mismatch.seats.resize(1);
    mismatch.seats[0].index = 0;
    mismatch.seats[0].cards = {"Ah", "Ks"};
    mismatch.board = {"7d", "Ks", "Qh"};           // 3 cards ...
    mismatch.game_stage = "Turn";                  // ... but says 4
    auto vm = glance::validate_table_state(mismatch);
    CHECK(!vm.valid && code_of(vm, "STAGE_BOARD_MISMATCH"),
          "stage/board-count mismatch is an error");

    glance::TableState neg;
    neg.seats.resize(1);
    neg.seats[0].index = 0;
    neg.seats[0].stack = -50.0;                    // not the -1 "unread" sentinel
    neg.total_pot = -1.0;
    auto vn = glance::validate_table_state(neg);
    CHECK(!vn.valid && code_of(vn, "NEGATIVE_AMOUNT") && code_of(vn, "NEGATIVE_STACK"),
          "negative amounts are errors");

    glance::TableState clean;
    clean.seats.resize(1);
    clean.seats[0].index = 0;
    clean.seats[0].cards = {"Ah", "Ks"};
    clean.board = {"7d", "Qh", "2c"};
    clean.game_stage = "Flop";
    clean.total_pot = 0.0;
    auto vc = glance::validate_table_state(clean);
    CHECK(vc.valid && vc.error_count == 0, "a consistent state is valid");
  }

  // --- OCR number parsing (pure text; runs without tesseract) -------------------
  // The comma/thousands handling that was inline in ocr_number is extracted and
  // unit-tested here: "1,200" must be read as 1200, not 1.2.
  auto expect_num = [](const char* what, const std::string& text, double expected) {
    auto v = glance::parse_ocr_number_text(text);
    bool ok = v && std::fabs(*v - expected) < 1e-9;
    std::printf("  %s: ocr text %s\n", ok ? "ok" : "FAIL", what);
    if (!ok) ++failures;
  };
  expect_num("243.50", "243.50", 243.5);
  expect_num("$1,200", "$1,200", 1200.0);
  expect_num("1,200.50", "1,200.50", 1200.5);
  expect_num("1.200,50", "1.200,50", 1200.5);
  expect_num("12,5", "12,5", 12.5);
  expect_num("1200B", "1200B", 1200.0);
  CHECK(!glance::parse_ocr_number_text("-5").has_value(), "ocr text rejects a minus");
  CHECK(!glance::parse_ocr_number_text("abc").has_value(), "ocr text rejects non-numeric");
  CHECK(!glance::parse_ocr_number_text("1.2.3").has_value(), "ocr text rejects an extra dot");

  // --- control: named-action resolution ----------------------------------------
  // The mapping's "actions" section maps names to "button:"/"stack:" targets;
  // resolve_action turns one into the target rectangle's centre in screen
  // space, given the anchored table origin. Unknown actions, unknown target
  // names and malformed target schemes all resolve to nullopt; an unanchored
  // table cannot resolve to ANY point (no click may land on a guess).
  {
    std::printf("selftest: named-action resolution\n");
    const cv::Point origin(anchor_at);
    auto res = [&](const char* name) { return glance::control::resolve_action(scraper.mapping(), origin, true, name); };
    auto p = res("call");
    CHECK(p && p->kind == "button" && p->x == origin.x + 290 && p->y == origin.y + 360,
          "action 'call' resolves to the call button's centre");
    p = res("pot_label");
    CHECK(p && p->kind == "stack" && p->x == origin.x + 480 && p->y == origin.y + 40,
          "action 'pot_label' resolves to the pot stack's centre");
    p = res("fold");
    CHECK(!p, "action with an unknown target name ('fold' -> button:fold) resolves to nullopt");
    p = res("bogus");
    CHECK(!p, "malformed target scheme ('bogus' -> weird:whatever) resolves to nullopt");
    p = res("no_such_action");
    CHECK(!p, "unknown action name resolves to nullopt");
    p = glance::control::resolve_action(scraper.mapping(), origin, false, "call");
    CHECK(!p, "an unanchored table resolves no action (a click must not land on a guess)");
  }

  // --- control: service semantics on a fake platform ----------------------------
  // The SAME ControlService the server runs, driven with a fake Screen/Input:
  // input-space conversion (frame-relative -> screen-absolute), the input
  // source bookkeeping, and the null-safe failure paths.
  {
    std::printf("selftest: control service on a fake platform\n");
    auto fake_screen = std::make_shared<FakeScreen>();
    fake_screen->region = shot;  // the composed screenshot (the anchor IS in it)
    auto fake_input = std::make_shared<FakeInput>();
    auto backend = std::make_shared<glance::control::Backend>();
    backend->name = "fake";
    backend->screen = fake_screen;
    backend->input = fake_input;
    glance::TableScraper cscraper;
    CHECK(cscraper.load_mapping((base / "mapping.json").string()), "control scraper loads the mapping");
    glance::ControlService ctrl(&cscraper, backend);
    CHECK(ctrl.backend_name() == "fake", "backend name is reported");

    // Region grab: the frame is the whole desktop content at (120,80); the
    // grab's own origin is what client coordinates are measured in, so a raw
    // click at (0,0) of that frame lands on the frame's screen origin.
    bool found = false;
    std::string err;
    CHECK(ctrl.grab_region(120, 80, shot_w, shot_h, found, &err), "region grab parses the frame");
    CHECK(ctrl.table_found() && found, "the table anchor is found in the grabbed frame");
    {
      nlohmann::json detail;
      glance::ControlService::ClickRequest cr;
      cr.use_coords = true;
      cr.x = 0;
      cr.y = 0;
      CHECK(ctrl.click(cr, detail, &err), "a raw click resolves against the last frame");
      CHECK(detail["x"] == 120 && detail["y"] == 80,
            "frame coordinates (0,0) arrive screen-absolute (120,80)");
    }
    // Region offset is frame-relative, NOT window-relative: a second grab
    // from a different position re-bases the click space.
    CHECK(ctrl.grab_region(40, 40, shot_w, shot_h, found, &err), "second region grab re-bases the input space");
    {
      nlohmann::json detail;
      glance::ControlService::ClickRequest cr;
      cr.use_coords = true;
      cr.x = 10;
      cr.y = 20;
      CHECK(ctrl.click(cr, detail, &err), "a raw click resolves after re-grab");
      CHECK(detail["x"] == 50 && detail["y"] == 60,
            "click coordinates are offset by the NEW grab's origin");
    }
    // Named action: resolve_action returns a point in the LAST FRAME's space
    // (its anchor is the frame-relative table origin), so it is re-based with
    // the frame origin like any raw coordinate — that is what lands the click
    // on the physical button. The last grab was at (40,40).
    {
      nlohmann::json detail;
      glance::ControlService::ClickRequest cr;
      cr.target = "call";
      CHECK(ctrl.click(cr, detail, &err), "a named action click resolves");
      CHECK(detail["kind"] == "button" && detail["x"] == anchor_at.x + 290 + 40 &&
                detail["y"] == anchor_at.y + 360 + 40,
            "the named action clicks the button centre, re-based by the frame origin");
      CHECK(detail.value("action", std::string()) == "call", "the action name is reported for audit");
    }
    // A frame with no table: raw clicks still work (client knows the frame),
    // named actions do not.
    {
      glance::TableScraper nscraper;
      CHECK(nscraper.load_mapping((base / "mapping.json").string()), "control scraper #2 loads");
      auto b2 = std::make_shared<glance::control::Backend>();
      b2->name = "fake";
      b2->screen = fake_screen;
      b2->input = fake_input;
      glance::ControlService nctrl(&nscraper, b2);
      nctrl.externally_parsed(false, cv::Point(0, 0));
      CHECK(!nctrl.table_found(), "a frame without the anchor reports the table as not found");
      nlohmann::json d2;
      glance::ControlService::ClickRequest c2;
      c2.target = "call";
      CHECK(!nctrl.click(c2, d2, &err), "a named action refuses when the table is not anchored");
      CHECK(err.find("not anchored") != std::string::npos, "the refusal names the missing anchor");
    }
    // Keys and text go straight to the platform input.
    {
      glance::ControlService::KeyRequest kr;
      kr.keysym = "Return";
      CHECK(ctrl.key(kr, &err), "a key press reaches the platform input");
      kr.keysym = "";
      kr.text = "200";
      CHECK(ctrl.key(kr, &err), "typed text reaches the platform input");
      CHECK(fake_input->keys.back() == "Return" && fake_input->typed == "200",
            "the fake input recorded the key and the typed text");
    }
    // A /sequence mixes steps; every step is reported even when one fails.
    {
      nlohmann::json steps = nlohmann::json::array();
      steps.push_back({{"action", std::string("call")}});
      steps.push_back({{"key", std::string("Return")}});
      steps.push_back({{"action", std::string("bogus")}});  // malformed -> reported, not fatal
      auto results = ctrl.sequence(steps);
      CHECK(results.size() == 3, "a sequence reports every step");
      CHECK(results[0].ok && results[1].ok && !results[2].ok,
            "each sequence step succeeds or fails independently");
    }
    // The /capture seam: a client-POSTed frame is the input-space reference,
    // used as given (no frame-origin offset applied).
    {
      glance::TableScraper escraper;
      CHECK(escraper.load_mapping((base / "mapping.json").string()), "control scraper #3 loads");
      auto b3 = std::make_shared<glance::control::Backend>();
      b3->name = "fake";
      b3->screen = std::make_shared<FakeScreen>();
      b3->input = std::make_shared<FakeInput>();
      glance::ControlService ectrl(&escraper, b3);
      ectrl.externally_parsed(true, cv::Point(anchor_at));
      nlohmann::json d4;
      glance::ControlService::ClickRequest c4;
      c4.use_coords = true;
      c4.x = 5;
      c4.y = 6;
      CHECK(ectrl.click(c4, d4, &err), "a raw click resolves after an externally-parsed frame");
      CHECK(d4["x"] == 5 && d4["y"] == 6,
            "externally-POSTed frames are used as given (no re-base)");
    }
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
