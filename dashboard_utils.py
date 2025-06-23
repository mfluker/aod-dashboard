import math
import re
from datetime import datetime, date, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from dash import dash_table, dcc, html
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

from datetime import datetime, timedelta
from typing import Optional


def get_delta_percent(current, previous):
    if previous in [None, 0]:
        return None
    return ((current - previous) / previous) * 100


def format_with_change(current: float, previous: float) -> str:
    """
    Returns formatted string with % change tooltip: "123 (↑12.5%)" or "95 (↓8.1%)"
    """
    if previous in [None, 0]:
        return f"{int(current)}"

    delta = ((current - previous) / previous) * 100
    arrow = "↑" if delta > 0 else "↓"
    
    return f"{int(current)} ({arrow}{abs(delta):.1f}%)"


def percent_to_color(delta: float | None) -> str:
    if delta is None:
        return "#999"  # neutral gray

    # Improved readability: avoid ultra-light shades
    if delta >= 50:
        return "#1b5e20"  # dark green
    elif delta >= 25:
        return "#388e3c"  # strong green
    elif delta >= 10:
        return "#66bb6a"  # medium green
    elif delta >= 0:
        return "#81c784"  # light green — but still visible
    elif delta > -10:
        return "#e57373"  # light red, readable
    elif delta > -25:
        return "#ef5350"  # medium red
    elif delta > -50:
        return "#c62828"  # strong red
    else:
        return "#b71c1c"  # dark red


def generate_week_options_from_parquet(jobs_df):
    weeks = (
        jobs_df[["week_start", "week_end"]]
        .drop_duplicates()
        .sort_values("week_start", ascending=False)
    )
    options = []
    for _, row in weeks.iterrows():
        ws = pd.to_datetime(row["week_start"]).date()
        we = pd.to_datetime(row["week_end"]).date()
        label = f"{ws.strftime('%B')} {ws.day} – {we.day}, {we.year}"
        value = f"{ws.strftime('%m/%d/%Y')}|{we.strftime('%m/%d/%Y')}"
        options.append({"label": label, "value": value})
    return options


def make_status_figure(jobs_df: pd.DataFrame, selected_franchisee: str, historical_lookup: dict) -> go.Figure:
    """
    Build and return the stacked-bar + totals figure for the given franchisee.
    """

    status_order = [
        "Measurement Appointment Scheduled",
        "Measurement Approved",
        "Submitted to Manufacturing Partner",
        "Order Shipped",
        "Order Received",
        "Install Scheduled",
        "Installed",
        "Complete",
    ]

    # 1) Filter
    df_f = (
        jobs_df
        if selected_franchisee == "All"
        else jobs_df[jobs_df["Franchisee"] == selected_franchisee]
    )

    # 2) Aggregate
    grouped = (
        df_f.groupby(["Status", "Order Type"], observed=False)
        .agg(Count=("ID", "nunique"))
        .reset_index()
    )
    grouped["Status"] = pd.Categorical(
        grouped["Status"], categories=status_order, ordered=True
    )

    # 3) Fill missing combos
    order_types = ["New", "Claim", "Reorder"]
    combos = pd.MultiIndex.from_product(
        [status_order, order_types], names=["Status", "Order Type"]
    )
    grouped = (
        grouped.set_index(["Status", "Order Type"])
        .reindex(combos, fill_value=0)
        .reset_index()
    )

    # 4) Compute totals
    totals = (
        grouped.groupby("Status", observed=False)["Count"]
        .sum()
        .reindex(status_order)
        .reset_index()
    )
    raw_max = int(totals["Count"].max()) if not totals.empty else 0
    top = math.ceil(raw_max / 5) * 5 * 1.1 if raw_max % 5 else raw_max * 1.1
    top = int(math.ceil(top))

    # 5) Build manually with go.Figure()
    fig = go.Figure()

    bar_colors = {"New": "#2C3E70", "Claim": "#a1c4bd", "Reorder": "#bbbfbf"}

    for ot in order_types:
        df_trace = grouped[grouped["Order Type"] == ot]
        fig.add_trace(
            go.Bar(
                x=df_trace["Status"],
                y=df_trace["Count"],
                name=ot,
                marker_color=bar_colors.get(ot, "#888"),
                customdata=[[ot]] * len(df_trace),
                hovertemplate="<b>%{x}</b><br>Type: %{customdata[0]}<br>Count: %{y}<extra></extra>",
                uid=ot,
                hoverlabel=dict(
                    bgcolor=bar_colors.get(ot, "#888"),
                    font_size=14,
                    font_color="white",  # white looks best on these
                ),
            )
        )

    hover_texts = []
    for s, c in zip(totals["Status"], totals["Count"]):
        if selected_franchisee == "All":
            prev = historical_lookup.get(s)
            # if prev is None:
            #     hover_texts.append(
            #         f"<b>{s}</b><br><b>1 Wk Ago:</b> –<extra></extra>"
            #     )
            # else:
            #     delta_color = percent_to_color(get_delta_percent(c, prev))
            #     delta_text = format_with_change(c, prev).split()[-1]
            #     hover_texts.append(
            #         f"<b>{s}</b><br><b>1 Wk Ago:</b> {int(prev)} "
            #         f"<span style='color:{delta_color}'>{delta_text}</span><extra></extra>"
            #     )
            if prev is None or prev == 0:
                hover_texts.append(f"<b>{s}</b><br><b>1 Wk Ago:</b> –<extra></extra>")
            else:
                delta = get_delta_percent(c, prev)
                delta_text = format_with_change(c, prev).split()[-1]
                color = percent_to_color(delta)
                hover_texts.append(
                    f"<b>{s}</b><br><b>1 Wk Ago:</b> {int(prev)} "
                    f"<span style='color:{color}'>{delta_text}</span><extra></extra>"
                )
        else:
            hover_texts.append(f"<b>{s}</b><br><b>Count:</b> {int(c)}<extra></extra>")

    # 6) Add total labels as pixel-aligned annotations
    for x, y, text in zip(totals["Status"], totals["Count"], totals["Count"]):
        fig.add_annotation(
            x=x,
            y=y,
            text=str(int(text)),
            showarrow=False,
            yanchor="bottom",
            yshift=2,  # shift label 2 pixels above bar
            font=dict(color="#2C3E70", size=14),
            align="center",
        )

    if selected_franchisee == "All":
        fig.add_trace(
            go.Scatter(
                x=totals["Status"],
                y=totals["Count"] + 4,  # ← ALIGN to true count, not offset
                mode="markers",
                marker=dict(size=30, color="rgba(0,0,0,0)"),  # transparent
                hovertemplate=hover_texts,
                showlegend=False,
                hoverlabel=dict(
                    bgcolor="white",
                    font_size=14,
                    font_color="black",
                    bordercolor="#2C3E70",
                ),
            )
        )

    fig.update_layout(
        uirevision="static-axes",
        plot_bgcolor="white",
        paper_bgcolor="white",
        hoverlabel=dict(
            bgcolor="white",  # Background color
            font_size=14,  # Font size
            font_color="black",  # Text color
            bordercolor="#2C3E70",  # Optional: adds a subtle border for separation
        ),
        barmode="stack",
        height=500,
        margin=dict(t=100, b=30, l=40, r=40),
        font=dict(
            family="Segoe UI, sans-serif", size=14, color="#2C3E70"
        ),  # Global font for axis, legend, etc.
        legend=dict(orientation="h", y=1.05, x=1, xanchor="right"),
        title=dict(
            text=f"Project Status by Order Type — {selected_franchisee}",
            font=dict(
                family="Segoe UI, sans-serif",
                size=20,  # Match H1-style prominence
                color="#2C3E70",
            ),
        ),
    )

    # 8) Shorten labels
    def shorten(lbl):
        lbl = re.sub(r"(?i)measurement[s]?", "Meas.", lbl)
        lbl = re.sub(r"(?i)manufacturing( partner)?", "MFG", lbl)
        return re.sub(r"(?i)appointment[s]?", "Appt.", lbl)

    # 9) Axes
    fig.update_xaxes(
        ticktext=[shorten(s) for s in status_order],
        tickvals=status_order,
        showticklabels=True,
        ticks="outside",
        tickangle=-45,
        showline=True,
        linecolor="#2C3E70",
        autorange=False,
        fixedrange=True,
        range=[-0.5, len(status_order) - 0.5],
    )

    fig.update_yaxes(
        range=[0, top],
        autorange=False,
        rangemode="tozero",
        showticklabels=False,
        ticks="",
        fixedrange=True,
    )

    return fig


def get_last_full_week(for_date: date = None) -> tuple[str, str]:
    """
    Return the most recent full Sunday–Saturday week *before* the given date.
    If no date is passed, use today.
    Output is in (MM/DD/YYYY, MM/DD/YYYY) format.
    """
    if for_date is None:
        for_date = date.today()

    # Go to the previous Sunday
    days_since_sunday = (for_date.weekday() + 1) % 7
    last_sunday = for_date - timedelta(days=days_since_sunday + 7)
    last_saturday = last_sunday + timedelta(days=6)

    return last_sunday.strftime("%m/%d/%Y"), last_saturday.strftime("%m/%d/%Y")


def parquet_has_week(df: pd.DataFrame, start: str, end: str) -> bool:

    return ((df["week_start"] == start) & (df["week_end"] == end)).any()


def fetch_and_append_week_if_needed(jobs_df: pd.DataFrame, calls_df: pd.DataFrame):
    jobs_path = Path("MasterData/all_jobs_data.parquet")
    calls_path = Path("MasterData/all_call_center_data.parquet")

    start, end = get_last_full_week(date.today())

    if not parquet_has_week(jobs_df, start, end):
        print(f"📦 Adding Jobs data for {start} – {end}...")
        new_jobs = load_jobs_data(start, end)
        new_jobs["week_start"] = start
        new_jobs["week_end"] = end
        new_jobs["ID"] = new_jobs["ID"].astype(str)
        jobs_df = pd.concat([jobs_df, new_jobs], ignore_index=True)
        jobs_df.to_parquet(jobs_path, index=False)
    else:
        print(f"✅ Jobs data for {start} – {end} already present.")

    if not parquet_has_week(calls_df, start, end):
        print(f"📞 Adding Call Center data for {start} – {end}...")
        inbound, _ = download_conversion_report(start, end, include_homeshow=False)
        outbound, _ = download_conversion_report(start, end, include_homeshow=True)

        inbound["mode"] = "inbound"
        outbound["mode"] = "outbound"
        for df in [inbound, outbound]:
            df["week_start"] = start
            df["week_end"] = end

        calls_df = pd.concat([calls_df, inbound, outbound], ignore_index=True)
        calls_df.to_parquet(calls_path, index=False)
    else:
        print(f"✅ Call Center data for {start} – {end} already present.")

    return jobs_df, calls_df


def generate_reference_weeks(selected_start_date: str, df) -> dict:
    """
    Given a selected start date and a DataFrame with 'week_start' column,
    return valid reference weeks (e.g., 1 week ago, 1 month ago),
    ensuring that the returned weeks actually exist in the dataset.

    Returns a dictionary of {label: (start_date_str, end_date_str) or (None, None)}
    """
    # Ensure all week_start values are datetime.date objects
    available_weeks = (
        df[["week_start", "week_end"]]
        .drop_duplicates()
        .dropna()
        .assign(
            week_start=lambda d: pd.to_datetime(d["week_start"]).dt.date,
            week_end=lambda d: pd.to_datetime(d["week_end"]).dt.date,
        )
        .sort_values("week_start")
        .reset_index(drop=True)
    )

    base_date = datetime.strptime(selected_start_date, "%m/%d/%Y").date()
    reference_map = {
        "1 week ago": 1,
        "1 month ago": 4,
        "3 months ago": 13,
        "6 months ago": 26,
        "1 year ago": 52,
    }

    result = {}
    for label, weeks_back in reference_map.items():
        target_date = base_date - timedelta(weeks=weeks_back)

        # Find the closest matching week_start
        match = available_weeks[available_weeks["week_start"] == target_date]

        if not match.empty:
            row = match.iloc[0]
            result[label] = (
                row["week_start"].strftime("%m/%d/%Y"),
                row["week_end"].strftime("%m/%d/%Y"),
            )
        else:
            result[label] = (None, None)

    return result


def update_dashboard(selected_week, selected_franchisee="All"):
    if not selected_week:
        return html.Div(
            "Please select a week above to load the report.",
            style={"textAlign": "center", 
                   "marginTop": "48px", 
                   "color": "gray"},
        )

    start_csv, end_csv = selected_week.split("|")

    # Load once at startup
    MASTER_JOBS_PARQUET = Path("MasterData/all_jobs_data.parquet")
    MASTER_CALLS_PARQUET = Path("MasterData/all_call_center_data.parquet")

    # Read full data into memory
    jobs_all_df = pd.read_parquet(MASTER_JOBS_PARQUET)
    calls_all_df = pd.read_parquet(MASTER_CALLS_PARQUET)

    # Historical period: 1 week ago
    reference_weeks = generate_reference_weeks(start_csv, jobs_all_df)
    one_week_ago_start, one_week_ago_end = reference_weeks["1 week ago"]

    # convert to date objects
    start_dt = datetime.strptime(start_csv, "%m/%d/%Y").date()
    end_dt = datetime.strptime(end_csv, "%m/%d/%Y").date()

    # build the human-readable labels
    lw_sun_str = start_dt.strftime("%B %-d")  # e.g. "June 8"
    lw_sat_str = end_dt.strftime("%B %-d")  # e.g. "June 14"

    # Filter jobs
    jobs_df = jobs_all_df[
        (jobs_all_df["week_start"] == start_csv) & (jobs_all_df["week_end"] == end_csv)
    ]
    if selected_franchisee != "All":
        jobs_df = jobs_df[jobs_df["Franchisee"] == selected_franchisee]

    # Filter calls
    inbound_df = calls_all_df[
        (calls_all_df["week_start"] == start_csv)
        & (calls_all_df["week_end"] == end_csv)
        & (calls_all_df["mode"] == "inbound")
    ].drop(columns=["week_start", "week_end", "mode"])

    outbound_df = calls_all_df[
        (calls_all_df["week_start"] == start_csv)
        & (calls_all_df["week_end"] == end_csv)
        & (calls_all_df["mode"] == "outbound")
    ].drop(columns=["week_start", "week_end", "mode"])

    # Defensive: skip if 1-wk-ago not available
    if "1 week ago" not in reference_weeks:
        previous_jobs_df = pd.DataFrame()
        one_week_ago_start, one_week_ago_end = None, None
    else:
        one_week_ago_start, one_week_ago_end = reference_weeks["1 week ago"]
        previous_jobs_df = jobs_all_df[
            (jobs_all_df["week_start"] == one_week_ago_start)
            & (jobs_all_df["week_end"] == one_week_ago_end)
        ]

    if selected_franchisee != "All":
        previous_jobs_df = previous_jobs_df[
            previous_jobs_df["Franchisee"] == selected_franchisee
        ]

    # Guard Historical Lookup
    if previous_jobs_df.empty:
        historical_lookup = {}
    else:
        historical_lookup = (
            previous_jobs_df.groupby("Status", observed=False)["ID"].nunique().to_dict()
        )

    if one_week_ago_start and one_week_ago_end:
        previous_outbound_df = calls_all_df[
            (calls_all_df["week_start"] == one_week_ago_start)
            & (calls_all_df["week_end"] == one_week_ago_end)
            & (calls_all_df["mode"] == "outbound")
        ]
    else:
        previous_outbound_df = pd.DataFrame()

    if previous_outbound_df.empty:
        proxy_last_week = None
        booked_last_week = None
    else:
        try:
            previous_outbound_totals = previous_outbound_df[
                previous_outbound_df["Call Center Rep"] == "Totals"
            ].iloc[0]
            proxy_last_week = int(
                previous_outbound_totals["Outbound Communication Count"]
            )
            booked_last_week = int(previous_outbound_totals["Total Booked"])
        except (IndexError, KeyError, ValueError):
            proxy_last_week = None
            booked_last_week = None

    # Continue as usual
    metrics_children = build_call_center_metrics(outbound_df, proxy_last_week, booked_last_week)

    fig = make_status_figure(jobs_df, selected_franchisee, historical_lookup)

    # Grab last week's "Totals" row
    previous_df = calls_all_df[
        (calls_all_df["week_start"] == one_week_ago_start)
        & (calls_all_df["week_end"] == one_week_ago_end)
        & (calls_all_df["mode"] == "inbound")
    ]

    try:
        previous_totals_row = previous_df[
            previous_df["Call Center Rep"] == "Totals"
        ].iloc[0]
        prev_inbound_rate = float(previous_totals_row["Inbound Rate Value"])
    except (IndexError, KeyError):
        prev_inbound_rate = None  # fallback

    def build_inbound_tooltip(row, prev_rate):
        if row["Call Center Rep"] != "Totals" or prev_rate is None:
            return ""

        delta = get_delta_percent(row["Inbound Rate Value"], prev_rate)
        color = percent_to_color(delta)
        change = format_with_change(row["Inbound Rate Value"], prev_rate).split()[-1]

        return (
            f"**1 Wk Ago:** {prev_rate:.1f}%  \n"
            f"<span style='color:{color}; font-weight:bold'>{change}</span>"
        )

    inbound_df["Inbound Help Rate Tooltip"] = inbound_df.apply(
        lambda row: build_inbound_tooltip(row, prev_inbound_rate), axis=1
    )

    dashboard_sections=[
        # Operations header + chart
        html.Div(
            style={"marginTop": "0px"},
            children=[
                html.H2(
                    "Operations",
                    style={
                        "marginTop": "10px",
                        "marginBottom": "6px",
                        "color": "#2C3E70",
                    },
                ),
                html.Div(
                    f"Data collected from the week of {lw_sun_str} – {lw_sat_str}",
                    style={
                        "fontSize": "14px",
                        "color": "gray",
                        "fontStyle": "italic",
                        "marginBottom": "24px",
                    },
                ),
                html.Div(
                    [
                        html.Label(
                            "Select Franchisee:",
                            style={
                                "fontWeight": "600",
                                "color": "#2C3E70",
                                "marginBottom": "6px",
                            },
                        ),
                        dcc.Dropdown(
                            id="franchisee-selector",
                            options=[
                                {"label": f, "value": f}
                                for f in [
                                    "All",
                                    *sorted(
                                        jobs_all_df["Franchisee"].dropna().unique()
                                    ),
                                ]
                            ],
                            value=selected_franchisee,
                            clearable=False,
                            style={"width": "240px", "border": "1px solid #2C3E70"},
                        ),
                        dcc.Graph(id="status-bar-chart", figure=fig),
                    ],
                    style={"display": "flex", "flexDirection": "column"},
                ),
            ],
        ),
        # Call Center
        html.Div(
            style={"marginTop": "0px"},
            children=[
                html.H2(
                    "Call Center", style={"color": "#2C3E70", "marginBottom": "6px"}
                ),
                html.Div(
                    f"Data collected from the week of {lw_sun_str} – {lw_sat_str}",
                    style={
                        "fontSize": "14px",
                        "color": "gray",
                        "textAlign": "left",
                        "marginBottom": "24px",
                        "fontStyle": "italic",
                    },
                ),
                # Metrics container
                html.Div(
                    id="metrics-container",
                    style={
                        "display": "flex",
                        "justifyContent": "center",
                        "gap": "80px",
                        "marginBottom": "16px",
                        "marginTop": "16px",
                    },
                    children=metrics_children,
                ),
                # Two tables
                html.Div(
                    style={"display": "flex", 
                           "gap": "40px"},
                    children=[
                        # Inbound
                        html.Div(
                            style={"flex": "1"},
                            children=[
                                html.H4(
                                    "Inbound Performance",
                                    style={
                                        "textAlign": "center",
                                        "color": "#2C3E70",
                                        "marginBottom": "6px",
                                    },
                                ),
                                html.Div(
                                    "(excludes homeshow data)",
                                    style={
                                        "fontSize": "14px",
                                        "color": "gray",
                                        "textAlign": "center",
                                        "marginBottom": "24px",
                                        "fontStyle": "italic",
                                    },
                                ),
                                dash_table.DataTable(
                                    id="inbound-table",
                                    columns=[
                                        {
                                            "name": "Call Center Rep",
                                            "id": "Call Center Rep",
                                        },
                                        {
                                            "name": "Inbound Lead Count",
                                            "id": "Inbound Lead Count",
                                        },
                                        {
                                            "name": "Inbound Booked Count",
                                            "id": "Inbound Booked Count",
                                        },
                                        {
                                            "name": "Inbound Help Rate (%)",
                                            "id": "Inbound Help Rate (%)",
                                        },
                                    ],
                                    data=inbound_df.to_dict("records"),
                                    style_cell={
                                        "padding": "8px",
                                        "fontFamily": "Segoe UI, sans-serif",
                                        "fontSize": "14px",
                                        "textAlign": "center",
                                    },
                                    style_header={
                                        "backgroundColor": "#2C3E70",
                                        "color": "white",
                                        "fontWeight": "bold",
                                    },
                                    # Inbound Conditional Formatiing
                                    style_data_conditional=[
                                        # Subtle Zebra Stripes
                                        {
                                            "if": {"row_index": "odd"},
                                            "backgroundColor": "#F9F9F9",
                                        },
                                        {
                                            "if": {"row_index": "even"},
                                            "backgroundColor": "#FFFFFF",
                                        },
                                        # Totals Row
                                        {
                                            "if": {
                                                "filter_query": '{Call Center Rep} = "Totals"'
                                            },
                                            "borderTop": "1px solid #000",
                                            "fontWeight": "600",
                                        },
                                        # Inbound Help Rate %
                                        # ≥ 86% → soft green
                                        {
                                            "if": {
                                                "filter_query": "{Inbound Rate Value} >= 86",
                                                "column_id": "Inbound Help Rate (%)",
                                            },
                                            "backgroundColor": "#e6ffed",
                                            "color": "#2c662d",
                                        },
                                        # 80–85% → lighter green
                                        {
                                            "if": {
                                                "filter_query": "{Inbound Rate Value} >= 80 && {Inbound Rate Value} < 86",
                                                "column_id": "Inbound Help Rate (%)",
                                            },
                                            "backgroundColor": "#f0fff4",
                                            "color": "#336633",
                                        },
                                        # 70–79% → soft yellow
                                        {
                                            "if": {
                                                "filter_query": "{Inbound Rate Value} >= 70 && {Inbound Rate Value} < 80",
                                                "column_id": "Inbound Help Rate (%)",
                                            },
                                            "backgroundColor": "#fffde1",
                                            "color": "#665c00",
                                        },
                                        # 60–69% → light coral
                                        {
                                            "if": {
                                                "filter_query": "{Inbound Rate Value} >= 60 && {Inbound Rate Value} < 70",
                                                "column_id": "Inbound Help Rate (%)",
                                            },
                                            "backgroundColor": "#ffe6e6",
                                            "color": "#802020",
                                        },
                                        # < 60% → pale pink
                                        {
                                            "if": {
                                                "filter_query": "{Inbound Rate Value} < 60",
                                                "column_id": "Inbound Help Rate (%)",
                                            },
                                            "backgroundColor": "#ffebe6",
                                            "color": "#800000",
                                        },
                                    ],
                                ),
                            ],
                        ),
                        # Outbound
                        html.Div(
                            style={"flex": "1"},
                            children=[
                                html.H4(
                                    "Outbound Performance",
                                    style={
                                        "textAlign": "center",
                                        "color": "#2C3E70",
                                        "marginBottom": "6px",
                                    },
                                ),
                                html.Div(
                                    "(includes homeshow data)",
                                    style={
                                        "fontSize": "14px",
                                        "color": "gray",
                                        "textAlign": "center",
                                        "marginBottom": "24px",
                                        "fontStyle": "italic",
                                    },
                                ),
                                dash_table.DataTable(
                                    id="outbound-table",
                                    columns=[
                                        {
                                            "name": "Call Center Rep",
                                            "id": "Call Center Rep",
                                        },
                                        {
                                            "name": "Outbound Call Count",
                                            "id": "Outbound Call Count",
                                        },
                                        {
                                            "name": "Outbound Booked Count",
                                            "id": "Outbound Booked Count",
                                        },
                                        {
                                            "name": "Outbound Help Rate (%)",
                                            "id": "Outbound Help Rate (%)",
                                        },
                                    ],
                                    data=outbound_df.to_dict("records"),
                                    style_cell={
                                        "padding": "8px",
                                        "fontFamily": "Segoe UI, sans-serif",
                                        "fontSize": "14px",
                                        "textAlign": "center",
                                    },
                                    style_header={
                                        "backgroundColor": "#2C3E70",
                                        "color": "white",
                                        "fontWeight": "bold",
                                    },
                                    style_data_conditional=[
                                        # subtle zebra stripes
                                        {
                                            "if": {"row_index": "odd"},
                                            "backgroundColor": "#F9F9F9",
                                        },
                                        {
                                            "if": {"row_index": "even"},
                                            "backgroundColor": "#FFFFFF",
                                        },
                                        # Totals row separator
                                        {
                                            "if": {
                                                "filter_query": '{Call Center Rep} = "Totals"'
                                            },
                                            "borderTop": "1px solid #000",
                                            "fontWeight": "600",
                                        },
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        # Finance
        html.Div(
            style={"marginTop": "0px"},
            children=[
                html.H2(
                    "Finance",
                    style={
                        "marginTop": "10px",
                        "marginBottom": "6px",
                        "color": "#2C3E70",
                    },
                ),
                html.Div(
                    f"Data collected from the week of {lw_sun_str} – {lw_sat_str}",
                    style={
                        "fontSize": "14px",
                        "color": "gray",
                        "fontStyle": "italic",
                        "marginBottom": "24px",
                    },
                ),   
            ]
        ),

        # Marketing
        html.Div(
            style={"marginTop": "0px"},
            children=[
                html.H2(
                    "Marketing",
                    style={
                        "marginTop": "10px",
                        "marginBottom": "6px",
                        "color": "#2C3E70",
                    },
                ),
                html.Div(
                    f"Data collected from the week of {lw_sun_str} – {lw_sat_str}",
                    style={
                        "fontSize": "14px",
                        "color": "gray",
                        "fontStyle": "italic",
                        "marginBottom": "24px",
                    },
                ),   
            ]
        )
    ]

    
    return dashboard_sections

def build_call_center_metrics(outbound_df, proxy_last_week=None, booked_last_week=None):
    """
    Reads the Totals row in outbound_df and returns
    [touches_box, design_box] for use as metrics_children,
    with five‐step coloring and border for touches.
    """
    
    def _get_proxy_color(total_proxy):
        """Determine color based on proxy count thresholds"""
        if total_proxy >= 700:
            return "#2c662d"  # dark green
        elif total_proxy >= 650:
            return "#336633"  # medium green
        elif total_proxy >= 550:
            return "#665c00"  # olive/gold
        elif total_proxy >= 450:
            return "#802020"  # dark coral
        else:
            return "#800000"  # dark red
    
    def _build_touches_box(totals, proxy_last_week):
        """Build the touches metric box"""
        total_proxy = int(totals["Outbound Communication Count"])
        
        # Determine color based on thresholds
        proxy_color = _get_proxy_color(total_proxy)
        
        # Calculate delta and formatting
        touches_delta = get_delta_percent(total_proxy, proxy_last_week)
        touches_color = percent_to_color(touches_delta)
        
        if proxy_last_week is None:
            touches_change_str = "–"
        else:
            touches_change_str = format_with_change(total_proxy, proxy_last_week).split()[-1]
        
        # Style definitions
        main_number_style = {
            "margin": 0,
            "fontSize": "56px",
            "color": percent_to_color(get_delta_percent(total_proxy, proxy_last_week)),
        }
        
        label_style = {
            "fontSize": "14px", 
            "color": "gray"
        }
        
        change_container_style = {
            "fontSize": "13px", 
            "marginTop": "4px"
        }
        
        change_text_style = {
            "color": (percent_to_color(get_delta_percent(total_proxy, proxy_last_week)) 
                     if proxy_last_week is not None else "gray"),
            "fontWeight": "bold",
        }
        
        # Build the component
        touches_box = html.Div(
            children=[
                html.H1(f"{total_proxy}", style=main_number_style),
                html.Div("touches – proxy", style=label_style),
                html.Div(
                    children=[
                        html.Span("1 Wk Ago: ", style={"fontWeight": "bold"}),
                        html.Span(
                            f"{int(proxy_last_week) if proxy_last_week is not None else '–'} ",
                            style={"marginRight": "4px"},
                        ),
                        html.Span(touches_change_str, style=change_text_style),
                    ],
                    style=change_container_style,
                ),
            ],
            style={"textAlign": "center"},
        )
        
        return touches_box
    
    def _build_design_box(totals, booked_last_week):
        """Build the design appointments metric box"""
        total_booked = int(totals["Total Booked"])
        
        # Calculate delta and formatting
        design_delta = get_delta_percent(total_booked, booked_last_week)
        
        if booked_last_week is None:
            design_change_str = "–"
        else:
            design_change_str = format_with_change(total_booked, booked_last_week).split()[-1]
        
        # Style definitions
        main_number_style = {
            "margin": 0,
            "fontSize": "56px",
            "color": percent_to_color(get_delta_percent(total_booked, booked_last_week)),
        }
        
        label_style = {
            "fontSize": "14px", 
            "color": "gray"
        }
        
        change_container_style = {
            "fontSize": "13px", 
            "marginTop": "4px"
        }
        
        change_text_style = {
            "color": percent_to_color(get_delta_percent(total_booked, booked_last_week)),
            "fontWeight": "bold",
        }
        
        # Build the component
        design_box = html.Div(
            children=[
                html.H1(f"{total_booked}", style=main_number_style),
                html.Div("design appointments scheduled", style=label_style),
                html.Div(
                    children=[
                        html.Span("1 Wk Ago: ", style={"fontWeight": "bold"}),
                        html.Span(
                            f"{int(booked_last_week) if booked_last_week is not None else '–'} ",
                            style={"marginRight": "4px"},
                        ),
                        html.Span(design_change_str, style=change_text_style),
                    ],
                    style=change_container_style,
                ),
            ],
            style={"textAlign": "center"},
        )
        
        return design_box
    
    # Main function logic
    # Pull the Totals row once
    totals = outbound_df.loc[outbound_df["Call Center Rep"] == "Totals"].iloc[0]

    # Build touches box
    touches_box = _build_touches_box(totals, proxy_last_week)
    
    # Build design appointments box
    design_box = _build_design_box(totals, booked_last_week)

    return [touches_box, design_box]
