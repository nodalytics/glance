#pragma once

#include <string>
#include <optional>
#include <opencv2/core.hpp>

namespace glance {

// Turn one OCR text line into a non-negative number.
// '$' and 'B' are ignored. A comma is a thousands separator when groups are
// three digits ("1,200" -> 1200, "1,200.50" -> 1200.5) and a decimal mark
// otherwise ("12,5" -> 12.5). "1.200,50" uses the last separator as decimal.
// A minus sign, an empty line, or leftover extra dots yield nullopt.
// Does not run tesseract.
std::optional<double> parse_ocr_number_text(const std::string& text);

// Read a number (stack sizes, pot, bet amounts) from a region of a screenshot
// with tesseract. Returns std::nullopt when OCR is unavailable or yields no
// parseable number.
std::optional<double> ocr_number(const cv::Mat& region);

// True when OCR support was compiled in and the tesseract binary is present.
bool ocr_available();

// Pre-process an OCR region: enlarge to a fixed width, grayscale,
// binarize. Returns the transformed copy.
cv::Mat prepare_for_ocr(const cv::Mat& region);

}  // namespace glance
