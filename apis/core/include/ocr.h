#pragma once

#include <string>
#include <optional>
#include <opencv2/core.hpp>

namespace poker {

// Read a number (stack sizes, pot, bet amounts) from a region of a screenshot
// with tesseract. Returns std::nullopt when OCR is unavailable or yields no
// parseable number.
std::optional<double> ocr_number(const cv::Mat& region);

// True when OCR support was compiled in and the tesseract binary is present.
bool ocr_available();

// Pre-process an OCR region: enlarge to a fixed width, grayscale,
// binarize. Returns the transformed copy.
cv::Mat prepare_for_ocr(const cv::Mat& region);

}  // namespace poker
