# NIFTY Trading Bot Versions Overview

This document provides a comprehensive overview of all trading bot versions, their strategies, and key differences.

## Bot Version Summary

| Version | Strategy | Key Features | Spread | Position Management |
|---------|----------|-------------|--------|-------------------|
| v1 | Simple Market Maker | 2% undercut, basic positioning | 2% tighter than MM | Basic limits (±200) |
| v2 | Enhanced Market Maker | 3 levels, position controls | 3.6 (10% tighter) | Stop quoting at ±150 |
| v4 | Standard Market Maker | Clean MM implementation | 3.8 | Linear fade |
| v5 | Dynamic Market Maker | Position-based level reduction | 3.6 | Dynamic levels (4→3→2→1→0) |
| v6 | Volatility-Adaptive MM | Spread adjusts to volatility | 3.8 + volatility | Advanced position controls |

## Version 1: Simple Market Maker with 2% Undercut

**File**: `src/version_1/nifty_trader.py`

**Strategy**: Basic market making with competitive pricing
- Undercuts market maker by 2% (uses 98% of MM spread)
- Places 2 levels on each side with 5 units per level
- Simple position tracking and linear fade (0.5 fade rate)

**Key Parameters**:
- Spread: `MM_spread × 0.98` (2% tighter)
- Levels: 2 on each side
- Size: 5 per level
- Fade rate: 0.5
- Position limit: ±200

**Pros**: Simple, easy to understand, competitive pricing
**Cons**: Basic risk management, limited sophistication

## Version 2: Enhanced Market Maker with Tighter Spread

**File**: `src/version_2/nifty_trader.py`

**Strategy**: Exact market maker clone with improvements
- Mimics MM behavior with 3 levels instead of 4
- 10% tighter spread for competitive advantage
- Stops quoting one side at ±150 position

**Key Parameters**:
- Spread: 3.6 (vs MM's 4.0)
- Levels: 1 on each side (note: code shows 1, description says 3)
- Size: 25 per level
- Fade rate: 0.02
- Position limits: ±125 (stops quoting one side)

**Pros**: Conservative risk management, proven MM strategy
**Cons**: Limited levels may reduce capture opportunities

## Version 4: Market Maker with 3.8 Spread  

**File**: `src/version_4/nifty_trader.py`

**Strategy**: Clean market maker implementation
- Standard MM behavior with competitive spread
- 4 levels on both sides for good market coverage
- Linear position fade for inventory management

**Key Parameters**:
- Spread: 3.8
- Levels: 4 on each side
- Size: 20 per level
- Fade rate: 0.05
- Position limits: Soft at ±100, hard at ±150

**Pros**: Good market coverage, proven strategy
**Cons**: Less sophisticated than later versions

## Version 5: Dynamic Market Maker

**File**: `src/version_5/nifty_trader.py`

**Strategy**: Advanced position-based risk management
- Dynamically reduces levels as position grows
- Asymmetric quoting (different sizes on bid/ask)
- Sophisticated position thresholds

**Key Parameters**:
- Spread: 3.6
- Dynamic levels: 4 → 3 → 2 → 1 → 0 based on position
- Size: 25 base, reduced when position > 50
- Fade rate: 0.025
- Position thresholds: 50, 100, 150, 180

**Level Reduction Logic**:
- Position < 50: 4 levels each side
- Position 50-100: 3 levels each side  
- Position 100-150: 2 levels each side
- Position 150-180: 1 level each side
- Position > 180: Stop adverse side

**Pros**: Sophisticated risk management, position-aware
**Cons**: Complex logic, may miss opportunities at high positions

## Version 6: Volatility-Adaptive Market Maker

**File**: `src/version_6/nifty_trader.py`

**Strategy**: Market-adaptive sophisticated market maker
- Spread widens based on recent price volatility
- Tracks market mid and gradually adjusts base mid
- Very conservative position limits
- Comprehensive data logging and state tracking

**Key Parameters**:
- Base spread: 3.8
- Volatility adjustment: `spread + (volatility / 0.8)`
- Dynamic levels: Similar to v5 but more conservative thresholds (25, 50, 150, 180)
- Size: 25 base with asymmetric adjustment
- Fade rate: 0.02
- Conservative position limit: ±150

**Advanced Features**:
- **Volatility calculation**: Standard deviation of last 3 mid prices
- **Market tracking**: Gradually adjusts base_mid toward market mid (10% speed)
- **Smart rounding**: Rounds bids down, asks up for better fills
- **Source code copying**: Saves bot source with data for reproducibility

**Pros**: Most sophisticated, adapts to market conditions, excellent logging
**Cons**: Most complex, conservative limits may reduce profitability

## Data Collection & Analysis

All versions collect comprehensive market data:
- Position, cash, PnL tracking over time
- Best bid/ask prices and sizes
- Trade quantities (buys/sells per tick)
- Settlement logic with position unwinding simulation

**Data Storage**: `research/raw_data/v{N}/round_{R}/instance_{I}.csv`

**Additional Files** (v5, v6):
- `.params.json`: Bot configuration parameters
- `.state.json`: Comprehensive tick-by-tick state (if enabled)
- Source code copies for reproducibility

## Performance Characteristics

**Expected Performance Ranking** (based on sophistication):
1. **v6**: Best - volatility adaptation + market tracking
2. **v5**: Very good - dynamic risk management  
3. **v4**: Good - solid MM implementation
4. **v2**: Moderate - conservative but limited levels
5. **v1**: Basic - simple but may take more risk

**Risk Management Ranking**:
1. **v6**: Most conservative (±150 hard limit)
2. **v5**: Dynamic risk scaling
3. **v2**: Stops quoting at ±125  
4. **v4**: Standard controls
5. **v1**: Basic (±200 limit)

## Choosing a Version

- **For competition**: v6 or v5 (most sophisticated)
- **For learning**: v1 or v4 (simpler logic)
- **For testing**: v4 (clean implementation)
- **For safety**: v2 or v6 (conservative limits)

## Evolution Path

The versions show clear evolution in sophistication:

1. **v1**: Basic market making concept
2. **v2**: Add position-based controls  
3. **v4**: Clean up implementation, standard MM
4. **v5**: Add dynamic risk management
5. **v6**: Add market adaptation and volatility response

Each version builds on lessons learned from previous implementations, with v6 representing the current state-of-the-art for this trading competition.