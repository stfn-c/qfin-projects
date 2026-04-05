# Balanced Fast Price Direction Predictor
# Generated: 20250902_215922
# Model: RF_25_trees

import joblib
import numpy as np

# Load the balanced model
model = joblib.load("balanced_model_RF_25_trees_20250902_215922.joblib")

# Balanced features (8 features)
BALANCED_FEATURES = ['price_returns', 'price_returns_2', 'size_imbalance', 'volume_imbalance', 'spread_pct', 'volatility_5', 'momentum_ratio', 'total_volume']

def predict_direction_balanced(market_data):
    """
    Balanced speed/accuracy price direction prediction

    Performance: 0.85ms per prediction, 79.8% accuracy

    Args:
        market_data: Dict or DataFrame with features

    Returns:
        int: 1=UP, 0=DOWN
    """
    # Prepare features
    if isinstance(market_data, dict):
        X = np.array([market_data[f] for f in BALANCED_FEATURES]).reshape(1, -1)
    else:
        X = market_data[BALANCED_FEATURES].values.reshape(1, -1)

    # Handle edge cases
    X = np.nan_to_num(X, nan=0.0, posinf=1e6, neginf=-1e6)

    return int(model.predict(X)[0])

def predict_with_confidence_balanced(market_data):
    """
    Balanced prediction with confidence
    """
    if isinstance(market_data, dict):
        X = np.array([market_data[f] for f in BALANCED_FEATURES]).reshape(1, -1)
    else:
        X = market_data[BALANCED_FEATURES].values.reshape(1, -1)

    X = np.nan_to_num(X, nan=0.0, posinf=1e6, neginf=-1e6)

    direction = int(model.predict(X)[0])

    try:
        proba = model.predict_proba(X)[0]
        confidence = float(max(proba))
        prob_up = float(proba[1]) if len(proba) > 1 else 0.5
    except:
        confidence = 0.8
        prob_up = 0.8 if direction == 1 else 0.2

    return {
        'direction': direction,
        'confidence': confidence,
        'probability_up': prob_up
    }


# Performance Stats:
# 🎯 Accuracy: 79.8% (vs 73.4% ultra-fast, vs ~92% full model)
# ⚡ Speed: 0.85ms (vs 0.18ms ultra-fast, vs 37ms full model)
# 📊 Features: 8 balanced features
# 📁 Size: 0.66MB
# ⏱️  20k predictions: 17.0 seconds
# 🏆 Selection: Good accuracy (≥75%) + Very fast (<5ms)
