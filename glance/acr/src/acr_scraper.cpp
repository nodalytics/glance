#include "acr_scraper.h"

#include "scraper.h"

namespace glance::acr {

bool AcrScraper::load_mapping(const std::string& mapping_json_path) {
  return scraper_.load_mapping(mapping_json_path);
}

std::optional<TableState> AcrScraper::scrape(const cv::Mat& screenshot) {
  return scraper_.scrape(screenshot);
}

nlohmann::json AcrScraper::scrape_json(const cv::Mat& screenshot) {
  auto state = scraper_.scrape(screenshot);
  if (!state) {
    nlohmann::json j;
    j["error"] = "table not found";
    return j;
  }
  return to_json(*state);
}

}  // namespace glance::acr
