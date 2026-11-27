cmake_minimum_required(VERSION 3.24)
project(glance LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

option(GLANCE_OCR "build the tesseract OCR reader (needs tesseract-dev)" ON)
# Screen grab + synthetic input (control, milestone M2): the X11 backend uses
# XGetImage + XTest from the distro's libx11-dev / libxext-dev. Like OCR above,
# it is a configure-time option: on a machine without the headers the build
# still succeeds and the null backend is used (the server then reports
# "no display" at runtime). Windows/macOS backends go here too (SendInput,
# CGEvent) when glance moves off Linux.
option(GLANCE_X11 "build the X11 screen/input backend (needs libx11-dev libxext-dev)" ON)

include(FetchContent)
# Single-header deps, pinned to kestrel's known-good json build
FetchContent_Declare(json URL https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz
                     URL_HASH SHA256=d6c65aca6b1ed68e7a182f4757257b107ae403032760ed6ef121c9d55e81757d)
FetchContent_Declare(httplib GIT_REPOSITORY https://github.com/yhirose/cpp-httplib.git GIT_TAG v0.67.0)
set(CMAKE_POLICY_VERSION_MINIMUM 3.5)
FetchContent_MakeAvailable(json)

# OpenCV: the distro's prebuilt package (libopencv-dev), NOT a source build.
# The from-source 5.1.0 we previously Fetched is what made builds slow and disk
# heavy (a full OpenCV build on a 2-core CI runner), and from-source 5.1.0 once
# aborted with `malloc(): corrupted top size` on two AVX-512 AMD hosts (NOT
# proven to be OpenCV's fault — a correct probe later showed the prebuilt
# 4.6 computes matchTemplate/minMaxLoc exactly right, so the abort was in our
# test code — see global memory, Nov 2026). Either way: the distro package
# (4.6 on Ubuntu 24.04; 4.x elsewhere) is already built and tuned by the
# maintainer, so we never compile OpenCV at build time.
find_package(OpenCV 4.5 REQUIRED COMPONENTS core imgproc imgcodecs)

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

# X11 screen/input backend for the control surface (POST /grab /click /key
# /sequence). Same pattern as OCR above: never required, detected here so the
# whole build falls back to the null backend when the dev headers are absent.
# libxext-dev does NOT ship X11/extensions/XTest.h on Ubuntu (it only has
# xtestext1.h) — that header is in libxtst-dev. XTestFake*Event lives in
# libXext.so, which libxtst-dev links against, so X11::Xext is still the
# right thing to link. Linux only; other platforms get their own backend under
# the same flag scheme later.
set(HAS_X11 OFF)
if(GLANCE_X11 AND CMAKE_SYSTEM_NAME STREQUAL "Linux")
  find_package(X11 QUIET)
  find_path(GLANCE_X11_XLIB_H X11/Xlib.h)
  find_path(GLANCE_X11_XTEST_H X11/extensions/XTest.h)
  if(X11_FOUND AND GLANCE_X11_XLIB_H AND GLANCE_X11_XTEST_H)
    set(HAS_X11 ON)
    message(STATUS "glance: X11 control enabled (libX11 + XTest from the distro)")
  else()
    message(STATUS "glance: no X11 development headers, control falls back to the null backend (install libx11-dev libxext-dev libxtst-dev)")
  endif()
endif()

add_library(glance_core
  core/src/mapping.cpp
  core/src/template_match.cpp
  core/src/ocr.cpp
  core/src/scraper.cpp
  core/src/server.cpp
  core/src/state_validation.cpp
  core/src/control.cpp
  core/src/control_service.cpp
  core/src/screen_x11.cpp
  core/src/server_control.cpp)
target_include_directories(glance_core PUBLIC core/include)
# find_package(OpenCV) exposes the per-module imported targets that carry the
# public header include paths. The namespaced aliases (OpenCV::core) only
# exist in OpenCV >= 4.9 configs, but the classic opencv_* names are what
# every 4.x install exports (Ubuntu 24.04 ships 4.6; newer distros both), so
# link those.
target_link_libraries(glance_core
  PUBLIC nlohmann_json::nlohmann_json opencv_core opencv_imgproc opencv_imgcodecs Threads::Threads)
if(HAS_OCR)
  string(REPLACE "\"" "\\\"" TESSERACT_BIN_ESCAPED "${TESSERACT_BIN_PATH}")
  target_compile_definitions(glance_core PUBLIC "GLANCE_OCR=1" "GLANCE_TESSERACT_BIN=\"${TESSERACT_BIN_ESCAPED}\"")
endif()
if(HAS_X11)
  # X11::Xext carries the XTest extension functions (XTestFake*Event) on
  # distro packages; the XTest.h header is what the header check above needs.
  target_link_libraries(glance_core PUBLIC X11::X11 X11::Xext)
  target_compile_definitions(glance_core PUBLIC "GLANCE_X11=1")
endif()

FetchContent_MakeAvailable(httplib)
target_link_libraries(glance_core PUBLIC httplib::httplib)
# POST /capture takes raw PNG/JPEG bytes. cpp-httplib reserves a tiny (8 KB
# by default) compile-time budget for bodies arriving labeled
# application/x-www-form-urlencoded, so a naive client (curl --data-binary
# sends exactly that content type) gets a silent 413 on a multi-MB
# screenshot. Every glance binary's only POST route takes raw image bytes,
# so the limit is lifted to match the 16 MB runtime payload cap set in
# server/main.cpp.
target_compile_definitions(glance_core PUBLIC CPPHTTPLIB_FORM_URL_ENCODED_PAYLOAD_MAX_LENGTH=16777216)

add_library(glance_acr acr/src/acr_scraper.cpp)
target_include_directories(glance_acr PUBLIC acr/include)
target_link_libraries(glance_acr PUBLIC glance_core)

add_executable(glance-server server/main.cpp)
target_link_libraries(glance-server PRIVATE glance_acr glance_core)

add_executable(glance-selftest tools/selftest.cpp)
target_link_libraries(glance-selftest PRIVATE glance_core)

# Diagnostics only: prints the imgcodecs "Image I/O" build section and
# exercises imwrite/imencode per format. Run standalone (the CI workflow has
# a dedicated step for it) so a host without the right codecs still reports
# what it can encode before the selftest is expected to work.
add_executable(glance-opencv-probe tools/opencv_probe.cpp)
target_link_libraries(glance-opencv-probe PRIVATE opencv_core opencv_imgcodecs)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(glance_core PRIVATE -Wall -Wextra)
  target_compile_options(glance_acr PRIVATE -Wall -Wextra)
endif()

enable_testing()
add_test(NAME selftest COMMAND glance-selftest)
