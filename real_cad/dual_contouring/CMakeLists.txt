cmake_minimum_required(VERSION 3.21)
project(topic4_regular_grid_dc LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Eigen3 REQUIRED)
find_path(LIBIGL_INCLUDE_DIR igl/signed_distance.h
  HINTS "$ENV{HOME}/libigl/include" /opt/homebrew/include /usr/local/include
  REQUIRED)

add_executable(regular_grid_dc regular_grid_dc.cpp)
target_include_directories(regular_grid_dc PRIVATE ${LIBIGL_INCLUDE_DIR})
target_link_libraries(regular_grid_dc PRIVATE Eigen3::Eigen)

