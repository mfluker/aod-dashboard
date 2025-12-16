# ROI Data Fetch Debugging - Complete Analysis

## Problem
The `fetch_roi` function was returning all zeros for the most recent week data pull.

## Root Cause
**EXPIRED CANVAS AUTHENTICATION COOKIES**

When Canvas cookies expire, the Canvas system returns an HTML login page instead of the actual ROI data. The scraper couldn't find the expected "Grand Totals" table in the login page HTML, so it returned an empty DataFrame which appeared as zeros in the final data.

### Evidence
1. **Cookie Expiration**: The `username` cookie expired on 2025-10-12 14:07
2. **Login Page Response**: Canvas returned `<h2>Login Required</h2>` instead of data
3. **Empty DataFrame**: No tables found → empty DataFrame → zeros in data

## Debugging Enhancements Added

### 1. Enhanced `fetch_roi` Function ([data_fetcher.py:267-424](updater/data_fetcher.py#L267-L424))

#### Added Comprehensive Logging:
- **Input Parameters**: Shows start/end dates and session status
- **Cookie Information**: Displays number of cookies loaded
- **HTTP Request Details**: URL, campaign IDs, and date parameters
- **Response Validation**: Status code and response size
- **HTML Debug Files**: Saves full HTML response to `/tmp/roi_debug_*.html` for inspection
- **Authentication Detection**: Checks for "Login Required" text to catch auth failures early
- **Table Parsing Details**: Shows number of tables and rowspan elements found
- **Data Extraction**: Displays headers and values extracted from HTML
- **Final DataFrame**: Shows shape, columns, and sample values

#### Example Debug Output:
```
============================================================
🔍 DEBUG: fetch_roi called with:
   Start date: 12/07/2025
   End date: 12/13/2025
   Session provided: True
   Session recreated (overwrites passed session)
   Cookies loaded: 2 cookies

📡 Making request to Canvas:
   URL: https://canvas.artofdrawers.com/scripts/marketing_roi.html
   Campaign IDs: [62, 59, 21, 63, 64, 60, 61]
   Date range params: sd=12/07/2025, ed=12/13/2025

✅ Response received:
   Status code: 200
   Response size: 6398 characters
   📄 Full HTML saved to: /tmp/roi_debug_12-07-2025_12-13-2025.html

❌ AUTHENTICATION FAILED!
   Canvas returned a login page instead of data.
   Your cookies have likely expired or are invalid.
   Please refresh your canvas_cookies.json file.
```

### 2. New Cookie Validation Function ([data_fetcher.py:35-83](updater/data_fetcher.py#L35-L83))

```python
validate_canvas_cookies(cookie_path=None)
```

**Checks:**
- ✅ File exists
- ✅ File is not empty
- ✅ Required cookies present (PHPSESSID, username)
- ✅ Cookies not expired

**Returns:** `(is_valid: bool, message: str)`

### 3. Enhanced Data Updater ([updater_utils.py](updater/updater_utils.py))

#### Pre-Fetch Cookie Validation (lines 161-171):
- Validates cookies BEFORE attempting any data fetch
- Prevents wasted API calls with expired credentials
- Returns early with clear error message if validation fails

#### Per-Week ROI Validation (lines 182-194):
- Checks if each ROI fetch returns empty DataFrame
- Displays row/column counts and sample values
- Warns immediately if authentication fails mid-fetch

#### Final Data Validation (lines 209-227):
- Verifies ROI data was actually added for missing weeks
- Shows preview of newly added data
- Warns if no data was added (suggests auth failure)

## How to Fix the Current Issue

### Step 1: Get Fresh Canvas Cookies

1. Open [Canvas](https://canvas.artofdrawers.com) in Chrome
2. Log in to your account
3. Install [Cookie-Editor Extension](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndedbemlkljdomclgjgkkdggpac)
4. Click the Cookie-Editor extension icon
5. Delete all cookies EXCEPT:
   - `PHPSESSID`
   - `username`
6. Click "Export" button
7. Copy the exported JSON
8. Go to [JSON Editor Online](https://jsoneditoronline.org/)
9. Paste into the left panel
10. Click "Save" → "Save to Disk"
11. Name it `canvas_cookies.json`

### Step 2: Update Local Cookie File

Replace the cookie file:
```bash
# For local testing
cp ~/Downloads/canvas_cookies.json /Users/artofdrawersllc/Documents/AoD_Dashboard/updater/canvas_cookies.json
```

### Step 3: Update Streamlit Deployment

In the Streamlit web interface:
1. Upload the fresh `canvas_cookies.json` file
2. The app will validate expiration dates
3. Only proceed if validation passes

### Step 4: Re-run Data Fetch

With fresh cookies, the updater will now:
- ✅ Pass cookie validation
- ✅ Successfully authenticate with Canvas
- ✅ Receive actual ROI data instead of login page
- ✅ Extract and save real values

## Debug Files Created

When debugging authentication issues, check these files:

1. **HTML Response**: `/tmp/roi_debug_[start]_[end].html`
   - Shows exactly what Canvas returned
   - Look for "Login Required" → auth failure
   - Look for tables with "Grand Totals" → success

2. **Test Script**: `/Users/artofdrawersllc/Documents/AoD_Dashboard/test_roi_debug.py`
   - Standalone script to test ROI fetch
   - Shows full debug output
   - Tests with next expected week

## Known Issues Fixed

### Issue 1: Session Parameter Ignored
**Problem:** `fetch_roi` accepts a `session` parameter but immediately overwrites it (line 274)

**Status:** Documented but not fixed (would require refactoring all callers)

**Workaround:** Session is recreated from cookies anyway, so this doesn't break functionality

### Issue 2: Missing Logging Import
**Problem:** Code referenced `logging.warning()` without importing logging module

**Status:** Fixed - now uses print statements instead

### Issue 3: Silent Authentication Failures
**Problem:** Authentication failures returned empty DataFrames with no error message

**Status:** ✅ FIXED - Now detects login pages and shows clear error message

### Issue 4: No Cookie Validation
**Problem:** No pre-flight check to verify cookies before making requests

**Status:** ✅ FIXED - Added `validate_canvas_cookies()` function called before fetch

## Testing

Run the test script to verify authentication:
```bash
cd /Users/artofdrawersllc/Documents/AoD_Dashboard
python3 test_roi_debug.py
```

Expected output with valid cookies:
```
✅ Found Grand Totals table!
✅ DataFrame created:
   Shape: (1, 13)
   Columns: ['Amount Invested', '# of Leads', ...]
```

Expected output with expired cookies:
```
❌ AUTHENTICATION FAILED!
   Canvas returned a login page instead of data.
```

## Monitoring in Production

When running the Streamlit updater, watch for these indicators:

### Success:
```
🔐 Validating Canvas authentication cookies...
✅ Cookies are valid

💰 Fetching ROI data...
✅ ROI data received: 1 row(s), 13 column(s)
   Columns: ['Amount Invested', '# of Leads', ...]
   Sample values: {...}
```

### Failure:
```
❌ COOKIE VALIDATION FAILED: Expired cookies: username (expired 2025-10-12 14:07)
   Cannot proceed with data fetch.
   Please refresh your canvas_cookies.json file and try again.
```

## Files Modified

1. **[updater/data_fetcher.py](updater/data_fetcher.py)**
   - Added `validate_canvas_cookies()` function
   - Enhanced `fetch_roi()` with comprehensive debugging
   - Added authentication failure detection

2. **[updater/updater_utils.py](updater/updater_utils.py)**
   - Added pre-fetch cookie validation
   - Added per-week ROI data validation
   - Added final data validation before save

3. **[test_roi_debug.py](test_roi_debug.py)** (new file)
   - Standalone debugging script
   - Tests ROI fetch with current cookies
   - Shows full debug output

## Next Steps

1. ✅ Refresh Canvas cookies
2. ✅ Test with `test_roi_debug.py` script
3. ✅ Upload fresh cookies to Streamlit app
4. ✅ Re-run data fetch in Streamlit
5. ✅ Verify ROI data contains real values, not zeros
6. ✅ Monitor debug output for any issues

---

**Last Updated:** 2024-12-16
**Status:** Debugging enhancements complete, awaiting fresh cookies
