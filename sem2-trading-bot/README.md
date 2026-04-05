# NIFTY Trader

1st place finish in the UWA QFin 2025 Semester 2 algorithmic trading competition. Solo entry competing against pair-based teams across an 8-week, 3-round simulated exchange.

## Competition Format

Bots traded in a turn-based simulated market alongside NPC market makers. Each round introduced new products and mechanics. Bots were evaluated on expected PnL across ~20 simulation runs of 20,000 ticks each, with $20/unit fines for exceeding position limits.

## Strategy Evolution

The bot went through 13 major iterations, progressing from a simple market maker to a volatility-adaptive system with ML-augmented direction prediction.

| Version | Strategy | Key Idea |
|---------|----------|----------|
| v1 | Simple MM | 2% spread undercut, basic position limits |
| v2 | Enhanced MM | Tighter spread (3.6 vs MM's 4.0), stops quoting at position limits |
| v4 | Standard MM | Clean 4-level implementation with linear fade |
| v5 | Dynamic MM | Position-dependent level reduction (4 -> 3 -> 2 -> 1 -> 0) |
| v6 | Volatility-Adaptive MM | Spread widens with price volatility, gradual mid tracking |
| v7-v13 | ML-Enhanced | Random Forest direction prediction, momentum signals, confidence-gated entries |

## Research Pipeline

Research was organized in phases, each building on the previous:

- **Phase 1-3**: Market microstructure analysis, spread dynamics, momentum discovery
- **Phase 4**: Momentum signal refinement across multiple products
- **Phase 5**: ML direction prediction (Random Forest, CatBoost), feature importance analysis, confidence calibration, model compression for low-latency inference

## Project Structure

```
base.py                      # Base trading bot class
nifty_trader_manager.py       # Bot version management and switching
trading_explorer.py           # Market analysis and visualization tools
trading_explorer_v2.py        # Extended analysis with multi-product support
BOT_OVERVIEW.md               # Detailed breakdown of each bot version
research/
  Phase 1-4/                  # Market analysis notebooks
  Phase 5/                    # ML pipeline: direction prediction, model exports
    direction_prediction/     # Random Forest results, feature importance, confidence analysis
    balanced_fast_exports/    # Production model configs and predictors
    compact_model_exports/    # Compressed models for fast inference
    ultra_fast_exports/       # Minimal-latency predictor variants
```
