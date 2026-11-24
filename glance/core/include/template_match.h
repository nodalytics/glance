#pragma once

#include <string>
#include <vector>
#include <optional>
#include <opencv2/core.hpp>

namespace glance {

// A template match result: the top-left corner of the match, plus the
// normalized match score (TM_SQDIFF_NORMED: 0.0 is a perfect match).
struct MatchResult {
  cv::Point location;
  double score = 0.0;
};

// Load a template image from disk (BGR). Empty Mat on failure.
cv::Mat load_template(const std::string& path);

// Find a template in an image with TM_SQDIFF_NORMED. A match is reported when
// the best score is at or below threshold.
std::optional<MatchResult> find_template(const cv::Mat& image, const cv::Mat& template_img, double threshold);

// Find a template inside a sub-rectangle of an image (the search area).
std::optional<MatchResult> find_template_in_area(const cv::Mat& image, const cv::Mat& template_img,
                                                 double threshold, int x1, int y1, int x2, int y2);

// True when the template is present anywhere in the (clamped) search area.
bool has_template_in_area(const cv::Mat& image, const cv::Mat& template_img, double threshold,
                          int x1, int y1, int x2, int y2);

// Number of positions whose TM_SQDIFF_NORMED score is at or below threshold.
// Used to require a unique anchor hit (the bot's "exactly one topleft corner"
// rule).
int count_template_hits(const cv::Mat& image, const cv::Mat& template_img, double threshold);

}  // namespace glance
