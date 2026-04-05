import pandas as pd
import PanicTrader as template  # Our trading algorithm
from copy import deepcopy

DATA_LOCATION = "./data"  # Location of the data folder

# List of stock names (without .csv)
products = ["FAWA", "SMIF"]  # The stocks our algorithm will be backtested on

# Dictionary to store the price series dataframes for each stock
price_series = {}  # In the form {"ABC": Dataframe, ...}

# Dictionary to keep track of the current positions on each stock
positions = {}  # In the form {"ABC": position, ...}

# Dictionary to keep track of the current cash on each stock
cash = {}

# Populate these dictionaries
for product in products:
    price_series[product] = pd.read_csv(f"{DATA_LOCATION}/{product}.csv")
    positions[product] = 0
    cash[product] = 0

# Set constants
position_limit = 100
fees = 0.002

# Find the number of total timestamps
n_timestamps = len(price_series[products[0]])
# print(f"Backtesting on {n_timestamps} timestamps")

# Process the trades our algo would make on each timestamp
for i in range(n_timestamps):
    # Print progress every 1000 timestamps
    if i % 1000 == 0:
        pass
        # print(f"Processing timestamp {i}/{n_timestamps}")

    # Dictionary that is submitted to our getOrders() function with the current timestamp, best bid and best ask
    current_data = {}

    # Loop through each product to populate current_data dictionary
    for product in products:
        current_data[product] = {
            "Timestamp": i,
            "Bid": price_series[product].iloc[i]["Bids"],
            "Ask": price_series[product].iloc[i]["Asks"],
        }

    # Send this data to our algo's getOrders() function
    order = template.getOrders(deepcopy(current_data), deepcopy(positions))

    # Loop through all the products that our algo submitted
    for product in order:
        # Find the quantity for this product
        quant = int(order[product])

        # If the order quantity is 0, we do not have to process it
        if quant == 0:
            continue

        # Process buys and sells
        if quant > 0:  # Team is buying
            # If sent buy quantity exceeds position limit, adjust the quantity to fit within limits
            if positions[product] + quant > position_limit:
                # print(
                #     f"Timestamp {i}: Attempted to buy past position limit for {product}"
                # )
                quant = position_limit - positions[product]

            # Change cash for this product
            cash[product] -= current_data[product]["Ask"] * quant * (1 + fees)

        elif quant < 0:  # Team is selling
            # If sent sell quantity exceeds position limit, adjust the quantity to fit within limits
            if positions[product] + quant < -position_limit:
                # print(
                #     f"Timestamp {i}: Attempted to sell past position limit for {product}"
                # )
                quant = -position_limit - positions[product]

            # Change cash for this product
            cash[product] += current_data[product]["Bid"] * -quant * (1 - fees)

        # Modify our algo's position for this product
        positions[product] += quant

# Close any open positions at the end of the algorithm
cash_sum = 0
# print("\nFinal Results:")
for product in products:
    # print(
    #     f"{product} unclosed: PnL = {cash[product]:.2f}, Position = {positions[product]}"
    # )

    # If final position is positive, we sell against the last timestamp's best bid
    if positions[product] > 0:
        cash[product] += (
            price_series[product].iloc[-1]["Bids"] * positions[product] * (1 - fees)
        )

    # If final position is negative, we buy against the last timestamp's best ask
    elif positions[product] < 0:
        cash[product] -= (
            price_series[product].iloc[-1]["Asks"] * -positions[product] * (1 + fees)
        )

    # Add the cash of this product to the cash sum of all products
    cash_sum += cash[product]

    # print(f"{product} closed: PnL = {cash[product]:.2f}")

# Output final PnL
# print(f"\nTotal PnL = {cash_sum:.2f}")

# Generate and display visualization
# print("\nGenerating visualization...")
template.team_algorithm.visualize_strategy()
