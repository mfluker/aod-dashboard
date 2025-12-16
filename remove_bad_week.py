#!/usr/bin/env python3
"""
Remove a specific week from ROI data if it contains bad/zero data
"""
import sys
import pandas as pd
from pathlib import Path

def remove_week(week_start, week_end):
    """Remove a specific week from the ROI data"""
    roi_path = Path(__file__).parent / "dashboard" / "Master_Data" / "all_roi_data.parquet"

    if not roi_path.exists():
        print(f"❌ ROI data file not found at: {roi_path}")
        return False

    # Load data
    roi_df = pd.read_parquet(roi_path)
    print(f"📊 Current ROI data: {len(roi_df)} rows")

    # Find the week to remove
    mask = (roi_df['week_start'] == week_start) & (roi_df['week_end'] == week_end)
    matching_rows = roi_df[mask]

    if len(matching_rows) == 0:
        print(f"❌ Week {week_start} - {week_end} not found in data")
        return False

    print(f"\n🔍 Found {len(matching_rows)} row(s) for week {week_start} - {week_end}:")
    for _, row in matching_rows.iterrows():
        print(f"   Amount Invested: {row['Amount Invested']}")
        print(f"   # of Leads: {row['# of Leads']}")
        print(f"   Revenue: {row['Revenue']}")

    # Confirm deletion
    response = input(f"\n⚠️  Delete this week? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Cancelled - no changes made")
        return False

    # Remove the week
    roi_df_cleaned = roi_df[~mask]
    print(f"\n✅ Removing week {week_start} - {week_end}")
    print(f"   Before: {len(roi_df)} rows")
    print(f"   After: {len(roi_df_cleaned)} rows")

    # Create backup
    backup_path = roi_path.parent / f"all_roi_data_backup_{week_start.replace('/', '-')}.parquet"
    roi_df.to_parquet(backup_path, index=False)
    print(f"\n💾 Backup saved to: {backup_path}")

    # Save cleaned data
    roi_df_cleaned.to_parquet(roi_path, index=False)
    print(f"✅ Cleaned data saved to: {roi_path}")
    print(f"\n🎉 Week {week_start} - {week_end} has been removed!")

    return True

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 remove_bad_week.py <week_start> <week_end>")
        print("Example: python3 remove_bad_week.py 12/07/2025 12/13/2025")
        sys.exit(1)

    week_start = sys.argv[1]
    week_end = sys.argv[2]

    print("=" * 60)
    print("REMOVE BAD WEEK FROM ROI DATA")
    print("=" * 60)

    success = remove_week(week_start, week_end)

    if success:
        print("\n" + "=" * 60)
        print("✅ Week removed successfully!")
        print("💡 Next steps:")
        print("   1. Re-run the Streamlit updater with fresh cookies")
        print("   2. The missing week will be re-fetched with valid data")
        print("   3. Push the updated data to GitHub")
        print("=" * 60)
    else:
        print("\n❌ Failed to remove week")
        sys.exit(1)

if __name__ == "__main__":
    main()
