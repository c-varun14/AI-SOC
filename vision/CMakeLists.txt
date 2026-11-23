cmake_minimum_required(VERSION 3.28)
project(PillGuardSinglePass LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
find_package(executorch REQUIRED CONFIG)
add_executable(pillguard_deployment_inference vision.cpp)
target_link_libraries(pillguard_deployment_inference PRIVATE
    executorch::runtime executorch::kernels_optimized executorch::backend_xnnpack)
