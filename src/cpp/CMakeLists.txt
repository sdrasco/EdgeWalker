cmake_minimum_required(VERSION 3.4)
cmake_policy(SET CMP0148 NEW)  # Suppress the policy warning related to Python module finding

project(strangle_module)

# Set the C++ standard
set(CMAKE_CXX_STANDARD 11)

# Set CMake prefix path for Homebrew (where pybind11 is installed)
set(CMAKE_PREFIX_PATH /opt/homebrew)

# Locate pybind11
find_package(pybind11 REQUIRED)

# Include directories
include_directories(include)

# Define the library with updated sources
add_library(strangle_module MODULE src/bindings.cpp src/strangle.cpp src/find_min_spread.cpp)
target_link_libraries(strangle_module PRIVATE pybind11::module)

# Optimization flags for Apple M1
#target_compile_options(strangle_module PRIVATE -Ofast -mcpu=apple-m1 -mtune=apple-m1)

# Optimization flags that detect chip
target_compile_options(strangle_module PRIVATE -O3 -march=native -ftree-vectorize -flto)

# Remove the 'lib' prefix from the output file
set_target_properties(strangle_module PROPERTIES PREFIX "")
