#!/usr/bin/env python3
"""
NIFTY Trader Interactive Explorer v2

A Streamlit web application for exploring trading bot performance data.
Enhanced version with click-to-jump functionality.

Run with: streamlit run trading_explorer_v2.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Configure Streamlit page
st.set_page_config(
    page_title="NIFTY Trading Bot Explorer",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better cursor and bigger icons
st.markdown("""
<style>
    /* Make plotly toolbar icons bigger */
    .modebar {
        transform: scale(1.3) !important;
        transform-origin: top left !important;
    }
    
    /* Change cursor from 4-arrows to pointer on plotly charts */
    .plot-container .plotly .drag {
        cursor: pointer !important;
    }
    
    .plot-container .plotly .nsewdrag {
        cursor: pointer !important;  
    }
    
    .js-plotly-plot .plotly .drag {
        cursor: pointer !important;
    }
    
    /* Improve hover cursor */
    .js-plotly-plot .plotly .modebar-btn {
        cursor: pointer !important;
    }
    
    /* Remove 4-arrow cursor completely */
    .draglayer {
        cursor: pointer !important;
    }
</style>
""", unsafe_allow_html=True)

# Main title
st.title("NIFTY Trading Bot Interactive Explorer")
st.markdown("---")

class DataLoader:
    """Handles loading and caching of trading data"""
    
    def __init__(self, base_path="research/raw_data"):
        self.base_path = Path(base_path)
    
    def get_available_versions(self):
        """Get all available bot versions"""
        if not self.base_path.exists():
            return []
        versions = []
        for path in self.base_path.iterdir():
            if path.is_dir() and path.name.startswith('v'):
                try:
                    version_num = int(path.name[1:])
                    versions.append(version_num)
                except ValueError:
                    continue
        return sorted(versions)
    
    def get_available_rounds(self, version):
        """Get all available rounds for a version"""
        version_path = self.base_path / f"v{version}"
        if not version_path.exists():
            return []
        rounds = []
        for path in version_path.iterdir():
            if path.is_dir() and path.name.startswith('round_'):
                try:
                    round_num = int(path.name.split('_')[1])
                    rounds.append(round_num)
                except ValueError:
                    continue
        return sorted(rounds)
    
    def get_available_instances(self, version, round_num):
        """Get all available instances for a version/round"""
        round_path = self.base_path / f"v{version}" / f"round_{round_num}"
        if not round_path.exists():
            return []
        instances = []
        for file_path in round_path.glob("instance_*.csv"):
            try:
                instance_num = int(file_path.stem.split('_')[1])
                instances.append(instance_num)
            except ValueError:
                continue
        return sorted(instances)
    
    @st.cache_data
    def load_csv_data(_self, version, round_num, instance):
        """Load CSV data for a specific instance"""
        csv_path = _self.base_path / f"v{version}" / f"round_{round_num}" / f"instance_{instance}.csv"
        print(f"[CSV] Loading: {csv_path}")
        
        if not csv_path.exists():
            print(f"[CSV] File not found: {csv_path}")
            return None
        
        try:
            print(f"[CSV] Reading CSV file...")
            df = pd.read_csv(csv_path)
            print(f"[CSV] Loaded {len(df)} rows, {len(df.columns)} columns")
            
            # Log NaN counts
            bid_nulls = df["best_bid"].isna().sum() if "best_bid" in df.columns else 0
            ask_nulls = df["best_ask"].isna().sum() if "best_ask" in df.columns else 0
            if bid_nulls > 0 or ask_nulls > 0:
                print(f"[CSV] Found NaN values: best_bid={bid_nulls}, best_ask={ask_nulls}")
            
            # Calculate derived metrics with NaN handling
            # Use existing mid_price if best_bid/ask are null
            if "mid_price" not in df.columns:
                print("[CSV] No mid_price column, calculating from bid/ask")
                df["mid_price"] = (df["best_bid"] + df["best_ask"]) / 2
            else:
                print("[CSV] mid_price column exists, recalculating where bid/ask available")
                # Only recalculate where we have both bid and ask
                mask = df["best_bid"].notna() & df["best_ask"].notna()
                valid_count = mask.sum()
                print(f"[CSV] Recalculating mid_price for {valid_count}/{len(df)} rows")
                df.loc[mask, "mid_price"] = (df.loc[mask, "best_bid"] + df.loc[mask, "best_ask"]) / 2
            
            # Calculate spread only where both exist
            df["spread"] = df["best_ask"] - df["best_bid"]
            
            # Fill NaN values in spread with 0
            spread_nans = df["spread"].isna().sum()
            if spread_nans > 0:
                print(f"[CSV] Filling {spread_nans} NaN spread values with 0")
            df["spread"] = df["spread"].fillna(0)
            
            print(f"[CSV] Successfully loaded v{version} r{round_num} i{instance}")
            return df
        except Exception as e:
            print(f"[CSV] ERROR loading CSV: {e}")
            st.error(f"Error loading CSV: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @st.cache_data
    def load_params_data(_self, version, round_num, instance):
        """Load parameters data for a specific instance"""
        params_path = _self.base_path / f"v{version}" / f"round_{round_num}" / f"instance_{instance}.params.json"
        if not params_path.exists():
            return None
        try:
            with open(params_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Error loading params: {e}")
            return None
    
    @st.cache_data
    def load_state_data(_self, version, round_num, instance):
        """Load state data for a specific instance"""
        state_path = _self.base_path / f"v{version}" / f"round_{round_num}" / f"instance_{instance}.state.json"
        print(f"[STATE] Loading: {state_path}")
        
        if not state_path.exists():
            print(f"[STATE] File not found: {state_path}")
            return None
        
        try:
            # Check file size and warn if very large
            file_size = state_path.stat().st_size
            print(f"[STATE] File size: {file_size/1024/1024:.1f}MB")
            
            if file_size > 50 * 1024 * 1024:  # 50MB
                st.warning(f"State file is very large ({file_size/1024/1024:.1f}MB). Loading may be slow or fail.")
            
            print(f"[STATE] Reading JSON file...")
            with open(state_path, 'r') as f:
                data = json.load(f)
                
            print(f"[STATE] JSON loaded, type: {type(data)}, keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
            
            # Handle both old and new formats
            if isinstance(data, dict) and 'state_history' in data:
                history_len = len(data['state_history']) if isinstance(data['state_history'], list) else 0
                param_keys = len(data.get('parameters', {}))
                print(f"[STATE] Found state_history with {history_len} entries and {param_keys} parameter keys")
                return data['state_history'], data.get('parameters', {})
            else:
                print(f"[STATE] Using legacy format")
                return data, {}
                
        except json.JSONDecodeError as e:
            print(f"[STATE] JSON decode error: {e}")
            st.error(f"JSON parsing error in state file: {e}")
            st.info("State data is corrupted or incomplete. Bot activity indicators and tick details will not be available.")
            return None
        except MemoryError:
            print(f"[STATE] Memory error - file too large")
            st.error("State file too large to load into memory. Bot activity indicators and tick details will not be available.")
            return None
        except Exception as e:
            print(f"[STATE] ERROR loading state: {e}")
            st.error(f"Error loading state: {e}")
            import traceback
            traceback.print_exc()
            return None

def create_clickable_instance_plots(df, layout_style="grid", state_data=None, bot_filters=None, ma_filters=None, graph_filters=None, vol_filters=None, bid_ask_filters=None, mode_filters=None):
    """Create clickable overview dashboard with selective graphs"""
    
    print(f"[PLOT] Creating plots - df shape: {df.shape if df is not None else 'None'}, has state: {state_data is not None}")
    print(f"[PLOT] Layout: {layout_style}, graphs enabled: {graph_filters}")
    
    # Use full dataset without optimization
    df_plot = df.copy()
    df_plot['original_index'] = df_plot.index
    
    # Check for critical columns
    if df is not None:
        print(f"[PLOT] DataFrame columns: {list(df.columns)[:10]}... (showing first 10 of {len(df.columns)})")
        if 'mid_price' in df.columns:
            nan_count = df['mid_price'].isna().sum()
            if nan_count > 0:
                print(f"[PLOT] WARNING: {nan_count} NaN values in mid_price column")
    
    # Determine which graphs to show and their titles
    all_graphs = [
        ('mid_price', 'Mid Price'),
        ('spread', 'Spread'), 
        ('volatility', 'Volatility'),
        ('position', 'Position'),
        ('total_pnl', 'Total PnL'),
        ('cash_position', 'Cash Position'),
        ('position_value', 'Position Value'),
        ('total_volume_traded', 'Total Volume Traded'),
        ('levels_offered', 'Levels Offered')
    ]
    
    if graph_filters:
        selected_graphs = [(key, title) for key, title in all_graphs if graph_filters.get(key, True)]
    else:
        selected_graphs = all_graphs
    
    num_graphs = len(selected_graphs)
    if num_graphs == 0:
        # Create empty figure if no graphs selected
        fig = go.Figure()
        return fig
    
    # Create subplot titles
    titles = [title for _, title in selected_graphs]
    
    if layout_style == "stacked":
        fig = make_subplots(
            rows=num_graphs, 
            cols=1, 
            shared_xaxes='all',
            shared_yaxes=False,
            subplot_titles=titles,
            vertical_spacing=0.04
        )
        positions = [(i+1, 1) for i in range(num_graphs)]
        height = max(600, num_graphs * 300)  # Dynamic height based on number of graphs
    else:  # grid layout
        cols = 2
        rows = (num_graphs + 1) // 2  # Round up division
        fig = make_subplots(
            rows=rows, 
            cols=cols, 
            shared_xaxes='all',
            shared_yaxes=False,
            subplot_titles=titles,
            vertical_spacing=0.08,
            horizontal_spacing=0.05
        )
        positions = []
        for i in range(num_graphs):
            row = (i // 2) + 1
            col = (i % 2) + 1
            positions.append((row, col))
        height = max(600, rows * 400)  # Dynamic height based on number of rows
    
    print(f"[PLOT] Creating subplots - rows: {rows if layout_style == 'grid' else num_graphs}, cols: {cols if layout_style == 'grid' else 1}")
    print(f"[PLOT] Selected graphs: {[g[0] for g in selected_graphs]}")
    
    # Add traces with click functionality - only for selected graphs
    graph_configs = {
        'mid_price': {
            'data': df_plot['mid_price'],
            'color': 'blue',
            'template': '<b>Mid Price</b><br>Tick: %{x}<br>Value: $%{y:.2f}<br><i>Click to jump to this tick!</i><extra></extra>'
        },
        'spread': {
            'data': df_plot['spread'],
            'color': 'orange', 
            'template': '<b>Spread</b><br>Tick: %{x}<br>Value: %{y:.2f}<br><i>Click to jump to this tick!</i><extra></extra>'
        },
        'volatility': {
            'data': df_plot.get('volatility_20', pd.Series(dtype=float)),
            'color': 'red',
            'template': '<b>Price Volatility (20-period)</b><br>Tick: %{x}<br>Value: %{y:.4f}<br><i>Click to jump to this tick!</i><extra></extra>'
        },
        'cash_position': {
            'data': df_plot['cash_position'],
            'color': 'green',
            'template': '<b>Cash Position</b><br>Tick: %{x}<br>Value: $%{y:,.2f}<br><i>Click to jump to this tick!</i><extra></extra>'
        },
        'position_value': {
            'data': df_plot['position_value'],
            'color': 'darkred',
            'template': '<b>Position Value</b><br>Tick: %{x}<br>Value: $%{y:,.2f}<br><i>Click to jump to this tick!</i><extra></extra>'
        },
        'position': {
            'data': df_plot['position'] if 'position' in df_plot.columns else pd.Series([0] * len(df_plot)),
            'color': 'purple',
            'template': '<b>Position</b><br>Tick: %{x}<br>Position: %{y}<br><i>Click to jump to this tick!</i><extra></extra>'
        },
        'total_pnl': {
            'data': df_plot['total_pnl'],
            'color': 'darkgreen',
            'template': '<b>Total PnL</b><br>Tick: %{x}<br>Value: $%{y:,.2f}<br><i>Click to jump to this tick!</i><extra></extra>'
        },
        'total_volume_traded': {
            'data': df_plot.get('total_volume_traded', pd.Series(dtype=float)),
            'color': 'brown',
            'template': '<b>Total Volume Traded</b><br>Tick: %{x}<br>Volume: %{y:,.0f}<br><i>Click to jump to this tick!</i><extra></extra>'
        },
        'levels_offered': {
            'data': df_plot.get('bid_levels_offered', pd.Series([0] * len(df_plot))),
            'color': 'green',
            'template': '<b>Bid Levels Offered</b><br>Tick: %{x}<br>Bid Levels: %{y}<br><i>Click to jump to this tick!</i><extra></extra>'
        }
    }
    
    for i, (graph_key, title) in enumerate(selected_graphs):
        print(f"[PLOT] Adding trace {i+1}/{len(selected_graphs)}: {graph_key}")
        config = graph_configs[graph_key]
        
        # Check if data is valid
        data_series = config['data']
        if hasattr(data_series, 'isna'):
            nan_count = data_series.isna().sum()
            if nan_count > 0:
                print(f"[PLOT] WARNING: {graph_key} has {nan_count} NaN values")
        
        fig.add_trace(go.Scatter(
            x=df_plot['original_index'], 
            y=config['data'], 
            name=title, 
            line=dict(color=config['color']),
            mode='lines+markers',
            marker=dict(size=4, opacity=0.1),
            hovertemplate=config['template'],
            selected=dict(marker=dict(opacity=1, size=8))
        ), row=positions[i][0], col=positions[i][1])
        print(f"[PLOT] Trace {graph_key} added successfully")
    
    # Add moving averages to Mid Price chart if enabled and Mid Price is selected
    print("[PLOT] Checking for moving averages...")
    mid_price_position = None
    for i, (graph_key, _) in enumerate(selected_graphs):
        if graph_key == 'mid_price':
            mid_price_position = positions[i]
            break
    
    if ma_filters and mid_price_position:
        print(f"[PLOT] Adding moving averages: {ma_filters}")
        ma_colors = {
            5: 'lightblue',
            10: 'orange', 
            20: 'yellow',
            50: 'lightgreen'
        }
        
        for period, show_ma in ma_filters.items():
            if show_ma and len(df_plot) > period:
                # Calculate rolling average
                ma_values = df_plot['mid_price'].rolling(window=period, min_periods=1).mean()
                
                fig.add_trace(go.Scatter(
                    x=df_plot['original_index'],
                    y=ma_values,
                    mode='lines',
                    line=dict(color=ma_colors[period], width=2),
                    name=f'{period}-period MA',
                    hovertemplate=f'<b>{period}-period Moving Average</b><br>' +
                                 'Tick: %{x}<br>' +
                                 'Value: $%{y:.2f}<extra></extra>',
                    showlegend=True
                ), row=mid_price_position[0], col=mid_price_position[1])
    else:
        print("[PLOT] No moving averages to add")
    
    # Add best bid and best ask to mid price chart if enabled and data is available
    print("[PLOT] Checking for bid/ask filters...")
    if mid_price_position and bid_ask_filters and 'best_bid' in df_plot.columns and 'best_ask' in df_plot.columns:
        print(f"[PLOT] Adding bid/ask lines: {bid_ask_filters}")
        # Best bid line
        if bid_ask_filters.get('best_bid', False):
            fig.add_trace(go.Scatter(
                x=df_plot['original_index'],
                y=df_plot['best_bid'],
                mode='lines',
                line=dict(color='green', width=1),
                name='Best Bid',
                hovertemplate='<b>Best Bid</b><br>' +
                             'Tick: %{x}<br>' +
                             'Price: $%{y:.2f}<extra></extra>',
                showlegend=True
            ), row=mid_price_position[0], col=mid_price_position[1])
        
        # Best ask line
        if bid_ask_filters.get('best_ask', False):
            fig.add_trace(go.Scatter(
                x=df_plot['original_index'],
                y=df_plot['best_ask'],
                mode='lines',
                line=dict(color='red', width=1),
                name='Best Ask',
                hovertemplate='<b>Best Ask</b><br>' +
                             'Tick: %{x}<br>' +
                             'Price: $%{y:.2f}<extra></extra>',
                showlegend=True
            ), row=mid_price_position[0], col=mid_price_position[1])
        
        # Our mid line
        if bid_ask_filters.get('our_mid', False) and 'our_mid' in df_plot.columns:
            fig.add_trace(go.Scatter(
                x=df_plot['original_index'],
                y=df_plot['our_mid'],
                mode='lines',
                line=dict(color='gold', width=2, dash='dash'),
                name='Our Mid',
                hovertemplate='<b>Our Mid</b><br>' +
                             'Tick: %{x}<br>' +
                             'Price: $%{y:.2f}<extra></extra>',
                showlegend=True
            ), row=mid_price_position[0], col=mid_price_position[1])
        
        # Our best bid line
        if bid_ask_filters.get('our_best_bid', False) and 'our_best_bid' in df_plot.columns:
            fig.add_trace(go.Scatter(
                x=df_plot['original_index'],
                y=df_plot['our_best_bid'],
                mode='lines',
                line=dict(color='lightgreen', width=1.5),
                name='Our Best Bid',
                hovertemplate='<b>Our Best Bid</b><br>' +
                             'Tick: %{x}<br>' +
                             'Price: $%{y:.2f}<extra></extra>',
                showlegend=True
            ), row=mid_price_position[0], col=mid_price_position[1])
        
        # Our best ask line
        if bid_ask_filters.get('our_best_ask', False) and 'our_best_ask' in df_plot.columns:
            fig.add_trace(go.Scatter(
                x=df_plot['original_index'],
                y=df_plot['our_best_ask'],
                mode='lines',
                line=dict(color='lightcoral', width=1.5),
                name='Our Best Ask',
                hovertemplate='<b>Our Best Ask</b><br>' +
                             'Tick: %{x}<br>' +
                             'Price: $%{y:.2f}<extra></extra>',
                showlegend=True
            ), row=mid_price_position[0], col=mid_price_position[1])
        
        # Transaction count overlay (as markers)
        if bid_ask_filters.get('transaction_count', False) and 'transaction_count' in df_plot.columns:
            # Only show points where transaction count increases
            transaction_increases = df_plot[df_plot['transaction_count'].diff() > 0]
            if not transaction_increases.empty:
                fig.add_trace(go.Scatter(
                    x=transaction_increases['original_index'],
                    y=transaction_increases['mid_price'],
                    mode='markers',
                    marker=dict(
                        symbol='star',
                        size=8,
                        color='purple',
                        line=dict(color='white', width=1)
                    ),
                    name='Transaction',
                    hovertemplate='<b>Transaction!</b><br>' +
                                 'Tick: %{x}<br>' +
                                 'Price: $%{y:.2f}<br>' +
                                 'Count: %{customdata}<extra></extra>',
                    customdata=transaction_increases['transaction_count'],
                    showlegend=True
                ), row=mid_price_position[0], col=mid_price_position[1])
    
    # Add additional volatility periods to volatility chart if enabled
    print("[PLOT] Checking for volatility filters...")
    volatility_position = None
    levels_offered_position = None
    for i, (graph_key, _) in enumerate(selected_graphs):
        if graph_key == 'volatility':
            volatility_position = positions[i]
        elif graph_key == 'levels_offered':
            levels_offered_position = positions[i]
    
    if vol_filters and volatility_position:
        print(f"[PLOT] Adding volatility overlays: {vol_filters}")
        vol_columns = {
            5: 'volatility_5',
            10: 'volatility_10',
            20: 'volatility_20', 
            50: 'volatility_50',
            100: 'volatility_100'
        }
        vol_colors = {
            5: 'red',
            10: 'orange',
            20: 'blue', 
            50: 'green',
            100: 'purple'
        }
        
        for period, show_vol in vol_filters.items():
            if show_vol and len(df_plot) > period:
                col_name = vol_columns.get(period)
                if col_name and col_name in df_plot.columns:
                    # Use bot's true volatility data
                    vol_values = df_plot[col_name]
                else:
                    # Skip if volatility column doesn't exist
                    continue
                
                fig.add_trace(go.Scatter(
                    x=df_plot['original_index'],
                    y=vol_values,
                    mode='lines',
                    line=dict(color=vol_colors[period], width=2),
                    name=f'{period}-period Vol',
                    hovertemplate=f'<b>{period}-period Volatility</b><br>' +
                                 'Tick: %{x}<br>' +
                                 'Value: %{y:.4f}<extra></extra>',
                    showlegend=True
                ), row=volatility_position[0], col=volatility_position[1])
    
    # Add ask levels to levels_offered chart if enabled (bid levels are already added by main graph)
    if levels_offered_position and 'ask_levels_offered' in df_plot.columns:
        fig.add_trace(go.Scatter(
            x=df_plot['original_index'],
            y=df_plot['ask_levels_offered'],
            mode='lines',
            line=dict(color='red', width=2),
            name='Ask Levels Offered',
            hovertemplate='<b>Ask Levels Offered</b><br>' +
                         'Tick: %{x}<br>' +
                         'Levels: %{y}<extra></extra>',
            showlegend=True
        ), row=levels_offered_position[0], col=levels_offered_position[1])
    else:
        print("[PLOT] No levels_offered overlays to add")
    
    # Add trading mode zones to ALL charts if enabled
    print("[PLOT] Checking for mode filters...")
    
    # Skip mode rendering for v8 to prevent hanging
    if 'current_mode' in df_plot.columns:
        unique_modes = df_plot['current_mode'].unique()
        print(f"[PLOT] Unique modes found: {unique_modes[:5]}... (showing first 5)")
        
        # Check if this is v8 data (has DECISION_TREE modes)
        is_v8 = any('DECISION_TREE' in str(mode) for mode in unique_modes if mode)
        if is_v8:
            print("[PLOT] WARNING: V8 data detected - skipping mode rendering to prevent hang")
            mode_filters = None
    
    charts_for_modes = []
    if mode_filters:
        # Add all chart positions - modes will appear on every graph
        charts_for_modes = positions.copy()
    
    if mode_filters and charts_for_modes:
        print(f"[PLOT] Processing mode changes...")
        # Show mode changes as background zones
        if mode_filters.get('mode_changes', False) and 'current_mode' in df_plot.columns:
            print(f"[PLOT] Building mode zones from {len(df_plot)} rows...")
            # Find mode zones (continuous periods of same mode)
            mode_zones = []
            current_zone = None
            
            # Limit processing to prevent hanging
            max_rows = min(len(df_plot), 10000)
            if len(df_plot) > max_rows:
                print(f"[PLOT] WARNING: Limiting mode processing to first {max_rows} rows")
            
            for idx, row in df_plot.head(max_rows).iterrows():
                current_mode = row.get('current_mode', '')
                tick = row['original_index']
                
                if current_zone is None or current_zone['mode'] != current_mode:
                    # Start new zone
                    if current_zone is not None:
                        current_zone['end_tick'] = prev_tick
                        mode_zones.append(current_zone)
                    
                    current_zone = {
                        'mode': current_mode,
                        'start_tick': tick,
                        'end_tick': tick
                    }
                
                prev_tick = tick
            
            # Close final zone
            if current_zone is not None:
                current_zone['end_tick'] = prev_tick
                mode_zones.append(current_zone)
            
            # Add shaded background zones to each chart
            print(f"[PLOT] Adding {len(mode_zones)} mode zones to charts...")
            for zone in mode_zones:
                if zone['mode'] == '':
                    continue
                    
                mode_color = {
                    'MARKET_MAKING': 'rgba(0, 100, 255, 0.1)',     # Light blue
                    'WHALE_FOLLOWING': 'rgba(0, 255, 0, 0.15)',    # Light green
                    'WHALE_LIQUIDATION': 'rgba(255, 0, 0, 0.15)',  # Light red
                    'POSITION_MANAGEMENT': 'rgba(255, 165, 0, 0.1)', # Light orange
                    # V8 decision tree modes
                    'DECISION_TREE_BUY': 'rgba(0, 255, 0, 0.15)',   # Light green
                    'DECISION_TREE_SELL': 'rgba(255, 0, 0, 0.15)',  # Light red
                    'DECISION_TREE_HOLD': 'rgba(128, 128, 128, 0.1)' # Light gray
                }.get(zone['mode'], 'rgba(128, 128, 128, 0.05)')   # Default light gray
                
                # Add zones to each chart position
                for chart_position in charts_for_modes:
                    fig.add_vrect(
                        x0=zone['start_tick'],
                        x1=zone['end_tick'],
                        fillcolor=mode_color,
                        layer="below",
                        line_width=0,
                        row=chart_position[0],
                        col=chart_position[1]
                    )
                
                # Add mode label at zone midpoint only on mid_price chart
                if mid_price_position and zone['end_tick'] - zone['start_tick'] > 100:  # Only label longer zones
                    midpoint = (zone['start_tick'] + zone['end_tick']) / 2
                    
                    fig.add_annotation(
                        x=midpoint,
                        y=df_plot['mid_price'].max() * 0.999,  # Near top of chart
                        text=zone['mode'].replace('_', ' '),
                        showarrow=False,
                        font=dict(size=9, color='gray'),
                        bgcolor='rgba(255, 255, 255, 0.8)',
                        bordercolor='gray',
                        borderwidth=1,
                        row=mid_price_position[0],
                        col=mid_price_position[1]
                    )
        
        # Show whale detection events as vertical lines on mid price
        if mode_filters.get('whale_detection', False) and 'whale_detected' in df_plot.columns:
            whale_events = []
            for idx, row in df_plot.iterrows():
                if row.get('whale_detected', False):
                    whale_events.append({
                        'tick': row['original_index'],
                        'direction': row.get('whale_direction', ''),
                        'mid_price': row['mid_price']
                    })
            
            # Add vertical lines for whale detection on mid price
            for event in whale_events:
                whale_color = 'darkgreen' if event['direction'] == 'LONG' else 'darkred'
                
                fig.add_vline(
                    x=event['tick'],
                    line=dict(color=whale_color, width=1),
                    annotation=dict(
                        text=f"🐋{event['direction'][:1]}",
                        font=dict(size=12, color=whale_color),
                        showarrow=False
                    ),
                    row=mid_price_position[0],
                    col=mid_price_position[1]
                )
    
    # Update layout to enable click events and unified hover
    fig.update_layout(
        hovermode="x",  # Back to simple x hover mode
        height=height,
        showlegend=True,  # Show legend for moving averages
        legend=dict(
            x=1.02, 
            y=1, 
            bgcolor='rgba(255,255,255,0.8)',
            bordercolor='black',
            borderwidth=1
        ),
        title_text="",
        clickmode='event+select',
        dragmode='zoom',  # Default to zoom mode instead of pan
        margin=dict(l=50, r=50, t=50, b=50),  # Smaller margins for performance
    )
    
    # Configure spikes to show across all subplots and constrain axes
    fig.update_xaxes(
        showspikes=True, 
        spikemode='across', 
        spikethickness=1, 
        spikecolor='red',
        spikedash='solid',
        constrain='domain',  # Prevent panning/zooming outside data bounds
        range=[df_plot['original_index'].min(), df_plot['original_index'].max()],  # Set explicit range
        showticklabels=True,  # Show x-axis tick labels
        tickmode='auto',  # Auto-generate tick positions
        title_text="Tick"  # Add x-axis label
    )
    fig.update_yaxes(
        showspikes=False,
        constrain='domain'  # Prevent panning/zooming outside data bounds
    )
    
    # Add custom CSS to change cursor
    fig.update_traces(
        hoverlabel=dict(bgcolor="white", bordercolor="black"),
        line=dict(width=2),  # Slightly thicker lines for better visibility
    )
    
    # Add bot activity indicators on Mid Price chart if state data is available and Mid Price is selected
    if state_data and bot_filters and mid_price_position:
        # Define bot configurations
        bot_configs = {
            'whale': {
                'name': 'Whale',
                'color_long': 'green',
                'color_short': 'red',
                'symbol_long': 'triangle-up',
                'symbol_short': 'triangle-down',
                'size': 15
            },
            'customer_flow1': {
                'name': 'Customer Flow 1',
                'color_long': 'blue',
                'color_short': 'orange',
                'symbol_long': 'circle',
                'symbol_short': 'circle',
                'size': 12
            },
            'customer_flow2': {
                'name': 'Customer Flow 2',
                'color_long': 'purple',
                'color_short': 'pink',
                'symbol_long': 'diamond',
                'symbol_short': 'diamond',
                'size': 12
            },
            'rev': {
                'name': 'Rev',
                'color_long': 'cyan',
                'color_short': 'magenta',
                'symbol_long': 'square',
                'symbol_short': 'square',
                'size': 10
            }
        }
        
        # Track each bot type
        for bot_key, show_bot in bot_filters.items():
            if not show_bot:
                continue
                
            config = bot_configs[bot_key]
            bot_bids_ticks = []
            bot_bids_prices = []
            bot_asks_ticks = []
            bot_asks_prices = []
            
            for tick_idx, tick_data in enumerate(state_data):
                if tick_idx < len(df_plot):  # Make sure we don't go out of bounds
                    order_book = tick_data.get('order_book', {})
                    bids = order_book.get('bids', [])
                    asks = order_book.get('asks', [])
                    
                    # Check for bot in bids (going long)
                    bot_in_bids = False
                    for bid in bids:
                        bot_name = bid.get('bot_name', '').lower()
                        # More flexible matching - check for key parts of the name
                        if (bot_key == 'whale' and 'whale' in bot_name) or \
                           (bot_key == 'customer_flow1' and ('customerflow1' in bot_name or 'customer_flow1' in bot_name)) or \
                           (bot_key == 'customer_flow2' and ('customerflow2' in bot_name or 'customer_flow2' in bot_name)) or \
                           (bot_key == 'rev' and 'rev' in bot_name):
                            bot_in_bids = True
                            break
                    
                    # Check for bot in asks (going short)
                    bot_in_asks = False
                    for ask in asks:
                        bot_name = ask.get('bot_name', '').lower()
                        # More flexible matching - check for key parts of the name
                        if (bot_key == 'whale' and 'whale' in bot_name) or \
                           (bot_key == 'customer_flow1' and ('customerflow1' in bot_name or 'customer_flow1' in bot_name)) or \
                           (bot_key == 'customer_flow2' and ('customerflow2' in bot_name or 'customer_flow2' in bot_name)) or \
                           (bot_key == 'rev' and 'rev' in bot_name):
                            bot_in_asks = True
                            break
                    
                    if bot_in_bids:
                        bot_bids_ticks.append(df_plot.iloc[tick_idx]['original_index'])
                        bot_bids_prices.append(df_plot.iloc[tick_idx]['mid_price'])
                    
                    if bot_in_asks:
                        bot_asks_ticks.append(df_plot.iloc[tick_idx]['original_index'])
                        bot_asks_prices.append(df_plot.iloc[tick_idx]['mid_price'])
            
            # Add long markers
            if bot_bids_ticks:
                fig.add_trace(go.Scatter(
                    x=bot_bids_ticks,
                    y=bot_bids_prices,
                    mode='markers',
                    marker=dict(
                        symbol=config['symbol_long'],
                        size=config['size'],
                        color=config['color_long'],
                        line=dict(color='black', width=1)
                    ),
                    name=f'{config["name"]} Long',
                    hovertemplate=f'<b>{config["name"]} Going Long!</b><br>' +
                                 'Tick: %{x}<br>' +
                                 'Mid Price: $%{y:.2f}<extra></extra>',
                    showlegend=False
                ), row=mid_price_position[0], col=mid_price_position[1])
            
            # Add short markers
            if bot_asks_ticks:
                fig.add_trace(go.Scatter(
                    x=bot_asks_ticks,
                    y=bot_asks_prices,
                    mode='markers',
                    marker=dict(
                        symbol=config['symbol_short'],
                        size=config['size'],
                        color=config['color_short'],
                        line=dict(color='black', width=1)
                    ),
                    name=f'{config["name"]} Short',
                    hovertemplate=f'<b>{config["name"]} Going Short!</b><br>' +
                                 'Tick: %{x}<br>' +
                                 'Mid Price: $%{y:.2f}<extra></extra>',
                    showlegend=False
                ), row=mid_price_position[0], col=mid_price_position[1])
    
    print(f"[PLOT] Figure creation complete - returning figure object")
    return fig

def create_summary_metrics_card(df, params=None):
    """Create a summary metrics card"""
    
    final_pnl = df['total_pnl'].iloc[-1] if len(df) > 0 else 0
    max_position = df['position'].abs().max() if len(df) > 0 else 0
    total_trades = df['position'].diff().ne(0).sum() if len(df) > 1 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Final PnL", f"${final_pnl:,.2f}")
    
    with col2:
        st.metric("Max Position", f"{max_position:.0f}")
    
    with col3:
        st.metric("Total Trades", f"{total_trades:.0f}")
    
    with col4:
        if params:
            bot_version = params.get('bot_version', 'Unknown')
            st.metric("Bot Version", bot_version)
        else:
            avg_spread = df['spread'].mean() if len(df) > 0 else 0
            st.metric("Avg Spread", f"{avg_spread:.2f}")

def show_tick_details(state_data, params, df):
    """Show tick details with slider"""
    
    if not state_data:
        st.warning("No state data available for tick analysis")
        return
    
    st.subheader("Tick Details")
    
    max_tick = len(state_data) - 1
    
    # Initialize session state for tick
    if 'selected_tick' not in st.session_state:
        st.session_state.selected_tick = 0
    
    
    # Precise tick input
    col1, col2 = st.columns([1, 2])
    
    with col1:
        manual_tick = st.number_input(
            "Jump to specific tick:", 
            min_value=0, 
            max_value=max_tick,
            value=st.session_state.selected_tick,
            step=1,
            key="manual_tick_input"
        )
        if manual_tick != st.session_state.selected_tick:
            st.session_state.selected_tick = manual_tick
    
    with col2:
        # Main tick slider - use current session state value
        tick_num = st.slider(
            "Or use slider:", 
            0, 
            max_tick, 
            st.session_state.selected_tick,
            key="main_tick_slider"
        )
        
        # Update session state only if slider moved
        if tick_num != st.session_state.selected_tick:
            st.session_state.selected_tick = tick_num
    
    # Use the current selected tick from session state
    tick_num = st.session_state.selected_tick
    
    if tick_num >= len(state_data):
        st.error("Invalid tick number")
        return
    
    tick_data = state_data[tick_num]
    bot_state = tick_data.get('bot_state', {})
    order_book = tick_data.get('order_book', {})
    trades = tick_data.get('trades_this_tick', [])
    messages = tick_data.get('messages_sent', [])
    
    # Show tick information in metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Tick", f"{tick_num}/{max_tick}")
    
    with col2:
        position = bot_state.get('position', 0)
        st.metric("Position", f"{position:+d}")
    
    with col3:
        cash = bot_state.get('cash_position', 0)
        st.metric("Cash", f"${cash:,.2f}")
    
    with col4:
        mid = bot_state.get('current_mid', 0)
        st.metric("Our Mid", f"${mid:.2f}")
    
    # Show order book, actions, and trades in expandable sections
    col1, col2, col3 = st.columns(3)
    
    with col1:
        with st.expander("Order Book", expanded=True):
            bids = order_book.get('bids', [])
            asks = order_book.get('asks', [])
            
            if asks or bids:
                # Create table-based orderbook display
                
                # Prepare asks data (best ask at top)
                ask_rows = []
                if asks:
                    for ask in asks[:5]:  # Show top 5, best ask at top
                        ask_rows.append({
                            'Bot': ask.get('bot_name', 'Unknown')[:10],  # Truncate for table
                            'Size': ask.get('size', 0),
                            'Price': ask.get('price', 0)
                        })
                
                # Prepare bids data (best bid at top, after spread)
                bid_rows = []
                if bids:
                    for bid in bids[:5]:  # Show top 5 levels
                        bid_rows.append({
                            'Bot': bid.get('bot_name', 'Unknown')[:10],  # Truncate for table
                            'Size': bid.get('size', 0),
                            'Price': bid.get('price', 0)
                        })
                
                # Build combined orderbook table
                orderbook_data = []
                
                # Add asks (top half) - reverse order so highest ask is at top
                for ask_row in reversed(ask_rows):
                    orderbook_data.append({
                        'Bid Bot': '',
                        'Bid Size': '',
                        'Price': f"{ask_row['Price']:.1f}",
                        'Ask Size': ask_row['Size'],
                        'Ask Bot': ask_row['Bot'],
                        'Side': 'ASK'
                    })
                
                # Add spread row
                if asks and bids:
                    spread = asks[0].get('price', 0) - bids[0].get('price', 0)
                    orderbook_data.append({
                        'Bid Bot': '',
                        'Bid Size': '',
                        'Price': f"SPREAD: {spread:.1f}",
                        'Ask Size': '',
                        'Ask Bot': '',
                        'Side': 'SPREAD'
                    })
                
                # Add bids (bottom half)
                for bid_row in bid_rows:
                    orderbook_data.append({
                        'Bid Bot': bid_row['Bot'],
                        'Bid Size': bid_row['Size'],
                        'Price': f"{bid_row['Price']:.1f}",
                        'Ask Size': '',
                        'Ask Bot': '',
                        'Side': 'BID'
                    })
                
                if orderbook_data:
                    df_orderbook = pd.DataFrame(orderbook_data)
                    # Display as table with custom styling - correct column order
                    st.dataframe(
                        df_orderbook[['Bid Bot', 'Bid Size', 'Price', 'Ask Size', 'Ask Bot']],
                        hide_index=True,
                        width='stretch',
                        height=600  # Much taller to prevent clipping
                    )
            else:
                st.text("Empty order book")
    
    with col2:
        with st.expander("Our Actions", expanded=True):
            if messages:
                cancels = [m for m in messages if m.get('type') == 'CANCEL']
                if cancels:
                    st.text(f"Cancelled {len(cancels)} orders")
                
                orders = [m for m in messages if m.get('type') == 'ORDER']
                if orders:
                    st.markdown("**New Orders:**")
                    for order in orders:
                        direction = order.get('direction', 'Unknown')
                        price = order.get('price', 0)
                        size = order.get('size', 0)
                        st.text(f"{direction}: ${price:.1f} x {size}")
            else:
                st.text("No actions this tick")
    
    with col3:
        with st.expander("Trades", expanded=True):
            if trades:
                # Create trades table
                trade_data = []
                for trade in trades:
                    agg_bot = trade.get('agg_bot', 'Unknown')[:8]  # Truncate for table
                    rest_bot = trade.get('rest_bot', 'Unknown')[:8]
                    direction = trade.get('agg_dir', 'Buy/Sell')
                    price = trade.get('price', 0)
                    size = trade.get('size', 0)
                    
                    # Mark if our bot is involved
                    involved = 'NIFTY' in agg_bot or 'NIFTY' in rest_bot
                    marker = "⭐" if involved else ""
                    
                    trade_data.append({
                        'Aggressor': agg_bot,
                        'Direction': direction, 
                        'Price': f"${price:.1f}",
                        'Size': size,
                        'Resting': rest_bot,
                        'Our Trade': marker
                    })
                
                if trade_data:
                    df_trades = pd.DataFrame(trade_data)
                    st.dataframe(
                        df_trades,
                        hide_index=True,
                        width='stretch',
                        height=600  # Much taller to prevent clipping
                    )
            else:
                st.text("No trades this tick")

# Initialize data loader
@st.cache_resource
def get_data_loader():
    return DataLoader()

def create_round_comparison_plots(loader, version, round_num, instances):
    """Create comparison plots across multiple instances in a round"""
    
    if not instances:
        st.warning("No instances available for comparison")
        return
    
    # Load data for all instances with progress indicator
    instance_data = {}
    metrics_summary = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, instance in enumerate(instances):
        # Update progress
        progress = (i + 1) / len(instances)
        progress_bar.progress(progress)
        status_text.text(f"Loading instance {instance} ({i+1}/{len(instances)})...")
        
        df = loader.load_csv_data(version, round_num, instance)
        if df is not None and len(df) > 0:
            instance_data[instance] = df
            
            # Calculate summary metrics
            final_pnl = df['total_pnl'].iloc[-1]
            max_position = df['position'].abs().max()
            avg_spread = df['spread'].mean()
            total_trades = df['position'].diff().ne(0).sum()
            num_ticks = len(df)
            # Remove the extra 1000 that gets added at the start
            adjusted_pnl = final_pnl - 1000
            pnl_per_tick = adjusted_pnl / num_ticks if num_ticks > 0 else 0
            
            metrics_summary.append({
                'instance': instance,
                'final_pnl': final_pnl,
                'max_position': max_position,
                'avg_spread': avg_spread,
                'total_trades': total_trades,
                'num_ticks': num_ticks,
                'pnl_per_tick': pnl_per_tick,
                'win': final_pnl > 0
            })
    
    # Clear progress indicators
    progress_bar.empty()
    status_text.empty()
    
    if not metrics_summary:
        st.warning("No valid data found for any instances")
        return
    
    metrics_df = pd.DataFrame(metrics_summary)
    
    # Create comparison plots
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=("Final PnL by Instance", "Max Position vs PnL", 
                       "Trading Activity vs PnL", "PnL Distribution"),
    )
    
    # Final PnL bar chart
    colors = ['green' if pnl > 0 else 'red' for pnl in metrics_df['final_pnl']]
    fig.add_trace(
        go.Bar(x=metrics_df['instance'], y=metrics_df['final_pnl'], 
               name='Final PnL', marker_color=colors),
        row=1, col=1
    )
    
    # Max Position vs PnL scatter
    fig.add_trace(
        go.Scatter(x=metrics_df['max_position'], y=metrics_df['final_pnl'],
                  mode='markers+text', text=metrics_df['instance'],
                  textposition='top center', name='Position vs PnL'),
        row=1, col=2
    )
    
    # Trading Activity vs PnL scatter
    fig.add_trace(
        go.Scatter(x=metrics_df['total_trades'], y=metrics_df['final_pnl'],
                  mode='markers+text', text=metrics_df['instance'],
                  textposition='top center', name='Trades vs PnL'),
        row=2, col=1
    )
    
    # PnL Distribution histogram
    fig.add_trace(
        go.Histogram(x=metrics_df['final_pnl'], nbinsx=10, name='PnL Distribution'),
        row=2, col=2
    )
    
    fig.update_layout(height=700, showlegend=False, title_text="Round Overview Analysis")
    st.plotly_chart(fig, width='stretch')
    
    # Enhanced Summary Statistics
    st.subheader("Performance Overview")
    
    # Create a summary table instead of metrics
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Key Performance Metrics")
        perf_data = {
            "Metric": ["Win Rate", "Average PnL", "Total PnL", "Avg $/Tick", "Best Instance"],
            "Value": [
                f"{(metrics_df['final_pnl'] > 0).mean() * 100:.1f}%",
                f"${metrics_df['final_pnl'].mean():,.2f}",
                f"${metrics_df['final_pnl'].sum():,.2f}",
                f"${metrics_df['pnl_per_tick'].mean():.2f}" if 'pnl_per_tick' in metrics_df.columns else "N/A",
                f"#{metrics_df.loc[metrics_df['final_pnl'].idxmax(), 'instance']} (${metrics_df['final_pnl'].max():,.2f})"
            ]
        }
        st.dataframe(pd.DataFrame(perf_data), hide_index=True, use_container_width=True)
    
    with col2:
        st.markdown("### Trading Statistics")
        trade_data = {
            "Metric": ["Total Trades", "Avg Trades/Run", "Total Ticks", "Avg Spread", "Full Position %"],
            "Value": [
                f"{metrics_df['total_trades'].sum():,}",
                f"{metrics_df['total_trades'].mean():.0f}",
                f"{metrics_df['num_ticks'].sum():,}" if 'num_ticks' in metrics_df.columns else "N/A",
                f"{metrics_df['avg_spread'].mean():.3f}" if 'avg_spread' in metrics_df.columns else "N/A",
                f"{(metrics_df['max_position'] == 200).mean() * 100:.1f}%"
            ]
        }
        st.dataframe(pd.DataFrame(trade_data), hide_index=True, use_container_width=True)
    
    # Risk & Statistical Analysis
    st.subheader("Risk Analysis")
    
    avg_pnl = metrics_df['final_pnl'].mean()
    pnl_std = metrics_df['final_pnl'].std()
    
    # Create risk metrics table
    risk_data = {
        "Metric": ["PnL Volatility", "Worst Instance", "PnL Range", "Risk-Adj Return", "Median PnL", "25th Percentile", "75th Percentile"],
        "Value": [
            f"${pnl_std:,.2f}",
            f"#{metrics_df.loc[metrics_df['final_pnl'].idxmin(), 'instance']} (${metrics_df['final_pnl'].min():,.2f})",
            f"${metrics_df['final_pnl'].max() - metrics_df['final_pnl'].min():,.2f}",
            f"{avg_pnl / pnl_std:.2f}" if pnl_std > 0 else "∞",
            f"${metrics_df['final_pnl'].median():,.2f}",
            f"${metrics_df['final_pnl'].quantile(0.25):,.2f}",
            f"${metrics_df['final_pnl'].quantile(0.75):,.2f}"
        ]
    }
    st.dataframe(pd.DataFrame(risk_data), hide_index=True, use_container_width=True)
    
    # Remove redundant Trading Behavior section since it's included in main tables
    
    # Remove redundant Performance Distribution section since percentiles are in Risk Analysis
    
    # Strategy Insights
    st.subheader("Strategy Insights")
    
    insights = []
    
    # Performance insights
    if win_rate >= 90:
        insights.append("**Excellent win rate** - Strategy is highly reliable")
    elif win_rate >= 70:
        insights.append("**Good win rate** - Strategy is generally reliable")
    else:
        insights.append("**Low win rate** - Strategy needs improvement")
    
    # Volatility insights
    cv = pnl_std / abs(avg_pnl) if avg_pnl != 0 else float('inf')
    if cv < 0.1:
        insights.append("**Low volatility** - Very consistent performance")
    elif cv < 0.3:
        insights.append("**Moderate volatility** - Reasonably consistent")
    else:
        insights.append("**High volatility** - Performance varies significantly")
    
    # Trading activity insights
    if avg_trades_per_instance > 3000:
        insights.append("**High trading activity** - Very active strategy")
    elif avg_trades_per_instance > 1500:
        insights.append("**Moderate trading activity** - Balanced approach")
    else:
        insights.append("**Low trading activity** - Conservative strategy")
    
    # Position management insights
    if position_consistency > 80:
        insights.append("**Aggressive positioning** - Frequently at max position")
    elif position_consistency > 40:
        insights.append("**Moderate positioning** - Balanced position management")
    else:
        insights.append("**Conservative positioning** - Cautious position sizing")
    
    for insight in insights:
        st.markdown(insight)
    
    # Comparative Performance
    st.subheader("Instance Ranking")
    
    # Sort by PnL and add ranking
    ranked_df = metrics_df.sort_values('final_pnl', ascending=False).reset_index(drop=True)
    ranked_df['rank'] = range(1, len(ranked_df) + 1)
    
    # Create a performance tier classification
    def get_performance_tier(rank, total):
        if rank <= total * 0.2:  # Top 20%
            return "Elite"
        elif rank <= total * 0.4:  # Top 40%
            return "Strong"
        elif rank <= total * 0.6:  # Top 60%
            return "Average"
        elif rank <= total * 0.8:  # Top 80%
            return "Below Average"
        else:
            return "Poor"
    
    ranked_df['tier'] = ranked_df['rank'].apply(lambda r: get_performance_tier(r, len(ranked_df)))
    
    # Display top and bottom performers
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Top Performers**")
        top_performers = ranked_df.head(3)[['rank', 'instance', 'final_pnl', 'tier']]
        for _, row in top_performers.iterrows():
            st.markdown(f"**#{row['rank']}** Instance {row['instance']}: ${row['final_pnl']:,.2f} ({row['tier']})")
    
    with col2:
        if len(ranked_df) > 3:
            st.markdown("**Bottom Performers**")
            bottom_performers = ranked_df.tail(3)[['rank', 'instance', 'final_pnl', 'tier']]
            for _, row in bottom_performers.iterrows():
                st.markdown(f"**#{row['rank']}** Instance {row['instance']}: ${row['final_pnl']:,.2f} ({row['tier']})")
    
    return metrics_df

def main():
    """Main application function"""
    
    print("[APP] Starting NIFTY Trading Explorer v2")
    print(f"[APP] Working directory: {Path.cwd()}")
    
    loader = get_data_loader()
    print(f"[APP] Data loader initialized, base path: {loader.base_path}")
    
    # Sidebar for navigation
    st.sidebar.title("Navigation")
    
    # Get available versions
    versions = loader.get_available_versions()
    if not versions:
        st.error("No trading data found. Please check that the research/raw_data directory exists and contains data.")
        return
    
    # Version selection - default to most recent version
    selected_version = st.sidebar.selectbox(
        "Select Bot Version",
        versions,
        index=len(versions)-1,  # Default to last (most recent) version
        format_func=lambda x: f"Version {x}"
    )
    print(f"[APP] Selected version: {selected_version}")
    
    # Get available rounds for selected version
    rounds = loader.get_available_rounds(selected_version)
    print(f"[APP] Available rounds for v{selected_version}: {rounds}")
    
    if not rounds:
        st.error(f"No rounds found for version {selected_version}")
        print(f"[APP] ERROR: No rounds found for v{selected_version}")
        return
    
    # Round selection - default to most recent round
    selected_round = st.sidebar.selectbox(
        "Select Round",
        rounds,
        index=len(rounds)-1,  # Default to last (most recent) round
        format_func=lambda x: f"Round {x}"
    )
    
    # Get available instances for selected version/round
    instances = loader.get_available_instances(selected_version, selected_round)
    if not instances:
        st.error(f"No instances found for version {selected_version}, round {selected_round}")
        return
    
    # Analysis mode selection - default to Instance Detail
    analysis_mode = st.sidebar.radio(
        "Analysis Mode",
        ["Round Overview", "Instance Detail"],
        index=1  # Default to Instance Detail (second option)
    )
    
    # Main content area
    if analysis_mode == "Round Overview":
        st.header(f"Round Overview: Version {selected_version}, Round {selected_round}")
        
        # Show round comparison with loading status
        with st.spinner(f"Loading {len(instances)} instances for round {selected_round}..."):
            metrics_df = create_round_comparison_plots(loader, selected_version, selected_round, instances)
        
        if metrics_df is not None:
            # Show detailed metrics table
            st.subheader("Detailed Instance Metrics")
            
            # Format the dataframe for display
            display_df = metrics_df.copy()
            display_df['final_pnl'] = display_df['final_pnl'].apply(lambda x: f"${x:,.2f}")
            display_df['avg_spread'] = display_df['avg_spread'].apply(lambda x: f"{x:.2f}")
            display_df['win'] = display_df['win'].apply(lambda x: "Yes" if x else "No")
            
            display_df.columns = ['Instance', 'Final PnL', 'Max Position', 'Avg Spread', 'Total Trades', 'Profitable']
            
            st.dataframe(
                display_df,
                width='stretch',
                hide_index=True
            )
    
    else:  # Instance Detail
        # Instance selection with navigation buttons
        default_instance_idx = 0  # Default to first instance (usually instance 1)
        if 1 in instances:
            default_instance_idx = instances.index(1)
        
        # Initialize session state for instance navigation
        if 'current_instance_idx' not in st.session_state:
            st.session_state.current_instance_idx = default_instance_idx
        
        # Ensure current index is within valid range
        if st.session_state.current_instance_idx >= len(instances):
            st.session_state.current_instance_idx = len(instances) - 1
        elif st.session_state.current_instance_idx < 0:
            st.session_state.current_instance_idx = 0
        
        # Direct selection via selectbox
        selected_instance_idx = st.sidebar.selectbox(
            "Select Instance",
            range(len(instances)),
            index=st.session_state.current_instance_idx,
            format_func=lambda x: f"Instance {instances[x]}",
            key="instance_selector"
        )
        
        # Update session state if user changed selection
        if selected_instance_idx != st.session_state.current_instance_idx:
            st.session_state.current_instance_idx = selected_instance_idx
            st.rerun()
        
        # Navigation buttons below selectbox
        col1, col2, col3 = st.sidebar.columns([1, 2, 1])
        
        with col1:
            if st.button("<", disabled=(st.session_state.current_instance_idx == 0), key="prev_instance"):
                st.session_state.current_instance_idx -= 1
                st.rerun()
        
        with col2:
            st.write("")  # Empty space for alignment
        
        with col3:
            if st.button(">", disabled=(st.session_state.current_instance_idx >= len(instances) - 1), key="next_instance"):
                st.session_state.current_instance_idx += 1
                st.rerun()
        
        selected_instance = instances[st.session_state.current_instance_idx]
        
        st.header(f"Instance Detail: Version {selected_version}, Round {selected_round}, Instance {selected_instance}")
        
        # Show loading progress
        with st.spinner(f"Loading v{selected_version} round {selected_round} instance {selected_instance}..."):
            # Load CSV data
            status_placeholder = st.empty()
            status_placeholder.info("📊 Loading CSV data...")
            df = loader.load_csv_data(selected_version, selected_round, selected_instance)
            
            # Load parameters
            status_placeholder.info("⚙️ Loading bot parameters...")
            params = loader.load_params_data(selected_version, selected_round, selected_instance)
            
            # Load state data (can be large)
            if Path(f"research/raw_data/v{selected_version}/round_{selected_round}/instance_{selected_instance}.state.json").exists():
                file_size = Path(f"research/raw_data/v{selected_version}/round_{selected_round}/instance_{selected_instance}.state.json").stat().st_size / (1024*1024)
                status_placeholder.info(f"📦 Loading state data ({file_size:.1f} MB)...")
            else:
                status_placeholder.info("📦 Checking for state data...")
            
            state_result = loader.load_state_data(selected_version, selected_round, selected_instance)
            if state_result is not None:
                state_data, state_params = state_result
                status_placeholder.success(f"✅ Loaded {len(state_data) if state_data else 0} tick states")
            else:
                state_data, state_params = None, {}
                if Path(f"research/raw_data/v{selected_version}/round_{selected_round}/instance_{selected_instance}.state.json").exists():
                    status_placeholder.warning("⚠️ State data exists but couldn't be loaded")
                else:
                    status_placeholder.info("ℹ️ No state data available (tick details disabled)")
            
            # Clear status after loading
            status_placeholder.empty()
        
        if df is None:
            st.error("Could not load data for the selected instance")
            return
        
        # Merge params if available
        if params is None and state_params:
            params = state_params
        
        # Show summary metrics
        create_summary_metrics_card(df, params)
        
        st.markdown("---")
        
        # Notes section  
        with st.expander("Notes", expanded=False):
            st.subheader("Trading Notes")
            
            # Create notes directory structure
            notes_dir = Path("research/notes")
            version_notes_dir = notes_dir / f"v{selected_version}"
            round_notes_dir = version_notes_dir / f"round_{selected_round}"
            
            # Ensure directories exist
            round_notes_dir.mkdir(parents=True, exist_ok=True)
            
            # File paths for different note types
            version_notes_file = version_notes_dir / "version_notes.md"
            round_notes_file = round_notes_dir / "round_notes.md"  
            instance_notes_file = round_notes_dir / f"instance_{selected_instance}_notes.md"
            
            # Load existing notes
            def load_note_file(file_path):
                try:
                    if file_path.exists():
                        return file_path.read_text()
                    return ""
                except Exception:
                    return ""
            
            # Save note function
            def save_note_file(file_path, content):
                try:
                    file_path.write_text(content)
                    return True
                except Exception:
                    return False
            
            # Arrange text boxes horizontally
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Version notes (persist across all rounds and instances for this version)
                version_notes = load_note_file(version_notes_file)
                version_notes_input = st.text_area(
                    f"Version {selected_version} Notes",
                    value=version_notes,
                    height=150,
                    help="Notes about this bot version (persists across all rounds and instances)",
                    key=f"version_notes_{selected_version}"
                )
            
            with col2:
                # Round notes (persist across all instances in this round)
                round_notes = load_note_file(round_notes_file)
                round_notes_input = st.text_area(
                    f"Round {selected_round} Notes", 
                    value=round_notes,
                    height=150,
                    help="Notes about this specific round (persists across instances)",
                    key=f"round_notes_{selected_version}_{selected_round}"
                )
            
            with col3:
                # Instance notes (specific to this instance only)
                instance_notes = load_note_file(instance_notes_file)
                instance_notes_input = st.text_area(
                    f"Instance {selected_instance} Notes",
                    value=instance_notes, 
                    height=150,
                    help="Notes specific to this instance",
                    key=f"instance_notes_{selected_version}_{selected_round}_{selected_instance}"
                )
            
            # Auto-save notes silently
            if version_notes_input != version_notes:
                save_note_file(version_notes_file, version_notes_input)
                
            if round_notes_input != round_notes:
                save_note_file(round_notes_file, round_notes_input)
                
            if instance_notes_input != instance_notes:
                save_note_file(instance_notes_file, instance_notes_input)
            
            # Instance navigation buttons below the text boxes
            st.subheader("Instance Navigation")
            col1, col2, col3 = st.columns([1, 2, 1])
            
            with col1:
                if st.button("◀ Previous Instance", disabled=(st.session_state.current_instance_idx == 0)):
                    st.session_state.current_instance_idx -= 1
                    st.rerun()
            
            with col2:
                st.write(f"**Current: Instance {selected_instance}**")
            
            with col3:
                if st.button("Next Instance ▶", disabled=(st.session_state.current_instance_idx == len(instances) - 1)):
                    st.session_state.current_instance_idx += 1
                    st.rerun()

        # Load saved settings from localStorage simulation using session state
        if 'settings' not in st.session_state:
            import json  # Import json module for settings loading
            
            # Default settings
            default_settings = {
                'layout_style': 'grid',
                'show_mid_price': True,
                'show_spread': True,
                'show_volatility': True,
                'show_levels_offered': True,
                'show_position': True,
                'show_total_pnl': True,
                'show_cash_pos': True,
                'show_pos_value': False,
                'show_whale': True,
                'show_cf1': False,
                'show_cf2': False,
                'show_rev': False,
                'show_ma5': False,
                'show_ma10': False,
                'show_ma20': False,
                'show_ma50': False,
                'show_best_bid': False,
                'show_best_ask': False,
                'show_our_mid': False,
                'show_mode_changes': False,
                'show_whale_detection': False,
                'show_vol5': False,
                'show_vol10': False,
                'show_vol20': False,
                'show_vol50': False,
                'show_vol100': False
            }
            
            # Try to load saved settings automatically
            settings_file = Path("research/chart_settings.json")
            alt_settings_file = Path.cwd() / "chart_settings.json"
            
            loaded_settings = None
            load_status = "No saved settings found"
            
            for file_path in [settings_file, alt_settings_file]:
                if file_path.exists():
                    try:
                        with open(file_path, 'r') as f:
                            loaded_settings = json.load(f)
                        load_status = f"Auto-loaded settings from: {file_path}"
                        break
                    except Exception as e:
                        load_status = f"Failed to load from {file_path}: {e}"
                        continue  # Try next location
            
            # Use loaded settings if available, otherwise defaults
            if loaded_settings:
                # Merge with defaults to ensure all keys exist
                default_settings.update(loaded_settings)
                st.session_state.settings = default_settings
                st.session_state.load_status = load_status
            else:
                st.session_state.settings = default_settings
                st.session_state.load_status = load_status

        # Chart configuration in expandable sections
        with st.expander("Chart Configuration", expanded=False):
            # Show load status for debugging
            if hasattr(st.session_state, 'load_status'):
                st.info(st.session_state.load_status)
            # Layout selector
            layout_style = st.radio(
                "Chart Layout",
                ["grid", "stacked"],
                index=0 if st.session_state.settings['layout_style'] == 'grid' else 1,
                format_func=lambda x: "Side by Side (Grid)" if x == "grid" else "Stacked Vertically",
                horizontal=True
            )
            st.session_state.settings['layout_style'] = layout_style
            
            # Graph selection toggles
            st.subheader("Select Graphs to Show")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                show_mid_price = st.checkbox("Mid Price", value=st.session_state.settings['show_mid_price'])
                show_spread = st.checkbox("Spread", value=st.session_state.settings['show_spread'])
                show_volatility = st.checkbox("Volatility", value=st.session_state.settings['show_volatility'])
                show_levels_offered = st.checkbox("Levels Offered", value=st.session_state.settings.get('show_levels_offered', True))
            with col2:
                show_position = st.checkbox("Position", value=st.session_state.settings['show_position'])
                show_total_pnl = st.checkbox("Total PnL", value=st.session_state.settings['show_total_pnl'])
            with col3:
                show_cash_pos = st.checkbox("Cash Position", value=st.session_state.settings['show_cash_pos'])
                show_pos_value = st.checkbox("Position Value", value=st.session_state.settings['show_pos_value'])
                show_volume_traded = st.checkbox("Total Volume Traded", value=st.session_state.settings.get('show_volume_traded', False))
            
            # Update settings
            st.session_state.settings.update({
                'show_mid_price': show_mid_price,
                'show_spread': show_spread,
                'show_volatility': show_volatility,
                'show_levels_offered': show_levels_offered,
                'show_position': show_position,
                'show_total_pnl': show_total_pnl,
                'show_cash_pos': show_cash_pos,
                'show_pos_value': show_pos_value,
                'show_volume_traded': show_volume_traded
            })
            
            graph_filters = {
                'mid_price': show_mid_price,
                'spread': show_spread,
                'volatility': show_volatility,
                'levels_offered': show_levels_offered,
                'position': show_position,
                'total_pnl': show_total_pnl,
                'cash_position': show_cash_pos,
                'position_value': show_pos_value,
                'total_volume_traded': show_volume_traded
            }
            
            # Bot activity toggles
            st.subheader("Bot Activity Indicators")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                show_whale = st.checkbox("Show Whale", value=st.session_state.settings['show_whale'])
            with col2:
                show_cf1 = st.checkbox("Show Customer Flow 1", value=st.session_state.settings['show_cf1'])
            with col3:
                show_cf2 = st.checkbox("Show Customer Flow 2", value=st.session_state.settings['show_cf2'])
            with col4:
                show_rev = st.checkbox("Show Rev", value=st.session_state.settings['show_rev'])
            
            # Update settings
            st.session_state.settings.update({
                'show_whale': show_whale,
                'show_cf1': show_cf1,
                'show_cf2': show_cf2,
                'show_rev': show_rev
            })
            
            bot_filters = {
                'whale': show_whale,
                'customer_flow1': show_cf1,
                'customer_flow2': show_cf2,
                'rev': show_rev
            }
            
            # Rolling averages toggles
            st.subheader("Rolling Averages")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                show_ma5 = st.checkbox("5-period MA", value=st.session_state.settings['show_ma5'], key="ma_5")
            with col2:
                show_ma10 = st.checkbox("10-period MA", value=st.session_state.settings['show_ma10'], key="ma_10")
            with col3:
                show_ma20 = st.checkbox("20-period MA", value=st.session_state.settings['show_ma20'], key="ma_20")
            with col4:
                show_ma50 = st.checkbox("50-period MA", value=st.session_state.settings['show_ma50'], key="ma_50")
            
            # Update settings
            st.session_state.settings.update({
                'show_ma5': show_ma5,
                'show_ma10': show_ma10,
                'show_ma20': show_ma20,
                'show_ma50': show_ma50
            })
            
            ma_filters = {
                5: show_ma5,
                10: show_ma10,
                20: show_ma20,
                50: show_ma50
            }
            
            # Price lines toggles
            st.subheader("Price Lines")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                show_best_bid = st.checkbox("Show Best Bid", value=st.session_state.settings['show_best_bid'])
                show_best_ask = st.checkbox("Show Best Ask", value=st.session_state.settings['show_best_ask'])
            with col2:
                show_our_mid = st.checkbox("Show Our Mid", value=st.session_state.settings.get('show_our_mid', False))
                show_our_best_bid = st.checkbox("Show Our Best Bid", value=st.session_state.settings.get('show_our_best_bid', False))
            with col3:
                show_our_best_ask = st.checkbox("Show Our Best Ask", value=st.session_state.settings.get('show_our_best_ask', False))
                show_transaction_count = st.checkbox("Show Transaction Count", value=st.session_state.settings.get('show_transaction_count', False))
            
            # Update settings
            st.session_state.settings.update({
                'show_best_bid': show_best_bid,
                'show_best_ask': show_best_ask,
                'show_our_mid': show_our_mid,
                'show_our_best_bid': show_our_best_bid,
                'show_our_best_ask': show_our_best_ask,
                'show_transaction_count': show_transaction_count,
            })
            
            bid_ask_filters = {
                'best_bid': show_best_bid,
                'best_ask': show_best_ask,
                'our_mid': show_our_mid,
                'our_best_bid': show_our_best_bid,
                'our_best_ask': show_our_best_ask,
                'transaction_count': show_transaction_count
            }
            
            # Trading modes overlay toggles (for v7 data)
            st.subheader("Trading Modes")
            col1, col2 = st.columns(2)
            
            with col1:
                show_mode_changes = st.checkbox("Show Mode Changes", value=st.session_state.settings['show_mode_changes'])
            with col2:
                show_whale_detection = st.checkbox("Show Whale Detection", value=st.session_state.settings['show_whale_detection'])
            
            # Update settings
            st.session_state.settings.update({
                'show_mode_changes': show_mode_changes,
                'show_whale_detection': show_whale_detection
            })
            
            mode_filters = {
                'mode_changes': show_mode_changes,
                'whale_detection': show_whale_detection
            }
            
            # Volatility (rolling standard deviation) toggles
            st.subheader("Rolling Volatility")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                show_vol5 = st.checkbox("5-period Vol", value=st.session_state.settings.get('show_vol5', False), key="vol_5")
                show_vol10 = st.checkbox("10-period Vol", value=st.session_state.settings.get('show_vol10', False), key="vol_10")
            with col2:
                show_vol20 = st.checkbox("20-period Vol", value=st.session_state.settings.get('show_vol20', False), key="vol_20")
                show_vol50 = st.checkbox("50-period Vol", value=st.session_state.settings.get('show_vol50', False), key="vol_50")
            with col3:
                show_vol100 = st.checkbox("100-period Vol", value=st.session_state.settings.get('show_vol100', False), key="vol_100")
            
            # Update settings
            st.session_state.settings.update({
                'show_vol5': show_vol5,
                'show_vol10': show_vol10,
                'show_vol20': show_vol20,
                'show_vol50': show_vol50,
                'show_vol100': show_vol100
            })
            
            vol_filters = {
                5: show_vol5,
                10: show_vol10,
                20: show_vol20,
                50: show_vol50,
                100: show_vol100
            }
            
            # Settings management buttons
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("💾 Save Settings", help="Save current settings as defaults"):
                    try:
                        # Save settings to a file (simulating localStorage)
                        import json
                        settings_file = Path("research/chart_settings.json")
                        settings_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(settings_file, 'w') as f:
                            json.dump(st.session_state.settings, f, indent=2)
                        st.success("Settings saved!")
                        st.write(f"Saved to: {settings_file.absolute()}")
                        st.session_state.load_status = f"Settings saved to: {settings_file}"
                    except Exception as e:
                        st.error(f"Failed to save settings: {e}")
                        st.write(f"Attempted path: {Path('research/chart_settings.json').absolute()}")
                        # Try alternative location
                        try:
                            settings_file = Path.cwd() / "chart_settings.json"
                            with open(settings_file, 'w') as f:
                                json.dump(st.session_state.settings, f, indent=2)
                            st.success(f"Settings saved to alternative location: {settings_file}")
                            st.session_state.load_status = f"Settings saved to: {settings_file}"
                        except Exception as e2:
                            st.error(f"Alternative save also failed: {e2}")
            
            with col2:
                if st.button("📂 Load Settings", help="Load previously saved settings"):
                    # Try primary location first
                    settings_file = Path("research/chart_settings.json")
                    alt_settings_file = Path.cwd() / "chart_settings.json"
                    
                    loaded = False
                    for file_path in [settings_file, alt_settings_file]:
                        if file_path.exists():
                            try:
                                with open(file_path, 'r') as f:
                                    loaded_settings = json.load(f)
                                    st.session_state.settings.update(loaded_settings)
                                st.success(f"Settings loaded from: {file_path}")
                                loaded = True
                                st.rerun()
                                break
                            except Exception as e:
                                st.error(f"Error loading settings from {file_path}: {e}")
                    
                    if not loaded:
                        st.warning("No saved settings found in expected locations")
                        st.write(f"Checked: {settings_file.absolute()}")
                        st.write(f"Checked: {alt_settings_file.absolute()}")
            
            with col3:
                if st.button("🔄 Reset to Defaults", help="Reset all settings to defaults"):
                    st.session_state.settings = {
                        'layout_style': 'grid',
                        'show_mid_price': True,
                        'show_spread': True,
                        'show_volatility': True,
                        'show_levels_offered': True,
                        'show_position': True,
                        'show_total_pnl': True,
                        'show_cash_pos': True,
                        'show_pos_value': False,
                        'show_whale': True,
                        'show_cf1': False,
                        'show_cf2': False,
                        'show_rev': False,
                        'show_ma5': False,
                        'show_ma10': False,
                        'show_ma20': False,
                        'show_ma50': False,
                        'show_best_bid': False,
                        'show_best_ask': False,
                        'show_our_mid': False,
                        'show_our_best_bid': False,
                        'show_our_best_ask': False,
                        'show_transaction_count': False,
                        'show_volume_traded': False,
                        'show_mode_changes': False,
                        'show_whale_detection': False,
                        'show_vol5': False,
                        'show_vol10': False,
                        'show_vol20': False,
                        'show_vol50': False,
                        'show_vol100': False
                    }
                    st.success("Settings reset to defaults!")
                    st.rerun()
        
        # Create layout: graphs and tick details split evenly
        chart_col, details_col = st.columns([1, 1])  # 50/50 split
        
        with chart_col:
            print("[APP] Creating figure...")
            fig = create_clickable_instance_plots(df, layout_style, state_data, bot_filters, ma_filters, graph_filters, vol_filters, bid_ask_filters, mode_filters)
            print(f"[APP] Figure created, type: {type(fig)}")
            
            # Create the plotly chart with click event handling and bigger icons
            print("[APP] Rendering plotly chart...")
            selected_data = st.plotly_chart(
                fig, 
                width='stretch', 
                config={
                    'displayModeBar': True,  # Show toolbar with essential tools only
                    'displaylogo': False,
                    'modeBarButtonsToRemove': ['lasso2d', 'select2d', 'autoScale2d', 'toImage'],  # Remove non-essential tools
                    'modeBarButtonsToKeep': ['zoom2d', 'pan2d', 'zoomIn2d', 'zoomOut2d', 'resetScale2d'],  # Keep zoom, pan, and home
                    'scrollZoom': False,  # Disable scroll zoom
                    'doubleClick': 'reset+autosize',  # Enable double click to reset
                },
                on_select="rerun",
                key="performance_charts"
            )
            
            # Handle click events to jump to selected tick
            if selected_data:
                # Try multiple ways to access the click data
                points = None
                
                # Method 1: Direct dictionary access
                if isinstance(selected_data, dict) and 'selection' in selected_data:
                    selection = selected_data['selection']
                    if 'points' in selection and selection['points']:
                        points = selection['points']
                
                # Method 2: Attribute access
                elif hasattr(selected_data, 'selection') and selected_data.selection:
                    if hasattr(selected_data.selection, 'points') and selected_data.selection.points:
                        points = selected_data.selection.points
                
                # Extract tick from first point
                if points and len(points) > 0:
                    point = points[0]
                    x_val = None
                    
                    # Try different ways to get x value
                    if isinstance(point, dict) and 'x' in point:
                        x_val = point['x']
                    elif hasattr(point, 'x'):
                        x_val = point.x
                    
                    if x_val is not None:
                        clicked_tick = int(x_val)
                        if clicked_tick != st.session_state.get('selected_tick', 0):
                            st.session_state.selected_tick = clicked_tick
        
        with details_col:
            # Show tick details if state data is available
            if state_data:
                show_tick_details(state_data, params, df)
        
        # Show parameters at the bottom if available
        if params:
            st.markdown("---")
            st.subheader("Bot Configuration")
            
            # Display key parameters in columns
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**Strategy Parameters:**")
                st.text(f"Bot Version: {params.get('bot_version', 'Unknown')}")
                st.text(f"Our Spread: {params.get('our_spread', 'N/A')}")
                st.text(f"Fade Rate: {params.get('fade_rate', 'N/A')}")
            
            with col2:
                st.markdown("**Position Management:**")
                st.text(f"Max Levels: {params.get('max_levels', 'N/A')}")
                st.text(f"Size per Level: {params.get('base_size_per_level', 'N/A')}")
                st.text(f"Hard Limit: {params.get('position_hard_limit', 'N/A')}")
            
            with col3:
                st.markdown("**Simulation Settings:**")
                st.text(f"Timestamps: {params.get('num_timestamps', 'N/A')}")
                st.text(f"Instance: {params.get('instance_num', 'N/A')}")
                run_time = params.get('run_timestamp', 'N/A')
                if run_time != 'N/A':
                    # Format timestamp nicely
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(run_time.replace('Z', '+00:00'))
                        run_time = dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        pass
                st.text(f"Run Time: {run_time}")
    
    # Footer
    st.markdown("---")
    st.markdown(
        "*Built with Streamlit and Plotly • "
        "Enhanced with click-to-jump functionality for tick exploration*"
    )

if __name__ == "__main__":
    main()