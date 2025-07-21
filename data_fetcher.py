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

# For RENDER!
# def get_session_with_canvas_cookie(cookie_path="/etc/secrets/canvas_cookies.json"):
#     import json
#     session = requests.Session()
#     with open(cookie_path, "r") as f:
#         cookies = json.load(f)
#     for cookie in cookies:
#         session.cookies.set(cookie['name'], cookie['value'])
#     return session

# # For Testing!

# COOKIE_PATH = "canvas_cookies.json"


# def get_session_with_canvas_cookie():
#     """
#     Load cookies from COOKIE_PATH and return a requests.Session
#     that only sets name, value, domain, path, secure, and expires.
#     """
#     with open(COOKIE_PATH, "r") as f:
#         raw_cookies = json.load(f)

#     session = requests.Session()
#     for c in raw_cookies:
#         # required:
#         name = c.get("name")
#         value = c.get("value")

#         # optional but valid in requests:
#         params = {}
#         if "domain" in c:
#             params["domain"] = c["domain"]
#         if "path" in c:
#             params["path"] = c["path"]
#         if "secure" in c:
#             params["secure"] = c["secure"]
#         if "expirationDate" in c:
#             # requests wants 'expires' (an int)
#             params["expires"] = int(c["expirationDate"])

#         session.cookies.set(name, value, **params)

#     return session


# ─── 1. JOBS-STATUS SCRAPER ───────────────────────────────────────────────────

STATUS_FILTERS = {
    "Measurement Appointment Scheduled": 2,
    "Measurement Approved": 23,
    "Submitted to Manufacturing Partner": 5,
    "Order Shipped": 6,
    "Order Received": 37,
    "Install Scheduled": 8,
    "Installed": 9,
    "Complete": 13,
}

TEMPLATE_URL = """
https://canvas.artofdrawers.com/listjobs.html?dsraas=1&id=&location_id=&zone=&zone_id=&production_priority_ge=&production_priority_le=&opportunity=&opportunity_id=&customer=&customer_id=&campaign_source=&customer_id_sub_filters_campaign_source_id=&customer_id_sub_filters_firstname=&customer_id_sub_filters_lastname=&customer_id_sub_filters_spouse=&customer_id_sub_filters_preferred_phone=&customer_id_sub_filters_cell_phone=&customer_id_sub_filters_emailaddr=&city=&state_id=&country_id=&latitude_ge=&latitude_le=&longitude_ge=&longitude_le=&location_tax_rate_id=&total_cost_ge=&total_cost_le=&material_total_ge=&material_total_le=&labor_total_ge=&labor_total_le=&delivery_total_ge=&delivery_total_le=&discount_total_ge=&discount_total_le=&credit_memo_total_ge=&credit_memo_total_le=&tax_total_ge=&tax_total_le=&order_total_ge=&order_total_le=&amount_paid_ge=&amount_paid_le=&amount_due_ge=&amount_due_le=&designer_id=&tma_id=&relationship_partner_id=&installer_id=&shipping_type_id=&number_of_items_ge=&number_of_items_le=&manufacturing_batch_id=&manufacturing_facility_id=&manufacturing_status_id=&date_submitted_to_manufacturing_ge=&date_submitted_to_manufacturing_le=&date_submitted_to_manufacturing_r=select&number_of_days_ago_submitted_to_go_ge=&number_of_days_ago_submitted_to_go_le=&number_of_biz_days_at_manufacturing_status_ge=&number_of_biz_days_at_manufacturing_status_le=&date_submitted_to_manufacturing_partner_ge=&date_submitted_to_manufacturing_partner_le=&date_submitted_to_manufacturing_partner_r=select&date_projected_to_ship_ge=&date_projected_to_ship_le=&date_projected_to_ship_r=select&date_shipped_ge=&date_shipped_le=&date_shipped_r=select&carrier_id=&tracking_number=&date_delivered_ge=&date_delivered_le=&date_delivered_r=select&commission_rate_type_id=&designer_commission_override_percentage_ge=&designer_commission_override_percentage_le=&tma_commission_rate_type_id=&tma_commission_has_been_paid_y=y&tma_commission_has_been_paid_n=n&job_type_id=&current_status_ids%5B%5D=2&current_status_ids%5B%5D=3&current_status_ids%5B%5D=5&current_status_ids%5B%5D=6&current_status_ids%5B%5D=7&current_status_ids%5B%5D=8&current_status_ids%5B%5D=9&current_status_ids%5B%5D=10&current_status_ids%5B%5D=11&current_status_ids%5B%5D=12&current_status_ids%5B%5D=13&current_status_ids%5B%5D=21&current_status_ids%5B%5D=22&current_status_ids%5B%5D=23&current_status_ids%5B%5D=24&current_status_ids%5B%5D=25&current_status_ids%5B%5D=30&current_status_ids%5B%5D=31&current_status_ids%5B%5D=33&current_status_ids%5B%5D=34&current_status_ids%5B%5D=37&current_status_ids%5B%5D=38&date_of_last_status_change_ge=&date_of_last_status_change_le=&date_of_last_status_change_r=select&promotion_id=&date_placed_ge=&date_placed_le=&date_placed_r=select&date_of_initial_appointment_ge=&date_of_initial_appointment_le=&date_of_initial_appointment_r=select&date_of_welcome_call_ge=&date_of_welcome_call_le=&date_of_welcome_call_r=select&date_measurements_scheduled_ge=&date_measurements_scheduled_le=&date_measurements_scheduled_r=select&date_installation_scheduled_ge=&date_installation_scheduled_le=&date_installation_scheduled_r=select&date_of_final_payment_ge=&date_of_final_payment_le=&date_of_final_payment_r=select&date_completed_ge=&date_completed_le=&date_completed_r=select&date_last_payment_ge=&date_last_payment_le=&date_last_payment_r=select&payment_type_id=&memo=&payment_value_lookup=&time_est=&job_survey_response_id=&is_rush_y=y&is_rush_n=n&rush_is_billable_y=y&rush_is_billable_n=n&is_split_order_y=y&is_split_order_n=n&exclude_from_close_rate_y=y&exclude_from_close_rate_n=n&exclude_from_average_sale_y=y&exclude_from_average_sale_n=n&number_of_basics_ge=&number_of_basics_le=&number_of_classics_ge=&number_of_classics_le=&number_of_designers_ge=&number_of_designers_le=&number_of_shelves_ge=&number_of_shelves_le=&number_of_dividers_ge=&number_of_dividers_le=&number_of_accessories_ge=&number_of_accessories_le=&number_of_strip_mounts_ge=&number_of_strip_mounts_le=&number_of_other_ge=&number_of_other_le=&number_of_options_ge=&number_of_options_le=&nps_survey_rating_ge=&nps_survey_rating_le=&wm_note=&active_y=y&date_last_modified_ge=&date_last_modified_le=&date_last_modified_r=select&date_added_ge=&date_added_le=&date_added_r=select&status_field_name_for_filter=REPLACE_ME&status_update_search_date_ge=REPLACE_START&status_update_search_date_le=REPLACE_END&status_update_search_date_r=select&sort_by=id&sort_dir=DESC&display=on&c%5B%5D=id&c%5B%5D=location_id&filter=Submit
""".strip()


def build_url(status_filter_id: int, start_date: str, end_date: str) -> str:
    return (
        TEMPLATE_URL.replace("REPLACE_ME", str(status_filter_id))
        .replace("REPLACE_START", quote_plus(start_date))
        .replace("REPLACE_END", quote_plus(end_date))
    )


def fetch_status_table(status_name: str, status_filter_id: int, start_date: str, end_date: str, session: requests.Session = None) -> pd.DataFrame:
    if session is None:
        session = get_session_with_canvas_cookie()

    url = build_url(status_filter_id, start_date, end_date)
    resp = session.get(url)
    resp.raise_for_status()

    cleaned = re.sub(r"<[^>]+>", "", resp.text).strip()
    if not cleaned:
        return pd.DataFrame()

    df = pd.read_csv(StringIO(cleaned), engine="python")
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

    look = f"{status_name} Date".lower()
    match = next((c for c in df.columns if c.lower() == look), None)
    df["Status"] = status_name
    df["Date"] = df[match] if match else pd.NaT

    def classify(oid):
        if isinstance(oid, str):
            if oid.startswith("C"):
                return "Claim"
            if oid.startswith("R"):
                return "Reorder"
            if re.match(r"^\d", oid):
                return "New"
        return "New"

    df["Order Type"] = df["ID"].apply(classify)
    
    return df[["ID", "Order Type", "Franchisee", "Date", "Status"]]


def generate_combined_jobs_csv(start_date: str, end_date: str, out_path: str = None, session: requests.Session = None) -> pd.DataFrame:
    if session is None:
        session = get_session_with_canvas_cookie()

    if out_path is None:
        a = start_date.replace("/", "")
        b = end_date.replace("/", "")
        out_path = f"Data/{a}_{b}_jobs.csv"

    dfs = []
    for name, fid in STATUS_FILTERS.items():
        df = fetch_status_table(name, fid, start_date, end_date, session=session)
        if not df.empty:
            dfs.append(df)

    if not dfs:
        return pd.DataFrame()

    all_jobs = pd.concat(dfs, ignore_index=True)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    all_jobs.to_csv(out_path, index=False)
    # print(f"✅ Combined CSV saved to {out_path}")
    return all_jobs


def load_jobs_data(start_date: str, end_date: str, out_dir: Path = Path("Data")) -> pd.DataFrame:
    """
    Look for the Jobs CSV under Data/, otherwise call
    generate_combined_jobs_csv to build it. Prints a friendly message.
    Returns the jobs DataFrame.
    """
    token_start = start_date.replace("/", "")
    token_end = end_date.replace("/", "")
    fp = out_dir / f"{token_start}_{token_end}_jobs.csv"

    print("→ Looking locally for Jobs Data…")
    if not fp.exists():
        print("   • Generating Jobs Data from Canvas…")
        df = generate_combined_jobs_csv(start_date, end_date, out_path=str(fp))
    else:
        print("   • Found it. Loading Jobs Data from your computer…\n")
        df = pd.read_csv(fp)

    return df


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

    # rep_reps = df[df["Call Center Rep"] != "Totals"].copy()

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
    session = get_session_with_canvas_cookie()
    
    url = "https://canvas.artofdrawers.com/scripts/marketing_roi.html"
    # hard-coded campaigns; change if you want dynamic
    campaign_ids = [62,59,21,63,64,60,61]
    params = [("campaign_ids[]", cid) for cid in campaign_ids] + [
        ("sd", start),
        ("ed", end),
        ("submit", "Generate Report")
    ]
    r = session.get(url, params=params)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # find “Grand Totals” two-row table
    grand_th = next(
        (th for th in soup.find_all("th", {"rowspan": "2"})
         if "Grand" in th.get_text()), None
    )
    if not grand_th:
        logging.warning(f"No ROI Grand Totals for {start}–{end}")
        return pd.DataFrame()

    tbl = grand_th.find_parent("table")
    # headers = first <tr>, values = second <tr>
    hdrs = [th.get_text(strip=True).replace("\n"," ") for th in tbl.find_all("tr")[0].find_all("th")]
    vals = [td.get_text(strip=True) for td in tbl.find_all("tr")[1].find_all("td")]

    df = pd.DataFrame([vals], columns=hdrs[1:])  # drop the rowspan “Grand Totals” header
    df["week_start"] = start
    df["week_end"]   = end
    return df
