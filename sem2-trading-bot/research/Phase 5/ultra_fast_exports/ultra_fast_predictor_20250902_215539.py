# Ultra-Fast Price Direction Predictor
# Generated: 20250902_215539
# Model: Single_Tree

import joblib
import numpy as np

# Load the ultra-fast model
model = joblib.load("ultra_fast_model_Single_Tree_20250902_215539.joblib")

# Ultra-minimal features (only 4!)
ULTRA_FEATURES = ['price_returns', 'size_imbalance', 'volume_momentum', 'spread_pct']

def predict_direction_ultra_fast(market_data):
    """
    Ultra-fast price direction prediction

    Performance: 0.18ms per prediction

    Args:
        market_data: Dict or DataFrame with features:
            - price_returns: Recent price change %
            - size_imbalance: (bid_size - ask_size) / total_size
            - volume_momentum: (buys - sells) / total_volume
            - spread_pct: spread / mid_price

    Returns:
        int: 1=UP, 0=DOWN
    """
    # Handle dict input
    if isinstance(market_data, dict):
        X = np.array([market_data[f] for f in ULTRA_FEATURES]).reshape(1, -1)
    else:
        X = market_data[ULTRA_FEATURES].values.reshape(1, -1)

    # Handle edge cases
    X = np.nan_to_num(X, nan=0.0, posinf=1e6, neginf=-1e6)

    return int(model.predict(X)[0])

def predict_with_confidence_ultra_fast(market_data):
    """
    Ultra-fast prediction with confidence (if model supports probabilities)
    """
    if isinstance(market_data, dict):
        X = np.array([market_data[f] for f in ULTRA_FEATURES]).reshape(1, -1)
    else:
        X = market_data[ULTRA_FEATURES].values.reshape(1, -1)

    X = np.nan_to_num(X, nan=0.0, posinf=1e6, neginf=-1e6)

    direction = int(model.predict(X)[0])

    # Try to get probabilities (some models support this)
    try:
        proba = model.predict_proba(X)[0]
        confidence = float(max(proba))
        prob_up = float(proba[1]) if len(proba) > 1 else 0.5
    except:
        confidence = 0.75  # Default confidence for non-probabilistic models
        prob_up = 0.75 if direction == 1 else 0.25

    return {
        'direction': direction,
        'confidence': confidence,
        'probability_up': prob_up
    }

# Performance Stats:
# ⚡ Speed: 0.18ms per prediction
# 📊 Accuracy: 73.4%
# 🎯 Features: 4 ultra-minimal features
# 📁 Size: 0.03MB
# ⏱️  20k predictions: 3.6 seconds
