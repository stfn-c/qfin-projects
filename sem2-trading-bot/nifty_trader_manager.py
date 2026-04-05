"""
NIFTY Trader Manager
This module manages different versions of the trading bot and provides a unified interface.
"""

from base import Product
from typing import List

# Bot version to use
BOT_VERSION = 13  # Change this to switch between versions
SAVE_DATA = True  # Set to False to disable CSV saving for speed


def get_player_algorithm(
    products: List[Product], instance_num: int = None, num_timestamps: int = None
):
    """
    Factory function to get the appropriate bot version.

    Args:
        products: List of tradeable products
        instance_num: Instance number for this simulation run
        num_timestamps: Total number of timestamps in the simulation

    Returns:
        An instance of the selected bot version
    """

    if BOT_VERSION == 1:
        from src.version_1.nifty_trader import NiftyTrader

        print(f"Loading NIFTY Trader Version 1 (Data Collection)")
        return NiftyTrader(products, instance_num=instance_num)

    elif BOT_VERSION == 2:
        from src.version_2.nifty_trader import NiftyTrader

        print(f"Loading NIFTY Trader Version 2 (Enhanced Position Management)")
        return NiftyTrader(products, instance_num=instance_num)

    elif BOT_VERSION == 3:
        from src.version_3.nifty_trader import NiftyTrader

        print(f"Loading NIFTY Trader Version 3 (Template - Data Collection Only)")
        return NiftyTrader(products, instance_num=instance_num)

    elif BOT_VERSION == 4:
        from src.version_4.nifty_trader import NiftyTrader

        print(f"Loading NIFTY Trader Version 4 (Template - Data Collection Only)")
        return NiftyTrader(
            products, instance_num=instance_num, num_timestamps=num_timestamps
        )

    elif BOT_VERSION == 5:
        from src.version_5.nifty_trader import NiftyTrader

        print(f"Loading NIFTY Trader Version 5 (Advanced Market Maker)")
        return NiftyTrader(
            products, instance_num=instance_num, num_timestamps=num_timestamps
        )

    elif BOT_VERSION == 6:
        from src.version_6.nifty_trader import NiftyTrader

        print(f"Loading NIFTY Trader Version 6 (Advanced Market Maker)")
        return NiftyTrader(
            products, instance_num=instance_num, num_timestamps=num_timestamps
        )

    elif BOT_VERSION == 7:
        from src.version_7.nifty_trader import NiftyTrader

        print(
            f"Loading NIFTY Trader Version 7 (Advanced Market Maker with Whale Detection)"
        )
        return NiftyTrader(
            products, instance_num=instance_num, num_timestamps=num_timestamps
        )

    elif BOT_VERSION == 8:
        from src.version_8.nifty_trader import NiftyTrader

        print(f"Loading NIFTY Trader Version 8 (Template - Infrastructure Only)")
        return NiftyTrader(
            products, instance_num=instance_num, num_timestamps=num_timestamps
        )

    elif BOT_VERSION == 9:
        from src.version_9.nifty_trader import NiftyTrader

        print(
            f"Loading NIFTY Trader Version 9 (v7 + Position-Based Price Skewing)"
        )
        return NiftyTrader(
            products, instance_num=instance_num, num_timestamps=num_timestamps
        )

    elif BOT_VERSION == 10:
        from src.version_10.nifty_trader import NiftyTrader

        print(f"Loading NIFTY Trader Version 10 (Data Logger - Observer Only)")
        return NiftyTrader(
            products, instance_num=instance_num, num_timestamps=num_timestamps
        )

    elif BOT_VERSION == 11:
        from src.version_11.nifty_trader import NiftyTrader

        print(f"Loading NIFTY Trader Version 11 (Pure ML Trading Bot)")
        return NiftyTrader(
            products, instance_num=instance_num, num_timestamps=num_timestamps
        )

    elif BOT_VERSION == 12:
        from src.version_12.nifty_trader import NiftyTrader

        print(f"Loading NIFTY Trader Version 12 (Decision Tree + Whale Detection)")
        return NiftyTrader(
            products, instance_num=instance_num, num_timestamps=num_timestamps
        )

    elif BOT_VERSION == 13:
        from src.version_13.nifty_trader import NiftyTrader

        print(f"Loading NIFTY Trader Version 13 (Hybrid Market Maker + Decision Tree)")
        return NiftyTrader(
            products, instance_num=instance_num, num_timestamps=num_timestamps
        )

    else:
        raise ValueError(f"Unknown bot version: {BOT_VERSION}")


# For backwards compatibility with existing code
class PlayerAlgorithm:
    """
    Wrapper class that maintains backwards compatibility with the original interface.
    This delegates all calls to the selected bot version.
    """

    def __init__(
        self,
        products: List[Product],
        instance_num: int = None,
        num_timestamps: int = None,
    ):
        self._bot = get_player_algorithm(
            products, instance_num=instance_num, num_timestamps=num_timestamps
        )
        # Copy over attributes for compatibility
        self.name = self._bot.name
        self.products = self._bot.products

    def send_messages(self, book):
        return self._bot.send_messages(book)

    def create_order(self, ticker, size, price, direction):
        return self._bot.create_order(ticker, size, price, direction)

    def remove_order(self, order_idx):
        return self._bot.remove_order(order_idx)

    def set_idx(self, idx):
        return self._bot.set_idx(idx)

    def process_trades(self, trades):
        return self._bot.process_trades(trades)
