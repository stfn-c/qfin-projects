import pandas as pd
import PanicTrader as template  # Replace 'filename' with whatever your algorithm file is named
from copy import deepcopy

DATA_LOCATION = "./data"  # Set this to the location of your data folder

# List of stock names (without .csv)
products = [
    "UEC",
    "SOBER"
]  # This list determiens the stocks your algorithm will be backtested on

# Dictionary to store the price series dataframes for each stock
price_series = {}  # In the form {"ABC": Dataframe, ...}

# Dictionary to keep track of the current positions on each stock
positions = {}  # In the form {"ABC": position, ...}

# Dictionary to keep track of the current cash on each stock
cash = {}

# Populate these dictionaries
for product in products:
    price_series[product] = pd.read_csv(f"{DATA_LOCATION}/{product}.csv")
    # price_series[product] = pd.read_csv(f"{DATA_LOCATION}/{product}_fut1.csv")
    positions[product] = 0
    cash[product] = 0

# Set constants
position_limit = 100
fees = 0.002

# Find the number of total timestamps (Should evaluate to 360 * 30)
n_timestamps = len(price_series[products[0]])

# Process the trades your algo would make on each timestamp
for i in range(n_timestamps):

    # Dictionary that is submitted to your getOrders() function with the current timestamp, best bid and best ask
    current_data = {}

    # Loop through each product to populate current_data dictionary
    for product in products:
        current_data[product] = {
            "Timestamp": i,
            "Bid": price_series[product].iloc[i]["Bids"],
            "Ask": price_series[product].iloc[i]["Asks"],
        }

    # Send this data to your algo's getOrders() function
    order = template.getOrders(deepcopy(current_data), deepcopy(positions))

    # Loop through all the products that your algo submitted
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
                # print("Attemtped to buy past position limit")
                quant = 0

            # Change cash for this product
            cash[product] -= current_data[product]["Ask"] * quant * (1 + fees)

        elif quant < 0:  # Team is selling

            # If sent sell quantity exceeds position limit, adjust the quantity to fit within limits
            if positions[product] + quant < -position_limit:
                # print("Attemtped to sell past position limit")
                quant = 0

            # Change cash for this product
            cash[product] += current_data[product]["Bid"] * -quant * (1 - fees)

        # Modify your algo's position for this product
        positions[product] += quant

# Close any open positions at the end of the algorithm
cash_sum = 0
for product in products:
    print(f"{product} unclosed: PnL = {cash[product]}, Position = {positions[product]}")

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

    print(f"{product} closed: PnL = {cash[product]}")

# Output final PnL
print(f"Total PnL = {cash_sum}")
