// glance-cardvision: drive the card-vision recognizer (core/card_vision.h)
// from the command line.
//
//   glance-cardvision read <card.png> --suits DIR [--ranks DIR]
//                     [--profile simulator|calibration] [--slot NAME]
//       print the full recognition JSON for one card crop.
//
//   glance-cardvision eval <dataset-dir> --suits DIR [--ranks DIR] [--profile P]
//                     [--json OUT] [--min-card-accuracy X] [--max-incorrect N]
//                     [--min-empty-rejection X] [--min-suit-accuracy X]
//       recognize every labelled crop of a research validation dataset
//       (research/test_assets/validation/...: <dir>/expected.json + <dir>/cards/)
//       and print the same summary the Python reports carried. With any
//       --min/--max gate the exit status is 1 when a gate fails (ctest).
//
//   glance-cardvision harvest <dataset-dir> <out-dir> [--filter SUBSTR]
//       write one normalized rank-glyph template per labelled crop
//       (<rank>_<file-stem>.png), from the tight rank box recognition uses.
//
// Two expected.json shapes are understood: {"records": [{"file", "occupied",
// "rank", "suit"}]} (generated datasets) and {"cards": {"<slot>": {"rank",
// "suit", "occupied"?}}} with cards/<slot>.png (street / calibration samples).

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <map>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>
#include <opencv2/imgcodecs.hpp>

#include "card_vision.h"
#include "ocr.h"

namespace fs = std::filesystem;
using glance::vision::CardReading;
using glance::vision::CardRecognizer;
using glance::vision::CardVisionConfig;

namespace {

struct Args {
  std::vector<std::string> pos;
  std::map<std::string, std::string> opt;
  std::string get(const std::string& k, const std::string& d = "") const {
    auto it = opt.find(k);
    return it == opt.end() ? d : it->second;
  }
  bool has(const std::string& k) const { return opt.count(k) > 0; }
};

Args parse(int argc, char** argv) {
  Args a;
  for (int i = 2; i < argc; ++i) {
    std::string s = argv[i];
    if (s.rfind("--", 0) == 0 && i + 1 < argc) {
      a.opt[s.substr(2)] = argv[++i];
    } else {
      a.pos.push_back(s);
    }
  }
  return a;
}

int usage() {
  std::fprintf(stderr,
               "usage:\n"
               "  glance-cardvision read <card.png> --suits DIR [--ranks DIR] [--profile P] [--slot S]\n"
               "  glance-cardvision eval <dataset-dir> --suits DIR [--ranks DIR] [--profile P] [--json OUT]\n"
               "                    [--min-card-accuracy X] [--min-suit-accuracy X] [--max-incorrect N]\n"
               "                    [--min-empty-rejection X]\n"
               "  glance-cardvision harvest <dataset-dir> <out-dir> [--filter SUBSTR]\n");
  return 2;
}

struct Sample {
  std::string file;  // path to the crop
  std::string slot;  // slot name for slot-specific regions ("" for records)
  std::string variant;
  bool occupied = true;
  std::string rank, suit;
};

bool load_dataset(const fs::path& dir, std::vector<Sample>& out, std::string& err) {
  std::ifstream in(dir / "expected.json");
  if (!in) {
    err = "no expected.json in " + dir.string();
    return false;
  }
  nlohmann::json j;
  try {
    in >> j;
  } catch (const std::exception& e) {
    err = std::string("expected.json: ") + e.what();
    return false;
  }
  auto str = [](const nlohmann::json& v, const char* k) {
    return v.contains(k) && v[k].is_string() ? v[k].get<std::string>() : std::string();
  };
  if (j.contains("records")) {
    for (const auto& r : j["records"]) {
      Sample s;
      s.file = (dir / "cards" / r.value("file", "")).string();
      s.variant = str(r, "variant");
      s.occupied = r.value("occupied", true);
      s.rank = str(r, "rank");
      s.suit = str(r, "suit");
      out.push_back(s);
    }
  } else if (j.contains("cards")) {
    for (const auto& [slot, c] : j["cards"].items()) {
      Sample s;
      s.file = (dir / "cards" / (slot + ".png")).string();
      s.slot = slot;
      s.variant = slot.rfind("hero", 0) == 0 ? "hero" : "board";
      s.occupied = c.value("occupied", true);
      s.rank = str(c, "rank");
      s.suit = str(c, "suit");
      out.push_back(s);
    }
  } else {
    err = "expected.json has neither \"records\" nor \"cards\"";
    return false;
  }
  return true;
}

bool make_recognizer(const Args& a, CardRecognizer& rec) {
  CardVisionConfig cfg;
  cfg.profile = a.get("profile", "simulator");
  if (a.has("rank-threshold")) cfg.rank_threshold = std::atof(a.get("rank-threshold").c_str());
  if (a.has("rank-margin")) cfg.rank_margin = std::atof(a.get("rank-margin").c_str());
  if (!rec.load(cfg, a.get("suits"), a.get("ranks"))) {
    std::fprintf(stderr, "%s\n", rec.error().c_str());
    return false;
  }
  return true;
}

int cmd_read(const Args& a) {
  if (a.pos.size() != 1 || !a.has("suits")) return usage();
  CardRecognizer rec;
  if (!make_recognizer(a, rec)) return 1;
  cv::Mat img = cv::imread(a.pos[0], cv::IMREAD_COLOR);
  if (img.empty()) {
    std::fprintf(stderr, "cannot read %s\n", a.pos[0].c_str());
    return 1;
  }
  std::printf("%s\n", rec.recognize(img, a.get("slot")).to_json().dump(2).c_str());
  return 0;
}

struct Tally {
  int total = 0, occupied = 0, empty = 0;
  int correct_ranks = 0, correct_suits = 0, correct_cards = 0;
  int rejected = 0, incorrect_accepted = 0;
  int empty_rejected = 0, empty_false_positive = 0;
  int skipped = 0;
  nlohmann::json to_json() const {
    auto ratio = [](int a, int b) { return b ? static_cast<double>(a) / b : 0.0; };
    return {{"total_slots", total},
            {"occupied_slots", occupied},
            {"empty_slots", empty},
            {"correct_ranks", correct_ranks},
            {"correct_suits", correct_suits},
            {"correct_cards", correct_cards},
            {"rejected_cards", rejected},
            {"incorrect_accepted_cards", incorrect_accepted},
            {"empty_slots_rejected", empty_rejected},
            {"empty_slots_false_positive", empty_false_positive},
            {"recognition_skipped", skipped},
            {"rank_accuracy", ratio(correct_ranks, occupied)},
            {"suit_accuracy", ratio(correct_suits, occupied)},
            {"card_accuracy", ratio(correct_cards, occupied)},
            {"empty_rejection_rate", empty ? ratio(empty_rejected, empty) : 1.0},
            {"overall_slot_accuracy", ratio(correct_cards + empty_rejected, total)}};
  }
};

int cmd_eval(const Args& a) {
  if (a.pos.size() != 1 || !a.has("suits")) return usage();
  std::vector<Sample> samples;
  std::string err;
  if (!load_dataset(a.pos[0], samples, err)) {
    std::fprintf(stderr, "%s\n", err.c_str());
    return 1;
  }
  CardRecognizer rec;
  if (!make_recognizer(a, rec)) return 1;

  Tally all;
  std::map<std::string, Tally> by_variant;
  nlohmann::json failures = nlohmann::json::array();
  nlohmann::json readings = nlohmann::json::array();
  std::map<std::string, int> verification;
  const auto t0 = std::chrono::steady_clock::now();
  for (const auto& s : samples) {
    cv::Mat img = cv::imread(s.file, cv::IMREAD_COLOR);
    CardReading r;
    if (!img.empty()) r = rec.recognize(img, s.slot);
    verification[r.rank_verification]++;
    for (Tally* t : {&all, &by_variant[s.variant]}) {
      t->total++;
      if (r.skipped) t->skipped++;
      if (!s.occupied) {
        t->empty++;
        if (r.recognized())
          t->empty_false_positive++;
        else
          t->empty_rejected++;
        continue;
      }
      t->occupied++;
      const bool rank_ok = r.rank.rank && *r.rank.rank == s.rank;
      const bool suit_ok = r.suit.suit && *r.suit.suit == s.suit;
      if (rank_ok) t->correct_ranks++;
      if (suit_ok) t->correct_suits++;
      if (rank_ok && suit_ok) t->correct_cards++;
      if (!r.recognized())
        t->rejected++;
      else if (!(rank_ok && suit_ok))
        t->incorrect_accepted++;
    }
    readings.push_back({{"file", fs::path(s.file).filename().string()},
                        {"expected_rank", s.rank},
                        {"expected_suit", s.suit},
                        {"occupied", s.occupied},
                        {"reading", r.to_json()}});
    const bool ok = s.occupied ? (r.rank.rank && *r.rank.rank == s.rank && r.suit.suit &&
                                  *r.suit.suit == s.suit)
                               : !r.recognized();
    if (!ok) {
      failures.push_back({{"file", fs::path(s.file).filename().string()},
                          {"expected", s.occupied ? s.rank + " " + s.suit : std::string("empty")},
                          {"reading", r.to_json()}});
    }
  }
  const double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();

  nlohmann::json report;
  report["dataset"] = fs::path(a.pos[0]).filename().string();
  report["profile"] = rec.config().profile;
  report["suit_templates"] = rec.suit_template_count();
  report["rank_templates"] = rec.rank_template_count();
  report["ocr_available"] = glance::ocr_available();
  report["summary"] = all.to_json();
  report["summary"]["total_time_seconds"] = secs;
  report["summary"]["average_time_per_image_seconds"] = samples.empty() ? 0.0 : secs / samples.size();
  for (const auto& [v, t] : by_variant) report["summary_by_variant"][v] = t.to_json();
  report["rank_verification"] = verification;
  report["failures"] = failures;
  report["readings"] = readings;

  const nlohmann::json& sm = report["summary"];
  std::printf("%s [%s]: %d slots (%d occupied, %d empty) in %.3fs\n", report["dataset"].get<std::string>().c_str(),
              rec.config().profile.c_str(), all.total, all.occupied, all.empty, secs);
  std::printf("  card %.4f  rank %.4f  suit %.4f  rejected %d  incorrect-accepted %d  empty-rejection %.4f\n",
              sm["card_accuracy"].get<double>(), sm["rank_accuracy"].get<double>(),
              sm["suit_accuracy"].get<double>(), all.rejected, all.incorrect_accepted,
              sm["empty_rejection_rate"].get<double>());
  for (const auto& [v, t] : by_variant) {
    auto tj = t.to_json();
    std::printf("    %-22s card %.4f  rank %.4f  suit %.4f  (%d)\n", v.c_str(), tj["card_accuracy"].get<double>(),
                tj["rank_accuracy"].get<double>(), tj["suit_accuracy"].get<double>(), t.total);
  }
  for (const auto& f : failures) {
    const auto& rd = f["reading"];
    std::printf("  miss %-34s want %-12s got %s/%s (rank %.3f m%.3f %s, suit %.3f m%.3f)\n",
                f["file"].get<std::string>().c_str(), f["expected"].get<std::string>().c_str(),
                rd["rank"].is_null() ? "-" : rd["rank"].get<std::string>().c_str(),
                rd["suit"].is_null() ? "-" : rd["suit"].get<std::string>().c_str(),
                rd["rank_confidence"].get<double>(), rd["rank_margin"].get<double>(),
                rd["rank_verification"].get<std::string>().c_str(), rd["suit_confidence"].get<double>(),
                rd["suit_margin"].get<double>());
  }
  if (a.has("json")) {
    std::ofstream(a.get("json")) << report.dump(2) << "\n";
  }

  bool pass = true;
  auto gate_min = [&](const char* opt, const char* key) {
    if (!a.has(opt)) return;
    const double want = std::atof(a.get(opt).c_str());
    const double got = sm[key].get<double>();
    if (got + 1e-12 < want) {
      std::printf("  GATE FAIL: %s %.4f < %.4f\n", key, got, want);
      pass = false;
    }
  };
  gate_min("min-card-accuracy", "card_accuracy");
  gate_min("min-suit-accuracy", "suit_accuracy");
  gate_min("min-empty-rejection", "empty_rejection_rate");
  if (a.has("max-incorrect") && all.incorrect_accepted + all.empty_false_positive > std::atoi(a.get("max-incorrect").c_str())) {
    std::printf("  GATE FAIL: incorrect accepted %d > %s\n", all.incorrect_accepted + all.empty_false_positive,
                a.get("max-incorrect").c_str());
    pass = false;
  }
  return pass ? 0 : 1;
}

int cmd_harvest(const Args& a) {
  if (a.pos.size() != 2) return usage();
  std::vector<Sample> samples;
  std::string err;
  if (!load_dataset(a.pos[0], samples, err)) {
    std::fprintf(stderr, "%s\n", err.c_str());
    return 1;
  }
  fs::create_directories(a.pos[1]);
  const std::string filter = a.get("filter");
  int n = 0;
  for (const auto& s : samples) {
    if (!s.occupied || s.rank.empty()) continue;
    if (!filter.empty() && fs::path(s.file).filename().string().find(filter) == std::string::npos) continue;
    cv::Mat img = cv::imread(s.file, cv::IMREAD_COLOR);
    if (img.empty()) continue;
    auto regions = glance::vision::rank_glyph_regions(img);
    if (regions.empty()) continue;
    cv::Mat g = glance::vision::normalize_rank_glyph(regions[0]);
    if (g.empty()) {
      std::fprintf(stderr, "no glyph in %s\n", s.file.c_str());
      continue;
    }
    const fs::path out = fs::path(a.pos[1]) / (s.rank + "_" + fs::path(s.file).stem().string() + ".png");
    if (cv::imwrite(out.string(), g)) ++n;
  }
  std::printf("harvested %d rank templates into %s\n", n, a.pos[1].c_str());
  return n > 0 ? 0 : 1;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) return usage();
  const std::string cmd = argv[1];
  Args a = parse(argc, argv);
  if (cmd == "read") return cmd_read(a);
  if (cmd == "eval") return cmd_eval(a);
  if (cmd == "harvest") return cmd_harvest(a);
  return usage();
}
