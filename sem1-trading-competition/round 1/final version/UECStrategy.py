from BaseStrategy import BaseStrategy
import numpy as np


class UECStrategy(BaseStrategy):
    """UEC Trading Strategy.

    This strategy trades UEC based on short and long moving averages
    with enhanced features for handling high spread periods and early exits.
    """

    def __init__(
        self,
        name="UEC Strategy",
        visualize_on_exit=True,
        short_window=83,
        long_window=500,
        waiting_period=78,
        high_spread_threshold=1.3,
        position_size=100,
        hs_exit_change_threshold=0.05,
        ma_turn_threshold=0.8299,
    ):
        """Initialize the UEC strategy.

        Args:
            name: Strategy name
            visualize_on_exit: Whether to visualize on exit
            short_window: Window size for short-term moving average
            long_window: Window size for long-term moving average
            waiting_period: Wait period after high spread exit
            high_spread_threshold: Threshold for high spread detection
            position_size: Size of positions to take
            hs_exit_change_threshold: Threshold for re-entry after high spread
            ma_turn_threshold: Threshold for early exit based on MA turning
        """
        super().__init__(name, visualize_on_exit)

        # Strategy parameters
        self.SHORT_WINDOW = short_window
        self.LONG_WINDOW = long_window
        self.WAITING_PERIOD = waiting_period
        self.HIGH_SPREAD_THRESHOLD = high_spread_threshold
        self.POSITION_SIZE = position_size
        self.HS_EXIT_CHANGE_THRESHOLD = hs_exit_change_threshold
        self.MA_TURN_THRESHOLD = ma_turn_threshold

        # Strategy state variables
        self.high_spread_exit_index = -1
        self.waiting_for_signal = False
        self.last_high_spread_exit_short_avg = None
        self.current_position_extreme = None
        self.in_position = False
        self.position_is_long = None

    def initialize_data(self):
        """Reset all data structures and state variables."""
        super().initialize_data()

        # Reset strategy state variables
        self.high_spread_exit_index = -1
        self.waiting_for_signal = False
        self.last_high_spread_exit_short_avg = None
        self.current_position_extreme = None
        self.in_position = False
        self.position_is_long = None

    def getOrders(self, current_data, positions):
        """Implement the UEC trading strategy.

        Args:
            current_data: Dictionary of current market data
            positions: Dictionary of current positions

        Returns:
            Dictionary of orders to execute
        """
        if len(self.historical_data["timestamp"]) == 0:
            self.initialize_data()

        orders = {p: 0 for p in current_data}

        for product, product_info in current_data.items():
            timestamp = product_info["Timestamp"]
            bid = product_info["Bid"]
            ask = product_info["Ask"]
            mid_price = (bid + ask) / 2
            spread = ask - bid

            current_position = positions[product]
            in_high_spread = spread >= self.HIGH_SPREAD_THRESHOLD

            # Compute short-term rolling average
            short_avg = None
            if len(self.historical_data["mid_price"]) >= self.SHORT_WINDOW:
                vals = self.historical_data["mid_price"][-self.SHORT_WINDOW :]
                short_avg = np.mean(vals)

            # Compute long-term average (for plotting)
            long_avg = None
            if len(self.historical_data["mid_price"]) >= self.LONG_WINDOW:
                vals_long = self.historical_data["mid_price"][-self.LONG_WINDOW :]
                long_avg = np.mean(vals_long)

            order_quantity = 0
            trade_profit = 0

            # --------------------------------------------------------
            # 0) If we're in a position => see if short avg turned
            #    from our local extreme by more than MA_TURN_THRESHOLD
            #    If yes => exit.
            # --------------------------------------------------------
            if short_avg is not None and self.in_position:
                if self.position_is_long:
                    # If short_avg > current_position_extreme => update it
                    if short_avg > self.current_position_extreme:
                        self.current_position_extreme = short_avg
                    else:
                        # If we've fallen from the extreme by > threshold => close
                        if (
                            self.current_position_extreme - short_avg
                            >= self.MA_TURN_THRESHOLD
                        ):
                            # Early exit
                            exit_index = len(self.historical_data["timestamp"])
                            entry_index = None
                            # find last time we had position=0
                            for i in range(
                                len(self.historical_data["position"]) - 1, -1, -1
                            ):
                                if self.historical_data["position"][i] == 0:
                                    entry_index = i + 1
                                    break

                            if entry_index is not None:
                                entry_price = self.historical_data["mid_price"][
                                    entry_index
                                ]
                                exit_price = mid_price
                                trade_profit = self.record_trade_section(
                                    entry_index,
                                    exit_index,
                                    entry_price,
                                    exit_price,
                                    current_position,
                                )

                            order_quantity = -current_position
                            if order_quantity > 0:
                                self.record_trade(timestamp, ask, order_quantity, "buy")
                            elif order_quantity < 0:
                                self.record_trade(
                                    timestamp, bid, order_quantity, "sell"
                                )

                            # reset
                            self.in_position = False
                            self.position_is_long = None
                            self.current_position_extreme = None

                else:
                    # We are short
                    if short_avg < self.current_position_extreme:
                        self.current_position_extreme = short_avg
                    else:
                        # If we've risen from the extreme by > threshold => close
                        if (
                            short_avg - self.current_position_extreme
                            >= self.MA_TURN_THRESHOLD
                        ):
                            exit_index = len(self.historical_data["timestamp"])
                            entry_index = None
                            for i in range(
                                len(self.historical_data["position"]) - 1, -1, -1
                            ):
                                if self.historical_data["position"][i] == 0:
                                    entry_index = i + 1
                                    break

                            if entry_index is not None:
                                entry_price = self.historical_data["mid_price"][
                                    entry_index
                                ]
                                exit_price = mid_price
                                trade_profit = self.record_trade_section(
                                    entry_index,
                                    exit_index,
                                    entry_price,
                                    exit_price,
                                    current_position,
                                )

                            order_quantity = -current_position
                            if order_quantity > 0:
                                self.record_trade(timestamp, ask, order_quantity, "buy")
                            elif order_quantity < 0:
                                self.record_trade(
                                    timestamp, bid, order_quantity, "sell"
                                )

                            # reset
                            self.in_position = False
                            self.position_is_long = None
                            self.current_position_extreme = None

            # --------------------------------------------------------
            # CASE 1: We just exited a high spread
            # --------------------------------------------------------
            if (
                len(self.historical_data["in_high_spread"]) > 0
                and self.historical_data["in_high_spread"][-1]
                and not in_high_spread
            ):
                hs_start = next(
                    (
                        i
                        for i in range(
                            len(self.historical_data["in_high_spread"]) - 1, -1, -1
                        )
                        if not self.historical_data["in_high_spread"][i]
                    ),
                    0,
                )
                if hs_start < len(self.historical_data["in_high_spread"]) - 1:
                    self.record_high_spread_period(
                        hs_start + 1, len(self.historical_data["in_high_spread"]) - 1
                    )

                self.high_spread_exit_index = len(self.historical_data["timestamp"]) - 1

                if short_avg is not None:
                    self.last_high_spread_exit_short_avg = short_avg
                else:
                    self.last_high_spread_exit_short_avg = mid_price

                self.waiting_for_signal = True
                self.waiting_periods.append(
                    {
                        "start": self.high_spread_exit_index,
                        "end": self.high_spread_exit_index + self.WAITING_PERIOD,
                    }
                )

            # --------------------------------------------------------
            # CASE 2: We waited WAITING_PERIOD => check threshold for new entry
            # --------------------------------------------------------
            elif (
                self.waiting_for_signal
                and len(self.historical_data["timestamp"]) - self.high_spread_exit_index
                >= self.WAITING_PERIOD
                and current_position == 0
                and not in_high_spread
            ):
                if (
                    short_avg is not None
                    and self.last_high_spread_exit_short_avg is not None
                ):
                    diff = abs(short_avg - self.last_high_spread_exit_short_avg)
                    if diff >= self.HS_EXIT_CHANGE_THRESHOLD:
                        # Normal logic
                        if mid_price > short_avg:
                            order_quantity = self.POSITION_SIZE
                            self.record_trade(timestamp, ask, order_quantity, "buy")

                            # NEW: we are now in a position => track extremes
                            self.in_position = True
                            self.position_is_long = True
                            self.current_position_extreme = short_avg  # initial max

                        elif mid_price < short_avg:
                            order_quantity = -self.POSITION_SIZE
                            self.record_trade(timestamp, bid, order_quantity, "sell")

                            self.in_position = True
                            self.position_is_long = False
                            self.current_position_extreme = short_avg  # initial min

                        self.waiting_for_signal = False

            # --------------------------------------------------------
            # CASE 3: In high spread + have a position => immediate close
            #         (No more hold-during-high-spread logic.)
            # --------------------------------------------------------
            elif in_high_spread and current_position != 0:
                exit_index = len(self.historical_data["timestamp"])
                entry_index = None
                for i in range(len(self.historical_data["position"]) - 1, -1, -1):
                    if self.historical_data["position"][i] == 0:
                        entry_index = i + 1
                        break

                if entry_index is not None:
                    entry_price = self.historical_data["mid_price"][entry_index]
                    exit_price = mid_price
                    trade_profit = self.record_trade_section(
                        entry_index,
                        exit_index,
                        entry_price,
                        exit_price,
                        current_position,
                    )

                order_quantity = -current_position
                if order_quantity > 0:
                    self.record_trade(timestamp, ask, order_quantity, "buy")
                elif order_quantity < 0:
                    self.record_trade(timestamp, bid, order_quantity, "sell")

                # reset universal position
                self.in_position = False
                self.position_is_long = None
                self.current_position_extreme = None

            # --------------------------------------------------------
            # Update history
            # --------------------------------------------------------
            new_position = current_position + order_quantity
            self.update_historical_data(
                timestamp,
                product_info,
                short_avg,
                long_avg,
                new_position,
                in_high_spread,
                trade_profit,
            )

            orders[product] = order_quantity

        return orders

    def _add_strategy_specific_visualization(self, ax, df):
        """Add UEC strategy-specific visualization elements."""
        # Mark early exits with a distinct marker
        early_exits = []
        for i in range(1, len(df)):
            if df["position"][i] == 0 and df["position"][i - 1] != 0:
                # Find the entry point
                entry_idx = None
                for j in range(i - 1, -1, -1):
                    if df["position"][j] == 0:
                        entry_idx = j + 1
                        break
                if entry_idx is not None:
                    if (
                        df["short_avg"][i] is not None
                        and df["short_avg"][entry_idx] is not None
                    ):
                        if df["position"][i - 1] > 0:  # Long position
                            if (
                                df["short_avg"][entry_idx] - df["short_avg"][i]
                                >= self.MA_TURN_THRESHOLD
                            ):
                                early_exits.append(i)
                        else:  # Short position
                            if (
                                df["short_avg"][i] - df["short_avg"][entry_idx]
                                >= self.MA_TURN_THRESHOLD
                            ):
                                early_exits.append(i)

        if early_exits:
            exit_x = [df["timestamp"][i] for i in early_exits]
            exit_y = [df["mid_price"][i] for i in early_exits]
            ax.scatter(
                exit_x,
                exit_y,
                marker="x",
                s=200,
                color="magenta",
                label="Early Exit",
                zorder=6,
                linewidth=3,
            )
            for i in early_exits:
                ax.annotate(
                    f"{df['mid_price'][i]:.2f}",
                    (df["timestamp"][i], df["mid_price"][i]),
                    xytext=(0, 15),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    color="magenta",
                    bbox=dict(
                        boxstyle="round,pad=0.3", fc="white", ec="magenta", alpha=0.7
                    ),
                )

    def _get_additional_stats(self):
        """Get UEC strategy-specific statistics."""
        # Get early exits
        df = None
        if len(self.historical_data["timestamp"]) > 0:
            import pandas as pd

            df = pd.DataFrame(self.historical_data)

            early_exits = []
            for i in range(1, len(df)):
                if df["position"][i] == 0 and df["position"][i - 1] != 0:
                    # Find the entry point
                    entry_idx = None
                    for j in range(i - 1, -1, -1):
                        if df["position"][j] == 0:
                            entry_idx = j + 1
                            break
                    if entry_idx is not None:
                        if (
                            df["short_avg"][i] is not None
                            and df["short_avg"][entry_idx] is not None
                        ):
                            if df["position"][i - 1] > 0:  # Long position
                                if (
                                    df["short_avg"][entry_idx] - df["short_avg"][i]
                                    >= self.MA_TURN_THRESHOLD
                                ):
                                    early_exits.append(i)
                            else:  # Short position
                                if (
                                    df["short_avg"][i] - df["short_avg"][entry_idx]
                                    >= self.MA_TURN_THRESHOLD
                                ):
                                    early_exits.append(i)

            return (
                f"SHORT_WINDOW: {self.SHORT_WINDOW}\n"
                f"LONG_WINDOW: {self.LONG_WINDOW}\n"
                f"WAITING_PERIOD: {self.WAITING_PERIOD}\n"
                f"HIGH_SPREAD_THRESHOLD: {self.HIGH_SPREAD_THRESHOLD}\n"
                f"HS_EXIT_CHANGE_THRESHOLD: {self.HS_EXIT_CHANGE_THRESHOLD}\n"
                f"MA_TURN_THRESHOLD: {self.MA_TURN_THRESHOLD}\n"
                f"Early Exits: {len(early_exits)}"
            )

        return (
            f"SHORT_WINDOW: {self.SHORT_WINDOW}\n"
            f"LONG_WINDOW: {self.LONG_WINDOW}\n"
            f"WAITING_PERIOD: {self.WAITING_PERIOD}\n"
            f"HIGH_SPREAD_THRESHOLD: {self.HIGH_SPREAD_THRESHOLD}\n"
            f"HS_EXIT_CHANGE_THRESHOLD: {self.HS_EXIT_CHANGE_THRESHOLD}\n"
            f"MA_TURN_THRESHOLD: {self.MA_TURN_THRESHOLD}\n"
        )
