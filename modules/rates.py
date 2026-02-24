"""
modules/rates.py — Rates & Financial Conditions v2
Macro Terminal — Desk Head build

Sources:
  FRED API     — Treasuries, SOFR corridor, TIPS, NFCI, VIX, spreads BAML,
                 mortgage, dollar index, TED spread
  US Treasury  — Yield curve oficial (sin key, mismo día)
  yfinance     — TLT, HYG, LQD, SHY para ratio proxies
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import os

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False

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
BLUE2  = "#1d4ed8"
VIOLET = "#a78bfa"
TEAL   = "#14b8a6"
PINK   = "#f472b6"
ORANGE = "#f97316"
WHITE  = "#e8e8f0"

# ── FRED Series map ────────────────────────────────────────────────────────────
FRED = {
    # Yield curve — Treasuries
    "dgs1m":  "DGS1MO",
    "dgs3m":  "DGS3MO",
    "dgs6m":  "DGS6MO",
    "dgs1":   "DGS1",
    "dgs2":   "DGS2",
    "dgs5":   "DGS5",
    "dgs7":   "DGS7",
    "dgs10":  "DGS10",
    "dgs20":  "DGS20",
    "dgs30":  "DGS30",
    # Spreads
    "t10y2y": "T10Y2Y",
    "t10y3m": "T10Y3M",
    # Fed corridor
    "fedfunds": "FEDFUNDS",
    "fed_lb":   "DFEDTARL",
    "fed_ub":   "DFEDTARU",
    "sofr":     "SOFR",
    "obfr":     "OBFR",
    "iorb":     "IORB",
    "onrrp":    "RRPONTSYAWARD",
    "onrrp_vol":"RRPONTTLD",
    # TIPS / Real
    "tips5":   "DFII5",
    "tips10":  "DFII10",
    "tips30":  "DFII30",
    # Breakevens
    "bei5":    "T5YIE",
    "bei10":   "T10YIE",
    # Credit OAS — BAML (values in %, multiply ×100 for bp)
    "ig_oas":  "BAMLC0A0CM",
    "hy_oas":  "BAMLH0A0HYM2",
    "bbb_oas": "BAMLC0A4CBBB",
    # Financial conditions
    "nfci":    "NFCI",
    "vix":     "VIXCLS",
    # Transmission
    "mortgage30": "MORTGAGE30US",
    "dollar":     "DTWEXBGS",
    "ted":        "TEDRATE",
}

# Tenor ordering for yield curve
TENORS     = ["1M","3M","6M","1Y","2Y","5Y","7Y","10Y","20Y","30Y"]
TENOR_KEYS = ["dgs1m","dgs3m","dgs6m","dgs1","dgs2","dgs5","dgs7","dgs10","dgs20","dgs30"]

# ── API helpers ────────────────────────────────────────────────────────────────
def _fkey():
    try:    return st.secrets["FRED_API_KEY"]
    except: return os.getenv("FRED_API_KEY", "")


def _fetch_fred(sid: str, start: str = "1995-01-01") -> pd.Series:
    params = {
        "series_id": sid,
        "observation_start": start,
        "api_key": _fkey(),
        "file_type": "json",
    }
    r = requests.get("https://api.stlouisfed.org/fred/series/observations",
                     params=params, timeout=20)
    r.raise_for_status()
    rows = []
    for o in r.json()["observations"]:
        try:
            rows.append({"date": pd.Timestamp(o["date"]), "value": float(o["value"])})
        except Exception:
            continue
    if not rows:
        return pd.Series(dtype=float)
    return pd.DataFrame(rows).set_index("date")["value"].sort_index()


def _fetch_treasury_curve() -> pd.Series:
    """
    Fetch today's yield curve from US Treasury XML feed.
    Returns Series indexed by tenor label.
    Falls back gracefully if unavailable.
    """
    try:
        url = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
        params = {"data": "daily_treasury_yield_curve", "field_tdr_date_value_month": pd.Timestamp.now().strftime("%Y%m")}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        # Parse XML
        import xml.etree.ElementTree as ET
        root = ET.fromstring(r.text)
        ns = {"m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
              "d": "http://schemas.microsoft.com/ado/2007/08/dataservices"}
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        if not entries:
            return pd.Series(dtype=float)
        # Take the last entry (most recent date)
        last_entry = entries[-1]
        props = last_entry.find(".//{http://schemas.microsoft.com/ado/2007/08/dataservices/metadata}properties")
        tenor_map = {
            "BC_1MONTH":"1M","BC_3MONTH":"3M","BC_6MONTH":"6M",
            "BC_1YEAR":"1Y","BC_2YEAR":"2Y","BC_3YEAR":"3Y",
            "BC_5YEAR":"5Y","BC_7YEAR":"7Y","BC_10YEAR":"10Y",
            "BC_20YEAR":"20Y","BC_30YEAR":"30Y",
        }
        curve = {}
        for tag, label in tenor_map.items():
            el = props.find(f"{{http://schemas.microsoft.com/ado/2007/08/dataservices}}{tag}")
            if el is not None and el.text:
                try: curve[label] = float(el.text)
                except: pass
        return pd.Series(curve)
    except Exception:
        return pd.Series(dtype=float)


@st.cache_data(ttl=3600, show_spinner=False)
def load_fred_data(start: str = "1995-01-01") -> dict:
    data = {}
    for name, sid in FRED.items():
        try:   data[name] = _fetch_fred(sid, start)
        except: data[name] = pd.Series(dtype=float)
    return data


@st.cache_data(ttl=1800, show_spinner=False)
def load_treasury_curve() -> pd.Series:
    return _fetch_treasury_curve()


@st.cache_data(ttl=3600, show_spinner=False)
def load_yf_data() -> dict:
    if not YF_AVAILABLE:
        return {}
    tickers = {"TLT":"TLT","HYG":"HYG","LQD":"LQD","SHY":"SHY"}
    out = {}
    for name, ticker in tickers.items():
        try:
            df = yf.download(ticker, start="2003-01-01", progress=False, auto_adjust=True)
            out[name] = df["Close"].squeeze()
        except Exception:
            out[name] = pd.Series(dtype=float)
    return out


# ── Layout helper ──────────────────────────────────────────────────────────────
def _L(h=360, title="", rmargin=30):
    d = dict(
        paper_bgcolor=BG, plot_bgcolor=BG2,
        font=dict(color=TEXT, size=11, family="monospace"),
        xaxis=dict(gridcolor=GRID, linecolor=GRID, showgrid=False,
                   tickfont=dict(color=MUTED, size=10)),
        yaxis=dict(gridcolor=GRID, linecolor=GRID, zeroline=False,
                   tickfont=dict(color=MUTED, size=10)),
        hovermode="x unified",
        height=h,
        margin=dict(l=55, r=rmargin, t=36, b=36),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT, size=10),
                    orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    if title:
        d["title"] = dict(text=title, font=dict(size=11, color=MUTED,
                          family="monospace"), x=0, xanchor="left")
    return d


def _last(s): return s.dropna().iloc[-1] if len(s.dropna()) else float("nan")
def _prev(s): return s.dropna().iloc[-2] if len(s.dropna()) >= 2 else float("nan")

def _pctile(s, val):
    d = s.dropna()
    if len(d) == 0: return float("nan")
    return (d <= val).mean() * 100

def _trim(s, cut):
    if cut == 0: return s
    return s.iloc[cut:] if len(s) > abs(cut) else s

def _regime_label(real, spr, nfci, hy_bp):
    """Derive cycle regime from real rate, 2s10s, NFCI, HY."""
    score = 0
    if not pd.isna(real)  and real  > 1.0:  score += 2
    if not pd.isna(spr)   and spr   < 0:    score += 2
    if not pd.isna(nfci)  and nfci  > 0.3:  score += 1
    if not pd.isna(hy_bp) and hy_bp > 500:  score += 1
    if score >= 4:   return "🔴 RESTRICTIVO", RED
    elif score >= 2: return "🟡 TRANSICIÓN",  AMBER
    else:            return "🟢 ACOMODATICIO", GREEN


# ── RENDER ─────────────────────────────────────────────────────────────────────
def render():
    st.markdown("""<style>
    .kpi-card{background:#13132b;border:1px solid #1e1e3a;border-radius:8px;
              padding:14px 16px;text-align:center;height:100%;}
    .kpi-value{font-family:monospace;font-size:1.65rem;font-weight:700;
               letter-spacing:-0.02em;}
    .kpi-label{font-size:0.65rem;color:#6b6b8a;text-transform:uppercase;
               letter-spacing:0.12em;margin-top:5px;}
    .kpi-sub{font-family:monospace;font-size:0.72rem;margin-top:3px;color:#6b6b8a;}
    .regime-bar{background:#0a0a16;border:1px solid #1e1e3a;border-radius:8px;
                padding:12px 20px;margin-bottom:16px;display:flex;
                align-items:center;gap:20px;font-family:monospace;}
    .regime-label{font-size:1rem;font-weight:700;letter-spacing:0.05em;}
    .regime-meta{font-size:0.72rem;color:#6b6b8a;}
    .sec{font-family:monospace;font-size:0.65rem;color:#6b6b8a;
         text-transform:uppercase;letter-spacing:0.15em;
         margin:20px 0 8px 0;border-bottom:1px solid #1e1e3a;padding-bottom:5px;}
    .insight{background:#0a0a18;border-left:3px solid #00d4ff;
             border-radius:0 6px 6px 0;padding:9px 14px;
             font-family:monospace;font-size:0.76rem;
             color:#9999bb;margin:6px 0 14px 0;line-height:1.5;}
    .corridor-label{font-family:monospace;font-size:0.7rem;color:#6b6b8a;
                    text-align:right;margin-top:-8px;margin-bottom:8px;}
    </style>""", unsafe_allow_html=True)

    # ── Range selector ─────────────────────────────────────────────────────────
    col_r, _ = st.columns([4, 8])
    with col_r:
        rng = st.radio("", ["2Y","5Y","10Y","All"], index=0,
                       horizontal=True, label_visibility="collapsed",
                       key="rates_range")
    cuts = {"2Y":-504, "5Y":-1260, "10Y":-2520, "All":0}
    cut  = cuts[rng]

    # ── Load data ──────────────────────────────────────────────────────────────
    with st.spinner("Loading rates data..."):
        try:
            D   = load_fred_data()
            tcv = load_treasury_curve()   # today's official curve
            yfd = load_yf_data() if YF_AVAILABLE else {}
        except Exception as e:
            st.error(f"Data error: {e}")
            return

    # ── Key values ─────────────────────────────────────────────────────────────
    l_ff    = _last(D["fedfunds"])
    l_10    = _last(D["dgs10"])
    l_2     = _last(D["dgs2"])
    l_30    = _last(D["dgs30"])
    l_3m    = _last(D["dgs3m"])
    l_spr   = _last(D["t10y2y"])
    l_t10t3m= _last(D["t10y3m"])
    l_real  = _last(D["tips10"])
    l_bei10 = _last(D["bei10"])
    l_sofr  = _last(D["sofr"])
    l_iorb  = _last(D["iorb"])
    l_onrrp = _last(D["onrrp"])
    l_nfci  = _last(D["nfci"])
    l_vix   = _last(D["vix"])
    l_mort  = _last(D["mortgage30"])
    l_dxy   = _last(D["dollar"])
    l_ted   = _last(D["ted"])

    # OAS: FRED BAML series are in %, convert to bp
    l_hy_bp  = _last(D["hy_oas"])  * 100
    l_ig_bp  = _last(D["ig_oas"])  * 100
    l_bbb_bp = _last(D["bbb_oas"]) * 100

    # Regime
    regime_label, regime_color = _regime_label(l_real, l_spr, l_nfci, l_hy_bp)
    latest_date = D["dgs10"].dropna().index[-1].strftime("%b %d, %Y") \
                  if len(D["dgs10"].dropna()) else "—"

    # ── REGIME BAR ─────────────────────────────────────────────────────────────
    r_star = 0.5
    stance = "RESTRICTIVA" if l_real > r_star else "ACOMODATICIA"
    stance_c = RED if l_real > r_star else GREEN
    inv_status = "INVERTIDA" if l_spr < 0 else ("PLANA" if l_spr < 0.3 else "NORMAL")
    inv_c = RED if l_spr < 0 else (AMBER if l_spr < 0.3 else GREEN)

    st.markdown(f"""
    <div class="regime-bar">
      <div>
        <div class="regime-label" style="color:{regime_color}">{regime_label}</div>
        <div class="regime-meta">ciclo macro actual</div>
      </div>
      <div style="width:1px;background:#1e1e3a;height:36px;"></div>
      <div>
        <span style="font-family:monospace;font-size:0.8rem;color:{stance_c};font-weight:600">
          Política {stance}</span>
        <span class="regime-meta"> · Real 10Y: {l_real:.2f}% vs r* {r_star:.1f}%</span>
      </div>
      <div style="width:1px;background:#1e1e3a;height:36px;"></div>
      <div>
        <span style="font-family:monospace;font-size:0.8rem;color:{inv_c};font-weight:600">
          Curva {inv_status}</span>
        <span class="regime-meta"> · 2s10s: {l_spr:+.2f}%</span>
      </div>
      <div style="width:1px;background:#1e1e3a;height:36px;"></div>
      <div class="regime-meta">{latest_date} · FRED · Treasury</div>
    </div>
    """, unsafe_allow_html=True)

    # ── KPI ROW ────────────────────────────────────────────────────────────────
    def _kpi(val, label, sub, color):
        return (f'<div class="kpi-card">'
                f'<div class="kpi-value" style="color:{color}">{val}</div>'
                f'<div class="kpi-label">{label}</div>'
                f'<div class="kpi-sub">{sub}</div>'
                f'</div>')

    def _spr_color(v):
        return GREEN if v > 0.3 else (AMBER if v > 0 else RED)

    c1,c2,c3,c4,c5,c6,c7 = st.columns(7)
    kpis = [
        (f"{l_ff:.2f}%",    "Fed Funds",   f"IORB {l_iorb:.2f}%",        AMBER),
        (f"{l_sofr:.2f}%",  "SOFR",        f"ON RRP {l_onrrp:.2f}%",     ORANGE),
        (f"{l_2:.2f}%",     "2Y",          f"3M: {l_3m:.2f}%",           BLUE),
        (f"{l_10:.2f}%",    "10Y",         f"30Y: {l_30:.2f}%",          CYAN),
        (f"{l_spr:+.2f}%",  "2s10s",       f"10Y-3M: {l_t10t3m:+.2f}%", _spr_color(l_spr)),
        (f"{l_real:.2f}%",  "10Y Real",    f"BEI 10Y: {l_bei10:.2f}%",  TEAL),
        (f"{l_hy_bp:.0f}bp","HY OAS",      f"IG: {l_ig_bp:.0f}bp",       GREEN if l_hy_bp < 350 else (AMBER if l_hy_bp < 600 else RED)),
    ]
    for col, (val, label, sub, color) in zip([c1,c2,c3,c4,c5,c6,c7], kpis):
        with col:
            st.markdown(_kpi(val, label, sub, color), unsafe_allow_html=True)

    # ── SECTION 1: CORREDOR DE TASAS ──────────────────────────────────────────
    st.markdown('<div class="sec">1 · Corredor de Tasas — Fed Funds · SOFR · IORB · ON RRP</div>',
                unsafe_allow_html=True)

    ff_t    = _trim(D["fedfunds"], cut)
    sofr_t  = _trim(D["sofr"],    cut)
    iorb_t  = _trim(D["iorb"],    cut)
    onrrp_t = _trim(D["onrrp"],   cut)
    onvol_t = _trim(D["onrrp_vol"], cut)

    fig_corr = make_subplots(specs=[[{"secondary_y": True}]])

    # Fed target range as band
    lb = _trim(D["fed_lb"], cut).dropna()
    ub = _trim(D["fed_ub"], cut).dropna()
    common_fed = lb.index.intersection(ub.index)
    if len(common_fed):
        fig_corr.add_trace(go.Scatter(
            name="Target Range",
            x=list(common_fed) + list(common_fed[::-1]),
            y=list(ub.reindex(common_fed).values) + list(lb.reindex(common_fed).values[::-1]),
            fill="toself", fillcolor="rgba(245,158,11,0.10)",
            line=dict(color="rgba(0,0,0,0)"),
            showlegend=True, hoverinfo="skip",
        ), secondary_y=False)

    for name, s, color, width, dash in [
        ("IORB (ceiling)",    iorb_t,  PINK,   1.5, "dot"),
        ("Fed Funds",         ff_t,    AMBER,  2.5, "solid"),
        ("SOFR",              sofr_t,  CYAN,   2.0, "solid"),
        ("ON RRP (floor)",    onrrp_t, VIOLET, 1.5, "dash"),
    ]:
        if len(s.dropna()):
            fig_corr.add_trace(go.Scatter(
                name=name, x=s.index, y=s.values,
                line=dict(color=color, width=width, dash=dash),
                hovertemplate=f"<b>{name}</b>: %{{y:.2f}}%<extra></extra>",
            ), secondary_y=False)

    # ON RRP volume as bars (billions)
    if len(onvol_t.dropna()):
        fig_corr.add_trace(go.Bar(
            name="ON RRP Volume ($B)",
            x=onvol_t.index,
            y=onvol_t.values / 1000,   # millions → billions
            marker_color=VIOLET, opacity=0.25,
            hovertemplate="<b>RRP Vol</b>: $%{y:,.0f}B<extra></extra>",
        ), secondary_y=True)

    fig_corr.update_layout(**_L(320), barmode="overlay")
    fig_corr.update_yaxes(title_text="Rate %", gridcolor=GRID, zeroline=False,
                          secondary_y=False, title_font=dict(color=AMBER, size=10),
                          ticksuffix="%")
    fig_corr.update_yaxes(title_text="RRP Vol $B", gridcolor="rgba(0,0,0,0)",
                          zeroline=False, secondary_y=True,
                          title_font=dict(color=VIOLET, size=10))
    fig_corr.update_xaxes(gridcolor=GRID, linecolor=GRID)
    st.plotly_chart(fig_corr, use_container_width=True)

    rrp_vol_last = _last(D["onrrp_vol"]) / 1000
    st.markdown(
        f'<div class="insight">🔧 Corredor actual: IORB <b style="color:{PINK}">{l_iorb:.2f}%</b> (techo) · '
        f'Fed Funds <b style="color:{AMBER}">{l_ff:.2f}%</b> · '
        f'SOFR <b style="color:{CYAN}">{l_sofr:.2f}%</b> · '
        f'ON RRP <b style="color:{VIOLET}">{l_onrrp:.2f}%</b> (piso). '
        f'Volumen ON RRP: <b style="color:{VIOLET}">${rrp_vol_last:,.0f}B</b> — '
        f'drenaje del RRP indica migración de liquidez a T-Bills, señal de normalización del plumbing.</div>',
        unsafe_allow_html=True)

    # ── SECTION 2: YIELD CURVE ────────────────────────────────────────────────
    st.markdown('<div class="sec">2 · Yield Curve</div>', unsafe_allow_html=True)

    tab_snap, tab_hist, tab_recent = st.tabs([
        "📐 Snapshot — Forma actual",
        "📊 Historia — Spreads & Ciclo",
        "📈 Dinámica reciente 12M",
    ])

    # ── Tab A: Snapshot ────────────────────────────────────────────────────────
    with tab_snap:
        # Build curves: today (Treasury official), 1Y ago, 2Y ago from FRED
        def _curve_from_fred(days_ago=0):
            pts = {}
            for label, key in zip(TENORS, TENOR_KEYS):
                s = D[key].dropna()
                if len(s) == 0:
                    continue
                idx = -1 - days_ago if days_ago > 0 else -1
                if abs(idx) <= len(s):
                    pts[label] = float(s.iloc[idx])
            return pts

        today_fred = _curve_from_fred(0)
        y1ago      = _curve_from_fred(252)
        y2ago      = _curve_from_fred(504)

        # Use Treasury official for today if available, else FRED
        today_curve = dict(tcv) if len(tcv) else today_fred
        # Merge — Treasury may have 3Y etc that FRED doesn't have above
        all_tenors_today = {**today_fred, **today_curve}

        # Order tenors
        tenor_order = ["1M","3M","6M","1Y","2Y","3Y","5Y","7Y","10Y","20Y","30Y"]
        def _ordered(d):
            return [(t, d[t]) for t in tenor_order if t in d]

        fig_snap = go.Figure()

        # Plot curves back → front for visibility
        for label, pts, color, dash, width in [
            ("2Y ago", y2ago,       MUTED2, "dot",   1.5),
            ("1Y ago", y1ago,       BLUE2,  "dash",  2.0),
            ("Today",  all_tenors_today, CYAN, "solid", 3.0),
        ]:
            ordered = _ordered(pts)
            if not ordered: continue
            xs, ys = zip(*ordered)
            fig_snap.add_trace(go.Scatter(
                name=label, x=xs, y=ys,
                mode="lines+markers",
                line=dict(color=color, width=width, dash=dash),
                marker=dict(size=6, color=color),
                hovertemplate=f"<b>{label}</b> %{{x}}: %{{y:.2f}}%<extra></extra>",
            ))

        fig_snap.add_hline(y=0, line_color=MUTED2, line_width=1, line_dash="dot")
        l_snap = _L(340)
        l_snap["yaxis"]["ticksuffix"] = "%"
        l_snap["xaxis"]["title"]      = dict(text="Tenor", font=dict(color=MUTED, size=10))
        l_snap["yaxis"]["title"]      = dict(text="Yield %", font=dict(color=MUTED, size=10))
        fig_snap.update_layout(**l_snap)
        st.plotly_chart(fig_snap, use_container_width=True)

        # Inversion table
        if all_tenors_today:
            o = _ordered(all_tenors_today)
            spreads_snap = {
                "2s10s":  today_curve.get("10Y", float("nan")) - today_curve.get("2Y", float("nan")),
                "3m10Y":  today_curve.get("10Y", float("nan")) - today_curve.get("3M", float("nan")),
                "2s30s":  today_curve.get("30Y", float("nan")) - today_curve.get("2Y", float("nan")),
                "5s30s":  today_curve.get("30Y", float("nan")) - today_curve.get("5Y", float("nan")),
            }
            cs1,cs2,cs3,cs4 = st.columns(4)
            for col, (sname, sval) in zip([cs1,cs2,cs3,cs4], spreads_snap.items()):
                sc = _spr_color(sval) if not pd.isna(sval) else MUTED
                sv = f"{sval:+.2f}%" if not pd.isna(sval) else "n/a"
                with col:
                    st.markdown(_kpi(sv, sname, "spread", sc), unsafe_allow_html=True)

    # ── Tab B: Historia ────────────────────────────────────────────────────────
    with tab_hist:
        r2_h  = _trim(D["dgs2"],   cut)
        r10_h = _trim(D["dgs10"],  cut)
        r30_h = _trim(D["dgs30"],  cut)
        spr_h = _trim(D["t10y2y"], cut)
        s3m_h = _trim(D["t10y3m"], cut)

        fig_hist = make_subplots(specs=[[{"secondary_y": True}]])

        for name, s, color, dash in [
            ("30Y", r30_h, VIOLET, "dot"),
            ("10Y", r10_h, CYAN,   "solid"),
            ("2Y",  r2_h,  BLUE,   "dash"),
        ]:
            fig_hist.add_trace(go.Scatter(
                name=name, x=s.index, y=s.values,
                line=dict(color=color, width=2, dash=dash),
                hovertemplate=f"<b>{name}</b>: %{{y:.2f}}%<extra></extra>",
            ), secondary_y=False)

        # 2s10s as filled area
        fig_hist.add_trace(go.Scatter(
            name="2s10s", x=spr_h.index, y=spr_h.values,
            fill="tozeroy", line=dict(color=AMBER, width=1.5),
            fillcolor="rgba(245,158,11,0.12)",
            hovertemplate="<b>2s10s</b>: %{y:+.2f}%<extra></extra>",
        ), secondary_y=True)
        # 10Y-3M as line
        fig_hist.add_trace(go.Scatter(
            name="10Y-3M", x=s3m_h.index, y=s3m_h.values,
            line=dict(color=RED, width=1, dash="dot"),
            hovertemplate="<b>10Y-3M</b>: %{y:+.2f}%<extra></extra>",
        ), secondary_y=True)

        fig_hist.add_hline(y=0, line_color=RED, line_width=1,
                           line_dash="dot", secondary_y=True)

        fig_hist.update_layout(**_L(360))
        fig_hist.update_yaxes(title_text="Yield %", gridcolor=GRID,
                              zeroline=False, secondary_y=False,
                              title_font=dict(color=CYAN, size=10), ticksuffix="%")
        fig_hist.update_yaxes(title_text="Spread %", gridcolor="rgba(0,0,0,0)",
                              zeroline=False, secondary_y=True,
                              title_font=dict(color=AMBER, size=10))
        fig_hist.update_xaxes(gridcolor=GRID, linecolor=GRID)
        st.plotly_chart(fig_hist, use_container_width=True)

        st.markdown(
            f'<div class="insight">📐 Curva <b style="color:{_spr_color(l_spr)}">'
            f'{inv_status}</b> — 2s10s: <b style="color:{AMBER}">{l_spr:+.2f}%</b> · '
            f'10Y-3M: <b style="color:{RED}">{l_t10t3m:+.2f}%</b>. '
            f'El spread 10Y-3M tiene el mejor track record como predictor de recesión (NY Fed model). '
            f'La inversión promedio históricamente precede recesión por 12-18 meses.</div>',
            unsafe_allow_html=True)

    # ── Tab C: Dinámica reciente ────────────────────────────────────────────────
    with tab_recent:
        # Last 12M daily
        r_12m = {k: D[k].iloc[-252:] for k in ["dgs2","dgs5","dgs10","dgs30"] if len(D[k])}

        fig_rec = go.Figure()
        for name, key, color in [
            ("2Y",  "dgs2",  BLUE),
            ("5Y",  "dgs5",  TEAL),
            ("10Y", "dgs10", CYAN),
            ("30Y", "dgs30", VIOLET),
        ]:
            if key in r_12m and len(r_12m[key]):
                s = r_12m[key]
                fig_rec.add_trace(go.Scatter(
                    name=name, x=s.index, y=s.values,
                    line=dict(color=color, width=2),
                    hovertemplate=f"<b>{name}</b>: %{{y:.2f}}%<extra></extra>",
                ))

        l_rec = _L(320)
        l_rec["yaxis"]["ticksuffix"] = "%"
        l_rec["xaxis"]["showgrid"]   = False
        fig_rec.update_layout(**l_rec)
        st.plotly_chart(fig_rec, use_container_width=True)

        # Bear steepener / Bull flattener diagnosis
        if len(D["dgs2"]) > 20 and len(D["dgs10"]) > 20:
            d2_1m  = D["dgs2"].dropna().iloc[-1]  - D["dgs2"].dropna().iloc[-22]
            d10_1m = D["dgs10"].dropna().iloc[-1] - D["dgs10"].dropna().iloc[-22]
            if d10_1m > 0 and d2_1m > 0 and d10_1m > d2_1m:
                dynamic = "BEAR STEEPENER 📈 — Long end sube más que short end. Mercado descontando inflación persistente o fiscal risk."
                dc = AMBER
            elif d10_1m < 0 and d2_1m < 0 and d2_1m < d10_1m:
                dynamic = "BULL FLATTENER 📉 — Short end baja más que long end. Mercado descontando recortes de la Fed."
                dc = GREEN
            elif d10_1m > 0 and d2_1m < 0:
                dynamic = "BEAR STEEPENER CLÁSICO 🔺 — Long end sube, short end baja. Desinversión activa, ciclo girando."
                dc = ORANGE
            elif d10_1m < 0 and d2_1m > 0:
                dynamic = "BULL FLATTENER / INVERSIÓN 🔻 — Short end sube, long end baja. Mercado ve desaceleración."
                dc = RED
            else:
                dynamic = f"Movimiento paralelo — 2Y: {d2_1m:+.2f}% · 10Y: {d10_1m:+.2f}% en último mes."
                dc = MUTED
            st.markdown(f'<div class="insight">🎯 Dinámica último mes: '
                        f'<b style="color:{dc}">{dynamic}</b></div>',
                        unsafe_allow_html=True)

    # ── SECTION 3: FED & REAL RATE ────────────────────────────────────────────
    st.markdown('<div class="sec">3 · Política Monetaria — Fed Funds · Real Rate · Transmission</div>',
                unsafe_allow_html=True)

    tab_policy, tab_trans = st.tabs(["🎯 Stance de Política", "🏠 Transmission Mechanism"])

    with tab_policy:
        ff_p    = _trim(D["fedfunds"], cut)
        tips_p  = _trim(D["tips10"],   cut)
        r10_p   = _trim(D["dgs10"],    cut)
        bei_p   = _trim(D["bei10"],    cut)

        fig_pol = go.Figure()

        # Fed target range band
        lb_p = _trim(D["fed_lb"], cut).dropna()
        ub_p = _trim(D["fed_ub"], cut).dropna()
        ci   = lb_p.index.intersection(ub_p.index)
        if len(ci):
            fig_pol.add_trace(go.Scatter(
                name="Target Range",
                x=list(ci)+list(ci[::-1]),
                y=list(ub_p.reindex(ci).values)+list(lb_p.reindex(ci).values[::-1]),
                fill="toself", fillcolor="rgba(245,158,11,0.10)",
                line=dict(color="rgba(0,0,0,0)"),
                showlegend=True, hoverinfo="skip",
            ))

        # r* neutral line
        fig_pol.add_hline(y=0.5, line_color=GREEN, line_width=1, line_dash="dot",
                          annotation_text="r* ~0.5%",
                          annotation_position="right",
                          annotation_font=dict(color=GREEN, size=9))

        for name, s, color, dash, width in [
            ("Fed Funds",    ff_p,   AMBER, "solid", 2.5),
            ("10Y Nominal",  r10_p,  CYAN,  "dash",  1.5),
            ("10Y Real (TIPS)", tips_p, TEAL, "solid", 2.0),
        ]:
            if len(s.dropna()):
                fig_pol.add_trace(go.Scatter(
                    name=name, x=s.index, y=s.values,
                    line=dict(color=color, width=width, dash=dash),
                    hovertemplate=f"<b>{name}</b>: %{{y:.2f}}%<extra></extra>",
                ))

        # Fill real rate area vs r*
        if len(tips_p.dropna()):
            fig_pol.add_trace(go.Scatter(
                name="Real vs r*",
                x=tips_p.index, y=tips_p.values,
                fill="tozeroy",
                fillcolor="rgba(20,184,166,0.07)",
                line=dict(color="rgba(0,0,0,0)"),
                showlegend=False, hoverinfo="skip",
            ))

        l_pol = _L(360)
        l_pol["yaxis"]["ticksuffix"] = "%"
        fig_pol.update_layout(**l_pol)
        st.plotly_chart(fig_pol, use_container_width=True)

        # Breakeven sub-chart
        fig_bei = go.Figure()
        for name, s, color in [
            ("BEI 5Y",  _trim(D["bei5"],  cut), ORANGE),
            ("BEI 10Y", _trim(D["bei10"], cut), PINK),
        ]:
            if len(s.dropna()):
                fig_bei.add_trace(go.Scatter(
                    name=name, x=s.index, y=s.values,
                    line=dict(color=color, width=2),
                    hovertemplate=f"<b>{name}</b>: %{{y:.2f}}%<extra></extra>",
                ))
        fig_bei.add_hline(y=2.0, line_color=GREEN, line_width=1, line_dash="dot",
                          annotation_text="Fed 2% target",
                          annotation_font=dict(color=GREEN, size=9))
        l_bei = _L(200, "Inflation Breakevens — Expectativas implícitas de mercado")
        l_bei["yaxis"]["ticksuffix"] = "%"
        fig_bei.update_layout(**l_bei)
        st.plotly_chart(fig_bei, use_container_width=True)

        st.markdown(
            f'<div class="insight">🎯 Real rate 10Y: <b style="color:{TEAL}">{l_real:.2f}%</b> vs r* ~0.5%. '
            f'Política <b style="color:{stance_c}">{stance}</b> en términos reales. '
            f'BEI 10Y: <b style="color:{PINK}">{l_bei10:.2f}%</b> — mercado descuenta inflación '
            f'{"por encima" if l_bei10 > 2.5 else "cercana a"} del target Fed. '
            f'Fed Funds real implícito: ~{l_ff - l_bei10:.2f}%.</div>',
            unsafe_allow_html=True)

    with tab_trans:
        mort_t = _trim(D["mortgage30"], cut)
        dxy_t  = _trim(D["dollar"],     cut)
        ff_t2  = _trim(D["fedfunds"],   cut)

        fig_tr = make_subplots(specs=[[{"secondary_y": True}]])
        if len(mort_t.dropna()):
            fig_tr.add_trace(go.Scatter(
                name="Mortgage 30Y", x=mort_t.index, y=mort_t.values,
                line=dict(color=PINK, width=2.5),
                hovertemplate="<b>Mortgage 30Y</b>: %{y:.2f}%<extra></extra>",
            ), secondary_y=False)
        if len(ff_t2.dropna()):
            fig_tr.add_trace(go.Scatter(
                name="Fed Funds", x=ff_t2.index, y=ff_t2.values,
                line=dict(color=AMBER, width=2, dash="dot"),
                hovertemplate="<b>Fed Funds</b>: %{y:.2f}%<extra></extra>",
            ), secondary_y=False)
        if len(dxy_t.dropna()):
            fig_tr.add_trace(go.Scatter(
                name="USD Broad Index", x=dxy_t.index, y=dxy_t.values,
                line=dict(color=CYAN, width=2),
                hovertemplate="<b>USD Index</b>: %{y:.1f}<extra></extra>",
            ), secondary_y=True)

        fig_tr.update_layout(**_L(300))
        fig_tr.update_yaxes(title_text="Rate %", gridcolor=GRID, zeroline=False,
                            secondary_y=False, title_font=dict(color=PINK, size=10))
        fig_tr.update_yaxes(title_text="USD Index", gridcolor="rgba(0,0,0,0)",
                            zeroline=False, secondary_y=True,
                            title_font=dict(color=CYAN, size=10))
        fig_tr.update_xaxes(gridcolor=GRID, linecolor=GRID)
        st.plotly_chart(fig_tr, use_container_width=True)

        mort_spread = l_mort - l_ff if not pd.isna(l_mort) else float("nan")
        st.markdown(
            f'<div class="insight">🏠 Mortgage 30Y: <b style="color:{PINK}">{l_mort:.2f}%</b> · '
            f'Spread sobre Fed Funds: <b style="color:{AMBER}">{mort_spread:+.2f}%</b>. '
            f'USD Broad Index: <b style="color:{CYAN}">{l_dxy:.1f}</b>. '
            f'La mortgage rate es el canal de transmisión más directo de política monetaria '
            f'a la economía real — afecta housing, wealth effect y consumo.</div>',
            unsafe_allow_html=True)

    # ── SECTION 4: CREDIT & RISK APPETITE ─────────────────────────────────────
    st.markdown('<div class="sec">4 · Credit & Risk Appetite — OAS Spreads</div>',
                unsafe_allow_html=True)

    # OAS × 100 to convert from % to bp
    ig_bp  = D["ig_oas"]  * 100
    hy_bp  = D["hy_oas"]  * 100
    bbb_bp = D["bbb_oas"] * 100

    ig_t  = _trim(ig_bp,  cut)
    hy_t  = _trim(hy_bp,  cut)
    bbb_t = _trim(bbb_bp, cut)

    # Percentiles vs full history
    ig_pct  = _pctile(ig_bp,  l_ig_bp)
    hy_pct  = _pctile(hy_bp,  l_hy_bp)
    bbb_pct = _pctile(bbb_bp, l_bbb_bp)

    def _oas_color(pct):
        return GREEN if pct < 30 else (AMBER if pct < 60 else RED)

    # Mini KPIs
    ca1,ca2,ca3,ca4 = st.columns(4)
    oas_kpis = [
        (f"{l_ig_bp:.0f}bp",  "IG OAS",      f"pctile {ig_pct:.0f}%",        _oas_color(ig_pct)),
        (f"{l_bbb_bp:.0f}bp", "BBB OAS",     f"pctile {bbb_pct:.0f}%",       _oas_color(bbb_pct)),
        (f"{l_hy_bp:.0f}bp",  "HY OAS",      f"pctile {hy_pct:.0f}%",        _oas_color(hy_pct)),
        (f"{l_hy_bp-l_ig_bp:.0f}bp", "HY-IG differential", "fallen angel proxy", AMBER),
    ]
    for col, (val, label, sub, color) in zip([ca1,ca2,ca3,ca4], oas_kpis):
        with col:
            st.markdown(_kpi(val, label, sub, color), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)

    fig_cr = go.Figure()

    # Dynamic y range
    all_oas = pd.concat([ig_t, bbb_t, hy_t]).dropna()
    y_max = min(float(all_oas.max()) * 1.15, 2500) if len(all_oas) else 500
    y_min = max(float(all_oas.min()) * 0.85, 0)

    # Stress zones — dynamic
    fig_cr.add_hrect(y0=600, y1=y_max, fillcolor=RED, opacity=0.04,
                     line_width=0, annotation_text="HY Stress Zone",
                     annotation_position="top right",
                     annotation_font=dict(color=RED, size=9))

    for name, s, color, dash in [
        ("IG OAS",  ig_t,  GREEN, "dot"),
        ("BBB OAS", bbb_t, AMBER, "dash"),
        ("HY OAS",  hy_t,  RED,   "solid"),
    ]:
        if len(s.dropna()):
            fig_cr.add_trace(go.Scatter(
                name=name, x=s.index, y=s.values,
                line=dict(color=color, width=2, dash=dash),
                hovertemplate=f"<b>{name}</b>: %{{y:.0f}}bp<extra></extra>",
            ))

    l_cr = _L(340)
    l_cr["yaxis"]["title"]   = dict(text="OAS (bp)", font=dict(color=MUTED, size=10))
    l_cr["yaxis"]["range"]   = [y_min, y_max]
    fig_cr.update_layout(**l_cr)
    st.plotly_chart(fig_cr, use_container_width=True)

    # HYG/LQD ratio if yfinance available
    if "HYG" in yfd and "LQD" in yfd and len(yfd["HYG"]) and len(yfd["LQD"]):
        common_etf = yfd["HYG"].index.intersection(yfd["LQD"].index)
        ratio = (yfd["HYG"].reindex(common_etf) / yfd["LQD"].reindex(common_etf))
        ratio_t = _trim(ratio, cut)
        ratio_ma = ratio_t.rolling(20).mean()

        fig_ratio = go.Figure()
        fig_ratio.add_trace(go.Scatter(
            name="HYG/LQD ratio", x=ratio_t.index, y=ratio_t.values,
            line=dict(color=ORANGE, width=1.5),
            hovertemplate="<b>HYG/LQD</b>: %{y:.3f}<extra></extra>",
        ))
        fig_ratio.add_trace(go.Scatter(
            name="20D MA", x=ratio_ma.index, y=ratio_ma.values,
            line=dict(color=WHITE, width=2),
            hovertemplate="<b>20D MA</b>: %{y:.3f}<extra></extra>",
        ))
        l_r = _L(180, "HYG/LQD — Risk Appetite Proxy (alto = risk-on / bajo = risk-off)")
        fig_ratio.update_layout(**l_r)
        st.plotly_chart(fig_ratio, use_container_width=True)

    hy_regime = ("TIGHT — risk-on" if l_hy_bp < 350
                 else ("ELEVATED — caution" if l_hy_bp < 600 else "WIDE — stress/risk-off"))
    hy_rc = GREEN if l_hy_bp < 350 else (AMBER if l_hy_bp < 600 else RED)
    st.markdown(
        f'<div class="insight">📊 HY OAS: <b style="color:{RED}">{l_hy_bp:.0f}bp</b> — '
        f'<b style="color:{hy_rc}">{hy_regime}</b> (pctile {hy_pct:.0f}% histórico). '
        f'IG OAS: <b style="color:{GREEN}">{l_ig_bp:.0f}bp</b> (pctile {ig_pct:.0f}%). '
        f'BBB-IG: <b style="color:{AMBER}">{l_bbb_bp-l_ig_bp:.0f}bp</b> — diferencial fallen angel.</div>',
        unsafe_allow_html=True)

    # ── SECTION 5: FINANCIAL CONDITIONS ───────────────────────────────────────
    st.markdown('<div class="sec">5 · Condiciones Financieras — NFCI · VIX · TED Spread</div>',
                unsafe_allow_html=True)

    nfci_t = _trim(D["nfci"], cut)
    vix_t  = _trim(D["vix"],  cut)
    ted_t  = _trim(D["ted"],  cut)

    # NFCI — dynamic Y range
    nfci_all = D["nfci"].dropna()
    nfci_min = float(nfci_all.min()) - 0.2 if len(nfci_all) else -3
    nfci_max = float(nfci_all.max()) + 0.2 if len(nfci_all) else 3
    nfci_ma52 = nfci_t.rolling(52).mean()

    fig_nf = go.Figure()
    fig_nf.add_hrect(y0=0.3, y1=nfci_max, fillcolor=RED, opacity=0.04, line_width=0,
                     annotation_text="Tight", annotation_position="top right",
                     annotation_font=dict(color=RED, size=9))
    fig_nf.add_hrect(y0=nfci_min, y1=-0.3, fillcolor=GREEN, opacity=0.04, line_width=0,
                     annotation_text="Loose", annotation_position="bottom right",
                     annotation_font=dict(color=GREEN, size=9))

    nfci_pos = nfci_t.clip(lower=0)
    nfci_neg = nfci_t.clip(upper=0)
    fig_nf.add_trace(go.Bar(name="Tight (>0)", x=nfci_pos.index, y=nfci_pos.values,
                            marker_color=RED, opacity=0.65,
                            hovertemplate="<b>NFCI</b>: %{y:+.3f}<extra></extra>"))
    fig_nf.add_trace(go.Bar(name="Loose (<0)", x=nfci_neg.index, y=nfci_neg.values,
                            marker_color=GREEN, opacity=0.65,
                            hovertemplate="<b>NFCI</b>: %{y:+.3f}<extra></extra>"))
    fig_nf.add_trace(go.Scatter(name="52W MA", x=nfci_ma52.index, y=nfci_ma52.values,
                                line=dict(color=WHITE, width=2),
                                hovertemplate="<b>52W MA</b>: %{y:+.3f}<extra></extra>"))
    fig_nf.add_hline(y=0, line_color=MUTED, line_width=1)

    l_nf = _L(280)
    l_nf["barmode"] = "overlay"
    l_nf["yaxis"]["range"] = [nfci_min, nfci_max]
    fig_nf.update_layout(**l_nf)
    st.plotly_chart(fig_nf, use_container_width=True)

    # VIX + TED in two columns
    col_vix, col_ted = st.columns(2)
    with col_vix:
        if len(vix_t.dropna()):
            vix_colors = [RED if v > 30 else (AMBER if v > 20 else GREEN) for v in vix_t.values]
            fig_vix = go.Figure()
            fig_vix.add_trace(go.Scatter(
                name="VIX", x=vix_t.index, y=vix_t.values,
                line=dict(color=ORANGE, width=2),
                fill="tozeroy", fillcolor="rgba(249,115,22,0.08)",
                hovertemplate="<b>VIX</b>: %{y:.1f}<extra></extra>",
            ))
            fig_vix.add_hrect(y0=30, y1=90, fillcolor=RED, opacity=0.05, line_width=0,
                              annotation_text="Stress >30", annotation_font=dict(color=RED, size=9))
            fig_vix.add_hrect(y0=20, y1=30, fillcolor=AMBER, opacity=0.05, line_width=0)
            l_vix = _L(220, "VIX — Volatilidad implícita equity")
            fig_vix.update_layout(**l_vix)
            st.plotly_chart(fig_vix, use_container_width=True)

    with col_ted:
        if len(ted_t.dropna()):
            fig_ted = go.Figure()
            fig_ted.add_trace(go.Scatter(
                name="TED Spread", x=ted_t.index, y=ted_t.values,
                line=dict(color=VIOLET, width=2),
                fill="tozeroy", fillcolor="rgba(167,139,250,0.08)",
                hovertemplate="<b>TED</b>: %{y:.2f}%<extra></extra>",
            ))
            fig_ted.add_hline(y=0.5, line_color=AMBER, line_width=1, line_dash="dot",
                              annotation_text="Stress threshold",
                              annotation_font=dict(color=AMBER, size=9))
            l_ted_lay = _L(220, "TED Spread — Stress interbancario")
            l_ted_lay["yaxis"]["ticksuffix"] = "%"
            fig_ted.update_layout(**l_ted_lay)
            st.plotly_chart(fig_ted, use_container_width=True)

    nfci_interp = "RESTRICTIVAS" if l_nfci > 0.3 else ("NEUTRALES" if l_nfci > -0.3 else "LAXAS")
    nfci_c = RED if l_nfci > 0.3 else (AMBER if l_nfci > -0.3 else GREEN)
    st.markdown(
        f'<div class="insight">🌡️ NFCI: <b style="color:{nfci_c}">{l_nfci:+.3f}</b> — '
        f'condiciones <b style="color:{nfci_c}">{nfci_interp}</b>. '
        f'VIX: <b style="color:{ORANGE}">{l_vix:.1f}</b> '
        f'{"— stress elevado" if l_vix > 30 else ("— cautela" if l_vix > 20 else "— risk-on")}. '
        f'TED Spread: <b style="color:{VIOLET}">{l_ted:.2f}%</b> — '
        f'{"stress interbancario" if l_ted > 0.5 else "condiciones interbancarias normales"}.</div>',
        unsafe_allow_html=True)

    # ── SECTION 6: RATE SNAPSHOT TABLE ────────────────────────────────────────
    st.markdown('<div class="sec">6 · Rate Snapshot — Niveles & Deltas</div>',
                unsafe_allow_html=True)

    snap_map = {
        "Fed Funds":      ("fedfunds", "rate"),
        "SOFR":           ("sofr",     "rate"),
        "IORB":           ("iorb",     "rate"),
        "ON RRP":         ("onrrp",    "rate"),
        "3M T-Bill":      ("dgs3m",    "rate"),
        "2Y Treasury":    ("dgs2",     "rate"),
        "5Y Treasury":    ("dgs5",     "rate"),
        "10Y Treasury":   ("dgs10",    "rate"),
        "30Y Treasury":   ("dgs30",    "rate"),
        "2s10s Spread":   ("t10y2y",   "spread"),
        "10Y-3M Spread":  ("t10y3m",   "spread"),
        "10Y Real (TIPS)":("tips10",   "rate"),
        "BEI 10Y":        ("bei10",    "rate"),
        "IG OAS (bp)":    ("ig_oas",   "oas"),
        "HY OAS (bp)":    ("hy_oas",   "oas"),
        "VIX":            ("vix",      "vix"),
        "NFCI":           ("nfci",     "nfci"),
        "Mortgage 30Y":   ("mortgage30","rate"),
        "USD Index":      ("dollar",   "idx"),
        "TED Spread":     ("ted",      "rate"),
    }

    rows = {}
    for label, (key, kind) in snap_map.items():
        s = D[key].dropna()
        cur = float(s.iloc[-1]) if len(s) else float("nan")
        # OAS: stored in % → convert to bp for display
        if kind == "oas": cur_disp = cur * 100
        else:             cur_disp = cur

        deltas = {}
        for dname, ddays in [("1W Δ",5),("1M Δ",22),("3M Δ",63),("1Y Δ",252)]:
            if len(s) > ddays:
                raw_d = float(s.iloc[-1] - s.iloc[-ddays])
                deltas[dname] = raw_d * 100 if kind == "oas" else raw_d
            else:
                deltas[dname] = float("nan")
        rows[label] = {"Current": cur_disp, **deltas}

    snap_df = pd.DataFrame(rows).T

    def _cc_cur(val):
        base = "text-align:center;font-family:monospace;font-size:0.79rem;padding:5px 8px;"
        return f"background:#13132b;color:{TEXT};{base}"

    def _cc_delta(val):
        base = "text-align:center;font-family:monospace;font-size:0.79rem;padding:5px 8px;"
        if pd.isna(val): return f"background:#0d0d1a;color:{MUTED2};{base}"
        if val > 0.5:    return f"background:#3d1010;color:#f87171;{base}"
        elif val > 0.05: return f"background:#2d1515;color:#fca5a5;{base}"
        elif val < -0.5: return f"background:#0d4f2b;color:#4ade80;{base}"
        elif val < -0.05:return f"background:#0a3320;color:#34d399;{base}"
        else:            return f"background:#13132b;color:{MUTED};{base}"

    def _fmt(label, val):
        if pd.isna(val): return "—"
        if "bp" in label or "OAS" in label: return f"{val:.0f}"
        if label == "NFCI":   return f"{val:+.3f}"
        if label == "VIX":    return f"{val:.1f}"
        if label == "USD Index": return f"{val:.1f}"
        return f"{val:.2f}%"

    def _fmt_d(label, val):
        if pd.isna(val): return "—"
        if "bp" in label or "OAS" in label: return f"{val:+.0f}"
        if label == "NFCI":   return f"{val:+.3f}"
        if label == "VIX":    return f"{val:+.1f}"
        if label == "USD Index": return f"{val:+.1f}"
        return f"{val:+.2f}%"

    styled = snap_df.style\
        .applymap(_cc_cur, subset=["Current"])\
        .applymap(_cc_delta, subset=["1W Δ","1M Δ","3M Δ","1Y Δ"])\
        .format({
            "Current": lambda v: "—" if pd.isna(v) else f"{v:.2f}",
            "1W Δ":  lambda v: "—" if pd.isna(v) else f"{v:+.2f}",
            "1M Δ":  lambda v: "—" if pd.isna(v) else f"{v:+.2f}",
            "3M Δ":  lambda v: "—" if pd.isna(v) else f"{v:+.2f}",
            "1Y Δ":  lambda v: "—" if pd.isna(v) else f"{v:+.2f}",
        })
    st.dataframe(styled, use_container_width=True)

    st.markdown(
        f'<div style="color:{MUTED};font-size:0.68rem;margin-top:10px;font-family:monospace">'
        f'Sources: FRED (Treasuries · SOFR corridor · BAML OAS · NFCI · VIX · TED · Mortgage · USD) · '
        f'US Treasury (yield curve oficial) · yfinance (ETF ratios) · '
        f'OAS en basis points (BAML series × 100) · Delta color: rojo = sube / verde = baja</div>',
        unsafe_allow_html=True)
