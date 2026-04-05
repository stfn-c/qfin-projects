import atexit
from UECStrategy import UECStrategy
from SOBERStrategy import SOBERStrategy

# Initialize strategy instances
uec_strategy = UECStrategy(name="UEC Strategy", visualize_on_exit=False)
sober_strategy = SOBERStrategy(name="SOBER Strategy", visualize_on_exit=False)

# Which strategy to use for each product
# This identifies whether a product should use UEC or SOBER strategy
# If product name contains these strings, it will use the corresponding strategy
UEC_IDENTIFIERS = ["UEC"]
SOBER_IDENTIFIERS = ["SOBER"]

# Whether to visualize results
VISUALIZE_ON_EXIT = True


def getOrders(current_data, positions):
    """Main order function called by the backtester.

    This function routes orders to the appropriate strategy based on
    product names. UEC strategy is used by default.

    Args:
        current_data: Dictionary of current market data
        positions: Dictionary of current positions

    Returns:
        Dictionary of orders to execute
    """
    orders = {}

    for product in current_data:
        # Determine which strategy to use based on product name
        use_sober = any(identifier in product for identifier in SOBER_IDENTIFIERS)

        if use_sober:
            # Use SOBER strategy
            product_orders = sober_strategy.getOrders(
                {product: current_data[product]}, {product: positions[product]}
            )
            orders[product] = product_orders[product]
        else:
            # Default to UEC strategy
            product_orders = uec_strategy.getOrders(
                {product: current_data[product]}, {product: positions[product]}
            )
            orders[product] = product_orders[product]

    return orders


# Function to customize strategies from external code if needed
def configure_strategies(uec_params=None, sober_params=None, visualize=None):
    """Configure strategy parameters and visualization settings.

    Args:
        uec_params: Dictionary of UEC strategy parameters
        sober_params: Dictionary of SOBER strategy parameters
        visualize: Boolean to enable/disable visualization
    """
    global uec_strategy, sober_strategy, VISUALIZE_ON_EXIT

    if visualize is not None:
        VISUALIZE_ON_EXIT = visualize

    # Create new UEC strategy with provided parameters
    if uec_params:
        uec_strategy = UECStrategy(
            name="UEC Strategy", visualize_on_exit=VISUALIZE_ON_EXIT, **uec_params
        )
    else:
        # Just update visualization setting
        uec_strategy.visualize_on_exit = VISUALIZE_ON_EXIT

    # Create new SOBER strategy with provided parameters
    if sober_params:
        sober_strategy = SOBERStrategy(
            name="SOBER Strategy", visualize_on_exit=VISUALIZE_ON_EXIT, **sober_params
        )
    else:
        # Just update visualization setting
        sober_strategy.visualize_on_exit = VISUALIZE_ON_EXIT


def exit_handler():
    """Ensure visualization happens at exit if enabled."""
    if VISUALIZE_ON_EXIT:
        if len(uec_strategy.historical_data["timestamp"]) > 0:
            uec_strategy.visualize_strategy()
        if len(sober_strategy.historical_data["timestamp"]) > 0:
            sober_strategy.visualize_strategy()


# Register exit handler
atexit.register(exit_handler)

# Example of how to configure strategies before running the backtest:
# This code won't run when imported, but shows how to use the module
if __name__ == "__main__":
    # Example configuration
    configure_strategies(
        uec_params={
            "short_window": 83,
            "long_window": 500,
            "waiting_period": 78,
            "high_spread_threshold": 1.3,
            "position_size": 100,
            "hs_exit_change_threshold": 0.05,
            "ma_turn_threshold": 0.829,
        },
        sober_params={
            "short_window": 20,
            "long_window": 100,
            "volatility_window": 50,
            "z_score_threshold": 5,
            "position_size": 100,
            "profit_taking_threshold": 0.01,
            "stop_loss_threshold": 0.02,
        },
        visualize=True,
    )

    print("PanicTrader configured with UEC and SOBER strategies")
    print("Run backtester.py to execute the backtest")
