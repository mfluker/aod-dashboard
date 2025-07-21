# 🖥️ Art of Drawers Dashboard

A streamlined dashboard built with [Dash](https://dash.plotly.com/) and hosted on [Render](https://render.com), used for internal reporting of Jobs, Call Center, and Marketing ROI data.

---

## 🔄 How It Works

This dashboard **does not connect to Canvas directly**. All data is pre-fetched and maintained by the companion app [`aod-updater`](https://github.com/mfluker/aod-updater), which:

- Authenticates with Canvas using a JSON cookie
- Pulls weekly Jobs, Call Center, and ROI data
- Appends it to master `.parquet` files
- Pushes only the updated data into this repo's `MasterData/` folder

When data is pushed to GitHub, **Render automatically redeploys** the dashboard with fresh insights.

---

## 📁 Data Structure

All data is stored as `.parquet` files under:

