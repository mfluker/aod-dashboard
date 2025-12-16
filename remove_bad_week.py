#!/usr/bin/env python3
"""
Remove a specific week from ROI data if it contains bad/zero data
"""
import sys
import pandas as pd
from pathlib import Path

def remove_week(week_start, week_end):
    """Remove a specific week from both ROI and Call Center data"""
    master_data_dir = Path(__file__).parent / "dashboard" / "Master_Data"
    roi_path = master_data_dir / "all_roi_data.parquet"
    calls_path = master_data_dir / "all_call_center_data.parquet"

    if not roi_path.exists():
        print(f"❌ ROI data file not found at: {roi_path}")
        return False

    if not calls_path.exists():
        print(f"❌ Call Center data file not found at: {calls_path}")
        return False

    # Load ROI data
    roi_df = pd.read_parquet(roi_path)
    print(f"📊 Current ROI data: {len(roi_df)} rows")

    # Load Call Center data
    calls_df = pd.read_parquet(calls_path)
    print(f"📞 Current Call Center data: {len(calls_df)} rows")

    # Find the week to remove in ROI data
    roi_mask = (roi_df['week_start'] == week_start) & (roi_df['week_end'] == week_end)
    roi_matching = roi_df[roi_mask]

    # Find the week to remove in Call Center data
    calls_mask = (calls_df['week_start'] == week_start) & (calls_df['week_end'] == week_end)
    calls_matching = calls_df[calls_mask]

    if len(roi_matching) == 0 and len(calls_matching) == 0:
        print(f"❌ Week {week_start} - {week_end} not found in any data")
        return False

    print(f"\n🔍 Week {week_start} - {week_end} status:")

    if len(roi_matching) > 0:
        print(f"\n   📊 ROI Data: {len(roi_matching)} row(s)")
        for _, row in roi_matching.iterrows():
            print(f"      Amount Invested: {row['Amount Invested']}")
            print(f"      # of Leads: {row['# of Leads']}")
            print(f"      Revenue: {row['Revenue']}")
    else:
        print(f"   📊 ROI Data: Not found (already removed)")

    if len(calls_matching) > 0:
        print(f"\n   📞 Call Center Data: {len(calls_matching)} row(s)")
        print(f"      Will be removed to keep data consistent")
    else:
        print(f"   📞 Call Center Data: Not found (already removed)")

    # Confirm deletion
    response = input(f"\n⚠️  Delete this week from ALL data sources? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Cancelled - no changes made")
        return False

    # Remove the week from both datasets
    roi_df_cleaned = roi_df[~roi_mask]
    calls_df_cleaned = calls_df[~calls_mask]

    print(f"\n✅ Removing week {week_start} - {week_end}")
    print(f"   ROI: {len(roi_df)} → {len(roi_df_cleaned)} rows")
    print(f"   Calls: {len(calls_df)} → {len(calls_df_cleaned)} rows")

    # Create backups
    timestamp = week_start.replace('/', '-')
    roi_backup_path = master_data_dir / f"all_roi_data_backup_{timestamp}.parquet"
    calls_backup_path = master_data_dir / f"all_call_center_data_backup_{timestamp}.parquet"

    roi_df.to_parquet(roi_backup_path, index=False)
    calls_df.to_parquet(calls_backup_path, index=False)
    print(f"\n💾 Backups saved:")
    print(f"   ROI: {roi_backup_path}")
    print(f"   Calls: {calls_backup_path}")

    # Save cleaned data
    roi_df_cleaned.to_parquet(roi_path, index=False)
    calls_df_cleaned.to_parquet(calls_path, index=False)
    print(f"\n✅ Cleaned data saved!")
    print(f"🎉 Week {week_start} - {week_end} has been removed from all data sources!")

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
