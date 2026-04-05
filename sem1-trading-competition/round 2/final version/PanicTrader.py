import random
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import webbrowser
from typing import Dict


class TradingAlgorithm:

    def __init__(self):
        # Parameters
        self.leader_asset = "FAWA"  # Leading asset
        self.follower_asset = "SMIF"  # Following asset
        self.leader_window = 39 # Longer window for leader
        self.follower_window = 5  # Shorter window for follower
        self.direction_threshold_pct = (
            1.4 # Percentage threshold for significant moves
        )
        self.max_position = 100  # Maximum position size

        # State tracking
        self.positions = {}
        self.primed = False  # Whether we've detected a signal in the leader
        self.primed_direction = (
            0  # Direction of the primed signal (1 for up, -1 for down)
        )
        self.last_primed_direction = 0  # Last direction we primed for
        self.waiting_for_follower = (
            False  # Whether we're waiting for follower confirmation
        )
        self.in_position = False  # Whether we're currently in a position
        self.can_prime_long = True  # Whether we can prime for a long position
        self.can_prime_short = True  # Whether we can prime for a short position

        # Data tracking
        self.historical_data = {}
        self.trades = []
        self.product_stats = {}

        # For tracking local extremes
        self.leader_max_sma = None
        self.leader_min_sma = None
        self.leader_last_direction = 0

        # Visualization
        self.plots_dir = "panic_trader_plots"
        if not os.path.exists(self.plots_dir):
            os.makedirs(self.plots_dir)
        self.html_path = None

    def _initialize_product_tracking(self, product):
        """Initialize data tracking for a new product"""
        if product not in self.historical_data:
            self.historical_data[product] = {
                "timestamp": [],
                "bid": [],
                "ask": [],
                "mid_price": [],
                "position": [],
                "trade_action": [],  # 'buy', 'sell', or 'none'
                "trade_price": [],
                "sma": [],  # SMA values
                "direction": [],  # Direction values
                "signal_marked": [],  # For visualization
                "entry_signal": [],  # For visualization
                "last_max": [],  # For tracking local extremes
                "last_min": [],  # For tracking local extremes
                "pct_change_from_max": [],
                "pct_change_from_min": [],
            }
            self.product_stats[product] = {"total_trades": 0}

    def _update_historical_data(
        self,
        product,
        timestamp,
        bid,
        ask,
        position,
        trade_action,
        trade_price=None,
        sma=None,
        direction=0,
        signal_marked=False,
        entry_signal=False,
        last_max=None,
        last_min=None,
        pct_change_from_max=None,
        pct_change_from_min=None,
    ):
        """Update historical data for a product"""
        self._initialize_product_tracking(product)
        mid_price = (bid + ask) / 2

        self.historical_data[product]["timestamp"].append(timestamp)
        self.historical_data[product]["bid"].append(bid)
        self.historical_data[product]["ask"].append(ask)
        self.historical_data[product]["mid_price"].append(mid_price)
        self.historical_data[product]["position"].append(position)
        self.historical_data[product]["trade_action"].append(trade_action)
        self.historical_data[product]["trade_price"].append(
            trade_price if trade_price else mid_price
        )
        self.historical_data[product]["sma"].append(sma)
        self.historical_data[product]["direction"].append(direction)
        self.historical_data[product]["signal_marked"].append(signal_marked)
        self.historical_data[product]["entry_signal"].append(entry_signal)
        self.historical_data[product]["last_max"].append(last_max)
        self.historical_data[product]["last_min"].append(last_min)
        self.historical_data[product]["pct_change_from_max"].append(pct_change_from_max)
        self.historical_data[product]["pct_change_from_min"].append(pct_change_from_min)

        # Record trade for analysis
        if trade_action != "none":
            if trade_action == "buy":
                entry_price = ask
                quantity = self.max_position
            else:  # sell
                entry_price = bid
                quantity = -self.max_position

            self.trades.append(
                {
                    "product": product,
                    "timestamp": timestamp,
                    "action": trade_action,
                    "price": entry_price,
                    "quantity": quantity,
                }
            )

            # Update product stats
            self.product_stats[product]["total_trades"] += 1

    def _calculate_sma(self, product, window):
        """Calculate the simple moving average for a product's mid price"""
        if len(self.historical_data[product]["mid_price"]) >= window:
            mid_prices = self.historical_data[product]["mid_price"][-window:]
            return np.mean(mid_prices)
        return None

    def _calculate_direction(self, current_sma, previous_sma):
        """Calculate direction of SMA change (1 for up, -1 for down, 0 for flat)"""
        if current_sma is None or previous_sma is None:
            return 0

        if current_sma > previous_sma:
            return 1
        elif current_sma < previous_sma:
            return -1
        return 0

    def _update_extremes(self, sma_value, direction):
        """Update local extremes for the leader based on direction changes"""
        # Initialize on first valid data point
        if self.leader_max_sma is None:
            self.leader_max_sma = sma_value
            self.leader_min_sma = sma_value
            self.leader_last_direction = direction
            return

        # Update running extremes based on current direction
        if direction == 1:  # Uptrend
            # Always update the maximum on uptrends
            if sma_value > self.leader_max_sma:
                self.leader_max_sma = sma_value

            # Only reset minimum if direction changed from down to up
            if self.leader_last_direction == -1:
                self.leader_min_sma = sma_value

        elif direction == -1:  # Downtrend
            # Always update the minimum on downtrends
            if sma_value < self.leader_min_sma:
                self.leader_min_sma = sma_value

            # Only reset maximum if direction changed from up to down
            if self.leader_last_direction == 1:
                self.leader_max_sma = sma_value

        # Store last direction for next comparison
        if direction != 0:
            self.leader_last_direction = direction

    def _check_significant_move(self, sma_value, direction):
        """Check if there's a significant price move from the last extreme"""
        if direction == 0 or self.leader_max_sma is None or self.leader_min_sma is None:
            return False, None, None

        # Calculate the percentage change from the relevant extreme
        pct_change_from_max = None
        pct_change_from_min = None

        if direction == 1:  # Uptrend - check move from recent minimum
            if self.leader_min_sma > 0:  # Avoid division by zero
                pct_change_from_min = (
                    (sma_value - self.leader_min_sma) / self.leader_min_sma
                ) * 100
                significant = pct_change_from_min >= self.direction_threshold_pct
            else:
                significant = False

        else:  # Downtrend - check move from recent maximum
            if self.leader_max_sma > 0:  # Avoid division by zero
                pct_change_from_max = (
                    (sma_value - self.leader_max_sma) / self.leader_max_sma
                ) * 100
                significant = pct_change_from_max <= -self.direction_threshold_pct
            else:
                significant = False

        return significant, pct_change_from_max, pct_change_from_min

    def getOrders(
        self, current_data: Dict[str, Dict[str, float]], order_data: Dict[str, int]
    ) -> Dict[str, int]:
        """Main strategy implementation with lead-follow logic"""
        # Skip if we don't have data for both assets
        if (
            self.leader_asset not in current_data
            or self.follower_asset not in current_data
        ):
            return order_data

        # Extract current data
        leader_data = current_data[self.leader_asset]
        follower_data = current_data[self.follower_asset]

        timestamp = leader_data["Timestamp"]
        leader_bid = leader_data["Bid"]
        leader_ask = leader_data["Ask"]
        leader_position = self.positions.get(self.leader_asset, 0)

        follower_bid = follower_data["Bid"]
        follower_ask = follower_data["Ask"]
        follower_position = self.positions.get(self.follower_asset, 0)

        # Initialize data tracking if not already done
        self._initialize_product_tracking(self.leader_asset)
        self._initialize_product_tracking(self.follower_asset)

        # Default values
        leader_trade_action = "none"
        follower_trade_action = "none"
        leader_trade_price = None
        follower_trade_price = None
        leader_signal_marked = False
        follower_entry_signal = False
        pct_change_from_max = None
        pct_change_from_min = None

        # Calculate SMAs for both assets
        leader_sma = self._calculate_sma(self.leader_asset, self.leader_window)
        follower_sma = self._calculate_sma(self.follower_asset, self.follower_window)

        # Get previous SMA values for direction calculation
        prev_leader_sma = (
            self.historical_data[self.leader_asset]["sma"][-1]
            if self.historical_data[self.leader_asset]["sma"]
            else None
        )
        prev_follower_sma = (
            self.historical_data[self.follower_asset]["sma"][-1]
            if self.historical_data[self.follower_asset]["sma"]
            else None
        )

        # Calculate directions
        leader_direction = self._calculate_direction(leader_sma, prev_leader_sma)
        follower_direction = self._calculate_direction(follower_sma, prev_follower_sma)

        # Debug variables
        signal_reason = "No signal"

        # Only proceed if we have enough data
        if leader_sma is not None and follower_sma is not None:
            # Update extremes for the leader
            self._update_extremes(leader_sma, leader_direction)

            # Check for significant moves in the leader
            significant_move, pct_change_from_max, pct_change_from_min = (
                self._check_significant_move(leader_sma, leader_direction)
            )

            # Debug print
            # print(f"[DEBUG] t={timestamp}, leader_dir={leader_direction}, follower_dir={follower_direction}, "
            #      f"min={self.leader_min_sma}, max={self.leader_max_sma}, "
            #      f"pct_from_min={pct_change_from_min}, pct_from_max={pct_change_from_max}, "
            #      f"significant={significant_move}, primed={self.primed}, primed_dir={self.primed_direction}")

            # Clear diagram states
            follower_desired_position = follower_position

            # Check if we're in a position
            self.in_position = follower_position != 0

            # Strategy logic: State machine
            if not self.primed:
                # Not primed yet - look for a significant move in the leader
                # Only prime if:
                # 1. We've detected a significant move AND
                # 2. We can prime in that direction (haven't already primed this direction without trading)
                if significant_move:
                    can_prime = (leader_direction == 1 and self.can_prime_long) or (
                        leader_direction == -1 and self.can_prime_short
                    )

                    if can_prime:
                        # Mark as primed and save the direction
                        self.primed = True
                        self.primed_direction = leader_direction
                        self.last_primed_direction = leader_direction
                        self.waiting_for_follower = True

                        # Block further priming in this direction until we reset
                        if leader_direction == 1:
                            self.can_prime_long = False
                        else:
                            self.can_prime_short = False

                        leader_signal_marked = True  # For visualization
                        # signal_reason = f"PRIMED {self.primed_direction} at {timestamp}"
                        # print(f"PRIMED: {signal_reason}")
            else:
                # Already primed - look for follower confirmation
                if follower_direction == self.primed_direction:
                    # Follower confirmed the direction - take position
                    # But first, let's check if we would be repeating the same action
                    would_repeat_action = False

                    if (
                        self.primed_direction == 1
                        and follower_position >= self.max_position
                    ):
                        # Already long, don't buy again
                        would_repeat_action = True
                        # print(
                        #     f"SKIPPED ENTRY at {timestamp}: Already long, won't buy again"
                        # )
                    elif (
                        self.primed_direction == -1
                        and follower_position <= -self.max_position
                    ):
                        # Already short, don't sell again
                        would_repeat_action = True
                        # print(
                        #     f"SKIPPED ENTRY at {timestamp}: Already short, won't sell again"
                        # )

                    if not would_repeat_action:
                        follower_entry_signal = True  # For visualization

                        # Determine the desired position based on direction
                        if self.primed_direction == 1:  # Going long
                            # If we're currently short, first exit the position
                            if follower_position < 0:
                                pass  # Log removed
                                # print(
                                #     f"REVERSING: Exiting short position before going long at {timestamp}"
                                # )

                            follower_desired_position = self.max_position
                            follower_trade_action = "buy"
                            follower_trade_price = follower_ask
                        else:  # Going short
                            # If we're currently long, first exit the position
                            if follower_position > 0:
                                pass  # Log removed
                                # print(
                                #     f"REVERSING: Exiting long position before going short at {timestamp}"
                                # )

                            follower_desired_position = -self.max_position
                            follower_trade_action = "sell"
                            follower_trade_price = follower_bid

                        # Reset the primed state
                        self.primed = False
                        self.waiting_for_follower = False  # Reset waiting state

                        # signal_reason = f"ENTRY {self.primed_direction} at {timestamp}"
                        # print(f"ENTRY: {signal_reason}")
                    else:
                        # Reset the primed state even if we didn't trade
                        self.primed = False
                        self.waiting_for_follower = False

                # Only reprime in the opposite direction
                elif (
                    significant_move
                    and leader_direction != 0
                    and leader_direction != self.primed_direction
                ):
                    # Only allow repriming if we can prime in that direction
                    can_reprime = (leader_direction == 1 and self.can_prime_long) or (
                        leader_direction == -1 and self.can_prime_short
                    )

                    if can_reprime:
                        # Update primed direction
                        self.primed_direction = leader_direction
                        self.last_primed_direction = leader_direction

                        # Block further priming in this new direction
                        if leader_direction == 1:
                            self.can_prime_long = False
                        else:
                            self.can_prime_short = False

                        leader_signal_marked = True  # For visualization
                        # signal_reason = (
                        #     f"REPRIMED {self.primed_direction} at {timestamp}"
                        # )
                        # print(f"REPRIMED: {signal_reason}")

            # Calculate the order size as the difference between desired and current position
            follower_order_size = follower_desired_position - follower_position
            if follower_order_size != 0:
                order_data[self.follower_asset] = follower_order_size

                # If we're closing a position, reset the can_prime flags
                if (follower_position > 0 and follower_desired_position <= 0) or (
                    follower_position < 0 and follower_desired_position >= 0
                ):
                    # Reset permission to prime in both directions after closing position
                    self.can_prime_long = True
                    self.can_prime_short = True
                    # print(
                    #     f"POSITION CLOSED at {timestamp}, can prime in both directions again"
                    # )

        # Update historical data for both assets
        new_leader_position = leader_position + order_data.get(self.leader_asset, 0)
        new_follower_position = follower_position + order_data.get(
            self.follower_asset, 0
        )

        self._update_historical_data(
            self.leader_asset,
            timestamp,
            leader_bid,
            leader_ask,
            new_leader_position,
            leader_trade_action,
            leader_trade_price,
            leader_sma,
            leader_direction,
            leader_signal_marked,
            False,  # Entry not relevant for leader
            self.leader_max_sma,
            self.leader_min_sma,
            pct_change_from_max,
            pct_change_from_min,
        )

        self._update_historical_data(
            self.follower_asset,
            timestamp,
            follower_bid,
            follower_ask,
            new_follower_position,
            follower_trade_action,
            follower_trade_price,
            follower_sma,
            follower_direction,
            False,  # Signal not relevant for follower
            follower_entry_signal,
            None,  # Max not tracked for follower
            None,  # Min not tracked for follower
            None,  # % change not tracked for follower
            None,  # % change not tracked for follower
        )

        return order_data

    def visualize_strategy(self):
        """Create interactive visualizations for the lead-follow strategy"""
        # Create figure with dual y-axes for prices and a subplot for positions
        fig = make_subplots(
            rows=2,
            cols=1,
            specs=[[{"secondary_y": True}], [{"secondary_y": False}]],
            shared_xaxes=True,
            vertical_spacing=0.1,
            row_heights=[0.7, 0.3],
            subplot_titles=(
                "Lead-Follow Strategy: FAWA leads, SMIF follows",
                "Position History",
            ),
        )

        # Convert data to DataFrames
        product_dfs = {}
        for product in self.historical_data:
            if len(self.historical_data[product]["timestamp"]) > 0:
                product_dfs[product] = pd.DataFrame(self.historical_data[product])

        if len(product_dfs) < 2:
            # print("Not enough data to visualize")
            return

        # Add leader price
        fig.add_trace(
            go.Scatter(
                x=product_dfs[self.leader_asset]["timestamp"],
                y=product_dfs[self.leader_asset]["mid_price"],
                mode="lines",
                name=f"{self.leader_asset} Price",
                line=dict(color="blue", width=1),
            ),
            row=1,
            col=1,
            secondary_y=False,
        )

        # Add follower price
        fig.add_trace(
            go.Scatter(
                x=product_dfs[self.follower_asset]["timestamp"],
                y=product_dfs[self.follower_asset]["mid_price"],
                mode="lines",
                name=f"{self.follower_asset} Price",
                line=dict(color="green", width=1),
            ),
            row=1,
            col=1,
            secondary_y=True,
        )

        # Add leader's long-term SMA
        if not all(pd.isna(product_dfs[self.leader_asset]["sma"])):
            sma_vals = product_dfs[self.leader_asset]["sma"]
            fig.add_trace(
                go.Scatter(
                    x=product_dfs[self.leader_asset]["timestamp"],
                    y=sma_vals,
                    mode="lines",
                    name=f"{self.leader_asset} {self.leader_window}-period SMA",
                    line=dict(color="purple", width=2),
                ),
                row=1,
                col=1,
                secondary_y=False,
            )

        # Add follower's short-term SMA
        if not all(pd.isna(product_dfs[self.follower_asset]["sma"])):
            sma_vals = product_dfs[self.follower_asset]["sma"]
            fig.add_trace(
                go.Scatter(
                    x=product_dfs[self.follower_asset]["timestamp"],
                    y=sma_vals,
                    mode="lines",
                    name=f"{self.follower_asset} {self.follower_window}-period SMA",
                    line=dict(color="orange", width=2),
                ),
                row=1,
                col=1,
                secondary_y=True,
            )

        # Add the local max and min lines for leader
        if not all(pd.isna(product_dfs[self.leader_asset]["last_max"])):
            max_vals = product_dfs[self.leader_asset]["last_max"]
            fig.add_trace(
                go.Scatter(
                    x=product_dfs[self.leader_asset]["timestamp"],
                    y=max_vals,
                    mode="lines",
                    name="Local Max",
                    line=dict(color="red", width=1, dash="dash"),
                ),
                row=1,
                col=1,
                secondary_y=False,
            )

        if not all(pd.isna(product_dfs[self.leader_asset]["last_min"])):
            min_vals = product_dfs[self.leader_asset]["last_min"]
            fig.add_trace(
                go.Scatter(
                    x=product_dfs[self.leader_asset]["timestamp"],
                    y=min_vals,
                    mode="lines",
                    name="Local Min",
                    line=dict(color="green", width=1, dash="dash"),
                ),
                row=1,
                col=1,
                secondary_y=False,
            )

        # Add extra lines to visualize percentage changes
        if "pct_change_from_min" in product_dfs[self.leader_asset].columns:
            fig.add_trace(
                go.Scatter(
                    x=product_dfs[self.leader_asset]["timestamp"],
                    y=product_dfs[self.leader_asset]["pct_change_from_min"],
                    mode="lines",
                    name="% Change from Min",
                    line=dict(color="magenta", width=1, dash="dash"),
                ),
                row=1,
                col=1,
                secondary_y=True,
            )

        if "pct_change_from_max" in product_dfs[self.leader_asset].columns:
            fig.add_trace(
                go.Scatter(
                    x=product_dfs[self.leader_asset]["timestamp"],
                    y=product_dfs[self.leader_asset]["pct_change_from_max"],
                    mode="lines",
                    name="% Change from Max",
                    line=dict(color="red", width=1, dash="dash"),
                ),
                row=1,
                col=1,
                secondary_y=True,
            )

        # Mark PRIMED signals (from leader)
        signal_indices = (
            product_dfs[self.leader_asset]
            .index[product_dfs[self.leader_asset]["signal_marked"] == True]
            .tolist()
        )

        if signal_indices:
            direction_values = product_dfs[self.leader_asset].loc[
                signal_indices, "direction"
            ]
            up_indices = [
                idx
                for i, idx in enumerate(signal_indices)
                if direction_values.iloc[i] == 1
            ]
            down_indices = [
                idx
                for i, idx in enumerate(signal_indices)
                if direction_values.iloc[i] == -1
            ]

            if up_indices:
                fig.add_trace(
                    go.Scatter(
                        x=product_dfs[self.leader_asset].loc[up_indices, "timestamp"],
                        y=product_dfs[self.leader_asset].loc[up_indices, "sma"],
                        mode="markers",
                        name="PRIMED: Up",
                        marker=dict(color="green", size=10, symbol="triangle-up"),
                    ),
                    row=1,
                    col=1,
                    secondary_y=False,
                )

            if down_indices:
                fig.add_trace(
                    go.Scatter(
                        x=product_dfs[self.leader_asset].loc[down_indices, "timestamp"],
                        y=product_dfs[self.leader_asset].loc[down_indices, "sma"],
                        mode="markers",
                        name="PRIMED: Down",
                        marker=dict(color="red", size=10, symbol="triangle-down"),
                    ),
                    row=1,
                    col=1,
                    secondary_y=False,
                )

        # Mark ENTRY signals (for follower)
        entry_indices = (
            product_dfs[self.follower_asset]
            .index[product_dfs[self.follower_asset]["entry_signal"] == True]
            .tolist()
        )

        if entry_indices:
            direction_values = product_dfs[self.follower_asset].loc[
                entry_indices, "direction"
            ]
            long_indices = [
                idx
                for i, idx in enumerate(entry_indices)
                if direction_values.iloc[i] == 1
            ]
            short_indices = [
                idx
                for i, idx in enumerate(entry_indices)
                if direction_values.iloc[i] == -1
            ]

            if long_indices:
                fig.add_trace(
                    go.Scatter(
                        x=product_dfs[self.follower_asset].loc[
                            long_indices, "timestamp"
                        ],
                        y=product_dfs[self.follower_asset].loc[
                            long_indices, "mid_price"
                        ],
                        mode="markers",
                        name="ENTRY: Long",
                        marker=dict(color="lime", size=12, symbol="circle"),
                    ),
                    row=1,
                    col=1,
                    secondary_y=True,
                )

            if short_indices:
                fig.add_trace(
                    go.Scatter(
                        x=product_dfs[self.follower_asset].loc[
                            short_indices, "timestamp"
                        ],
                        y=product_dfs[self.follower_asset].loc[
                            short_indices, "mid_price"
                        ],
                        mode="markers",
                        name="ENTRY: Short",
                        marker=dict(color="red", size=12, symbol="circle"),
                    ),
                    row=1,
                    col=1,
                    secondary_y=True,
                )

        # Add buy/sell markers for follower (the asset we actually trade)
        buys_df = product_dfs[self.follower_asset][
            product_dfs[self.follower_asset]["trade_action"] == "buy"
        ]
        sells_df = product_dfs[self.follower_asset][
            product_dfs[self.follower_asset]["trade_action"] == "sell"
        ]

        if len(buys_df) > 0:
            fig.add_trace(
                go.Scatter(
                    x=buys_df["timestamp"],
                    y=buys_df["trade_price"],
                    mode="markers",
                    name=f"{self.follower_asset} Buy",
                    marker=dict(color="darkgreen", size=8, symbol="triangle-up"),
                ),
                row=1,
                col=1,
                secondary_y=True,
            )

        if len(sells_df) > 0:
            fig.add_trace(
                go.Scatter(
                    x=sells_df["timestamp"],
                    y=sells_df["trade_price"],
                    mode="markers",
                    name=f"{self.follower_asset} Sell",
                    marker=dict(color="darkred", size=8, symbol="triangle-down"),
                ),
                row=1,
                col=1,
                secondary_y=True,
            )

        # Add position history traces
        fig.add_trace(
            go.Scatter(
                x=product_dfs[self.leader_asset]["timestamp"],
                y=product_dfs[self.leader_asset]["position"],
                mode="lines",
                name=f"{self.leader_asset} Position",
                line=dict(color="blue", width=1, dash="dot"),
            ),
            row=2,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=product_dfs[self.follower_asset]["timestamp"],
                y=product_dfs[self.follower_asset]["position"],
                mode="lines",
                name=f"{self.follower_asset} Position",
                line=dict(color="green", width=2),
            ),
            row=2,
            col=1,
        )

        # Set layout properties
        trades_count = sum(
            self.product_stats[p]["total_trades"] for p in self.product_stats
        )

        param_str = f"Leader Window: {self.leader_window}, Follower Window: {self.follower_window}, Threshold: {self.direction_threshold_pct}%"
        results_str = f"Total Trades: {trades_count}"

        fig.update_layout(
            title=f"Lead-Follow Trading Strategy<br><sub>{param_str}<br>{results_str}</sub>",
            height=900,
            width=1100,
            legend=dict(x=0.01, y=0.99, bordercolor="LightGray", borderwidth=1),
            hovermode="x unified",
        )

        # Update axes titles
        fig.update_yaxes(title_text=self.leader_asset, secondary_y=False, row=1, col=1)
        fig.update_yaxes(title_text=self.follower_asset, secondary_y=True, row=1, col=1)
        fig.update_yaxes(title_text="Position", row=2, col=1)
        fig.update_xaxes(
            title_text="Tick",
            showgrid=True,
            gridwidth=1,
            gridcolor="LightGray",
            row=2,
            col=1,
        )

        # Add rangeslider to bottom subplot only
        fig.update_xaxes(
            rangeslider=dict(visible=True, thickness=0.05),
            row=2,
            col=1,
        )

        # Print trading statistics
        # print("\nLead-Follow Strategy Results:")
        # print(
        #     f"• Parameters: Leader Window={self.leader_window}, Follower Window={self.follower_window}, Threshold={self.direction_threshold_pct}%"
        # )
        # print(f"• {self.leader_asset} leads, {self.follower_asset} follows")
        # print(f"• Total Trades: {trades_count}")
        # for product in self.product_stats:
        #     print(f"• {product}: {self.product_stats[product]['total_trades']} trades")

        # Save the figure to an HTML file
        self.html_path = os.path.abspath(f"{self.plots_dir}/trading_visualization.html")
        fig.write_html(self.html_path)
        # print(f"\nVisualization saved to: {self.html_path}")

        # Open the file in the default browser
        webbrowser.open(f"file://{self.html_path}", new=2)


# Create trading algorithm instance
team_algorithm = TradingAlgorithm()


def getOrders(current_data, positions):
    team_algorithm.positions = positions
    order_data = {product: 0 for product in current_data}
    return team_algorithm.getOrders(current_data, order_data)
