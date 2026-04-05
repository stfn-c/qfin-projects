import pandas as pd
import plotly.express as px

# Define the path to the CSV file
csv_file_path = (
    "./fuzzing_pnl_summary.csv"
)

# Read the CSV data from the file, skipping the first row (header)
df = pd.read_csv(csv_file_path, skiprows=1)

# Rename columns for clarity if necessary (assuming original names might be just indices after skipping header)
# Or, if the C++ output already has headers that pandas can pick up after skipping the first line,
# you might need to adjust `skiprows` or use `header=0` or `header=1` depending on the exact CSV structure.
# For now, let's assume the C++ output doesn't have a useful header in the *second* line and we assign names.
# If the file *does* have a proper header in the second line that pandas picks up, this renaming might be redundant or incorrect.
# Let's assume the columns are in the order: RollingAvgWindow, PositiveDiffMAThreshold, NegativeDiffMAThreshold, FixedOrderQuantity, PnL
df.columns = [
    "RollingAvgWindow",
    "PositiveDiffMAThreshold",
    "NegativeDiffMAThreshold",
    "FixedOrderQuantity",
    "PnL",
]


# Create an interactive 3D scatter plot
fig = px.scatter_3d(
    df,
    x="PositiveDiffMAThreshold",
    y="NegativeDiffMAThreshold",
    z="PnL",
    color="PnL",  # Color points by PnL
    hover_data=["RollingAvgWindow", "FixedOrderQuantity", "PnL"],  # Show these on hover
    title="3D Interactive Plot of Fuzzing PnL Results",
)

# Update layout for better axis labels (optional, but good practice)
fig.update_layout(
    scene=dict(
        xaxis_title="Positive Difference MA Threshold",
        yaxis_title="Negative Difference MA Threshold",
        zaxis_title="PnL",
    )
)

# Show the plot
fig.show()

# If you want to save it to an HTML file:
# fig.write_html("fuzzing_pnl_plot_interactive.html")
