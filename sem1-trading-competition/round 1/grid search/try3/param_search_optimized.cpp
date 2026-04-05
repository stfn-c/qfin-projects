#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <cmath>
#include <limits>
#include <algorithm>
#include <iomanip>
#include <thread>
#include <mutex>
#include <queue>
#include <chrono>
#include <atomic>

// Constants from PanicTrader.py with ranges for searching
const int BASE_SHORT_WINDOW = 80;
const int BASE_WAITING_PERIOD = 80;
const double BASE_HS_EXIT_CHANGE_THRESHOLD = 0.2;
const double BASE_MA_TURN_THRESHOLD = 0.9;

// Fixed parameters
const int LONG_WINDOW = 500;
const double HIGH_SPREAD_THRESHOLD = 1.3;
const int POSITION_SIZE = 100;
const bool HOLD_DURING_HIGH_SPREAD = false;

// Data structures
struct PriceData {
    double Bid;
    double Ask;
};

struct BacktestResult {
    double pnl;
    double total_fees;
};

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

// Global variables for thread coordination
std::mutex resultMutex;
std::priority_queue<ParameterSet> bestResults;
std::atomic<int> completedTasks(0);
std::atomic<int> runningTasks(0);
int totalTasks = 0;

// Optimized function to compute rolling average
double computeRollingAverage(const std::vector<double>& midPrices, int endIndex, int windowSize) {
    int startIndex = endIndex - windowSize + 1;
    if(startIndex < 0) return std::numeric_limits<double>::quiet_NaN();
    
    double sum = 0.0;
    for(int i = startIndex; i <= endIndex; i++) {
        sum += midPrices[i];
    }
    return sum / windowSize;
}

// Core strategy logic, optimized for performance
int getOrders(const PriceData& data, int timeIndex, int& currentPosition, double& cash, double& totalFees,
              std::vector<double>& midPrices, const ParameterSet& params,
              bool& in_position, bool& position_is_long, bool& waiting_for_signal,
              int& high_spread_exit_index, double& last_high_spread_exit_short_avg,
              double& current_position_extreme, bool& prev_in_high_spread) {
    double bid = data.Bid;
    double ask = data.Ask;
    double mid_price = 0.5 * (bid + ask);
    double spread = ask - bid;
    
    // Store the current mid price
    midPrices[timeIndex] = mid_price;
    
    // Compute rolling averages with the parameter set
    double short_avg = computeRollingAverage(midPrices, timeIndex, params.short_window);
    
    // Skip if not enough data points
    if(std::isnan(short_avg)) return 0;
    
    bool in_high_spread = (spread >= HIGH_SPREAD_THRESHOLD);
    int order_quantity = 0;
    
    // 0) If in a position => check if short_avg turned from local extreme
    if(in_position) {
        if(position_is_long) {
            if(short_avg > current_position_extreme) {
                current_position_extreme = short_avg;
            } else {
                if((current_position_extreme - short_avg) >= params.ma_turn_threshold) {
                    // early exit => close
                    order_quantity = -currentPosition;
                    
                    // Reset state
                    in_position = false;
                    position_is_long = false;
                    current_position_extreme = 0.0;
                }
            }
        } else {
            // short
            if(short_avg < current_position_extreme) {
                current_position_extreme = short_avg;
            } else {
                if((short_avg - current_position_extreme) >= params.ma_turn_threshold) {
                    order_quantity = -currentPosition;
                    
                    // Reset state
                    in_position = false;
                    position_is_long = false;
                    current_position_extreme = 0.0;
                }
            }
        }
    }

    // 1) Just exited a high spread
    if(prev_in_high_spread && !in_high_spread) {
        high_spread_exit_index = timeIndex;
        if(!std::isnan(short_avg)) {
            last_high_spread_exit_short_avg = short_avg;
        } else {
            last_high_spread_exit_short_avg = mid_price;
        }
        waiting_for_signal = true;
    }
    prev_in_high_spread = in_high_spread;

    // 2) waited WAITING_PERIOD => check threshold
    if(waiting_for_signal) {
        int diff = timeIndex - high_spread_exit_index;
        if(diff >= params.waiting_period && currentPosition == 0 && !in_high_spread) {
            if(!std::isnan(short_avg) && !std::isnan(last_high_spread_exit_short_avg)) {
                double delta = std::fabs(short_avg - last_high_spread_exit_short_avg);
                if(delta >= params.hs_exit_change_threshold) {
                    // normal logic
                    if(mid_price > short_avg) {
                        order_quantity = POSITION_SIZE; // buy
                        in_position = true;
                        position_is_long = true;
                        current_position_extreme = short_avg;
                    } else if(mid_price < short_avg) {
                        order_quantity = -POSITION_SIZE; // sell
                        in_position = true;
                        position_is_long = false;
                        current_position_extreme = short_avg;
                    }
                    waiting_for_signal = false;
                }
            }
        }
    }

    // 3) If in high spread + have position => immediate close
    if(in_high_spread && currentPosition != 0) {
        order_quantity = -currentPosition;
        in_position = false;
        position_is_long = false;
        current_position_extreme = 0.0;
    }

    return order_quantity;
}

BacktestResult runBacktest(const std::vector<PriceData>& priceData, const ParameterSet& params, bool verbose = false) {
    // Initialize strategy state
    bool in_position = false;
    bool position_is_long = false;
    bool waiting_for_signal = false;
    bool holding_position_in_high_spread = false;
    int high_spread_exit_index = -1;
    int position_entry_index_in_hs = -1;
    double last_high_spread_exit_short_avg = 0.0;
    double prev_short_avg_in_hs = 0.0;
    double current_position_extreme = 0.0;
    
    int currentPosition = 0;
    double cash = 0.0;
    double totalFees = 0.0;
    
    // Pre-allocate vector for midPrices
    std::vector<double> midPrices(priceData.size(), 0.0);
    
    // Track previous high spread state between iterations
    bool prev_in_high_spread = false;
    
    if (verbose) {
        std::cout << "Running backtest with parameters:" << std::endl;
        std::cout << "  Short Window: " << params.short_window << std::endl;
        std::cout << "  Waiting Period: " << params.waiting_period << std::endl;
        std::cout << "  HS Exit Threshold: " << params.hs_exit_change_threshold << std::endl;
        std::cout << "  MA Turn Threshold: " << params.ma_turn_threshold << std::endl;
    }
    
    const double fees_rate = 0.002; // 0.2%
    const int position_limit = 100;
    
    // Run through all price data
    for(size_t i = 0; i < priceData.size(); i++) {
        double bid = priceData[i].Bid;
        double ask = priceData[i].Ask;
        double mid_price = 0.5 * (bid + ask);
        double spread = ask - bid;
        
        // Store the current mid price
        midPrices[i] = mid_price;
        
        // Compute rolling average with the parameter set
        double short_avg = computeRollingAverage(midPrices, i, params.short_window);
        
        // Skip if not enough data points
        if(std::isnan(short_avg)) continue;
        
        bool in_high_spread = (spread >= HIGH_SPREAD_THRESHOLD);
        int order_quantity = 0;
        
        // 0) If in a position => check if short_avg turned from local extreme
        if(in_position) {
            if(position_is_long) {
                if(short_avg > current_position_extreme) {
                    current_position_extreme = short_avg;
                } else {
                    if((current_position_extreme - short_avg) >= params.ma_turn_threshold) {
                        // early exit => close
                        order_quantity = -currentPosition;
                        
                        // Reset state
                        in_position = false;
                        position_is_long = false;
                        current_position_extreme = 0.0;
                    }
                }
            } else {
                // short
                if(short_avg < current_position_extreme) {
                    current_position_extreme = short_avg;
                } else {
                    if((short_avg - current_position_extreme) >= params.ma_turn_threshold) {
                        order_quantity = -currentPosition;
                        
                        // Reset state
                        in_position = false;
                        position_is_long = false;
                        current_position_extreme = 0.0;
                    }
                }
            }
        }

        // 1) Just exited a high spread
        if(prev_in_high_spread && !in_high_spread) {
            high_spread_exit_index = i;
            if(!std::isnan(short_avg)) {
                last_high_spread_exit_short_avg = short_avg;
            } else {
                last_high_spread_exit_short_avg = mid_price;
            }
            waiting_for_signal = true;
        }
        prev_in_high_spread = in_high_spread;

        // 2) waited WAITING_PERIOD => check threshold
        if(waiting_for_signal) {
            int diff = i - high_spread_exit_index;
            if(diff >= params.waiting_period && currentPosition == 0 && !in_high_spread) {
                if(!std::isnan(short_avg) && !std::isnan(last_high_spread_exit_short_avg)) {
                    double delta = std::fabs(short_avg - last_high_spread_exit_short_avg);
                    if(delta >= params.hs_exit_change_threshold) {
                        // normal logic
                        if(mid_price > short_avg) {
                            order_quantity = POSITION_SIZE; // buy
                            in_position = true;
                            position_is_long = true;
                            current_position_extreme = short_avg;
                        } else if(mid_price < short_avg) {
                            order_quantity = -POSITION_SIZE; // sell
                            in_position = true;
                            position_is_long = false;
                            current_position_extreme = short_avg;
                        }
                        waiting_for_signal = false;
                    }
                }
            }
        }

        // 3) If in high spread + have position => immediate close
        if(in_high_spread && currentPosition != 0) {
            order_quantity = -currentPosition;
            in_position = false;
            position_is_long = false;
            current_position_extreme = 0.0;
        }
        
        // Process the order
        if(order_quantity != 0) {
            // Check position limit
            if(order_quantity > 0) {
                // Buying
                if(currentPosition + order_quantity > position_limit) {
                    if (verbose) {
                        std::cout << "[LOG] Attempted buy beyond limit for UEC, ignoring." << std::endl;
                    }
                    order_quantity = 0;
                }
                
                if (order_quantity > 0) {
                    double cost = ask * order_quantity * (1.0 + fees_rate);
                    cash -= cost;
                    double fees_incurred = ask * order_quantity * fees_rate;
                    totalFees += fees_incurred;
                    
                    if (verbose) {
                        std::cout << "[LOG] Buying " << order_quantity << " of UEC at " 
                                << std::fixed << std::setprecision(3) << ask 
                                << "; Fees = " << std::fixed << std::setprecision(3) << fees_incurred << std::endl;
                    }
                }
            } else {
                // Selling
                if(currentPosition + order_quantity < -position_limit) {
                    if (verbose) {
                        std::cout << "[LOG] Attempted sell beyond limit for UEC, ignoring." << std::endl;
                    }
                    order_quantity = 0;
                }
                
                if (order_quantity < 0) {
                    double revenue = bid * (-order_quantity) * (1.0 - fees_rate);
                    cash += revenue;
                    double fees_incurred = bid * (-order_quantity) * fees_rate;
                    totalFees += fees_incurred;
                    
                    if (verbose) {
                        std::cout << "[LOG] Selling " << -order_quantity << " of UEC at " 
                                << std::fixed << std::setprecision(3) << bid 
                                << "; Fees = " << std::fixed << std::setprecision(3) << fees_incurred << std::endl;
                    }
                }
            }
            
            currentPosition += order_quantity;
        }
    }
    
    // Final close
    if (verbose) {
        std::cout << "\n=== Closing Any Open Positions ===" << std::endl;
        std::cout << "[INFO] UEC unclosed before final close: PnL = " 
                << std::fixed << std::setprecision(2) << cash 
                << ", Position = " << currentPosition << std::endl;
    }
    
    if(currentPosition > 0) {
        double finalBid = priceData.back().Bid;
        double final_sell_amount = finalBid * currentPosition * (1.0 - fees_rate);
        cash += final_sell_amount;
        double fees_incurred = finalBid * currentPosition * fees_rate;
        totalFees += fees_incurred;
        
        if (verbose) {
            std::cout << "[LOG] Final close SELL " << currentPosition 
                    << " UEC at " << std::fixed << std::setprecision(3) << finalBid 
                    << "; Fees = " << std::fixed << std::setprecision(3) << fees_incurred << std::endl;
        }
        currentPosition = 0;
    }
    else if(currentPosition < 0) {
        double finalAsk = priceData.back().Ask;
        double final_buy_amount = finalAsk * (-currentPosition) * (1.0 + fees_rate);
        cash -= final_buy_amount;
        double fees_incurred = finalAsk * (-currentPosition) * fees_rate;
        totalFees += fees_incurred;
        
        if (verbose) {
            std::cout << "[LOG] Final close BUY " << -currentPosition 
                    << " UEC at " << std::fixed << std::setprecision(3) << finalAsk 
                    << "; Fees = " << std::fixed << std::setprecision(3) << fees_incurred << std::endl;
        }
        currentPosition = 0;
    }
    
    if (verbose) {
        std::cout << "[INFO] UEC closed: PnL = " << std::fixed << std::setprecision(2) << cash << std::endl;
    }
    
    BacktestResult result;
    result.pnl = cash;
    result.total_fees = totalFees;
    
    if (verbose) {
        std::cout << "Final PnL: " << std::fixed << std::setprecision(2) << cash << std::endl;
        std::cout << "Total Fees: " << std::fixed << std::setprecision(2) << totalFees << std::endl;
    }
    
    return result;
}

// Load CSV data optimized for performance
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
    // Load CSV data
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