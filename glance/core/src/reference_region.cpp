#include "reference_region.h"
#include <algorithm>
#include <cmath>
#include <stdexcept>
namespace glance {
namespace {
double round_even(double x) {
  const double base = std::floor(x);
  const double fraction = x - base;
  return base + (fraction > 0.5 || (fraction == 0.5 && std::fmod(base, 2.0) != 0.0));
}
}
cv::Mat crop_reference_region(const cv::Mat& image, cv::Size reference,
                              cv::Rect region, int padding) {
  if (image.empty() || image.dims != 2 || reference.width <= 0 || reference.height <= 0 || region.width <= 0 || region.height <= 0 || padding < 0)
    throw std::invalid_argument("Invalid image or region");
  const double sx = static_cast<double>(image.cols) / reference.width;
  const double sy = static_cast<double>(image.rows) / reference.height;
  const double px = round_even(padding * sx), py = round_even(padding * sy);
  const auto clip = [](double x, int limit) { return static_cast<int>(std::clamp(x, 0.0, static_cast<double>(limit))); };
  const int x1 = clip(round_even(region.x * sx) - px, image.cols);
  const int y1 = clip(round_even(region.y * sy) - py, image.rows);
  const int x2 = clip(round_even((static_cast<double>(region.x) + region.width) * sx) + px, image.cols);
  const int y2 = clip(round_even((static_cast<double>(region.y) + region.height) * sy) + py, image.rows);
  if (x2 <= x1 || y2 <= y1) throw std::invalid_argument("Empty crop");
  return image(cv::Rect(x1, y1, x2-x1, y2-y1));
}
}
