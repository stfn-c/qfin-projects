#include "../include/Backtester.h"
#include <vector>
#include <cmath>
#include <algorithm>
#include <limits>

// ---------------------------------------------------------
// Constants used by the strategy
// ---------------------------------------------------------
static const int    LONG_WINDOW           = 500;
static const double HIGH_SPREAD_THRESHOLD = 1.3;
static const int    POSITION_SIZE         = 100;
static const double FEES                  = 0.002;
static const int    POSITION_LIMIT        = 100;

// Helper: calculates the mean of the last N elements in an array
static double mean_of_last_N(const std::vector<double>& arr, int N)
{
    double sum = 0.0;
    int sz = (int)arr.size();
    for (int i = sz - N; i < sz; i++) {
        sum += arr[i];
    }
    return sum / N;
}

// ---------------------------------------------------------
// runBacktest(): Implementation of the trading strategy
// ---------------------------------------------------------
double runBacktest(
    int    short_window, 
    int    waiting_period,
    double hs_exit_change_threshold,
    double ma_turn_threshold,
    const std::vector<int>    &ticks,
    const std::vector<double> &bids,
    const std::vector<double> &asks
)
{
    int nrows = (int)ticks.size();
    if(nrows == 0) {
        return 0.0;
    }

    // "Historical" arrays for logging strategy state
    std::vector<int>    timestamp;
    std::vector<double> bid_vec;
    std::vector<double> ask_vec;
    std::vector<double> mid_price;
    std::vector<double> spread;
    std::vector<double> short_avg;
    std::vector<double> long_avg;
    std::vector<int>    position_log;
    std::vector<bool>   in_high_spread;
    std::vector<double> trade_profit;

    // Strategy states
    bool   in_position                = false;
    bool   position_is_long           = false;
    double current_position_extreme   = 0.0;
    bool   waiting_for_signal         = false;
    int    high_spread_exit_index     = -1;
    double last_high_spread_exit_savg = 0.0;

    // Track position and cash
    int    pos  = 0;
    double cash = 0.0;

    // Helper to record trade profit
    auto record_trade_section = [&](int entry_i, int exit_i,
                                  double entry_price, double exit_price,
                                  int position_size)
    {
        double profit = 0.0;
        if(position_size > 0) {
            profit = (exit_price - entry_price) * position_size;
        }
        else if(position_size < 0) {
            profit = (entry_price - exit_price) * std::abs(position_size);
        }
        return profit;
    };

    // Helper to update historical data
    auto update_history = [&](int t, double b, double a,
                            double savg, double lavg,
                            int newpos, bool hs, double trp)
    {
        timestamp.push_back(t);
        bid_vec.push_back(b);
        ask_vec.push_back(a);
        double m = 0.5 * (b + a);
        mid_price.push_back(m);
        spread.push_back(a - b);
        short_avg.push_back(savg);
        long_avg.push_back(lavg);
        position_log.push_back(newpos);
        in_high_spread.push_back(hs);
        trade_profit.push_back(trp);
    };

    // Main backtest loop
    for (int i = 0; i < nrows; i++)
    {
        double b = bids[i];
        double a = asks[i];
        double m = 0.5 * (b + a);
        double spr = a - b;
        bool hs = (spr >= HIGH_SPREAD_THRESHOLD);

        // Calculate short/long rolling averages
        double s_avg = std::numeric_limits<double>::quiet_NaN();
        if((int)mid_price.size() >= short_window) {
            s_avg = mean_of_last_N(mid_price, short_window);
        }
        double l_avg = std::numeric_limits<double>::quiet_NaN();
        if((int)mid_price.size() >= LONG_WINDOW) {
            l_avg = mean_of_last_N(mid_price, LONG_WINDOW);
        }

        int order_quantity = 0;
        double trade_p = 0.0;

        // 0) If in position => check if short_avg turned from extreme
        if(!std::isnan(s_avg) && in_position) {
            if(position_is_long) {
                if(s_avg > current_position_extreme) {
                    current_position_extreme = s_avg;
                } else {
                    if((current_position_extreme - s_avg) >= ma_turn_threshold) {
                        // exit
                        int exit_index = (int)timestamp.size();
                        int entry_index = -1;
                        for(int k=(int)position_log.size()-1; k>=0; k--) {
                            if(position_log[k] == 0) {
                                entry_index = k+1;
                                break;
                            }
                        }
                        if(entry_index >= 0 && entry_index < exit_index) {
                            double ep = mid_price[entry_index];
                            double xp = m;
                            trade_p = record_trade_section(entry_index, exit_index, ep, xp, pos);
                        }
                        order_quantity = -pos; // close
                        in_position = false;
                        position_is_long = false;
                        current_position_extreme = 0.0;
                    }
                }
            }
            else { // short
                if(s_avg < current_position_extreme) {
                    current_position_extreme = s_avg;
                } else {
                    if((s_avg - current_position_extreme) >= ma_turn_threshold) {
                        int exit_index = (int)timestamp.size();
                        int entry_index = -1;
                        for(int k=(int)position_log.size()-1; k>=0; k--) {
                            if(position_log[k] == 0) {
                                entry_index = k+1;
                                break;
                            }
                        }
                        if(entry_index >= 0 && entry_index < exit_index) {
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

        // 1) Just exited HS
        if(!timestamp.empty() && in_high_spread.back() && !hs) {
            high_spread_exit_index = (int)timestamp.size() - 1;
            if(!std::isnan(s_avg)) {
                last_high_spread_exit_savg = s_avg;
            } else {
                last_high_spread_exit_savg = m;
            }
            waiting_for_signal = true;
        }
        // 2) waited WAITING_PERIOD => check threshold for new entry
        else if(waiting_for_signal 
                && ((int)timestamp.size() - high_spread_exit_index) >= waiting_period
                && pos == 0
                && !hs)
        {
            if(!std::isnan(s_avg)) {
                double diff = std::fabs(s_avg - last_high_spread_exit_savg);
                if(diff >= hs_exit_change_threshold) {
                    if(m > s_avg) {
                        order_quantity = POSITION_SIZE;
                        in_position = true;
                        position_is_long = true;
                        current_position_extreme = s_avg;
                    } else if(m < s_avg) {
                        order_quantity = -POSITION_SIZE;
                        in_position = true;
                        position_is_long = false;
                        current_position_extreme = s_avg;
                    }
                    waiting_for_signal = false;
                }
            }
        }
        // 3) in HS & have a position => close now
        else if(hs && pos != 0) {
            int exit_index = (int)timestamp.size();
            int entry_index = -1;
            for(int k=(int)position_log.size()-1; k>=0; k--) {
                if(position_log[k] == 0) {
                    entry_index = k+1;
                    break;
                }
            }
            if(entry_index >= 0 && entry_index < exit_index) {
                double ep = mid_price[entry_index];
                double xp = m;
                trade_p = record_trade_section(entry_index, exit_index, ep, xp, pos);
            }
            order_quantity = -pos;
            in_position = false;
            position_is_long = false;
            current_position_extreme = 0.0;
        }

        // Apply position limits and update cash
        int actual_order = order_quantity;
        if(actual_order > 0 && (pos + actual_order) > POSITION_LIMIT) {
            actual_order = 0;
        }
        if(actual_order < 0 && (pos + actual_order) < -POSITION_LIMIT) {
            actual_order = 0;
        }
        if(actual_order > 0) {
            cash -= a * actual_order * (1.0 + FEES);
        }
        else if(actual_order < 0) {
            cash += b * (-actual_order) * (1.0 - FEES);
        }
        int new_pos = pos + actual_order;

        // record to history
        double use_savg = std::isnan(s_avg) ? m : s_avg;
        double use_lavg = std::isnan(l_avg) ? m : l_avg;
        update_history(ticks[i], b, a, use_savg, use_lavg, new_pos, hs, trade_p);

        pos = new_pos;
    }

    // flatten final position
    if(pos != 0) {
        double final_bid = bids[nrows - 1];
        double final_ask = asks[nrows - 1];
        if(pos > 0) {
            cash += final_bid * pos * (1.0 - FEES);
        } else {
            cash -= final_ask * (-pos) * (1.0 + FEES);
        }
    }

    return cash;
} 