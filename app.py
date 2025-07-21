# testing_dashboard.ipynb
import re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import date
from datetime import timedelta
import math
import os
from dash import Dash, dcc, html, dash_table
from dash.dependencies import Input, Output
from data_fetcher import *
from dashboard_utils import *
from datetime import datetime

# Load in Data
MASTER_JOBS_PARQUET = Path("MasterData/all_jobs_data.parquet")
MASTER_CALLS_PARQUET = Path("MasterData/all_call_center_data.parquet") # Need to add in Marketing
MASTER_ROI_PARQUET = Path("MasterData/all_roi_data.parquet")

jobs_all_df = pd.read_parquet(MASTER_JOBS_PARQUET)
calls_all_df = pd.read_parquet(MASTER_CALLS_PARQUET)
roi_all_df = pd.read_parquet(MASTER_ROI_PARQUET)

# Check if Dashboard Needs Updated Data
# jobs_all_df, calls_all_df, roi_all_df = fetch_and_append_week_if_needed(jobs_all_df, calls_all_df, roi_all_df) # Need to add in marketing to this function


# ─── 1. Instantiate Dash App & Layout ─────────────────────────────────────
all_franchisees = ["All"] + sorted(jobs_all_df["Franchisee"].dropna().unique())
week_options = generate_week_options_from_parquet(jobs_all_df)

app = Dash(__name__, suppress_callback_exceptions=True)

server = app.server
app.title = "Art of Drawers Dashboard"

app.layout = html.Div(
    style={
        "fontFamily": "Segoe UI, sans-serif",
        "margin": "0 auto",
        "maxWidth": "1200px",
        "backgroundColor": "#FFFFFF",
    },
    children=[
        # Title
        html.H1(
            "AoD Weekly Report",
            style={
                "marginTop": "24px",
                "marginBottom": "10px",
                "color": "#2C3E70",
                "textAlign": "center",
            },
        ),
        # Select Week Drop Down
        html.Div(
            style={
                "display": "flex",
                "flexDirection": "column",
                "alignItems": "center",
                "marginBottom": "14px",
            },
            children=[
                html.Label(
                    "Select Date Range:",
                    style={
                        "fontSize": "14px",
                        "color": "gray",
                        "fontStyle": "italic",
                        "marginBottom": "6px",
                    },
                ),
                dcc.Dropdown(
                    id="date-selector",
                    options=week_options,
                    value=week_options[0]["value"],
                    placeholder="Select Week",
                    clearable=False,
                    style={
                        "width": "240px",
                        "fontFamily": "Segoe UI, sans-serif",
                        "textAlign": "center",
                        "fontSize": "14px",
                        "borderRadius": "4px",
                        "border": "1px solid #2C3E70",
                    },
                ),
                # HIDDEN FRANCHISEE SELECTOR (so the callback can hook into it)
                dcc.Dropdown(
                    id="franchisee-selector",
                    options=[{"label": f, "value": f} for f in all_franchisees],
                    value="All",
                    clearable=False,
                    style={
                        "display": "none"
                    },  # ← keep it invisible until your update_dashboard renders the real one
                ),
            ],
        ),
        # Franchisee selector + loading wrapper
        html.Div(
            style={"display": "flex", "flexDirection": "column"},
            children=[
                # this Loading will wrap ALL of our dynamic content
                dcc.Loading(
                    id=" -dashboard",
                    type="circle",
                    children=html.Div(
                        id="dashboard-content", style={"minHeight": "800px"}
                    ),
                ),
            ],
        ),
    ],
)


# ─── 2. Callbacks ───────────────────────────────────────────────────────────
@app.callback(
    Output("dashboard-content", "children"),
    Input("date-selector", "value"),
    Input("franchisee-selector", "value"),
)
def _update_dashboard_wrapper(selected_week, selected_franchisee):
    return update_dashboard(selected_week, selected_franchisee)


# ─── 3. Run ─────────────────────────────────────────────────────────────────
# if __name__ == "__main__":
#     app.run(debug=True, port=8058)

# UNCOMMENT IF IT IS APP.PY
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))  # Render sets PORT dynamically
    app.run(host="0.0.0.0", port=port, debug=True)