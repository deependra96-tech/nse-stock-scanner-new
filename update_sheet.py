import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import requests
import zipfile
import io
from datetime import datetime, timedelta
import os
import json

# Credentials
creds_json = os.environ.get('GCP_CREDENTIALS')

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

# अपनी Google Sheet ID यहाँ डालें
spreadsheet_id = "1I7Na1hK7rqa6SRe5vHKMvw16_Z6xYpOtO2KjGCDBVBs"

worksheet = client.open_by_key(spreadsheet_id).worksheet("Top 250 Stocks")

def fetch_data(date_obj):

    date_str = date_obj.strftime("%Y%m%d")

    url = f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{date_str}_F_0000.csv.zip"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:

        response = requests.get(url, headers=headers, timeout=20)

        if response.status_code == 200:

            with zipfile.ZipFile(io.BytesIO(response.content)) as z:

                csv_file = z.namelist()[0]

                with z.open(csv_file) as f:

                    df = pd.read_csv(f)

                    symbol_col = "TckrSymb" if "TckrSymb" in df.columns else "SYMBOL"
                    volume_col = "TtlTradgVol" if "TtlTradgVol" in df.columns else "TOTTRDQTY"
                    close_col = "ClsPric" if "ClsPric" in df.columns else "CLOSE"
                    series_col = "SctySrs" if "SctySrs" in df.columns else "SERIES"

                    df = df[df[series_col] == "EQ"]

                    df = df.sort_values(
                        by=volume_col,
                        ascending=False
                    ).head(250)

                    return df[[symbol_col, volume_col, close_col]].values.tolist()

    except Exception as e:
        print(e)

    return None

today = datetime.now()

data = None

for i in range(7):

    test_date = today - timedelta(days=i)

    if test_date.weekday() >= 5:
        continue

    data = fetch_data(test_date)

    if data:
        break

if data:

    worksheet.batch_clear(['A2:C251'])

    worksheet.update('A2', data)

    print("SUCCESS")

else:

    print("FAILED")
