cmake_minimum_required(VERSION 3.10)
project(PanicTrader VERSION 1.0)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Add optimization flags for Release build
set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -O3")

# Include directories
include_directories(include)

# Find required packages
find_package(Threads REQUIRED)

# Create the backtester library (shared)
add_library(backtester SHARED
    src/Backtester.cpp
)

# Set properties for the shared library
set_target_properties(backtester PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 1
    PUBLIC_HEADER include/Backtester.h
)

# Create the main fuzzer executable
add_executable(fuzzer src/FuzzerMain.cpp)

# Link the executable with the library and required packages
target_link_libraries(fuzzer
    backtester
    Threads::Threads
)

# Install rules
install(TARGETS backtester
    LIBRARY DESTINATION lib
    PUBLIC_HEADER DESTINATION include
)

install(TARGETS fuzzer
    RUNTIME DESTINATION bin
) 