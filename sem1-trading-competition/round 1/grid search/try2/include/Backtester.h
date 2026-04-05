#ifndef BACKTESTER_H
#define BACKTESTER_H

#include <vector>

/**
 * @brief Runs a trading strategy backtest with the given parameters on the provided data.
 * 
 * @param short_window Length of the short-term rolling average window
 * @param waiting_period Length of the waiting period after high spread exit
 * @param hs_exit_change_threshold Threshold for re-entry after high spread
 * @param ma_turn_threshold Threshold for early exit when moving average turns
 * @param ticks Vector of timestamps
 * @param bids Vector of bid prices
 * @param asks Vector of ask prices
 * 
 * @return Final profit and loss (PnL) of the strategy
 */
double runBacktest(
    int    short_window, 
    int    waiting_period,
    double hs_exit_change_threshold,
    double ma_turn_threshold,
    const std::vector<int>    &ticks,
    const std::vector<double> &bids,
    const std::vector<double> &asks
);

#endif // BACKTESTER_H 