from BaseStrategy import BaseStrategy
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec


class SOBERStrategy(BaseStrategy):
    """SOBER Trading Strategy.

    A simplified volatility-based strategy that:
    1. Maintains a short position of -100 by default.
    2. Only enters a long position (buys 200) when:
       - Volatility is above a threshold (and we've seen it below before)
       - The short rolling average of price hits a minimum (was declining, now increasing)
       - We are not already in a volatility position
       - We are not waiting for volatility to drop below threshold (cool-down)
    3. Exits the long position (sells 200, returning to -100) when:
       - The volatility rolling average hits a maximum (was increasing, now decreasing)
       - Or price drops below a certain threshold
    4. After any exit, we wait for volatility to drop back below threshold
       before initiating a new high-volatility trade.
    """

    def __init__(
        self,
        name="Simplified SOBER Strategy",
        visualize_on_exit=True,
        short_window=5,
        volatility_window=50,
        volatility_threshold=0.002,
        vol_ma_window=5,
        position_size=100,
        price_threshold=95,
    ):
        """Initialize the SOBER strategy.

        Args:
            name: Strategy name
            visualize_on_exit: Whether to visualize on exit
            short_window: Window size for short-term (price) moving average
            volatility_window:  Window size for volatility calculation
            volatility_threshold: Threshold for high volatility detection
            vol_ma_window: Window size for volatility moving average
            position_size: Size of positions to take
            price_threshold: Price below which to stop (force exit)
        """
        super().__init__(name, visualize_on_exit)

        # Strategy parameters
        self.SHORT_WINDOW = short_window
        self.VOLATILITY_WINDOW = volatility_window
        self.VOLATILITY_THRESHOLD = volatility_threshold
        self.VOL_MA_WINDOW = vol_ma_window
        self.POSITION_SIZE = position_size
        self.PRICE_THRESHOLD = price_threshold

        # Strategy state variables
        self.initialized_initial_short = False
        self.in_volatility_position = False
        self.below_price_threshold = False
        self.last_price = None

        # For tracking short_avg turning points
        self.last_short_avg = None
        self.short_avg_was_decreasing = False
        self.short_avg_now_increasing = False

        # For tracking vol_ma turning points
        self.last_vol_ma = None
        self.vol_ma_was_increasing = False
        self.vol_ma_now_decreasing = False

        # Volatility cycle tracking
        self.waiting_for_volatility_below_threshold = False
        self.volatility_below_threshold = True  # Start true for the first trade

    def initialize_data(self):
        """Reset all data structures and state variables."""
        super().initialize_data()

        self.initialized_initial_short = False
        self.in_volatility_position = False
        self.below_price_threshold = False
        self.last_price = None

        # Reset short avg tracking
        self.last_short_avg = None
        self.short_avg_was_decreasing = False
        self.short_avg_now_increasing = False

        # Reset vol_ma tracking
        self.last_vol_ma = None
        self.vol_ma_was_increasing = False
        self.vol_ma_now_decreasing = False

        # Volatility cycle
        self.waiting_for_volatility_below_threshold = False
        self.volatility_below_threshold = True

    def getOrders(self, current_data, positions):
        """Implement the SOBER trading strategy.

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

            # Check if price is below threshold
            if mid_price < self.PRICE_THRESHOLD:
                self.below_price_threshold = True

            current_position = positions[product]
            order_quantity = 0
            trade_profit = 0

            # Step 1: Initialize with a short position of -100 if not done yet
            if not self.initialized_initial_short:
                order_quantity = -self.POSITION_SIZE  # short 100
                self.record_trade(timestamp, bid, order_quantity, "sell")
                self.initialized_initial_short = True

            # ---------------------------
            # 1) Compute short rolling average (price)
            # ---------------------------
            short_avg = None
            if len(self.historical_data["mid_price"]) >= self.SHORT_WINDOW:
                recent_prices = self.historical_data["mid_price"][-self.SHORT_WINDOW :]
                short_avg = np.mean(recent_prices)

                # Determine if short_avg has turned from decreasing to increasing
                if self.last_short_avg is not None:
                    short_avg_decreasing = short_avg < self.last_short_avg
                    short_avg_increasing = short_avg > self.last_short_avg

                    # If we were decreasing but now are increasing => short_avg bottomed out
                    if self.short_avg_was_decreasing and short_avg_increasing:
                        self.short_avg_now_increasing = True
                    else:
                        self.short_avg_now_increasing = False

                    # Update for the next iteration
                    self.short_avg_was_decreasing = short_avg_decreasing

                self.last_short_avg = short_avg

            # ---------------------------
            # 2) Compute volatility
            # ---------------------------
            volatility = None
            if len(self.historical_data["mid_price"]) >= self.VOLATILITY_WINDOW + 1:
                prices = self.historical_data["mid_price"][
                    -(self.VOLATILITY_WINDOW + 1) :
                ]
                returns = [
                    prices[i + 1] / prices[i] - 1 for i in range(len(prices) - 1)
                ]
                volatility = np.std(returns)

                # Track if volatility crosses threshold
                if volatility is not None:
                    # If we're waiting for volatility to drop below threshold (cool-down):
                    if self.waiting_for_volatility_below_threshold:
                        if volatility <= self.VOLATILITY_THRESHOLD:
                            # Vol dropped below threshold => next trade is allowed
                            self.waiting_for_volatility_below_threshold = False
                            self.volatility_below_threshold = True
                    else:
                        # Normal tracking
                        if volatility <= self.VOLATILITY_THRESHOLD:
                            self.volatility_below_threshold = True
                        elif (
                            volatility > self.VOLATILITY_THRESHOLD
                            and not self.in_volatility_position
                            and self.volatility_below_threshold
                        ):
                            # Vol just crossed above threshold => potential new trade
                            self.volatility_below_threshold = False

            # ---------------------------
            # 3) Compute volatility rolling average
            # ---------------------------
            vol_ma = None
            if (
                "volatility" in self.historical_data
                and len(self.historical_data["volatility"]) >= self.VOL_MA_WINDOW
            ):
                # Filter out None
                recent_vols = [
                    v
                    for v in self.historical_data["volatility"][-self.VOL_MA_WINDOW :]
                    if v is not None
                ]
                if len(recent_vols) >= self.VOL_MA_WINDOW:
                    vol_ma = np.mean(recent_vols)

                    # Determine if vol_ma has turned from increasing to decreasing (max)
                    if self.last_vol_ma is not None:
                        vol_ma_increasing = vol_ma > self.last_vol_ma
                        vol_ma_decreasing = vol_ma < self.last_vol_ma

                        # If we were increasing but now are decreasing => vol_ma topped out
                        if self.vol_ma_was_increasing and vol_ma_decreasing:
                            self.vol_ma_now_decreasing = True
                        else:
                            self.vol_ma_now_decreasing = False

                        self.vol_ma_was_increasing = vol_ma_increasing

                    self.last_vol_ma = vol_ma

            # -------------------------------------------------
            # EXIT if price fell below threshold and we are in a volatility position
            # -------------------------------------------------
            if self.below_price_threshold and self.in_volatility_position:
                if current_position == self.POSITION_SIZE:
                    # Sell 200 → go back to -100
                    order_quantity = -2 * self.POSITION_SIZE
                    self.record_trade(timestamp, bid, order_quantity, "sell")

                    # Compute profit
                    exit_index = len(self.historical_data["timestamp"])
                    entry_index = None
                    for i in range(len(self.historical_data["position"]) - 1, -1, -1):
                        if self.historical_data["position"][i] == -self.POSITION_SIZE:
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

                    self.in_volatility_position = False
                    # Must wait for volatility to drop below threshold again
                    self.waiting_for_volatility_below_threshold = True
                    self.volatility_below_threshold = False

            # -------------------------------------------------
            # TRADING LOGIC if price is above threshold
            # -------------------------------------------------
            elif not self.below_price_threshold:
                # 3a) ENTRY: if not in volatility position
                #    Condition:
                #       - volatility > threshold
                #       - short_avg just turned from down to up
                #       - not waiting for vol below
                #       - we have already crossed vol threshold once
                if not self.in_volatility_position:
                    if (
                        volatility is not None
                        and volatility > self.VOLATILITY_THRESHOLD
                        and self.short_avg_now_increasing  # short avg hit a min
                        and current_position == -self.POSITION_SIZE
                        and not self.volatility_below_threshold  # means it just crossed above threshold
                        and not self.waiting_for_volatility_below_threshold
                    ):
                        # Buy 200 => go from -100 to +100
                        order_quantity = 2 * self.POSITION_SIZE
                        self.record_trade(timestamp, ask, order_quantity, "buy")
                        self.in_volatility_position = True

                # 3b) EXIT: if in volatility position
                else:
                    # Condition: volatility MA just turned from up to down => vol_ma top
                    # OR user can still exit if price threshold is triggered above,
                    #   but that's handled in the block above
                    if vol_ma is not None and self.vol_ma_now_decreasing:
                        if current_position == self.POSITION_SIZE:
                            # Sell 200 => go to -100
                            order_quantity = -2 * self.POSITION_SIZE
                            self.record_trade(timestamp, bid, order_quantity, "sell")

                            # Compute trade profit
                            exit_index = len(self.historical_data["timestamp"])
                            entry_index = None
                            for i in range(
                                len(self.historical_data["position"]) - 1, -1, -1
                            ):
                                if (
                                    self.historical_data["position"][i]
                                    == -self.POSITION_SIZE
                                ):
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

                            self.in_volatility_position = False
                            # Must wait for volatility below threshold again
                            self.waiting_for_volatility_below_threshold = True
                            self.volatility_below_threshold = False

            # -------------------------------------------
            # Ensure we remain at -100 if not in position
            # -------------------------------------------
            if (
                not self.in_volatility_position
                and current_position + order_quantity != -self.POSITION_SIZE
            ):
                adjustment = -self.POSITION_SIZE - (current_position + order_quantity)
                if adjustment < 0:
                    self.record_trade(timestamp, bid, adjustment, "sell")
                elif adjustment > 0:
                    self.record_trade(timestamp, ask, adjustment, "buy")
                order_quantity += adjustment

            # -------------------------------------------
            # Update historical data
            # -------------------------------------------
            new_position = current_position + order_quantity
            self.update_historical_data(
                timestamp,
                product_info,
                short_avg,
                None,  # No long average needed
                new_position,
                False,  # Not using high_spread logic
                trade_profit,
            )

            orders[product] = order_quantity

        return orders

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
        """Update historical data with current tick info and calculate volatility & volatility MA."""
        bid = product_data["Bid"]
        ask = product_data["Ask"]
        mid_price = (bid + ask) / 2

        # Calculate volatility for storage
        volatility = None
        if len(self.historical_data["mid_price"]) >= self.VOLATILITY_WINDOW:
            prices = self.historical_data["mid_price"][-self.VOLATILITY_WINDOW :] + [
                mid_price
            ]
            returns = [prices[i + 1] / prices[i] - 1 for i in range(len(prices) - 1)]
            volatility = np.std(returns)

        # Store standard data first
        super().update_historical_data(
            timestamp,
            product_data,
            short_avg,
            long_avg,
            position,
            in_high_spread,
            trade_profit,
        )

        # Also store volatility in historical data
        if "volatility" not in self.historical_data:
            self.historical_data["volatility"] = []
            self.historical_data["vol_ma"] = []

        # For debug/tracking of waiting states
        if "waiting_for_vol_below" not in self.historical_data:
            self.historical_data["waiting_for_vol_below"] = []

        self.historical_data["volatility"].append(volatility)
        self.historical_data["waiting_for_vol_below"].append(
            self.waiting_for_volatility_below_threshold
        )

        # Calculate volatility MA
        vol_ma = None
        if len(self.historical_data["volatility"]) >= self.VOL_MA_WINDOW:
            vol_vals = [
                v
                for v in self.historical_data["volatility"][-self.VOL_MA_WINDOW :]
                if v is not None
            ]
            if len(vol_vals) >= self.VOL_MA_WINDOW:
                vol_ma = np.mean(vol_vals)

        self.historical_data["vol_ma"].append(vol_ma)

    def _add_strategy_specific_visualization(self, ax, df):
        """Add SOBER strategy-specific visualization elements."""
        # Clear figure and rebuild with GridSpec
        fig = ax.figure
        fig.clear()

        gs = GridSpec(2, 1, height_ratios=[2, 1], hspace=0.15)
        ax1 = fig.add_subplot(gs[0])
        ax2 = fig.add_subplot(gs[1], sharex=ax1)

        ax1.set_title(f"{self.name} Strategy Visualization")
        ax1.set_ylabel("Price")
        ax2.set_xlabel("Timestamp")
        ax2.set_ylabel("Volatility")

        # -------------------------
        # Top chart: Price & short_avg
        # -------------------------
        ax1.plot(df["timestamp"], df["mid_price"], label="Mid Price", linewidth=1)

        short_mask = ~df["short_avg"].isna()
        if short_mask.any():
            ax1.plot(
                df.loc[short_mask, "timestamp"],
                df.loc[short_mask, "short_avg"],
                label="Short-Term Avg",
                linewidth=1,
            )

        # Plot trades (buys/sells)
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

        # Add strategy stats on top chart
        total_trades = len(self.trades)
        profitable_trades = sum(1 for s in self.trade_sections if s["profitable"])
        total_profit = sum(s["profit"] for s in self.trade_sections)

        stats_text = (
            f"Strategy: {self.name}\n"
            f"Total Trades: {total_trades}\n"
            f"Profitable Trades: {profitable_trades}/"
            f"{len(self.trade_sections) if self.trade_sections else 0}\n"
            f"Total Profit: {total_profit:.2f}\n"
        )
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

        # Price threshold line
        ax1.axhline(
            y=self.PRICE_THRESHOLD,
            linestyle="--",
            alpha=0.7,
            label=f"Price Threshold ({self.PRICE_THRESHOLD})",
        )

        # Mark first crossing below threshold
        threshold_crossed_index = None
        for i in range(1, len(df)):
            if (
                threshold_crossed_index is None
                and df["mid_price"][i] < self.PRICE_THRESHOLD
            ):
                threshold_crossed_index = i
                break
        if threshold_crossed_index is not None:
            ax1.axvline(
                x=df["timestamp"][threshold_crossed_index],
                linestyle="-.",
                alpha=0.5,
                label="Threshold Crossed",
            )

        ax1.legend(loc="upper left")
        ax1.grid(True, alpha=0.3)

        # -------------------------
        # Bottom chart: Volatility & vol_ma
        # -------------------------
        if "volatility" in df.columns:
            vol_mask = ~df["volatility"].isna()
            vol_ma_mask = ~df["vol_ma"].isna() if "vol_ma" in df.columns else None

            if vol_mask.any():
                ax2.plot(
                    df.loc[vol_mask, "timestamp"],
                    df.loc[vol_mask, "volatility"],
                    alpha=0.7,
                    linestyle="-",
                    label="Volatility",
                )
                ax2.axhline(
                    y=self.VOLATILITY_THRESHOLD,
                    linestyle="--",
                    alpha=0.5,
                    label=f"Vol Threshold ({self.VOLATILITY_THRESHOLD:.4f})",
                )

            if vol_ma_mask is not None and vol_ma_mask.any():
                ax2.plot(
                    df.loc[vol_ma_mask, "timestamp"],
                    df.loc[vol_ma_mask, "vol_ma"],
                    alpha=0.7,
                    linestyle="-",
                    label=f"Vol MA ({self.VOL_MA_WINDOW})",
                )

            # Mark entry/exit points on vol chart
            entry_points = []
            exit_points = []
            for i in range(1, len(df)):
                # Entry: position from -100 -> +100
                if (
                    df["position"][i] == self.POSITION_SIZE
                    and df["position"][i - 1] == -self.POSITION_SIZE
                ):
                    entry_points.append(i)
                # Exit: position from +100 -> -100
                if (
                    df["position"][i] == -self.POSITION_SIZE
                    and df["position"][i - 1] == self.POSITION_SIZE
                ):
                    exit_points.append(i)

            if entry_points and vol_mask.any():
                entry_x = [df["timestamp"][i] for i in entry_points if vol_mask[i]]
                entry_y = [df["volatility"][i] for i in entry_points if vol_mask[i]]
                ax2.scatter(
                    entry_x, entry_y, marker="^", s=100, label="Vol Entry", zorder=7
                )

            if exit_points and vol_mask.any():
                exit_x = [df["timestamp"][i] for i in exit_points if vol_mask[i]]
                exit_y = [df["volatility"][i] for i in exit_points if vol_mask[i]]
                ax2.scatter(
                    exit_x, exit_y, marker="v", s=100, label="Vol Exit", zorder=7
                )

            # Highlight waiting_for_vol_below
            if "waiting_for_vol_below" in df.columns:
                waiting_periods = []
                in_waiting = False
                start_idx = None
                for i in range(len(df)):
                    if not in_waiting and df["waiting_for_vol_below"].iloc[i]:
                        in_waiting = True
                        start_idx = i
                    elif in_waiting and not df["waiting_for_vol_below"].iloc[i]:
                        in_waiting = False
                        waiting_periods.append((start_idx, i))

                if in_waiting:
                    waiting_periods.append((start_idx, len(df) - 1))

                for start, end in waiting_periods:
                    if start < len(df) and end < len(df):
                        ax2.axvspan(
                            df["timestamp"].iloc[start],
                            df["timestamp"].iloc[end],
                            alpha=0.2,
                            label=(
                                "Waiting for Vol < Threshold"
                                if waiting_periods.index((start, end)) == 0
                                else ""
                            ),
                        )

            ax2.legend(loc="upper right")
            ax2.grid(True, alpha=0.3)

        # -------------------------
        # Slider & Navigation
        # -------------------------
        data_length = len(df)
        window_size = min(5000, data_length)
        ax_slider = plt.axes([0.2, 0.02, 0.65, 0.03])
        from matplotlib.widgets import Slider, Button

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

        plt.tight_layout()
        return ax1

    def _get_additional_stats(self):
        """Get SOBER strategy-specific statistics."""
        entry_count = 0
        exit_count = 0
        threshold_crossed = False
        waiting_periods = 0

        if len(self.historical_data["timestamp"]) > 0:
            import pandas as pd

            df = pd.DataFrame(self.historical_data)

            # Check if price threshold was crossed
            if any(df["mid_price"] < self.PRICE_THRESHOLD):
                threshold_crossed = True

            # Count waiting periods (transition from False to True)
            if "waiting_for_vol_below" in df:
                for i in range(1, len(df)):
                    if (
                        not df["waiting_for_vol_below"].iloc[i - 1]
                        and df["waiting_for_vol_below"].iloc[i]
                    ):
                        waiting_periods += 1

            # Count entries/exits
            for i in range(1, len(df)):
                if (
                    df["position"][i] == self.POSITION_SIZE
                    and df["position"][i - 1] == -self.POSITION_SIZE
                ):
                    entry_count += 1
                if (
                    df["position"][i] == -self.POSITION_SIZE
                    and df["position"][i - 1] == self.POSITION_SIZE
                ):
                    exit_count += 1

        return (
            f"SHORT_WINDOW: {self.SHORT_WINDOW}\n"
            f"VOLATILITY_WINDOW: {self.VOLATILITY_WINDOW}\n"
            f"VOLATILITY_THRESHOLD: {self.VOLATILITY_THRESHOLD:.4f}\n"
            f"VOL_MA_WINDOW: {self.VOL_MA_WINDOW}\n"
            f"POSITION_SIZE: {self.POSITION_SIZE}\n"
            f"PRICE_THRESHOLD: {self.PRICE_THRESHOLD}\n"
            f"Price Threshold Crossed: {'Yes' if threshold_crossed else 'No'}\n"
            f"Volatility Entries: {entry_count}\n"
            f"Volatility Exits: {exit_count}\n"
            f"Waiting Periods: {waiting_periods}\n"
        )
