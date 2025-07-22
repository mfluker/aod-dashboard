# 📊 Art of Drawers Dashboard

This repository powers **Art of Drawers' internal analytics tools**, including a dynamic Dash dashboard and a secure Streamlit app for updating weekly data from Canvas.

---

## 🔧 Repo Structure

```
AoD_Dashboard/
├── dashboard/              # Dash app deployed via Render
│   ├── render_app.py       # Main dashboard entrypoint
│   ├── dashboard_utils.py  # All core logic & visuals
│   ├── requirements.txt    # Dash app dependencies
│   └── render.yaml         # Render deployment config
│
├── updater/                # Streamlit app for fetching + pushing data
│   ├── streamlit_app.py    # Streamlit entrypoint
│   ├── requirements.txt    # Streamlit-specific dependencies
│
├── MasterData/             # Central location for Parquet datasets
│   ├── all_jobs_data.parquet
│   ├── all_call_center_data.parquet
│   └── all_roi_data.parquet
│
└── data_fetcher.py         # Secure API logic for retrieving Canvas data
```

---

## 🖥️ The Dashboard (`dashboard/`)

### Features
- Weekly breakdown of job pipeline by order type and status
- Call center metrics with YoY and WoW changes
- Inbound/Outbound performance tables
- ROI card metrics (Leads, Revenue per Appt, Ad Spend)
- Franchisee filtering

### How It Works
- Pulls data **only** from `MasterData/*.parquet`
- **Never contacts Canvas directly**
- Automatically redeploys on Render when new data is pushed to GitHub

---

## 🔁 The Updater (`updater/`)

### Purpose
Fetch new weekly data from Canvas, append it to existing `.parquet` files, and commit + push changes to GitHub — which automatically triggers a dashboard redeploy via Render.

### How It Works
1. Upload your `canvas_cookies.json` in the Streamlit UI
2. App validates the cookie
3. Pulls any **missing weeks** of data using `data_fetcher.py`
4. Appends new rows to files in `MasterData/`
5. Pushes updated `.parquet` files to the GitHub repo using your `GH_TOKEN`

---

## 📁 MasterData Directory

All final `.parquet` files live in:

```
AoD_Dashboard/MasterData/
```

These are the only files used by the dashboard:
- `all_jobs_data.parquet`
- `all_call_center_data.parquet`
- `all_roi_data.parquet`

This directory is **only modified by the Streamlit updater**, not the dashboard.

---

## 🚀 Deploying to Render

Render uses the `render.yaml` located in `dashboard/`:

```yaml
services:
  - type: web
    name: aod-dashboard
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python render_app.py
    plan: free
```

Make sure that:
- The `dashboard/requirements.txt` file includes all Dash dependencies
- Your `MasterData/` folder is committed and kept in the root (`AoD_Dashboard/MasterData`)
- Any updates from the updater are committed to GitHub to trigger redeploys

---

## 🧠 Notes & Best Practices

- Only the updater should write to `MasterData/`
- The dashboard never fetches live Canvas data
- You do **not** need cookie or GitHub secrets in your Render deployment — it's read-only
- Keep updater secrets in `.streamlit/secrets.toml`

---

## 🪪 Auth Setup for Updater

In `.streamlit/secrets.toml` (not tracked by Git), include:

```toml
GH_TOKEN = "your_personal_token"
GH_REPO = "mfluker/aod-dashboard"
GH_USERNAME = "mfluker"
```

---

## ✅ You're Ready!

- Run the Streamlit updater weekly
- Push to GitHub from there
- Let Render auto-refresh your dashboard
