"""
utils/fred.py — FRED API client for Macro Terminal
"""

import requests
import pandas as pd
import os

FRED_BASE_URL = "https://api.stlouisfed.org/fred"
API_KEY = os.getenv("FRED_API_KEY", "")  # Set in Streamlit secrets


def fetch_series(series_id: str, observation_start: str = "2000-01-01") -> pd.DataFrame:
    """
    Fetch a FRED series.

    Returns DataFrame with columns: date, value
    """
    if not API_KEY:
        raise ValueError("FRED_API_KEY not set. Add it to .streamlit/secrets.toml")

    url = f"{FRED_BASE_URL}/series/observations"
    params = {
        "series_id": series_id,
        "observation_start": observation_start,
        "api_key": API_KEY,
        "file_type": "json",
    }

    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    df = pd.DataFrame(data["observations"])
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df[["date", "value"]].dropna().sort_values("date").reset_index(drop=True)
    return df


def fetch_multiple(series_dict: dict, observation_start: str = "2000-01-01") -> pd.DataFrame:
    """
    Fetch multiple FRED series and merge into a single wide DataFrame.
    
    series_dict: {column_name: series_id}  e.g. {"fed_funds": "FEDFUNDS"}
    """
    dfs = []
    for col_name, series_id in series_dict.items():
        df = fetch_series(series_id, observation_start)
        df = df.rename(columns={"value": col_name})
        dfs.append(df.set_index("date"))

    if not dfs:
        return pd.DataFrame()

    combined = dfs[0]
    for df in dfs[1:]:
        combined = combined.join(df, how="outer")

    return combined.sort_index().reset_index()
