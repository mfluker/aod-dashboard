import re
import requests
import pandas as pd

from io import StringIO
from pathlib import Path
from urllib.parse import quote_plus


# ─── 0. Cookie Loader ─────────────────────────────────────────────────────────

def get_session_with_canvas_cookie(cookie_path="canvas_cookies.json"):
    import json
    session = requests.Session()
    with open(cookie_path, "r") as f:
        cookies = json.load(f)
    for cookie in cookies:
        session.cookies.set(cookie['name'], cookie['value'])
    return session


# ─── 1. JOBS-STATUS SCRAPER ───────────────────────────────────────────────────


# Map human‐readable status → filter ID
STATUS_FILTERS = {
    "Measurement Appointment Scheduled": 2,
    "Measurement Approved":              23,
    "Submitted to Manufacturing Partner": 5,
    "Order Shipped":                     6,
    "Order Received":                   37,
    "Install Scheduled":                8,
    "Installed":                        9,
    "Complete":                        13,
}

# Base URL template — replace three placeholders below
TEMPLATE_URL = """
https://canvas.artofdrawers.com/listjobs.html?dsraas=1&id=&location_id=&zone=&zone_id=&production_priority_ge=&production_priority_le=&opportunity=&opportunity_id=&customer=&customer_id=&campaign_source=&customer_id_sub_filters_campaign_source_id=&customer_id_sub_filters_firstname=&customer_id_sub_filters_lastname=&customer_id_sub_filters_spouse=&customer_id_sub_filters_preferred_phone=&customer_id_sub_filters_cell_phone=&customer_id_sub_filters_emailaddr=&city=&state_id=&country_id=&latitude_ge=&latitude_le=&longitude_ge=&longitude_le=&location_tax_rate_id=&total_cost_ge=&total_cost_le=&material_total_ge=&material_total_le=&labor_total_ge=&labor_total_le=&delivery_total_ge=&delivery_total_le=&discount_total_ge=&discount_total_le=&credit_memo_total_ge=&credit_memo_total_le=&tax_total_ge=&tax_total_le=&order_total_ge=&order_total_le=&amount_paid_ge=&amount_paid_le=&amount_due_ge=&amount_due_le=&designer_id=&tma_id=&relationship_partner_id=&installer_id=&shipping_type_id=&number_of_items_ge=&number_of_items_le=&manufacturing_batch_id=&manufacturing_facility_id=&manufacturing_status_id=&date_submitted_to_manufacturing_ge=&date_submitted_to_manufacturing_le=&date_submitted_to_manufacturing_r=select&number_of_days_ago_submitted_to_go_ge=&number_of_days_ago_submitted_to_go_le=&number_of_biz_days_at_manufacturing_status_ge=&number_of_biz_days_at_manufacturing_status_le=&date_submitted_to_manufacturing_partner_ge=&date_submitted_to_manufacturing_partner_le=&date_submitted_to_manufacturing_partner_r=select&date_projected_to_ship_ge=&date_projected_to_ship_le=&date_projected_to_ship_r=select&date_shipped_ge=&date_shipped_le=&date_shipped_r=select&carrier_id=&tracking_number=&date_delivered_ge=&date_delivered_le=&date_delivered_r=select&commission_rate_type_id=&designer_commission_override_percentage_ge=&designer_commission_override_percentage_le=&tma_commission_rate_type_id=&tma_commission_has_been_paid_y=y&tma_commission_has_been_paid_n=n&job_type_id=&current_status_ids%5B%5D=2&current_status_ids%5B%5D=3&current_status_ids%5B%5D=5&current_status_ids%5B%5D=6&current_status_ids%5B%5D=7&current_status_ids%5B%5D=8&current_status_ids%5B%5D=9&current_status_ids%5B%5D=10&current_status_ids%5B%5D=11&current_status_ids%5B%5D=12&current_status_ids%5B%5D=13&current_status_ids%5B%5D=21&current_status_ids%5B%5D=22&current_status_ids%5B%5D=23&current_status_ids%5B%5D=24&current_status_ids%5B%5D=25&current_status_ids%5B%5D=30&current_status_ids%5B%5D=31&current_status_ids%5B%5D=33&current_status_ids%5B%5D=34&current_status_ids%5B%5D=37&current_status_ids%5B%5D=38&date_of_last_status_change_ge=&date_of_last_status_change_le=&date_of_last_status_change_r=select&promotion_id=&date_placed_ge=&date_placed_le=&date_placed_r=select&date_of_initial_appointment_ge=&date_of_initial_appointment_le=&date_of_initial_appointment_r=select&date_of_welcome_call_ge=&date_of_welcome_call_le=&date_of_welcome_call_r=select&date_measurements_scheduled_ge=&date_measurements_scheduled_le=&date_measurements_scheduled_r=select&date_installation_scheduled_ge=&date_installation_scheduled_le=&date_installation_scheduled_r=select&date_of_final_payment_ge=&date_of_final_payment_le=&date_of_final_payment_r=select&date_completed_ge=&date_completed_le=&date_completed_r=select&date_last_payment_ge=&date_last_payment_le=&date_last_payment_r=select&payment_type_id=&memo=&payment_value_lookup=&time_est=&job_survey_response_id=&is_rush_y=y&is_rush_n=n&rush_is_billable_y=y&rush_is_billable_n=n&is_split_order_y=y&is_split_order_n=n&exclude_from_close_rate_y=y&exclude_from_close_rate_n=n&exclude_from_average_sale_y=y&exclude_from_average_sale_n=n&number_of_basics_ge=&number_of_basics_le=&number_of_classics_ge=&number_of_classics_le=&number_of_designers_ge=&number_of_designers_le=&number_of_shelves_ge=&number_of_shelves_le=&number_of_dividers_ge=&number_of_dividers_le=&number_of_accessories_ge=&number_of_accessories_le=&number_of_strip_mounts_ge=&number_of_strip_mounts_le=&number_of_other_ge=&number_of_other_le=&number_of_options_ge=&number_of_options_le=&nps_survey_rating_ge=&nps_survey_rating_le=&wm_note=&active_y=y&date_last_modified_ge=&date_last_modified_le=&date_last_modified_r=select&date_added_ge=&date_added_le=&date_added_r=select&status_field_name_for_filter=REPLACE_ME&status_update_search_date_ge=REPLACE_START&status_update_search_date_le=REPLACE_END&status_update_search_date_r=select&sort_by=id&sort_dir=DESC&display=on&c%5B%5D=id&c%5B%5D=location_id&filter=Submit
""".strip()

# HEADERS = {
#     "Cookie":     "username=mat.fluker; PHPSESSID=3dol5qpthtu5rnfuepi0rvh8t4",
#     "User-Agent": "Mozilla/5.0",
# }


def build_url(status_filter_id: int, start_date: str, end_date: str) -> str:
    return (
        TEMPLATE_URL
        .replace("REPLACE_ME",    str(status_filter_id))
        .replace("REPLACE_START", quote_plus(start_date))
        .replace("REPLACE_END",   quote_plus(end_date))
    )

def fetch_status_table(status_name: str,
                       status_filter_id: int,
                       start_date: str,
                       end_date:   str) -> pd.DataFrame:
    url = build_url(status_filter_id, start_date, end_date)
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()

    # Strip HTML tags, load CSV
    cleaned = re.sub(r"<[^>]+>", "", resp.text).strip()
    if not cleaned:
        return pd.DataFrame()

    df = pd.read_csv(StringIO(cleaned), engine="python")
    # drop any Unnamed columns
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

    # pick off the correct date‐column
    look = f"{status_name} Date".lower()
    match = next((c for c in df.columns if c.lower()==look), None)
    df["Status"] = status_name
    df["Date"]   = df[match] if match else pd.NaT

    # classify order type
    def classify(oid):
        if isinstance(oid, str):
            if oid.startswith("C"): return "Claim"
            if oid.startswith("R"): return "Reorder"
            if re.match(r"^\d", oid): return "New"
        return "New"

    df["Order Type"] = df["ID"].apply(classify)
    return df[["ID","Order Type","Franchisee","Date","Status"]]

def generate_combined_jobs_csv(start_date: str,
                               end_date:   str,
                               out_path:   str = None) -> pd.DataFrame:
    """
    Loops through each status, fetches its table, concatenates all,
    saves to Data/<MMDDYYYY>_<MMDDYYYY>_jobs.csv, and returns that df.
    """
    if out_path is None:
        a = start_date.replace("/", "")
        b = end_date.replace(  "/", "")
        out_path = f"Data/{a}_{b}_jobs.csv"

    dfs = []
    for name, fid in STATUS_FILTERS.items():
        df = fetch_status_table(name, fid, start_date, end_date)
        if not df.empty:
            dfs.append(df)

    if not dfs:
        return pd.DataFrame()

    all_jobs = pd.concat(dfs, ignore_index=True)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    all_jobs.to_csv(out_path, index=False)
    print(f"✅ Combined CSV saved to {out_path}")
    return all_jobs




# ─── 2. CALL-CENTER SCRAPER ────────────────────────────────────────────────────


# Form/CVS endpoints
BASE      = "https://canvas.artofdrawers.com"
FORM_URL  = BASE + "/scripts/lead-to-appointment-conversion/index.html"
CSV_URL   = BASE + "/scripts/report_as_spreadsheet.html?report=report_lead_to_appointment_conversion"

def download_conversion_report(start_date: str,
                               end_date:   str,
                               include_homeshow: bool = False,
                               out_path:   str = None):
    """
    Downloads the lead→appointment report for the given date range,
    applies formatting + drops Totals row + builds dropdown options,
    saves to Data/<MMDDYYYY>_<MMDDYYYY>_ccNoHs.csv or _ccYesHs.csv,
    returns (rep_reps_df, rep_options).
    """
    sess = requests.Session()
    sess.headers.update(HEADERS)

    # build form‐POST payload
    payload = {
        "start_date":   start_date,
        "end_date":     end_date,
        **({"include_homeshow":"true"} if include_homeshow else {}),
        "quick_search": "Search",
        "search_for":   "",
        "submit":       "Show Report"
    }
    r1 = sess.post(FORM_URL, data=payload, headers={"Referer":FORM_URL})
    r1.raise_for_status()

    # download CSV
    r2 = sess.get(CSV_URL, headers={"Referer":FORM_URL})
    r2.raise_for_status()

    df = pd.read_csv(StringIO(r2.text))

    # prepare columns
    df["Inbound Rate Value"]   = df["Inbound Help Rate"].str.rstrip("%").astype(float)
    df["Outbound Proxy Value"]  = df["Outbound Communication Count"].astype(int)

    df["Inbound Help Rate (%)"]  = df["Inbound Rate Value"].map("{:.1f}%".format)
    df["Outbound Help Rate (%)"] = (
        df["Outbound Help Rate"]
          .str.rstrip("%").astype(float)
          .map("{:.1f}%".format)
    )

    # filter out Totals
    rep_reps = df[df["Call Center Rep"]!="Totals"].copy()

    # dropdown options
    rep_options = [{"label":"All","value":"All"}] + [
        {"label":r,"value":r} for r in rep_reps["Call Center Rep"].unique()
    ]

    # decide filename
    a = start_date.replace("/","")
    b = end_date.replace(  "/","")
    suf = "ccYesHs" if include_homeshow else "ccNoHs"
    # if caller gave us a string, or None, make sure it's a Path
    if out_path is None:
        out_path = Path("Data")/f"{a}_{b}_{suf}.csv"
    else:
        out_path = Path(out_path)

    # create parent directory if needed
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rep_reps.to_csv(out_path, index=False)
    print(f"✅ Saved report to {out_path}")
    return rep_reps, rep_options

