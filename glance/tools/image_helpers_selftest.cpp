#include "preprocessing.h"
#include "reference_region.h"
#include <opencv2/imgproc.hpp>
#include <cstdio>
#include <stdexcept>
int main() {
  int failures = 0;
  const auto check = [&](bool ok, const char* msg) { std::printf("%s: %s\n", ok ? "ok" : "FAIL", msg); failures += !ok; };
  using glance::ImagePreprocessor;
  cv::Mat image(60, 80, CV_8UC3);
  cv::RNG rng(42); rng.fill(image, cv::RNG::UNIFORM, 0, 256);
  const auto before = image.clone();
  const auto result = ImagePreprocessor::process(image);
  check(result.original.data != image.data && cv::norm(result.original, image, cv::NORM_INF) == 0, "independent original");
  check(result.denoised.size() == image.size() && result.denoised.type() == CV_8UC3, "denoise shape/type");
  check(result.enhanced.size() == image.size() && result.enhanced.type() == CV_8UC3, "enhanced shape/type");
  check(result.grayscale.size() == image.size() && result.grayscale.type() == CV_8UC1, "gray shape/type");
  cv::Mat expected; cv::cvtColor(result.enhanced, expected, cv::COLOR_BGR2GRAY);
  check(cv::norm(expected, result.grayscale, cv::NORM_INF) == 0, "gray pixels");
  check(cv::norm(before, image, cv::NORM_INF) == 0, "input unchanged");
  check(ImagePreprocessor::resize(image, 40).size() == cv::Size(40,30), "resize ratio");
  auto crop = glance::crop_reference_region(image, {160,120}, {21,21,20,20}, 3);
  check(crop.size() == cv::Size(14,14), "scaled padding and ties-to-even");
  check(cv::norm(crop, image(cv::Rect(8,8,14,14)), cv::NORM_INF) == 0, "crop pixels");
  check(glance::crop_reference_region(image, {80,60}, {0,0,10,10}, 3).size() == cv::Size(13,13), "boundary clipping");
  bool rejected = false; try { ImagePreprocessor::process({}); } catch (const std::invalid_argument&) { rejected = true; }
  check(rejected, "empty input rejected");
  rejected = false; try { glance::crop_reference_region(image, {80,60}, {100,100,5,5}); } catch (const std::invalid_argument&) { rejected = true; }
  check(rejected, "empty crop rejected");
  return failures ? 1 : 0;
}
