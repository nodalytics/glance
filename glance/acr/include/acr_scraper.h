#pragma once

#include <string>
#include <optional>
#include <nlohmann/json.hpp>
#include <opencv2/core.hpp>

#include "scraper.h"

namespace glance::acr {

// ACR-specific table scraper for https://www.acrpoker.eu/.
//
// Wraps the generic core TableScraper with the ACR table mapping, which the
// caller must provide (a JSON file describing the ACR 6-max table skin: the
// top-left anchor, card/button/number search areas). ACR is a web client, so
// the "screenshot" is a grab of the poker window — exactly the same pixel
// data model as a desktop grab.
class AcrScraper {
 public:
  // Load the ACR table mapping JSON. Paths in the mapping are resolved
  // relative to the mapping file's directory. Returns false on error (see
  // error()).
  bool load_mapping(const std::string& mapping_json_path);
  const std::string& error() const { return scraper_.error(); }

  // Parse a screenshot of the ACR table into a TableState.
  std::optional<TableState> scrape(const cv::Mat& screenshot);
  nlohmann::json scrape_json(const cv::Mat& screenshot);

  bool table_found() const { return scraper_.table_found(); }
  // The wrapped core scraper, for callers that need to drive it directly
  // (e.g. the ScreenshotService around the HTTP API).
  glance::TableScraper* core_scraper() { return &scraper_; }

 private:
  glance::TableScraper scraper_;
};

}  // namespace glance::acr
