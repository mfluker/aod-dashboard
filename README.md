# 📊 Art of Drawers Dashboard

This repository powers **Art of Drawers' internal analytics dashboard**, featuring a dynamic Dash dashboard and a secure Streamlit app for updating weekly data automatically from Canvas.

---

## ⚡ How This Works

1. **Update:** Run the Data Updater
2. **Push:** Updater automatically pushes the new data to GitHub, which then triggers Render to redeploy the dashboard.
3. **Deploy & View:** Wait 3 minutes, then view the live dashboard

---

## 🚀 Quick Start

Open these **2 central links** for a seamless weekly update:

* **Updater App**: [https://aod-dashboard-updater.streamlit.app/](https://aod-dashboard-updater.streamlit.app/)
* **Dashboard**: [https://aod-dashboard.onrender.com/](https://aod-dashboard.onrender.com/)

---

### Step 1: Run the Updater

1. Open the **Updater App** URL above.
2. If it hasn’t loaded, click the **red "Load Updater"** button (may take up to 30 seconds).
3. Follow instructions on the updater site:

   * Upload your `canvas_cookies.json`.
   * The app checks for missing weeks in `MasterData/*.parquet`.
   * If needed, it runs `data_fetcher.py` (\~1 minute) and pushes updates to GitHub.
4. Errors are usually due to the cookie file. Regenerate `canvas_cookies.json` and retry.

---

### Step 2: GitHub Push & Render Redeploy

* After the updater pushes to **GitHub**, Render detects changes automatically.
  * If run successfully, the MasterData file in the GitHub Repo should show that a update has been made   
* Redeployment takes **\~3 minutes**.
* Seeing a **502 Bad Gateway?** Wait 3 minutes, then paste the **Dashboard URL** into your browser.

---

### Step 3: View the Dashboard

* Visit **Dashboard** to see the latest data at the URL below:

  * [https://aod-dashboard.onrender.com/](https://aod-dashboard.onrender.com/)

---

That’s it—1 update, 1 push, 1 view. Happy reporting!
