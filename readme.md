# PanicTrader: Algorithmic Trading Bot

![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)
![C++](https://img.shields.io/badge/C++-17-blue.svg)
![Finance](https://img.shields.io/badge/Finance-Algorithmic_Trading-green.svg)

## Project Overview

PanicTrader is an algorithmic trading system designed to identify and exploit market inefficiencies across diverse financial datasets. The project focuses on analyzing historical price data, bid-ask spreads, and volatility metrics to develop distinct trading strategies tailored to specific market behaviors. All strategies were developed and tested using simulated financial data provided as part of an 8-week, 3-round UWA Quantitative Finance Society (QFin) algorithmic trading competition.

This project achieved 1st place in the competition, competing against pair-based teams across 8 diverse simulated stocks.

**Author:** Stefan Ciutina  
**Presented To:** QFin & IMC representatives

### Objectives

This project explores market inefficiencies beyond conventional trading strategies by:

- Identifying exploitable patterns across various financial instruments
- Developing automated systems to execute trades based on these patterns
- Moving beyond standard trend-following and mean-reversion approaches
- Applying statistical methods to analyze financial datasets
- Iteratively testing and refining strategy performance

### Methodology Overview

The development process involved:
- Initial research and signal discovery using Jupyter Notebooks
- Implementation of algorithms with tunable parameters
- Transpiling algorithms to C++ for optimized parameter sweeping
- Creating interactive visualizations to analyze trading performance

## Trading Strategies

The project developed four distinct trading strategies, each targeting different market characteristics and inefficiencies.

### UEC Stock Strategy: Bid-Ask Spread Analysis

#### Key Findings

Analysis of UEC data revealed a non-random pattern in the bid-ask spread, where periods of tight spread (approximately 1.00) alternated with well-defined periods of widened spread (approximately 1.40). 

During low spread periods, UEC demonstrated directional price movement, while high spread periods corresponded with price stagnation. This correlation provided the basis for a trading strategy.

#### Implementation

The strategy operates on the following principles:

1. Monitor UEC's bid-ask spread to identify transitions from high to low spread
2. Implement an observation window after transitions to allow trend establishment
3. Determine price direction using short-term moving averages
4. Enter positions in the determined direction
5. Exit when high spread conditions reemerge

#### Performance Analysis

The strategy development followed systematic optimization:

1. Initial implementation achieved a PNL of approximately $4,000 with significant drawdowns
2. Parameter optimization was implemented for key variables including moving average windows and threshold values
3. Strategy logic was transpiled from Python to C++ to accelerate testing, achieving a 5,000x performance improvement
4. Grid search across approximately 1,000 parameter combinations identified optimal configurations
5. Optimized strategy achieved $8,677 PNL on the training dataset
6. Out-of-sample testing yielded approximately $4,000 PNL, indicating potential overfitting

#### Key Parameters

Four primary parameters drove strategy performance:

- `short_window`: Lookback period for short-term moving average
- `HS_exit_threshold`: Price movement threshold after high spread periods
- `ma_turn_threshold`: Rolling average pullback threshold for position exits
- `waiting_period`: Observation window after spread transitions

### SOBER Stock Strategy: Volatility Analysis

#### Key Findings

SOBER exhibited distinct characteristics from UEC, notably showing sharp volatility spikes against a consistent downward price trend. These features formed the basis for a counter-trend trading strategy.

#### Implementation

The strategy was designed with the following structure:

1. Maintain a default short position aligned with the general downward trend
2. Calculate volatility as the standard deviation of recent returns
3. When volatility exceeds a critical threshold, prepare for potential counter-trend trade
4. Use short-term moving average (SMA) to identify potential price reversals
5. Enter long positions when SMA begins increasing after volatility spike
6. Exit when the moving average of volatility peaks and starts decreasing
7. Implement risk management via price thresholds and spread monitoring

#### Performance Analysis

The SOBER strategy demonstrated robust performance:

- Training dataset PNL: $92,000
- Out-of-sample PNL: $52,000 (56% retention)

The strong out-of-sample performance suggests the strategy captures a genuine market inefficiency rather than merely fitting to historical data.

#### Key Parameters

Six critical parameters influenced strategy effectiveness:

- `short_window` (Default: 5): Lookback period for price moving average
- `volatility_window` (Default: 50): Period for volatility calculation
- `volatility_threshold` (Default: 0.002): Volatility level triggering entry conditions
- `vol_ma_window` (Default: 5): Sensitivity of volatility's moving average
- `position_size` (Default: 100): Standard position size
- `price_threshold` (Default: 95): Stop-loss level

### FAWA & SMIF Strategy: Lead-Lag Relationship

#### Key Findings

Analysis of FAWA and SMIF revealed a clear lead-lag relationship between the two assets. Correlation metrics showed:

- Maximum price correlation of 0.9671 at -68 tick lag
- Maximum returns correlation of 0.3512 at -68 tick lag
- Maximum R² of 0.9353 at -68 tick lag

These metrics indicated potential for using one asset's movements to predict the other's.

#### Implementation

Rather than implementing a fixed lag, the strategy used a confirmation-based approach:

1. Monitor FAWA's price using a short-term moving average
2. Identify significant moves, defined as percentage changes from recent extremes
3. Enter a "primed" state noting the direction of FAWA's movement
4. Calculate SMIF's own SMA and determine its trend direction
5. Execute trades when SMIF's direction confirms FAWA's signal
6. Maintain positions until exit conditions are met

#### Performance Analysis

The strategy produced consistent results:

- PNL range of $8,000-$9,000 across different parameter sets
- Best performance: $8,974.20 with 33 trades (Leader: 39, Follower: 14, Threshold: 1.4%)
- Notably, the statistically identified 68-tick lag proved less relevant in the final implementation than a confirmation-based approach

#### Key Parameters

Three parameters drove strategy performance:

- `Leader Window`: FAWA's SMA lookback period
- `Follower Window`: SMIF's SMA lookback period
- `Threshold %`: Percentage move in FAWA required to prime a signal

### Multi-Asset Statistical Arbitrage Strategy

#### Key Findings

Analysis of ORE, SHEEP, VP, and WHEAT revealed significant inter-asset correlations:

- Strong correlation between ORE & VP (0.846)
- Moderate correlation between VP & WHEAT (0.593)

Linear regression modeling showed high predictive power:
- VP predicted by other assets: R² = 0.977
- ORE predicted by other assets: R² = 0.963

#### Implementation

The strategy development followed these steps:

1. Build multiple linear regression models with each asset as the target variable
2. Implement Forward Chaining Cross-Validation to test model robustness
3. Analyze coefficient stability and predictive power across time periods
4. Develop a trading strategy based on deviations between actual and predicted prices
5. Optimize parameters using 3D visualization of the parameter space

#### Performance Analysis

The multi-asset strategy delivered the strongest performance:

- Total PNL: $1,750,067.28
- Breakdown:
  - VP: ~$1.73 Million
  - SHEEP: ~$21,000
  - ORE: ~$1,700
  - WHEAT: $0 (no profitable trading opportunities identified)

#### Key Parameters

The optimal parameter configuration:

- `Positive DiffMAThreshold`: 34 (Threshold for positive price-prediction deviations)
- `Negative DiffMAThreshold`: -30.4 (Threshold for negative deviations)
- `RollingAvgWindow`: 1 (Smoothing window for difference calculations)
- `FixedOrderQuantity`: 100 (Standard position size)

## Technical Implementation

### Programming Languages

The project utilized a dual-language approach:

- **Python:** Used for data exploration, visualization, and prototype development, leveraging data analysis libraries for pattern identification and initial testing
  
- **C++:** Implemented for parameter optimization and large-scale backtesting, providing substantial performance improvements (up to 5,000x faster) for computationally intensive tasks

### Visualization Methods

Several visualization techniques were employed throughout the development process:

- Time series analysis for price and spread patterns
- Volatility visualization for spike identification
- Correlation matrices for inter-asset relationship mapping
- R² and prediction error analysis during cross-validation
- 3D parameter space visualization for optimization
- Interactive performance plots showing trade execution and results

## Key Findings

1. **Market Microstructure Signals:** Bid-ask spread patterns can provide actionable trading signals, with UEC demonstrating how spread regimes correlate with price behavior

2. **Volatility as Signal:** Volatility spikes can indicate counter-trend opportunities when combined with appropriate confirmatory indicators

3. **Lead-Lag Implementation:** Inter-asset relationships require adaptive implementation rather than fixed lags, with confirmation-based approaches outperforming rigid timing models

4. **Statistical Arbitrage Efficacy:** Linear regression models can identify significant mispricings with high predictive power, enabling substantial returns when properly implemented

5. **Technical Implementation Impact:** The choice of programming language and optimization techniques directly affects strategy development capacity, with significant performance differences between Python and C++

6. **Cross-Validation Value:** Forward chaining cross-validation reveals how statistical relationships evolve over time, providing insights into model stability and potential regime changes

---

*Note: This project was developed for an educational trading competition using simulated financial data. Performance metrics should not be interpreted as indicative of real-market results.*