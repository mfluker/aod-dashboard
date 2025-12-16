#!/usr/bin/env python3
"""
Debug script to test fetch_roi function with the most recent week
"""
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta

# Add the updater directory to the path
sys.path.insert(0, str(Path(__file__).parent / "updater"))

from data_fetcher import fetch_roi, get_session_with_canvas_cookie

def get_next_week_dates(last_end_str):
    """
    Given a date string like '12/06/2025', calculate the next week's start and end
    """
    # Parse the date (MM/DD/YYYY format)
    month, day, year = map(int, last_end_str.split('/'))
    last_end = datetime(year, month, day)

    # Next day is the start of next week
    next_start = last_end + timedelta(days=1)
    # End is 6 days later (7-day week)
    next_end = next_start + timedelta(days=6)

    # Format back to MM/DD/YYYY
    start_str = next_start.strftime("%m/%d/%Y")
    end_str = next_end.strftime("%m/%d/%Y")

    return start_str, end_str

def main():
    print("=" * 80)
    print("ROI FETCH DEBUG SCRIPT")
    print("=" * 80)

    # Load existing ROI data to find the last week
    roi_path = Path(__file__).parent / "dashboard" / "Master_Data" / "all_roi_data.parquet"

    if not roi_path.exists():
        print(f"❌ ROI data file not found at: {roi_path}")
        return

    roi_df = pd.read_parquet(roi_path)
    last_week_end = roi_df['week_end'].max()
    last_week_start = roi_df['week_start'].max()

    print(f"\n📊 Current ROI data:")
    print(f"   Total weeks: {len(roi_df)}")
    print(f"   Last recorded week: {last_week_start} - {last_week_end}")

    # Calculate the next week
    next_start, next_end = get_next_week_dates(last_week_end)

    print(f"\n🔍 Testing fetch_roi for the NEXT week:")
    print(f"   Week to fetch: {next_start} - {next_end}")
    print(f"\nNote: If this week hasn't happened yet or has no data, you'll see zeros!")
    print(f"Current date: {datetime.now().strftime('%m/%d/%Y')}")

    # Create a session
    print(f"\n🔐 Loading Canvas session...")
    session = get_session_with_canvas_cookie()

    # Call fetch_roi with debug output
    print(f"\n🚀 Calling fetch_roi...")
    result_df = fetch_roi(next_start, next_end, session)

    print(f"\n📊 RESULT:")
    print(f"   DataFrame shape: {result_df.shape}")

    if result_df.empty:
        print(f"   ❌ EMPTY DATAFRAME RETURNED!")
        print(f"   This is why you're seeing zeros!")
    else:
        print(f"   ✅ Data returned:")
        print(result_df.to_string())

    print(f"\n" + "=" * 80)
    print(f"Check the debug HTML file to see what Canvas actually returned!")
    print(f"=" * 80)

if __name__ == "__main__":
    main()
