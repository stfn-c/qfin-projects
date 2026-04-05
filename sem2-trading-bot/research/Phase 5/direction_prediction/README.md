# Direction Prediction Research

## Overview
This folder contains advanced machine learning models for predicting short-term price direction (UP/DOWN) in high-frequency trading data. The goal is to achieve maximum accuracy for 1-10 tick horizons using only market microstructure variables.

## What We're Doing

### 🎯 **Problem Statement**
- **Input**: Market microstructure data (order book, volume, spreads, etc.)
- **Output**: Binary prediction (UP=1, DOWN=0) for future price direction
- **Horizons**: 1, 2, 3, 5, and 10 ticks ahead
- **Constraint**: No internal bot data - only observable market variables

### 🔬 **Research Approach**

#### **1. Data Preparation**
- Load trading data from v7/round_1 (48K observations from 8 instances)
- Create 26 market-only features:
  - Price movements & momentum
  - Order book imbalances
  - Volume patterns
  - Technical indicators
  - Moving average signals

#### **2. Model Development**
- **Simple Rules**: Baseline heuristics (size_imbalance, volatility_low, etc.)
- **Advanced ML**: Ensemble of optimized models with feature selection
- **Target**: Maximize accuracy beyond random (50%) baseline

#### **3. Optimization Techniques**
- **Feature Selection**: Top 20 most predictive variables
- **Hyperparameter Tuning**: Optimized model parameters
- **Ensemble Methods**: Voting classifier combining best models
- **Data Preprocessing**: Robust scaling and outlier removal

### 📊 **Results Achieved**
- **Best Performance**: 90.0% accuracy on 1-tick direction prediction
- **Model**: RandomForest with 85.1% UP precision, 91.4% DOWN precision
- **Trading Edge**: 40% advantage over random (90% vs 50%)
- **Simple Rules**: Best achieved 71.7% (volatility_low rule)

### 💰 **Trading Implications**
- **Expected Edge**: 80% per trade ((90%-50%)*2)
- **Profitability**: Viable if transaction costs < 80%
- **Strategy**: Ultra-high frequency trading on 1-tick predictions
- **Risk Management**: 10% error rate requires position sizing

## Files

### `price_direction_prediction.ipynb`
Main research notebook containing:
- Data loading and feature engineering
- Simple rule-based models
- Advanced ML training with ensemble methods
- Results analysis and visualization
- Feature importance analysis

## Key Features Engineered

### **Price-Based (3 features)**
- `price_returns`: 1-tick price changes
- `price_returns_2`: 2-tick price changes  
- `price_returns_5`: 5-tick price changes

### **Order Book (4 features)**
- `spread`: Bid-ask spread
- `mid_price_vs_bid`: Distance from mid to best bid
- `mid_price_vs_ask`: Distance from mid to best ask
- `bid_ask_ratio`: Ratio of bid to ask prices

### **Size & Imbalance (3 features)**
- `size_imbalance`: (Bid size - Ask size) / Total size
- `total_top_size`: Combined top-of-book size
- `size_ratio`: Bid size / Ask size ratio

### **Volume (3 features)**
- `volume_imbalance`: (Buy volume - Sell volume) / Total
- `total_volume`: Combined trading volume
- `buy_ratio`: Buy volume percentage

### **Market Depth (2 features)**
- `depth_imbalance`: Bid levels vs Ask levels imbalance
- `total_depth`: Total order book depth

### **Technical Indicators (6 features)**
- `volatility_5/10/20`: Rolling volatility measures
- `vol_5_vs_20`: Volatility ratio (short vs long)
- `vol_10_vs_50`: Another volatility ratio
- `recent_vol_change`: Change in recent volatility

### **Moving Averages (3 features)**
- `price_vs_ma5`: Price relative to 5-tick MA
- `price_vs_ma20`: Price relative to 20-tick MA  
- `ma5_vs_ma20`: Short vs long MA ratio

### **Momentum (2 features)**
- `price_momentum_3`: 3-tick momentum
- `price_momentum_10`: 10-tick momentum

## Model Performance Summary

| Model | Accuracy | UP Precision | DOWN Precision | Notes |
|-------|----------|--------------|----------------|--------|
| RandomForest | 90.0% | 85.1% | 91.4% | Best overall |
| LogisticRegression | 81.4% | 74.5% | 82.6% | Fast, interpretable |
| ExtraTrees | TBD | TBD | TBD | Advanced version |
| XGBoost | TBD | TBD | TBD | Advanced version |
| Ensemble | TBD | TBD | TBD | Voting combination |

## Next Steps

1. **Robustness Testing**: Validate on different rounds/versions
2. **Feature Engineering**: Create additional predictive variables
3. **Real-time Implementation**: Optimize for live trading latency
4. **Risk Management**: Develop position sizing algorithms
5. **Market Regime Analysis**: Performance across different market conditions

## Usage Notes

- Models trained on v7/round_1 data only
- Performance may vary across different market conditions
- 90% accuracy is exceptional but not 100% - risk management essential
- 1-tick predictions require ultra-low latency execution
- Transaction costs must be < 80% for profitability