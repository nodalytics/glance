#include "preprocessing.h"
#include <algorithm>
#include <stdexcept>
#include <vector>
#include <opencv2/imgproc.hpp>
#include <opencv2/photo.hpp>
namespace glance {
namespace {
void validate(const cv::Mat& image) {
  if (image.empty() || image.dims != 2 || image.type() != CV_8UC3)
    throw std::invalid_argument("Expected a nonempty 8-bit BGR image");
}
}
cv::Mat ImagePreprocessor::resize(const cv::Mat& image, int max_width) {
  validate(image);
  if (max_width <= 0) throw std::invalid_argument("Invalid maximum width");
  if (image.cols <= max_width) return image.clone();
  const double scale = static_cast<double>(max_width) / image.cols;
  cv::Mat out;
  cv::resize(image, out, cv::Size(max_width, std::max(1, static_cast<int>(image.rows * scale))), 0, 0, cv::INTER_AREA);
  return out;
}
cv::Mat ImagePreprocessor::denoise(const cv::Mat& image) {
  validate(image);
  cv::Mat out;
  cv::fastNlMeansDenoisingColored(image, out, 5, 5, 7, 21);
  return out;
}
cv::Mat ImagePreprocessor::enhance_contrast(const cv::Mat& image) {
  validate(image);
  cv::Mat lab, light, out;
  cv::cvtColor(image, lab, cv::COLOR_BGR2Lab);
  std::vector<cv::Mat> channels;
  cv::split(lab, channels);
  cv::createCLAHE(2.0, cv::Size(8, 8))->apply(channels[0], light);
  channels[0] = light;
  cv::merge(channels, lab);
  cv::cvtColor(lab, out, cv::COLOR_Lab2BGR);
  return out;
}
cv::Mat ImagePreprocessor::grayscale(const cv::Mat& image) {
  validate(image);
  cv::Mat out;
  cv::cvtColor(image, out, cv::COLOR_BGR2GRAY);
  return out;
}
PreprocessedImage ImagePreprocessor::process(const cv::Mat& image) {
  PreprocessedImage out;
  out.original = resize(image);
  out.denoised = denoise(out.original);
  out.enhanced = enhance_contrast(out.denoised);
  out.grayscale = grayscale(out.enhanced);
  return out;
}
}  // namespace glance
