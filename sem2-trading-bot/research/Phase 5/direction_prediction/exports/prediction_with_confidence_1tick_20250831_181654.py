
# Enhanced prediction with confidence analysis
import joblib
import pandas as pd
import numpy as np

# Load the model
model = joblib.load("best_rf_model_1tick_20250831_181654.joblib")

# Feature list (must match training exactly)
FEATURES = ['price_returns', 'price_returns_2', 'price_returns_5', 'spread', 'mid_price_vs_bid', 'mid_price_vs_ask', 'bid_ask_ratio', 'size_imbalance', 'total_top_size', 'size_ratio', 'volume_imbalance', 'total_volume', 'buy_ratio', 'depth_imbalance', 'total_depth', 'volatility_5', 'volatility_10', 'volatility_20', 'vol_5_vs_20', 'vol_10_vs_50', 'recent_vol_change', 'price_vs_ma5', 'price_vs_ma20', 'ma5_vs_ma20', 'price_momentum_3', 'price_momentum_10']

# Confidence thresholds from training
HIGH_CONFIDENCE_THRESHOLD = 0.8
VERY_HIGH_CONFIDENCE_THRESHOLD = 0.9

def predict_direction_with_confidence(market_data):
    """
    Predict price direction for 1-tick horizon with confidence analysis

    Args:
        market_data: DataFrame with columns matching FEATURES

    Returns:
        dict: {
            'direction': int (1=UP, 0=DOWN),
            'confidence': float (0.5-1.0),
            'probability_up': float,
            'probability_down': float,
            'conviction': str ('LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH'),
            'trade_signal': str ('PASS', 'CONSIDER', 'TRADE', 'STRONG_TRADE')
        }
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
    probabilities = model.predict_proba(X)[0]

    prob_down = probabilities[0]
    prob_up = probabilities[1]
    confidence = max(prob_up, prob_down)

    # Determine conviction level
    if confidence >= VERY_HIGH_CONFIDENCE_THRESHOLD:
        conviction = 'VERY_HIGH'
        trade_signal = 'STRONG_TRADE'  # Expected accuracy: 98.9%
    elif confidence >= HIGH_CONFIDENCE_THRESHOLD:
        conviction = 'HIGH'
        trade_signal = 'TRADE'  # Expected accuracy: 97.3%
    elif confidence >= 0.7:
        conviction = 'MEDIUM'
        trade_signal = 'CONSIDER'
    else:
        conviction = 'LOW'
        trade_signal = 'PASS'

    return {
        'direction': int(prediction),
        'confidence': float(confidence),
        'probability_up': float(prob_up),
        'probability_down': float(prob_down),
        'conviction': conviction,
        'trade_signal': trade_signal
    }

# Usage example:
# result = predict_direction_with_confidence(your_market_data)
# if result['trade_signal'] in ['TRADE', 'STRONG_TRADE']:
#     direction = 'UP' if result['direction'] else 'DOWN'
#     print(f"TRADE: {direction} ({result['confidence']:.1%} confidence, {result['conviction']} conviction)")
