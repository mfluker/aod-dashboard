# AoD Dashboard Architecture Guide

## 📁 Project Structure

```
AoD_Dashboard/
├── dashboard/                      # Production dashboard (deployed on Render)
│   ├── render_app.py              # Entry point - loads data and sets up Dash app
│   ├── dashboard_utils.py         # Core visualization logic
│   ├── Master_Data/               # Parquet data files (the single source of truth)
│   │   ├── all_call_center_data.parquet
│   │   └── all_roi_data.parquet
│   └── requirements.txt
│
├── updater/                       # Data fetching tool (run locally via Streamlit)
│   ├── streamlit_app.py          # Streamlit UI for updating data
│   ├── updater_utils.py          # Update orchestration logic
│   ├── data_fetcher.py           # Canvas CRM scraping functions
│   ├── metrics/                  # ⭐ NEW: Modular metric definitions
│   │   ├── __init__.py
│   │   ├── base.py              # Base metric class
│   │   ├── call_center.py       # Call center metric
│   │   └── roi.py               # ROI metric
│   └── requirements.txt
│
└── Master_Data_Backup/           # Manual backups
```

---

## 🎯 Current Metrics

### 1. Call Center Performance
- **Source**: Canvas CRM Call Center Report
- **Frequency**: Weekly (Sunday-Saturday)
- **Data Points**:
  - Inbound: Lead count, booked count, help rate
  - Outbound: Call count, booked count, help rate
- **Visualization**: Two side-by-side tables with conditional formatting

### 2. Marketing ROI
- **Source**: Canvas CRM Marketing ROI Page
- **Frequency**: Weekly
- **Data Points**:
  - Amount Invested
  - Leads Generated
  - Revenue Per Appointment
- **Visualization**: Three metric cards with week-over-week comparison

---

## 🔧 How Data Flows

### Weekly Update Process (via Streamlit Updater)

```
1. User uploads canvas_cookies.json
   ↓
2. Streamlit app loads existing Parquet files
   ↓
3. System identifies ALL missing weeks (from last data to today)
   ↓
4. For each missing week:
   ├─ Fetch Call Center data (inbound + outbound)
   ├─ Fetch ROI data
   └─ Append to DataFrames
   ↓
5. Save updated Parquet files
   ↓
6. Git commit + push to GitHub
   ↓
7. Render auto-deploys updated dashboard
```

### Dashboard Rendering Process

```
1. render_app.py loads Parquet files into memory (once at startup)
   ↓
2. User selects a week from dropdown
   ↓
3. dashboard_utils.update_dashboard() filters data by week
   ↓
4. Generates visualizations:
   ├─ Call Center tables
   └─ ROI metric cards
   ↓
5. Returns Dash layout to user
```

---

## ➕ How to Add a New Metric

### Quick Steps:

1. **Create metric fetcher** in `data_fetcher.py`
   - Add a function like `fetch_YOUR_METRIC(start_date, end_date, session)`
   - Returns a DataFrame with columns + `week_start` and `week_end`

2. **Update Parquet storage** in `updater_utils.py`
   - Add new Parquet file path (e.g., `all_YOUR_METRIC_data.parquet`)
   - Update `load_master_data()` to load your new file
   - Update `fetch_and_append_week_if_needed()` to fetch your metric

3. **Create visualization** in `dashboard_utils.py`
   - Add a function like `build_YOUR_METRIC_viz(df, ...)`
   - Returns Dash HTML components

4. **Add to dashboard** in `dashboard_utils.py`
   - Update `update_dashboard()` to include your new section
   - Add to `dashboard_sections` list

### Example: Adding "Customer Satisfaction" Metric

#### Step 1: Fetch the data (`data_fetcher.py`)

```python
def fetch_customer_satisfaction(start_date: str, end_date: str, session: requests.Session) -> pd.DataFrame:
    """
    Fetch customer satisfaction data from Canvas for a given week.
    """
    url = "https://canvas.artofdrawers.com/YOUR_REPORT_URL"
    params = {
        "start_date": start_date,
        "end_date": end_date,
    }

    response = session.get(url, params=params)
    response.raise_for_status()

    # Parse the response (CSV, JSON, or HTML)
    df = pd.read_csv(StringIO(response.text))

    # Add week identifiers
    df["week_start"] = start_date
    df["week_end"] = end_date

    return df
```

#### Step 2: Store the data (`updater_utils.py`)

```python
# In load_master_data()
sat_path = master_data_dir / "all_customer_satisfaction_data.parquet"
sat_df = pd.read_parquet(sat_path)
return jobs_df, calls_df, roi_df, sat_df  # Add to return

# In fetch_and_append_week_if_needed()
sat_path = base_dir / "all_customer_satisfaction_data.parquet"

# Inside the missing weeks loop:
print(f"  😊 Fetching Customer Satisfaction data...")
new_sat = data_fetcher.fetch_customer_satisfaction(start, end, session)
sat_df = pd.concat([sat_df, new_sat], ignore_index=True)

# In the save section:
sat_df.to_parquet(sat_path, index=False)
```

#### Step 3: Visualize (`dashboard_utils.py`)

```python
def build_satisfaction_metrics(sat_df: pd.DataFrame) -> html.Div:
    """
    Build customer satisfaction visualization.
    """
    avg_rating = sat_df["rating"].mean()
    total_responses = len(sat_df)

    return html.Div([
        html.H2("Customer Satisfaction"),
        html.Div(f"Average Rating: {avg_rating:.1f}/5"),
        html.Div(f"Total Responses: {total_responses}"),
    ])
```

#### Step 4: Add to dashboard (`dashboard_utils.py`)

```python
# In update_dashboard():
sat_df = sat_all_df[
    (sat_all_df["week_start"] == start_csv) &
    (sat_all_df["week_end"] == end_csv)
]

sat_viz = build_satisfaction_metrics(sat_df)

# In dashboard_sections:
dashboard_sections = [
    # ... existing sections ...
    sat_viz,  # Add your new section
]
```

---

## 📝 Best Practices

### Data Fetching
- ✅ Always add `week_start` and `week_end` columns
- ✅ Handle empty responses gracefully
- ✅ Use session object for authentication
- ✅ Add print statements for debugging

### Data Storage
- ✅ Use Parquet format (efficient + supports complex types)
- ✅ One file per metric type
- ✅ Never edit historical data directly (append only)

### Visualization
- ✅ Use consistent color scheme (`#2C3E70` for primary)
- ✅ Add week-over-week comparisons where applicable
- ✅ Mobile-friendly layouts (use Dash responsive grid)

### Code Organization
- ✅ Keep fetchers in `data_fetcher.py`
- ✅ Keep orchestration in `updater_utils.py`
- ✅ Keep visualizations in `dashboard_utils.py`
- ✅ Comment out old code instead of deleting

---

## 🐛 Troubleshooting

### "No data for selected week"
→ Check that the week exists in the Parquet file
→ Run the updater to fetch missing weeks

### "Cookie expired"
→ Re-export cookies from Canvas using Cookie-Editor extension

### "Dashboard not updating after push"
→ Check Render logs for deployment errors
→ Ensure Parquet files were pushed to GitHub

### "Week-over-week comparison shows '–'"
→ Previous week data might be missing
→ Run updater to backfill historical data

---

## 🔐 Security Notes

- ✅ Never commit `canvas_cookies.json` to Git
- ✅ Store GitHub token in `.streamlit/secrets.toml` (gitignored)
- ✅ Dashboard has NO secrets (read-only from static files)
- ✅ Updater runs locally (never deployed)

---

## 📊 Current Data Schema

### Call Center Data
```python
{
    "Call Center Rep": str,
    "Inbound Lead Count": int,
    "Inbound Booked Count": int,
    "Inbound Help Rate (%)": str,
    "Inbound Rate Value": float,
    "Outbound Call Count": int,
    "Outbound Booked Count": int,
    "Outbound Help Rate (%)": str,
    "Outbound Communication Count": int,
    "mode": str,  # "inbound" or "outbound"
    "week_start": str,  # "MM/DD/YYYY"
    "week_end": str,    # "MM/DD/YYYY"
}
```

### ROI Data
```python
{
    "Amount Invested": str,  # "$1,234.56"
    "# of Leads": str,       # "123"
    "Revenue Per Appt": str, # "$1,234.56"
    # ... other campaign metrics
    "week_start": str,
    "week_end": str,
}
```

---

## 🚀 Deployment

### Dashboard (Render)
- **Trigger**: Git push to `main` branch
- **Build**: `pip install -r dashboard/requirements.txt`
- **Start**: `python dashboard/render_app.py`
- **Environment**: `PORT` provided by Render

### Updater (Local)
- **Run**: `streamlit run updater/streamlit_app.py`
- **Requirements**: `canvas_cookies.json` + `.streamlit/secrets.toml`

---

Last updated: 2025-12-09
