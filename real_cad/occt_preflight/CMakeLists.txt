cmake_minimum_required(VERSION 3.21)
project(topic4_occt_preflight LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Intentionally exclude the OpenCascade Draw module.  Several Draw libraries
# install process-exit handlers, which makes exit codes unreliable in a batch
# validation harness.
find_package(OpenCASCADE REQUIRED COMPONENTS
  FoundationClasses
  ModelingData
  ModelingAlgorithms
  Visualization
  ApplicationFramework
  DataExchange
)

add_executable(occt_step_preflight occt_step_preflight.cpp)
target_include_directories(occt_step_preflight PRIVATE ${OpenCASCADE_INCLUDE_DIR})
target_link_libraries(occt_step_preflight PRIVATE
  TKDESTEP
  TKDE
  TKXSBase
  TKXCAF
  TKLCAF
  TKCAF
  TKCDF
  TKShHealing
  TKMesh
  TKTopAlgo
  TKGeomAlgo
  TKBRep
  TKGeomBase
  TKG3d
  TKG2d
  TKMath
  TKernel
)

if(APPLE)
  set_target_properties(occt_step_preflight PROPERTIES
    BUILD_RPATH "/opt/homebrew/lib"
  )
endif()
