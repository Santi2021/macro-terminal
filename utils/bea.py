"""
utils/bea.py — Generic BEA API client for Macro Terminal
"""

import requests
import pandas as pd
import json
import os
from datetime import datetime

BEA_BASE_URL = "https://apps.bea.gov/api/data"
API_KEY = os.getenv("BEA_API_KEY", "081DA2FC-1900-47A0-A40B-49C31925E395")


def fetch_nipa(table_name: str, frequency: str = "Q", year: str = "ALL") -> pd.DataFrame:
    """
    Fetch a NIPA table from BEA and return a tidy DataFrame.
    
    Parameters
    ----------
    table_name : str  e.g. "T10102"
    frequency  : str  "Q" | "A" | "M"
    year       : str  "ALL" or comma-separated e.g. "2020,2021,2022"
    
    Returns
    -------
    pd.DataFrame with columns: SeriesCode, LineDescription, TimePeriod, DataValue
    """
    params = {
        "UserID": API_KEY,
        "method": "GetData",
        "DataSetName": "NIPA",
        "TableName": table_name,
        "Frequency": frequency,
        "Year": year,
        "ResultFormat": "JSON",
    }

    resp = requests.get(BEA_BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    rows = data["BEAAPI"]["Results"]["Data"]
    df = pd.DataFrame(rows)

    # Clean numeric column
    df["DataValue"] = (
        df["DataValue"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .replace("", "0")
        .astype(float)
    )

    # Parse TimePeriod → datetime-friendly string kept as-is; add sortable date
    df["Date"] = df["TimePeriod"].apply(_period_to_date)

    return df.sort_values("Date").reset_index(drop=True)


def _period_to_date(period: str) -> pd.Timestamp:
    """Convert BEA period string (e.g. '2023Q3', '2023') to Timestamp."""
    period = str(period).strip()
    if "Q" in period:
        year, q = period.split("Q")
        month = int(q) * 3 - 2  # Q1→1, Q2→4, Q3→7, Q4→10
        return pd.Timestamp(f"{year}-{month:02d}-01")
    elif len(period) == 4:  # Annual
        return pd.Timestamp(f"{period}-01-01")
    else:
        try:
            return pd.Timestamp(period)
        except Exception:
            return pd.NaT


def get_series(df: pd.DataFrame, series_code: str) -> pd.Series:
    """Extract a single series by SeriesCode, indexed by Date."""
    mask = df["SeriesCode"] == series_code
    subset = df[mask].set_index("Date")["DataValue"]
    return subset.sort_index()


def get_series_by_description(df: pd.DataFrame, keyword: str) -> pd.DataFrame:
    """Filter rows where LineDescription contains keyword (case-insensitive)."""
    mask = df["LineDescription"].str.contains(keyword, case=False, na=False)
    return df[mask]
