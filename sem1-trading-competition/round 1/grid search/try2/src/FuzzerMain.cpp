#include "../include/Backtester.h"

#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <thread>
#include <mutex>
#include <atomic>
#include <algorithm>
#include <cmath>
#include <chrono>
#include <iomanip>

//-----------------------------------------------
// Global variables for CSV data
//-----------------------------------------------
static std::vector<int>    g_ticks;
static std::vector<double> g_bids;
static std::vector<double> g_asks;
static int                 g_nrows = 0;

//-----------------------------------------------
// Structure to hold parameter combinations and results
//-----------------------------------------------
struct ParamResult {
    int short_window;
    int waiting_period;
    double hs_exit_change_threshold;
    double ma_turn_threshold;
    double pnl;
};

//-----------------------------------------------
// Generate fuzzy parameter values (±10% range in 1% steps)
//-----------------------------------------------
std::vector<int> fuzzIntParam(int baseVal)
{
    // Produce 21 steps from 90% to 110%
    std::vector<int> vals;
    for(int i = -10; i <= 10; i++){
        double factor = (100.0 + i)/100.0; 
        double dval = baseVal * factor;
        int iv = (int)std::round(dval);
        if(iv < 1) iv = 1; // Avoid zero values
        vals.push_back(iv);
    }
    std::sort(vals.begin(), vals.end());
    return vals;
}

std::vector<double> fuzzDoubleParam(double baseVal)
{
    std::vector<double> vals;
    for(int i = -10; i <= 10; i++){
        double factor = (100.0 + i)/100.0;
        double dv = baseVal * factor;
        if(dv <= 0.0) dv = 1e-6; // Avoid non-positive values
        vals.push_back(dv);
    }
    std::sort(vals.begin(), vals.end());
    return vals;
}

//-----------------------------------------------
// Global variables for tracking fuzzer state
//-----------------------------------------------
static std::vector<ParamResult> g_combos;
static std::vector<ParamResult> g_results;
static std::atomic<size_t> g_nextIdx{0};
static std::atomic<size_t> g_doneCount{0};
static size_t g_totalCount = 0;

std::mutex g_resMutex;

//-----------------------------------------------
// Worker thread function
//-----------------------------------------------
void workerThreadFunc()
{
    while(true){
        size_t idx = g_nextIdx.fetch_add(1);
        if(idx >= g_totalCount) {
            return; // No more combinations to test
        }
        
        // Get parameters for this run
        ParamResult pr = g_combos[idx];

        // Run backtest with these parameters
        double pnl = runBacktest(
            pr.short_window,
            pr.waiting_period,
            pr.hs_exit_change_threshold,
            pr.ma_turn_threshold,
            g_ticks,
            g_bids,
            g_asks
        );
        pr.pnl = pnl;

        // Store the result
        {
            std::lock_guard<std::mutex> lk(g_resMutex);
            g_results[idx] = pr;
        }
        g_doneCount.fetch_add(1);
    }
}

//-----------------------------------------------
// Progress reporting thread
//-----------------------------------------------
void progressThreadFunc()
{
    using clock = std::chrono::steady_clock;
    auto nextPrint = clock::now() + std::chrono::seconds(1);

    while(true){
        std::this_thread::sleep_until(nextPrint);
        nextPrint = clock::now() + std::chrono::seconds(1);

        size_t done = g_doneCount.load();
        if(done >= g_totalCount){
            // All done => break for final print
            break;
        }
        
        // Get current results and find top performers
        std::vector<ParamResult> localCopy;
        {
            std::lock_guard<std::mutex> lk(g_resMutex);
            localCopy = g_results; 
        }
        std::sort(localCopy.begin(), localCopy.end(),
                  [](auto &a, auto &b){
                      return a.pnl > b.pnl; // Sort descending by PnL
                  });

        // Print progress and top 3 results
        std::cerr << "\r" << std::flush; // Carriage return
        std::cerr << "Progress: " << done << "/" << g_totalCount << " (" 
                  << std::fixed << std::setprecision(1) 
                  << (100.0 * done / g_totalCount) << "%)  ";
        
        int topCount = std::min<int>((int)localCopy.size(), 3);
        if (topCount > 0) {
            std::cerr << "Top " << topCount << ": ";
            for(int i=0; i<topCount; i++){
                std::cerr << "[SW=" << localCopy[i].short_window
                        << ", WP=" << localCopy[i].waiting_period
                        << ", HSX=" << std::fixed << std::setprecision(3) << localCopy[i].hs_exit_change_threshold
                        << ", MAT=" << std::fixed << std::setprecision(3) << localCopy[i].ma_turn_threshold
                        << " => " << std::fixed << std::setprecision(2) << localCopy[i].pnl << "]  ";
            }
        }
        // Erase to end of line
        std::cerr << "\x1b[K" << std::flush;
    }

    // Final results
    {
        size_t done = g_doneCount.load();
        std::vector<ParamResult> localCopy;
        {
            std::lock_guard<std::mutex> lk(g_resMutex);
            localCopy = g_results;
        }
        std::sort(localCopy.begin(), localCopy.end(),
                  [](auto &a, auto &b){
                      return a.pnl > b.pnl;
                  });

        std::cerr << "\r" << std::flush;
        std::cerr << done << "/" << g_totalCount 
                  << " complete. Final top 3 combinations:\n";
        int topCount = std::min<int>((int)localCopy.size(), 3);
        for(int i=0; i<topCount; i++){
            std::cerr << (i+1) << ") [SW=" << localCopy[i].short_window
                      << ", WP=" << localCopy[i].waiting_period
                      << ", HSX=" << std::fixed << std::setprecision(3) << localCopy[i].hs_exit_change_threshold
                      << ", MAT=" << std::fixed << std::setprecision(3) << localCopy[i].ma_turn_threshold
                      << "] => PnL=" << std::fixed << std::setprecision(2) << localCopy[i].pnl << "\n";
        }
    }
}

//-----------------------------------------------
// Main function
//-----------------------------------------------
int main(int argc, char* argv[])
{
    // Default CSV file path
    std::string csvPath = "../data/UEC.csv";
    
    // Parse command line arguments
    if (argc > 1) {
        csvPath = argv[1];
    }
    
    std::cout << "Loading data from: " << csvPath << std::endl;
    
    // 1) Read CSV data
    {
        std::ifstream fin(csvPath);
        if(!fin.is_open()){
            std::cerr << "Error: cannot open " << csvPath << std::endl;
            return 1;
        }
        
        bool first_line = true;
        std::string line;
        while(std::getline(fin, line)){
            if(line.empty()) continue;
            
            // Skip header if present
            if(first_line){
                first_line = false;
                // Uncomment next line if there's no header
                // continue; 
            }
            
            std::stringstream ss(line);
            std::string c1, c2, c3;
            if(std::getline(ss, c1, ',') &&
               std::getline(ss, c2, ',') &&
               std::getline(ss, c3, ','))
            {
                int tk = std::stoi(c1);
                double bd = std::stod(c2);
                double ak = std::stod(c3);
                g_ticks.push_back(tk);
                g_bids.push_back(bd);
                g_asks.push_back(ak);
            }
        }
        fin.close();
    }
    
    g_nrows = (int)g_ticks.size();
    if(g_nrows == 0){
        std::cerr << "Error: No data loaded from " << csvPath << std::endl;
        return 1;
    }
    std::cout << "Loaded " << g_nrows << " rows from " << csvPath << std::endl;

    // 2) Define base parameter values and create combinations
    int    baseSW  = 80;
    int    baseWP  = 80;
    double baseHSX = 0.2;
    double baseMAT = 0.9;

    auto sw_vals  = fuzzIntParam(baseSW);
    auto wp_vals  = fuzzIntParam(baseWP);
    auto hsx_vals = fuzzDoubleParam(baseHSX);
    auto mat_vals = fuzzDoubleParam(baseMAT);

    // Build all parameter combinations
    for(int sw : sw_vals){
        for(int wp : wp_vals){
            for(double hsx : hsx_vals){
                for(double mat : mat_vals){
                    ParamResult pr;
                    pr.short_window = sw;
                    pr.waiting_period = wp;
                    pr.hs_exit_change_threshold = hsx;
                    pr.ma_turn_threshold = mat;
                    pr.pnl = 0.0;
                    g_combos.push_back(pr);
                }
            }
        }
    }
    g_totalCount = g_combos.size();
    g_results.resize(g_totalCount);

    std::cout << "Testing " << g_totalCount << " parameter combinations..." << std::endl;

    // 3) Multi-threading setup
    unsigned int hw = std::thread::hardware_concurrency();
    if(hw == 0) hw = 2; // Fallback if hardware_concurrency fails
    std::cout << "Using " << hw << " threads." << std::endl;

    // Start progress reporting thread
    std::thread progThread(progressThreadFunc);

    // Spawn worker threads
    std::vector<std::thread> workers;
    workers.reserve(hw);
    for(unsigned int i=0; i<hw; i++){
        workers.emplace_back(workerThreadFunc);
    }

    // Wait for worker threads to complete
    for(auto &t : workers){
        t.join();
    }

    // Wait for progress thread to finish final report
    progThread.join();

    return 0;
} 