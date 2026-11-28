
#pragma once

#include <opencv2/core.hpp>

namespace glance {

// Generic offline image crop.
// Region uses exclusive right/bottom edges.
// Padding is expressed in reference-image coordinates.
// Returns an ROI view sharing the original image's storage.
// Throws std::invalid_argument for invalid inputs or empty crops.
cv::Mat crop_reference_region(
    const cv::Mat& image,
    cv::Size reference,
    cv::Rect region,
    int padding = 3
);

}  // namespace glance
