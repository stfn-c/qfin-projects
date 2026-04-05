#!/bin/bash

# NIFTY Trading Bot Explorer Launch Script
# 
# This script launches the Streamlit web application for exploring trading bot data.

echo "🚀 Launching NIFTY Trading Bot Interactive Explorer..."
echo "📊 This will open a web browser with your trading analysis dashboard"
echo ""
echo "Features included:"
echo "  • Version and round selection"
echo "  • Round overview with comparison graphs"
echo "  • Instance detail view with 6-plot dashboard"
echo "  • Tick-by-tick explorer with orderbook display"
echo "  • Interactive hover functionality"
echo ""
echo "Press Ctrl+C to stop the server when you're done."
echo ""

# Launch Streamlit
python -m streamlit run trading_explorer_v2.py