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

That’s it. 1 update, 1 push, 1 view.
