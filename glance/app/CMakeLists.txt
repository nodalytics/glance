# glance-admin — Qt6 Widgets desktop client of the glance HTTP API.
#
# Standalone-buildable (cmake -S glance/app -B <dir>) and also pulled in by
# glance/CMakeLists.txt (option GLANCE_APP) when Qt6 is found. It links only
# Qt (Widgets + Network): no OpenCV, no glance_core, so it builds on machines
# without OpenCV and talks to any glance-server over HTTP.
cmake_minimum_required(VERSION 3.24)
project(glance_admin VERSION 0.1.0 LANGUAGES CXX)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 20)
  set(CMAKE_CXX_STANDARD_REQUIRED ON)
endif()

find_package(Qt6 6.2 REQUIRED COMPONENTS Widgets Network)

set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

add_executable(glance-admin
  src/main.cpp
  src/apiclient.h      src/apiclient.cpp
  src/theme.h          src/theme.cpp
  src/widgets.h        src/widgets.cpp
  src/tableview.h      src/tableview.cpp
  src/pages.h
  src/overviewpage.cpp
  src/tablepage.cpp
  src/capturepage.cpp
  src/cardlabpage.cpp
  src/controlpage.cpp
  src/inspectorpage.cpp
  src/settingspage.cpp
  src/mainwindow.h     src/mainwindow.cpp
  src/demo.h           src/demo.cpp
  resources/app.qrc
)
target_compile_features(glance-admin PRIVATE cxx_std_20)
target_link_libraries(glance-admin PRIVATE Qt6::Widgets Qt6::Network)
target_compile_definitions(glance-admin PRIVATE
  GLANCE_ADMIN_VERSION="${PROJECT_VERSION}"
  QT_NO_KEYWORDS)
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(glance-admin PRIVATE -Wall -Wextra)
endif()
