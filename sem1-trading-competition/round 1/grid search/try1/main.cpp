/*********************************************************
 * Single-file C++ Fuzzer / Backtester
 * 
 * 1) Reads "UEC.csv" with columns: Tick, Bids, Asks
 * 2) For each combination of fuzzed parameters:
 *      - short_window, waiting_period, 
 *        hs_exit_change_threshold, ma_turn_threshold
 *    in ±10% around the base, in 1%-increments
 *    => total 21 steps each => 21^4 combos
 * 3) Runs EXACT SAME backtest logic as before 
 *    (no optimizations, no logic changes).
 * 4) Multi-threaded. Reports progress every second, 
 *    overwriting a single console line. Shows top 3 combos so far.
 *********************************************************/
#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <map>
#include <cmath>
#include <algorithm>
#include <thread>
#include <mutex>
#include <chrono>
#include <atomic>
#include <condition_variable>

// We will reuse the naive logic from before, 
// so let's put it in a function `runBacktest(...)` that returns final PnL.

//============================================================
//               DATA + GLOBAL STRUCTURES
//============================================================

static const int    LONG_WINDOW           = 500;  // stays fixed
static const double HIGH_SPREAD_THRESHOLD = 1.3;  // stays fixed
static const int    POSITION_SIZE         = 100;  // stays fixed
static const double FEES                  = 0.002; // fixed
static const int    POSITION_LIMIT        = 100;  // fixed

// We'll store the entire CSV in vectors:
static std::vector<int>    g_ticks;
static std::vector<double> g_bids;
static std::vector<double> g_asks;
static int                 g_nrows = 0;

// We copy/paste the naive approach from the old code:

//------------------------------------
// Rolling averages by naive summation
//------------------------------------
static double mean_of_last_N(const std::vector<double>& arr, int N)
{
    double sum = 0.0;
    int sz = (int)arr.size();
    for(int i = sz - N; i < sz; i++){
        sum += arr[i];
    }
    return sum / N;
}

//------------------------------------
// Helper to run the entire backtest
//------------------------------------
double runBacktest(int short_window, 
                   int waiting_period,
                   double hs_exit_change_threshold,
                   double ma_turn_threshold)
{
    // Strategy-state arrays (like "historical_data" in Python):
    std::vector<int>    timestamp;
    std::vector<double> bid_vec;
    std::vector<double> ask_vec;
    std::vector<double> mid_price;
    std::vector<double> spread;
    std::vector<double> short_avg;
    std::vector<double> long_avg;
    std::vector<int>    position_log;
    std::vector<bool>   in_high_spread;
    // trade_profit we keep for reference
    std::vector<double> trade_profit;

    // We'll keep them in function-scope (like global in Python).
    bool   in_position                = false;
    bool   position_is_long           = false;
    double current_position_extreme   = 0.0;
    bool   waiting_for_signal         = false;
    int    high_spread_exit_index     = -1;
    double last_high_spread_exit_savg = 0.0;

    // There's only one product "UEC" => position & cash
    int    pos  = 0;
    double cash = 0.0;

    auto record_trade_section = [&](int entry_i, int exit_i, 
                                    double entry_price, double exit_price, 
                                    int position_size){
        double pr = 0.0;
        if(position_size > 0){
            pr = (exit_price - entry_price) * position_size;
        } else if(position_size < 0){
            pr = (entry_price - exit_price) * std::abs(position_size);
        }
        return pr;
    };

    auto update_history = [&](int t, double b, double a,
                              double savg, double lavg,
                              int p, bool hs, double tp)
    {
        timestamp.push_back(t);
        bid_vec.push_back(b);
        ask_vec.push_back(a);
        double m = 0.5*(b+a);
        mid_price.push_back(m);
        double spr = a-b;
        spread.push_back(spr);
        short_avg.push_back(savg);
        long_avg.push_back(lavg);
        position_log.push_back(p);
        in_high_spread.push_back(hs);
        trade_profit.push_back(tp);
    };

    // Main loop: replicate the old approach
    for(int i = 0; i < g_nrows; i++){
        double b = g_bids[i];
        double a = g_asks[i];
        double m = 0.5*(b+a);
        double spr = a - b;
        bool hs = (spr >= HIGH_SPREAD_THRESHOLD);

        double s_avg = NAN;
        if((int)mid_price.size() >= short_window){
            s_avg = mean_of_last_N(mid_price, short_window);
        }
        double l_avg = NAN;
        if((int)mid_price.size() >= LONG_WINDOW){
            l_avg = mean_of_last_N(mid_price, LONG_WINDOW);
        }

        int order_quantity = 0;
        double trade_p = 0.0;

        // (0) If in a position => check short_avg turn
        if(!std::isnan(s_avg) && in_position){
            if(position_is_long){
                if(s_avg > current_position_extreme){
                    current_position_extreme = s_avg;
                } else {
                    if((current_position_extreme - s_avg) >= ma_turn_threshold){
                        // exit early
                        int exit_index = (int)timestamp.size();
                        int entry_index = -1;
                        for(int k = (int)position_log.size()-1; k >= 0; k--){
                            if(position_log[k] == 0){
                                entry_index = k+1;
                                break;
                            }
                        }
                        if(entry_index >= 0 && entry_index < exit_index){
                            double ep = mid_price[entry_index];
                            double xp = m;
                            trade_p = record_trade_section(entry_index, exit_index, ep, xp, pos);
                        }
                        order_quantity = -pos;
                        in_position = false;
                        position_is_long = false;
                        current_position_extreme = 0.0;
                    }
                }
            } else {
                // short
                if(s_avg < current_position_extreme){
                    current_position_extreme = s_avg;
                } else {
                    if((s_avg - current_position_extreme) >= ma_turn_threshold){
                        int exit_index = (int)timestamp.size();
                        int entry_index = -1;
                        for(int k = (int)position_log.size()-1; k >= 0; k--){
                            if(position_log[k] == 0){
                                entry_index = k+1;
                                break;
                            }
                        }
                        if(entry_index >= 0 && entry_index < exit_index){
                            double ep = mid_price[entry_index];
                            double xp = m;
                            trade_p = record_trade_section(entry_index, exit_index, ep, xp, pos);
                        }
                        order_quantity = -pos;
                        in_position = false;
                        position_is_long = false;
                        current_position_extreme = 0.0;
                    }
                }
            }
        }

        // CASE 1: just exited high spread
        if(!timestamp.empty() 
           && in_high_spread.back()
           && !hs)
        {
            high_spread_exit_index = (int)timestamp.size() - 1;
            if(!std::isnan(s_avg)){
                last_high_spread_exit_savg = s_avg;
            } else {
                last_high_spread_exit_savg = m;
            }
            waiting_for_signal = true;
        }
        // CASE 2: waited WAITING_PERIOD => new entry if not in HS
        else if(waiting_for_signal
                && ((int)timestamp.size() - high_spread_exit_index) >= waiting_period
                && pos == 0
                && !hs)
        {
            if(!std::isnan(s_avg)){
                double diff = std::fabs(s_avg - last_high_spread_exit_savg);
                if(diff >= hs_exit_change_threshold){
                    // normal logic
                    if(m > s_avg){
                        order_quantity = POSITION_SIZE;
                        in_position = true;
                        position_is_long = true;
                        current_position_extreme = s_avg;
                    } else if(m < s_avg){
                        order_quantity = -POSITION_SIZE;
                        in_position = true;
                        position_is_long = false;
                        current_position_extreme = s_avg;
                    }
                    waiting_for_signal = false;
                }
            }
        }
        // CASE 3: in HS & have a position => close now
        else if(hs && pos != 0){
            int exit_index = (int)timestamp.size();
            int entry_index = -1;
            for(int k = (int)position_log.size()-1; k >= 0; k--){
                if(position_log[k] == 0){
                    entry_index = k+1;
                    break;
                }
            }
            if(entry_index >= 0 && entry_index < exit_index){
                double ep = mid_price[entry_index];
                double xp = m;
                trade_p = record_trade_section(entry_index, exit_index, ep, xp, pos);
            }
            order_quantity = -pos;
            in_position = false;
            position_is_long = false;
            current_position_extreme = 0.0;
        }

        // Update position & logs
        int new_pos = pos + order_quantity;
        // But apply the position limit & fees logic EXACTLY like the old code
        // => we do it *outside* this logic or we match the old backtester?
        // The old code forcibly set quant=0 if it would exceed limit. Then updated cash.

        // We'll do it step-by-step as the old code:
        // The final backtester code did something like:
        //   if(quant > 0 && pos+quant > position_limit) => quant=0
        //   if(quant < 0 && pos+quant < -position_limit)=> quant=0
        //   if(quant>0) => cash -= ask*quant*(1+fees)
        //   if(quant<0) => cash += bid*(-quant)*(1-fees)
        // We'll replicate that carefully.

        int actual_order = order_quantity;
        // clamp buy
        if(actual_order > 0 && (pos + actual_order > POSITION_LIMIT)){
            actual_order = 0;
        }
        // clamp sell
        if(actual_order < 0 && (pos + actual_order < -POSITION_LIMIT)){
            actual_order = 0;
        }
        if(actual_order > 0){
            cash -= a * actual_order * (1.0 + FEES);
        } else if(actual_order < 0){
            cash += b * (-actual_order) * (1.0 - FEES);
        }
        new_pos = pos + actual_order; // final position

        // Now record to history
        double use_savg = std::isnan(s_avg) ? m : s_avg;
        double use_lavg = std::isnan(l_avg) ? m : l_avg;
        update_history(g_ticks[i], b, a, use_savg, use_lavg, new_pos, hs, trade_p);

        pos = new_pos;
    }

    // After loop, flatten any remaining position at final tick
    if(pos != 0 && g_nrows>0){
        double final_bid = g_bids[g_nrows - 1];
        double final_ask = g_asks[g_nrows - 1];
        if(pos > 0){
            cash += final_bid * pos * (1.0 - FEES);
        } else {
            cash -= final_ask * (-pos) * (1.0 + FEES);
        }
    }

    return cash;
}

//============================================================
//     Fuzzing parameters around base ±10% in 1% increments
//============================================================

// A small helper to produce integer steps in ±10% of an integer base:
std::vector<int> fuzzIntParam(int baseVal)
{
    // from 90% to 110%, stepping by 1% => 21 steps total
    // e.g. if base=80, range is [72 .. 88] in integer steps
    // We'll do rounding carefully: 0.9 * 80 = 72, 1.1 * 80 = 88
    // step => 0.01 * base => 0.8 => we can handle that by generating 
    // each i from -10..+10, and do base * (1.0 + i/100.0).
    // Then round to nearest integer
    std::vector<int> vals;
    for(double i = -3; i <= 3; i = i + 1){
        double factor = (100.0 + i) / 100.0; 
        double val = baseVal * factor;
        int iv = (int)std::round(val);
        if(iv < 1) iv=1; // avoid 0 or negative in places where logic might break
        vals.push_back(iv);
    }
    std::sort(vals.begin(), vals.end());
    return vals;
}

// For double-based parameters, we do a similar approach:
std::vector<double> fuzzDoubleParam(double baseVal)
{
    // from 0.9*baseVal to 1.1*baseVal in steps of 0.01*baseVal
    // We'll store doubles
    std::vector<double> vals;
    for(double i = -3; i <= 3; i = i + 0.3){
        double factor = (100.0 + i) / 100.0; 
        double dv = baseVal * factor;
        // In some strategies, you might ensure dv>0
        if(dv <= 0.0) dv = 0.000001;
        vals.push_back(dv);
    }
    std::sort(vals.begin(), vals.end());
    return vals;
}

// A struct to hold a single param combination + result
struct ParamResult {
    int short_window;
    int waiting_period;
    double hs_exit_change_threshold;
    double ma_turn_threshold;
    double pnl;
};

//============================================================
//         MAIN: load CSV, build combos, run in threads
//============================================================
#include <mutex>
#include <condition_variable>
#include <atomic>
#include <chrono>
#include <iomanip>

// We'll store all combos in a global vector, plus a global 
// vector for results. We’ll use an atomic index to dispatch.
static std::vector<ParamResult> g_combos;
static std::atomic<size_t> g_nextIdx{0};
static std::vector<ParamResult> g_results; 
static std::mutex g_resMutex; // protect g_results updates

// We also want to track how many combos have completed
static std::atomic<size_t> g_doneCount{0};
static size_t g_totalCount = 0;

// For live progress: every second, we’ll print the top 3 combos so far.
void progressThreadFunc()
{
    using clock = std::chrono::steady_clock;
    auto nextPrint = clock::now() + std::chrono::seconds(1);

    while(true){
        std::this_thread::sleep_until(nextPrint);
        nextPrint = clock::now() + std::chrono::seconds(1);

        size_t done = g_doneCount.load();
        if(done >= g_totalCount){
            // all combos done => do one last print & exit
            break;
        }

        // gather top 3
        std::vector<ParamResult> localCopy;
        {
            std::lock_guard<std::mutex> lk(g_resMutex);
            localCopy = g_results; // copy so we can sort outside the lock
        }
        // sort by PnL descending
        std::sort(localCopy.begin(), localCopy.end(),
                  [](auto &a, auto &b){return a.pnl > b.pnl;});
        
        // top 3
        std::ostringstream oss;
        oss << "\r" << std::flush; // carriage return
        oss << "Progress: " << done << "/" << g_totalCount << " done.  ";
        
        int topCount = std::min<int>(3, (int)localCopy.size());
        oss << "Top " << topCount << ": ";
        for(int i=0; i<topCount; i++){
            oss << "[SW=" << localCopy[i].short_window
                << ",WP=" << localCopy[i].waiting_period
                << ",HSX=" << std::fixed << std::setprecision(3) 
                << localCopy[i].hs_exit_change_threshold
                << ",MAT=" << std::fixed << std::setprecision(3)
                << localCopy[i].ma_turn_threshold
                << " => " << std::fixed << std::setprecision(2)
                << localCopy[i].pnl << "]  ";
        }
        // Erase to end of line:
        oss << "\x1b[K";
        std::cerr << oss.str() << std::flush;
    }

    // Final print after completion
    {
        size_t done = g_doneCount.load();
        std::vector<ParamResult> localCopy;
        {
            std::lock_guard<std::mutex> lk(g_resMutex);
            localCopy = g_results;
        }
        std::sort(localCopy.begin(), localCopy.end(),
                  [](auto &a, auto &b){return a.pnl > b.pnl;});
        
        std::cerr << "\r" << std::flush;
        std::cerr << done << "/" << g_totalCount 
                  << " done. Final top 3 combos:\n";
        int topCount = std::min<int>(3, (int)localCopy.size());
        for(int i=0; i<topCount; i++){
            std::cerr << " " << i+1 << ") "
                      << "[SW=" << localCopy[i].short_window
                      << ", WP=" << localCopy[i].waiting_period
                      << ", HSX=" << std::fixed << std::setprecision(3) 
                      << localCopy[i].hs_exit_change_threshold
                      << ", MAT=" << std::fixed << std::setprecision(3)
                      << localCopy[i].ma_turn_threshold
                      << "] => PnL="
                      << std::fixed << std::setprecision(2)
                      << localCopy[i].pnl << "\n";
        }
    }
}

// Worker thread function
void workerThreadFunc()
{
    while(true){
        // fetch next index
        size_t idx = g_nextIdx.fetch_add(1);
        if(idx >= g_totalCount){
            // no more
            return;
        }
        // get combo
        ParamResult pr = g_combos[idx];

        // run backtest
        double resultPNL = runBacktest(pr.short_window,
                                       pr.waiting_period,
                                       pr.hs_exit_change_threshold,
                                       pr.ma_turn_threshold);
        pr.pnl = resultPNL;

        {
            std::lock_guard<std::mutex> lk(g_resMutex);
            g_results[idx] = pr;
        }

        // done
        g_doneCount.fetch_add(1);
    }
}

int main()
{
    // 1) Load CSV "UEC.csv"
    {
        std::ifstream fin("UEC.csv");
        if(!fin.is_open()){
            std::cerr << "Error opening UEC.csv\n";
            return 1;
        }
        bool first_line = true;
        std::string line;
        while(std::getline(fin, line)){
            if(line.empty()) continue;
            // If CSV has a header row, skip it
            if(first_line){
                first_line = false;
                // comment out next line if no header
                continue;
            }
            std::stringstream ss(line);
            std::string c1,c2,c3;
            if(std::getline(ss,c1,',') && 
               std::getline(ss,c2,',') &&
               std::getline(ss,c3,','))
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
    if(g_nrows==0){
        std::cerr << "No data found in UEC.csv\n";
        return 1;
    }
    std::cerr << "Loaded " << g_nrows << " rows from UEC.csv\n";

    // Base parameter values
    int base_SHORT_WINDOW      = 83;
    int base_WAITING_PERIOD    = 76;
    double base_HS_EXIT_CHANGE = 0.015;
    double base_MA_TURN        = 0.650;

    // 2) Build fuzzed parameter sets
    auto sw_vals = fuzzIntParam(base_SHORT_WINDOW);       // short_window
    auto wp_vals = fuzzIntParam(base_WAITING_PERIOD);     // waiting_period
    auto hs_vals = fuzzDoubleParam(base_HS_EXIT_CHANGE);  // hs_exit_change_threshold
    auto ma_vals = fuzzDoubleParam(base_MA_TURN);         // ma_turn_threshold

    // Generate all combos
    for(int sw : sw_vals){
        for(int wp : wp_vals){
            for(double hsx : hs_vals){
                for(double mat : ma_vals){
                    ParamResult pr;
                    pr.short_window            = sw;
                    pr.waiting_period          = wp;
                    pr.hs_exit_change_threshold= hsx;
                    pr.ma_turn_threshold       = mat;
                    pr.pnl = 0.0;
                    g_combos.push_back(pr);
                }
            }
        }
    }
    g_totalCount = g_combos.size();
    g_results.resize(g_totalCount);

    std::cerr << "Total combos to test: " << g_totalCount << std::endl;

    // 3) Spawn threads => as many cores as possible
    unsigned int hw = std::thread::hardware_concurrency();
    if(hw == 0) hw = 2; // fallback if unknown
    std::cerr << "Using " << hw << " worker threads...\n";

    // Start progress thread
    std::thread progThread(progressThreadFunc);

    // Start worker threads
    std::vector<std::thread> workers;
    workers.reserve(hw);
    for(unsigned int i=0; i<hw; i++){
        workers.emplace_back(workerThreadFunc);
    }

    // Join workers
    for(auto &th : workers){
        th.join();
    }

    // Join progress thread
    progThread.join();

    // Done
    return 0;
}
