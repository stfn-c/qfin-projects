# friend's script (wesley from UWA)

from typing import Dict

class TradingAlgorithm:

    def __init__(self):
        self.positions: Dict[str, int] = {}  # Tracking the positions in products

        # Coefficients from the trained linear regression models for VP, ORE, and WHEAT
        self.vp_coef = [0.89205968, 22.4798756, 2.88036676]  # Coefficients for VP (SHEEP, ORE, WHEAT)
        self.intercept_vp = 42.15015333713495
        self.threshold_vp = 30.35
        self.max_order_size = 100  # Max allowable position size (e.g., 100 units)

    def getMidprice(self, bid: float, ask: float) -> float:
        """Returns the midprice as the average of the bid and ask."""
        return (bid + ask) / 2
    
    def predict_vp(self, sheep: float, ore: float, wheat: float) -> float:
        """Predict VP price based on ORE, SHEEP, and WHEAT prices using the regression model."""
        return self.vp_coef[0] * sheep + self.vp_coef[1] * ore + self.vp_coef[2] * wheat + self.intercept_vp

    def getOrders(self, current_data: Dict[str, Dict[str, float]], order_data: Dict[str, int]) -> Dict[str, int]:
        # Extract current market prices for each product (bid and ask)
        sheep_bid = current_data["SHEEP"]["Bid"]
        sheep_ask = current_data["SHEEP"]["Ask"]
        ore_bid = current_data["ORE"]["Bid"]
        ore_ask = current_data["ORE"]["Ask"]
        vp_bid = current_data["VP"]["Bid"]
        vp_ask = current_data["VP"]["Ask"]
        wheat_bid = current_data["WHEAT"]["Bid"]
        wheat_ask = current_data["WHEAT"]["Ask"]

        # Get midprices for each product
        sheep_mid = self.getMidprice(sheep_bid, sheep_ask)
        ore_mid = self.getMidprice(ore_bid, ore_ask)
        vp_mid = self.getMidprice(vp_bid, vp_ask)
        wheat_mid = self.getMidprice(wheat_bid, wheat_ask)

        # Predict prices using the regression models
        predicted_vp = self.predict_vp(sheep_mid, ore_mid, wheat_mid)
        # Calculate thresholds for each product
        threshold_vp = self.threshold_vp

        # Decision to buy or sell VP, ORE, and WHEAT based on predicted price and threshold
        # Always try to buy or sell the max order size based on the prediction
        if predicted_vp >= vp_mid + threshold_vp:
            # Check current position and ensure we don't exceed the max limit
            remaining_capacity = self.max_order_size - self.positions.get("VP", 0)
            if remaining_capacity > 0:
                order_data["VP"] = min(self.max_order_size, remaining_capacity)  # Buy as much as possible within the limit
        elif predicted_vp <= vp_mid - threshold_vp:
            # Check current position and ensure we don't exceed the max limit
            remaining_capacity = -self.max_order_size - self.positions.get("VP", 0)
            if remaining_capacity < 0:
                order_data["VP"] = max(-self.max_order_size, remaining_capacity)  # Sell as much as possible within the limit

        # Similarly for ORE and WHEAT (if you'd like them to "full send" too):
        # Apply similar logic for ORE and WHEAT if you want to handle them
        # For now, we will leave it as is for VP.

        return order_data


# Leave this stuff as it is
team_algorithm = TradingAlgorithm()

def getOrders(current_data, positions):
    team_algorithm.positions = positions
    order_data = {product: 0 for product in current_data}
    return team_algorithm.getOrders(current_data, order_data)
