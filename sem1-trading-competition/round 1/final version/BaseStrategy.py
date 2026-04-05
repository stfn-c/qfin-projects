import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button
import atexit


class BaseStrategy:
    """Base class for all trading strategies.

    This class provides common functionality for trading strategies including
    data handling, visualization, and trade tracking. Specific strategies should
    inherit from this class and implement their own getOrders() method.
    """

    def __init__(self, name, visualize_on_exit=True):
        """Initialize a trading strategy.

        Args:
            name: Name of the strategy
             visualize_on_exit: Whether to automatically visualize when the program exits
        """
        self.name = name
        self.visualize_on_exit = visualize_on_exit

        # Historical data storage for visualization
        self.historical_data = {
            "timestamp": [],
            "bid": [],
            "ask": [],
            "mid_price": [],
            "spread": [],
            "short_avg": [],
            "long_avg": [],
            "position": [],
            "in_high_spread": [],
            "trade_profit": [],
        }

        # Trade tracking
        self.trades = []
        self.high_spread_periods = []
        self.waiting_periods = []
        self.trade_sections = []

        # Register exit handler if needed
        if visualize_on_exit:
            atexit.register(self._exit_handler)

    def _exit_handler(self):
        """Handle program exit by visualizing if needed."""
        if self.visualize_on_exit and len(self.historical_data["timestamp"]) > 0:
            self.visualize_strategy()

    def initialize_data(self):
        """Reset all data structures."""
        self.historical_data = {
            "timestamp": [],
            "bid": [],
            "ask": [],
            "mid_price": [],
            "spread": [],
            "short_avg": [],
            "long_avg": [],
            "position": [],
            "in_high_spread": [],
            "trade_profit": [],
        }
        self.trades.clear()
        self.high_spread_periods.clear()
        self.waiting_periods.clear()
        self.trade_sections.clear()

    def update_historical_data(
        self,
        timestamp,
        product_data,
        short_avg,
        long_avg,
        position,
        in_high_spread,
        trade_profit=0,
    ):
        """Update historical data with current tick information."""
        bid = product_data["Bid"]
        ask = product_data["Ask"]
        mid_price = (bid + ask) / 2
        spread = ask - bid

        self.historical_data["timestamp"].append(timestamp)
        self.historical_data["bid"].append(bid)
        self.historical_data["ask"].append(ask)
        self.historical_data["mid_price"].append(mid_price)
        self.historical_data["spread"].append(spread)
        self.historical_data["short_avg"].append(short_avg)
        self.historical_data["long_avg"].append(long_avg)
        self.historical_data["position"].append(position)
        self.historical_data["in_high_spread"].append(in_high_spread)
        self.historical_data["trade_profit"].append(trade_profit)

    def record_trade(self, timestamp, price, quantity, trade_type):
        """Record a trade for visualization."""
        self.trades.append(
            {
                "timestamp": timestamp,
                "price": price,
                "quantity": quantity,
                "type": trade_type,  # 'buy' or 'sell'
            }
        )

    def record_high_spread_period(self, start, end):
        """Record a high spread period for visualization."""
        if end > start:
            self.high_spread_periods.append({"start": start, "end": end})

    def record_trade_section(
        self, start_idx, end_idx, entry_price, exit_price, position_size
    ):
        """Record a trade section and calculate profit."""
        if end_idx > start_idx:
            profit = (
                (exit_price - entry_price) * position_size
                if position_size > 0
                else (entry_price - exit_price) * abs(position_size)
            )
            self.trade_sections.append(
                {
                    "start": start_idx,
                    "end": end_idx,
                    "profit": profit,
                    "profitable": profit > 0,
                }
            )
            return profit
        return 0

    def getOrders(self, current_data, positions):
        """Get orders based on current market data and positions.

        This method should be implemented by specific strategy classes.

        Args:
            current_data: Dictionary of current market data
            positions: Dictionary of current positions

        Returns:
            Dictionary of orders to execute
        """
        raise NotImplementedError("Subclasses must implement getOrders()")

    def visualize_strategy(self):
        """Visualize the strategy's performance."""
        df = pd.DataFrame(self.historical_data)
        if df.empty:
            print(f"No data to visualize for {self.name}.")
            return

        print(f"Generating visualization for {self.name} with {len(df)} data points...")

        fig = plt.figure(figsize=(14, 7))
        ax1 = fig.add_subplot(111)

        ax1.set_title(f"{self.name} Strategy Visualization")
        ax1.set_xlabel("Timestamp")
        ax1.set_ylabel("Price")

        # Mid Price
        ax1.plot(df["timestamp"], df["mid_price"], label="Mid Price", linewidth=1)

        # Short Rolling Average
        short_mask = ~df["short_avg"].isna()
        if short_mask.any():
            ax1.plot(
                df.loc[short_mask, "timestamp"],
                df.loc[short_mask, "short_avg"],
                label="Short-Term Avg",
                linewidth=1,
            )

        # Long Rolling Average
        long_mask = ~df["long_avg"].isna()
        if long_mask.any():
            ax1.plot(
                df.loc[long_mask, "timestamp"],
                df.loc[long_mask, "long_avg"],
                label="Long-Term Avg",
                linewidth=1,
            )

        # Plot buys/sells with annotations
        buy_trades = [
            t for t in self.trades if t["type"] == "buy" and t["quantity"] > 0
        ]
        sell_trades = [
            t for t in self.trades if t["type"] == "sell" and t["quantity"] < 0
        ]

        if buy_trades:
            bx = [t["timestamp"] for t in buy_trades]
            by = [t["price"] for t in buy_trades]
            ax1.scatter(bx, by, marker="^", s=100, label="Buy", zorder=5)
            for trade in buy_trades:
                ax1.annotate(
                    f"{trade['price']:.2f}",
                    (trade["timestamp"], trade["price"]),
                    xytext=(0, 10),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                )

        if sell_trades:
            sx = [t["timestamp"] for t in sell_trades]
            sy = [t["price"] for t in sell_trades]
            ax1.scatter(sx, sy, marker="v", s=100, label="Sell", zorder=5)
            for trade in sell_trades:
                ax1.annotate(
                    f"{trade['price']:.2f}",
                    (trade["timestamp"], trade["price"]),
                    xytext=(0, -10),
                    textcoords="offset points",
                    ha="center",
                    va="top",
                    fontsize=8,
                )

        # Mark high spread periods
        for period in self.high_spread_periods:
            s, e = period["start"], period["end"]
            if s < len(df) and e < len(df):
                ax1.axvspan(
                    df["timestamp"][s],
                    df["timestamp"][e],
                    color="red",
                    alpha=0.2,
                    label="_HighSpread",
                )

        # Mark waiting periods
        for wperiod in self.waiting_periods:
            s, e = wperiod["start"], wperiod["end"]
            if s < len(df) and e < len(df):
                ax1.axvspan(
                    df["timestamp"][s],
                    df["timestamp"][min(e, len(df) - 1)],
                    color="blue",
                    alpha=0.2,
                    label="_Waiting",
                )

        # Mark trade sections
        for section in self.trade_sections:
            s, e = section["start"], section["end"]
            if s < len(df) and e < len(df):
                color = "lightgreen" if section["profitable"] else "mistyrose"
                ax1.axvspan(
                    df["timestamp"][s],
                    df["timestamp"][e],
                    color=color,
                    alpha=0.2,
                    label="_" + ("Profit" if section["profitable"] else "Loss"),
                )

        # Strategy-specific visualization can be added in subclasses
        self._add_strategy_specific_visualization(ax1, df)

        # Stats
        total_trades = len(self.trades)
        profitable_trades = sum(1 for s in self.trade_sections if s["profitable"])
        total_profit = sum(s["profit"] for s in self.trade_sections)

        # Add strategy-specific stats
        stats_text = (
            f"Strategy: {self.name}\n"
            f"Total Trades: {total_trades}\n"
            f"Profitable Trades: {profitable_trades}/{len(self.trade_sections) if self.trade_sections else 0}\n"
            f"Total Profit: {total_profit:.2f}\n"
        )

        # Add additional stats from subclass
        stats_text += self._get_additional_stats()

        ax1.text(
            0.01,
            0.99,
            stats_text,
            transform=ax1.transAxes,
            fontsize=9,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
        )

        # Slider & Buttons for navigation
        data_length = len(df)
        window_size = min(5000, data_length)
        ax_slider = plt.axes([0.2, 0.02, 0.65, 0.03])
        slider = Slider(
            ax=ax_slider,
            label="Scroll",
            valmin=0,
            valmax=max(1, data_length - window_size),
            valinit=0,
            valstep=max(1, window_size // 10) if window_size > 1 else 1,
        )

        def update_slider(val):
            pos = int(slider.val)
            ax1.set_xlim(
                [
                    df["timestamp"][pos],
                    df["timestamp"][min(pos + window_size, data_length - 1)],
                ]
            )
            fig.canvas.draw_idle()

        slider.on_changed(update_slider)

        ax_prev = plt.axes([0.07, 0.02, 0.1, 0.03])
        ax_next = plt.axes([0.87, 0.02, 0.1, 0.03])
        btn_prev = Button(ax_prev, "Previous")
        btn_next = Button(ax_next, "Next")

        def go_prev(event):
            new_val = max(0, slider.val - window_size // 2)
            slider.set_val(new_val)

        def go_next(event):
            new_val = min(data_length - window_size, slider.val + window_size // 2)
            slider.set_val(new_val)

        btn_prev.on_clicked(go_prev)
        btn_next.on_clicked(go_next)

        ax1.legend(loc="upper left")
        ax1.grid(True, alpha=0.3)
        plt.tight_layout()

        print(f"Displaying visualization for {self.name}...")
        plt.show()

    def _add_strategy_specific_visualization(self, ax, df):
        """Add strategy-specific visualization elements.

        This method should be overridden by subclasses to add
        strategy-specific visualization elements.

        Args:
            ax: Matplotlib axis
            df: DataFrame of historical data
        """
        pass

    def _get_additional_stats(self):
        """Get additional statistics for the strategy.

        This method should be overridden by subclasses to add
        strategy-specific statistics to the visualization.

        Returns:
            String with additional statistics
        """
        return ""
