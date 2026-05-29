import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import requests
import zipfile
import io
from datetime import datetime, timedelta
import os
import json

# 1. Credentials Setup
creds_json = os.environ.get('GCP_CREDENTIALS')

if not creds_json:
    print("ERROR: GCP_CREDENTIALS secret missing!")
    exit(1)

creds_dict = json.loads(creds_json)

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    creds_dict,
    scope
)

client = gspread.authorize(creds)

# YOUR GOOGLE SHEET ID
spreadsheet_id = "1I7Na1hK7rqa6SRe5vHKMvw16_Z6xYpOtO2KjGCDBVBs"

# CONNECT BOTH SHEETS
try:
    ws_volume = client.open_by_key(spreadsheet_id).worksheet("Top 250 Stocks")
    ws_turnover = client.open_by_key(spreadsheet_id).worksheet("Top 250 Turnover")

except Exception as e:
    print(f"Sheet Connection Error: {e}")
    exit(1)

# 2. NSE DATA FETCHER

def fetch_bhavcopy_for_date(date_obj):

    date_str = date_obj.strftime("%Y%m%d")

    url = f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{date_str}_F_0000.csv.zip"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    print(f"Checking date: {date_obj.strftime('%d-%m-%Y')}")

    try:

        response = requests.get(url, headers=headers, timeout=20)

        if response.status_code == 200:

            print("File found. Processing...")

            with zipfile.ZipFile(io.BytesIO(response.content)) as z:

                csv_filename = z.namelist()[0]

                with z.open(csv_filename) as f:

                    df = pd.read_csv(f)

                    # Detect Columns
                    symbol_col = "TckrSymb" if "TckrSymb" in df.columns else "SYMBOL"

                    close_col = "ClsPric" if "ClsPric" in df.columns else "CLOSE"

                    series_col = "SctySrs" if "SctySrs" in df.columns else "SERIES"

                    # Volume Column
                    volume_col = "TtlTradgVol"

                    for c in [
                        "TtlTradgVol",
                        "TOTTRDQTY",
                        "TtlTrdQty",
                        "TotTrdQty"
                    ]:
                        if c in df.columns:
                            volume_col = c
                            break

                    # Turnover Column
                    turnover_col = "TtlTrfVal"

                    for c in [
                        "TtlTrfVal",
                        "TOTTRDVAL",
                        "TtlTrdVal",
                        "TotTrdVal"
                    ]:
                        if c in df.columns:
                            turnover_col = c
                            break

                    # Filter EQ Series
                    if series_col in df.columns:
                        df = df[df[series_col].astype(str).str.strip() == "EQ"]

                    # Remove ETFs / Gold / Liquid
                    filter_keywords = 'BEES|ETF|GOLD|LIQUID|CASE|SILVER|LIQ'

                    df = df[
                        ~df[symbol_col].astype(str).str.contains(
                            filter_keywords,
                            case=False,
                            na=False
                        )
                    ]

                    # TOP 250 BY VOLUME
                    df_volume = df.sort_values(
                        by=volume_col,
                        ascending=False
                    ).head(250)

                    data_volume = df_volume[
                        [symbol_col, volume_col, close_col]
                    ].values.tolist()

                    # TOP 250 BY TURNOVER
                    df_turnover = df.sort_values(
                        by=turnover_col,
                        ascending=False
                    ).head(250)

                    data_turnover = df_turnover[
                        [symbol_col, turnover_col, close_col]
                    ].values.tolist()

                    return data_volume, data_turnover

        else:
            print(f"NSE returned status code: {response.status_code}")

            return None, None

    except Exception as e:

        print(f"Error: {e}")

        return None, None

# 3. EXECUTION LOGIC

today = datetime.now()

data_volume = None
data_turnover = None

fetched_date = ""

for i in range(7):

    test_date = today - timedelta(days=i)

    # Skip Saturday / Sunday
    if test_date.weekday() >= 5:
        continue

    vol_data, turn_data = fetch_bhavcopy_for_date(test_date)

    if vol_data and turn_data:

        data_volume = vol_data
        data_turnover = turn_data

        fetched_date = test_date.strftime("%d-%b-%Y")

        break

# 4. UPDATE SHEETS

if data_volume and data_turnover:

    try:

        # UPDATE VOLUME SHEET
        ws_volume.batch_clear(['A2:C251'])

        ws_volume.update('A2', data_volume)

        # UPDATE TURNOVER SHEET
        ws_turnover.batch_clear(['A2:C251'])

        ws_turnover.update('A2', data_turnover)

        # STATUS MESSAGE
        ist_now = (
            datetime.utcnow() +
            timedelta(hours=5, minutes=30)
        ).strftime('%d-%b %H:%M')

        status_msg = f"Data Date: {fetched_date} | Last Update: {ist_now} (IST)"

        ws_volume.update('K2', [[status_msg]])

        ws_turnover.update('K2', [[status_msg]])

        print("SUCCESS: Both sheets updated successfully!")

    except Exception as e:

        print(f"Google Sheet Update Error: {e}")

else:

    print("FAILED: No NSE file found in last 7 days.")
