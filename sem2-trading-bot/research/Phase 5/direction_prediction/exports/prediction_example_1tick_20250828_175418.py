
# Quick prediction example for exported model
import joblib
import pandas as pd
import numpy as np

# Load the model
model = joblib.load("best_rf_model_1tick_20250828_175418.joblib")

# Feature list (must match training exactly)
FEATURES = ['price_returns', 'price_returns_2', 'price_returns_5', 'spread', 'mid_price_vs_bid', 'mid_price_vs_ask', 'bid_ask_ratio', 'size_imbalance', 'total_top_size', 'size_ratio', 'volume_imbalance', 'total_volume', 'buy_ratio', 'depth_imbalance', 'total_depth', 'volatility_5', 'volatility_10', 'volatility_20', 'vol_5_vs_20', 'vol_10_vs_50', 'recent_vol_change', 'price_vs_ma5', 'price_vs_ma20', 'ma5_vs_ma20', 'price_momentum_3', 'price_momentum_10']

# Example prediction function
def predict_direction(market_data):
    """
    Predict price direction for 1-tick horizon

    Args:
        market_data: DataFrame with columns matching FEATURES

    Returns:
        int: 1 for UP, 0 for DOWN
        float: Probability of UP move
    """
    # Clean the data (same as training)
    X = market_data[FEATURES].copy()
    X = X.replace([np.inf, -np.inf], np.nan)
    for col in X.columns:
        X[col] = X[col].fillna(X[col].median())
        q1, q99 = X[col].quantile([0.01, 0.99])
        X[col] = X[col].clip(q1, q99)

    # Predict
    prediction = model.predict(X)[0]
    probability = model.predict_proba(X)[0, 1]  # Prob of UP

    return prediction, probability

# Usage example:
# direction, confidence = predict_direction(your_market_data)
# print(f"Prediction: {'UP' if direction else 'DOWN'} ({confidence:.1%} confidence)")
