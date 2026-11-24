#include "server.h"

#include <opencv2/imgcodecs.hpp>

#include "scraper.h"

namespace poker {

ScreenshotService::ScreenshotService(TableScraper* scraper) : scraper_(scraper) {}

bool ScreenshotService::update(const std::vector<unsigned char>& data) {
  if (data.empty() || !scraper_) return false;
  cv::Mat img = cv::imdecode(cv::Mat(data), cv::IMREAD_COLOR);
  if (img.empty()) {
    has_state_ = false;
    return false;
  }
  auto state = scraper_->scrape(img);
  if (!state) {
    frame_ = img;
    has_state_ = false;
    return false;
  }
  frame_ = img;
  state_json_ = to_json(*state);
  has_state_ = true;
  return true;
}

}  // namespace poker
