from typing import Dict, List, Tuple
import collections
import atexit
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Constants for product symbols
VP_SYMBOL = "VP"
COMPONENT_SYMBOLS = ["SHEEP", "ORE", "WHEAT"]
SHEEP_SYMBOL = "SHEEP"
ORE_SYMBOL = "ORE"
WHEAT_SYMBOL = "WHEAT"


class TradingAlgorithm:

    def __init__(self):
        self.positions: Dict[str, int] = {}
        # E.g. {"ABC": 2, "XYZ": -5, ...}
        # This will get automatically updated after each call to getOrders()

        # Ratios and intercept for predicting VP
        self.vp_ratios = {"SHEEP": 0.89205968, "ORE": 22.4798756, "WHEAT": 2.88036676}
        self.vp_intercept = 42.15015333713495
        self.etf_symbol = (
            VP_SYMBOL  # VP is the main ETF whose components are SHEEP, ORE, WHEAT
        )
        self.vp_component_symbols = COMPONENT_SYMBOLS

        # Ratios and intercept for predicting SHEEP
        self.sheep_target_symbol = SHEEP_SYMBOL
        self.sheep_pred_ratios = {
            "VP": 0.28230762,
            "ORE": -6.1923182,
            "WHEAT": -0.69850408,
        }
        self.sheep_pred_intercept = 157.94747815590347
        self.sheep_pred_components = [
            VP_SYMBOL,
            ORE_SYMBOL,
            WHEAT_SYMBOL,
        ]  # Components used to predict SHEEP

        # Ratios and intercept for predicting ORE
        self.ore_target_symbol = ORE_SYMBOL
        self.ore_pred_ratios = {
            "SHEEP": -0.03727556,
            "WHEAT": -0.12264661,
            "VP": 0.04282461,
        }
        self.ore_pred_intercept = -0.5394605760168432
        self.ore_pred_components = [
            SHEEP_SYMBOL,
            WHEAT_SYMBOL,
            VP_SYMBOL,
        ]  # Components used to predict ORE

        self.rolling_avg_window = (
            1  # Shared window for simplicity, can be individualized
        )

        # VP trading parameters and history
        self.vp_difference_history = collections.deque(maxlen=self.rolling_avg_window)
        self.vp_positive_diff_ma_threshold = 32.0
        self.vp_negative_diff_ma_threshold = -32.0
        self.vp_fixed_order_quantity = 100

        # SHEEP trading parameters and history
        self.sheep_difference_history = collections.deque(
            maxlen=self.rolling_avg_window
        )
        self.sheep_positive_diff_ma_threshold = 15.0  # Placeholder
        self.sheep_negative_diff_ma_threshold = -15.0  # Placeholder
        self.sheep_fixed_order_quantity = 100  # Placeholder

        # ORE trading parameters and history
        self.ore_difference_history = collections.deque(maxlen=self.rolling_avg_window)
        self.ore_positive_diff_ma_threshold = 5.0  # Placeholder
        self.ore_negative_diff_ma_threshold = -5.0  # Placeholder
        self.ore_fixed_order_quantity = 100  # Placeholder

        # Data for plotting
        self.timestamps_history: List[int] = []
        self.price_history: Dict[str, List[float]] = {
            sym: [] for sym in [VP_SYMBOL, SHEEP_SYMBOL, ORE_SYMBOL, WHEAT_SYMBOL]
        }

        self.vp_expected_price_history: List[float] = []
        self.sheep_expected_price_history: List[float] = []
        self.ore_expected_price_history: List[float] = []

        self.vp_diff_ma_history: List[float] = []
        self.sheep_diff_ma_history: List[float] = []
        self.ore_diff_ma_history: List[float] = []

        # (timestamp, product_traded, "BUY"/"SELL", price, quantity, diff_ma_at_signal)
        self.trade_signals: List[Tuple[int, str, str, float, int, float]] = []

        self.position_history: Dict[str, List[int]] = {
            VP_SYMBOL: [],
            SHEEP_SYMBOL: [],
            ORE_SYMBOL: [],
        }

        atexit.register(self.generate_plot_on_exit)

    def _get_mid_price(
        self, product: str, current_data: Dict[str, Dict[str, float]]
    ) -> float | None:
        if product not in current_data:
            return None

        product_info = current_data[product]
        bid = product_info.get("Bid")
        ask = product_info.get("Ask")

        if (
            bid is not None and ask is not None and bid > 0 and ask > 0
        ):  # ensure prices are valid
            return (bid + ask) / 2.0
        return None

    # This method will be called every timestamp with information about the new best bid and best ask for each product
    def getOrders(
        self, current_data: Dict[str, Dict[str, float]], order_data: Dict[str, int]
    ) -> Dict[str, int]:
        current_timestamp = -1
        if VP_SYMBOL in current_data and "Timestamp" in current_data[VP_SYMBOL]:
            current_timestamp = int(current_data[VP_SYMBOL]["Timestamp"])

        # Fetch all potentially needed mid-prices
        vp_price = self._get_mid_price(VP_SYMBOL, current_data)
        sheep_price = self._get_mid_price(SHEEP_SYMBOL, current_data)
        ore_price = self._get_mid_price(ORE_SYMBOL, current_data)
        wheat_price = self._get_mid_price(WHEAT_SYMBOL, current_data)

        # ----- Universal Data Logging (if timestamp is valid) -----
        if current_timestamp != -1:
            self.timestamps_history.append(current_timestamp)
            if vp_price is not None:
                self.price_history[VP_SYMBOL].append(vp_price)
            else:
                self.price_history[VP_SYMBOL].append(
                    float("nan")
                )  # Log NaN if price missing

            if sheep_price is not None:
                self.price_history[SHEEP_SYMBOL].append(sheep_price)
            else:
                self.price_history[SHEEP_SYMBOL].append(float("nan"))

            if ore_price is not None:
                self.price_history[ORE_SYMBOL].append(ore_price)
            else:
                self.price_history[ORE_SYMBOL].append(float("nan"))

            if wheat_price is not None:
                self.price_history[WHEAT_SYMBOL].append(wheat_price)
            else:
                self.price_history[WHEAT_SYMBOL].append(float("nan"))

            self.position_history[VP_SYMBOL].append(self.positions.get(VP_SYMBOL, 0))
            self.position_history[SHEEP_SYMBOL].append(
                self.positions.get(SHEEP_SYMBOL, 0)
            )
            self.position_history[ORE_SYMBOL].append(self.positions.get(ORE_SYMBOL, 0))

        # ----- VP Trading Logic -----
        if (
            vp_price is not None
            and sheep_price is not None
            and ore_price is not None
            and wheat_price is not None
        ):
            expected_vp_price = self.vp_intercept
            expected_vp_price += self.vp_ratios[SHEEP_SYMBOL] * sheep_price
            expected_vp_price += self.vp_ratios[ORE_SYMBOL] * ore_price
            expected_vp_price += self.vp_ratios[WHEAT_SYMBOL] * wheat_price

            raw_vp_difference = vp_price - expected_vp_price
            self.vp_difference_history.append(raw_vp_difference)

            if current_timestamp != -1:
                self.vp_expected_price_history.append(expected_vp_price)
                self.vp_diff_ma_history.append(raw_vp_difference)

            current_vp_signal_value = raw_vp_difference

            orders_to_place_vp = 0
            if current_vp_signal_value > self.vp_positive_diff_ma_threshold:
                orders_to_place_vp = -self.vp_fixed_order_quantity
                if current_timestamp != -1:
                    self.trade_signals.append(
                        (
                            current_timestamp,
                            VP_SYMBOL,
                            "SELL",
                            vp_price,
                            orders_to_place_vp,
                            current_vp_signal_value,
                        )
                    )
            elif current_vp_signal_value < self.vp_negative_diff_ma_threshold:
                orders_to_place_vp = self.vp_fixed_order_quantity
                if current_timestamp != -1:
                    self.trade_signals.append(
                        (
                            current_timestamp,
                            VP_SYMBOL,
                            "BUY",
                            vp_price,
                            orders_to_place_vp,
                            current_vp_signal_value,
                        )
                    )

            if orders_to_place_vp != 0:
                order_data[VP_SYMBOL] = (
                    order_data.get(VP_SYMBOL, 0) + orders_to_place_vp
                )
        else:  # Not enough data for VP calculation
            if current_timestamp != -1:
                self.vp_expected_price_history.append(float("nan"))
                self.vp_diff_ma_history.append(float("nan"))

        # ----- SHEEP Trading Logic -----
        if (
            sheep_price is not None
            and vp_price is not None
            and ore_price is not None
            and wheat_price is not None
        ):
            implied_sheep_price = self.sheep_pred_intercept
            implied_sheep_price += self.sheep_pred_ratios[VP_SYMBOL] * vp_price
            implied_sheep_price += self.sheep_pred_ratios[ORE_SYMBOL] * ore_price
            implied_sheep_price += self.sheep_pred_ratios[WHEAT_SYMBOL] * wheat_price

            raw_sheep_difference = sheep_price - implied_sheep_price
            self.sheep_difference_history.append(raw_sheep_difference)

            if current_timestamp != -1:
                self.sheep_expected_price_history.append(implied_sheep_price)
                self.sheep_diff_ma_history.append(raw_sheep_difference)

            current_sheep_signal_value = raw_sheep_difference

            orders_to_place_sheep = 0
            if current_sheep_signal_value > self.sheep_positive_diff_ma_threshold:
                orders_to_place_sheep = -self.sheep_fixed_order_quantity
                if current_timestamp != -1:
                    self.trade_signals.append(
                        (
                            current_timestamp,
                            SHEEP_SYMBOL,
                            "SELL",
                            sheep_price,
                            orders_to_place_sheep,
                            current_sheep_signal_value,
                        )
                    )
            elif current_sheep_signal_value < self.sheep_negative_diff_ma_threshold:
                orders_to_place_sheep = self.sheep_fixed_order_quantity
                if current_timestamp != -1:
                    self.trade_signals.append(
                        (
                            current_timestamp,
                            SHEEP_SYMBOL,
                            "BUY",
                            sheep_price,
                            orders_to_place_sheep,
                            current_sheep_signal_value,
                        )
                    )

            if orders_to_place_sheep != 0:
                order_data[SHEEP_SYMBOL] = (
                    order_data.get(SHEEP_SYMBOL, 0) + orders_to_place_sheep
                )
        else:  # Not enough data for SHEEP calculation
            if current_timestamp != -1:
                self.sheep_expected_price_history.append(float("nan"))
                self.sheep_diff_ma_history.append(float("nan"))

        # ----- ORE Trading Logic -----
        if (
            ore_price is not None
            and vp_price is not None
            and sheep_price is not None
            and wheat_price is not None
        ):
            implied_ore_price = self.ore_pred_intercept
            implied_ore_price += self.ore_pred_ratios[VP_SYMBOL] * vp_price
            implied_ore_price += self.ore_pred_ratios[SHEEP_SYMBOL] * sheep_price
            implied_ore_price += self.ore_pred_ratios[WHEAT_SYMBOL] * wheat_price

            raw_ore_difference = ore_price - implied_ore_price
            self.ore_difference_history.append(raw_ore_difference)

            if current_timestamp != -1:
                self.ore_expected_price_history.append(implied_ore_price)
                self.ore_diff_ma_history.append(raw_ore_difference)

            current_ore_signal_value = raw_ore_difference

            orders_to_place_ore = 0
            if current_ore_signal_value > self.ore_positive_diff_ma_threshold:
                orders_to_place_ore = -self.ore_fixed_order_quantity
                if current_timestamp != -1:
                    self.trade_signals.append(
                        (
                            current_timestamp,
                            ORE_SYMBOL,
                            "SELL",
                            ore_price,
                            orders_to_place_ore,
                            current_ore_signal_value,
                        )
                    )
            elif current_ore_signal_value < self.ore_negative_diff_ma_threshold:
                orders_to_place_ore = self.ore_fixed_order_quantity
                if current_timestamp != -1:
                    self.trade_signals.append(
                        (
                            current_timestamp,
                            ORE_SYMBOL,
                            "BUY",
                            ore_price,
                            orders_to_place_ore,
                            current_ore_signal_value,
                        )
                    )

            if orders_to_place_ore != 0:
                order_data[ORE_SYMBOL] = (
                    order_data.get(ORE_SYMBOL, 0) + orders_to_place_ore
                )
        else:  # Not enough data for ORE calculation
            if current_timestamp != -1:
                self.ore_expected_price_history.append(float("nan"))
                self.ore_diff_ma_history.append(float("nan"))

        return order_data

    def generate_plot_on_exit(self):
        if not self.timestamps_history:
            print("No data collected during the trading session to generate a plot.")
            return

        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            specs=[
                [{"secondary_y": False}],  # Row 1: Prices
                [{"secondary_y": False}],  # Row 2: Differences
                [{"secondary_y": False}],
            ],  # Row 3: Position
            vertical_spacing=0.03,
            row_heights=[0.5, 0.25, 0.25],  # Adjusted row heights
        )

        # Ensure timestamps are available for all main traces
        if not self.timestamps_history:
            print("Timestamps history is empty. Cannot generate plot.")
            return

        # Plot VP Actual Price
        if self.price_history.get(self.etf_symbol) and len(
            self.price_history[self.etf_symbol]
        ) == len(self.timestamps_history):
            fig.add_trace(
                go.Scatter(
                    x=self.timestamps_history,
                    y=self.price_history[self.etf_symbol],
                    mode="lines",
                    name=f"{self.etf_symbol} Actual Price",
                ),
                row=1,
                col=1,
            )
        else:
            print(
                f"Warning: VP actual price data missing or length mismatch. TS: {len(self.timestamps_history)}, VP: {len(self.price_history.get(self.etf_symbol, []))}"
            )

        # Plot VP Expected Price
        if self.vp_expected_price_history and len(
            self.vp_expected_price_history
        ) == len(self.timestamps_history):
            fig.add_trace(
                go.Scatter(
                    x=self.timestamps_history,
                    y=self.vp_expected_price_history,
                    mode="lines",
                    name=f"{self.etf_symbol} Expected Price",
                    line=dict(dash="dot"),
                ),
                row=1,
                col=1,
            )
        else:
            print(
                f"Warning: VP expected price data missing or length mismatch. TS: {len(self.timestamps_history)}, Expected: {len(self.vp_expected_price_history)}"
            )

        # Plot Component Prices (initially hidden)
        for sym in self.vp_component_symbols:
            if self.price_history.get(sym) and len(self.price_history[sym]) == len(
                self.timestamps_history
            ):
                fig.add_trace(
                    go.Scatter(
                        x=self.timestamps_history,
                        y=self.price_history[sym],
                        mode="lines",
                        name=f"{sym} Price",
                        visible="legendonly",
                    ),
                    row=1,
                    col=1,
                )
            # else:
            # print(f"Warning: Data for component {sym} missing or length mismatch.")

        # --- Row 2: Difference Plots ---
        # Plot Difference MA (on primary y-axis of the second subplot)
        if self.vp_diff_ma_history and len(self.vp_diff_ma_history) == len(
            self.timestamps_history
        ):
            fig.add_trace(
                go.Scatter(
                    x=self.timestamps_history,
                    y=self.vp_diff_ma_history,
                    mode="lines",
                    name="Difference MA (VP - Expected VP)",
                    line=dict(color="orange"),  # Distinct color for diff_ma
                ),
                row=2,
                col=1,
            )

        # --- Row 3: Position Plot ---
        if self.position_history[self.etf_symbol] and len(
            self.position_history[self.etf_symbol]
        ) == len(self.timestamps_history):
            fig.add_trace(
                go.Scatter(
                    x=self.timestamps_history,
                    y=self.position_history[self.etf_symbol],
                    mode="lines",
                    name="VP Position",
                    line=dict(shape="hv"),  # Step line for position
                ),
                row=3,
                col=1,  # Moved to row 3
            )
        else:
            if self.timestamps_history:
                print(
                    f"Warning: VP position data missing or length mismatch for plotting. TS: {len(self.timestamps_history)}, Pos: {len(self.position_history[self.etf_symbol])}"
                )

        buy_signals_price_ts = []
        buy_signals_price_y = []
        buy_signals_price_text = []
        sell_signals_price_ts = []
        sell_signals_price_y = []
        sell_signals_price_text = []

        # For difference plot signals
        buy_signals_diff_ts = []
        buy_signals_diff_y = []  # This will be diff_ma_at_signal
        buy_signals_diff_text = []
        sell_signals_diff_ts = []
        sell_signals_diff_y = []  # This will be diff_ma_at_signal
        sell_signals_diff_text = []

        for (
            ts,
            signal_type,
            product,
            price,
            quantity,
            diff_ma_val,
        ) in self.trade_signals:
            text_content = f"Type: {signal_type}<br>Qty: {quantity}<br>Price: {price:.2f}<br>DiffMA: {diff_ma_val:.2f}<br>TS: {ts}"
            if "BUY" in signal_type.upper():
                buy_signals_price_ts.append(ts)
                buy_signals_price_y.append(price)
                buy_signals_price_text.append(text_content)

                buy_signals_diff_ts.append(ts)
                buy_signals_diff_y.append(diff_ma_val)
                buy_signals_diff_text.append(text_content)

            elif "SELL" in signal_type.upper():
                sell_signals_price_ts.append(ts)
                sell_signals_price_y.append(price)
                sell_signals_price_text.append(text_content)

                sell_signals_diff_ts.append(ts)
                sell_signals_diff_y.append(diff_ma_val)
                sell_signals_diff_text.append(text_content)

        # Signals on Price Chart (Row 1)
        if buy_signals_price_ts:
            fig.add_trace(
                go.Scatter(
                    x=buy_signals_price_ts,
                    y=buy_signals_price_y,
                    mode="markers",
                    name="Buy/Cover Signals (Price)",
                    marker=dict(color="green", size=10, symbol="triangle-up"),
                    text=buy_signals_price_text,
                    hovertemplate="%{text}<extra></extra>",
                ),
                row=1,
                col=1,
            )
        if sell_signals_price_ts:
            fig.add_trace(
                go.Scatter(
                    x=sell_signals_price_ts,
                    y=sell_signals_price_y,
                    mode="markers",
                    name="Sell/Short Signals (Price)",
                    marker=dict(color="red", size=10, symbol="triangle-down"),
                    text=sell_signals_price_text,
                    hovertemplate="%{text}<extra></extra>",
                ),
                row=1,
                col=1,
            )

        # Signals on Difference Chart (Row 2)
        if buy_signals_diff_ts:
            fig.add_trace(
                go.Scatter(
                    x=buy_signals_diff_ts,
                    y=buy_signals_diff_y,
                    mode="markers",
                    name="Buy/Cover Signals (DiffMA)",
                    marker=dict(color="darkgreen", size=8, symbol="triangle-up-dot"),
                    text=buy_signals_diff_text,
                    hovertemplate="%{text}<extra></extra>",
                ),
                row=2,
                col=1,
            )
        if sell_signals_diff_ts:
            fig.add_trace(
                go.Scatter(
                    x=sell_signals_diff_ts,
                    y=sell_signals_diff_y,
                    mode="markers",
                    name="Sell/Short Signals (DiffMA)",
                    marker=dict(color="darkred", size=8, symbol="triangle-down-dot"),
                    text=sell_signals_diff_text,
                    hovertemplate="%{text}<extra></extra>",
                ),
                row=2,
                col=1,
            )

        fig.update_layout(
            title_text="Trading Strategy Performance: VP, Differences, and Position",
            legend_title_text="Trace",
            hovermode="x unified",
            autosize=True,
            height=900,  # Adjusted height for three subplots
        )

        fig.update_xaxes(
            title_text="Timestamp", row=3, col=1
        )  # Shared X-axis title on the bottom subplot

        fig.update_yaxes(title_text="Price (VP & Components)", row=1, col=1)
        fig.update_yaxes(title_text="Difference / Diff MA", row=2, col=1)
        fig.update_yaxes(title_text="VP Position", row=3, col=1)

        file_path = "trading_performance_plot.html"
        try:
            fig.write_html(file_path, auto_open=True)
            print(
                f"Interactive plot saved to {file_path} and (attempted to) open in browser."
            )
        except Exception as e:
            print(f"Error generating or opening plot: {e}")
            print(
                f"Plot data might still be available in {file_path} if write_html succeeded partially."
            )


team_algorithm = TradingAlgorithm()


def getOrders(current_data, positions):
    team_algorithm.positions = positions
    order_data = {product: 0 for product in current_data}
    return team_algorithm.getOrders(current_data, order_data)
