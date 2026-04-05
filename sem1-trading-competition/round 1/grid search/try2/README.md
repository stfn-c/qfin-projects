# PanicTrader Backtester

A C++ implementation of the PanicTrader strategy backtester with parameter optimization capabilities. This project extracts the backtesting logic into a reusable shared library that can be linked with different applications.

## Project Structure

```
backtest/
├── include/
│   └── Backtester.h      # Public API header
├── src/
│   ├── Backtester.cpp    # Implementation of the strategy logic
│   └── FuzzerMain.cpp    # Parameter optimization program
├── lib/                  # Compiled libraries output
├── CMakeLists.txt        # Build configuration
└── README.md             # This file
```

## Components

1. **Backtester Library** - A shared library (.so/.dll) that implements the core trading strategy logic:
   - Accurate implementation of the original Python strategy
   - Highly optimized for speed
   - Clean API with a single function: `runBacktest()`

2. **Parameter Fuzzer** - A multithreaded application that:
   - Loads market data from CSV files
   - Tests thousands of parameter combinations
   - Reports the best performing parameter sets
   - Uses all available CPU cores for maximum efficiency

## Build Instructions

### Prerequisites

- CMake 3.10 or higher
- C++17 compatible compiler
- Make or your preferred build system

### Building

```bash
# Create a build directory
mkdir -p build && cd build

# Generate build files
cmake ..

# Build the project
make

# Optionally install
make install
```

## Usage

### Running the Fuzzer

```bash
# Run with default settings (reads ../data/UEC.csv)
./fuzzer

# Run with a custom CSV file
./fuzzer /path/to/data.csv
```

### Using the Backtester Library

```cpp
#include <Backtester.h>

// Call the backtest function
double pnl = runBacktest(
    short_window,             // Length of short-term moving average
    waiting_period,           // Waiting period after high spread exit
    hs_exit_change_threshold, // Threshold for high spread exit
    ma_turn_threshold,        // Moving average turn threshold
    ticks,                    // Vector of timestamps
    bids,                     // Vector of bid prices
    asks                      // Vector of ask prices
);
```

## Strategy Parameters

1. `short_window`: Length of the short-term rolling average window
2. `waiting_period`: Length of the waiting period after high spread exit
3. `hs_exit_change_threshold`: Threshold for re-entry after high spread
4. `ma_turn_threshold`: Threshold for early exit when moving average turns

## License

This project is proprietary and confidential. 