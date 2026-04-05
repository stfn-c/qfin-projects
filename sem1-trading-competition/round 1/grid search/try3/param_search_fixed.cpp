#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <map>
#include <cmath>
#include <limits>
#include <algorithm>
#include <iomanip> // For std::setprecision
#include <thread>
#include <mutex>
#include <queue>
#include <chrono>
#include <atomic>

// Structure for parameters
struct ParameterSet {
    int short_window;
    int waiting_period;
    double hs_exit_change_threshold;
    double ma_turn_threshold;
    double pnl;

    bool operator<(const ParameterSet& rhs) const {
        return pnl < rhs.pnl;
    }
};

// Base parameters from PanicTrader.py
const int BASE_SHORT_WINDOW = 80;
const int BASE_WAITING_PERIOD = 80;
const double BASE_HS_EXIT_CHANGE_THRESHOLD = 0.2;
const double BASE_MA_TURN_THRESHOLD = 0.9;

// Fixed parameters (not being optimized)
const int LONG_WINDOW = 500;
const double HIGH_SPREAD_THRESHOLD = 1.3;
const int POSITION_SIZE = 100;
const bool HOLD_DURING_HIGH_SPREAD = false;

// Data structures
struct PriceData {
    double Bid;
    double Ask;
};

struct StrategyState {
    bool in_position;
    bool position_is_long;
    bool waiting_for_signal;
    bool holding_position_in_high_spread;

    int high_spread_exit_index;
    int position_entry_index_in_hs;

    double last_high_spread_exit_short_avg;
    double prev_short_avg_in_hs;
    double current_position_extreme;

    int current_position;   
    double cash;            
    double total_fees;      
    int time_index;         
};

// Add a new struct to hold backtest results
struct BacktestResult {
    double pnl;
    double total_fees;
};

// Function to compute rolling average
double computeRollingAverage(const std::vector<double>& midPrices, int endIndex, int windowSize) {
    int startIndex = endIndex - windowSize + 1;
    if(startIndex < 0) {
        return std::numeric_limits<double>::quiet_NaN();
    }
    double sum = 0.0;
    for(int i = startIndex; i <= endIndex; i++) {
        sum += midPrices[i];
    }
    return sum / static_cast<double>(windowSize);
}

// Core strategy logic with parameterization
int getOrdersWithParams(const PriceData& data, 
                       StrategyState& st, 
                       std::vector<double>& midPrices,
                       const ParameterSet& params) {
    
    double bid = data.Bid;
    double ask = data.Ask;
    double mid_price = 0.5 * (bid + ask);
    double spread = ask - bid;
    
    // Store the current mid price
    if (st.time_index >= 0 && st.time_index < static_cast<int>(midPrices.size())) {
        midPrices[st.time_index] = mid_price;
    }
    
    // Compute rolling averages using the parameter values
    double short_avg = computeRollingAverage(midPrices, st.time_index, params.short_window);
    double long_avg = computeRollingAverage(midPrices, st.time_index, LONG_WINDOW);
    
    bool in_high_spread = (spread >= HIGH_SPREAD_THRESHOLD);
    int current_position = st.current_position;
    int order_quantity = 0;
    
    // Track previous high spread state
    static bool prev_in_high_spread = false;
    bool last_in_high_spread = prev_in_high_spread;
    prev_in_high_spread = in_high_spread;
    
    // 0) If in a position => check if short_avg turned from local extreme
    if(!std::isnan(short_avg) && st.in_position) {
        if(st.position_is_long) {
            // Long position
            if(short_avg > st.current_position_extreme) {
                st.current_position_extreme = short_avg;
            } else {
                if((st.current_position_extreme - short_avg) >= params.ma_turn_threshold) {
                    // Close position
                    order_quantity = -current_position;
                    st.in_position = false;
                    st.position_is_long = false;
                    st.current_position_extreme = 0.0;
                    st.holding_position_in_high_spread = false;
                    st.position_entry_index_in_hs = -1;
                    st.prev_short_avg_in_hs = 0.0;
                }
            }
        } else {
            // Short position
            if(short_avg < st.current_position_extreme) {
                st.current_position_extreme = short_avg;
            } else {
                if((short_avg - st.current_position_extreme) >= params.ma_turn_threshold) {
                    // Close position
                    order_quantity = -current_position;
                    st.in_position = false;
                    st.position_is_long = false;
                    st.current_position_extreme = 0.0;
                    st.holding_position_in_high_spread = false;
                    st.position_entry_index_in_hs = -1;
                    st.prev_short_avg_in_hs = 0.0;
                }
            }
        }
    }
    
    // 1) Just exited a high spread (last tick in HS, current not in HS)
    if(last_in_high_spread && !in_high_spread) {
        st.high_spread_exit_index = st.time_index - 1;
        if(!std::isnan(short_avg)) {
            st.last_high_spread_exit_short_avg = short_avg;
        } else {
            st.last_high_spread_exit_short_avg = mid_price;
        }
        st.waiting_for_signal = true;
    }
    
    // 2) If waited WAITING_PERIOD => check threshold for new entry
    if(st.waiting_for_signal) {
        int diff = st.time_index - st.high_spread_exit_index;
        if(diff >= params.waiting_period && current_position == 0 && !in_high_spread) {
            if(!std::isnan(short_avg) && !std::isnan(st.last_high_spread_exit_short_avg)) {
                double delta = std::fabs(short_avg - st.last_high_spread_exit_short_avg);
                if(delta >= params.hs_exit_change_threshold) {
                    if(mid_price > short_avg) {
                        // Buy (go long)
                        order_quantity = POSITION_SIZE;
                        st.in_position = true;
                        st.position_is_long = true;
                        st.current_position_extreme = short_avg;
                    } else if(mid_price < short_avg) {
                        // Sell (go short)
                        order_quantity = -POSITION_SIZE;
                        st.in_position = true;
                        st.position_is_long = false;
                        st.current_position_extreme = short_avg;
                    }
                    st.waiting_for_signal = false;
                }
            }
        }
    }
    
    // 3) If in high spread + have a position => close immediately (ignore bool)
    if(in_high_spread && current_position != 0) {
        if (HOLD_DURING_HIGH_SPREAD) {
            // Logic for holding during high spread (not tested, keeping this as placeholder)
            if (!st.holding_position_in_high_spread && last_in_high_spread != in_high_spread) {
                st.holding_position_in_high_spread = true;
                st.position_entry_index_in_hs = st.time_index;
                st.prev_short_avg_in_hs = short_avg;
            } else {
                if (!std::isnan(short_avg) && !std::isnan(st.prev_short_avg_in_hs)) {
                    bool turned_against_us = false;
                    if (current_position > 0) {
                        if (short_avg < st.prev_short_avg_in_hs) {
                            turned_against_us = true;
                        }
                    } else {
                        if (short_avg > st.prev_short_avg_in_hs) {
                            turned_against_us = true;
                        }
                    }
                    
                    if (turned_against_us) {
                        order_quantity = -current_position;
                        st.in_position = false;
                        st.position_is_long = false;
                        st.current_position_extreme = 0.0;
                        st.holding_position_in_high_spread = false;
                        st.position_entry_index_in_hs = -1;
                        st.prev_short_avg_in_hs = 0.0;
                    } else {
                        st.prev_short_avg_in_hs = short_avg;
                    }
                }
            }
        } else {
            // Just close immediately
            order_quantity = -current_position;
            st.in_position = false;
            st.position_is_long = false;
            st.current_position_extreme = 0.0;
            st.holding_position_in_high_spread = false;
            st.position_entry_index_in_hs = -1;
            st.prev_short_avg_in_hs = 0.0;
        }
    }
    
    return order_quantity;
}

// Backtest runner function - equivalent to runBacktest
BacktestResult runBacktest(const std::vector<PriceData>& priceData, const ParameterSet& params, bool verbose = false) {
    StrategyState st = {};
    st.in_position = false;
    st.position_is_long = false;
    st.waiting_for_signal = false;
    st.holding_position_in_high_spread = false;
    st.high_spread_exit_index = -1;
    st.position_entry_index_in_hs = -1;
    st.last_high_spread_exit_short_avg = 0.0;
    st.prev_short_avg_in_hs = 0.0;
    st.current_position_extreme = 0.0;
    
    st.current_position = 0;
    st.cash = 0.0;
    st.total_fees = 0.0;
    st.time_index = 0;
    
    // Store midPrices for rolling average calculations
    std::vector<double> midPrices(priceData.size(), 0.0);
    
    const int position_limit = 100;
    const double fees_rate = 0.002; // 0.2%
    
    if (verbose) {
        std::cout << "Running backtest with parameters:" << std::endl;
        std::cout << "  Short Window: " << params.short_window << std::endl;
        std::cout << "  Waiting Period: " << params.waiting_period << std::endl;
        std::cout << "  HS Exit Threshold: " << params.hs_exit_change_threshold << std::endl;
        std::cout << "  MA Turn Threshold: " << params.ma_turn_threshold << std::endl;
    }
    
    int n_timestamps = static_cast<int>(priceData.size());
    for(int i = 0; i < n_timestamps; i++) {
        st.time_index = i;
        
        int quant = getOrdersWithParams(priceData[i], st, midPrices, params);
        
        if(quant != 0) {
            // Check position limit
            if(quant > 0) {
                // Buying
                if(st.current_position + quant > position_limit) {
                    if (verbose) {
                        std::cout << "[LOG] Attempted buy beyond limit for UEC, ignoring." << std::endl;
                    }
                    quant = 0;
                }
                
                if (quant > 0) {
                    double cost = priceData[i].Ask * quant * (1.0 + fees_rate);
                    st.cash -= cost;
                    double fees_incurred = priceData[i].Ask * quant * fees_rate;
                    st.total_fees += fees_incurred;
                    if (verbose) {
                        std::cout << "[LOG] Buying " << quant << " of UEC at " 
                                << std::fixed << std::setprecision(3) << priceData[i].Ask 
                                << "; Fees = " << std::fixed << std::setprecision(3) << fees_incurred << std::endl;
                    }
                }
            } else {
                // Selling
                if(st.current_position + quant < -position_limit) {
                    if (verbose) {
                        std::cout << "[LOG] Attempted sell beyond limit for UEC, ignoring." << std::endl;
                    }
                    quant = 0;
                }
                
                if (quant < 0) {
                    double revenue = priceData[i].Bid * (-quant) * (1.0 - fees_rate);
                    st.cash += revenue;
                    double fees_incurred = priceData[i].Bid * (-quant) * fees_rate;
                    st.total_fees += fees_incurred;
                    if (verbose) {
                        std::cout << "[LOG] Selling " << -quant << " of UEC at " 
                                << std::fixed << std::setprecision(3) << priceData[i].Bid 
                                << "; Fees = " << std::fixed << std::setprecision(3) << fees_incurred << std::endl;
                    }
                }
            }
            
            st.current_position += quant;
        }
    }
    
    // Close out any remaining position
    if (verbose) {
        std::cout << "\n=== Closing Any Open Positions ===" << std::endl;
        std::cout << "[INFO] UEC unclosed before final close: PnL = " 
                << std::fixed << std::setprecision(2) << st.cash 
                << ", Position = " << st.current_position << std::endl;
    }
    
    if(st.current_position > 0) {
        double final_sell_amount = priceData.back().Bid * st.current_position * (1.0 - fees_rate);
        st.cash += final_sell_amount;
        double fees_incurred = priceData.back().Bid * st.current_position * fees_rate;
        st.total_fees += fees_incurred;
        if (verbose) {
            std::cout << "[LOG] Final close SELL " << st.current_position 
                    << " UEC at " << std::fixed << std::setprecision(3) << priceData.back().Bid 
                    << "; Fees = " << std::fixed << std::setprecision(3) << fees_incurred << std::endl;
        }
        st.current_position = 0;
    } else if(st.current_position < 0) {
        double final_buy_amount = priceData.back().Ask * (-st.current_position) * (1.0 + fees_rate);
        st.cash -= final_buy_amount;
        double fees_incurred = priceData.back().Ask * (-st.current_position) * fees_rate;
        st.total_fees += fees_incurred;
        if (verbose) {
            std::cout << "[LOG] Final close BUY " << -st.current_position 
                    << " UEC at " << std::fixed << std::setprecision(3) << priceData.back().Ask 
                    << "; Fees = " << std::fixed << std::setprecision(3) << fees_incurred << std::endl;
        }
        st.current_position = 0;
    }
    
    if (verbose) {
        std::cout << "[INFO] UEC closed: PnL = " << std::fixed << std::setprecision(2) << st.cash << std::endl;
    }
    
    // Return both PnL and total fees
    BacktestResult result;
    result.pnl = st.cash;
    result.total_fees = st.total_fees;
    return result;
}

// Function to load price data from CSV
std::vector<PriceData> loadCSV(const std::string& filename) {
    std::vector<PriceData> data;
    std::ifstream file(filename);
    if(!file.is_open()) {
        std::cerr << "Error opening CSV: " << filename << std::endl;
        return data;
    }
    
    // Skip header
    std::string headerLine;
    if(std::getline(file, headerLine)) {
        // Header is ",Bids,Asks" for UEC.csv
    }
    
    std::string line;
    while(std::getline(file, line)) {
        std::stringstream ss(line);
        std::string indexStr, bidStr, askStr;
        
        // Skip the index column first
        if(!std::getline(ss, indexStr, ',')) continue;
        if(!std::getline(ss, bidStr, ',')) continue;
        if(!std::getline(ss, askStr)) continue;
        
        PriceData pd;
        pd.Bid = std::stod(bidStr);
        pd.Ask = std::stod(askStr);
        data.push_back(pd);
    }
    
    file.close();
    return data;
}

// Global variables for thread coordination
std::mutex resultMutex;
std::priority_queue<ParameterSet> bestResults;
std::atomic<int> completedTasks(0);
std::atomic<int> runningTasks(0);
int totalTasks = 0;

// Thread worker function for grid search
void workerThread(const std::vector<PriceData>& priceData, std::vector<ParameterSet> paramSets) {
    for (auto& params : paramSets) {
        if(params.short_window <= 0 || params.waiting_period <= 0) continue;
        
        runningTasks++;
        BacktestResult result = runBacktest(priceData, params);
        params.pnl = result.pnl;
        
        // Add to best results
        {
            std::lock_guard<std::mutex> lock(resultMutex);
            bestResults.push(params);
            // Keep only top 10 results
            if (bestResults.size() > 10) {
                // Create a new queue with just the top 10
                std::priority_queue<ParameterSet> newQueue;
                for (int i = 0; i < 10; i++) {
                    if (bestResults.empty()) break;
                    newQueue.push(bestResults.top());
                    bestResults.pop();
                }
                bestResults = std::move(newQueue);
            }
        }
        
        // Update progress
        completedTasks++;
        runningTasks--;
    }
}

// Function to print progress bar
void printProgressBar(int width, float progress) {
    std::cout << "[";
    int pos = width * progress;
    for (int i = 0; i < width; ++i) {
        if (i < pos) std::cout << "=";
        else if (i == pos) std::cout << ">";
        else std::cout << " ";
    }
    std::cout << "] " << int(progress * 100.0) << " % (Running: " << runningTasks << ")" << "\r";
    std::cout.flush();
}

// Function to display top results
void displayTopResults(int n = 3) {
    std::cout << "\nTop " << n << " parameter sets:" << std::endl;
    std::cout << std::setw(15) << "Short Window" 
              << std::setw(15) << "Wait Period" 
              << std::setw(15) << "HS Exit Thres" 
              << std::setw(15) << "MA Turn Thres" 
              << std::setw(15) << "PnL" << std::endl;
    
    // Copy queue to array to display in order
    std::vector<ParameterSet> topResults;
    std::priority_queue<ParameterSet> tempQueue = bestResults;
    
    while (!tempQueue.empty() && topResults.size() < n) {
        topResults.push_back(tempQueue.top());
        tempQueue.pop();
    }
    
    // Sort in descending order (highest PnL first)
    std::sort(topResults.begin(), topResults.end(), 
              [](const ParameterSet& a, const ParameterSet& b) { return a.pnl > b.pnl; });
    
    for (const auto& result : topResults) {
        std::cout << std::setw(15) << result.short_window
                  << std::setw(15) << result.waiting_period
                  << std::setw(15) << std::fixed << std::setprecision(4) << result.hs_exit_change_threshold
                  << std::setw(15) << std::fixed << std::setprecision(4) << result.ma_turn_threshold
                  << std::setw(15) << std::fixed << std::setprecision(2) << result.pnl << std::endl;
    }
    std::cout << std::endl;
}

// Main function
int main() {
    // 1. Load CSV data
    const std::string csvFile = "./data/UEC.csv";
    std::vector<PriceData> priceData = loadCSV(csvFile);
    
    if(priceData.empty()) {
        std::cerr << "No price data loaded. Exiting." << std::endl;
        return 1;
    }
    
    // First, run backtest with baseline parameters
    std::cout << "=== Testing Baseline Parameters ===" << std::endl;
    ParameterSet baselineParams;
    baselineParams.short_window = BASE_SHORT_WINDOW;
    baselineParams.waiting_period = BASE_WAITING_PERIOD;
    baselineParams.hs_exit_change_threshold = BASE_HS_EXIT_CHANGE_THRESHOLD;
    baselineParams.ma_turn_threshold = BASE_MA_TURN_THRESHOLD;
    
    BacktestResult baselineResult = runBacktest(priceData, baselineParams, true);
    
    std::cout << "\n=== Baseline Results ===" << std::endl;
    std::cout << "Short Window: " << baselineParams.short_window << std::endl;
    std::cout << "Waiting Period: " << baselineParams.waiting_period << std::endl;
    std::cout << "HS Exit Threshold: " << baselineParams.hs_exit_change_threshold << std::endl;
    std::cout << "MA Turn Threshold: " << baselineParams.ma_turn_threshold << std::endl;
    std::cout << "Total PnL = " << std::fixed << std::setprecision(2) << baselineResult.pnl << std::endl;
    std::cout << "Total Fees Paid = " << std::fixed << std::setprecision(2) << baselineResult.total_fees << std::endl;
    std::cout << std::endl;
    
    // Generate 31 variations per parameter (-15% to +15% in 1% increments)
    std::vector<ParameterSet> allParamSets;
    
    // Pre-calculate parameter values (31 values per parameter)
    std::vector<int> short_window_values;
    std::vector<int> waiting_period_values;
    std::vector<double> hs_exit_threshold_values;
    std::vector<double> ma_turn_threshold_values;
    
    // Generate parameter values
    for (int i = -15; i <= 15; i++) {
        double multiplier = 1.0 + (i / 100.0);
        
        short_window_values.push_back(static_cast<int>(BASE_SHORT_WINDOW * multiplier));
        waiting_period_values.push_back(static_cast<int>(BASE_WAITING_PERIOD * multiplier));
        hs_exit_threshold_values.push_back(BASE_HS_EXIT_CHANGE_THRESHOLD * multiplier);
        ma_turn_threshold_values.push_back(BASE_MA_TURN_THRESHOLD * multiplier);
    }
    
    // Generate all parameter combinations
    for (int sw : short_window_values) {
        for (int wp : waiting_period_values) {
            for (double hs : hs_exit_threshold_values) {
                for (double ma : ma_turn_threshold_values) {
                    ParameterSet params;
                    params.short_window = sw;
                    params.waiting_period = wp;
                    params.hs_exit_change_threshold = hs;
                    params.ma_turn_threshold = ma;
                    allParamSets.push_back(params);
                }
            }
        }
    }
    
    totalTasks = allParamSets.size();
    
    std::cout << "=== Starting Parameter Grid Search ===" << std::endl;
    std::cout << "Number of parameter combinations: " << totalTasks << std::endl;
    std::cout << "Parameter ranges:" << std::endl;
    std::cout << "  Short Window: " << short_window_values.front() << " to " << short_window_values.back() << std::endl;
    std::cout << "  Waiting Period: " << waiting_period_values.front() << " to " << waiting_period_values.back() << std::endl;
    std::cout << "  HS Exit Threshold: " << hs_exit_threshold_values.front() << " to " << hs_exit_threshold_values.back() << std::endl;
    std::cout << "  MA Turn Threshold: " << ma_turn_threshold_values.front() << " to " << ma_turn_threshold_values.back() << std::endl;
    
    // Get the number of threads to use
    unsigned int numThreads = std::thread::hardware_concurrency();
    if (numThreads == 0) numThreads = 4; // Default to 4 if can't detect
    
    std::cout << "Using " << numThreads << " threads" << std::endl;
    
    // Split work among threads
    std::vector<std::thread> threads;
    std::vector<std::vector<ParameterSet>> threadWorkloads(numThreads);
    
    for (size_t i = 0; i < allParamSets.size(); i++) {
        threadWorkloads[i % numThreads].push_back(allParamSets[i]);
    }
    
    // Start the threads
    auto start_time = std::chrono::high_resolution_clock::now();
    
    for (unsigned int i = 0; i < numThreads; i++) {
        threads.emplace_back(workerThread, std::ref(priceData), threadWorkloads[i]);
    }
    
    // Monitor progress and display top results
    const int progressBarWidth = 50;
    int lastPercent = 0;
    
    while (completedTasks < totalTasks) {
        float progress = static_cast<float>(completedTasks) / totalTasks;
        int currentPercent = static_cast<int>(progress * 100);
        
        printProgressBar(progressBarWidth, progress);
        
        // Display top 3 results every 1% or 0.1% if less than 10%
        if (currentPercent != lastPercent || 
            (currentPercent < 10 && static_cast<int>(progress * 1000) % 10 == 0)) {
            lastPercent = currentPercent;
            std::lock_guard<std::mutex> lock(resultMutex);
            if (!bestResults.empty()) {
                displayTopResults(3);
            }
        }
        
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }
    
    printProgressBar(progressBarWidth, 1.0);
    std::cout << std::endl;
    
    // Wait for all threads to complete
    for (auto& t : threads) {
        t.join();
    }
    
    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::seconds>(end_time - start_time).count();
    
    std::cout << "\n=== Grid Search Complete ===" << std::endl;
    std::cout << "Total time: " << duration << " seconds" << std::endl;
    
    // Display final top 10 results
    std::cout << "\nTop 10 parameter sets:" << std::endl;
    std::cout << std::setw(15) << "Short Window" 
              << std::setw(15) << "Wait Period" 
              << std::setw(15) << "HS Exit Thres" 
              << std::setw(15) << "MA Turn Thres" 
              << std::setw(15) << "PnL" << std::endl;
    
    // Copy queue to array to display in order
    std::vector<ParameterSet> topResults;
    while (!bestResults.empty()) {
        topResults.push_back(bestResults.top());
        bestResults.pop();
    }
    
    // Sort in descending order (highest PnL first)
    std::sort(topResults.begin(), topResults.end(), 
              [](const ParameterSet& a, const ParameterSet& b) { return a.pnl > b.pnl; });
    
    for (const auto& result : topResults) {
        std::cout << std::setw(15) << result.short_window
                  << std::setw(15) << result.waiting_period
                  << std::setw(15) << std::fixed << std::setprecision(4) << result.hs_exit_change_threshold
                  << std::setw(15) << std::fixed << std::setprecision(4) << result.ma_turn_threshold
                  << std::setw(15) << std::fixed << std::setprecision(2) << result.pnl << std::endl;
    }
    
    // Compare top 3 to baseline
    std::cout << "\n=== Top 3 vs Baseline ===" << std::endl;
    std::cout << std::setw(15) << "Parameters" 
              << std::setw(15) << "Short Window" 
              << std::setw(15) << "Wait Period" 
              << std::setw(15) << "HS Exit Thres" 
              << std::setw(15) << "MA Turn Thres" 
              << std::setw(15) << "PnL" 
              << std::setw(15) << "% Improvement" << std::endl;
    
    std::cout << std::setw(15) << "Baseline"
              << std::setw(15) << baselineParams.short_window
              << std::setw(15) << baselineParams.waiting_period
              << std::setw(15) << std::fixed << std::setprecision(4) << baselineParams.hs_exit_change_threshold
              << std::setw(15) << std::fixed << std::setprecision(4) << baselineParams.ma_turn_threshold
              << std::setw(15) << std::fixed << std::setprecision(2) << baselineResult.pnl
              << std::setw(15) << "0.00%" << std::endl;
    
    for (int i = 0; i < std::min(3, static_cast<int>(topResults.size())); i++) {
        double improvement = ((topResults[i].pnl - baselineResult.pnl) / std::abs(baselineResult.pnl)) * 100.0;
        
        std::cout << std::setw(15) << "Top " + std::to_string(i+1)
                  << std::setw(15) << topResults[i].short_window
                  << std::setw(15) << topResults[i].waiting_period
                  << std::setw(15) << std::fixed << std::setprecision(4) << topResults[i].hs_exit_change_threshold
                  << std::setw(15) << std::fixed << std::setprecision(4) << topResults[i].ma_turn_threshold
                  << std::setw(15) << std::fixed << std::setprecision(2) << topResults[i].pnl
                  << std::setw(15) << std::fixed << std::setprecision(2) << improvement << "%" << std::endl;
    }
    
    // Run the best parameter set once more with verbose output
    if (!topResults.empty()) {
        std::cout << "\n=== Running Best Parameter Set with Details ===" << std::endl;
        BacktestResult finalResult = runBacktest(priceData, topResults[0], true);
        
        std::cout << "\n=== Final Report for Best Parameters ===" << std::endl;
        std::cout << "Total PnL = " << std::fixed << std::setprecision(2) << finalResult.pnl << std::endl;
        std::cout << "Total Fees Paid = " << std::fixed << std::setprecision(2) << finalResult.total_fees << std::endl;
        
        double improvement = ((finalResult.pnl - baselineResult.pnl) / std::abs(baselineResult.pnl)) * 100.0;
        
        std::cout << "Baseline PnL = " << std::fixed << std::setprecision(2) << baselineResult.pnl << std::endl;
        std::cout << "Improvement = " << std::fixed << std::setprecision(2) << improvement << "%" << std::endl;
    }
    
    return 0;
} 