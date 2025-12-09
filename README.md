# 📊 Art of Drawers Dashboard

This repository powers **Art of Drawers' internal analytics dashboard**, featuring a dynamic Dash dashboard and a secure Streamlit app for updating weekly data automatically from Canvas.

---

## ⚡ How This Works

1. **Update:** Run the Data Updater which collects new data from Canvas.
2. **Push:** Updater automatically pushes the new data to GitHub, which then triggers Render to deploy the dashboard.
3. **Deploy & View:** Wait 3 minutes, then view the live dashboard.

---

## 🚀 Step By Step Process


### Key URLs

Open these **2 links** for a seamless weekly update:

* **Updater App**: [https://aod-dashboard-updater.streamlit.app/](https://aod-dashboard-updater.streamlit.app/)
* **Dashboard**: [https://aod-dashboard.onrender.com/](https://aod-dashboard.onrender.com/)


### Step 1: Run the Updater

* Open the **Updater App** URL above.
    * If it hasn’t loaded, click the **red "Load Updater"** button (takes about 30 seconds).
* Follow instructions on the updater site:
    * Upload your `canvas_cookies.json`.
    * The app checks for if data is updated in `MasterData/*.parquet`.
    * If the data is not up to date, it runs `data_fetcher.py` (takes about 1 minute) and pushes the new data collected from Canvas, to GitHub.
* Errors are usually due to the cookie file. If errors occur, regenerate `canvas_cookies.json` and retry.


### Step 2: GitHub Push & Render Redeploy

* After the updater pushes to **GitHub**, Render detects changes automatically.
    * If run successfully, the MasterData file in the GitHub Repo should show that a update has been made   
* Redeployment takes roughly **3 minutes**.


### Step 3: View the Dashboard

* Click the **Dashboard URL** above.
* Seeing a **502 Bad Gateway?** Wait 3 minutes, then paste the **Dashboard URL** into your browser.

---

That's it. 1 update, 1 push, 1 view.

---

## 📚 Additional Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Complete technical guide for developers
  - How to add new metrics
  - Data flow diagrams
  - Code organization
  - Best practices

---

## 📊 Current Metrics

### Call Center Performance
- Inbound leads and bookings
- Outbound calls and bookings
- Help rates with conditional formatting

### Marketing ROI
- Amount invested
- Leads generated
- Revenue per appointment

All metrics include week-over-week comparisons.

---

## ➕ Adding New Metrics

See [ARCHITECTURE.md](ARCHITECTURE.md) for complete instructions on adding new metrics to the dashboard.

**Quick summary:**
1. Create fetcher function in `updater/data_fetcher.py`
2. Update storage in `updater/updater_utils.py`
3. Create visualization in `dashboard/dashboard_utils.py`
4. Add to dashboard sections

---

## 🔄 Recent Updates (Dec 2025)

- ✅ **Auto-backfill**: Updater now fetches ALL missing weeks automatically
- ✅ **Performance**: Removed slow Job Status Graph feature
- ✅ **Better UI**: Improved Streamlit updater with modern styling
- ✅ **Documentation**: Added comprehensive ARCHITECTURE.md guide

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Cookie expired | Re-export from Canvas using Cookie-Editor |
| Dashboard not updating | Check Render logs, verify Git push |
| Missing weeks | Updater auto-detects and fills gaps |
| Week-over-week shows "–" | Previous week missing, run updater |

---

Last Updated: December 9, 2025
