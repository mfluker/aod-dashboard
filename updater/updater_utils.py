import data_fetcher
import math
import re
from datetime import datetime, date, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from dash import dash_table, dcc, html
from functools import lru_cache

from data_fetcher import download_conversion_report, fetch_roi  # removed: load_jobs_data


# Helpers
@lru_cache(maxsize=1)

# def load_master_data():
#     """Read and cache the master parquet files from the parent directory."""
#     base_dir = Path(__file__).resolve().parent.parent  # <-- from dashboard/ up to AoD_Dashboard/
#     master_data_dir = base_dir / "Master_Data"

#     jobs_path  = master_data_dir / "all_jobs_data.parquet"
#     calls_path = master_data_dir / "all_call_center_data.parquet"
#     roi_path   = master_data_dir / "all_roi_data.parquet"

#     jobs_df  = pd.read_parquet(jobs_path)
#     calls_df = pd.read_parquet(calls_path)
#     roi_df   = pd.read_parquet(roi_path)

#     return jobs_df, calls_df, roi_df

def load_master_data():
    """Read and cache the master parquet files from the parent directory."""
    # base_dir = Path(__file__).resolve().parent.parent  # <-- from dashboard/ up to AoD_Dashboard/
    # master_data_dir = base_dir / "Master_Data"

    master_data_dir = Path(__file__).resolve().parent.parent / "dashboard" / "Master_Data"
    
    jobs_path  = master_data_dir / "all_jobs_data.parquet"
    calls_path = master_data_dir / "all_call_center_data.parquet"
    roi_path   = master_data_dir / "all_roi_data.parquet"

    jobs_df  = pd.read_parquet(jobs_path)
    calls_df = pd.read_parquet(calls_path)
    roi_df   = pd.read_parquet(roi_path)

    return jobs_df, calls_df, roi_df
    

def get_delta_percent(current, previous):
    if previous in [None, 0]:
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


def get_all_missing_weeks(df: pd.DataFrame) -> list[tuple[str, str]]:
    """
    Get ALL missing weeks from the earliest week in the DataFrame to today.
    This includes any gaps in the historical data, not just recent missing weeks.
    Returns a list of (start_date, end_date) tuples in chronological order.
    """
    # Determine the starting point for checking
    if df.empty or "week_start" not in df.columns:
        # If no data exists, start from 3 months ago
        start_from = date.today() - timedelta(weeks=12)
    else:
        # Start from the EARLIEST week in the data, not the latest
        earliest_week_start = pd.to_datetime(df["week_start"]).min()
        start_from = earliest_week_start.date()

    # Get the most recent complete week
    current_week_start, current_week_end = get_last_full_week(date.today())
    current_week_start_date = datetime.strptime(current_week_start, "%m/%d/%Y").date()

    # Generate all weeks from start_from to current and check which ones are missing
    missing_weeks = []
    week_cursor = start_from

    # Align to Sunday
    days_since_sunday = (week_cursor.weekday() + 1) % 7
    if days_since_sunday > 0:
        week_cursor = week_cursor - timedelta(days=days_since_sunday)

    while week_cursor <= current_week_start_date:
        week_start = week_cursor
        week_end = week_cursor + timedelta(days=6)

        start_str = week_start.strftime("%m/%d/%Y")
        end_str = week_end.strftime("%m/%d/%Y")

        # Check if this week exists in the dataframe
        if not parquet_has_week(df, start_str, end_str):
            missing_weeks.append((start_str, end_str))

        week_cursor = week_cursor + timedelta(days=7)

    return missing_weeks


def load_projections_data():
    """Load projections parquet files. Returns empty DataFrames if files don't exist yet."""
    master_data_dir = Path(__file__).resolve().parent.parent / "dashboard" / "Master_Data"
    rpa_path = master_data_dir / "projections_rpa_data.parquet"
    sales_path = master_data_dir / "projections_sales_data.parquet"
    appts_path = master_data_dir / "projections_appointments_data.parquet"

    rpa_df = pd.read_parquet(rpa_path) if rpa_path.exists() else pd.DataFrame()
    sales_df = pd.read_parquet(sales_path) if sales_path.exists() else pd.DataFrame()
    appts_df = pd.read_parquet(appts_path) if appts_path.exists() else pd.DataFrame()

    return rpa_df, sales_df, appts_df


def fetch_and_save_projections(week_start: str, week_end: str):
    """
    Fetch all projections data (RPA rankings, sales rankings, future appointments),
    merge and save to parquet. Appends to existing data for time-series tracking.

    Args:
        week_start: Week start date in MM/DD/YYYY format
        week_end: Week end date in MM/DD/YYYY format

    Returns: (rpa_df, sales_df, appointments_df)
    """
    from datetime import datetime as dt

    master_data_dir = Path(__file__).resolve().parent.parent / "dashboard" / "Master_Data"
    rpa_path = master_data_dir / "projections_rpa_data.parquet"
    sales_path = master_data_dir / "projections_sales_data.parquet"
    appts_path = master_data_dir / "projections_appointments_data.parquet"

    print(f"\n🔐 Validating Canvas authentication cookies...")
    is_valid, message = data_fetcher.validate_canvas_cookies()
    if not is_valid:
        print(f"❌ COOKIE VALIDATION FAILED: {message}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    print(f"✅ {message}")

    session = data_fetcher.get_session_with_canvas_cookie()
    fetched_at = dt.now().strftime("%B %d, %Y at %I:%M %p")

    # Fetch RPA rankings
    rpa_df = data_fetcher.fetch_location_rpa(session)
    if not rpa_df.empty:
        rpa_df["week_start"] = week_start
        rpa_df["week_end"] = week_end
        rpa_df["fetched_at"] = fetched_at
        # Normalize location names
        for col in rpa_df.columns:
            if "location" in col.lower() or "name" in col.lower():
                rpa_df[col] = rpa_df[col].apply(data_fetcher._normalize_location)
                break

    # Fetch sales rankings
    sales_df = data_fetcher.fetch_location_sales(session)
    if not sales_df.empty:
        sales_df["week_start"] = week_start
        sales_df["week_end"] = week_end
        sales_df["fetched_at"] = fetched_at
        # Normalize location names
        for col in sales_df.columns:
            if "location" in col.lower() or "name" in col.lower():
                sales_df[col] = sales_df[col].apply(data_fetcher._normalize_location)
                break

    # Fetch future appointments
    appts_df = data_fetcher.fetch_future_appointments(session)
    if not appts_df.empty:
        appts_df["week_start"] = week_start
        appts_df["week_end"] = week_end
        appts_df["fetched_at"] = fetched_at
        # Normalize location names
        for col in appts_df.columns:
            if "location" in col.lower():
                appts_df[col] = appts_df[col].apply(data_fetcher._normalize_location)
                break

    # Load existing data and append (time-series mode)
    existing_rpa = pd.read_parquet(rpa_path) if rpa_path.exists() else pd.DataFrame()
    existing_sales = pd.read_parquet(sales_path) if sales_path.exists() else pd.DataFrame()
    existing_appts = pd.read_parquet(appts_path) if appts_path.exists() else pd.DataFrame()

    # Remove any existing data for this week (deduplication) before appending
    if not existing_rpa.empty and "week_start" in existing_rpa.columns:
        existing_rpa = existing_rpa[~((existing_rpa["week_start"] == week_start) & (existing_rpa["week_end"] == week_end))]
    if not existing_sales.empty and "week_start" in existing_sales.columns:
        existing_sales = existing_sales[~((existing_sales["week_start"] == week_start) & (existing_sales["week_end"] == week_end))]
    if not existing_appts.empty and "week_start" in existing_appts.columns:
        existing_appts = existing_appts[~((existing_appts["week_start"] == week_start) & (existing_appts["week_end"] == week_end))]

    # Append new data
    if not rpa_df.empty:
        combined_rpa = pd.concat([existing_rpa, rpa_df], ignore_index=True)
        combined_rpa.to_parquet(rpa_path, index=False)
        print(f"\n💾 Saved RPA data: {rpa_path} ({len(rpa_df)} new rows, {len(combined_rpa)} total)")
    else:
        print(f"\n⚠️  RPA data was empty, not saved")

    if not sales_df.empty:
        combined_sales = pd.concat([existing_sales, sales_df], ignore_index=True)
        combined_sales.to_parquet(sales_path, index=False)
        print(f"💾 Saved sales data: {sales_path} ({len(sales_df)} new rows, {len(combined_sales)} total)")
    else:
        print(f"⚠️  Sales data was empty, not saved")

    if not appts_df.empty:
        combined_appts = pd.concat([existing_appts, appts_df], ignore_index=True)
        combined_appts.to_parquet(appts_path, index=False)
        print(f"💾 Saved appointments data: {appts_path} ({len(appts_df)} new rows, {len(combined_appts)} total)")
    else:
        print(f"⚠️  Appointments data was empty, not saved")

    return rpa_df, sales_df, appts_df


def append_projections_if_needed():
    """
    Check if current week's projections data exists. If not, fetch and append.
    Returns: (rpa_df, sales_df, appts_df) for the current week
    """
    # Load existing projections data
    rpa_df, sales_df, appts_df = load_projections_data()

    # Get current week
    current_week_start, current_week_end = get_last_full_week()

    # Check if current week already exists in projections data
    has_rpa = parquet_has_week(rpa_df, current_week_start, current_week_end) if not rpa_df.empty else False
    has_sales = parquet_has_week(sales_df, current_week_start, current_week_end) if not sales_df.empty else False
    has_appts = parquet_has_week(appts_df, current_week_start, current_week_end) if not appts_df.empty else False

    if has_rpa and has_sales and has_appts:
        print(f"\n✅ Projections data for week {current_week_start} – {current_week_end} already exists!")
        # Return current week's data
        current_rpa = rpa_df[(rpa_df["week_start"] == current_week_start) & (rpa_df["week_end"] == current_week_end)]
        current_sales = sales_df[(sales_df["week_start"] == current_week_start) & (sales_df["week_end"] == current_week_end)]
        current_appts = appts_df[(appts_df["week_start"] == current_week_start) & (appts_df["week_end"] == current_week_end)]
        return current_rpa, current_sales, current_appts

    print(f"\n📊 Fetching projections data for week {current_week_start} – {current_week_end}...")

    # Fetch and save new data
    new_rpa, new_sales, new_appts = fetch_and_save_projections(current_week_start, current_week_end)

    return new_rpa, new_sales, new_appts


def fetch_and_append_week_if_needed(jobs_df: pd.DataFrame, calls_df: pd.DataFrame, roi_df: pd.DataFrame):
    """
    Fetch and append ALL missing weeks from the earliest data to today.
    This ensures all gaps in the historical data are filled, including:
    - Missing weeks between the earliest and latest data (e.g., Sept-Nov gaps)
    - Missing weeks from the latest data to today
    """
    # Robust path pointing to top-level Master_Data directory
    base_dir = Path(__file__).resolve().parent.parent / "dashboard" / "Master_Data"

    jobs_path = base_dir / "all_jobs_data.parquet"
    calls_path = base_dir / "all_call_center_data.parquet"
    roi_path = base_dir / "all_roi_data.parquet"

    session = data_fetcher.get_session_with_canvas_cookie()

    # JOBS DATA FETCHING COMMENTED OUT - REMOVED FROM DASHBOARD
    print(f"⏭️  Skipping Jobs data (feature removed from dashboard)")

    # Show current data range
    if not calls_df.empty:
        earliest = pd.to_datetime(calls_df["week_start"]).min().strftime("%m/%d/%Y")
        latest = pd.to_datetime(calls_df["week_end"]).max().strftime("%m/%d/%Y")
        print(f"\n📊 Current data range: {earliest} to {latest}")
    else:
        print(f"\n📊 No existing data found")

    # Get all missing weeks for Call Center data (use calls_df as reference)
    print(f"🔍 Checking for missing weeks from earliest date to today...")
    missing_weeks = get_all_missing_weeks(calls_df)

    if not missing_weeks:
        print(f"✅ All data is up to date! No missing weeks found.")
        return jobs_df, calls_df, roi_df

    print(f"\n📅 Found {len(missing_weeks)} missing week(s) to fetch:")
    for start, end in missing_weeks:
        print(f"   • {start} – {end}")

    # VALIDATE COOKIES BEFORE FETCHING
    print(f"\n🔐 Validating Canvas authentication cookies...")
    is_valid, message = data_fetcher.validate_canvas_cookies()
    if not is_valid:
        print(f"❌ COOKIE VALIDATION FAILED: {message}")
        print(f"   Cannot proceed with data fetch.")
        print(f"   Please refresh your canvas_cookies.json file and try again.")
        # Return original data without changes
        return jobs_df, calls_df, roi_df
    else:
        print(f"✅ {message}")

    # Fetch each missing week
    for week_num, (start, end) in enumerate(missing_weeks, 1):
        print(f"\n📦 Fetching week {week_num}/{len(missing_weeks)}: {start} – {end}")

        # Fetch Call Center data
        print(f"  📞 Fetching Call Center data...")
        inbound, _ = data_fetcher.download_conversion_report(start, end, include_homeshow=False)
        outbound, _ = data_fetcher.download_conversion_report(start, end, include_homeshow=True)

        inbound["mode"] = "inbound"
        outbound["mode"] = "outbound"
        for df in [inbound, outbound]:
            df["week_start"] = start
            df["week_end"] = end

        calls_df = pd.concat([calls_df, inbound, outbound], ignore_index=True)

        # Fetch ROI data
        print(f"  💰 Fetching ROI data...")
        new_roi = data_fetcher.fetch_roi(start, end, session)

        # VALIDATION: Check if ROI data is empty or invalid
        if new_roi.empty:
            print(f"  ❌ WARNING: ROI data fetch returned EMPTY DataFrame!")
            print(f"     This usually means Canvas authentication failed or no data exists for this week.")
            print(f"     Week: {start} – {end}")
            print(f"     Check the debug HTML file at: /tmp/roi_debug_{start.replace('/', '-')}_{end.replace('/', '-')}.html")
        else:
            print(f"  ✅ ROI data received: {new_roi.shape[0]} row(s), {new_roi.shape[1]} column(s)")
            print(f"     Columns: {list(new_roi.columns)}")
            # Show first row values to verify it's not all zeros
            if len(new_roi) > 0:
                first_row_sample = {col: new_roi[col].iloc[0] for col in list(new_roi.columns)[:5]}
                print(f"     Sample values: {first_row_sample}")

                # Check for suspicious zero/empty data
                if 'Amount Invested' in new_roi.columns and 'Revenue' in new_roi.columns:
                    amount_str = str(new_roi['Amount Invested'].iloc[0]).replace('$', '').replace(',', '').strip()
                    revenue_str = str(new_roi['Revenue'].iloc[0]).replace('$', '').replace(',', '').strip()

                    try:
                        amount_val = float(amount_str) if amount_str not in ['', '-', 'nan'] else 0
                        revenue_val = float(revenue_str) if revenue_str not in ['', '-', 'nan'] else 0

                        if amount_val == 0 and revenue_val == 0:
                            print(f"  ⚠️  SUSPICIOUS: Both Amount Invested and Revenue are $0.00!")
                            print(f"     This may indicate authentication failure or genuinely no activity this week.")
                            print(f"     Review the debug HTML at: /tmp/roi_debug_{start.replace('/', '-')}_{end.replace('/', '-')}.html")
                    except:
                        pass

        new_roi["week_start"] = start
        new_roi["week_end"] = end

        roi_df = pd.concat([roi_df, new_roi], ignore_index=True)

        print(f"  ✅ Week {start} – {end} fetched successfully!")

    # Save all updated data at once
    print(f"\n💾 Saving updated data to Parquet files...")
    print(f"  • Saving Call Center data to: {calls_path}")
    calls_df.to_parquet(calls_path, index=False)
    print(f"  • Saving ROI data to: {roi_path}")

    # FINAL VALIDATION: Check the ROI data we're about to save
    print(f"\n🔍 Final ROI Data Validation:")
    print(f"  Total ROI rows: {len(roi_df)}")

    # Check how many rows for the newly added weeks
    new_roi_rows = roi_df[roi_df['week_start'].isin([w[0] for w in missing_weeks])]
    print(f"  New ROI rows added: {len(new_roi_rows)}")

    if len(new_roi_rows) == 0:
        print(f"  ⚠️  WARNING: No new ROI data was added for the missing weeks!")
        print(f"     This likely means all fetch_roi calls returned empty DataFrames.")
        print(f"     Check authentication and Canvas access.")
    else:
        # Show sample of new data
        print(f"  ✅ New ROI data preview:")
        for _, row in new_roi_rows.head(3).iterrows():
            sample_cols = [col for col in row.index if col not in ['week_start', 'week_end']][:3]
            sample_data = {col: row[col] for col in sample_cols}
            print(f"     Week {row['week_start']}-{row['week_end']}: {sample_data}")

    roi_df.to_parquet(roi_path, index=False)
    print(f"✅ All {len(missing_weeks)} week(s) saved successfully to Master_Data!")

    return jobs_df, calls_df, roi_df


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


# Builders
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

    # filter current week and 1-week-ago
    roi_curr = roi_df[
        (roi_df["week_start"] == start_csv) &
        (roi_df["week_end"]   == end_csv)
    ]
    roi_prev = roi_df[
        (roi_df["week_start"] == one_week_ago_start) &
        (roi_df["week_end"]   == one_week_ago_end)
    ]

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


    curr = {
        "Amount Invested":  _get_val(roi_curr, "Amount Invested"),
        "Leads Generated":  _get_val(roi_curr, "# of Leads"),
        "Revenue Per Appt": _get_val(roi_curr, "Revenue Per Appt"),
    }
    prev = {
        k: _get_val(roi_prev, k if k != "Leads Generated" else "# of Leads")
        for k in curr
    }

    cards = []
    for label, now in curr.items():
        old = prev[label]

        # display value
        if now is None:
            disp = "–"
        elif label == "Leads Generated":
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
                                f"{('$'+format(old,',.2f')) if old not in [None,0] and label!='Leads Generated' else (str(int(old)) if old not in [None,0] else '–')} ",
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
                    children=cards,
                ),
            ],
        ),

                
    ]
    #     )
    # ]

    
    return dashboard_sections

