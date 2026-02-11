import streamlit as st
import json
import subprocess
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from datetime import date

from updater_utils import load_master_data, fetch_and_append_week_if_needed, get_last_full_week, append_projections_if_needed

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="AoD Data Updater",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .main > div {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    .hero-section {
        background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
        color: white;
        padding: 2rem;
        border-radius: 8px;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .hero-title {
        font-size: 2.2rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    
    .hero-subtitle {
        font-size: 1.1rem;
        opacity: 0.9;
    }
    
    .step-card {
        background: #f8f9fa;
        border: 1px solid #e1e8ed;
        border-radius: 6px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }
    
    .step-number {
        background: #2c3e50;
        color: white;
        border-radius: 50%;
        width: 28px;
        height: 28px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-weight: 600;
        font-size: 0.9rem;
        margin-right: 12px;
    }
    
    .success-box {
        background: #d4edda;
        color: #155724;
        border: 1px solid #c3e6cb;
        padding: 1rem;
        border-radius: 6px;
        margin: 1rem 0;
        text-align: center;
    }
    
    .error-box {
        background: #f8d7da;
        color: #721c24;
        border: 1px solid #f5c6cb;
        padding: 1rem;
        border-radius: 6px;
        margin: 1rem 0;
        text-align: center;
    }
    
    .info-box {
        background: #d1ecf1;
        color: #0c5460;
        border: 1px solid #bee5eb;
        padding: 1rem;
        border-radius: 6px;
        margin: 1rem 0;
        text-align: center;
    }
    
    .upload-section {
        background: white;
        border: 2px dashed #2c3e50;
        border-radius: 8px;
        padding: 2rem;
        text-align: center;
        margin: 2rem 0;
    }
    
    .info-section {
        background: #f8f9fa;
        border-left: 4px solid #2c3e50;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
    }
    
    .instructions-section {
        background: #f8f9fa;
        border: 1px solid #e1e8ed;
        border-radius: 6px;
        padding: 1.5rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# --- GET LAST UPDATE INFO ---
def get_last_data_update():
    """Get the timestamp of the last data update from parquet files"""
    from pathlib import Path
    from datetime import datetime

    master_data_dir = Path(__file__).resolve().parent.parent / "dashboard" / "Master_Data"
    roi_file = master_data_dir / "all_roi_data.parquet"

    try:
        if roi_file.exists():
            mtime = roi_file.stat().st_mtime
            dt = datetime.fromtimestamp(mtime)
            return dt.strftime("%B %d, %Y at %I:%M %p")
        return "Unknown"
    except:
        return "Unknown"

last_update = get_last_data_update()

# --- HERO SECTION ---
st.markdown(f"""
<div class="hero-section">
    <div class="hero-title">📦 AoD Data Updater</div>
    <div class="hero-subtitle">Fetch and push weekly data updates to your dashboard</div>
    <div style="margin-top: 10px; font-size: 0.9rem; opacity: 0.8;">
        Last Data Update: {last_update}
    </div>
</div>
""", unsafe_allow_html=True)

# --- INSTRUCTIONS SECTION ---
st.markdown("## Getting Started")

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div class="step-card">
        <div style="display: flex; align-items: center; margin-bottom: 1rem;">
            <div class="step-number">1</div>
            <strong>Login to Canvas</strong>
        </div>
        <p>Open Canvas in a new tab and log in to your account.</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('[🔗 Open Canvas Login](https://canvas.artofdrawers.com)')

with col2:
    st.markdown("""
    <div class="step-card">
        <div style="display: flex; align-items: center; margin-bottom: 1rem;">
            <div class="step-number">2</div>
            <strong>Upload Cookies</strong>
        </div>
        <p>Return to this tab and upload your canvas_cookies.json file below.</p>
    </div>
    """, unsafe_allow_html=True)

# --- COOKIE INSTRUCTIONS EXPANDER ---
with st.expander("How to get your canvas_cookies.json file", expanded=False):
    st.markdown("**Follow these steps to generate your canvas_cookies.json file:**")
    
    steps = [
        "Open [Canvas in Chrome](https://canvas.artofdrawers.com)",
        "Install the [Cookie-Editor Extension](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndedbemlkljdomclgjgkkdggpac)",
        "In Canvas, click on the Cookie-Editor Extension",
        "Keep only the **PHPSESSID** and **username** cookies",
        "Click the **Export** button at the top of the extension",
        "Visit [JSON Editor Online](https://jsoneditoronline.org/)",
        "Paste the cookies into the 'New Document 1' text box on the left",
        "Click the **save** button, then 'Save to Disk'",
        "Name the file **canvas_cookies.json** and click **Save**",
        "You now have your canvas_cookies.json file!"
    ]
    
    for i, step in enumerate(steps, 1):
        st.write(f"{i}. {step}")

# --- UPLOAD SECTION ---
st.markdown("## Upload Your Canvas Cookies File")

uploaded_cookie = st.file_uploader(
    "Choose your canvas_cookies.json file",
    type="json",
    help="Upload your canvas_cookies.json file from Canvas"
)

# --- HELPER FUNCTIONS ---
def get_expiration_date(cookie_bytes):
    try:
        cookies = json.load(cookie_bytes)
        expiration_timestamps = [
            int(cookie.get("expirationDate"))
            for cookie in cookies if "expirationDate" in cookie
        ]
        if not expiration_timestamps:
            return None
        latest_exp = max(expiration_timestamps)
        return datetime.fromtimestamp(latest_exp)
    except Exception:
        return None

def cookie_valid(cookie_file) -> bool:
    try:
        cookies = json.load(cookie_file)
        cookie_file.seek(0)
        exp_ts = max(c.get("expirationDate", 0) for c in cookies)
        return datetime.fromtimestamp(exp_ts) > datetime.now()
    except Exception:
        return False

# --- COOKIE VALIDATION ---
valid_cookies = False
cookie_exp = None

if uploaded_cookie:
    cookie_exp = get_expiration_date(uploaded_cookie)
    uploaded_cookie.seek(0)

    if cookie_exp:
        if cookie_exp < datetime.now():
            st.markdown(f"""
            <div class="error-box">
                <div style="font-weight: 600; margin-bottom: 0.5rem;">
                    ❌ Cookie Expired
                </div>
                <div>
                    Your cookies expired on: <strong>{cookie_exp.strftime('%Y-%m-%d %H:%M:%S')}</strong>
                </div>
                <div style="margin-top: 0.5rem;">
                    Please follow the instructions below to get a new canvas_cookies.json file.
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("### Get Fresh Cookies")
            st.markdown("""
            <div class="instructions-section">
                <strong>Follow these steps to generate a new canvas_cookies.json file:</strong>
            </div>
            """, unsafe_allow_html=True)
            
            steps = [
                "Open [Canvas in Chrome](https://canvas.artofdrawers.com)",
                "Install the [Cookie-Editor Extension](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndedbemlkljdomclgjgkkdggpac)",
                "In Canvas, click on the Cookie-Editor Extension",
                "Keep only the **PHPSESSID** and **username** cookies",
                "Click the **Export** button at the top of the extension",
                "Visit [JSON Editor Online](https://jsoneditoronline.org/)",
                "Paste the cookies into the 'New Document 1' text box on the left",
                "Click the **save** button, then 'Save to Disk'",
                "Name the file **canvas_cookies.json** and click **Save**",
                "You now have your new canvas_cookies.json file!"
            ]
            
            for i, step in enumerate(steps, 1):
                st.write(f"{i}. {step}")
            
        else:
            st.markdown(f"""
            <div class="success-box">
                <div style="font-weight: 600; margin-bottom: 0.5rem;">
                    ✅ Cookies Valid
                </div>
                <div>
                    Expires on: <strong>{cookie_exp.strftime('%Y-%m-%d %H:%M:%S')}</strong>
                </div>
            </div>
            """, unsafe_allow_html=True)
            valid_cookies = True
            # Save cookies to the updater directory where data_fetcher.py expects them
            cookie_dest = Path(__file__).resolve().parent / "canvas_cookies.json"
            cookie_dest.write_bytes(uploaded_cookie.read())
    else:
        st.markdown("""
        <div class="error-box">
            <div style="font-weight: 600; margin-bottom: 0.5rem;">
                ❌ Invalid Cookie File
            </div>
            <div>
                Could not read the cookie file. Please check the format and try again.
            </div>
        </div>
        """, unsafe_allow_html=True)

# --- FETCH AND PUSH SECTION ---
if valid_cookies:
    st.markdown("## Update Your Dashboard Data")

    st.markdown("""
    <div class="info-section">
        <strong>Ready to update!</strong> This will fetch the latest weekly data and push it to your GitHub dashboard repository.
    </div>
    """, unsafe_allow_html=True)

    if st.button("🔄 Fetch + Push Weekly Data", type="primary"):
        with st.status("📦 Fetching new data if needed...", expanded=True) as status:
            try:
                # Load existing data
                jobs_df, calls_df, roi_df = load_master_data()

                # Debug information
                st.write("📊 Current data status:")
                if not calls_df.empty:
                    import pandas as pd
                    earliest = pd.to_datetime(calls_df["week_start"]).min().strftime("%m/%d/%Y")
                    latest_end = calls_df['week_end'].max()
                    st.write(f"• Data range: {earliest} to {latest_end}")

                    # Count unique weeks
                    unique_weeks = calls_df[['week_start', 'week_end']].drop_duplicates()
                    st.write(f"• Unique weeks in data: {len(unique_weeks)}")
                else:
                    st.write("• No existing data")
                st.write(f"• Last full week available: {get_last_full_week(date.today())[1]}")

                # Check for missing weeks BEFORE fetching
                from updater_utils import get_all_missing_weeks
                status.update(label="🔍 Checking for ALL missing weeks (including historical gaps)...")
                missing_weeks = get_all_missing_weeks(calls_df)

                if missing_weeks:
                    st.warning(f"⚠️ Found **{len(missing_weeks)}** missing week(s) that will be backfilled:")
                    # Show first 5 and last 5 if there are many
                    if len(missing_weeks) <= 10:
                        for start, end in missing_weeks:
                            st.write(f"  • {start} – {end}")
                    else:
                        for start, end in missing_weeks[:5]:
                            st.write(f"  • {start} – {end}")
                        st.write(f"  ... ({len(missing_weeks) - 10} more weeks) ...")
                        for start, end in missing_weeks[-5:]:
                            st.write(f"  • {start} – {end}")
                    st.write(f"\n🔄 This will fetch Call Center and ROI data for all {len(missing_weeks)} weeks...")
                else:
                    st.success("✅ No missing weeks detected! All historical data is complete.")

                # Fetch and append new data if needed
                status.update(label=f"📦 Fetching {len(missing_weeks)} missing week(s)..." if missing_weeks else "✅ Data up to date")
                jobs_df_updated, calls_df_updated, roi_df_updated = fetch_and_append_week_if_needed(jobs_df, calls_df, roi_df)

                # Show what was done
                if missing_weeks:
                    new_weeks_count = len(calls_df_updated[['week_start', 'week_end']].drop_duplicates()) - len(unique_weeks)
                    st.markdown(f"""
                    <div class="success-box">
                        ✅ Successfully fetched {len(missing_weeks)} missing week(s)!<br>
                        📊 Total weeks now: {len(calls_df_updated[['week_start', 'week_end']].drop_duplicates())} (added {new_weeks_count})
                    </div>
                    """, unsafe_allow_html=True)
                    jobs_df, calls_df, roi_df = jobs_df_updated, calls_df_updated, roi_df_updated
                else:
                    st.markdown("""
                    <div class="info-box">
                        ℹ️ No new data to fetch - all weeks are already present!
                    </div>
                    """, unsafe_allow_html=True)

                # Fetch projections data (location rankings and future appointments)
                status.update(label="📍 Fetching location rankings and future appointments...")
                st.write("📍 **Fetching Location Performance Data...**")

                try:
                    rpa_df, sales_df, appts_df = append_projections_if_needed()

                    if not rpa_df.empty or not sales_df.empty or not appts_df.empty:
                        st.markdown(f"""
                        <div class="success-box">
                            ✅ Successfully fetched projections data!<br>
                            📊 RPA Rankings: {len(rpa_df)} locations<br>
                            📊 Sales Rankings: {len(sales_df)} locations<br>
                            📊 Future Appointments: {len(appts_df)} appointments
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div class="info-box">
                            ℹ️ Projections data already up to date!
                        </div>
                        """, unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"⚠️ Error fetching projections data: {e}")
                    st.write("Continuing with main data update...")

                # --- COMMIT AND PUSH TO GITHUB ---
                status.update(label="🛠 Cloning dashboard repo...")
                token = st.secrets["GH_TOKEN"]
                repo = st.secrets["GH_REPO"]
                username = st.secrets["GH_USERNAME"]
                remote_url = f"https://{username}:{token}@github.com/{repo}.git"

                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_path = Path(tmpdir)
                    subprocess.run(["git", "clone", remote_url, str(tmp_path)], check=True)

                    status.update(label="📂 Copying updated Parquet files...")
                    dest = tmp_path / "dashboard" / "Master_Data"
                    dest.mkdir(exist_ok=True)
                    # Use absolute path to Master_Data directory
                    master_data_dir = Path(__file__).resolve().parent.parent / "dashboard" / "Master_Data"

                    # Debug: Show which files are being copied
                    parquet_files = list(master_data_dir.glob("*.parquet"))
                    st.write(f"📁 Copying {len(parquet_files)} parquet file(s) from {master_data_dir}")
                    for f in parquet_files:
                        st.write(f"  • {f.name}")
                        shutil.copy(f, dest / f.name)
            
                    subprocess.run(["git", "config", "--global", "user.name", "AoD Updater Bot"], check=True)
                    subprocess.run(["git", "config", "--global", "user.email", "updater@app.aod"], check=True)
            
                    subprocess.run(["git", "add", "dashboard/Master_Data/*.parquet"], cwd=tmp_path, check=True)
                    
                    # CHECK if there's anything to commit
                    result = subprocess.run(
                        ["git", "status", "--porcelain"], cwd=tmp_path, capture_output=True, text=True
                    )
            
                    if result.stdout.strip() == "":
                        st.markdown("""
                        <div class="info-box">
                            ℹ️ Parquet files already up to date. No commit necessary.
                        </div>
                        """, unsafe_allow_html=True)
                        status.update(label="✔️ Data already up to date!", state="complete")
                    else:
                        today_str = date.today().strftime("%Y-%m-%d")
                        commit_message = f"🔄 Weekly data update via Streamlit ({today_str})"
            
                        subprocess.run(["git", "commit", "-m", commit_message], cwd=tmp_path, check=True)
                        subprocess.run(["git", "push", "origin", "main"], cwd=tmp_path, check=True)
                        
                        st.markdown("""
                        <div class="success-box">
                            <div style="font-weight: 600; margin-bottom: 0.5rem;">
                                🎉 Success!
                            </div>
                            <div>
                                Data has been successfully pushed to GitHub!
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        status.update(label="✅ Data pushed to GitHub!", state="complete")
            
            except subprocess.CalledProcessError as e:
                st.markdown(f"""
                <div class="error-box">
                    <div style="font-weight: 600; margin-bottom: 0.5rem;">
                        ❌ Git Push Failed
                    </div>
                    <div>
                        {str(e)}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                status.update(label="❌ Git push failed", state="error")
                
            except Exception as e:
                st.markdown(f"""
                <div class="error-box">
                    <div style="font-weight: 600; margin-bottom: 0.5rem;">
                        ❌ Data Fetch Failed
                    </div>
                    <div>
                        {str(e)}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                status.update(label="❌ Data fetch failed", state="error")

# --- FOOTER ---
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.9rem; margin-top: 2rem;">
    <p>📦 AoD Data Updater - Keep your dashboard current with the latest weekly data</p>
</div>
""", unsafe_allow_html=True)


