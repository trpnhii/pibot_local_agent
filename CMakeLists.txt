cmake_minimum_required(VERSION 3.20)
project(pibot_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(FetchContent)

# JSON dependency for config parsing.
FetchContent_Declare(
  nlohmann_json
  GIT_REPOSITORY https://github.com/nlohmann/json.git
  GIT_TAG v3.11.3
)
FetchContent_MakeAvailable(nlohmann_json)

add_executable(
  pibot
  src/main.cpp
  src/config.cpp
)

target_include_directories(pibot PRIVATE src)
target_link_libraries(pibot PRIVATE nlohmann_json::nlohmann_json)
