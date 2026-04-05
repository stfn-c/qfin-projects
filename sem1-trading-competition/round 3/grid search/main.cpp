#include <iostream>
#include <vector>
#include <string>
#include <map>
#include <deque>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <algorithm>
#include <optional>
#include <tuple>
#include <limits>
#include <thread>
#include <future>
#include <mutex> // For protecting shared resources if any (primarily for collecting results)
#include <numeric> // For std::accumulate
#include <cmath>   // For std::isnan

// --- Constants ---
const std::string VP_SYMBOL = "VP";
const std::vector<std::string> COMPONENT_SYMBOLS = {"SHEEP", "ORE", "WHEAT"};
const std::string DATA_LOCATION = "./data"; // Relative path to data files

// --- Helper Structures ---
struct PriceData {
    double bid;
    double ask;
    long long timestamp; // Assuming timestamp is part of the data row eventually
};

struct MarketSnapshot {
    std::map<std::string, std::map<std::string, double>> data;
    // e.g., data["VP"]["Bid"] = 100.0; data["VP"]["Timestamp"] = 12345;
};

struct TradeSignalInfo {
    long long timestamp;
    std::string type; // "BUY" or "SELL"
    double price;
    int quantity;
    double diff_ma_at_signal;
};

struct FuzzParams {
    int rolling_avg_window;
    double positive_diff_ma_threshold;
    double negative_diff_ma_threshold;
    int fixed_order_quantity;

    // For reporting
    bool operator<(const FuzzParams& other) const { // For map keys if needed
        if (rolling_avg_window != other.rolling_avg_window) return rolling_avg_window < other.rolling_avg_window;
        if (positive_diff_ma_threshold != other.positive_diff_ma_threshold) return positive_diff_ma_threshold < other.positive_diff_ma_threshold;
        if (negative_diff_ma_threshold != other.negative_diff_ma_threshold) return negative_diff_ma_threshold < other.negative_diff_ma_threshold;
        return fixed_order_quantity < other.fixed_order_quantity;
    }
};

struct BacktestResult {
    FuzzParams params;
    double pnl;
};


// --- TradingAlgorithm Class ---
class TradingAlgorithm {
public:
    std::map<std::string, int> positions; // Current positions, updated by backtester

    // Parameters (can be set by constructor for fuzzing)
    int rolling_avg_window;
    double positive_diff_ma_threshold;
    double negative_diff_ma_threshold;
    int fixed_order_quantity;

    // Fixed model parameters (from Python)
    std::map<std::string, double> ratios;
    double intercept;
    std::string etf_symbol;
    std::vector<std::string> component_symbols_list; // Renamed to avoid conflict

    // Internal state
    std::deque<double> difference_history;

    // Data for plotting/reporting (populated during getOrders)
    std::vector<long long> timestamps_history;
    std::map<std::string, std::vector<double>> price_history; // Mid-prices
    std::vector<double> expected_vp_price_history;
    std::vector<double> diff_ma_history;
    std::vector<TradeSignalInfo> trade_signals_history;
    std::vector<int> position_history_vp;
    std::vector<double> raw_difference_plot_history;


    TradingAlgorithm(
        int ravg_w, double pos_thresh, double neg_thresh, int order_qty,
        const std::map<std::string, double>& initial_ratios, double initial_intercept,
        const std::string& etf_sym, const std::vector<std::string>& comp_syms
    ) : rolling_avg_window(ravg_w),
        positive_diff_ma_threshold(pos_thresh),
        negative_diff_ma_threshold(neg_thresh),
        fixed_order_quantity(order_qty),
        ratios(initial_ratios),
        intercept(initial_intercept),
        etf_symbol(etf_sym),
        component_symbols_list(comp_syms)
    {
        difference_history = std::deque<double>(); // Maxlen handled by check before use
        for(const auto& sym : comp_syms) {
            price_history[sym] = {};
        }
        price_history[etf_sym] = {};
    }
    
    void reset_internal_state() {
        difference_history.clear();
        timestamps_history.clear();
        for(auto& pair_val : price_history) {
            pair_val.second.clear();
        }
        expected_vp_price_history.clear();
        diff_ma_history.clear();
        trade_signals_history.clear();
        position_history_vp.clear();
        raw_difference_plot_history.clear();
        // positions map is managed by the backtester externally and set via set_current_positions
    }

    // To be called by backtester before getOrders
    void set_current_positions(const std::map<std::string, int>& current_positions) {
        this->positions = current_positions;
    }

    std::optional<double> _get_mid_price(
        const std::string& product,
        const std::map<std::string, std::map<std::string, double>>& current_data
    ) {
        auto it_product = current_data.find(product);
        if (it_product == current_data.end()) {
            return std::nullopt;
        }

        const auto& product_info = it_product->second;
        auto it_bid = product_info.find("Bid");
        auto it_ask = product_info.find("Ask");

        if (it_bid != product_info.end() && it_ask != product_info.end()) {
            double bid = it_bid->second;
            double ask = it_ask->second;
            if (bid > 0 && ask > 0) { // Ensure prices are valid
                return (bid + ask) / 2.0;
            }
        }
        return std::nullopt;
    }

    // order_data is an out-parameter, populated by this function
    void getOrders(
        const std::map<std::string, std::map<std::string, double>>& current_data_snapshot,
        std::map<std::string, int>& orders_to_place // Output: orders to place for each product
    ) {
        orders_to_place.clear(); // Start with no orders

        long long current_timestamp = -1;
        if (current_data_snapshot.count(etf_symbol) && current_data_snapshot.at(etf_symbol).count("Timestamp")) {
             current_timestamp = static_cast<long long>(current_data_snapshot.at(etf_symbol).at("Timestamp"));
        }


        std::optional<double> vp_price_opt = _get_mid_price(etf_symbol, current_data_snapshot);
        if (!vp_price_opt) return; // Cannot proceed without VP price
        double vp_price = *vp_price_opt;

        std::map<std::string, double> component_mid_prices;
        for (const auto& sym : component_symbols_list) {
            std::optional<double> price_opt = _get_mid_price(sym, current_data_snapshot);
            if (!price_opt) return; // Cannot proceed if any component price is missing
            component_mid_prices[sym] = *price_opt;
        }

        double expected_vp_price = intercept;
        for (const auto& sym : component_symbols_list) {
            expected_vp_price += ratios[sym] * component_mid_prices[sym];
        }

        double raw_difference = vp_price - expected_vp_price;
        
        difference_history.push_back(raw_difference);
        if (difference_history.size() > static_cast<size_t>(rolling_avg_window) && rolling_avg_window > 0) {
            difference_history.pop_front();
        }

        // Record data for plotting/analysis if timestamp is valid
        if (current_timestamp != -1) {
            timestamps_history.push_back(current_timestamp);
            price_history[etf_symbol].push_back(vp_price);
            for (const auto& sym : component_symbols_list) {
                price_history[sym].push_back(component_mid_prices[sym]);
            }
            expected_vp_price_history.push_back(expected_vp_price);
            
            auto pos_it = positions.find(etf_symbol);
            position_history_vp.push_back(pos_it != positions.end() ? pos_it->second : 0);
            
            raw_difference_plot_history.push_back(raw_difference);
        }


        if (difference_history.size() < static_cast<size_t>(rolling_avg_window)) {
            if (current_timestamp != -1) {
                 diff_ma_history.push_back(std::nan("")); // Not enough data for MA
            }
            return; // Not enough data for MA calculation
        }

        double sum_diff = 0;
        for(double diff : difference_history) sum_diff += diff;
        double current_diff_ma = sum_diff / difference_history.size();
        
        if (current_timestamp != -1) {
            diff_ma_history.push_back(current_diff_ma);
        }


        int order_quantity_for_vp = 0;
        if (current_diff_ma > positive_diff_ma_threshold) { // VP likely overpriced
            order_quantity_for_vp = -fixed_order_quantity;
            if (current_timestamp != -1) {
                 trade_signals_history.push_back({current_timestamp, "SELL", vp_price, order_quantity_for_vp, current_diff_ma});
            }
        } else if (current_diff_ma < negative_diff_ma_threshold) { // VP likely underpriced
            order_quantity_for_vp = fixed_order_quantity;
            if (current_timestamp != -1) {
                trade_signals_history.push_back({current_timestamp, "BUY", vp_price, order_quantity_for_vp, current_diff_ma});
            }
        }

        if (order_quantity_for_vp != 0) {
            orders_to_place[etf_symbol] = order_quantity_for_vp;
        }
    }

    void export_data_to_csv(const std::string& market_data_filename, const std::string& signals_filename) {
        // Export market data
        std::ofstream market_file(market_data_filename);
        if (!market_file.is_open()) {
            std::cerr << "Error: Could not open market data CSV file for writing: " << market_data_filename << std::endl;
            return;
        }

        market_file << "Timestamp,VP_Price,Expected_VP_Price,Diff_MA,Raw_Difference,VP_Position";
        for (const auto& sym : component_symbols_list) {
            market_file << "," << sym << "_Price";
        }
        market_file << "\n";

        for (size_t i = 0; i < timestamps_history.size(); ++i) {
            market_file << timestamps_history[i]
                        << "," << (price_history[etf_symbol].size() > i ? std::to_string(price_history[etf_symbol][i]) : "N/A")
                        << "," << (expected_vp_price_history.size() > i ? std::to_string(expected_vp_price_history[i]) : "N/A")
                        << "," << (diff_ma_history.size() > i ? (std::isnan(diff_ma_history[i]) ? "N/A" : std::to_string(diff_ma_history[i])) : "N/A")
                        << "," << (raw_difference_plot_history.size() > i ? std::to_string(raw_difference_plot_history[i]) : "N/A")
                        << "," << (position_history_vp.size() > i ? std::to_string(position_history_vp[i]) : "N/A");
            for (const auto& sym : component_symbols_list) {
                market_file << "," << (price_history[sym].size() > i ? std::to_string(price_history[sym][i]) : "N/A");
            }
            market_file << "\n";
        }
        market_file.close();
        std::cout << "Market data exported to " << market_data_filename << std::endl;

        // Export trade signals
        std::ofstream signals_file(signals_filename);
         if (!signals_file.is_open()) {
            std::cerr << "Error: Could not open signals CSV file for writing: " << signals_filename << std::endl;
            return;
        }
        signals_file << "Timestamp,Signal_Type,Price,Quantity,Diff_MA_At_Signal\n";
        for (const auto& signal : trade_signals_history) {
            signals_file << signal.timestamp << "," << signal.type << "," << signal.price
                         << "," << signal.quantity << "," << signal.diff_ma_at_signal << "\n";
        }
        signals_file.close();
        std::cout << "Trade signals exported to " << signals_filename << std::endl;
    }
};

// --- Function to Export Fuzzing PnL Results ---
void export_fuzzing_pnl_results(const std::vector<BacktestResult>& all_results, const std::string& filename) {
    std::ofstream outfile(filename);
    if (!outfile.is_open()) {
        std::cerr << "Error: Could not open file for writing fuzzing PnL results: " << filename << std::endl;
        return;
    }

    // Write header
    outfile << "RollingAvgWindow,PositiveDiffMAThreshold,NegativeDiffMAThreshold,FixedOrderQuantity,PnL\\n";

    // Write data
    // Ensure PnL is written with sufficient precision, similar to console output.
    // Using std::fixed and std::setprecision for consistency if needed,
    // but default to_string precision for double is often sufficient for CSV.
    outfile << std::fixed << std::setprecision(5); 

    for (const auto& res : all_results) {
        outfile << res.params.rolling_avg_window << ","
                << res.params.positive_diff_ma_threshold << ","
                << res.params.negative_diff_ma_threshold << ","
                << res.params.fixed_order_quantity << ","
                << res.pnl << "\\n";
    }

    outfile.close();
    std::cout << "Fuzzing PnL results exported to " << filename << std::endl;
}


// --- CSV Parsing Logic ---
// Reads a CSV file for a single product. Expects "Bids,Asks" after header.
std::vector<PriceData> load_product_csv(const std::string& product_name) {
    std::vector<PriceData> data_series;
    std::string filepath = DATA_LOCATION + "/" + product_name + ".csv";
    std::ifstream file(filepath);

    if (!file.is_open()) {
        std::cerr << "Error: Could not open data file " << filepath << std::endl;
        return data_series; // Return empty if file error
    }

    std::string line;
    long long current_ts = 0;
    bool header_skipped = false;

    while (std::getline(file, line)) {
        if (!header_skipped) { // Skip the header line (e.g., ",Bids,Asks")
            header_skipped = true;
            continue;
        }
        if (line.empty() || line.find_first_not_of(',') == std::string::npos) continue; // Skip empty or only-comma lines


        std::stringstream ss(line);
        std::string segment;
        std::vector<std::string> segments;

        while(std::getline(ss, segment, ',')) {
           segments.push_back(segment);
        }
        
        // Expecting format: (optional index), Bids, Asks
        // If index is present and first: segments[0] = index, segments[1]=bid, segments[2]=ask
        // If index is implicit (like example data): segments[0]=bid, segments[1]=ask (after first non-data char)
        // The example has ",Bids,Asks" then "0,bid_val,ask_val". So segments[0] is index.
        if (segments.size() >= 3) { // Assuming index, bid, ask
            try {
                // Skip segments[0] as it's the index, we use current_ts
                double bid = std::stod(segments[1]);
                double ask = std::stod(segments[2]);
                data_series.push_back({bid, ask, current_ts++});
            } catch (const std::invalid_argument& ia) {
                std::cerr << "Warning: Invalid number format in " << filepath << " at line: " << line << std::endl;
            } catch (const std::out_of_range& oor) {
                std::cerr << "Warning: Number out of range in " << filepath << " at line: " << line << std::endl;
            }
        } else if (segments.size() == 2) { // Assuming bid, ask (if index is implicit and not read)
             try {
                double bid = std::stod(segments[0]); // This is likely wrong if data has index as first column
                double ask = std::stod(segments[1]); // Adjust if format is different
                // This path needs care; Python backtester implies index is present
                std::cerr << "Warning: CSV line in " << filepath << " has 2 segments, check format. Line: " << line << std::endl;
                // data_series.push_back({bid, ask, current_ts++}); // Uncomment if this is a valid format
            } catch (const std::invalid_argument& ia) {
                std::cerr << "Warning: Invalid number format in " << filepath << " at line: " << line << std::endl;
            } catch (const std::out_of_range& oor) {
                std::cerr << "Warning: Number out of range in " << filepath << " at line: " << line << std::endl;
            }
        }
         else {
            if (!line.empty())
             std::cerr << "Warning: Malformed line in " << filepath << " (expected 3 segments: index,bid,ask): " << line << std::endl;
        }
    }
    file.close();
    return data_series;
}

// --- Backtesting Function ---
double run_backtest(
    TradingAlgorithm& algo, // Pass by reference to modify and retrieve history
    const std::map<std::string, std::vector<PriceData>>& all_market_data,
    const std::vector<std::string>& products_to_trade, // e.g., {"ORE", "SHEEP", "WHEAT", "VP"}
    int position_limit,
    double fees,
    bool record_history_for_this_run // Flag to control if this run's history is kept
) {
    algo.reset_internal_state(); // Clear any previous run's history

    std::map<std::string, int> current_positions;
    std::map<std::string, double> cash_pnl; // PnL per product

    for (const auto& p : products_to_trade) {
        current_positions[p] = 0;
        cash_pnl[p] = 0.0;
    }

    size_t n_timestamps = 0;
    if (all_market_data.count(VP_SYMBOL) && !all_market_data.at(VP_SYMBOL).empty()) {
        n_timestamps = all_market_data.at(VP_SYMBOL).size();
    } else if (!products_to_trade.empty() && all_market_data.count(products_to_trade[0])) {
         n_timestamps = all_market_data.at(products_to_trade[0]).size();
    }


    if (n_timestamps == 0) {
        std::cerr << "Error: No timestamp data available for backtest." << std::endl;
        return 0.0;
    }
    
    // Check all products have enough data
    for(const auto& prod_name : products_to_trade) {
        if (!all_market_data.count(prod_name) || all_market_data.at(prod_name).size() < n_timestamps) {
            std::cerr << "Error: Product " << prod_name << " has insufficient data. Expected " << n_timestamps << " timestamps." << std::endl;
            return 0.0; // Or handle more gracefully
        }
    }


    for (size_t i = 0; i < n_timestamps; ++i) {
        std::map<std::string, std::map<std::string, double>> current_snapshot_data;
        for (const auto& product_name : products_to_trade) {
            if (all_market_data.count(product_name) && all_market_data.at(product_name).size() > i) {
                const auto& tick_data = all_market_data.at(product_name)[i];
                current_snapshot_data[product_name]["Timestamp"] = static_cast<double>(tick_data.timestamp);
                current_snapshot_data[product_name]["Bid"] = tick_data.bid;
                current_snapshot_data[product_name]["Ask"] = tick_data.ask;
            } else {
                 // Should not happen if initial check passed
                std::cerr << "Critical Error: Missing data for " << product_name << " at timestamp " << i << std::endl;
                return 0.0; // Fatal error for this run
            }
        }

        algo.set_current_positions(current_positions); // Algo needs to know current positions

        std::map<std::string, int> orders; // Algo will populate this
        algo.getOrders(current_snapshot_data, orders); // Populates algo's history vectors too

        for (const auto& order_pair : orders) {
            const std::string& product = order_pair.first;
            int quant = order_pair.second;

            if (quant == 0) continue;

            double ask_price = current_snapshot_data[product]["Ask"];
            double bid_price = current_snapshot_data[product]["Bid"];

            if (quant > 0) { // Buying
                if (current_positions[product] + quant > position_limit) {
                    quant = 0; // New: Cancel order if limit breached (matches Python)
                }
                if (quant > 0) { // if still buying after check
                    cash_pnl[product] -= ask_price * quant * (1 + fees);
                    current_positions[product] += quant;
                }
            } else { // Selling (quant < 0)
                if (current_positions[product] + quant < -position_limit) {
                    quant = 0; // New: Cancel order if limit breached (matches Python)
                }
                 if (quant < 0) { // if still selling after check
                    cash_pnl[product] += bid_price * (-quant) * (1 - fees);
                    current_positions[product] += quant;
                }
            }
        }
    }

    // Close open positions at the end
    double total_pnl = 0;
    for (const auto& product_name : products_to_trade) {
        if (all_market_data.count(product_name) && !all_market_data.at(product_name).empty()) {
            const auto& last_tick = all_market_data.at(product_name).back();
            if (current_positions[product_name] > 0) {
                cash_pnl[product_name] += last_tick.bid * current_positions[product_name] * (1 - fees);
            } else if (current_positions[product_name] < 0) {
                cash_pnl[product_name] -= last_tick.ask * (-current_positions[product_name]) * (1 + fees);
            }
        }
        total_pnl += cash_pnl[product_name];
    }
    
    // If this run was flagged to record history (e.g. best run), it's already in 'algo'.
    // The caller (main) will decide whether to call algo.export_data_to_csv()

    return total_pnl;
}


int main() {
    std::cout << std::fixed << std::setprecision(5); // For PnL output

    // --- Load Market Data (once) ---
    std::map<std::string, std::vector<PriceData>> all_market_data;
    std::vector<std::string> products_for_backtest = {VP_SYMBOL, "SHEEP", "ORE", "WHEAT"};
    bool data_load_ok = true;
    for (const auto& prod_name : products_for_backtest) {
        all_market_data[prod_name] = load_product_csv(prod_name);
        if (all_market_data[prod_name].empty()) {
            std::cerr << "Failed to load or empty data for product: " << prod_name << std::endl;
            data_load_ok = false;
        }
    }
    if (!data_load_ok) {
        std::cerr << "Aborting due to data loading errors." << std::endl;
        return 1;
    }


    // --- Define Parameters for Fuzzing ---
    std::vector<FuzzParams> param_combos;
    // Example fuzzing parameters (adjust these ranges as you see fit)
    std::vector<int> windows = {1}; // Python code has 1, and user requested only this
    std::vector<double> pos_thresholds;
    for (double val = 25.0; val <= 37.0; val += 0.2) { // Around 31, 6 on either side, 0.2 increments
        pos_thresholds.push_back(std::round(val * 10.0) / 10.0); // Mitigate potential floating point inaccuracies
    }
    std::vector<double> neg_thresholds;
    for (double val = -37.0; val <= -25.0; val += 0.2) { // Around -31, 6 on either side, 0.2 increments
        neg_thresholds.push_back(std::round(val * 10.0) / 10.0); // Mitigate potential floating point inaccuracies
    }
    std::vector<int> quantities = {100}; //{100};


    for (int w : windows) {
        for (double pt : pos_thresholds) {
            for (double nt : neg_thresholds) {
                if (nt >= pt) continue; // Basic sanity check
                for (int q : quantities) {
                    param_combos.push_back({w, pt, nt, q});
                }
            }
        }
    }
    
    if (param_combos.empty()) { // Default if fuzzing lists are empty (use Python values)
         param_combos.push_back({1, 33.0, -33.0, 100});
    }


    std::cout << "Starting parameter fuzzing with " << param_combos.size() << " combinations..." << std::endl;

    // --- Fixed Algorithm Parameters (from Python script) ---
    std::map<std::string, double> base_ratios = {{"SHEEP", 0.89205968}, {"ORE", 22.4798756}, {"WHEAT", 2.88036676}};
    double base_intercept = 42.15015333713495;
    int base_position_limit = 100;
    double base_fees = 0.002;

    std::vector<std::future<BacktestResult>> futures;
    std::mutex results_mutex;
    std::vector<BacktestResult> all_results;

    for (const auto& params_to_test : param_combos) {
        futures.push_back(
            std::async(std::launch::async, 
                [&all_market_data, params_to_test, &base_ratios, base_intercept, &products_for_backtest, base_position_limit, base_fees]() {
                TradingAlgorithm algo_instance(
                    params_to_test.rolling_avg_window,
                    params_to_test.positive_diff_ma_threshold,
                    params_to_test.negative_diff_ma_threshold,
                    params_to_test.fixed_order_quantity,
                    base_ratios, base_intercept, VP_SYMBOL, COMPONENT_SYMBOLS
                );
                double pnl = run_backtest(algo_instance, all_market_data, products_for_backtest, base_position_limit, base_fees, false);
                return BacktestResult{params_to_test, pnl};
            })
        );
    }

    for (auto& fut : futures) {
        all_results.push_back(fut.get());
    }

    // --- Report Results ---
    std::cout << "\n--- Parameter Fuzzing Report ---" << std::endl;
    std::cout << std::left << std::setw(10) << "Window"
              << std::setw(15) << "PosThresh"
              << std::setw(15) << "NegThresh"
              << std::setw(10) << "Quantity"
              << std::setw(15) << "PnL" << std::endl;

    BacktestResult best_result = {{0,0,0,0}, -std::numeric_limits<double>::infinity()};
    if (!all_results.empty()) {
        best_result = all_results[0]; // Initialize with the first result
         for(const auto& res : all_results) {
            if (res.pnl > best_result.pnl) {
                best_result = res;
            }
        }
    }


    std::sort(all_results.begin(), all_results.end(), [](const BacktestResult& a, const BacktestResult& b){
        return a.pnl > b.pnl; // Sort descending by PnL
    });

    for (const auto& res : all_results) {
        std::cout << std::left << std::setw(10) << res.params.rolling_avg_window
                  << std::setw(15) << res.params.positive_diff_ma_threshold
                  << std::setw(15) << res.params.negative_diff_ma_threshold
                  << std::setw(10) << res.params.fixed_order_quantity
                  << std::setw(15) << res.pnl << std::endl;
    }
    
    // Export all PnL results to CSV before checking if all_results is empty for the best result logic
    if (!all_results.empty()) {
        export_fuzzing_pnl_results(all_results, "fuzzing_pnl_summary.csv");
    }

    if (all_results.empty()) {
        std::cout << "No results from fuzzing to report." << std::endl;
        return 1;
    }


    std::cout << "\n--- Best Parameter Set ---" << std::endl;
    std::cout << "Rolling Avg Window: " << best_result.params.rolling_avg_window << std::endl;
    std::cout << "Positive DiffMA Threshold: " << best_result.params.positive_diff_ma_threshold << std::endl;
    std::cout << "Negative DiffMA Threshold: " << best_result.params.negative_diff_ma_threshold << std::endl;
    std::cout << "Fixed Order Quantity: " << best_result.params.fixed_order_quantity << std::endl;
    std::cout << "Best PnL: " << best_result.pnl << std::endl;

    // --- Generate Plot Data for the Best Result ---
    std::cout << "\nGenerating plot data for the best parameter set..." << std::endl;
    TradingAlgorithm best_algo(
        best_result.params.rolling_avg_window,
        best_result.params.positive_diff_ma_threshold,
        best_result.params.negative_diff_ma_threshold,
        best_result.params.fixed_order_quantity,
        base_ratios, base_intercept, VP_SYMBOL, COMPONENT_SYMBOLS
    );

    // Re-run backtest with the best_algo instance to populate its history specifically.
    // The history from the threaded run is not directly accessible here unless we redesign.
    // Simpler to re-run the deterministic backtest for the best params.
    run_backtest(best_algo, all_market_data, products_for_backtest, base_position_limit, base_fees, true); // true: indicates history should be kept and is now populated in best_algo

    best_algo.export_data_to_csv("market_data_report.csv", "trade_signals_report.csv");

    std::cout << "\nApplication finished." << std::endl;

    return 0;
}
