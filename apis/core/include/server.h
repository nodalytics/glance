#pragma once

#include <memory>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
#include <opencv2/core.hpp>

namespace poker {

class TableScraper;

// A stateful screenshot service: it holds the last screenshot and the table
// state parsed from it. Callers POST a screenshot (PNG/JPEG bytes) via the
// server and read back the parsed state.
class ScreenshotService {
 public:
  explicit ScreenshotService(TableScraper* scraper);
  // Accept raw image bytes, decode, and (re)parse the table state.
  // Returns false when the bytes do not decode or the table is not found.
  bool update(const std::vector<unsigned char>& data);
  bool has_state() const { return has_state_; }
  const nlohmann::json& state_json() const { return state_json_; }
  const cv::Mat& last_frame() const { return frame_; }

 private:
  TableScraper* scraper_;
  cv::Mat frame_;
  nlohmann::json state_json_;
  bool has_state_ = false;
};

}  // namespace poker
