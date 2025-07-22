import streamlit as st
import json
import subprocess
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from datetime import date

from updater_utils import load_master_data, fetch_and_append_week_if_needed, get_last_full_week


# --- SETUP ---
st.set_page_config(page_title="📦 AoD Data Updater", layout="centered")
st.title("📦 AoD Weekly Data Updater")

st.markdown("""
1. **[Log in to Canvas](https://canvas.artofdrawers.com)** in another tab  
2. Upload your `canvas_cookies.json` file below  
""")

# --- COOKIE UPLOAD ---
cookie_file = st.file_uploader("Upload `canvas_cookies.json`", type="json")

def cookie_valid(cookie_file) -> bool:
    try:
        cookies = json.load(cookie_file)
        cookie_file.seek(0)
        exp_ts = max(c.get("expirationDate", 0) for c in cookies)
        return datetime.fromtimestamp(exp_ts) > datetime.now()
    except Exception:
        return False

if cookie_file:
    if not cookie_valid(cookie_file):
        st.error("❌ Cookie is invalid or expired.")
        st.stop()
    st.success("✅ Cookie is valid.")
    Path("canvas_cookies.json").write_bytes(cookie_file.read())


# --- FETCH AND PUSH LOGIC ---
if cookie_file and st.button("🔄 Fetch + Push Weekly Data"):
    with st.status("📦 Fetching new data if needed...", expanded=True) as status:
        jobs_df, calls_df, roi_df = load_master_data()

        
        print("JOBS latest week_end:", jobs_df['week_end'].max())
        print("CALLS latest week_end:", calls_df['week_end'].max())
        print("ROI latest week_end:", roi_df['week_end'].max())
        print("Expected week_end for fetch:", get_last_full_week(date.today())[1])
        print("Last full week is:", get_last_full_week(date.today()))


        try:
            jobs_df, calls_df, roi_df = fetch_and_append_week_if_needed(jobs_df, calls_df, roi_df)
            st.success("✅ Parquet files updated.")
        except Exception as e:
            st.error(f"❌ Data fetch failed: {e}")
            st.stop()

        # --- COMMIT AND PUSH TO GITHUB ---
        status.update(label="🛠 Cloning dashboard repo...")
        token = st.secrets["GH_TOKEN"]
        repo = st.secrets["GH_REPO"]
        username = st.secrets["GH_USERNAME"]
        remote_url = f"https://{username}:{token}@github.com/{repo}.git"
        
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                subprocess.run(["git", "clone", remote_url, str(tmp_path)], check=True)
        
                status.update(label="📂 Copying updated Parquet files...")
                dest = tmp_path / "dashboard" / "Master_Data"
                dest.mkdir(exist_ok=True)
                for f in Path("dashboard/Master_Data").glob("*.parquet"):
                    shutil.copy(f, dest / f.name)
        
                subprocess.run(["git", "config", "--global", "user.name", "AoD Updater Bot"], check=True)
                subprocess.run(["git", "config", "--global", "user.email", "updater@app.aod"], check=True)
        
                subprocess.run(["git", "add", "dashboard/Master_Data/*.parquet"], cwd=tmp_path, check=True)
                
                # CHECK if there's anything to commit
                result = subprocess.run(
                    ["git", "status", "--porcelain"], cwd=tmp_path, capture_output=True, text=True
                )
        
                if result.stdout.strip() == "":
                    st.info("✅ Parquet files already up to date. No commit necessary.")
                    status.update(label="✔️ Skipped Git commit.", state="complete")
                else:
                    from datetime import date
                    today_str = date.today().strftime("%Y-%m-%d")
                    commit_message = f"🔄 Weekly data update via Streamlit ({today_str})"
        
                    subprocess.run(["git", "commit", "-m", commit_message], cwd=tmp_path, check=True)
                    subprocess.run(["git", "push", "origin", "main"], cwd=tmp_path, check=True)
                    status.update(label="✅ Data pushed to GitHub!", state="complete")
        
        except subprocess.CalledProcessError as e:
            st.error("❌ Git push failed.")
            st.code(str(e))


