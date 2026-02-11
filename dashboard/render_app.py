# render_app.py
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
from dashboard_utils import *
from datetime import datetime
from pathlib import Path
import sys
from pathlib import Path

MASTERDATA_DIR = MASTERDATA_DIR = Path("Master_Data")

MASTER_JOBS_PARQUET = MASTERDATA_DIR / "all_jobs_data.parquet"
MASTER_CALLS_PARQUET = MASTERDATA_DIR / "all_call_center_data.parquet"
MASTER_ROI_PARQUET = MASTERDATA_DIR / "all_roi_data.parquet"
MASTER_RPA_PARQUET = MASTERDATA_DIR / "projections_rpa_data.parquet"
MASTER_SALES_PARQUET = MASTERDATA_DIR / "projections_sales_data.parquet"
MASTER_APPTS_PARQUET = MASTERDATA_DIR / "projections_appointments_data.parquet"

# Data will be loaded dynamically via cached functions in dashboard_utils
# This allows automatic cache invalidation when files are updated

# Get last updated timestamp from parquet files
def get_last_updated():
    """Get the most recent modification time of the parquet files"""
    try:
        times = []
        for f in [MASTER_CALLS_PARQUET, MASTER_ROI_PARQUET]:
            if f.exists():
                times.append(f.stat().st_mtime)
        if times:
            latest = max(times)
            dt = datetime.fromtimestamp(latest)
            return dt.strftime("%B %d, %Y at %I:%M %p")
        return "Unknown"
    except:
        return "Unknown"

last_updated = get_last_updated()


# ─── 1. Instantiate Dash App & Layout ─────────────────────────────────────
# Load initial data to generate week options (will reload dynamically in callbacks)
_, calls_df_temp, _ = load_master_data()
week_options = generate_week_options_from_parquet(calls_df_temp)

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
        # Last Updated Timestamp
        html.Div(
            f"Last Updated: {last_updated}",
            style={
                "textAlign": "center",
                "fontSize": "12px",
                "color": "#666",
                "fontStyle": "italic",
                "marginBottom": "20px",
            },
        ),
        # Hidden Week Selector (always defaults to latest week)
        html.Div(
            style={
                "display": "none",  # Hidden - always uses latest week
            },
            children=[
                dcc.Dropdown(
                    id="date-selector",
                    options=week_options,
                    value=week_options[0]["value"],  # Always defaults to latest week
                    clearable=False,
                ),
                # FRANCHISEE SELECTOR REMOVED - JOBS FEATURE REMOVED FROM DASHBOARD
                # # HIDDEN FRANCHISEE SELECTOR (so the callback can hook into it)
                # dcc.Dropdown(
                #     id="franchisee-selector",
                #     options=[{"label": f, "value": f} for f in all_franchisees],
                #     value="All",
                #     clearable=False,
                #     style={
                #         "display": "none"
                #     },  # ← keep it invisible until your update_dashboard renders the real one
                # ),
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
    # FRANCHISEE INPUT REMOVED - JOBS FEATURE REMOVED FROM DASHBOARD
    # Input("franchisee-selector", "value"),
)
def _update_dashboard_wrapper(selected_week):
    # Always pass "All" for selected_franchisee (not used anymore)
    return update_dashboard(selected_week, selected_franchisee="All")


# Call Center Chart Toggle Callback
@app.callback(
    [Output("cc-chart-container", "style"),
     Output("cc-chart-toggle", "children")],
    Input("cc-chart-toggle", "n_clicks")
)
def toggle_cc_chart(n_clicks):
    if n_clicks % 2 == 1:  # Odd clicks = show chart
        return {"display": "block", "marginBottom": "30px"}, "📉 Hide Trend Chart"
    else:  # Even clicks = hide chart
        return {"display": "none", "marginBottom": "30px"}, "📈 Show Trend Chart"


# Call Center Metric Selector Callback
@app.callback(
    Output("cc-line-chart", "figure"),
    Input("cc-metric-selector", "value")
)
def update_cc_chart(selected_metric):
    _, calls_df, _ = load_master_data()
    return build_call_center_line_chart(calls_df, selected_metric)


# Marketing Chart Toggle Callback
@app.callback(
    [Output("mkt-chart-container", "style"),
     Output("mkt-chart-toggle", "children")],
    Input("mkt-chart-toggle", "n_clicks")
)
def toggle_mkt_chart(n_clicks):
    if n_clicks % 2 == 1:  # Odd clicks = show chart
        return {"display": "block", "marginBottom": "30px"}, "📉 Hide Trend Chart"
    else:  # Even clicks = hide chart
        return {"display": "none", "marginBottom": "30px"}, "📈 Show Trend Chart"


# Marketing Metric Selector Callback
@app.callback(
    Output("mkt-line-chart", "figure"),
    Input("mkt-metric-selector", "value")
)
def update_mkt_chart(selected_metric):
    _, _, roi_df = load_master_data()
    return build_marketing_line_chart(roi_df, selected_metric)


# Finance Chart Toggle Callback
@app.callback(
    [Output("fin-chart-container", "style"),
     Output("fin-chart-toggle", "children")],
    Input("fin-chart-toggle", "n_clicks")
)
def toggle_fin_chart(n_clicks):
    if n_clicks % 2 == 1:  # Odd clicks = show chart
        return {"display": "block", "marginBottom": "30px"}, "📉 Hide Trend Chart"
    else:  # Even clicks = hide chart
        return {"display": "none", "marginBottom": "30px"}, "📈 Show Trend Chart"


# Finance Metric Selector Callback
@app.callback(
    Output("fin-line-chart", "figure"),
    Input("fin-metric-selector", "value")
)
def update_fin_chart(selected_metric):
    _, _, roi_df = load_master_data()
    return build_finance_line_chart(roi_df, selected_metric)


# Appointments Forecast Chart Toggle Callback
@app.callback(
    [Output("appts-forecast-container", "style"),
     Output("appts-forecast-toggle", "children")],
    Input("appts-forecast-toggle", "n_clicks")
)
def toggle_appts_forecast(n_clicks):
    if n_clicks % 2 == 1:  # Odd clicks = show chart
        return {"display": "block", "marginBottom": "30px"}, "📉 Hide Forecast Chart"
    else:  # Even clicks = hide chart
        return {"display": "none", "marginBottom": "30px"}, "📈 Show Forecast Chart"


# Revenue Projection Chart Toggle Callback
@app.callback(
    [Output("revenue-projection-container", "style"),
     Output("revenue-projection-toggle", "children")],
    Input("revenue-projection-toggle", "n_clicks")
)
def toggle_revenue_projection(n_clicks):
    if n_clicks % 2 == 1:  # Odd clicks = show chart
        return {"display": "block", "marginBottom": "30px"}, "📉 Hide Revenue Projection"
    else:  # Even clicks = hide chart
        return {"display": "none", "marginBottom": "30px"}, "📈 Show Revenue Projection"


# ─── 3. Run ─────────────────────────────────────────────────────────────────
# FOR TESTING LOCALLY
# if __name__ == "__main__":
#     app.run(debug=True, port=8058)

# UNCOMMENT IF IT IS FOR RENDER
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))  # Render sets PORT dynamically
    app.run(host="0.0.0.0", port=port, debug=True)