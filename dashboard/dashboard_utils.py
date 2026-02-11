# import data_fetcher
import math
import re
from datetime import datetime, date, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from dash import dash_table, dcc, html
from functools import lru_cache

# from data_fetcher import load_jobs_data, download_conversion_report, fetch_roi


# Helpers
@lru_cache(maxsize=1)
def load_master_data():
    """Read and cache the master parquet files from the parent directory."""
    # base_dir = Path(__file__).resolve().parent.parent  # <-- from dashboard/ up to AoD_Dashboard/
    # master_data_dir = base_dir / "Master_Data"

    master_data_dir = Path(__file__).resolve().parent / "Master_Data"

    jobs_path  = master_data_dir / "all_jobs_data.parquet"
    calls_path = master_data_dir / "all_call_center_data.parquet"
    roi_path   = master_data_dir / "all_roi_data.parquet"

    jobs_df  = pd.read_parquet(jobs_path)
    calls_df = pd.read_parquet(calls_path)
    roi_df   = pd.read_parquet(roi_path)

    return jobs_df, calls_df, roi_df


@lru_cache(maxsize=1)
def load_projections_data():
    """Read and cache the projections parquet files."""
    master_data_dir = Path(__file__).resolve().parent / "Master_Data"

    rpa_path = master_data_dir / "projections_rpa_data.parquet"
    sales_path = master_data_dir / "projections_sales_data.parquet"
    appts_path = master_data_dir / "projections_appointments_data.parquet"

    rpa_df = pd.read_parquet(rpa_path) if rpa_path.exists() else pd.DataFrame()
    sales_df = pd.read_parquet(sales_path) if sales_path.exists() else pd.DataFrame()
    appts_df = pd.read_parquet(appts_path) if appts_path.exists() else pd.DataFrame()

    return rpa_df, sales_df, appts_df


def get_delta_percent(current, previous):
    if current is None or previous is None or previous == 0:
        return None
    return ((current - previous) / previous) * 100


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


# def fetch_and_append_week_if_needed(jobs_df: pd.DataFrame, calls_df: pd.DataFrame, roi_df: pd.DataFrame):
#     jobs_path = Path("MasterData/all_jobs_data.parquet")
#     calls_path = Path("MasterData/all_call_center_data.parquet")
#     roi_path = Path("MasterData/all_roi_data.parquet")

#     start, end = get_last_full_week(date.today())

#     session = data_fetcher.get_session_with_canvas_cookie()

#     if not parquet_has_week(jobs_df, start, end):
#         print(f"📦 Adding Jobs data for {start} – {end}...")
#         new_jobs   = data_fetcher.load_jobs_data(start, end)
#         new_jobs["week_start"] = start
#         new_jobs["week_end"] = end
#         new_jobs["ID"] = new_jobs["ID"].astype(str)
#         jobs_df = pd.concat([jobs_df, new_jobs], ignore_index=True)
#         jobs_df.to_parquet(jobs_path, index=False)
#     else:
#         print(f"✅ Jobs data for {start} – {end} already present.")

#     if not parquet_has_week(calls_df, start, end):
#         print(f"📞 Adding Call Center data for {start} – {end}...")
#         inbound, _ = data_fetcher.download_conversion_report(start, end, include_homeshow=False)
#         outbound,_ = data_fetcher.download_conversion_report(start, end, include_homeshow=True)

#         inbound["mode"] = "inbound"
#         outbound["mode"] = "outbound"
#         for df in [inbound, outbound]:
#             df["week_start"] = start
#             df["week_end"] = end

#         calls_df = pd.concat([calls_df, inbound, outbound], ignore_index=True)
#         calls_df.to_parquet(calls_path, index=False)
#     else:
#         print(f"✅ Call Center data for {start} – {end} already present.")

#     if not parquet_has_week(roi_df, start, end):
#         print(f"Adding ROI data for {start} – {end}...")
#         new_roi = data_fetcher.fetch_roi(start, end, session) 
#         new_roi["week_start"] = start
#         new_roi["week_end"] = end

#         roi_df = pd.concat([roi_df, new_roi], ignore_index=True)
#         roi_df.to_parquet(roi_path, index=False)
#     else:
#         print(f"✅ ROI data for {start} – {end} already present.")

#     return jobs_df, calls_df, roi_df


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


def format_with_change(current: float, previous: float) -> str:
    """
    Returns formatted string with % change tooltip: "123 (↑12.5%)" or "95 (↓8.1%)"
    """
    if current is None or previous is None or previous == 0:
        return f"{int(current) if current is not None else 0}"

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


def generate_week_options_from_parquet(df):
    """Generate week options from any DataFrame with week_start/week_end columns"""
    weeks = (
        df[["week_start", "week_end"]]
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


# Builders
# MAKE_STATUS_FIGURE FUNCTION COMMENTED OUT - REMOVED FROM DASHBOARD
# def make_status_figure(jobs_df: pd.DataFrame, selected_franchisee: str, historical_lookup: dict) -> go.Figure:
#     """
#     Build and return the stacked-bar + totals figure for the given franchisee.
#     """
#
#     status_order = [
#         "Measurement Appointment Scheduled",
#         "Measurement Approved",
#         "Submitted to Manufacturing Partner",
#         "Order Shipped",
#         "Order Received",
#         "Install Scheduled",
#         "Installed",
#         "Complete",
#     ]
#
#     # 1) Filter
#     df_f = (
#         jobs_df
#         if selected_franchisee == "All"
#         else jobs_df[jobs_df["Franchisee"] == selected_franchisee]
#     )
#
#     # 2) Aggregate
#     grouped = (
#         df_f.groupby(["Status", "Order Type"], observed=False)
#         .agg(Count=("ID", "nunique"))
#         .reset_index()
#     )
#     grouped["Status"] = pd.Categorical(
#         grouped["Status"], categories=status_order, ordered=True
#     )
#
#     # 3) Fill missing combos
#     order_types = ["New", "Claim", "Reorder"]
#     combos = pd.MultiIndex.from_product(
#         [status_order, order_types], names=["Status", "Order Type"]
#     )
#     grouped = (
#         grouped.set_index(["Status", "Order Type"])
#         .reindex(combos, fill_value=0)
#         .reset_index()
#     )
#
#     # 4) Compute totals
#     totals = (
#         grouped.groupby("Status", observed=False)["Count"]
#         .sum()
#         .reindex(status_order)
#         .reset_index()
#     )
#     raw_max = int(totals["Count"].max()) if not totals.empty else 0
#     top = math.ceil(raw_max / 5) * 5 * 1.1 if raw_max % 5 else raw_max * 1.1
#     top = int(math.ceil(top))
#
#     # 5) Build manually with go.Figure()
#     fig = go.Figure()
#
#     bar_colors = {"New": "#2C3E70", "Claim": "#a1c4bd", "Reorder": "#bbbfbf"}
#
#     for ot in order_types:
#         df_trace = grouped[grouped["Order Type"] == ot]
#         fig.add_trace(
#             go.Bar(
#                 x=df_trace["Status"],
#                 y=df_trace["Count"],
#                 name=ot,
#                 marker_color=bar_colors.get(ot, "#888"),
#                 customdata=[[ot]] * len(df_trace),
#                 hovertemplate="<b>%{x}</b><br>Type: %{customdata[0]}<br>Count: %{y}<extra></extra>",
#                 uid=ot,
#                 hoverlabel=dict(
#                     bgcolor=bar_colors.get(ot, "#888"),
#                     font_size=14,
#                     font_color="white",  # white looks best on these
#                 ),
#             )
#         )
#
#     hover_texts = []
#     for s, c in zip(totals["Status"], totals["Count"]):
#         if selected_franchisee == "All":
#             prev = historical_lookup.get(s)
#             if prev is None or prev == 0:
#                 hover_texts.append(f"<b>{s}</b><br><b>1 Wk Ago:</b> –<extra></extra>")
#             else:
#                 delta = get_delta_percent(c, prev)
#                 delta_text = format_with_change(c, prev).split()[-1]
#                 color = percent_to_color(delta)
#                 hover_texts.append(
#                     f"<b>{s}</b><br><b>1 Wk Ago:</b> {int(prev)} "
#                     f"<span style='color:{color}'>{delta_text}</span><extra></extra>"
#                 )
#         else:
#             hover_texts.append(f"<b>{s}</b><br><b>Count:</b> {int(c)}<extra></extra>")
#
#     # 6) Add total labels as pixel-aligned annotations
#     for x, y, text in zip(totals["Status"], totals["Count"], totals["Count"]):
#         fig.add_annotation(
#             x=x,
#             y=y,
#             text=str(int(text)),
#             showarrow=False,
#             yanchor="bottom",
#             yshift=2,  # shift label 2 pixels above bar
#             font=dict(color="#2C3E70", size=14),
#             align="center",
#         )
#
#     if selected_franchisee == "All":
#         fig.add_trace(
#             go.Scatter(
#                 x=totals["Status"],
#                 y=totals["Count"] + 4,  # ← ALIGN to true count, not offset
#                 mode="markers",
#                 marker=dict(size=30, color="rgba(0,0,0,0)"),  # transparent
#                 hovertemplate=hover_texts,
#                 showlegend=False,
#                 hoverlabel=dict(
#                     bgcolor="white",
#                     font_size=14,
#                     font_color="black",
#                     bordercolor="#2C3E70",
#                 ),
#             )
#         )
#
#     fig.update_layout(
#         uirevision="static-axes",
#         plot_bgcolor="white",
#         paper_bgcolor="white",
#         hoverlabel=dict(
#             bgcolor="white",  # Background color
#             font_size=14,  # Font size
#             font_color="black",  # Text color
#             bordercolor="#2C3E70",  # Optional: adds a subtle border for separation
#         ),
#         barmode="stack",
#         height=500,
#         margin=dict(t=100, b=30, l=40, r=40),
#         font=dict(
#             family="Segoe UI, sans-serif", size=14, color="#2C3E70"
#         ),  # Global font for axis, legend, etc.
#         legend=dict(orientation="h", y=1.05, x=1, xanchor="right"),
#         title=dict(
#             text=f"Project Status by Order Type — {selected_franchisee}",
#             font=dict(
#                 family="Segoe UI, sans-serif",
#                 size=20,  # Match H1-style prominence
#                 color="#2C3E70",
#             ),
#         ),
#     )
#
#     # 8) Shorten labels
#     def shorten(lbl):
#         lbl = re.sub(r"(?i)measurement[s]?", "Meas.", lbl)
#         lbl = re.sub(r"(?i)manufacturing( partner)?", "MFG", lbl)
#         return re.sub(r"(?i)appointment[s]?", "Appt.", lbl)
#
#     # 9) Axes
#     fig.update_xaxes(
#         ticktext=[shorten(s) for s in status_order],
#         tickvals=status_order,
#         showticklabels=True,
#         ticks="outside",
#         tickangle=-45,
#         showline=True,
#         linecolor="#2C3E70",
#         autorange=False,
#         fixedrange=True,
#         range=[-0.5, len(status_order) - 0.5],
#     )
#
#     fig.update_yaxes(
#         range=[0, top],
#         autorange=False,
#         rangemode="tozero",
#         showticklabels=False,
#         ticks="",
#         fixedrange=True,
#     )
#
#     return fig


def build_call_center_line_chart(calls_all_df, selected_metric="touches"):
    """
    Build a line chart showing Call Center metrics over all available weeks.
    selected_metric: "touches" or "design_appts"
    """
    # Get data for outbound (for both metrics)
    outbound_data = calls_all_df[calls_all_df["mode"] == "outbound"].copy()

    # Group by week and sum the Totals row values
    weekly_data = []
    for (week_start, week_end), group in outbound_data.groupby(["week_start", "week_end"]):
        totals_row = group[group["Call Center Rep"] == "Totals"]
        if not totals_row.empty:
            touches = int(totals_row["Outbound Communication Count"].iloc[0])
            design_appts = int(totals_row["Total Booked"].iloc[0])
            weekly_data.append({
                "week_start": week_start,
                "week_end": week_end,
                "touches": touches,
                "design_appts": design_appts
            })

    # Convert to DataFrame and sort by date
    df = pd.DataFrame(weekly_data)
    if df.empty:
        # Return empty figure if no data
        return go.Figure().update_layout(
            title="No data available",
            font=dict(family="Segoe UI, sans-serif", color="#2C3E70")
        )

    df["week_start_dt"] = pd.to_datetime(df["week_start"])
    df = df.sort_values("week_start_dt")

    # Create week labels
    df["week_label"] = df.apply(
        lambda row: f"{pd.to_datetime(row['week_start']).strftime('%m/%d')} – {pd.to_datetime(row['week_end']).strftime('%m/%d')}",
        axis=1
    )

    # Select metric
    if selected_metric == "touches":
        y_values = df["touches"]
        title = "Touches (Proxy) Over Time"
        y_title = "Touch Count"
        color = "#2C3E70"
    else:  # design_appts
        y_values = df["design_appts"]
        title = "Design Appointments Scheduled Over Time"
        y_title = "Appointments Count"
        color = "#2C3E70"

    # Create figure
    fig = go.Figure()

    # Main data line
    fig.add_trace(go.Scatter(
        x=df["week_label"],
        y=y_values,
        mode="lines+markers",
        name=y_title,
        line=dict(color=color, width=3, shape="spline", smoothing=1.2),
        marker=dict(size=7, color="white", line=dict(color=color, width=2.5)),
        fill="tozeroy",
        fillcolor="rgba(44, 62, 112, 0.05)",
        hovertemplate="%{y:,}<extra></extra>"
    ))

    # Dashed average line
    avg_val = y_values.mean()
    fig.add_hline(
        y=avg_val, line_dash="dot", line_color="rgba(44, 62, 112, 0.3)", line_width=1.5,
        annotation_text=f"Avg: {int(avg_val):,}",
        annotation_position="top right",
        annotation_font=dict(size=11, color="rgba(44, 62, 112, 0.5)", family="Segoe UI, sans-serif"),
    )

    # Best/Worst week annotations
    if len(y_values) > 1:
        best_idx = y_values.idxmax()
        worst_idx = y_values.idxmin()
        fig.add_annotation(
            x=df.loc[best_idx, "week_label"], y=y_values[best_idx],
            text=f"Peak: {int(y_values[best_idx]):,}",
            showarrow=True, arrowhead=0, arrowwidth=1.5, arrowcolor="#2c662d",
            font=dict(color="#2c662d", size=11, family="Segoe UI, sans-serif"),
            bgcolor="rgba(230,255,237,0.95)", bordercolor="#c3e6cb", borderpad=5,
            borderwidth=1, ax=0, ay=-32
        )
        if best_idx != worst_idx:
            fig.add_annotation(
                x=df.loc[worst_idx, "week_label"], y=y_values[worst_idx],
                text=f"Low: {int(y_values[worst_idx]):,}",
                showarrow=True, arrowhead=0, arrowwidth=1.5, arrowcolor="#c62828",
                font=dict(color="#c62828", size=11, family="Segoe UI, sans-serif"),
                bgcolor="rgba(255,235,230,0.95)", bordercolor="#f5c6cb", borderpad=5,
                borderwidth=1, ax=0, ay=32
            )

    fig.update_layout(
        title=dict(
            text=title,
            font=dict(family="Segoe UI, sans-serif", size=18, color="#2C3E70"),
            x=0.02, xanchor="left"
        ),
        yaxis_title=y_title,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Segoe UI, sans-serif", size=13, color="#2C3E70"),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="white", bordercolor="#2C3E70",
            font=dict(family="Segoe UI, sans-serif", size=13, color="#2C3E70")
        ),
        height=400,
        margin=dict(t=50, b=50, l=55, r=30),
        showlegend=False,
    )

    fig.update_xaxes(
        showgrid=False,
        showline=True, linecolor="#ddd", linewidth=1,
        tickangle=-45,
        tickfont=dict(size=11),
    )

    fig.update_yaxes(
        showgrid=True, gridcolor="#f0f0f0", griddash="dot",
        showline=False,
        zeroline=False,
        tickfont=dict(size=11),
    )

    return fig


def build_marketing_line_chart(roi_all_df, selected_metric="cost_per_appt"):
    """
    Build a line chart showing Marketing metrics over all available weeks.
    selected_metric: "cost_per_appt", "amount_invested", or "leads_generated"
    """
    # Get all ROI data
    roi_data = roi_all_df.copy()

    if roi_data.empty:
        return go.Figure().update_layout(
            title="No data available",
            font=dict(family="Segoe UI, sans-serif", color="#2C3E70")
        )

    # Sort by week_start
    roi_data["week_start_dt"] = pd.to_datetime(roi_data["week_start"])
    roi_data = roi_data.sort_values("week_start_dt")

    # Create week labels
    roi_data["week_label"] = roi_data.apply(
        lambda row: f"{pd.to_datetime(row['week_start']).strftime('%m/%d')} – {pd.to_datetime(row['week_end']).strftime('%m/%d')}",
        axis=1
    )

    # Helper to extract numeric value
    import re
    def extract_numeric(val):
        if pd.isna(val):
            return None
        if isinstance(val, (int, float)):
            return float(val)
        cleaned = re.sub(r"[^\d\.\-]", "", str(val))
        try:
            return float(cleaned)
        except ValueError:
            return None

    # Select metric and prepare data
    if selected_metric == "cost_per_appt":
        roi_data["value"] = roi_data["Cost Per Appt"].apply(extract_numeric)
        title = "Cost Per Appointment Over Time"
        y_title = "Cost ($)"
        hover_format = "$%{y:,.2f}"
    elif selected_metric == "amount_invested":
        roi_data["value"] = roi_data["Amount Invested"].apply(extract_numeric)
        title = "Amount Invested Over Time"
        y_title = "Amount ($)"
        hover_format = "$%{y:,.2f}"
    else:  # leads_generated
        roi_data["value"] = roi_data["# of Leads"].apply(extract_numeric)
        title = "Leads Generated Over Time"
        y_title = "Number of Leads"
        hover_format = "%{y}"

    # Filter out null values
    roi_data = roi_data[roi_data["value"].notna()]

    # Create figure
    fig = go.Figure()
    is_dollar = "$" in hover_format

    fig.add_trace(go.Scatter(
        x=roi_data["week_label"],
        y=roi_data["value"],
        mode="lines+markers",
        name=y_title,
        line=dict(color="#2C3E70", width=3, shape="spline", smoothing=1.2),
        marker=dict(size=7, color="white", line=dict(color="#2C3E70", width=2.5)),
        fill="tozeroy",
        fillcolor="rgba(44, 62, 112, 0.05)",
        hovertemplate=f"{hover_format}<extra></extra>"
    ))

    # Dashed average line
    values = roi_data["value"].reset_index(drop=True)
    labels = roi_data["week_label"].reset_index(drop=True)
    avg_val = values.mean()
    avg_text = f"Avg: ${avg_val:,.0f}" if is_dollar else f"Avg: {int(avg_val):,}"
    fig.add_hline(
        y=avg_val, line_dash="dot", line_color="rgba(44, 62, 112, 0.3)", line_width=1.5,
        annotation_text=avg_text,
        annotation_position="top right",
        annotation_font=dict(size=11, color="rgba(44, 62, 112, 0.5)", family="Segoe UI, sans-serif"),
    )

    # Best/Worst week annotations
    if len(values) > 1:
        best_idx = values.idxmax()
        worst_idx = values.idxmin()
        best_text = f"Peak: ${values[best_idx]:,.0f}" if is_dollar else f"Peak: {int(values[best_idx]):,}"
        worst_text = f"Low: ${values[worst_idx]:,.0f}" if is_dollar else f"Low: {int(values[worst_idx]):,}"
        fig.add_annotation(
            x=labels[best_idx], y=values[best_idx],
            text=best_text,
            showarrow=True, arrowhead=0, arrowwidth=1.5, arrowcolor="#2c662d",
            font=dict(color="#2c662d", size=11, family="Segoe UI, sans-serif"),
            bgcolor="rgba(230,255,237,0.95)", bordercolor="#c3e6cb", borderpad=5,
            borderwidth=1, ax=0, ay=-32
        )
        if best_idx != worst_idx:
            fig.add_annotation(
                x=labels[worst_idx], y=values[worst_idx],
                text=worst_text,
                showarrow=True, arrowhead=0, arrowwidth=1.5, arrowcolor="#c62828",
                font=dict(color="#c62828", size=11, family="Segoe UI, sans-serif"),
                bgcolor="rgba(255,235,230,0.95)", bordercolor="#f5c6cb", borderpad=5,
                borderwidth=1, ax=0, ay=32
            )

    fig.update_layout(
        title=dict(
            text=title,
            font=dict(family="Segoe UI, sans-serif", size=18, color="#2C3E70"),
            x=0.02, xanchor="left"
        ),
        yaxis_title=y_title,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Segoe UI, sans-serif", size=13, color="#2C3E70"),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="white", bordercolor="#2C3E70",
            font=dict(family="Segoe UI, sans-serif", size=13, color="#2C3E70")
        ),
        height=400,
        margin=dict(t=50, b=50, l=55, r=30),
        showlegend=False,
    )

    fig.update_xaxes(
        showgrid=False,
        showline=True, linecolor="#ddd", linewidth=1,
        tickangle=-45,
        tickfont=dict(size=11),
    )

    fig.update_yaxes(
        showgrid=True, gridcolor="#f0f0f0", griddash="dot",
        showline=False,
        zeroline=False,
        tickfont=dict(size=11),
    )

    return fig


def build_finance_line_chart(roi_all_df, selected_metric="revenue"):
    """
    Build a line chart showing Finance metrics over all available weeks.
    selected_metric: "revenue", "revenue_per_appt", or "num_appts"
    """
    # Get all ROI data
    roi_data = roi_all_df.copy()

    if roi_data.empty:
        return go.Figure().update_layout(
            title="No data available",
            font=dict(family="Segoe UI, sans-serif", color="#2C3E70")
        )

    # Sort by week_start
    roi_data["week_start_dt"] = pd.to_datetime(roi_data["week_start"])
    roi_data = roi_data.sort_values("week_start_dt")

    # Create week labels
    roi_data["week_label"] = roi_data.apply(
        lambda row: f"{pd.to_datetime(row['week_start']).strftime('%m/%d')} – {pd.to_datetime(row['week_end']).strftime('%m/%d')}",
        axis=1
    )

    # Helper to extract numeric value
    import re
    def extract_numeric(val):
        if pd.isna(val):
            return None
        if isinstance(val, (int, float)):
            return float(val)
        cleaned = re.sub(r"[^\d\.\-]", "", str(val))
        try:
            return float(cleaned)
        except ValueError:
            return None

    # Select metric and prepare data
    if selected_metric == "revenue":
        roi_data["value"] = roi_data["Revenue"].apply(extract_numeric)
        title = "Revenue Over Time"
        y_title = "Revenue ($)"
        hover_format = "$%{y:,.2f}"
    elif selected_metric == "revenue_per_appt":
        roi_data["value"] = roi_data["Revenue Per Appt"].apply(extract_numeric)
        title = "Revenue Per Appointment Over Time"
        y_title = "Revenue ($)"
        hover_format = "$%{y:,.2f}"
    else:  # num_appts
        roi_data["value"] = roi_data["# of Appts"].apply(extract_numeric)
        title = "# of Appointments Over Time"
        y_title = "Number of Appointments"
        hover_format = "%{y}"

    # Filter out null values
    roi_data = roi_data[roi_data["value"].notna()]

    # Create figure
    fig = go.Figure()
    is_dollar = "$" in hover_format

    fig.add_trace(go.Scatter(
        x=roi_data["week_label"],
        y=roi_data["value"],
        mode="lines+markers",
        name=y_title,
        line=dict(color="#2C3E70", width=3, shape="spline", smoothing=1.2),
        marker=dict(size=7, color="white", line=dict(color="#2C3E70", width=2.5)),
        fill="tozeroy",
        fillcolor="rgba(44, 62, 112, 0.05)",
        hovertemplate=f"{hover_format}<extra></extra>"
    ))

    # Dashed average line
    values = roi_data["value"].reset_index(drop=True)
    labels = roi_data["week_label"].reset_index(drop=True)
    avg_val = values.mean()
    avg_text = f"Avg: ${avg_val:,.0f}" if is_dollar else f"Avg: {int(avg_val):,}"
    fig.add_hline(
        y=avg_val, line_dash="dot", line_color="rgba(44, 62, 112, 0.3)", line_width=1.5,
        annotation_text=avg_text,
        annotation_position="top right",
        annotation_font=dict(size=11, color="rgba(44, 62, 112, 0.5)", family="Segoe UI, sans-serif"),
    )

    # Best/Worst week annotations
    if len(values) > 1:
        best_idx = values.idxmax()
        worst_idx = values.idxmin()
        best_text = f"Peak: ${values[best_idx]:,.0f}" if is_dollar else f"Peak: {int(values[best_idx]):,}"
        worst_text = f"Low: ${values[worst_idx]:,.0f}" if is_dollar else f"Low: {int(values[worst_idx]):,}"
        fig.add_annotation(
            x=labels[best_idx], y=values[best_idx],
            text=best_text,
            showarrow=True, arrowhead=0, arrowwidth=1.5, arrowcolor="#2c662d",
            font=dict(color="#2c662d", size=11, family="Segoe UI, sans-serif"),
            bgcolor="rgba(230,255,237,0.95)", bordercolor="#c3e6cb", borderpad=5,
            borderwidth=1, ax=0, ay=-32
        )
        if best_idx != worst_idx:
            fig.add_annotation(
                x=labels[worst_idx], y=values[worst_idx],
                text=worst_text,
                showarrow=True, arrowhead=0, arrowwidth=1.5, arrowcolor="#c62828",
                font=dict(color="#c62828", size=11, family="Segoe UI, sans-serif"),
                bgcolor="rgba(255,235,230,0.95)", bordercolor="#f5c6cb", borderpad=5,
                borderwidth=1, ax=0, ay=32
            )

    fig.update_layout(
        title=dict(
            text=title,
            font=dict(family="Segoe UI, sans-serif", size=18, color="#2C3E70"),
            x=0.02, xanchor="left"
        ),
        yaxis_title=y_title,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Segoe UI, sans-serif", size=13, color="#2C3E70"),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="white", bordercolor="#2C3E70",
            font=dict(family="Segoe UI, sans-serif", size=13, color="#2C3E70")
        ),
        height=400,
        margin=dict(t=50, b=50, l=55, r=30),
        showlegend=False,
    )

    fig.update_xaxes(
        showgrid=False,
        showline=True, linecolor="#ddd", linewidth=1,
        tickangle=-45,
        tickfont=dict(size=11),
    )

    fig.update_yaxes(
        showgrid=True, gridcolor="#f0f0f0", griddash="dot",
        showline=False,
        zeroline=False,
        tickfont=dict(size=11),
    )

    return fig


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


def build_location_ranking_cards(rpa_df, sales_df):
    """
    Build location performance cards showing top 5 for sales and RPA separately.
    Returns html.Div component with organized sections.
    """
    if rpa_df.empty and sales_df.empty:
        return html.Div("No location data available", style={"color": "gray", "textAlign": "center"})

    # Helper to create a location card
    def create_location_card(location, rank, metric_value, metric_label, is_top=True):
        badge_color = "#2c662d" if is_top else "#b71c1c"
        badge_text = f"#{rank}"

        return html.Div(
            children=[
                html.Div(
                    badge_text,
                    style={
                        "position": "absolute",
                        "top": "10px",
                        "right": "10px",
                        "backgroundColor": badge_color,
                        "color": "white",
                        "padding": "4px 12px",
                        "borderRadius": "12px",
                        "fontSize": "14px",
                        "fontWeight": "bold",
                    }
                ),
                html.H3(location, style={"color": "#2C3E70", "marginBottom": "8px", "fontSize": "16px", "paddingRight": "50px"}),
                html.Div(metric_value, style={"fontSize": "28px", "fontWeight": "bold", "color": badge_color, "marginBottom": "4px"}),
                html.Div(metric_label, style={"fontSize": "11px", "color": "gray"}),
            ],
            style={
                "position": "relative",
                "border": f"2px solid {badge_color}",
                "borderRadius": "8px",
                "padding": "16px",
                "minWidth": "180px",
                "flex": "1",
                "backgroundColor": "white",
                "boxShadow": "0 2px 4px rgba(0,0,0,0.1)",
            }
        )

    sections = []

    # Top 5 Sales Section
    if not sales_df.empty and "Rank" in sales_df.columns:
        sales_sorted = sales_df.sort_values("Rank").head(5)
        sales_cards = []
        for _, row in sales_sorted.iterrows():
            location = row.get("Location", "Unknown")
            rank = row.get("Rank", "-")
            sales = row.get("Sales", "$0")
            sales_cards.append(create_location_card(location, rank, sales, "Total Sales", is_top=True))

        sections.append(html.Div([
            html.H4("Top 5 by Sales", style={"color": "#2C3E70", "marginBottom": "12px", "fontSize": "16px"}),
            html.Div(sales_cards, style={"display": "flex", "gap": "12px", "flexWrap": "wrap", "marginBottom": "30px"})
        ]))

    # Top 5 RPA Section
    if not rpa_df.empty and "Rank" in rpa_df.columns:
        rpa_sorted = rpa_df.sort_values("Rank").head(5)
        rpa_cards = []

        # Try different possible column names for RPA
        rpa_column = None
        for col in ["Revenue per Appointment", "Revenue Per Appointment", "RPA"]:
            if col in rpa_df.columns:
                rpa_column = col
                break

        for _, row in rpa_sorted.iterrows():
            location = row.get("Location", "Unknown")
            rank = row.get("Rank", "-")
            rpa = row.get(rpa_column, "$0") if rpa_column else "$0"
            rpa_cards.append(create_location_card(location, rank, rpa, "Revenue per Appointment", is_top=True))

        sections.append(html.Div([
            html.H4("Top 5 by Revenue Per Appointment", style={"color": "#2C3E70", "marginBottom": "12px", "fontSize": "16px"}),
            html.Div(rpa_cards, style={"display": "flex", "gap": "12px", "flexWrap": "wrap"})
        ]))

    return html.Div(sections)


def build_appointment_pipeline_summary(appts_df):
    """
    Build future appointment pipeline summary.
    Returns html.Div component.
    """
    if appts_df.empty:
        return html.Div("No future appointments data available", style={"color": "gray", "textAlign": "center"})

    # Count total appointments
    total_appts = len(appts_df)

    # Group by location
    if "Location" in appts_df.columns:
        location_counts = appts_df.groupby("Location").size().sort_values(ascending=False).head(10)

        location_cards = []
        for location, count in location_counts.items():
            location_cards.append(
                html.Div(
                    children=[
                        html.Div(location, style={"fontWeight": "bold", "color": "#2C3E70", "marginBottom": "4px"}),
                        html.Div(f"{count} appointments", style={"fontSize": "24px", "color": "#2c662d"}),
                    ],
                    style={
                        "border": "1px solid #ddd",
                        "borderRadius": "6px",
                        "padding": "12px",
                        "minWidth": "180px",
                        "backgroundColor": "#f9f9f9",
                    }
                )
            )
    else:
        location_cards = []

    return html.Div(
        children=[
            html.Div(
                children=[
                    html.H1(f"{total_appts}", style={"margin": 0, "fontSize": "48px", "color": "#2C3E70"}),
                    html.Div("Total Future Appointments", style={"fontSize": "14px", "color": "gray"}),
                ],
                style={"textAlign": "center", "marginBottom": "24px"}
            ),
            html.Div(
                children=[
                    html.H4("Top Locations by Appointment Count", style={"color": "#2C3E70", "marginBottom": "12px"}),
                    html.Div(
                        location_cards,
                        style={"display": "flex", "gap": "12px", "flexWrap": "wrap"}
                    ),
                ],
            ) if location_cards else html.Div(),
        ]
    )


def build_location_rankings_table(df, ranking_type="sales"):
    """
    Build full location rankings table with conditional formatting.
    Returns dash_table.DataTable component.
    """
    if df.empty:
        return html.Div("No data available", style={"color": "gray", "textAlign": "center"})

    # Prepare columns for display
    columns = [{"name": col, "id": col} for col in df.columns if col not in ["week_start", "week_end", "fetched_at"]]

    # Conditional formatting
    style_data_conditional = [
        # Zebra stripes
        {"if": {"row_index": "odd"}, "backgroundColor": "#F9F9F9"},
        {"if": {"row_index": "even"}, "backgroundColor": "#FFFFFF"},
    ]

    # Top 10 green, bottom 10 red (if Rank column exists)
    if "Rank" in df.columns:
        style_data_conditional.extend([
            {
                "if": {"filter_query": "{Rank} <= 10"},
                "backgroundColor": "#e6ffed",
                "color": "#2c662d",
            },
            {
                "if": {"filter_query": f"{{Rank}} >= {len(df) - 9}"},
                "backgroundColor": "#ffebe6",
                "color": "#b71c1c",
            },
        ])

    return dash_table.DataTable(
        data=df.to_dict("records"),
        columns=columns,
        style_cell={
            "padding": "8px",
            "fontFamily": "Segoe UI, sans-serif",
            "fontSize": "13px",
            "textAlign": "center",
        },
        style_header={
            "backgroundColor": "#2C3E70",
            "color": "white",
            "fontWeight": "bold",
            "fontSize": "14px",
        },
        style_data_conditional=style_data_conditional,
        style_table={"overflowX": "auto"},
    )


# Updaters
def update_dashboard(selected_week, selected_franchisee="All"):
    if not selected_week:
        return html.Div(
            "Please select a week above to load the report.",
            style={"textAlign": "center", 
                   "marginTop": "48px", 
                   "color": "gray"},
        )

    start_csv, end_csv = selected_week.split("|")

    # # Load once at startup
    # MASTER_JOBS_PARQUET = Path("MasterData/all_jobs_data.parquet")
    # MASTER_CALLS_PARQUET = Path("MasterData/all_call_center_data.parquet")

    # # Read full data into memory
    # jobs_all_df = pd.read_parquet(MASTER_JOBS_PARQUET)
    # calls_all_df = pd.read_parquet(MASTER_CALLS_PARQUET)

    # Read full data into memory (cached)
    jobs_all_df, calls_all_df, roi_df = load_master_data()

    # Load projections data (location rankings and appointments) - cached
    rpa_all_df, sales_all_df, appts_all_df = load_projections_data()

    # Historical period: 1 week ago
    # JOBS REMOVED - using calls_all_df for reference weeks instead
    reference_weeks = generate_reference_weeks(start_csv, calls_all_df)
    one_week_ago_start, one_week_ago_end = reference_weeks["1 week ago"]

    # convert to date objects
    start_dt = datetime.strptime(start_csv, "%m/%d/%Y").date()
    end_dt = datetime.strptime(end_csv, "%m/%d/%Y").date()

    # build the human-readable labels
    lw_sun_str = start_dt.strftime("%B %-d")  # e.g. "June 8"
    lw_sat_str = end_dt.strftime("%B %-d")  # e.g. "June 14"

    # JOBS FILTERING COMMENTED OUT - REMOVED FROM DASHBOARD
    # jobs_df = jobs_all_df[
    #     (jobs_all_df["week_start"] == start_csv) & (jobs_all_df["week_end"] == end_csv)
    # ]
    # if selected_franchisee != "All":
    #     jobs_df = jobs_df[jobs_df["Franchisee"] == selected_franchisee]

    # Filter calls
    inbound_df = calls_all_df[
        (calls_all_df["week_start"] == start_csv)
        & (calls_all_df["week_end"] == end_csv)
        & (calls_all_df["mode"] == "inbound")
    ].drop(columns=["week_start", "week_end", "mode"])

    # Filter out rows where Inbound Help Rate is "nan%"
    inbound_df = inbound_df[inbound_df["Inbound Help Rate (%)"] != "nan%"]

    outbound_df = calls_all_df[
        (calls_all_df["week_start"] == start_csv)
        & (calls_all_df["week_end"] == end_csv)
        & (calls_all_df["mode"] == "outbound")
    ].drop(columns=["week_start", "week_end", "mode"])

    # Filter out rows where Outbound Help Rate is "nan%"
    outbound_df = outbound_df[outbound_df["Outbound Help Rate (%)"] != "nan%"]

    # Defensive: skip if 1-wk-ago not available
    if "1 week ago" not in reference_weeks:
        # previous_jobs_df = pd.DataFrame()
        one_week_ago_start, one_week_ago_end = None, None
    else:
        one_week_ago_start, one_week_ago_end = reference_weeks["1 week ago"]
        # JOBS PREVIOUS WEEK LOOKUP COMMENTED OUT - REMOVED FROM DASHBOARD
        # previous_jobs_df = jobs_all_df[
        #     (jobs_all_df["week_start"] == one_week_ago_start)
        #     & (jobs_all_df["week_end"] == one_week_ago_end)
        # ]

    # JOBS FRANCHISEE FILTER COMMENTED OUT - REMOVED FROM DASHBOARD
    # if selected_franchisee != "All":
    #     previous_jobs_df = previous_jobs_df[
    #         previous_jobs_df["Franchisee"] == selected_franchisee
    #     ]

    # Guard Historical Lookup
    # JOBS HISTORICAL LOOKUP COMMENTED OUT - REMOVED FROM DASHBOARD
    # if previous_jobs_df.empty:
    #     historical_lookup = {}
    # else:
    #     historical_lookup = (
    #         previous_jobs_df.groupby("Status", observed=False)["ID"].nunique().to_dict()
    #     )

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

    # JOBS STATUS FIGURE COMMENTED OUT - REMOVED FROM DASHBOARD
    # fig = make_status_figure(jobs_df, selected_franchisee, historical_lookup)

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

    # filter current week and 1-week-ago
    roi_curr = roi_df[
        (roi_df["week_start"] == start_csv) &
        (roi_df["week_end"]   == end_csv)
    ]
    roi_prev = roi_df[
        (roi_df["week_start"] == one_week_ago_start) &
        (roi_df["week_end"]   == one_week_ago_end)
    ]

    # Filter projections data for current week
    rpa_curr = rpa_all_df[
        (rpa_all_df["week_start"] == start_csv) &
        (rpa_all_df["week_end"] == end_csv)
    ] if not rpa_all_df.empty else pd.DataFrame()

    sales_curr = sales_all_df[
        (sales_all_df["week_start"] == start_csv) &
        (sales_all_df["week_end"] == end_csv)
    ] if not sales_all_df.empty else pd.DataFrame()

    appts_curr = appts_all_df[
        (appts_all_df["week_start"] == start_csv) &
        (appts_all_df["week_end"] == end_csv)
    ] if not appts_all_df.empty else pd.DataFrame()

    # helper to safely pull a numeric value
    import re

    def _get_val(df, col):
        """
        Pull a numeric column out of a one‐row ROI DataFrame.
        Strips out dollar signs, commas, etc., before converting to float.
        Returns None if the column is missing or the DataFrame is empty.
        """
        if df.empty or col not in df.columns:
            return None
    
        raw = df.iloc[0][col]
        # If it’s already numeric, just return it
        if isinstance(raw, (int, float)):
            return float(raw)
    
        # Otherwise, strip out anything that’s not a digit, dot or minus
        cleaned = re.sub(r"[^\d\.\-]", "", str(raw))
        try:
            return float(cleaned)
        except ValueError:
            return None


    # Marketing Metrics: Cost Per Appt, Amount Invested, Leads Generated
    marketing_curr = {
        "Cost Per Appointment": _get_val(roi_curr, "Cost Per Appt"),
        "Amount Invested":  _get_val(roi_curr, "Amount Invested"),
        "Leads Generated":  _get_val(roi_curr, "# of Leads"),
    }
    marketing_prev = {
        "Cost Per Appointment": _get_val(roi_prev, "Cost Per Appt"),
        "Amount Invested": _get_val(roi_prev, "Amount Invested"),
        "Leads Generated": _get_val(roi_prev, "# of Leads"),
    }

    # Finance Metrics: Revenue, Revenue Per Appt, # of Appointments
    finance_curr = {
        "Revenue": _get_val(roi_curr, "Revenue"),
        "Revenue Per Appointment": _get_val(roi_curr, "Revenue Per Appt"),
        "# of Appointments": _get_val(roi_curr, "# of Appts"),
    }
    finance_prev = {
        "Revenue": _get_val(roi_prev, "Revenue"),
        "Revenue Per Appointment": _get_val(roi_prev, "Revenue Per Appt"),
        "# of Appointments": _get_val(roi_prev, "# of Appts"),
    }

    def build_metric_cards(curr_dict, prev_dict):
        """Helper function to build metric cards"""
        cards = []
        for label, now in curr_dict.items():
            old = prev_dict[label]

            # display value
            if now is None:
                disp = "–"
            elif label in ["Leads Generated", "# of Appointments"]:
                disp = f"{int(now)}"
            else:
                disp = f"${now:,.2f}"

            # change + color
            if old in [None, 0]:
                ch, col = "–", "#999"
            else:
                d   = get_delta_percent(now, old)
                ch  = format_with_change(now, old).split()[-1]
                col = percent_to_color(d)

            cards.append(
                html.Div(
                    children=[
                        html.H1(disp,
                                style={"margin": 0, "fontSize": "56px", "color": col}),
                        html.Div(label,
                                 style={"fontSize": "14px", "color": "gray"}),
                        html.Div(
                            [
                                html.Span("1 Wk Ago: ",
                                          style={"fontWeight": "bold"}),
                                html.Span(
                                    f"{('$'+format(old,',.2f')) if old not in [None,0] and label not in ['Leads Generated', '# of Appointments'] else (str(int(old)) if old not in [None,0] else '–')} ",
                                    style={"marginRight": "4px"},
                                ),
                                html.Span(ch,
                                          style={"color": col,
                                                 "fontWeight": "bold"}),
                            ],
                            style={"fontSize": "13px", "marginTop": "4px"},
                        ),
                    ],
                    style={"textAlign": "center", "flex": "1"},
                )
            )
        return cards

    marketing_cards = build_metric_cards(marketing_curr, marketing_prev)
    finance_cards = build_metric_cards(finance_curr, finance_prev)
    
    dashboard_sections=[
        # OPERATIONS SECTION COMMENTED OUT - REMOVED FROM DASHBOARD
        # # Operations header + chart
        # html.Div(
        #     style={"marginTop": "0px"},
        #     children=[
        #         html.H2(
        #             "Operations",
        #             style={
        #                 "marginTop": "10px",
        #                 "marginBottom": "6px",
        #                 "color": "#2C3E70",
        #             },
        #         ),
        #         html.Div(
        #             f"Data collected from the week of {lw_sun_str} – {lw_sat_str}",
        #             style={
        #                 "fontSize": "14px",
        #                 "color": "gray",
        #                 "fontStyle": "italic",
        #                 "marginBottom": "24px",
        #             },
        #         ),
        #         html.Div(
        #             [
        #                 html.Label(
        #                     "Select Franchisee:",
        #                     style={
        #                         "fontWeight": "600",
        #                         "color": "#2C3E70",
        #                         "marginBottom": "6px",
        #                     },
        #                 ),
        #                 dcc.Dropdown(
        #                     id="franchisee-selector",
        #                     options=[
        #                         {"label": f, "value": f}
        #                         for f in [
        #                             "All",
        #                             *sorted(
        #                                 jobs_all_df["Franchisee"].dropna().unique()
        #                             ),
        #                         ]
        #                     ],
        #                     value=selected_franchisee,
        #                     clearable=False,
        #                     style={"width": "240px", "border": "1px solid #2C3E70"},
        #                 ),
        #                 dcc.Graph(id="status-bar-chart", figure=fig),
        #             ],
        #             style={"display": "flex", "flexDirection": "column"},
        #         ),
        #     ],
        # ),
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
                # Line Chart Toggle Button
                html.Div(
                    style={"textAlign": "center", "marginBottom": "20px"},
                    children=[
                        html.Button(
                            "Show Trend Chart",
                            id="cc-chart-toggle",
                            n_clicks=0,
                            style={
                                "backgroundColor": "#2C3E70",
                                "color": "white",
                                "border": "none",
                                "padding": "10px 20px",
                                "fontSize": "14px",
                                "borderRadius": "4px",
                                "cursor": "pointer",
                                "fontFamily": "Segoe UI, sans-serif"
                            }
                        )
                    ]
                ),
                # Line Chart Section (hidden by default)
                html.Div(
                    id="cc-chart-container",
                    style={"display": "none", "marginBottom": "30px"},
                    children=[
                        html.Div(
                            style={"textAlign": "center", "marginBottom": "16px"},
                            children=[
                                dcc.RadioItems(
                                    id="cc-metric-selector",
                                    options=[
                                        {"label": "  Touches (Proxy)", "value": "touches"},
                                        {"label": "  Design Appointments", "value": "design_appts"}
                                    ],
                                    value="touches",
                                    inline=True,
                                    style={"fontFamily": "Segoe UI, sans-serif", "fontSize": "14px"},
                                    labelStyle={"marginRight": "20px", "cursor": "pointer"}
                                )
                            ]
                        ),
                        dcc.Graph(
                            id="cc-line-chart",
                            figure=build_call_center_line_chart(calls_all_df, "touches"),
                            config={"displayModeBar": False}
                        )
                    ]
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
                html.Div(
                    id="finance-metrics-container",
                    style={
                        "display": "flex",
                        "justifyContent": "center",
                        "gap": "80px",
                        "marginBottom": "16px",
                        "marginTop": "16px",
                    },
                    children=finance_cards,
                ),
                # Line Chart Toggle Button
                html.Div(
                    style={"textAlign": "center", "marginBottom": "20px"},
                    children=[
                        html.Button(
                            "📈 Show Trend Chart",
                            id="fin-chart-toggle",
                            n_clicks=0,
                            style={
                                "backgroundColor": "#2C3E70",
                                "color": "white",
                                "border": "none",
                                "padding": "10px 20px",
                                "fontSize": "14px",
                                "borderRadius": "4px",
                                "cursor": "pointer",
                                "fontFamily": "Segoe UI, sans-serif"
                            }
                        )
                    ]
                ),
                # Line Chart Section (hidden by default)
                html.Div(
                    id="fin-chart-container",
                    style={"display": "none", "marginBottom": "30px"},
                    children=[
                        html.Div(
                            style={"textAlign": "center", "marginBottom": "16px"},
                            children=[
                                dcc.RadioItems(
                                    id="fin-metric-selector",
                                    options=[
                                        {"label": "  Revenue", "value": "revenue"},
                                        {"label": "  Revenue Per Appointment", "value": "revenue_per_appt"},
                                        {"label": "  # of Appointments", "value": "num_appts"}
                                    ],
                                    value="revenue",
                                    inline=True,
                                    style={"fontFamily": "Segoe UI, sans-serif", "fontSize": "14px"},
                                    labelStyle={"marginRight": "20px", "cursor": "pointer"}
                                )
                            ]
                        ),
                        dcc.Graph(
                            id="fin-line-chart",
                            figure=build_finance_line_chart(roi_df, "revenue"),
                            config={"displayModeBar": False}
                        )
                    ]
                ),
            ]
        ),

        # # Marketing
        # html.Div(
        #     style={"marginTop": "0px"},
        #     children=[
        #         html.H2(
        #             "Marketing",
        #             style={
        #                 "marginTop": "10px",
        #                 "marginBottom": "6px",
        #                 "color": "#2C3E70",
        #             },
        #         ),
        #         html.Div(
        #             f"Data collected from the week of {lw_sun_str} – {lw_sat_str}",
        #             style={
        #                 "fontSize": "14px",
        #                 "color": "gray",
        #                 "fontStyle": "italic",
        #                 "marginBottom": "24px",
        #             },
        #         ),
        
        # the actual Marketing section
        html.Div(
            style={"marginTop": "0px"},
            children=[
                html.H2("Marketing",
                        style={"marginTop": "10px",
                               "marginBottom": "6px",
                               "color": "#2C3E70"}),
                html.Div(f"Data collected from the week of {lw_sun_str} – {lw_sat_str}",
                         style={"fontSize": "14px",
                                "color": "gray",
                                "fontStyle": "italic",
                                "marginBottom": "24px"}),
                html.Div(
                    id="marketing-metrics-container",
                    style={
                        "display": "flex",
                        "justifyContent": "center",
                        "gap": "80px",
                        "marginBottom": "16px",
                        "marginTop": "16px",
                    },
                    children=marketing_cards,
                ),
                # Line Chart Toggle Button
                html.Div(
                    style={"textAlign": "center", "marginBottom": "20px"},
                    children=[
                        html.Button(
                            "Show Trend Chart",
                            id="mkt-chart-toggle",
                            n_clicks=0,
                            style={
                                "backgroundColor": "#2C3E70",
                                "color": "white",
                                "border": "none",
                                "padding": "10px 20px",
                                "fontSize": "14px",
                                "borderRadius": "4px",
                                "cursor": "pointer",
                                "fontFamily": "Segoe UI, sans-serif"
                            }
                        )
                    ]
                ),
                # Line Chart Section (hidden by default)
                html.Div(
                    id="mkt-chart-container",
                    style={"display": "none", "marginBottom": "30px"},
                    children=[
                        html.Div(
                            style={"textAlign": "center", "marginBottom": "16px"},
                            children=[
                                dcc.RadioItems(
                                    id="mkt-metric-selector",
                                    options=[
                                        {"label": "  Cost Per Appointment", "value": "cost_per_appt"},
                                        {"label": "  Amount Invested", "value": "amount_invested"},
                                        {"label": "  Leads Generated", "value": "leads_generated"}
                                    ],
                                    value="cost_per_appt",
                                    inline=True,
                                    style={"fontFamily": "Segoe UI, sans-serif", "fontSize": "14px"},
                                    labelStyle={"marginRight": "20px", "cursor": "pointer"}
                                )
                            ]
                        ),
                        dcc.Graph(
                            id="mkt-line-chart",
                            figure=build_marketing_line_chart(roi_df, "cost_per_appt"),
                            config={"displayModeBar": False}
                        )
                    ]
                ),
            ],
        ),

        # Location Performance Section
        html.Div(
            style={"marginTop": "40px"},
            children=[
                html.H2(
                    "Location Performance",
                    style={
                        "marginTop": "10px",
                        "marginBottom": "6px",
                        "color": "#2C3E70",
                    },
                ),
                html.Div(
                    f"Snapshot from the week of {lw_sun_str} – {lw_sat_str}",
                    style={
                        "fontSize": "14px",
                        "color": "gray",
                        "fontStyle": "italic",
                        "marginBottom": "24px",
                    },
                ),

                # Top Performing Locations
                build_location_ranking_cards(rpa_curr, sales_curr),

                # Future Appointments Pipeline
                html.H3(
                    "Future Appointment Pipeline",
                    style={"color": "#2C3E70", "marginTop": "30px", "marginBottom": "12px"}
                ),
                build_appointment_pipeline_summary(appts_curr),

                # Full Rankings Tables (collapsible)
                html.Details(
                    children=[
                        html.Summary(
                            "View Full Location Rankings",
                            style={
                                "cursor": "pointer",
                                "fontWeight": "600",
                                "color": "#2C3E70",
                                "marginTop": "30px",
                                "fontSize": "15px",
                            }
                        ),
                        html.Div(
                            children=[
                                html.H4(
                                    "Sales Rankings",
                                    style={"color": "#2C3E70", "marginTop": "20px", "marginBottom": "12px"}
                                ),
                                build_location_rankings_table(sales_curr, "sales"),

                                html.H4(
                                    "Revenue Per Appointment Rankings",
                                    style={"color": "#2C3E70", "marginTop": "30px", "marginBottom": "12px"}
                                ),
                                build_location_rankings_table(rpa_curr, "rpa"),
                            ],
                            style={"marginTop": "20px"}
                        ),
                    ],
                    style={"marginTop": "20px"}
                ),
            ],
        ) if not rpa_curr.empty or not sales_curr.empty or not appts_curr.empty else html.Div(),

    ]
    #     )
    # ]


    return dashboard_sections

