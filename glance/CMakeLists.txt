cmake_minimum_required(VERSION 3.24)
project(glance LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

option(GLANCE_OCR "build the tesseract OCR reader (needs tesseract-dev)" ON)

include(FetchContent)
# Single-header deps, pinned to kestrel's known-good json build
FetchContent_Declare(json URL https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz
                     URL_HASH SHA256=d6c65aca6b1ed68e7a182f4757257b107ae403032760ed6ef121c9d55e81757d)
FetchContent_Declare(httplib GIT_REPOSITORY https://github.com/yhirose/cpp-httplib.git GIT_TAG v0.67.0)
set(CMAKE_POLICY_VERSION_MINIMUM 3.5)
FetchContent_MakeAvailable(json)

# OpenCV from source, minimal module list (template matching + image codecs)
set(BUILD_LIST "core;imgproc;imgcodecs" CACHE STRING "" FORCE)
set(BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(BUILD_PERF_TESTS OFF CACHE BOOL "" FORCE)
set(BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(BUILD_opencv_apps OFF CACHE BOOL "" FORCE)
set(WITH_IPP OFF CACHE BOOL "" FORCE)
set(WITH_OPENCL OFF CACHE BOOL "" FORCE)
set(OPENCV_ENABLE_NONFREE OFF CACHE BOOL "" FORCE)
set(WITH_QUIRC OFF CACHE BOOL "" FORCE)
set(WITH_PROTOBUF OFF CACHE BOOL "" FORCE)
set(INSTALL_CREATE_DISTRIB OFF CACHE BOOL "" FORCE)
set(BUILD_ZLIB OFF CACHE BOOL "" FORCE)   # build bundled zlib/JPEG/PNG
set(BUILD_JPEG OFF CACHE BOOL "" FORCE)
set(BUILD_PNG OFF CACHE BOOL "" FORCE)
# Release tarball (not a git checkout): much smaller working tree on the lab,
# where the OpenCV build dominates disk usage. URL_HASH pins the exact source.
FetchContent_Declare(OpenCV
  URL https://github.com/opencv/opencv/archive/refs/tags/5.1.0.tar.gz
  URL_HASH SHA256=638c1dae7e37e45afea21aa217dc667ad7cf57acc66cdf652c074f1e0e5ad6d2)
FetchContent_MakeAvailable(OpenCV)

find_package(Threads REQUIRED)

set(HAS_OCR OFF)
if(GLANCE_OCR)
  find_program(TESSERACT_BIN tesseract)
  if(TESSERACT_BIN)
    set(HAS_OCR ON)
    set(TESSERACT_BIN_PATH "${TESSERACT_BIN}" CACHE STRING "tesseract binary for OCR")
    message(STATUS "glance: OCR enabled via ${TESSERACT_BIN}")
  else()
    message(STATUS "glance: no tesseract binary, OCR disabled (install tesseract for reading pots/stacks)")
  endif()
endif()

add_library(glance_core
  core/src/mapping.cpp
  core/src/template_match.cpp
  core/src/ocr.cpp
  core/src/scraper.cpp
  core/src/server.cpp)
target_include_directories(glance_core PUBLIC core/include)
# OpenCV from source (add_subdirectory) exposes plain module targets — the
# OpenCV:: namespaced targets only exist in an installed package.
target_link_libraries(glance_core
  PUBLIC nlohmann_json::nlohmann_json opencv_core opencv_imgproc opencv_imgcodecs Threads::Threads)
# A from-source (add_subdirectory) OpenCV build marks each module's per-module
# `opencv2/` header directory PRIVATE, so linking opencv_core alone does not
# let us #include <opencv2/core.hpp>. Add the headers for the modules we use.
target_include_directories(glance_core SYSTEM PUBLIC
  ${OpenCV_SOURCE_DIR}/modules/core/include
  ${OpenCV_SOURCE_DIR}/modules/imgproc/include
  ${OpenCV_SOURCE_DIR}/modules/imgcodecs/include
  ${OpenCV_SOURCE_DIR}/3rdparty/ittnotify/include
  ${CMAKE_BINARY_DIR})
if(HAS_OCR)
  string(REPLACE "\"" "\\\"" TESSERACT_BIN_ESCAPED "${TESSERACT_BIN_PATH}")
  target_compile_definitions(glance_core PUBLIC "GLANCE_OCR=1" "GLANCE_TESSERACT_BIN=\"${TESSERACT_BIN_ESCAPED}\"")
endif()

FetchContent_MakeAvailable(httplib)
target_link_libraries(glance_core PUBLIC httplib::httplib)

add_library(glance_acr acr/src/acr_scraper.cpp)
target_include_directories(glance_acr PUBLIC acr/include)
target_link_libraries(glance_acr PUBLIC glance_core)

add_executable(glance-server server/main.cpp)
target_link_libraries(glance-server PRIVATE glance_acr glance_core)

add_executable(glance-selftest tools/selftest.cpp)
target_link_libraries(glance-selftest PRIVATE glance_core)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(glance_core PRIVATE -Wall -Wextra)
  target_compile_options(glance_acr PRIVATE -Wall -Wextra)
endif()

enable_testing()
add_test(NAME selftest COMMAND glance-selftest)
