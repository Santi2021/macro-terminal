"""
utils/bls.py — BLS API client for Macro Terminal
"""

import requests
import pandas as pd
import os
import json

BLS_BASE_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
API_KEY = os.getenv("BLS_API_KEY", "")  # Set in Streamlit secrets


def fetch_series(series_ids: list, start_year: str = "2000", end_year: str = None) -> pd.DataFrame:
    """
    Fetch one or more BLS series.
    
    Returns tidy DataFrame with columns: series_id, date, value
    """
    if end_year is None:
        end_year = str(pd.Timestamp.now().year)

    headers = {"Content-type": "application/json"}
    payload = {
        "seriesid": series_ids,
        "startyear": start_year,
        "endyear": end_year,
        "registrationkey": API_KEY,
    }

    resp = requests.post(BLS_BASE_URL, data=json.dumps(payload), headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    rows = []
    for series in data["Results"]["series"]:
        sid = series["seriesID"]
        for obs in series["data"]:
            period = obs["period"]  # e.g. "M01" or "Q01"
            year = obs["year"]
            value = obs["value"]

            if period.startswith("M") and period != "M13":
                month = int(period[1:])
                date = pd.Timestamp(f"{year}-{month:02d}-01")
            elif period.startswith("Q"):
                q = int(period[1:])
                month = q * 3 - 2
                date = pd.Timestamp(f"{year}-{month:02d}-01")
            elif period == "A01":
                date = pd.Timestamp(f"{year}-01-01")
            else:
                continue

            try:
                val = float(value)
            except Exception:
                continue

            rows.append({"series_id": sid, "date": date, "value": val})

    df = pd.DataFrame(rows).sort_values(["series_id", "date"]).reset_index(drop=True)
    return df


def wide_format(df: pd.DataFrame, name_map: dict = None) -> pd.DataFrame:
    """
    Pivot tidy BLS DataFrame to wide format.
    
    name_map: {series_id: column_name}
    """
    wide = df.pivot(index="date", columns="series_id", values="value").reset_index()
    if name_map:
        wide = wide.rename(columns=name_map)
    return wide.sort_values("date").reset_index(drop=True)
