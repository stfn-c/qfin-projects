import pandas as pd
import numpy as np
import PanicTrader as template
import backtester
from copy import deepcopy
import time
import os
from itertools import product


def run_backtest(leader_window, follower_window, threshold_pct):
    """Run a single backtest with given parameters and return PnL"""
    # Reset the algorithm with new parameters
    template.team_algorithm = template.TradingAlgorithm()
    template.team_algorithm.leader_window = leader_window
    template.team_algorithm.follower_window = follower_window
    template.team_algorithm.direction_threshold_pct = threshold_pct

    # Reset positions and cash
    positions = {product: 0 for product in backtester.products}
    cash = {product: 0 for product in backtester.products}
    position_limit = backtester.position_limit
    fees = backtester.fees

    # Run the backtest
    for i in range(backtester.n_timestamps):
        # Create current data
        current_data = {}
        for product in backtester.products:
            current_data[product] = {
                "Timestamp": i,
                "Bid": backtester.price_series[product].iloc[i]["Bids"],
                "Ask": backtester.price_series[product].iloc[i]["Asks"],
            }

        # Get orders
        order = template.getOrders(deepcopy(current_data), deepcopy(positions))

        # Process orders
        for product in order:
            quant = int(order[product])
            if quant == 0:
                continue

            if quant > 0:  # Team is buying
                if positions[product] + quant > position_limit:
                    quant = position_limit - positions[product]
                cash[product] -= current_data[product]["Ask"] * quant * (1 + fees)

            elif quant < 0:  # Team is selling
                if positions[product] + quant < -position_limit:
                    quant = -position_limit - positions[product]
                cash[product] += current_data[product]["Bid"] * -quant * (1 - fees)

            positions[product] += quant

    # Close any open positions
    for product in backtester.products:
        if positions[product] > 0:
            cash[product] += (
                backtester.price_series[product].iloc[-1]["Bids"]
                * positions[product]
                * (1 - fees)
            )
        elif positions[product] < 0:
            cash[product] -= (
                backtester.price_series[product].iloc[-1]["Asks"]
                * -positions[product]
                * (1 + fees)
            )

    # Calculate total PnL
    total_pnl = sum(cash.values())

    # Count trades
    total_trades = sum(
        template.team_algorithm.product_stats[p]["total_trades"]
        for p in template.team_algorithm.product_stats
    )

    return total_pnl, total_trades


def grid_search():
    """Run a grid search to find optimal parameters"""
    # Define parameter ranges
    leader_windows = range(30, 40, 2)  # 10, 15, 20, ..., 50
    follower_windows = range(13, 17, 1)  # 5, 10, 15, 20
    thresholds = [1.4, 1.6, 1.8, 2.0]

    # Create results tracking
    results = []

    # Total combinations
    total_combos = len(leader_windows) * len(follower_windows) * len(thresholds)
    print(f"Running grid search with {total_combos} parameter combinations...")

    # Create directory for results
    os.makedirs("grid_search_results", exist_ok=True)

    # Start timer
    start_time = time.time()

    # Run grid search
    for i, (leader_window, follower_window, threshold) in enumerate(
        product(leader_windows, follower_windows, thresholds)
    ):
        # Skip invalid combinations where follower_window > leader_window
        if follower_window >= leader_window:
            continue

        # Run backtest with current parameters
        pnl, trades = run_backtest(leader_window, follower_window, threshold)

        # Store results
        results.append(
            {
                "leader_window": leader_window,
                "follower_window": follower_window,
                "threshold_pct": threshold,
                "pnl": pnl,
                "trades": trades,
            }
        )

        # Print progress
        print(f"Progress: {i+1}/{total_combos} combinations tested", end="\r")

    # End timer
    elapsed_time = time.time() - start_time

    # Convert results to DataFrame
    results_df = pd.DataFrame(results)

    # Sort by PnL (descending)
    results_df = results_df.sort_values("pnl", ascending=False)

    # Save results to CSV
    results_df.to_csv("grid_search_results/grid_search_results.csv", index=False)

    # Print top 10 results
    print("\n\nGrid Search Results:")
    print(
        f"Tested {len(results_df)} parameter combinations in {elapsed_time:.2f} seconds"
    )
    print("\nTop 10 Parameter Sets:")
    print(results_df.head(10))

    # Get the best parameters
    best_params = results_df.iloc[0]
    print(f"\nBest Parameters:")
    print(f"leader_window = {best_params['leader_window']}")
    print(f"follower_window = {best_params['follower_window']}")
    print(f"threshold_pct = {best_params['threshold_pct']}")
    print(f"PnL = {best_params['pnl']:.2f}")
    print(f"Trades = {best_params['trades']}")

    # Run visualizer with best parameters
    print("\nVisualizing strategy with best parameters...")
    run_best_visualization(
        best_params["leader_window"],
        best_params["follower_window"],
        best_params["threshold_pct"],
    )


def run_best_visualization(leader_window, follower_window, threshold_pct):
    """Run the strategy with the best parameters and generate visualization"""
    # Reset the algorithm with best parameters
    template.team_algorithm = template.TradingAlgorithm()
    template.team_algorithm.leader_window = leader_window
    template.team_algorithm.follower_window = follower_window
    template.team_algorithm.direction_threshold_pct = threshold_pct

    # Run the original backtester which handles visualization
    import importlib

    importlib.reload(backtester)


if __name__ == "__main__":
    grid_search()
