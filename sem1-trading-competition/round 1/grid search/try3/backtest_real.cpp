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

// Constants from PanicTrader.py
const int SHORT_WINDOW = 80;
const int LONG_WINDOW = 500;
const int WAITING_PERIOD = 80;
const double HIGH_SPREAD_THRESHOLD = 1.3;
const int POSITION_SIZE = 100;
const double HS_EXIT_CHANGE_THRESHOLD = 0.2;
const bool HOLD_DURING_HIGH_SPREAD = false;
const double MA_TURN_THRESHOLD = 0.9;

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

// Core strategy logic, equivalent to getOrders in PanicTrader.py
int getOrders(const PriceData& data, 
              StrategyState& st, 
              std::vector<double>& midPrices) {
    
    double bid = data.Bid;
    double ask = data.Ask;
    double mid_price = 0.5 * (bid + ask);
    double spread = ask - bid;
    
    // Store the current mid price
    if (st.time_index >= 0 && st.time_index < static_cast<int>(midPrices.size())) {
        midPrices[st.time_index] = mid_price;
    }
    
    // Compute rolling averages
    double short_avg = computeRollingAverage(midPrices, st.time_index, SHORT_WINDOW);
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
                if((st.current_position_extreme - short_avg) >= MA_TURN_THRESHOLD) {
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
                if((short_avg - st.current_position_extreme) >= MA_TURN_THRESHOLD) {
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
        if(diff >= WAITING_PERIOD && current_position == 0 && !in_high_spread) {
            if(!std::isnan(short_avg) && !std::isnan(st.last_high_spread_exit_short_avg)) {
                double delta = std::fabs(short_avg - st.last_high_spread_exit_short_avg);
                if(delta >= HS_EXIT_CHANGE_THRESHOLD) {
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
            // Close position immediately
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
BacktestResult runBacktest(const std::vector<PriceData>& priceData) {
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
    
    int n_timestamps = static_cast<int>(priceData.size());
    for(int i = 0; i < n_timestamps; i++) {
        st.time_index = i;
        
        int quant = getOrders(priceData[i], st, midPrices);
        
        if(quant != 0) {
            // Check position limit
            if(quant > 0) {
                // Buying
                if(st.current_position + quant > position_limit) {
                    std::cout << "[LOG] Attempted buy beyond limit for UEC, ignoring." << std::endl;
                    quant = 0;
                }
                
                if (quant > 0) {
                    double cost = priceData[i].Ask * quant * (1.0 + fees_rate);
                    st.cash -= cost;
                    double fees_incurred = priceData[i].Ask * quant * fees_rate;
                    st.total_fees += fees_incurred;
                    std::cout << "[LOG] Buying " << quant << " of UEC at " 
                              << std::fixed << std::setprecision(3) << priceData[i].Ask 
                              << "; Fees = " << std::fixed << std::setprecision(3) << fees_incurred << std::endl;
                }
            } else {
                // Selling
                if(st.current_position + quant < -position_limit) {
                    std::cout << "[LOG] Attempted sell beyond limit for UEC, ignoring." << std::endl;
                    quant = 0;
                }
                
                if (quant < 0) {
                    double revenue = priceData[i].Bid * (-quant) * (1.0 - fees_rate);
                    st.cash += revenue;
                    double fees_incurred = priceData[i].Bid * (-quant) * fees_rate;
                    st.total_fees += fees_incurred;
                    std::cout << "[LOG] Selling " << -quant << " of UEC at " 
                              << std::fixed << std::setprecision(3) << priceData[i].Bid 
                              << "; Fees = " << std::fixed << std::setprecision(3) << fees_incurred << std::endl;
                }
            }
            
            st.current_position += quant;
        }
    }
    
    // Close out any remaining position
    std::cout << "\n=== Closing Any Open Positions ===" << std::endl;
    std::cout << "[INFO] UEC unclosed before final close: PnL = " 
              << std::fixed << std::setprecision(2) << st.cash 
              << ", Position = " << st.current_position << std::endl;
    
    if(st.current_position > 0) {
        double final_sell_amount = priceData.back().Bid * st.current_position * (1.0 - fees_rate);
        st.cash += final_sell_amount;
        double fees_incurred = priceData.back().Bid * st.current_position * fees_rate;
        st.total_fees += fees_incurred;
        std::cout << "[LOG] Final close SELL " << st.current_position 
                  << " UEC at " << std::fixed << std::setprecision(3) << priceData.back().Bid 
                  << "; Fees = " << std::fixed << std::setprecision(3) << fees_incurred << std::endl;
        st.current_position = 0;
    } else if(st.current_position < 0) {
        double final_buy_amount = priceData.back().Ask * (-st.current_position) * (1.0 + fees_rate);
        st.cash -= final_buy_amount;
        double fees_incurred = priceData.back().Ask * (-st.current_position) * fees_rate;
        st.total_fees += fees_incurred;
        std::cout << "[LOG] Final close BUY " << -st.current_position 
                  << " UEC at " << std::fixed << std::setprecision(3) << priceData.back().Ask 
                  << "; Fees = " << std::fixed << std::setprecision(3) << fees_incurred << std::endl;
        st.current_position = 0;
    }
    
    std::cout << "[INFO] UEC closed: PnL = " << std::fixed << std::setprecision(2) << st.cash << std::endl;
    
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

// Main function
int main() {
    // 1. Load CSV data
    const std::string csvFile = "./data/UEC.csv";
    std::vector<PriceData> priceData = loadCSV(csvFile);
    
    if(priceData.empty()) {
        std::cerr << "No price data loaded. Exiting." << std::endl;
        return 1;
    }
    
    std::cout << "=== Starting Backtest ===" << std::endl;
    std::cout << "Products: [UEC]" << std::endl;
    std::cout << "Number of timestamps: " << priceData.size() << std::endl;
    std::cout << "Position limit: 100" << std::endl;
    std::cout << "Fees rate: 0.002" << std::endl;
    
    // 2. Run backtest
    BacktestResult result = runBacktest(priceData);
    
    // 3. Output final results
    std::cout << "\n=== Final Report ===" << std::endl;
    std::cout << "Total PnL = " << std::fixed << std::setprecision(2) << result.pnl << std::endl;
    std::cout << "Total Fees Paid = " << std::fixed << std::setprecision(2) << result.total_fees << std::endl;
    
    return 0;
} 