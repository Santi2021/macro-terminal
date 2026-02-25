"""
modules/energy.py — Energy & Oil · Oferta / Demanda / Precio
Macro Terminal

Filosofía: Precio es consecuencia del balance O&D.
Cada sección responde UNA pregunta concreta de decision making.

Sources:
  EIA API v2   — inventarios, producción, imports/exports, rig count, demand
  FRED API     — WTI spot, Brent spot, Henry Hub, DXY, real yields
  EIA STEO     — Short-Term Energy Outlook (forecasts)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import os
from datetime import datetime, timedelta

# ── Palette ────────────────────────────────────────────────────────────────────
BG     = "#0d0d1a"
BG2    = "#13132b"
BG3    = "#0a0a16"
GRID   = "#1e1e3a"
TEXT   = "#e8e8f0"
MUTED  = "#6b6b8a"
MUTED2 = "#3d3d5c"
CYAN   = "#00d4ff"
GREEN  = "#10b981"
RED    = "#ef4444"
AMBER  = "#f59e0b"
BLUE   = "#3b82f6"
VIOLET = "#a78bfa"
TEAL   = "#14b8a6"
ORANGE = "#f97316"
PINK   = "#f472b6"
WHITE  = "#e8e8f0"

# ── API Keys ───────────────────────────────────────────────────────────────────
def _eia_key():
    try:    return st.secrets["EIA_API_KEY"]
    except: return os.getenv("EIA_API_KEY", "")

def _fred_key():
    try:    return st.secrets["FRED_API_KEY"]
    except: return os.getenv("FRED_API_KEY", "")

# ── EIA API v2 helper ──────────────────────────────────────────────────────────
EIA_BASE = "https://api.eia.gov/v2"

def _eia_fetch(route: str, params: dict) -> pd.DataFrame:
    """Generic EIA v2 fetch → tidy DataFrame."""
    api_key = _eia_key()
    params["api_key"] = api_key
    url = f"{EIA_BASE}/{route}/data/"
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    body = resp.json()
    data = body.get("response", {}).get("data", [])
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    return df

# ── FRED helper ────────────────────────────────────────────────────────────────
def _fred_fetch(sid: str, start: str = "2000-01-01") -> pd.Series:
    params = {
        "series_id": sid,
        "observation_start": start,
        "api_key": _fred_key(),
        "file_type": "json",
    }
    r = requests.get(
        "https://api.stlouisfed.org/fred/series/observations",
        params=params, timeout=20
    )
    r.raise_for_status()
    rows = []
    for o in r.json().get("observations", []):
        try:
            rows.append({"date": pd.Timestamp(o["date"]), "value": float(o["value"])})
        except Exception:
            continue
    if not rows:
        return pd.Series(dtype=float)
    return pd.DataFrame(rows).set_index("date")["value"].sort_index()

# ── EIA Series definitions ─────────────────────────────────────────────────────
# Weekly Petroleum Status Report (WPSR)
# All inventory in thousand barrels (Mb)

EIA_WEEKLY = {  # (route, series_id, description)
    # Crude — ruta correcta: petroleum/stoc/wstk
    "crude_stocks":     ("petroleum/stoc/wstk", "WCRSTUS1",              "Weekly Crude Stocks USA"),
    "crude_cushing":    ("petroleum/sum/sndw",  "W_EPC0_SAX_YCUOK_MBBL", "Cushing OK Crude Stocks"),
    "crude_spe":        ("petroleum/stoc/wstk", "WCSSTUS1",              "Crude in SPR"),
    # Products — ruta correcta: petroleum/stoc/wstk
    "gasoline_stocks":  ("petroleum/stoc/wstk", "WGTSTUS1",              "Total Gasoline Stocks"),
    "distillate_stocks":("petroleum/stoc/wstk", "WDISTUS1",              "Distillate Fuel Stocks"),
    "jet_stocks":       ("petroleum/stoc/wstk", "WKJSTUS1",              "Kerosene-Jet Fuel Stocks"),
    # Production
    "crude_prod":       ("petroleum/sum/sndw",  "WCRFPUS2",              "US Crude Production (kb/d)"),
    # Imports / Exports
    "crude_imports":    ("petroleum/sum/sndw",  "WCRIMUS2",              "Crude Imports (kb/d)"),
    "crude_exports":    ("petroleum/sum/sndw",  "WCREXUS2",              "Crude Exports (kb/d)"),
    # Refining
    "refinery_runs":    ("petroleum/sum/sndw",  "WCRRIUS2",              "Refinery Crude Runs (kb/d)"),
    "refinery_util":    ("petroleum/sum/sndw",  "WPULEUS3",              "Refinery Utilization (%)"),
    # Implied demand (product supplied = proxy demand)
    "gasoline_demand":  ("petroleum/sum/sndw",  "WGFUPUS2",              "Gasoline Supplied (kb/d)"),
    "distillate_demand":("petroleum/sum/sndw",  "WDIUPUS2",              "Distillate Supplied (kb/d)"),
    "jet_demand":       ("petroleum/sum/sndw",  "WKJUPUS2",              "Jet Fuel Supplied (kb/d)"),
    "total_demand":     ("petroleum/sum/sndw",  "WRPUPUS2",              "Total Petroleum Supplied (kb/d)"),
    # Rig count — Baker Hughes via EIA (monthly)
    "rig_oil":          ("petroleum/crd/drill", "E_ERTRRO_XR0_NUS_C",  "US Oil Rotary Rigs (count)", "monthly"),
}

# FRED series
FRED_ENERGY = {
    "wti":        "DCOILWTICO",      # WTI Crude Oil Spot $/bbl
    "brent":      "DCOILBRENTEU",    # Brent Crude Spot $/bbl
    "natgas":     "DHHNGSP",         # Henry Hub Natural Gas $/MMBtu
    "gasoline_r": "GASREGCOVW",      # US Regular Gasoline retail $/gallon
    "dxy":        "DTWEXBGS",        # Broad USD Index
    "tips10":     "DFII10",          # 10Y Real yield
    "natgas_2":   "MHHNGSP",         # Henry Hub monthly backup (unused)
}

# ── Data loaders ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600*4, show_spinner=False)   # EIA updates Wed ~10:30am ET
def load_eia_series(series_id: str, route: str, start: str = "2015-01-01", frequency: str = "weekly") -> pd.Series:
    """
    Fetch a single EIA series (weekly or monthly).
    Returns pd.Series indexed by date.
    """
    params = {
        "frequency": frequency,
        "data[0]": "value",
        "facets[series][]": series_id,
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "offset": 0,
        "length": 5000,
        "start": start,
    }
    df = _eia_fetch(route, params)
    if df.empty:
        return pd.Series(dtype=float, name=series_id)
    # EIA v2 returns "period" as date string
    df["date"] = pd.to_datetime(df["period"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    s = df.set_index("date")["value"].sort_index().dropna()
    s.name = series_id
    return s


@st.cache_data(ttl=3600*4, show_spinner=False)
def load_all_eia(start: str = "2015-01-01") -> dict:
    """Load all EIA weekly series into a dict of pd.Series."""
    out = {}
    for name, entry in EIA_WEEKLY.items():
        route, sid = entry[0], entry[1]
        freq = entry[3] if len(entry) > 3 else "weekly"
        try:
            out[name] = load_eia_series(sid, route, start, freq)
        except Exception as e:
            out[name] = pd.Series(dtype=float, name=name)
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def load_fred_energy(start: str = "2000-01-01") -> dict:
    """Load all FRED energy series."""
    out = {}
    for name, sid in FRED_ENERGY.items():
        try:
            out[name] = _fred_fetch(sid, start)
        except Exception:
            out[name] = pd.Series(dtype=float)
    return out


@st.cache_data(ttl=3600*24, show_spinner=False)
def load_seasonal_bands(series: pd.Series, years: int = 5) -> pd.DataFrame:
    """
    Build 5-year seasonal min/max/avg band for weekly inventory data.
    Returns DataFrame with columns: week, min5y, max5y, avg5y
    """
    if len(series) == 0:
        return pd.DataFrame()

    df = series.reset_index()
    df.columns = ["date", "value"]
    df["year"]  = df["date"].dt.year
    df["week"]  = df["date"].dt.isocalendar().week.astype(int)

    cutoff_year = df["year"].max() - 1   # exclude current year from band
    hist = df[df["year"] <= cutoff_year].copy()
    recent_hist = hist[hist["year"] >= (cutoff_year - years + 1)]

    band = recent_hist.groupby("week")["value"].agg(
        min5y="min", max5y="max", avg5y="mean"
    ).reset_index()
    return band


# ── Layout helpers ─────────────────────────────────────────────────────────────
def _L(h=360, title=""):
    d = dict(
        paper_bgcolor=BG, plot_bgcolor=BG2,
        font=dict(color=TEXT, size=11, family="monospace"),
        xaxis=dict(gridcolor=GRID, linecolor=GRID, showgrid=False,
                   tickfont=dict(color=MUTED, size=10)),
        yaxis=dict(gridcolor=GRID, linecolor=GRID, zeroline=False,
                   tickfont=dict(color=MUTED, size=10)),
        hovermode="x unified",
        height=h,
        margin=dict(l=60, r=24, t=36, b=36),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT, size=10),
                    orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    if title:
        d["title"] = dict(text=title, font=dict(size=11, color=MUTED,
                          family="monospace"), x=0, xanchor="left")
    return d


def _last(s):
    d = s.dropna()
    return float(d.iloc[-1]) if len(d) else float("nan")

def _prev(s, n=1):
    d = s.dropna()
    return float(d.iloc[-1-n]) if len(d) > n else float("nan")

def _chg(s, n=1):
    return _last(s) - _prev(s, n)

def _trim(s, cut):
    if cut is None or len(s) == 0: return s
    if not isinstance(s.index, pd.DatetimeIndex): return s
    return s[s.index >= pd.Timestamp(cut)]

def _kpi(val, label, sub, color):
    return (f'<div class="kpi-card">'
            f'<div class="kpi-value" style="color:{color}">{val}</div>'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-sub">{sub}</div>'
            f'</div>')

def _insight(text):
    return f'<div class="insight">{text}</div>'

def _sec(text):
    return f'<div class="sec">{text}</div>'


# ── Seasonal chart builder ─────────────────────────────────────────────────────
def _seasonal_chart(series: pd.Series, band_df: pd.DataFrame,
                    label: str, unit: str, color: str,
                    height: int = 340) -> go.Figure:
    """
    Build the canonical EIA-style seasonal inventory chart:
    5Y min/max band (shaded) + 5Y avg (dashed) + current year (solid colored)
    """
    fig = go.Figure()

    if not band_df.empty and len(series):
        # Build current year weekly series aligned to week number
        df_cur = series.reset_index()
        df_cur.columns = ["date", "value"]
        df_cur["week"]  = df_cur["date"].dt.isocalendar().week.astype(int)
        cur_year = df_cur["date"].dt.year.max()
        cur = df_cur[df_cur["date"].dt.year == cur_year].set_index("week")["value"]

        # Prior year for context
        prev_yr = df_cur[df_cur["date"].dt.year == cur_year - 1].set_index("week")["value"]

        weeks = band_df["week"].values

        # 5Y min/max band
        fig.add_trace(go.Scatter(
            name=f"5Y Range",
            x=list(weeks) + list(weeks[::-1]),
            y=list(band_df["max5y"].values) + list(band_df["min5y"].values[::-1]),
            fill="toself",
            fillcolor="rgba(59,130,246,0.10)",
            line=dict(color="rgba(0,0,0,0)"),
            showlegend=True,
            hoverinfo="skip",
        ))

        # 5Y average
        fig.add_trace(go.Scatter(
            name="5Y Avg",
            x=weeks, y=band_df["avg5y"].values,
            line=dict(color=MUTED, width=1.5, dash="dash"),
            hovertemplate=f"<b>5Y Avg</b> W%{{x}}: %{{y:,.0f}} {unit}<extra></extra>",
        ))

        # Prior year
        if len(prev_yr):
            fig.add_trace(go.Scatter(
                name=f"{cur_year-1}",
                x=prev_yr.index, y=prev_yr.values,
                line=dict(color=MUTED2, width=1.5, dash="dot"),
                hovertemplate=f"<b>{cur_year-1}</b> W%{{x}}: %{{y:,.0f}} {unit}<extra></extra>",
            ))

        # Current year — use actual dates for x-axis on the main overlay
        # but for seasonal view use week numbers
        if len(cur):
            fig.add_trace(go.Scatter(
                name=f"{cur_year} (current)",
                x=cur.index, y=cur.values,
                line=dict(color=color, width=3),
                mode="lines",
                hovertemplate=f"<b>{cur_year}</b> W%{{x}}: %{{y:,.0f}} {unit}<extra></extra>",
            ))

            # Latest dot
            latest_week = int(cur.index[-1])
            latest_val  = float(cur.iloc[-1])
            avg_val     = float(band_df[band_df["week"] == latest_week]["avg5y"].values[0]) \
                          if latest_week in band_df["week"].values else float("nan")
            fig.add_trace(go.Scatter(
                name="Latest",
                x=[latest_week], y=[latest_val],
                mode="markers",
                marker=dict(symbol="circle", size=10, color=color,
                            line=dict(color=WHITE, width=2)),
                hovertemplate=f"<b>Latest W{latest_week}</b>: {latest_val:,.0f} {unit}<extra></extra>",
                showlegend=False,
            ))

    l = _L(height)
    l["xaxis"]["title"] = dict(text="Week of Year", font=dict(color=MUTED, size=10))
    l["yaxis"]["title"] = dict(text=unit, font=dict(color=MUTED, size=10))
    l["xaxis"]["range"] = [1, 52]
    fig.update_layout(**l)
    return fig


# ── MAIN RENDER ────────────────────────────────────────────────────────────────
def render():
    st.markdown("""<style>
    .kpi-card{background:#13132b;border:1px solid #1e1e3a;border-radius:8px;
              padding:14px 16px;text-align:center;}
    .kpi-value{font-family:monospace;font-size:1.65rem;font-weight:700;
               letter-spacing:-0.02em;}
    .kpi-label{font-size:0.65rem;color:#6b6b8a;text-transform:uppercase;
               letter-spacing:0.12em;margin-top:5px;}
    .kpi-sub{font-family:monospace;font-size:0.72rem;margin-top:3px;color:#6b6b8a;}
    .sec{font-family:monospace;font-size:0.65rem;color:#6b6b8a;
         text-transform:uppercase;letter-spacing:0.15em;
         margin:20px 0 8px 0;border-bottom:1px solid #1e1e3a;padding-bottom:5px;}
    .insight{background:#0a0a18;border-left:3px solid #00d4ff;
             border-radius:0 6px 6px 0;padding:9px 14px;
             font-family:monospace;font-size:0.76rem;
             color:#9999bb;margin:6px 0 14px 0;line-height:1.5;}
    .od-bar{background:#0a0a16;border:1px solid #1e1e3a;border-radius:8px;
            padding:12px 20px;margin-bottom:16px;
            font-family:monospace;font-size:0.8rem;color:#9999bb;}
    .od-signal{font-size:1rem;font-weight:700;letter-spacing:0.05em;}
    </style>""", unsafe_allow_html=True)

    # ── Range selector ─────────────────────────────────────────────────────────
    col_r, _ = st.columns([4, 8])
    with col_r:
        rng = st.radio("", ["1Y", "2Y", "5Y", "All"],
                       index=1, horizontal=True,
                       label_visibility="collapsed", key="energy_range")
    today = pd.Timestamp.today()
    cut_map = {
        "1Y":  (today - pd.DateOffset(years=1)).strftime("%Y-%m-%d"),
        "2Y":  (today - pd.DateOffset(years=2)).strftime("%Y-%m-%d"),
        "5Y":  (today - pd.DateOffset(years=5)).strftime("%Y-%m-%d"),
        "All": None,
    }
    cut = cut_map[rng]
    # For EIA load — always fetch from 2010 for seasonal bands
    eia_start = "2010-01-01"
    fred_start = "2000-01-01"

    # ── Load data ──────────────────────────────────────────────────────────────
    with st.spinner("Loading EIA + FRED energy data..."):
        try:
            E = load_all_eia(eia_start)
            F = load_fred_energy(fred_start)
        except Exception as e:
            st.error(f"Data fetch error: {e}")
            return

    # ── Key values ─────────────────────────────────────────────────────────────
    l_wti    = _last(F["wti"])
    l_brent  = _last(F["brent"])
    l_spread = l_brent - l_wti          # Brent premium
    l_natgas = _last(F["natgas"])
    l_rig    = _last(E["rig_oil"])

    wti_1w   = _chg(F["wti"], 5)
    wti_1m   = _chg(F["wti"], 22)
    wti_3m   = _chg(F["wti"], 63)
    wti_1y   = _chg(F["wti"], 252)

    l_crude  = _last(E["crude_stocks"])   # Mb (thousand barrels)
    l_prod   = _last(E["crude_prod"])     # kb/d
    l_imp    = _last(E["crude_imports"])  # kb/d
    l_exp    = _last(E["crude_exports"])  # kb/d
    l_runs   = _last(E["refinery_runs"])  # kb/d
    l_util   = _last(E["refinery_util"])  # %
    l_dem    = _last(E["total_demand"])   # kb/d

    # Net supply = production + imports - exports
    l_net_supply = l_prod + l_imp - l_exp if not any(
        pd.isna(x) for x in [l_prod, l_imp, l_exp]) else float("nan")

    # Weekly crude build/draw
    crude_chg_1w = _chg(E["crude_stocks"], 1)   # Mb change WoW

    # O&D signal
    draws = sum(1 for i in range(1, 5) if _chg(E["crude_stocks"], i) < 0)
    if draws >= 3:
        od_signal = "🟢 DRAWS — BULLISH"
        od_color  = GREEN
        od_note   = f"{draws}/4 semanas recientes con draw de inventarios"
    elif draws >= 2:
        od_signal = "🟡 MIXTO"
        od_color  = AMBER
        od_note   = f"{draws}/4 semanas con draw — mercado equilibrado"
    else:
        od_signal = "🔴 BUILDS — BEARISH"
        od_color  = RED
        od_note   = f"Solo {draws}/4 semanas con draw — oferta excede demanda"

    latest_eia_date = E["crude_stocks"].dropna().index[-1].strftime("%b %d, %Y") \
                      if len(E["crude_stocks"].dropna()) else "—"
    latest_wti_date = F["wti"].dropna().index[-1].strftime("%b %d, %Y") \
                      if len(F["wti"].dropna()) else "—"

    # ── O&D SIGNAL BAR ────────────────────────────────────────────────────────
    wti_color = GREEN if wti_1w >= 0 else RED
    st.markdown(f"""
    <div class="od-bar">
      <div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap;">
        <div>
          <div class="od-signal" style="color:{od_color}">{od_signal}</div>
          <div style="font-size:0.68rem;color:{MUTED};margin-top:3px">{od_note}</div>
        </div>
        <div style="width:1px;background:#1e1e3a;height:36px;"></div>
        <div>
          <span style="color:{CYAN};font-weight:700">WTI ${l_wti:.2f}</span>
          <span style="color:{wti_color};margin-left:8px">{wti_1w:+.2f} (1W)</span>
          <span style="color:{MUTED};margin-left:8px">Brent ${l_brent:.2f} · spread {l_spread:+.2f}</span>
        </div>
        <div style="width:1px;background:#1e1e3a;height:36px;"></div>
        <div style="color:{MUTED};font-size:0.68rem">
          EIA: {latest_eia_date} · WTI: {latest_wti_date}
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── KPI ROW ────────────────────────────────────────────────────────────────
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    kpis = [
        (f"${l_wti:.2f}",          "WTI Spot",          f"1M: {wti_1m:+.2f}",
         GREEN if wti_1m >= 0 else RED),
        (f"${l_brent:.2f}",        "Brent Spot",        f"spread: {l_spread:+.2f}",
         CYAN),
        (f"{l_crude/1000:.0f}M bbl","Crude Stocks",     f"WoW: {crude_chg_1w:+.0f}Mb",
         GREEN if crude_chg_1w < 0 else RED),
        (f"{l_prod:.0f} kb/d",     "US Production",     f"vs peak ~13,300",
         AMBER),
        (f"{l_rig:.0f}",           "Oil Rig Count",     f"leading 6M indicator",
         ORANGE),
        (f"${l_natgas:.2f}",       "Henry Hub",         f"Natural Gas $/MMBtu",
         VIOLET),
    ]
    for col, (val, label, sub, color) in zip([c1,c2,c3,c4,c5,c6], kpis):
        with col:
            st.markdown(_kpi(val, label, sub, color), unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 1: PRECIO — WTI & Brent
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown(_sec("1 · Precio — WTI · Brent · Spread"), unsafe_allow_html=True)

    wti_t   = _trim(F["wti"],   cut)
    brent_t = _trim(F["brent"], cut)

    if len(wti_t) and len(brent_t):
        common_p = wti_t.index.intersection(brent_t.index)
        spread_t = brent_t.reindex(common_p) - wti_t.reindex(common_p)

        fig_px = make_subplots(specs=[[{"secondary_y": True}]])

        fig_px.add_trace(go.Scatter(
            name="WTI", x=wti_t.index, y=wti_t.values,
            line=dict(color=CYAN, width=2.5),
            hovertemplate="<b>WTI</b>: $%{y:.2f}<extra></extra>",
        ), secondary_y=False)

        fig_px.add_trace(go.Scatter(
            name="Brent", x=brent_t.index, y=brent_t.values,
            line=dict(color=ORANGE, width=2, dash="dash"),
            hovertemplate="<b>Brent</b>: $%{y:.2f}<extra></extra>",
        ), secondary_y=False)

        fig_px.add_trace(go.Scatter(
            name="Brent-WTI Spread", x=spread_t.index, y=spread_t.values,
            line=dict(color=AMBER, width=1.5),
            fill="tozeroy", fillcolor="rgba(245,158,11,0.06)",
            hovertemplate="<b>Spread</b>: $%{y:.2f}<extra></extra>",
        ), secondary_y=True)

        fig_px.update_layout(**_L(340))
        fig_px.update_yaxes(title_text="$/bbl", gridcolor=GRID, zeroline=False,
                            secondary_y=False, title_font=dict(color=CYAN, size=10),
                            tickprefix="$")
        fig_px.update_yaxes(title_text="Spread $", gridcolor="rgba(0,0,0,0)",
                            zeroline=True, zerolinecolor=MUTED2,
                            secondary_y=True, title_font=dict(color=AMBER, size=10))
        st.plotly_chart(fig_px, use_container_width=True)

        # Performance table
        p1,p2,p3,p4 = st.columns(4)
        perf = [
            ("1W", wti_1w, wti_1w/l_wti*100),
            ("1M", wti_1m, wti_1m/l_wti*100),
            ("3M", wti_3m, wti_3m/l_wti*100),
            ("1Y", wti_1y, wti_1y/l_wti*100),
        ]
        for col, (per, chg, pct) in zip([p1,p2,p3,p4], perf):
            c = GREEN if chg >= 0 else RED
            with col:
                st.markdown(_kpi(f"{chg:+.2f}", f"WTI {per}", f"{pct:+.1f}%", c),
                            unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 2: INVENTARIOS — El Score del Partido
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown(_sec("2 · Inventarios — Score del Partido O&D"), unsafe_allow_html=True)

    inv_tabs = st.tabs(["🛢️ Crude Total", "🏙️ Cushing Hub", "⛽ Gasolina", "🚛 Destilados"])

    inv_configs = [
        ("crude_stocks",      "Crude Total USA",   "Mb",   CYAN,   inv_tabs[0]),
        ("crude_cushing",     "Cushing OK",        "Mb",   ORANGE, inv_tabs[1]),
        ("gasoline_stocks",   "Gasolina",          "Mb",   GREEN,  inv_tabs[2]),
        ("distillate_stocks", "Destilados",        "Mb",   AMBER,  inv_tabs[3]),
    ]

    for key, label, unit, color, tab in inv_configs:
        with tab:
            s = E[key]
            if len(s) == 0:
                st.info(f"EIA data not available for {label}. Check EIA_API_KEY.")
                continue

            band = load_seasonal_bands(s)
            fig_inv = _seasonal_chart(s, band, label, unit, color, height=340)
            st.plotly_chart(fig_inv, use_container_width=True)

            # vs 5Y avg
            if not band.empty:
                cur_week = int(pd.Timestamp.now().isocalendar()[1])
                avg_row  = band[band["week"] == cur_week]
                if len(avg_row):
                    avg_val = float(avg_row["avg5y"].values[0])
                    min_val = float(avg_row["min5y"].values[0])
                    max_val = float(avg_row["max5y"].values[0])
                    cur_val = _last(s)
                    vs_avg  = cur_val - avg_val
                    pct_range = (cur_val - min_val) / (max_val - min_val) * 100 \
                                if (max_val - min_val) != 0 else 50
                    pos_label = ("ABOVE AVG 🔴 → bearish" if vs_avg > 0
                                 else "BELOW AVG 🟢 → bullish")
                    pos_color = RED if vs_avg > 0 else GREEN
                    st.markdown(_insight(
                        f"📊 {label}: <b style='color:{color}'>{cur_val:,.0f} {unit}</b> · "
                        f"vs 5Y avg <b style='color:{pos_color}'>{vs_avg:+,.0f} {unit} ({pos_label})</b> · "
                        f"5Y range percentile: <b style='color:{AMBER}'>{pct_range:.0f}%</b> "
                        f"(0%=min histórico, 100%=max). "
                        f"WoW change: <b style='color:{GREEN if _chg(s) < 0 else RED}'>"
                        f"{_chg(s):+,.0f} {unit}</b>"
                    ), unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 3: OFERTA — Producción + Rig Count
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown(_sec("3 · Oferta — Producción USA · Rig Count · Imports/Exports"),
                unsafe_allow_html=True)

    prod_t = _trim(E["crude_prod"], cut)
    rig_t  = _trim(E["rig_oil"],   cut)
    imp_t  = _trim(E["crude_imports"], cut)
    exp_t  = _trim(E["crude_exports"], cut)

    sup_tabs = st.tabs(["📦 Producción + Rigs", "🔄 Imports vs Exports"])

    with sup_tabs[0]:
        if len(prod_t):
            fig_sup = make_subplots(specs=[[{"secondary_y": True}]])

            fig_sup.add_trace(go.Scatter(
                name="US Crude Production (kb/d)",
                x=prod_t.index, y=prod_t.values,
                line=dict(color=CYAN, width=2.5),
                hovertemplate="<b>Producción</b>: %{y:,.0f} kb/d<extra></extra>",
            ), secondary_y=False)

            # Rig count with 4W MA
            rig_ma4 = rig_t.rolling(4).mean()
            fig_sup.add_trace(go.Bar(
                name="Oil Rig Count",
                x=rig_t.index, y=rig_t.values,
                marker_color=ORANGE, opacity=0.4,
                hovertemplate="<b>Rigs</b>: %{y:.0f}<extra></extra>",
            ), secondary_y=True)
            fig_sup.add_trace(go.Scatter(
                name="Rig 4W MA",
                x=rig_ma4.index, y=rig_ma4.values,
                line=dict(color=AMBER, width=2),
                hovertemplate="<b>Rig 4W MA</b>: %{y:.0f}<extra></extra>",
            ), secondary_y=True)

            fig_sup.update_layout(**_L(360), barmode="overlay")
            fig_sup.update_yaxes(
                title_text="Production kb/d", gridcolor=GRID, zeroline=False,
                secondary_y=False, title_font=dict(color=CYAN, size=10)
            )
            fig_sup.update_yaxes(
                title_text="Rig Count", gridcolor="rgba(0,0,0,0)", zeroline=False,
                secondary_y=True, title_font=dict(color=ORANGE, size=10)
            )
            st.plotly_chart(fig_sup, use_container_width=True)

            # Rig trend
            if len(rig_t) >= 13:
                rig_3m_chg = _last(rig_t) - _prev(rig_t, 13)
                rig_dir = "cayendo 🔻 → señal bearish producción en ~6M" if rig_3m_chg < -10 \
                          else ("subiendo 🔺 → oferta creciente en ~6M" if rig_3m_chg > 10
                                else "estable →")
                st.markdown(_insight(
                    f"🔧 Producción USA: <b style='color:{CYAN}'>{l_prod:,.0f} kb/d</b> · "
                    f"Rig count: <b style='color:{ORANGE}'>{l_rig:.0f}</b> ({rig_dir}). "
                    f"Cambio 3M rigs: <b style='color:{GREEN if rig_3m_chg < 0 else RED}'>"
                    f"{rig_3m_chg:+.0f}</b>. "
                    f"⚡ El rig count lidera la producción por ~6 meses — "
                    f"caída de rigs hoy = menor oferta en H2."
                ), unsafe_allow_html=True)
        else:
            st.info("EIA production data not available — check EIA_API_KEY.")

    with sup_tabs[1]:
        if len(imp_t) and len(exp_t):
            common_ie = imp_t.index.intersection(exp_t.index)
            net_imp   = imp_t.reindex(common_ie) - exp_t.reindex(common_ie)

            fig_ie = go.Figure()
            fig_ie.add_trace(go.Scatter(
                name="Imports", x=imp_t.index, y=imp_t.values,
                line=dict(color=RED, width=2),
                fill="tozeroy", fillcolor="rgba(239,68,68,0.06)",
                hovertemplate="<b>Imports</b>: %{y:,.0f} kb/d<extra></extra>",
            ))
            fig_ie.add_trace(go.Scatter(
                name="Exports", x=exp_t.index, y=exp_t.values,
                line=dict(color=GREEN, width=2),
                fill="tozeroy", fillcolor="rgba(16,185,129,0.06)",
                hovertemplate="<b>Exports</b>: %{y:,.0f} kb/d<extra></extra>",
            ))
            fig_ie.add_trace(go.Scatter(
                name="Net Imports (Imp-Exp)",
                x=net_imp.index, y=net_imp.values,
                line=dict(color=AMBER, width=2, dash="dot"),
                hovertemplate="<b>Net Imports</b>: %{y:,.0f} kb/d<extra></extra>",
            ))
            fig_ie.add_hline(y=0, line_color=MUTED2, line_width=1)
            l_ie = _L(320)
            l_ie["yaxis"]["title"] = dict(text="kb/d", font=dict(color=MUTED, size=10))
            fig_ie.update_layout(**l_ie)
            st.plotly_chart(fig_ie, use_container_width=True)

            l_net = _last(net_imp)
            net_label = "NET IMPORTER" if l_net > 0 else "NET EXPORTER"
            net_color  = AMBER if l_net > 0 else GREEN
            st.markdown(_insight(
                f"🌐 USA {net_label}: imports {l_imp:,.0f} - exports {l_exp:,.0f} = "
                f"<b style='color:{net_color}'>{l_net:+,.0f} kb/d neto</b>. "
                f"USA se convirtió en exportador neto de crudo — "
                f"exports altos reducen la oferta doméstica disponible → bullish precio."
            ), unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 4: DEMANDA — Implied demand (product supplied)
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown(_sec("4 · Demanda — Implied Demand (Product Supplied)"),
                unsafe_allow_html=True)

    gas_d  = _trim(E["gasoline_demand"],   cut)
    dist_d = _trim(E["distillate_demand"], cut)
    jet_d  = _trim(E["jet_demand"],        cut)
    tot_d  = _trim(E["total_demand"],      cut)

    if len(tot_d):
        dem_tabs = st.tabs(["📊 Total & Componentes", "📈 YoY Demanda"])

        with dem_tabs[0]:
            fig_dem = go.Figure()

            for name, s, color in [
                ("Gasolina",    gas_d,  GREEN),
                ("Destilados",  dist_d, AMBER),
                ("Jet Fuel",    jet_d,  VIOLET),
            ]:
                if len(s):
                    # 4-week moving average to smooth weekly noise
                    s_ma = s.rolling(4).mean()
                    fig_dem.add_trace(go.Scatter(
                        name=f"{name} (4W MA)",
                        x=s_ma.index, y=s_ma.values,
                        line=dict(color=color, width=2),
                        hovertemplate=f"<b>{name}</b>: %{{y:,.0f}} kb/d<extra></extra>",
                    ))

            # Total as area
            tot_ma = tot_d.rolling(4).mean()
            fig_dem.add_trace(go.Scatter(
                name="Total Petroleum (4W MA)",
                x=tot_ma.index, y=tot_ma.values,
                line=dict(color=CYAN, width=3),
                hovertemplate="<b>Total</b>: %{y:,.0f} kb/d<extra></extra>",
            ))

            l_dem_fig = _L(340)
            l_dem_fig["yaxis"]["title"] = dict(text="kb/d", font=dict(color=MUTED, size=10))
            fig_dem.update_layout(**l_dem_fig)
            st.plotly_chart(fig_dem, use_container_width=True)

        with dem_tabs[1]:
            # YoY % change in 4W MA demand
            fig_yoy = go.Figure()
            fig_yoy.add_hline(y=0, line_color=MUTED2, line_width=1)

            for name, s, color in [
                ("Total Petroleum", tot_d,  CYAN),
                ("Gasolina",        gas_d,  GREEN),
                ("Destilados",      dist_d, AMBER),
                ("Jet Fuel",        jet_d,  VIOLET),
            ]:
                if len(s) >= 52:
                    s_ma  = s.rolling(4).mean()
                    s_yoy = s_ma.pct_change(52) * 100
                    s_yoy = _trim(s_yoy, cut)
                    if len(s_yoy.dropna()):
                        fig_yoy.add_trace(go.Scatter(
                            name=name, x=s_yoy.index, y=s_yoy.values,
                            line=dict(color=color, width=2),
                            hovertemplate=f"<b>{name} YoY</b>: %{{y:+.1f}}%<extra></extra>",
                        ))

            l_yoy = _L(320)
            l_yoy["yaxis"]["ticksuffix"] = "%"
            l_yoy["yaxis"]["zeroline"]   = True
            l_yoy["yaxis"]["zerolinecolor"] = MUTED2
            fig_yoy.update_layout(**l_yoy)
            st.plotly_chart(fig_yoy, use_container_width=True)

        # Demand insight
        l_gas_d  = _last(gas_d)
        l_dist_d = _last(dist_d)
        l_jet_d  = _last(jet_d)
        dem_trend = "EXPANSION" if _chg(tot_d, 13) > 0 else "CONTRACCIÓN"
        dem_color = GREEN if dem_trend == "EXPANSION" else RED
        st.markdown(_insight(
            f"📊 Demanda implícita total: <b style='color:{CYAN}'>{l_dem:,.0f} kb/d</b> · "
            f"Tendencia 3M: <b style='color:{dem_color}'>{dem_trend}</b>. "
            f"Gasolina: {l_gas_d:,.0f} · Destilados: {l_dist_d:,.0f} · Jet: {l_jet_d:,.0f} kb/d. "
            f"⚡ Destilados = proxy de actividad industrial/logística. "
            f"Jet = proxy de demanda de viajes. Gasolina = consumidor USA."
        ), unsafe_allow_html=True)
    else:
        st.info("EIA demand data not available — check EIA_API_KEY.")

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 5: BALANCE SEMANAL — Builds vs Draws
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown(_sec("5 · Balance Semanal — Crude Builds vs Draws"),
                unsafe_allow_html=True)

    crude_s = E["crude_stocks"]
    if len(crude_s):
        chg_weekly = crude_s.diff()
        chg_t      = _trim(chg_weekly, cut)
        chg_ma4    = chg_t.rolling(4).mean()

        colors_bar = [GREEN if v < 0 else RED for v in chg_t.values]

        fig_bal = go.Figure()
        fig_bal.add_trace(go.Bar(
            name="Weekly Change",
            x=chg_t.index, y=chg_t.values,
            marker_color=colors_bar,
            hovertemplate="<b>%{x|%b %d}</b>: %{y:+,.0f} Mb<extra></extra>",
        ))
        fig_bal.add_trace(go.Scatter(
            name="4W MA",
            x=chg_ma4.index, y=chg_ma4.values,
            line=dict(color=WHITE, width=2),
            hovertemplate="<b>4W MA</b>: %{y:+,.0f} Mb<extra></extra>",
        ))
        fig_bal.add_hline(y=0, line_color=MUTED, line_width=1.5)

        l_bal = _L(320)
        l_bal["barmode"]             = "overlay"
        l_bal["yaxis"]["title"]      = dict(text="Mb change", font=dict(color=MUTED, size=10))
        l_bal["yaxis"]["zeroline"]   = True
        l_bal["yaxis"]["zerolinecolor"] = MUTED2
        fig_bal.update_layout(**l_bal)
        st.plotly_chart(fig_bal, use_container_width=True)

        # Consecutive draws/builds count
        chg_recent = chg_weekly.dropna().iloc[-8:]
        streak = 0
        streak_type = ""
        for v in reversed(chg_recent.values):
            if streak == 0:
                streak_type = "draw" if v < 0 else "build"
                streak = 1
            elif (v < 0 and streak_type == "draw") or (v >= 0 and streak_type == "build"):
                streak += 1
            else:
                break

        streak_color = GREEN if streak_type == "draw" else RED
        ma4_val = float(chg_ma4.dropna().iloc[-1]) if len(chg_ma4.dropna()) else 0
        st.markdown(_insight(
            f"📊 Racha actual: <b style='color:{streak_color}'>"
            f"{streak} semanas consecutivas de {streak_type}s</b>. "
            f"4W MA de cambio: <b style='color:{GREEN if ma4_val < 0 else RED}'>"
            f"{ma4_val:+,.0f} Mb/semana</b>. "
            f"Draws consecutivos = mercado absorbiendo oferta = presión alcista precio. "
            f"Builds = exceso de oferta = presión bajista."
        ), unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 6: REFINERY — El cuello de botella
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown(_sec("6 · Refinería — Utilización + Runs · Crack Spread Proxy"),
                unsafe_allow_html=True)

    runs_t = _trim(E["refinery_runs"], cut)
    util_t = _trim(E["refinery_util"], cut)

    if len(runs_t) and len(util_t):
        fig_ref = make_subplots(specs=[[{"secondary_y": True}]])

        fig_ref.add_trace(go.Scatter(
            name="Refinery Runs (kb/d)",
            x=runs_t.index, y=runs_t.values,
            line=dict(color=TEAL, width=2.5),
            hovertemplate="<b>Runs</b>: %{y:,.0f} kb/d<extra></extra>",
        ), secondary_y=False)

        fig_ref.add_trace(go.Scatter(
            name="Utilization %",
            x=util_t.index, y=util_t.values,
            line=dict(color=PINK, width=2, dash="dot"),
            hovertemplate="<b>Utilization</b>: %{y:.1f}%<extra></extra>",
        ), secondary_y=True)

        # Utilization reference lines
        fig_ref.add_hline(y=90, line_color=AMBER, line_width=1, line_dash="dot",
                          annotation_text="90% capacity",
                          annotation_font=dict(color=AMBER, size=9),
                          secondary_y=True)

        fig_ref.update_layout(**_L(300), barmode="overlay")
        fig_ref.update_yaxes(title_text="Runs kb/d", gridcolor=GRID, zeroline=False,
                             secondary_y=False, title_font=dict(color=TEAL, size=10))
        fig_ref.update_yaxes(title_text="Utilization %", gridcolor="rgba(0,0,0,0)",
                             zeroline=False, secondary_y=True,
                             title_font=dict(color=PINK, size=10))
        st.plotly_chart(fig_ref, use_container_width=True)

        # Crack spread proxy: gasoline retail - WTI
        gas_r_t = _trim(F["gasoline_r"], cut)
        wti_t2  = _trim(F["wti"], cut)
        if len(gas_r_t) and len(wti_t2):
            common_cr = gas_r_t.index.intersection(wti_t2.index)
            # Convert retail gasoline $/gal → $/bbl (×42) and subtract WTI
            crack_proxy = gas_r_t.reindex(common_cr) * 42 - wti_t2.reindex(common_cr)

            fig_crack = go.Figure()
            fig_crack.add_trace(go.Scatter(
                name="Crack Spread Proxy (Gasoline-WTI, $/bbl)",
                x=crack_proxy.index, y=crack_proxy.values,
                line=dict(color=ORANGE, width=2),
                fill="tozeroy", fillcolor="rgba(249,115,22,0.07)",
                hovertemplate="<b>Crack</b>: $%{y:.2f}/bbl<extra></extra>",
            ))
            fig_crack.add_hline(y=0, line_color=MUTED2, line_width=1)
            l_crack = _L(260, "Crack Spread Proxy — Gasoline retail × 42 − WTI spot")
            l_crack["yaxis"]["tickprefix"] = "$"
            fig_crack.update_layout(**l_crack)
            st.plotly_chart(fig_crack, use_container_width=True)

            l_crack_val = _last(crack_proxy)
            st.markdown(_insight(
                f"⚙️ Utilización refinerías: <b style='color:{PINK}'>{l_util:.1f}%</b> · "
                f"Runs: <b style='color:{TEAL}'>{l_runs:,.0f} kb/d</b>. "
                f"Crack spread proxy: <b style='color:{ORANGE}'>${l_crack_val:.2f}/bbl</b>. "
                f"Utilización alta + crack spread comprimiéndose = refinerías bajo presión de margen. "
                f"Crack spread alto = demanda de productos > oferta de crude → bullish refining."
            ), unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 7: RELACIONES MACRO — WTI vs DXY vs Real Yields
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown(_sec("7 · Relaciones Macro — WTI vs DXY · WTI vs Real Yields"),
                unsafe_allow_html=True)

    wti_f   = _trim(F["wti"],    cut)
    dxy_f   = _trim(F["dxy"],    cut)
    tips_f  = _trim(F["tips10"], cut)

    rel_tabs = st.tabs(["💵 WTI vs DXY", "📐 WTI vs Real Yields", "⛽ Natural Gas"])

    with rel_tabs[0]:
        if len(wti_f) and len(dxy_f):
            common_wd = wti_f.index.intersection(dxy_f.index)
            wti_wd  = wti_f.reindex(common_wd)
            dxy_wd  = dxy_f.reindex(common_wd)

            fig_wd = make_subplots(specs=[[{"secondary_y": True}]])
            fig_wd.add_trace(go.Scatter(
                name="WTI $/bbl", x=wti_wd.index, y=wti_wd.values,
                line=dict(color=CYAN, width=2.5),
                hovertemplate="<b>WTI</b>: $%{y:.2f}<extra></extra>",
            ), secondary_y=False)
            fig_wd.add_trace(go.Scatter(
                name="USD Broad Index (inverted)", x=dxy_wd.index, y=dxy_wd.values,
                line=dict(color=ORANGE, width=2, dash="dash"),
                hovertemplate="<b>DXY</b>: %{y:.1f}<extra></extra>",
            ), secondary_y=True)

            fig_wd.update_layout(**_L(320))
            fig_wd.update_yaxes(title_text="WTI $/bbl", gridcolor=GRID, zeroline=False,
                                secondary_y=False, title_font=dict(color=CYAN, size=10),
                                tickprefix="$")
            fig_wd.update_yaxes(title_text="USD Index", gridcolor="rgba(0,0,0,0)",
                                zeroline=False, secondary_y=True,
                                title_font=dict(color=ORANGE, size=10),
                                autorange="reversed")    # invert DXY to show correlation
            st.plotly_chart(fig_wd, use_container_width=True)

            # Rolling correlation
            if len(common_wd) >= 63:
                corr_3m = wti_wd.rolling(63).corr(dxy_wd).dropna()
                corr_val = float(corr_3m.iloc[-1])
                corr_t   = _trim(corr_3m, cut)
                fig_corr = go.Figure()
                fig_corr.add_hline(y=0, line_color=MUTED2, line_width=1)
                fig_corr.add_hline(y=-0.6, line_color=GREEN, line_width=1, line_dash="dot",
                                   annotation_text="Strong negative",
                                   annotation_font=dict(color=GREEN, size=9))
                fig_corr.add_trace(go.Scatter(
                    name="WTI/DXY 63D Rolling Correlation",
                    x=corr_t.index, y=corr_t.values,
                    line=dict(color=VIOLET, width=2),
                    fill="tozeroy", fillcolor="rgba(167,139,250,0.07)",
                    hovertemplate="<b>Corr</b>: %{y:.2f}<extra></extra>",
                ))
                l_corr = _L(220, "Rolling 63D Correlation — WTI vs USD")
                l_corr["yaxis"]["range"] = [-1.1, 1.1]
                fig_corr.update_layout(**l_corr)
                st.plotly_chart(fig_corr, use_container_width=True)

                l_dxy = _last(F["dxy"])
                st.markdown(_insight(
                    f"💵 Correlación WTI/DXY 63D: <b style='color:{VIOLET}'>{corr_val:.2f}</b>. "
                    f"DXY actual: <b style='color:{ORANGE}'>{l_dxy:.1f}</b>. "
                    f"La correlación inversa WTI-USD es estructural — oil cotiza en dólares. "
                    f"USD fuerte = oil más caro en otras monedas = demanda global comprimida. "
                    f"Correlación cerca de -1 = el dólar está dominando el movimiento del precio."
                ), unsafe_allow_html=True)

    with rel_tabs[1]:
        if len(wti_f) and len(tips_f):
            common_wr = wti_f.index.intersection(tips_f.index)
            wti_wr  = wti_f.reindex(common_wr)
            tips_wr = tips_f.reindex(common_wr)

            fig_wr = make_subplots(specs=[[{"secondary_y": True}]])
            fig_wr.add_trace(go.Scatter(
                name="WTI $/bbl", x=wti_wr.index, y=wti_wr.values,
                line=dict(color=CYAN, width=2.5),
                hovertemplate="<b>WTI</b>: $%{y:.2f}<extra></extra>",
            ), secondary_y=False)
            fig_wr.add_trace(go.Scatter(
                name="10Y Real Yield (TIPS)", x=tips_wr.index, y=tips_wr.values,
                line=dict(color=TEAL, width=2, dash="dash"),
                hovertemplate="<b>Real Yield</b>: %{y:.2f}%<extra></extra>",
            ), secondary_y=True)

            fig_wr.update_layout(**_L(320))
            fig_wr.update_yaxes(title_text="WTI $/bbl", gridcolor=GRID, zeroline=False,
                                secondary_y=False, title_font=dict(color=CYAN, size=10),
                                tickprefix="$")
            fig_wr.update_yaxes(title_text="Real Yield %", gridcolor="rgba(0,0,0,0)",
                                zeroline=True, zerolinecolor=MUTED2,
                                secondary_y=True, title_font=dict(color=TEAL, size=10),
                                ticksuffix="%")
            st.plotly_chart(fig_wr, use_container_width=True)

            l_tips = _last(F["tips10"])
            st.markdown(_insight(
                f"📐 Real yield 10Y: <b style='color:{TEAL}'>{l_tips:.2f}%</b>. "
                f"Real yields altos = costo de oportunidad de holdear commodities sube = presión bajista. "
                f"Real yields negativos o en caída = entorno favorable para commodities como store of value. "
                f"La relación es más fuerte en Gold, pero aplica a oil en períodos de demanda estable."
            ), unsafe_allow_html=True)

    with rel_tabs[2]:
        ng_t = _trim(F["natgas"], cut)
        if len(ng_t):
            fig_ng = go.Figure()
            ng_ma4  = ng_t.rolling(20).mean()  # ~monthly MA for daily data
            fig_ng.add_trace(go.Scatter(
                name="Henry Hub $/MMBtu",
                x=ng_t.index, y=ng_t.values,
                line=dict(color=VIOLET, width=1.5),
                hovertemplate="<b>Henry Hub</b>: $%{y:.2f}/MMBtu<extra></extra>",
            ))
            fig_ng.add_trace(go.Scatter(
                name="20D MA",
                x=ng_ma4.index, y=ng_ma4.values,
                line=dict(color=WHITE, width=2.5),
                hovertemplate="<b>20D MA</b>: $%{y:.2f}<extra></extra>",
            ))
            l_ng = _L(300)
            l_ng["yaxis"]["tickprefix"] = "$"
            l_ng["yaxis"]["title"] = dict(text="$/MMBtu", font=dict(color=MUTED, size=10))
            fig_ng.update_layout(**l_ng)
            st.plotly_chart(fig_ng, use_container_width=True)

            ng_1m = _chg(F["natgas"], 22)
            ng_color = GREEN if ng_1m >= 0 else RED
            st.markdown(_insight(
                f"⛽ Henry Hub: <b style='color:{VIOLET}'>${l_natgas:.2f}/MMBtu</b> · "
                f"1M change: <b style='color:{ng_color}'>{ng_1m:+.2f}</b>. "
                f"Gas → power gen → industria. "
                f"Gas alto comprime márgenes industriales y eleva costos de electricidad."
            ), unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 8: SNAPSHOT TABLE — Todo en un vistazo
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown(_sec("8 · Snapshot — Niveles · Cambios · Contexto"),
                unsafe_allow_html=True)

    snap_items = [
        ("WTI $/bbl",          F["wti"],              "price"),
        ("Brent $/bbl",        F["brent"],             "price"),
        ("Henry Hub $/MMBtu",  F["natgas"],            "price"),
        ("Gasoline Retail $/g",F["gasoline_r"],        "price"),
        ("Crude Stocks (Mb)",  E["crude_stocks"],      "level"),
        ("Cushing (Mb)",       E["crude_cushing"],     "level"),
        ("Gasoline Stocks (Mb)",E["gasoline_stocks"],  "level"),
        ("Distillate (Mb)",    E["distillate_stocks"], "level"),
        ("US Production (kb/d)",E["crude_prod"],       "level"),
        ("Crude Imports (kb/d)",E["crude_imports"],    "level"),
        ("Crude Exports (kb/d)",E["crude_exports"],    "level"),
        ("Refinery Runs (kb/d)",E["refinery_runs"],    "level"),
        ("Refinery Util (%)",  E["refinery_util"],     "pct"),
        ("Total Demand (kb/d)",E["total_demand"],      "level"),
        ("Oil Rig Count",      E["rig_oil"],           "level"),
        ("USD Index",          F["dxy"],               "idx"),
        ("10Y Real Yield",     F["tips10"],            "rate"),
    ]

    rows = {}
    for label, s, kind in snap_items:
        d = s.dropna()
        if len(d) == 0:
            continue
        cur = float(d.iloc[-1])
        deltas = {}
        for dname, dn in [("1W Δ", 1), ("4W Δ", 4), ("13W Δ", 13), ("52W Δ", 52)]:
            # Weekly series: 1 obs = 1 week; daily: 1 obs = 1 day
            # Determine if weekly by checking avg gap
            if len(d) > 10:
                avg_gap = (d.index[-1] - d.index[0]).days / len(d)
                mult = 1 if avg_gap > 4 else 5  # weekly vs daily
            else:
                mult = 1
            n = dn * mult
            if len(d) > n:
                deltas[dname] = float(d.iloc[-1] - d.iloc[-n])
            else:
                deltas[dname] = float("nan")
        rows[label] = {"Current": cur, **deltas}

    if rows:
        snap_df = pd.DataFrame(rows).T

        def _cc_cur(val):
            b = "text-align:center;font-family:monospace;font-size:0.79rem;padding:5px 8px;"
            return f"background:#13132b;color:{TEXT};{b}"

        def _cc_d(val):
            b = "text-align:center;font-family:monospace;font-size:0.79rem;padding:5px 8px;"
            if pd.isna(val): return f"background:#0d0d1a;color:{MUTED2};{b}"
            if val > 500:    return f"background:#3d1010;color:#f87171;{b}"
            elif val > 0:    return f"background:#2d1515;color:#fca5a5;{b}"
            elif val < -500: return f"background:#0d4f2b;color:#4ade80;{b}"
            elif val < 0:    return f"background:#0a3320;color:#34d399;{b}"
            else:            return f"background:#13132b;color:{MUTED};{b}"

        styled = snap_df.style\
            .applymap(_cc_cur, subset=["Current"])\
            .applymap(_cc_d, subset=["1W Δ","4W Δ","13W Δ","52W Δ"])\
            .format({
                "Current": lambda v: "—" if pd.isna(v) else f"{v:,.1f}",
                "1W Δ":   lambda v: "—" if pd.isna(v) else f"{v:+,.1f}",
                "4W Δ":   lambda v: "—" if pd.isna(v) else f"{v:+,.1f}",
                "13W Δ":  lambda v: "—" if pd.isna(v) else f"{v:+,.1f}",
                "52W Δ":  lambda v: "—" if pd.isna(v) else f"{v:+,.1f}",
            })
        st.dataframe(styled, use_container_width=True)

    st.markdown(
        f'<div style="color:{MUTED};font-size:0.68rem;margin-top:10px;font-family:monospace">'
        f'Sources: EIA API v2 (Weekly Petroleum Status Report) · FRED (WTI, Brent, Henry Hub, '
        f'Gasoline, DXY, TIPS, Baker Hughes Rig Count) · '
        f'Inventories in thousand barrels (Mb) · Production/demand in kb/d · '
        f'Seasonal bands = 5-year historical range (prior years only)</div>',
        unsafe_allow_html=True)
