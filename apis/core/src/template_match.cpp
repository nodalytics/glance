#include "template_match.h"

#include <algorithm>

#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

namespace poker {

cv::Mat load_template(const std::string& path) {
  cv::Mat img = cv::imread(path, cv::IMREAD_COLOR);
  return img;
}

// Clamp a search-area rect into the image bounds. Returns false when the
// rect is empty after clamping.
static bool clamp_area(const cv::Mat& image, int& x1, int& y1, int& x2, int& y2) {
  x1 = std::clamp(x1, 0, image.cols);
  y1 = std::clamp(y1, 0, image.rows);
  x2 = std::clamp(x2, 0, image.cols);
  y2 = std::clamp(y2, 0, image.rows);
  return x2 > x1 && y2 > y1;
}

std::optional<MatchResult> find_template(const cv::Mat& image, const cv::Mat& template_img, double threshold) {
  if (image.empty() || template_img.empty()) return std::nullopt;
  if (template_img.cols > image.cols || template_img.rows > image.rows) return std::nullopt;
  cv::Mat tmpl = template_img;
  if (image.type() != tmpl.type()) {
    if (tmpl.channels() != image.channels()) return std::nullopt;
    tmpl.convertTo(tmpl, image.type());
  }

  cv::Mat result;
  cv::matchTemplate(image, tmpl, result, cv::TM_SQDIFF_NORMED);

  double min_val;
  cv::Point min_loc;
  cv::minMaxLoc(result, &min_val, nullptr, &min_loc, nullptr);
  // TM_SQDIFF_NORMED: lower is better.
  if (min_val > threshold) return std::nullopt;
  MatchResult r;
  r.location = min_loc;
  r.score = min_val;
  return r;
}

std::optional<MatchResult> find_template_in_area(const cv::Mat& image, const cv::Mat& template_img,
                                                 double threshold, int x1, int y1, int x2, int y2) {
  if (!clamp_area(image, x1, y1, x2, y2)) return std::nullopt;
  cv::Mat roi = image(cv::Rect(x1, y1, x2 - x1, y2 - y1));
  auto res = find_template(roi, template_img, threshold);
  if (!res) return std::nullopt;
  res->location.x += x1;
  res->location.y += y1;
  return res;
}

bool has_template_in_area(const cv::Mat& image, const cv::Mat& template_img, double threshold,
                          int x1, int y1, int x2, int y2) {
  return find_template_in_area(image, template_img, threshold, x1, y1, x2, y2).has_value();
}

int count_template_hits(const cv::Mat& image, const cv::Mat& template_img, double threshold) {
  if (image.empty() || template_img.empty()) return 0;
  if (template_img.cols > image.cols || template_img.rows > image.rows) return 0;
  cv::Mat tmpl = template_img;
  if (image.type() != tmpl.type()) {
    if (tmpl.channels() != image.channels()) return 0;
    tmpl.convertTo(tmpl, image.type());
  }
  cv::Mat result;
  cv::matchTemplate(image, tmpl, result, cv::TM_SQDIFF_NORMED);
  cv::Mat good;
  cv::compare(result, cv::Scalar(threshold), good, cv::CMP_LE);
  return cv::countNonZero(good);
}

}  // namespace poker
