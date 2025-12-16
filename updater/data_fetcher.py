# data_fetcher_Copy1.py
import os
import json
import requests
import pandas as pd
import re

from io import StringIO
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import quote_plus

import requests
import pandas as pd
from bs4 import BeautifulSoup


# ─── 0. Cookie Loader ─────────────────────────────────────────────────────────

# # For RENDER!
# def get_session_with_canvas_cookie(cookie_path="/etc/secrets/canvas_cookies.json"):
#     import json
#     session = requests.Session()
#     with open(cookie_path, "r") as f:
#         cookies = json.load(f)
#     for cookie in cookies:
#         session.cookies.set(cookie['name'], cookie['value'])
#     return session

# # For Testing!

COOKIE_PATH = "canvas_cookies.json"


def validate_canvas_cookies(cookie_path=None):
    """
    Validate that Canvas cookies exist and are not expired.
    Returns: (is_valid, message)
    """
    if cookie_path is None:
        cookie_path = COOKIE_PATH

    from datetime import datetime
    from pathlib import Path

    # Check if file exists
    if not Path(cookie_path).exists():
        return False, f"Cookie file not found at: {cookie_path}"

    try:
        with open(cookie_path, "r") as f:
            cookies = json.load(f)

        if not cookies:
            return False, "Cookie file is empty"

        # Check for required cookies
        cookie_names = [c.get("name") for c in cookies]
        required = ["PHPSESSID", "username"]
        missing = [r for r in required if r not in cookie_names]

        if missing:
            return False, f"Missing required cookies: {missing}"

        # Check expiration
        now = datetime.now()
        expired_cookies = []

        for cookie in cookies:
            name = cookie.get("name")
            if "expirationDate" in cookie:
                exp_timestamp = int(cookie["expirationDate"])
                exp_date = datetime.fromtimestamp(exp_timestamp)
                if exp_date < now:
                    expired_cookies.append(f"{name} (expired {exp_date.strftime('%Y-%m-%d %H:%M')})")

        if expired_cookies:
            return False, f"Expired cookies: {', '.join(expired_cookies)}"

        return True, "Cookies are valid"

    except Exception as e:
        return False, f"Error reading cookies: {str(e)}"


def get_session_with_canvas_cookie():
    """
    Load cookies from COOKIE_PATH and return a requests.Session
    that only sets name, value, domain, path, secure, and expires.
    """
    with open(COOKIE_PATH, "r") as f:
        raw_cookies = json.load(f)

    session = requests.Session()
    for c in raw_cookies:
        # required:
        name = c.get("name")
        value = c.get("value")

        # optional but valid in requests:
        params = {}
        if "domain" in c:
            params["domain"] = c["domain"]
        if "path" in c:
            params["path"] = c["path"]
        if "secure" in c:
            params["secure"] = c["secure"]
        if "expirationDate" in c:
            # requests wants 'expires' (an int)
            params["expires"] = int(c["expirationDate"])

        session.cookies.set(name, value, **params)

    return session


# ─── 1. JOBS-STATUS SCRAPER ─────────────────────────────────────────────────── (COMMENTED OUT - REMOVED)

# STATUS_FILTERS = {
#     "Measurement Appointment Scheduled": 2,
#     "Measurement Approved": 23,
#     "Submitted to Manufacturing Partner": 5,
#     "Order Shipped": 6,
#     "Order Received": 37,
#     "Install Scheduled": 8,
#     "Installed": 9,
#     "Complete": 13,
# }
#
# TEMPLATE_URL = """
# https://canvas.artofdrawers.com/listjobs.html?dsraas=1&id=&location_id=&zone=&zone_id=&production_priority_ge=&production_priority_le=&opportunity=&opportunity_id=&customer=&customer_id=&campaign_source=&customer_id_sub_filters_campaign_source_id=&customer_id_sub_filters_firstname=&customer_id_sub_filters_lastname=&customer_id_sub_filters_spouse=&customer_id_sub_filters_preferred_phone=&customer_id_sub_filters_cell_phone=&customer_id_sub_filters_emailaddr=&city=&state_id=&country_id=&latitude_ge=&latitude_le=&longitude_ge=&longitude_le=&location_tax_rate_id=&total_cost_ge=&total_cost_le=&material_total_ge=&material_total_le=&labor_total_ge=&labor_total_le=&delivery_total_ge=&delivery_total_le=&discount_total_ge=&discount_total_le=&credit_memo_total_ge=&credit_memo_total_le=&tax_total_ge=&tax_total_le=&order_total_ge=&order_total_le=&amount_paid_ge=&amount_paid_le=&amount_due_ge=&amount_due_le=&designer_id=&tma_id=&relationship_partner_id=&installer_id=&shipping_type_id=&number_of_items_ge=&number_of_items_le=&manufacturing_batch_id=&manufacturing_facility_id=&manufacturing_status_id=&date_submitted_to_manufacturing_ge=&date_submitted_to_manufacturing_le=&date_submitted_to_manufacturing_r=select&number_of_days_ago_submitted_to_go_ge=&number_of_days_ago_submitted_to_go_le=&number_of_biz_days_at_manufacturing_status_ge=&number_of_biz_days_at_manufacturing_status_le=&date_submitted_to_manufacturing_partner_ge=&date_submitted_to_manufacturing_partner_le=&date_submitted_to_manufacturing_partner_r=select&date_projected_to_ship_ge=&date_projected_to_ship_le=&date_projected_to_ship_r=select&date_shipped_ge=&date_shipped_le=&date_shipped_r=select&carrier_id=&tracking_number=&date_delivered_ge=&date_delivered_le=&date_delivered_r=select&commission_rate_type_id=&designer_commission_override_percentage_ge=&designer_commission_override_percentage_le=&tma_commission_rate_type_id=&tma_commission_has_been_paid_y=y&tma_commission_has_been_paid_n=n&job_type_id=&current_status_ids%5B%5D=2&current_status_ids%5B%5D=3&current_status_ids%5B%5D=5&current_status_ids%5B%5D=6&current_status_ids%5B%5D=7&current_status_ids%5B%5D=8&current_status_ids%5B%5D=9&current_status_ids%5B%5D=10&current_status_ids%5B%5D=11&current_status_ids%5B%5D=12&current_status_ids%5B%5D=13&current_status_ids%5B%5D=21&current_status_ids%5B%5D=22&current_status_ids%5B%5D=23&current_status_ids%5B%5D=24&current_status_ids%5B%5D=25&current_status_ids%5B%5D=30&current_status_ids%5B%5D=31&current_status_ids%5B%5D=33&current_status_ids%5B%5D=34&current_status_ids%5B%5D=37&current_status_ids%5B%5D=38&date_of_last_status_change_ge=&date_of_last_status_change_le=&date_of_last_status_change_r=select&promotion_id=&date_placed_ge=&date_placed_le=&date_placed_r=select&date_of_initial_appointment_ge=&date_of_initial_appointment_le=&date_of_initial_appointment_r=select&date_of_welcome_call_ge=&date_of_welcome_call_le=&date_of_welcome_call_r=select&date_measurements_scheduled_ge=&date_measurements_scheduled_le=&date_measurements_scheduled_r=select&date_installation_scheduled_ge=&date_installation_scheduled_le=&date_installation_scheduled_r=select&date_of_final_payment_ge=&date_of_final_payment_le=&date_of_final_payment_r=select&date_completed_ge=&date_completed_le=&date_completed_r=select&date_last_payment_ge=&date_last_payment_le=&date_last_payment_r=select&payment_type_id=&memo=&payment_value_lookup=&time_est=&job_survey_response_id=&is_rush_y=y&is_rush_n=n&rush_is_billable_y=y&rush_is_billable_n=n&is_split_order_y=y&is_split_order_n=n&exclude_from_close_rate_y=y&exclude_from_close_rate_n=n&exclude_from_average_sale_y=y&exclude_from_average_sale_n=n&number_of_basics_ge=&number_of_basics_le=&number_of_classics_ge=&number_of_classics_le=&number_of_designers_ge=&number_of_designers_le=&number_of_shelves_ge=&number_of_shelves_le=&number_of_dividers_ge=&number_of_dividers_le=&number_of_accessories_ge=&number_of_accessories_le=&number_of_strip_mounts_ge=&number_of_strip_mounts_le=&number_of_other_ge=&number_of_other_le=&number_of_options_ge=&number_of_options_le=&nps_survey_rating_ge=&nps_survey_rating_le=&wm_note=&active_y=y&date_last_modified_ge=&date_last_modified_le=&date_last_modified_r=select&date_added_ge=&date_added_le=&date_added_r=select&status_field_name_for_filter=REPLACE_ME&status_update_search_date_ge=REPLACE_START&status_update_search_date_le=REPLACE_END&status_update_search_date_r=select&sort_by=id&sort_dir=DESC&display=on&c%5B%5D=id&c%5B%5D=location_id&filter=Submit
# """.strip()
#
#
# def build_url(status_filter_id: int, start_date: str, end_date: str) -> str:
#     return (
#         TEMPLATE_URL.replace("REPLACE_ME", str(status_filter_id))
#         .replace("REPLACE_START", quote_plus(start_date))
#         .replace("REPLACE_END", quote_plus(end_date))
#     )
#
#
# def fetch_status_table(status_name: str, status_filter_id: int, start_date: str, end_date: str, session: requests.Session = None) -> pd.DataFrame:
#     if session is None:
#         session = get_session_with_canvas_cookie()
#
#     url = build_url(status_filter_id, start_date, end_date)
#     resp = session.get(url)
#     resp.raise_for_status()
#
#     cleaned = re.sub(r"<[^>]+>", "", resp.text).strip()
#     if not cleaned:
#         return pd.DataFrame()
#
#     df = pd.read_csv(StringIO(cleaned), engine="python")
#     df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
#
#     look = f"{status_name} Date".lower()
#     match = next((c for c in df.columns if c.lower() == look), None)
#     df["Status"] = status_name
#     df["Date"] = df[match] if match else pd.NaT
#
#     def classify(oid):
#         if isinstance(oid, str):
#             if oid.startswith("C"):
#                 return "Claim"
#             if oid.startswith("R"):
#                 return "Reorder"
#             if re.match(r"^\d", oid):
#                 return "New"
#         return "New"
#
#     df["Order Type"] = df["ID"].apply(classify)
#
#     return df[["ID", "Order Type", "Franchisee", "Date", "Status"]]
#
#
# def generate_combined_jobs_csv(start_date: str, end_date: str, out_path: str = None, session: requests.Session = None) -> pd.DataFrame:
#     if session is None:
#         session = get_session_with_canvas_cookie()
#
#     if out_path is None:
#         a = start_date.replace("/", "")
#         b = end_date.replace("/", "")
#         out_path = f"Data/{a}_{b}_jobs.csv"
#
#     dfs = []
#     for name, fid in STATUS_FILTERS.items():
#         df = fetch_status_table(name, fid, start_date, end_date, session=session)
#         if not df.empty:
#             dfs.append(df)
#
#     if not dfs:
#         return pd.DataFrame()
#
#     all_jobs = pd.concat(dfs, ignore_index=True)
#     Path(out_path).parent.mkdir(parents=True, exist_ok=True)
#
#     all_jobs.to_csv(out_path, index=False)
#     # print(f"✅ Combined CSV saved to {out_path}")
#     return all_jobs
#
#
# def load_jobs_data(start_date: str, end_date: str, out_dir: Path = Path("Data")) -> pd.DataFrame:
#     """
#     Look for the Jobs CSV under Data/, otherwise call
#     generate_combined_jobs_csv to build it. Prints a friendly message.
#     Returns the jobs DataFrame.
#     """
#     token_start = start_date.replace("/", "")
#     token_end = end_date.replace("/", "")
#     fp = out_dir / f"{token_start}_{token_end}_jobs.csv"
#
#     print("→ Looking locally for Jobs Data…")
#     if not fp.exists():
#         print("   • Generating Jobs Data from Canvas…")
#         df = generate_combined_jobs_csv(start_date, end_date, out_path=str(fp))
#     else:
#         print("   • Found it. Loading Jobs Data from your computer…\n")
#         df = pd.read_csv(fp)
#
#     return df


# # ─── 2. CALL-CENTER SCRAPER ────────────────────────────────────────────────────

BASE = "https://canvas.artofdrawers.com"
FORM_URL = BASE + "/scripts/lead-to-appointment-conversion/index.html"
CSV_URL = (
    BASE
    + "/scripts/report_as_spreadsheet.html?report=report_lead_to_appointment_conversion"
)


def download_conversion_report(start_date: str, end_date: str, include_homeshow: bool = False, out_path: str = None, session: requests.Session = None):
    if session is None:
        session = get_session_with_canvas_cookie()

    payload = {
        "start_date": start_date,
        "end_date": end_date,
        **({"include_homeshow": "true"} if include_homeshow else {}),
        "quick_search": "Search",
        "search_for": "",
        "submit": "Show Report",
    }

    r1 = session.post(FORM_URL, data=payload, headers={"Referer": FORM_URL})
    r1.raise_for_status()

    r2 = session.get(CSV_URL, headers={"Referer": FORM_URL})
    r2.raise_for_status()

    df = pd.read_csv(StringIO(r2.text))
    df["Inbound Rate Value"] = df["Inbound Help Rate"].str.rstrip("%").astype(float)
    df["Outbound Proxy Value"] = df["Outbound Communication Count"].astype(int)
    df["Inbound Help Rate (%)"] = df["Inbound Rate Value"].map("{:.1f}%".format)
    df["Outbound Help Rate (%)"] = (
        df["Outbound Help Rate"].str.rstrip("%").astype(float).map("{:.1f}%".format)
    )

    rep_reps = df.copy()

    rep_options = [{"label": "All", "value": "All"}] + [
        {"label": r, "value": r} for r in rep_reps["Call Center Rep"].unique()
    ]

    a = start_date.replace("/", "")
    b = end_date.replace("/", "")
    suf = "ccYesHs" if include_homeshow else "ccNoHs"
    if out_path is None:
        out_path = Path("Data") / f"{a}_{b}_{suf}.csv"
    else:
        out_path = Path(out_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    rep_reps.to_csv(out_path, index=False)
    # print(f"✅ Saved report to {out_path}")

    return rep_reps, rep_options


def load_conversion_data(start_date: str, end_date: str, include_homeshow: bool = False, data_dir: Path = Path("Data")) -> tuple[pd.DataFrame, list]:
    """
    Builds the file path for inbound/outbound CSV,
    prints a friendly message, and either loads or downloads it.
    Returns: (df, dropdown_options)
    """
    token_start = start_date.replace("/", "")
    token_end = end_date.replace("/", "")
    mode = "outbound" if include_homeshow else "inbound"
    fname = f"{token_start}_{token_end}_{mode}.csv"
    fp = data_dir / fname

    if include_homeshow:
        print("→ Looking locally for Outbound Call Center Data…")
    else:
        print("→ Looking locally for Inbound Call Center Data…")

    if not fp.exists():
        what = "Outbound" if include_homeshow else "Inbound"
        print(f"   • Downloading {what} Call Center Data from Canvas…")
        df, opts = download_conversion_report(
            start_date, end_date, include_homeshow=include_homeshow, out_path=str(fp)
        )
    else:
        print("   • Found it. Loading it in from your computer…\n")
        df = pd.read_csv(fp)
        opts = [{"label": "All", "value": "All"}] + [
            {"label": r, "value": r} for r in df["Call Center Rep"].unique()
        ]

    return df, opts


# Marekting Pull
def fetch_roi(start: str, end: str, session: requests.Session) -> pd.DataFrame:
    print(f"\n{'='*60}")
    print(f"🔍 DEBUG: fetch_roi called with:")
    print(f"   Start date: {start}")
    print(f"   End date: {end}")
    print(f"   Session provided: {session is not None}")

    session = get_session_with_canvas_cookie()
    print(f"   Session recreated (overwrites passed session)")
    print(f"   Cookies loaded: {len(session.cookies)} cookies")

    url = "https://canvas.artofdrawers.com/scripts/marketing_roi.html"
    # hard-coded campaigns; change if you want dynamic
    campaign_ids = [62,59,21,63,64,60,61]
    params = [("campaign_ids[]", cid) for cid in campaign_ids] + [
        ("sd", start),
        ("ed", end),
        ("submit", "Generate Report")
    ]

    print(f"\n📡 Making request to Canvas:")
    print(f"   URL: {url}")
    print(f"   Campaign IDs: {campaign_ids}")
    print(f"   Date range params: sd={start}, ed={end}")

    try:
        r = session.get(url, params=params)
        print(f"\n✅ Response received:")
        print(f"   Status code: {r.status_code}")
        print(f"   Response size: {len(r.text)} characters")
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"\n❌ HTTP Request failed: {e}")
        return pd.DataFrame()

    # Save response for inspection
    debug_file = f"/tmp/roi_debug_{start.replace('/', '-')}_{end.replace('/', '-')}.html"
    with open(debug_file, 'w') as f:
        f.write(r.text)
    print(f"   📄 Full HTML saved to: {debug_file}")

    # CHECK FOR LOGIN PAGE (Authentication failure detection)
    if "Login Required" in r.text or "logged in" in r.text.lower():
        print(f"\n❌ AUTHENTICATION FAILED!")
        print(f"   Canvas returned a login page instead of data.")
        print(f"   Your cookies have likely expired or are invalid.")
        print(f"   Please refresh your canvas_cookies.json file.")
        print(f"   See HTML at: {debug_file}")
        return pd.DataFrame()

    soup = BeautifulSoup(r.text, "html.parser")

    # Debug: Find all tables
    all_tables = soup.find_all("table")
    print(f"\n🔎 HTML Parsing:")
    print(f"   Total tables found: {len(all_tables)}")

    # Debug: Find all th elements with rowspan="2"
    rowspan_ths = soup.find_all("th", {"rowspan": "2"})
    print(f"   TH elements with rowspan=2: {len(rowspan_ths)}")
    for i, th in enumerate(rowspan_ths):
        print(f"      [{i}] Text: '{th.get_text(strip=True)}'")

    # find "Grand Totals" two-row table
    grand_th = next(
        (th for th in soup.find_all("th", {"rowspan": "2"})
         if "Grand" in th.get_text()), None
    )

    if not grand_th:
        print(f"\n❌ WARNING: No ROI Grand Totals table found for {start}–{end}")
        print(f"   This means the HTML structure didn't contain a <th rowspan='2'> with 'Grand' in it")
        print(f"   Check the HTML file at: {debug_file}")
        return pd.DataFrame()

    print(f"\n✅ Found Grand Totals table!")
    print(f"   Grand Totals TH text: '{grand_th.get_text(strip=True)}'")

    tbl = grand_th.find_parent("table")
    print(f"   Parent table found: {tbl is not None}")

    # headers = first <tr>, values = second <tr>
    all_rows = tbl.find_all("tr")
    print(f"   Total rows in table: {len(all_rows)}")

    if len(all_rows) < 2:
        print(f"❌ ERROR: Not enough rows in table (need at least 2, got {len(all_rows)})")
        return pd.DataFrame()

    hdrs = [th.get_text(strip=True).replace("\n"," ") for th in all_rows[0].find_all("th")]
    vals = [td.get_text(strip=True) for td in all_rows[1].find_all("td")]

    print(f"\n📊 Extracted data:")
    print(f"   Headers ({len(hdrs)}): {hdrs}")
    print(f"   Values ({len(vals)}): {vals}")

    if len(hdrs) == 0 or len(vals) == 0:
        print(f"❌ ERROR: No data extracted (headers or values empty)")
        return pd.DataFrame()

    if len(vals) != len(hdrs) - 1:
        print(f"⚠️  WARNING: Value count mismatch!")
        print(f"   Expected {len(hdrs)-1} values, got {len(vals)}")

    df = pd.DataFrame([vals], columns=hdrs[1:])  # drop the rowspan "Grand Totals" header
    df["week_start"] = start
    df["week_end"]   = end

    print(f"\n✅ DataFrame created:")
    print(f"   Shape: {df.shape}")
    print(f"   Columns: {list(df.columns)}")
    print(f"   First row values:")
    for col in df.columns:
        print(f"      {col}: {df[col].iloc[0]}")
    print(f"{'='*60}\n")

    return df
