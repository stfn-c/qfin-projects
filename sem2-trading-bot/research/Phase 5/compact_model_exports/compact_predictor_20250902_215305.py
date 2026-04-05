# Compact Fast Price Direction Predictor
# Generated: 20250902_215305

import joblib
import numpy as np
import pandas as pd

# Load the compact model
model = joblib.load("compact_rf_model_20250902_215305.joblib")

# Required features (only 9 features!)
COMPACT_FEATURES = ['price_returns', 'price_returns_2', 'spread_pct', 'size_imbalance', 'price_momentum_3', 'volatility_5', 'total_volume', 'buy_ratio', 'spread']

def predict_direction_fast(market_data):
    """
    Fast price direction prediction with compact model

    Args:
        market_data: DataFrame with required features

    Returns:
        dict: {
            'direction': int (1=UP, 0=DOWN),
            'confidence': float,
            'probability_up': float,
            'probability_down': float
        }
    """
    # Prepare features
    X = market_data[COMPACT_FEATURES].values.reshape(1, -1)

    # Handle any NaN or inf values
    X = np.nan_to_num(X, nan=0.0, posinf=1e6, neginf=-1e6)

    # Predict
    direction = model.predict(X)[0]
    probabilities = model.predict_proba(X)[0]

    prob_down = probabilities[0]
    prob_up = probabilities[1]
    confidence = max(prob_up, prob_down)

    return {
        'direction': int(direction),
        'confidence': float(confidence),
        'probability_up': float(prob_up),
        'probability_down': float(prob_down)
    }

# Performance stats:
# - Accuracy: 82.7%
# - Speed: ~29.1ms per prediction
# - Features: 9 (vs 26 in full model)
# - Size: ~1.2MB (vs 35MB in full model)
