#include "server.h"

#include "image_io.h"
#include "scraper.h"

namespace glance {

ScreenshotService::ScreenshotService(TableScraper* scraper) : scraper_(scraper) {}

bool ScreenshotService::update(const std::vector<unsigned char>& data) {
  if (data.empty() || !scraper_) return false;
  cv::Mat img = decode_image(data, /*color=*/true);
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

}  // namespace glance
