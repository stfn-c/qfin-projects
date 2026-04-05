#!/usr/bin/env python3
"""
NIFTY Trader Interactive Explorer

A Streamlit web application for exploring trading bot performance data.
Combines functionality from research_2a_instance_graphs.ipynb, research_3_tick_explorer.ipynb,
and research_2b_correlation_analysis.ipynb into an interactive web interface.

Run with: streamlit run trading_explorer.py
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
        if not csv_path.exists():
            return None
        try:
            df = pd.read_csv(csv_path)
            # Calculate derived metrics
            df["mid_price"] = (df["best_bid"] + df["best_ask"]) / 2
            df["spread"] = df["best_ask"] - df["best_bid"]
            return df
        except Exception as e:
            st.error(f"Error loading CSV: {e}")
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
        if not state_path.exists():
            return None
        try:
            with open(state_path, 'r') as f:
                data = json.load(f)
                # Handle both old and new formats
                if isinstance(data, dict) and 'state_history' in data:
                    return data['state_history'], data.get('parameters', {})
                else:
                    return data, {}
        except Exception as e:
            st.error(f"Error loading state: {e}")
            return None, {}

def create_instance_overview_plots(df, layout_style="grid"):
    """Create the 6-subplot overview dashboard similar to research_2a"""
    
    if layout_style == "stacked":
        fig = make_subplots(
            rows=6, 
            cols=1, 
            shared_xaxes=True,
            subplot_titles=("Mid Price", "Spread", "Cash Position", "Position Value", "Position", "Total PnL"),
            vertical_spacing=0.04
        )
        positions = [(1,1), (2,1), (3,1), (4,1), (5,1), (6,1)]
        height = 1200
    else:  # grid layout
        fig = make_subplots(
            rows=3, 
            cols=2, 
            shared_xaxes=True,
            subplot_titles=("Mid Price", "Spread", "Cash Position", "Position Value", "Position", "Total PnL"),
            vertical_spacing=0.08
        )
        positions = [(1,1), (1,2), (2,1), (2,2), (3,1), (3,2)]
        height = 800
    
    # Mid Price
    fig.add_trace(go.Scatter(x=df.index, y=df['mid_price'], name='Mid Price', line=dict(color='blue')), 
                  row=positions[0][0], col=positions[0][1])
    
    # Spread
    fig.add_trace(go.Scatter(x=df.index, y=df['spread'], name='Spread', line=dict(color='orange')), 
                  row=positions[1][0], col=positions[1][1])
    
    # Cash Position
    fig.add_trace(go.Scatter(x=df.index, y=df['cash_position'], name='Cash Position', line=dict(color='green')), 
                  row=positions[2][0], col=positions[2][1])
    
    # Position Value
    fig.add_trace(go.Scatter(x=df.index, y=df['position_value'], name='Position Value', line=dict(color='red')), 
                  row=positions[3][0], col=positions[3][1])
    
    # Position
    fig.add_trace(go.Scatter(x=df.index, y=df['position'], name='Position', line=dict(color='purple')), 
                  row=positions[4][0], col=positions[4][1])
    
    # Total PnL
    fig.add_trace(go.Scatter(x=df.index, y=df['total_pnl'], name='Total PnL', line=dict(color='darkgreen')), 
                  row=positions[5][0], col=positions[5][1])
    
    # Update layout
    fig.update_layout(
        hovermode='x unified',
        height=height,
        showlegend=False,
        title_text=""
    )
    fig.update_xaxes(showspikes=True, spikemode='across')
    fig.update_yaxes(showspikes=True)
    
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

def create_round_comparison_plots(loader, version, round_num, instances):
    """Create comparison plots across multiple instances in a round"""
    
    if not instances:
        st.warning("No instances available for comparison")
        return
    
    # Load data for all instances
    instance_data = {}
    metrics_summary = []
    
    for instance in instances:
        df = loader.load_csv_data(version, round_num, instance)
        if df is not None and len(df) > 0:
            instance_data[instance] = df
            
            # Calculate summary metrics
            final_pnl = df['total_pnl'].iloc[-1]
            max_position = df['position'].abs().max()
            avg_spread = df['spread'].mean()
            total_trades = df['position'].diff().ne(0).sum()
            
            metrics_summary.append({
                'instance': instance,
                'final_pnl': final_pnl,
                'max_position': max_position,
                'avg_spread': avg_spread,
                'total_trades': total_trades,
                'win': final_pnl > 0
            })
    
    if not metrics_summary:
        st.warning("No valid data found for any instances")
        return
    
    metrics_df = pd.DataFrame(metrics_summary)
    
    # Create comparison plots
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=("Final PnL by Instance", "Max Position vs PnL", 
                       "Trading Activity vs PnL", "PnL Distribution"),
        specs=[[{"secondary_y": False}, {"secondary_y": False}],
               [{"secondary_y": False}, {"secondary_y": False}]]
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
    
    fig.update_xaxes(title_text="Instance", row=1, col=1)
    fig.update_xaxes(title_text="Max Position", row=1, col=2)
    fig.update_xaxes(title_text="Total Trades", row=2, col=1)
    fig.update_xaxes(title_text="Final PnL", row=2, col=2)
    
    fig.update_yaxes(title_text="Final PnL", row=1, col=1)
    fig.update_yaxes(title_text="Final PnL", row=1, col=2)
    fig.update_yaxes(title_text="Final PnL", row=2, col=1)
    fig.update_yaxes(title_text="Count", row=2, col=2)
    
    fig.update_layout(height=700, showlegend=False, title_text="Round Overview Analysis")
    
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False, 'modeBarButtonsToRemove': []})
    
    # Summary statistics
    st.subheader(" Round Summary Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        win_rate = (metrics_df['final_pnl'] > 0).mean() * 100
        st.metric("Win Rate", f"{win_rate:.1f}%")
    
    with col2:
        avg_pnl = metrics_df['final_pnl'].mean()
        st.metric("Average PnL", f"${avg_pnl:,.2f}")
    
    with col3:
        total_pnl = metrics_df['final_pnl'].sum()
        st.metric("Total PnL", f"${total_pnl:,.2f}")
    
    with col4:
        best_instance = metrics_df.loc[metrics_df['final_pnl'].idxmax(), 'instance']
        best_pnl = metrics_df['final_pnl'].max()
        st.metric("Best Instance", f"#{best_instance} (${best_pnl:,.2f})")
    
    return metrics_df

def show_tick_explorer(state_data, params, df):
    """Show the tick-by-tick explorer similar to research_3"""
    
    if not state_data:
        st.warning("No state data available for tick-by-tick analysis")
        return
    
    st.subheader("Tick-by-Tick Explorer")
    
    max_tick = len(state_data) - 1
    
    # Create tick navigation controls
    col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
    
    # Initialize session state for tick
    if 'current_tick' not in st.session_state:
        st.session_state.current_tick = 0
    
    with col1:
        if st.button("First", key="first_tick"):
            st.session_state.current_tick = 0
    
    with col2:
        if st.button("Prev", key="prev_tick"):
            st.session_state.current_tick = max(0, st.session_state.current_tick - 1)
    
    with col3:
        # Tick selector with input box for jumping to specific tick
        tick_input = st.number_input(
            f"Jump to tick (0-{max_tick})", 
            min_value=0, 
            max_value=max_tick, 
            value=st.session_state.current_tick,
            key="tick_input"
        )
        if tick_input != st.session_state.current_tick:
            st.session_state.current_tick = tick_input
    
    with col4:
        if st.button("Next", key="next_tick"):
            st.session_state.current_tick = min(max_tick, st.session_state.current_tick + 1)
    
    with col5:
        if st.button("Last", key="last_tick"):
            st.session_state.current_tick = max_tick
    
    tick_num = st.session_state.current_tick
    
    # Show current tick position
    st.progress(tick_num / max_tick, text=f"Tick {tick_num} of {max_tick}")
    
    if tick_num >= len(state_data):
        st.error("Invalid tick number")
        return
    
    tick_data = state_data[tick_num]
    bot_state = tick_data.get('bot_state', {})
    order_book = tick_data.get('order_book', {})
    trades = tick_data.get('trades_this_tick', [])
    messages = tick_data.get('messages_sent', [])
    
    # Tick information
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
    
    st.markdown("---")
    
    # Create three columns for the tick analysis
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        st.markdown("### 📖 Order Book")
        
        # Display order book
        bids = order_book.get('bids', [])
        asks = order_book.get('asks', [])
        
        if asks or bids:
            # Show asks (reversed so best is at bottom)
            if asks:
                st.markdown("**Asks:**")
                for ask in reversed(asks[:5]):  # Top 5 levels
                    owner = '[MM]' if 'MM' in ask.get('bot_name', '') else '[P]'
                    price = ask.get('price', 0)
                    size = ask.get('size', 0)
                    bot_name = ask.get('bot_name', 'Unknown')
                    st.text(f"  {price:7.1f} x {size:3d}  {owner} {bot_name}")
            
            # Show spread
            if asks and bids:
                spread = asks[0].get('price', 0) - bids[0].get('price', 0)
                st.markdown(f"**Spread: {spread:.1f}**")
            
            # Show bids
            if bids:
                st.markdown("**Bids:**")
                for bid in bids[:5]:  # Top 5 levels
                    owner = '[MM]' if 'MM' in bid.get('bot_name', '') else '[P]'
                    price = bid.get('price', 0)
                    size = bid.get('size', 0)
                    bot_name = bid.get('bot_name', 'Unknown')
                    st.text(f"  {owner} {bot_name} {size:3d} x {price:7.1f}")
        else:
            st.text("(empty order book)")
    
    with col2:
        st.markdown("###  Our Actions")
        
        if messages:
            # Show cancellations
            cancels = [m for m in messages if m.get('type') == 'CANCEL']
            if cancels:
                st.text(f"Cancelled {len(cancels)} orders")
            
            # Show new orders
            orders = [m for m in messages if m.get('type') == 'ORDER']
            if orders:
                st.markdown("**New Orders:**")
                
                # Separate buys and sells
                buys = [o for o in orders if o.get('direction') == 'Buy']
                sells = [o for o in orders if o.get('direction') == 'Sell']
                
                # Show sells first (asks)
                if sells:
                    for sell in sorted(sells, key=lambda x: x.get('price', 0), reverse=True):
                        price = sell.get('price', 0)
                        size = sell.get('size', 0)
                        st.text(f"  ASK  ${price:7.1f} x {size:2d}")
                
                if buys and sells:
                    st.text("  ─────────────────")
                
                # Show buys (bids)
                if buys:
                    for buy in sorted(buys, key=lambda x: x.get('price', 0), reverse=True):
                        price = buy.get('price', 0)
                        size = buy.get('size', 0)
                        st.text(f"  BID  {size:2d} x ${price:7.1f}")
        else:
            st.text("No actions this tick")
    
    with col3:
        st.markdown("### 💼 Trades Executed")
        
        if trades:
            st.markdown(f"**{len(trades)} trade(s):**")
            for trade in trades:
                agg_bot = trade.get('agg_bot', 'Unknown')
                rest_bot = trade.get('rest_bot', 'Unknown')
                direction = trade.get('agg_dir', 'Unknown')
                price = trade.get('price', 0)
                size = trade.get('size', 0)
                
                # Check if we're involved
                involved = 'NIFTY' in agg_bot or 'NIFTY' in rest_bot
                marker = "*" if involved else " "
                arrow = "->" if direction == "Buy" else "<-"
                
                st.text(f"{marker} ${price:.1f} x {size:2d}")
                st.text(f"  {agg_bot} {arrow} {rest_bot}")
        else:
            st.text("No trades this tick")

# Initialize data loader
@st.cache_resource
def get_data_loader():
    return DataLoader()

def main():
    """Main application function"""
    
    loader = get_data_loader()
    
    # Sidebar for navigation
    st.sidebar.title("Navigation")
    
    # Get available versions
    versions = loader.get_available_versions()
    if not versions:
        st.error("No trading data found. Please check that the research/raw_data directory exists and contains data.")
        return
    
    # Version selection
    selected_version = st.sidebar.selectbox(
        "Select Bot Version",
        versions,
        format_func=lambda x: f"Version {x}"
    )
    
    # Get available rounds for selected version
    rounds = loader.get_available_rounds(selected_version)
    if not rounds:
        st.error(f"No rounds found for version {selected_version}")
        return
    
    # Round selection
    selected_round = st.sidebar.selectbox(
        "Select Round",
        rounds,
        format_func=lambda x: f"Round {x}"
    )
    
    # Get available instances for selected version/round
    instances = loader.get_available_instances(selected_version, selected_round)
    if not instances:
        st.error(f"No instances found for version {selected_version}, round {selected_round}")
        return
    
    # Analysis mode selection
    analysis_mode = st.sidebar.radio(
        "Analysis Mode",
        ["Round Overview", "Instance Detail"]
    )
    
    # Main content area
    if analysis_mode == "Round Overview":
        st.header(f" Round Overview: Version {selected_version}, Round {selected_round}")
        
        # Show round comparison
        metrics_df = create_round_comparison_plots(loader, selected_version, selected_round, instances)
        
        if metrics_df is not None:
            # Show detailed metrics table
            st.subheader(" Detailed Instance Metrics")
            
            # Format the dataframe for display
            display_df = metrics_df.copy()
            display_df['final_pnl'] = display_df['final_pnl'].apply(lambda x: f"${x:,.2f}")
            display_df['avg_spread'] = display_df['avg_spread'].apply(lambda x: f"{x:.2f}")
            display_df['win'] = display_df['win'].apply(lambda x: "Yes" if x else "No")
            
            display_df.columns = ['Instance', 'Final PnL', 'Max Position', 'Avg Spread', 'Total Trades', 'Profitable']
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )
    
    else:  # Instance Detail
        # Instance selection
        selected_instance = st.sidebar.selectbox(
            "Select Instance",
            instances,
            format_func=lambda x: f"Instance {x}"
        )
        
        st.header(f" Instance Detail: Version {selected_version}, Round {selected_round}, Instance {selected_instance}")
        
        # Load data for the selected instance
        df = loader.load_csv_data(selected_version, selected_round, selected_instance)
        params = loader.load_params_data(selected_version, selected_round, selected_instance)
        state_data, state_params = loader.load_state_data(selected_version, selected_round, selected_instance)
        
        if df is None:
            st.error("Could not load data for the selected instance")
            return
        
        # Merge params if available
        if params is None and state_params:
            params = state_params
        
        # Show summary metrics
        create_summary_metrics_card(df, params)
        
        st.markdown("---")
        
        # Layout selector
        layout_style = st.radio(
            "Chart Layout",
            ["grid", "stacked"],
            format_func=lambda x: "Side by Side (Grid)" if x == "grid" else "Stacked Vertically",
            horizontal=True
        )
        
        # Show main plots
        st.subheader("Performance Overview")
        fig = create_instance_overview_plots(df, layout_style)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False, 'modeBarButtonsToRemove': []})
        
        # Show parameters if available
        if params:
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
        
        # Show tick details if state data is available
        if state_data:
            st.markdown("---")
            show_tick_details(state_data, params, df)
    
    # Footer
    st.markdown("---")
    st.markdown(
        "*Built with Streamlit and Plotly • "
        "Combines analysis from research_2a_instance_graphs.ipynb, "
        "research_3_tick_explorer.ipynb, and research_2b_correlation_analysis.ipynb*"
    )

if __name__ == "__main__":
    main()