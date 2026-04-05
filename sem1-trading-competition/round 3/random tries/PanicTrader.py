# === Strategy Explanation ===
# This algorithm trades a pair (ORE vs VP) based on signals derived from WHEAT's price movements.
# 1. WHEAT Signal Generation:
#    - Calculate the Simple Moving Average (SMA) of WHEAT's mid-price over a defined window (`wheat_ma_window`).
#    - Track the rolling minimum and maximum of this SMA since last reset.
#    - IMPORTANT CHANGE: We do NOT reset the opposite extreme when finding a new min/max
#    - A buy signal is generated if the SMA moves upwards from its rolling minimum by a certain percentage (`wheat_threshold_pct`).
# 2. Pair Trade Entry:
#    - After a WHEAT buy signal is generated, wait for a specific number of ticks (`holding_period`).
#    - At the end of the holding period, compare the price change of ORE and VP since the signal timestamp.
#    - Sell the one that went up more (or down less) and Buy the one that went up less (or down more).
#    - Enter full positions (`trade_size`, typically the position limit) in both ORE and VP (long one, short the other).
# 3. Pair Trade Exit:
#    - Once in the ORE/VP pair trade, monitor the WHEAT SMA.
#    - Exit *both* the long ORE/VP position and the short ORE/VP position (go flat) as soon as the WHEAT SMA hits a new rolling maximum *after* the pair trade was entered.
# === Implementation Details ===
# - Uses a deque to efficiently calculate the rolling SMA.
# - Manages state transitions: 'NEUTRAL', 'SIGNAL_TRIGGERED', 'IN_TRADE'.
# - Records historical positions and orders for plotting via atexit.
# === Debug Features ===
# - Prints detailed MA, min/max values at each tick
# - Logs state transitions and trade decisions
# - Includes forced test trade option to verify trade mechanics

import random
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go  # Import graph_objects
from plotly.subplots import make_subplots  # Import make_subplots
import argparse
import atexit
import os  # Import os for path joining
from typing import Dict, List, Any
from collections import deque  # Import deque
import numpy as np  # Import numpy for nan handling


def plot_prices(
    history: List[Dict[str, Any]], price_data: Dict[str, pd.DataFrame]
):  # Now takes history and price_data
    """Processes simulation history and price data to generate an interactive plot saved to HTML."""
    output_filename = "trade_and_position_plot.html"

    if not history:
        print("No simulation history recorded for plotting.")
        return
    if not price_data:
        print("No price data loaded for plotting.")
        return

    # --- Process History ---
    hist_df = pd.DataFrame(history)
    print("Plotting Data Check:")
    print(hist_df[["timestamp", "wheat_ma", "rolling_min_ma", "rolling_max_ma"]].head())
    print(hist_df[["timestamp", "wheat_ma", "rolling_min_ma", "rolling_max_ma"]].tail())
    # Extract individual positions
    products_to_track = ["ORE", "WHEAT", "VP"]
    for product in products_to_track:
        hist_df[f"pos_{product}"] = hist_df["positions"].apply(
            lambda p: p.get(product, 0)
        )

    buy_events = []
    sell_events = []

    for index, row in hist_df.iterrows():
        ts = row["timestamp"]
        # Check if 'orders' key exists, handle potential KeyError if processing incomplete history
        orders = row.get("orders", {})
        for product, quantity in orders.items():
            if product not in products_to_track:
                continue
            if quantity > 0:
                if product in price_data and ts < len(price_data[product]):
                    price = price_data[product].iloc[ts]["Asks"]
                    buy_events.append(
                        {
                            "timestamp": ts,
                            "product": product,
                            "price": price,
                            "quantity": quantity,
                        }
                    )
            elif quantity < 0:
                if product in price_data and ts < len(price_data[product]):
                    price = price_data[product].iloc[ts]["Bids"]
                    sell_events.append(
                        {
                            "timestamp": ts,
                            "product": product,
                            "price": price,
                            "quantity": quantity,
                        }
                    )

    buy_df = pd.DataFrame(buy_events)
    sell_df = pd.DataFrame(sell_events)

    # --- Create Plot ---
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,  # Adjusted spacing slightly
        row_heights=[0.7, 0.3],
        specs=[[{"secondary_y": False}], [{"secondary_y": False}]],
    )

    # Top Plot (Row 1)
    # Plot Prices
    for product, df in price_data.items():
        if product in products_to_track:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=(df["Bids"] + df["Asks"]) / 2,
                    mode="lines",
                    name=f"{product} Price",
                    legendgroup="prices",
                    line=dict(width=1),
                ),
                row=1,
                col=1,
            )

    # Add WHEAT MA to top plot if available in history (needs calculation during run)
    if "wheat_ma" in hist_df.columns:
        fig.add_trace(
            go.Scatter(
                x=hist_df["timestamp"],
                y=hist_df["wheat_ma"],
                mode="lines",
                name="WHEAT MA",
                line=dict(color="cyan", dash="dot", width=1.5),
            ),
            row=1,
            col=1,
        )

    # Add Rolling Min/Max MA to top plot
    if "rolling_min_ma" in hist_df.columns:
        fig.add_trace(
            go.Scatter(
                x=hist_df["timestamp"],
                y=hist_df["rolling_min_ma"],
                mode="lines",
                name="Rolling Min MA",
                line=dict(color="orangered", dash="dashdot", width=1.5),
                legendgroup="ma_stats",
            ),
            row=1,
            col=1,
        )
    if "rolling_max_ma" in hist_df.columns:
        fig.add_trace(
            go.Scatter(
                x=hist_df["timestamp"],
                y=hist_df["rolling_max_ma"],
                mode="lines",
                name="Rolling Max MA",
                line=dict(color="mediumspringgreen", dash="dashdot", width=1.5),
                legendgroup="ma_stats",
            ),
            row=1,
            col=1,
        )

    # Plot Buy/Sell Markers
    if not buy_df.empty:
        fig.add_trace(
            go.Scatter(
                x=buy_df["timestamp"],
                y=buy_df["price"],
                mode="markers",
                name="Buy Order",
                marker=dict(
                    color="green", size=7, symbol="triangle-up"
                ),  # Slightly smaller markers
                legendgroup="trades",
                hovertemplate="Buy %{customdata[0]} @ %{y:.2f} (Qty: %{customdata[1]})<extra></extra>",
                customdata=buy_df[["product", "quantity"]],
            ),
            row=1,
            col=1,
        )
    if not sell_df.empty:
        fig.add_trace(
            go.Scatter(
                x=sell_df["timestamp"],
                y=sell_df["price"],
                mode="markers",
                name="Sell Order",
                marker=dict(
                    color="red", size=7, symbol="triangle-down"
                ),  # Slightly smaller markers
                legendgroup="trades",
                hovertemplate="Sell %{customdata[0]} @ %{y:.2f} (Qty: %{customdata[1]})<extra></extra>",
                customdata=sell_df[["product", "quantity"]],
            ),
            row=1,
            col=1,
        )

    # Bottom Plot (Row 2)
    # Plot Individual Positions
    position_colors = {
        "ORE": "blue",
        "WHEAT": "orange",
        "VP": "purple",
    }  # Define colors
    for product in products_to_track:
        fig.add_trace(
            go.Scatter(
                x=hist_df["timestamp"],
                y=hist_df[f"pos_{product}"],
                mode="lines",
                name=f"{product} Position",
                line=dict(color=position_colors.get(product, "grey")),
                legendgroup="positions",
            ),  # Group legends
            row=2,
            col=1,
        )

    # --- Layout Updates ---
    fig.update_layout(
        title_text="Strategy Analysis: Prices, Trades, and Positions",
        legend_title_text="Trace Type",
        hovermode="x unified",
        legend=dict(tracegroupgap=20),
    )  # Add gap between legend groups
    fig.update_xaxes(title_text="Timestamp", row=2, col=1)
    fig.update_yaxes(title_text="Price / MA", row=1, col=1)  # Updated label
    fig.update_yaxes(title_text="Position", row=2, col=1)  # Updated bottom axis label

    # --- Save Plot ---
    try:
        # Handle potential __file__ issue when run via atexit from another script
        try:
            script_dir = os.path.dirname(__file__)
        except NameError:
            script_dir = os.getcwd()  # Fallback to current working directory

        filepath = os.path.join(script_dir, output_filename)
        fig.write_html(filepath, auto_open=False)
        print(f"Interactive plot saved to: {filepath}")
    except Exception as e:
        try:
            # Fallback save location
            filepath = os.path.abspath(output_filename)
            fig.write_html(filepath, auto_open=False)
            print(f"Interactive plot saved to current directory: {filepath}")
        except Exception as e_fallback:
            print(f"Error saving plot: {e_fallback}")


# --- Modified atexit registration ---
def run_plot_on_exit():
    # Need to access the global team_algorithm instance to get its history and price_data
    if (
        team_algorithm
        and hasattr(team_algorithm, "history")
        and hasattr(team_algorithm, "price_data")
    ):
        # Ensure history is not empty before plotting
        if team_algorithm.history:
            plot_prices(team_algorithm.history, team_algorithm.price_data)
        else:
            print("History is empty, skipping plot generation on exit.")
    else:
        print("Could not find algorithm history or price data for plotting on exit.")


atexit.register(run_plot_on_exit)  # Register the wrapper function


class TradingAlgorithm:

    def __init__(self, products=["ORE", "WHEAT", "VP"], data_location="./data"):
        # --- Parameters ---
        self.wheat_ma_window = 30
        self.wheat_threshold_pct = 0.005  # 0.5% threshold from rolling min
        self.holding_period = 10  # Ticks to wait after signal before entry
        self.trade_size = 100  # Position size for ORE/VP pair trade
        self.forced_test_trade = False  # Set to True to force a test trade
        self.forced_trade_timestamp = 100  # Timestamp for forced test trade if enabled
        self.verbose_debug = True  # Set to True for detailed tick-by-tick debug output

        # --- State Variables ---
        self.positions: Dict[str, int] = {}
        self.history: List[Dict[str, Any]] = []
        self.price_data: Dict[str, pd.DataFrame] = {}  # Pre-loaded price data

        # WHEAT MA calculation state
        self.wheat_prices_deque = deque(maxlen=self.wheat_ma_window)
        self.wheat_ma = np.nan  # Current Moving Average

        # Rolling Min/Max tracking for WHEAT MA
        self.rolling_min_ma = np.inf
        self.rolling_max_ma = -np.inf
        self.min_max_reset_count = 0  # Track how often we reset min/max

        # Strategy State Machine
        self.current_state = (
            "NEUTRAL"  # Can be 'NEUTRAL', 'SIGNAL_TRIGGERED', 'IN_TRADE'
        )
        self.signal_timestamp = -1
        self.entry_price_ore = np.nan
        self.entry_price_vp = np.nan
        self.new_max_after_entry = (
            False  # Flag to track if new WHEAT MA max occurred after entering trade
        )

        # Stats/Debug
        self.tick_count = 0  # Count total ticks processed
        self.signal_count = 0  # Count signals triggered
        self.trade_count = 0  # Count trades made

        # --- Initialization ---
        print("Initializing Trading Algorithm...")
        # Load price data
        print("Loading price data...")
        all_products = products + ["SHEEP"]  # Load all for potential reference
        for product in all_products:
            try:
                df = pd.read_csv(f"{data_location}/{product}.csv", index_col=0)
                self.price_data[product] = df
            except FileNotFoundError:
                print(f"Warning: Initial data load failed for {product}.")
        print("Price data loaded.")

        print(
            f"Parameters: MA Window={self.wheat_ma_window}, Threshold={self.wheat_threshold_pct*100}%, Holding Period={self.holding_period}, Trade Size={self.trade_size}"
        )
        if self.forced_test_trade:
            print(
                f"NOTICE: Forced test trade enabled at timestamp {self.forced_trade_timestamp}"
            )

    def getOrders(
        self,
        current_data: Dict[str, Dict[str, float]],
        order_data_template: Dict[str, int],
    ) -> Dict[str, int]:

        final_orders = order_data_template.copy()  # Start with zero orders
        timestamp = -1
        products_in_data = list(current_data.keys())

        # --- Timestamp and Data Check ---
        if not products_in_data:
            print("Warning: No product data received.")
            # Append minimal history if needed, otherwise return zero orders
            self.history.append(
                {
                    "timestamp": -1,
                    "positions": self.positions.copy(),
                    "orders": final_orders,
                    "wheat_ma": self.wheat_ma,
                }
            )
            return final_orders

        timestamp = current_data[products_in_data[0]].get("Timestamp", -1)
        if timestamp == -1:
            print("Warning: Could not determine timestamp.")
            # Append minimal history if needed, otherwise return zero orders
            self.history.append(
                {
                    "timestamp": -1,
                    "positions": self.positions.copy(),
                    "orders": final_orders,
                    "wheat_ma": self.wheat_ma,
                }
            )
            return final_orders

        # --- WHEAT MA Calculation & Rolling Min/Max ---
        if "WHEAT" in current_data:
            wheat_bid = current_data["WHEAT"]["Bid"]
            wheat_ask = current_data["WHEAT"]["Ask"]
            wheat_mid_price = (wheat_bid + wheat_ask) / 2

            self.wheat_prices_deque.append(wheat_mid_price)

            if len(self.wheat_prices_deque) == self.wheat_ma_window:
                self.wheat_ma = np.mean(self.wheat_prices_deque)

                # Update rolling min/max ONLY when MA is valid
                if not np.isnan(self.wheat_ma):
                    previous_rolling_max = self.rolling_max_ma

                    # Did we hit a new minimum?
                    if self.wheat_ma < self.rolling_min_ma:
                        self.rolling_min_ma = self.wheat_ma
                        # Don't reset max when new min is hit
                        if self.current_state == "IN_TRADE":
                            self.new_max_after_entry = False  # Reset this flag too

                    # Did we hit a new maximum?
                    elif self.wheat_ma > self.rolling_max_ma:
                        self.rolling_max_ma = self.wheat_ma
                        # Don't reset min when new max is hit
                        if self.current_state == "IN_TRADE":
                            # A new max occurred while in trade
                            self.new_max_after_entry = True
            else:
                self.wheat_ma = np.nan  # Not enough data yet

        # --- Forced Test Trade Logic ---
        if self.forced_test_trade and timestamp == self.forced_trade_timestamp:
            print(f"T{timestamp}: EXECUTING FORCED TEST TRADE")
            # Test selling ORE and buying VP
            final_orders["ORE"] = -self.trade_size
            final_orders["VP"] = self.trade_size
            print(
                f"T{timestamp}: Forced trade orders: SELL ORE {-self.trade_size}, BUY VP {self.trade_size}"
            )

            # After forced trade, disable so it doesn't repeat if we re-enter this timestamp
            self.forced_test_trade = False

            # Don't execute normal strategy logic when forcing a trade
            state_changed = True
            history_entry = {
                "timestamp": timestamp,
                "positions": self.positions.copy(),
                "orders": final_orders.copy(),
                "wheat_ma": self.wheat_ma,
                "rolling_min_ma": (
                    np.nan if np.isinf(self.rolling_min_ma) else self.rolling_min_ma
                ),
                "rolling_max_ma": (
                    np.nan if np.isinf(self.rolling_max_ma) else self.rolling_max_ma
                ),
                "state": "FORCED_TRADE",
            }
            self.history.append(history_entry)
            return final_orders

        # --- State Machine Logic ---
        state_changed = False  # Track if state changes for logging

        # --- State: NEUTRAL ---
        if self.current_state == "NEUTRAL":
            if not np.isnan(self.wheat_ma) and not np.isinf(self.rolling_min_ma):
                # Log values every 50 ticks for debugging
                if timestamp % 50 == 0:
                    print(
                        f"T{timestamp}: WHEAT MA={self.wheat_ma:.2f}, Min={self.rolling_min_ma:.2f}, Max={self.rolling_max_ma:.2f}, Threshold={self.rolling_min_ma * (1 + self.wheat_threshold_pct):.2f}"
                    )

                # Check for threshold cross: Current MA > Rolling Min * (1 + Threshold)
                if self.wheat_ma > (
                    self.rolling_min_ma * (1 + self.wheat_threshold_pct)
                ):
                    print(
                        f"T{timestamp}: Signal Triggered! WHEAT MA {self.wheat_ma:.2f} crossed threshold above min {self.rolling_min_ma:.2f}"
                    )
                    self.current_state = "SIGNAL_TRIGGERED"
                    self.signal_timestamp = timestamp
                    # Record entry prices for ORE/VP at the signal time for later comparison
                    if "ORE" in current_data:
                        self.entry_price_ore = (
                            current_data["ORE"]["Bid"] + current_data["ORE"]["Ask"]
                        ) / 2
                    if "VP" in current_data:
                        self.entry_price_vp = (
                            current_data["VP"]["Bid"] + current_data["VP"]["Ask"]
                        ) / 2
                    self.new_max_after_entry = False  # Reset exit flag
                    # Reset rolling max: Start looking for a new peak *after* this signal
                    self.rolling_max_ma = self.wheat_ma

        # --- State: SIGNAL_TRIGGERED ---
        elif self.current_state == "SIGNAL_TRIGGERED":
            if timestamp >= self.signal_timestamp + self.holding_period:
                print(f"T{timestamp}: Holding period ended. Evaluating ORE vs VP.")
                ore_current_price = np.nan
                vp_current_price = np.nan

                if "ORE" in current_data:
                    ore_current_price = (
                        current_data["ORE"]["Bid"] + current_data["ORE"]["Ask"]
                    ) / 2
                if "VP" in current_data:
                    vp_current_price = (
                        current_data["VP"]["Bid"] + current_data["VP"]["Ask"]
                    ) / 2

                # Check if we have valid prices for comparison
                if (
                    not np.isnan(self.entry_price_ore)
                    and not np.isnan(ore_current_price)
                    and not np.isnan(self.entry_price_vp)
                    and not np.isnan(vp_current_price)
                ):

                    ore_change = (
                        ore_current_price - self.entry_price_ore
                    ) / self.entry_price_ore
                    vp_change = (
                        vp_current_price - self.entry_price_vp
                    ) / self.entry_price_vp

                    print(
                        f"T{timestamp}: ORE Change: {ore_change*100:.2f}%, VP Change: {vp_change*100:.2f}%"
                    )

                    # Determine which to buy/sell
                    if (
                        ore_change >= vp_change
                    ):  # Sell ORE (better performer), Buy VP (worse performer)
                        print(f"T{timestamp}: Entering Trade: SELL ORE, BUY VP")
                        final_orders["ORE"] = -self.trade_size
                        final_orders["VP"] = self.trade_size
                    else:  # Sell VP (better performer), Buy ORE (worse performer)
                        print(f"T{timestamp}: Entering Trade: BUY ORE, SELL VP")
                        final_orders["ORE"] = self.trade_size
                        final_orders["VP"] = -self.trade_size

                    self.current_state = "IN_TRADE"

                else:  # This block handles missing price data
                    print(
                        f"T{timestamp}: Missing price data for ORE/VP comparison. Resetting state."
                    )
                    self.current_state = "NEUTRAL"  # Reset if data is missing
                    # Reset entry prices
                    self.entry_price_ore = np.nan
                    self.entry_price_vp = np.nan

            # else: still waiting for holding period to end

        # --- State: IN_TRADE ---
        elif self.current_state == "IN_TRADE":
            # Exit Condition: New WHEAT MA maximum reached *after* entering the trade
            if self.new_max_after_entry:
                print(
                    f"T{timestamp}: Exit Condition Met! WHEAT MA hit new max {self.rolling_max_ma:.2f} after entry."
                )
                # Go flat on ORE and VP
                if "ORE" in self.positions:
                    final_orders["ORE"] = -self.positions.get("ORE", 0)
                if "VP" in self.positions:
                    final_orders["VP"] = -self.positions.get("VP", 0)

                self.current_state = "NEUTRAL"
                self.entry_price_ore = np.nan  # Reset entry prices
                self.entry_price_vp = np.nan
                self.new_max_after_entry = False
                # Reset rolling min: Start looking for a new trough *after* this exit
                if not np.isnan(self.wheat_ma):
                    self.rolling_min_ma = self.wheat_ma
                # Important: Reset rolling min/max after exit to avoid immediate re-entry signal based on old levels
                # self.rolling_min_ma = np.inf # Let the natural update handle this on next tick
                # self.rolling_max_ma = -np.inf

        # --- Record History (including orders and MA) ---
        history_entry = {
            "timestamp": timestamp,
            "positions": self.positions.copy(),  # Positions *before* orders are applied by backtester
            "orders": final_orders.copy(),
            "wheat_ma": self.wheat_ma,
            "rolling_min_ma": (
                np.nan if np.isinf(self.rolling_min_ma) else self.rolling_min_ma
            ),  # Ensure inf becomes nan
            "rolling_max_ma": (
                np.nan if np.isinf(self.rolling_max_ma) else self.rolling_max_ma
            ),  # Ensure inf becomes nan
            "state": self.current_state,
            "state_changed": state_changed,
        }
        self.history.append(history_entry)

        return final_orders


# --- Plotting Execution (if script is run directly) ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run trading algorithm or plot prices."
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Generate and show the price plot instead of running the algorithm simulation.",
    )
    args = parser.parse_args()

    if args.plot:
        print(
            "Plotting mode activated. Requires manual run history (not applicable with atexit)."
        )
        print(
            "Please run backtester_updated.py first to generate history, then use atexit plotting."
        )
    else:
        print(
            "Template file loaded. Run backtester_updated.py to execute the algorithm and generate plot on exit."
        )

# --- Backtester Interface ---

# Leave this stuff as it is
team_algorithm = TradingAlgorithm()


def getOrders(current_data, positions):
    # Update the positions in the algorithm instance *before* getOrders is called
    # This reflects the state after the previous timestamp's trades were applied
    team_algorithm.positions = positions
    # The order_data passed here is just a template {product: 0}, the algo fills it
    order_data_template = {product: 0 for product in current_data}
    return team_algorithm.getOrders(current_data, order_data_template)
