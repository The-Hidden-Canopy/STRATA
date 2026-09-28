cmake_minimum_required(VERSION 3.20)
project(strata VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(strata-core STATIC cpp/src/types.cpp)
target_include_directories(strata-core PUBLIC cpp/include)
target_compile_features(strata-core PUBLIC cxx_std_20)

add_executable(strata-cli cpp/apps/strata-cli/main.cpp)
target_link_libraries(strata-cli PRIVATE strata-core)

include(CTest)
if(BUILD_TESTING)
  add_executable(strata-core-smoke cpp/tests/core_smoke.cpp)
  target_link_libraries(strata-core-smoke PRIVATE strata-core)
  add_test(NAME strata-core-smoke COMMAND strata-core-smoke)
endif()

