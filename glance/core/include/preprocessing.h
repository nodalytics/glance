#pragma once
#include <opencv2/core.hpp>
namespace glance {
struct PreprocessedImage {
  cv::Mat original, denoised, enhanced, grayscale;
};
class ImagePreprocessor {
 public:
  static cv::Mat resize(const cv::Mat& image, int max_width = 1600);
  static cv::Mat denoise(const cv::Mat& image);
  static cv::Mat enhance_contrast(const cv::Mat& image);
  static cv::Mat grayscale(const cv::Mat& image);
  static PreprocessedImage process(const cv::Mat& image);
};
}  // namespace glance
