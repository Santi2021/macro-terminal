"""
modules/rates.py — Interest Rates & Financial Conditions for Macro Terminal
Sources: FRED API
  - Yield curve: DGS2, DGS5, DGS10, DGS30
  - Spreads: T10Y2Y (2s10s), T10Y3M
  - Fed Funds: FEDFUNDS, DFEDTARL, DFEDTARU (target range)
  - Credit: BAMLC0A0CM (IG OAS), BAMLH0A0HYM2 (HY OAS), BAMLC0A4CBBB (BBB)
  - Financial Conditions: NFCI (Chicago Fed)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import os

# ── Style ──────────────────────────────────────────────────────────────────────
BG    = "#0d0d1a"
BG2   = "#13132b"
GRID  = "#1e1e3a"
TEXT  = "#e8e8f0"
MUTED = "#6b6b8a"
CYAN  = "#00d4ff"
GREEN = "#10b981"
RED   = "#ef4444"
AMBER = "#f59e0b"
BLUE  = "#3b82f6"
VIOLET= "#a78bfa"
TEAL  = "#14b8a6"
PINK  = "#f472b6"
ORANGE= "#f97316"

# ── FRED Series ────────────────────────────────────────────────────────────────
FRED_SERIES = {
    # Treasuries
    "dgs1m":  "DGS1MO",
    "dgs3m":  "DGS3MO",
    "dgs6m":  "DGS6MO",
    "dgs1":   "DGS1",
    "dgs2":   "DGS2",
    "dgs5":   "DGS5",
    "dgs10":  "DGS10",
    "dgs30":  "DGS30",
    # Spreads
    "t10y2y": "T10Y2Y",   # 2s10s spread
    "t10y3m": "T10Y3M",   # 10Y-3M spread
    # Fed Funds
    "fedfunds":  "FEDFUNDS",
    "fed_lb":    "DFEDTARL",   # Lower bound target
    "fed_ub":    "DFEDTARU",   # Upper bound target
    # Credit spreads (OAS, bp)
    "ig_oas":  "BAMLC0A0CM",     # Investment Grade
    "hy_oas":  "BAMLH0A0HYM2",   # High Yield
    "bbb_oas": "BAMLC0A4CBBB",   # BBB specifically
    # Financial Conditions
    "nfci":    "NFCI",           # Chicago Fed NFCI (weekly)
    # TIPS / Real
    "tips10":  "DFII10",         # 10Y Real yield
    "tips5":   "DFII5",          # 5Y Real yield
}


def _fred_key():
    try:    return st.secrets["FRED_API_KEY"]
    except: return os.getenv("FRED_API_KEY", "")


def _fetch_fred(sid: str, start: str = "2000-01-01") -> pd.Series:
    """Fetch a single FRED series → pd.Series indexed by date."""
    api_key = _fred_key()
    params = {
        "series_id": sid,
        "observation_start": start,
        "api_key": api_key,
        "file_type": "json",
    }
    resp = requests.get(
        "https://api.stlouisfed.org/fred/series/observations",
        params=params, timeout=20
    )
    resp.raise_for_status()
    obs = resp.json()["observations"]
    rows = []
    for o in obs:
        try:
            rows.append({"date": pd.Timestamp(o["date"]), "value": float(o["value"])})
        except Exception:
            continue
    df = pd.DataFrame(rows).dropna()
    if df.empty:
        return pd.Series(dtype=float)
    return df.set_index("date")["value"].sort_index()


@st.cache_data(ttl=3600, show_spinner=False)
def load_all_rates(start: str = "2000-01-01") -> dict:
    """Load all rate series into a dict of pd.Series."""
    data = {}
    for name, sid in FRED_SERIES.items():
        try:
            data[name] = _fetch_fred(sid, start)
        except Exception:
            data[name] = pd.Series(dtype=float)
    return data


def make_layout(height=380, title=""):
    layout = dict(
        paper_bgcolor=BG, plot_bgcolor=BG2,
        font=dict(color=TEXT, size=11, family="monospace"),
        xaxis=dict(gridcolor=GRID, linecolor=GRID, showgrid=False),
        yaxis=dict(gridcolor=GRID, linecolor=GRID, zeroline=True, zerolinecolor="#444466"),
        hovermode="x unified",
        height=height,
        margin=dict(l=55, r=20, t=44 if title else 28, b=36),
        legend=dict(
            bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT, size=10),
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
        ),
    )
    if title:
        layout["title"] = dict(text=title, font=dict(size=12, color=MUTED), x=0, xanchor="left")
    return layout


def last(s: pd.Series):
    return s.dropna().iloc[-1] if len(s.dropna()) else float("nan")


def prev(s: pd.Series):
    return s.dropna().iloc[-2] if len(s.dropna()) >= 2 else float("nan")


# ── Main render ────────────────────────────────────────────────────────────────
def render():
    st.markdown("""
    <style>
    .kpi-card { background:#13132b; border:1px solid #1e1e3a; border-radius:8px;
                padding:14px 16px; text-align:center; }
    .kpi-value { font-family:monospace; font-size:1.75rem; font-weight:600; }
    .kpi-label { font-size:0.68rem; color:#6b6b8a; text-transform:uppercase;
                 letter-spacing:0.1em; margin-top:4px; }
    .kpi-sub   { font-family:monospace; font-size:0.75rem; margin-top:4px; }
    .sec { font-family:monospace; font-size:0.68rem; color:#6b6b8a; text-transform:uppercase;
           letter-spacing:0.15em; margin:24px 0 8px 0;
           border-bottom:1px solid #1e1e3a; padding-bottom:6px; }
    .insight { background:#0a0a18; border-left:3px solid #00d4ff; border-radius:0 6px 6px 0;
               padding:10px 14px; font-family:monospace; font-size:0.78rem;
               color:#9999bb; margin:8px 0 16px 0; }
    .curve-label { font-family:monospace; font-size:0.75rem; color:#6b6b8a;
                   text-align:center; margin-top:4px; }
    </style>
    """, unsafe_allow_html=True)

    # Range selector
    col_r, _ = st.columns([3, 7])
    with col_r:
        rng = st.radio("Range", ["2Y", "5Y", "10Y", "All"],
                       index=0, horizontal=True, label_visibility="collapsed",
                       key="rates_range")
    cuts = {"2Y": -504, "5Y": -1260, "10Y": -2520, "All": 0}   # ~252 trading days/yr
    cut  = cuts[rng]

    with st.spinner("Loading FRED rates data..."):
        try:
            data = load_all_rates()
        except Exception as e:
            st.error(f"Data fetch error: {e}")
            return

    def trim(s):
        return s.iloc[cut:] if cut != 0 and len(s) > abs(cut) else s

    # ── KPI Row ────────────────────────────────────────────────────────────────
    r10   = data["dgs10"]
    r2    = data["dgs2"]
    r30   = data["dgs30"]
    r3m   = data["dgs3m"]
    spr   = data["t10y2y"]
    ff    = data["fedfunds"]
    hy    = data["hy_oas"]
    nfci  = data["nfci"]
    tips10= data["tips10"]

    l_10  = last(r10)
    l_2   = last(r2)
    l_30  = last(r30)
    l_3m  = last(r3m)
    l_spr = last(spr)
    l_ff  = last(ff)
    l_hy  = last(hy)
    l_nfci= last(nfci)
    l_real= last(tips10)

    def spread_color(val):
        if val > 0.5:  return GREEN
        elif val > 0:  return AMBER
        else:          return RED

    def hy_color(val):
        if val < 350:  return GREEN
        elif val < 550:return AMBER
        else:          return RED

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    kpis = [
        (f"{l_10:.2f}%",          "10Y Treasury",  f"2Y: {l_2:.2f}%",        CYAN),
        (f"{l_3m:.2f}%",          "3M T-Bill",     f"30Y: {l_30:.2f}%",      BLUE),
        (f"{l_spr:+.2f}%",        "2s10s Spread",  "inverted = recession risk", spread_color(l_spr)),
        (f"{l_ff:.2f}%",          "Fed Funds",     "effective rate",           AMBER),
        (f"{l_hy:.0f}bp",         "HY OAS Spread", "High yield risk premium",  hy_color(l_hy)),
        (f"{l_nfci:+.2f}",        "NFCI",          "tight > 0 · loose < 0",   RED if l_nfci > 0 else GREEN),
    ]
    for col, (val, label, sub, color) in zip([c1,c2,c3,c4,c5,c6], kpis):
        with col:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-value" style="color:{color}">{val}</div>
                <div class="kpi-label">{label}</div>
                <div class="kpi-sub" style="color:{MUTED}">{sub}</div>
            </div>""", unsafe_allow_html=True)

    latest_date = r10.dropna().index[-1].strftime("%b %d, %Y") if len(r10.dropna()) else ""
    st.markdown(
        f'<div style="color:{MUTED};font-size:0.7rem;margin-top:6px;font-family:monospace">'
        f'Latest: {latest_date} · FRED · Daily data (except NFCI weekly)</div>',
        unsafe_allow_html=True)

    # ── Section 1: Full Yield Curve Snapshot ──────────────────────────────────
    st.markdown('<div class="sec">Yield Curve Shape — Today vs History</div>', unsafe_allow_html=True)

    col_curve, col_hist = st.columns([2, 3])

    TENORS = ["1M", "3M", "6M", "1Y", "2Y", "5Y", "10Y", "30Y"]
    KEYS   = ["dgs1m", "dgs3m", "dgs6m", "dgs1", "dgs2", "dgs5", "dgs10", "dgs30"]
    TENOR_YEARS = [1/12, 3/12, 6/12, 1, 2, 5, 10, 30]

    def get_curve_at(date_offset_days=0):
        """Get yield curve at a given date (0=latest, -252=1yr ago, etc.)."""
        vals = []
        for key in KEYS:
            s = data[key].dropna()
            if len(s) == 0:
                vals.append(None)
                continue
            if date_offset_days == 0:
                vals.append(s.iloc[-1])
            else:
                idx = max(0, len(s) + date_offset_days)
                vals.append(s.iloc[idx] if idx < len(s) else None)
        return vals

    curve_now  = get_curve_at(0)
    curve_1ya  = get_curve_at(-252)
    curve_2ya  = get_curve_at(-504)

    with col_curve:
        fig_cv = go.Figure()
        for label, vals, color, dash, width in [
            ("2Y ago",  curve_2ya, MUTED,  "dot",   1.5),
            ("1Y ago",  curve_1ya, BLUE,   "dash",  1.5),
            ("Today",   curve_now, CYAN,   "solid", 2.5),
        ]:
            clean_x = [TENOR_YEARS[i] for i, v in enumerate(vals) if v is not None]
            clean_y = [v for v in vals if v is not None]
            clean_labels = [TENORS[i] for i, v in enumerate(vals) if v is not None]
            fig_cv.add_trace(go.Scatter(
                name=label, x=clean_labels, y=clean_y,
                mode="lines+markers",
                line=dict(color=color, width=width, dash=dash),
                marker=dict(size=5),
                hovertemplate=f"<b>{label}</b> %{{x}}: %{{y:.2f}}%<extra></extra>",
            ))

        # Zero line
        fig_cv.add_hline(y=0, line_color="#444466", line_width=1, line_dash="dot")
        layout_cv = make_layout(340)
        layout_cv["yaxis"]["ticksuffix"] = "%"
        layout_cv["xaxis"]["title"] = dict(text="Maturity")
        fig_cv.update_layout(**layout_cv)
        st.plotly_chart(fig_cv, use_container_width=True)

    with col_hist:
        # Historical 2Y and 10Y over time
        r2_t  = trim(data["dgs2"])
        r10_t = trim(data["dgs10"])
        r30_t = trim(data["dgs30"])
        spr_t = trim(data["t10y2y"])

        fig_ht = make_subplots(specs=[[{"secondary_y": True}]])
        for name, s, color, dash in [
            ("30Y", r30_t, VIOLET, "dot"),
            ("10Y", r10_t, CYAN,   "solid"),
            ("2Y",  r2_t,  BLUE,   "dash"),
        ]:
            fig_ht.add_trace(go.Scatter(
                name=name, x=s.index, y=s.values,
                line=dict(color=color, width=2, dash=dash),
                hovertemplate=f"<b>{name}</b>: %{{y:.2f}}%<extra></extra>",
            ), secondary_y=False)

        # 2s10s spread as area
        fig_ht.add_trace(go.Scatter(
            name="2s10s Spread",
            x=spr_t.index, y=spr_t.values,
            fill="tozeroy",
            line=dict(color=AMBER, width=1),
            fillcolor="rgba(245,158,11,0.10)",
            hovertemplate="<b>2s10s</b>: %{y:+.2f}%<extra></extra>",
        ), secondary_y=True)

        fig_ht.add_hline(y=0, line_color=RED, line_width=1, line_dash="dot", secondary_y=True)

        fig_ht.update_layout(**make_layout(340))
        fig_ht.update_layout(paper_bgcolor=BG, plot_bgcolor=BG2, hovermode="x unified")
        fig_ht.update_yaxes(title_text="Yield %", gridcolor=GRID, linecolor=GRID,
                             zeroline=False, secondary_y=False,
                             title_font=dict(color=CYAN, size=10))
        fig_ht.update_yaxes(title_text="2s10s Spread %", gridcolor="rgba(0,0,0,0)",
                             zeroline=False, secondary_y=True,
                             title_font=dict(color=AMBER, size=10))
        fig_ht.update_xaxes(gridcolor=GRID, linecolor=GRID)
        st.plotly_chart(fig_ht, use_container_width=True)

    # Curve inversion insight
    inv_status = "🔴 INVERTIDA" if l_spr < 0 else ("🟡 PLANA" if l_spr < 0.5 else "🟢 NORMAL")
    days_inverted = (data["t10y2y"].dropna() < 0).sum()
    st.markdown(
        f'<div class="insight">📐 Curva {inv_status} — Spread 2s10s: <b style="color:{spread_color(l_spr)}">{l_spr:+.2f}%</b>. '
        f'10Y-3M: <b style="color:{spread_color(last(data["t10y3m"]))}">{last(data["t10y3m"]):+.2f}%</b>. '
        f'La inversión 10Y-3M tiene mejor track record como predictor de recesión (NY Fed model). '
        f'Curva actualmente: 10Y a {l_10:.2f}% vs Fed Funds {l_ff:.2f}%.</div>',
        unsafe_allow_html=True)

    # ── Section 2: Fed Funds & Policy Rate ────────────────────────────────────
    st.markdown('<div class="sec">Federal Reserve — Policy Rate & Real Rate</div>', unsafe_allow_html=True)

    ff_t    = trim(data["fedfunds"])
    fed_lb  = trim(data["fed_lb"])
    fed_ub  = trim(data["fed_ub"])
    tips_t  = trim(data["tips10"])
    r10_t2  = trim(data["dgs10"])

    fig_fed = go.Figure()

    # Target range band
    if len(fed_lb.dropna()) > 0 and len(fed_ub.dropna()) > 0:
        common_fed = fed_lb.dropna().index.intersection(fed_ub.dropna().index)
        if len(common_fed) > 0:
            lb = fed_lb.reindex(common_fed)
            ub = fed_ub.reindex(common_fed)
            fig_fed.add_trace(go.Scatter(
                name="Target Range",
                x=list(common_fed) + list(common_fed[::-1]),
                y=list(ub.values) + list(lb.values[::-1]),
                fill="toself",
                fillcolor="rgba(245,158,11,0.12)",
                line=dict(color="rgba(0,0,0,0)"),
                showlegend=True,
                hoverinfo="skip",
            ))

    # Effective Fed Funds
    fig_fed.add_trace(go.Scatter(
        name="Fed Funds Effective",
        x=ff_t.index, y=ff_t.values,
        line=dict(color=AMBER, width=2.5),
        hovertemplate="<b>Fed Funds</b>: %{y:.2f}%<extra></extra>",
    ))

    # 10Y nominal
    fig_fed.add_trace(go.Scatter(
        name="10Y Nominal",
        x=r10_t2.index, y=r10_t2.values,
        line=dict(color=CYAN, width=2, dash="dash"),
        hovertemplate="<b>10Y</b>: %{y:.2f}%<extra></extra>",
    ))

    # 10Y Real (TIPS)
    if len(tips_t.dropna()) > 0:
        fig_fed.add_trace(go.Scatter(
            name="10Y Real (TIPS)",
            x=tips_t.index, y=tips_t.values,
            line=dict(color=TEAL, width=2),
            fill="tozeroy",
            fillcolor="rgba(20,184,166,0.07)",
            hovertemplate="<b>10Y Real</b>: %{y:.2f}%<extra></extra>",
        ))
        fig_fed.add_hline(y=0, line_color="#444466", line_width=1, line_dash="dot")

    layout_fed = make_layout(360)
    layout_fed["yaxis"]["ticksuffix"] = "%"
    fig_fed.update_layout(**layout_fed)
    st.plotly_chart(fig_fed, use_container_width=True)

    # Neutral rate insight
    neutral_real = 0.5  # Rough r-star estimate
    policy_stance = "RESTRICTIVA" if l_real > neutral_real else "ACOMODATICIA"
    stance_color  = RED if l_real > neutral_real else GREEN
    st.markdown(
        f'<div class="insight">🎯 Tasa real a 10Y (TIPS): <b style="color:{TEAL}">{l_real:.2f}%</b>. '
        f'Estimado r* neutral ~0.5%. Política monetaria <b style="color:{stance_color}">{policy_stance}</b> en términos reales. '
        f'Fed Funds: <b style="color:{AMBER}">{l_ff:.2f}%</b>. '
        f'Con inflación breakeven 5Y a {last(data["tips5"]):.2f}%, la tasa real de corto plazo implícita es '
        f'~{l_ff - last(data["tips5"]):.2f}%.</div>',
        unsafe_allow_html=True)

    # ── Section 3: Credit Spreads ──────────────────────────────────────────────
    st.markdown('<div class="sec">Credit Spreads — IG / BBB / High Yield OAS (bp)</div>', unsafe_allow_html=True)

    ig_t  = trim(data["ig_oas"])
    hy_t  = trim(data["hy_oas"])
    bbb_t = trim(data["bbb_oas"])

    l_ig  = last(ig_t)
    l_hy2 = last(hy_t)
    l_bbb = last(bbb_t)

    # Historical percentiles
    def pctile(s, val):
        if len(s.dropna()) == 0: return float("nan")
        return (s.dropna() <= val).mean() * 100

    ig_pctile  = pctile(data["ig_oas"],  l_ig)
    hy_pctile  = pctile(data["hy_oas"],  l_hy2)
    bbb_pctile = pctile(data["bbb_oas"], l_bbb)

    # KPI mini row for spreads
    sc1, sc2, sc3 = st.columns(3)
    spread_kpis = [
        (f"{l_ig:.0f}bp",  "IG OAS",  f"histórico pctile {ig_pctile:.0f}%",  GREEN if ig_pctile < 40 else (AMBER if ig_pctile < 70 else RED)),
        (f"{l_bbb:.0f}bp", "BBB OAS", f"histórico pctile {bbb_pctile:.0f}%", GREEN if bbb_pctile < 40 else (AMBER if bbb_pctile < 70 else RED)),
        (f"{l_hy2:.0f}bp", "HY OAS",  f"histórico pctile {hy_pctile:.0f}%",  GREEN if hy_pctile < 40 else (AMBER if hy_pctile < 70 else RED)),
    ]
    for col, (val, label, sub, color) in zip([sc1,sc2,sc3], spread_kpis):
        with col:
            st.markdown(f"""
            <div class="kpi-card" style="margin-bottom:12px">
                <div class="kpi-value" style="color:{color};font-size:1.5rem">{val}</div>
                <div class="kpi-label">{label}</div>
                <div class="kpi-sub" style="color:{MUTED}">{sub}</div>
            </div>""", unsafe_allow_html=True)

    fig_cr = go.Figure()

    for name, s, color, dash in [
        ("IG OAS",  ig_t,  GREEN, "dot"),
        ("BBB OAS", bbb_t, AMBER, "dash"),
        ("HY OAS",  hy_t,  RED,   "solid"),
    ]:
        if len(s.dropna()) > 0:
            fig_cr.add_trace(go.Scatter(
                name=name, x=s.index, y=s.values,
                line=dict(color=color, width=2, dash=dash),
                hovertemplate=f"<b>{name}</b>: %{{y:.0f}}bp<extra></extra>",
            ))

    # Recession thresholds
    fig_cr.add_hrect(y0=600, y1=2500, fillcolor=RED, opacity=0.04, line_width=0,
                     annotation_text="Stress zone HY", annotation_position="top right",
                     annotation_font=dict(color=RED, size=9))
    fig_cr.add_hrect(y0=0, y1=150, fillcolor=GREEN, opacity=0.04, line_width=0,
                     annotation_text="Tight IG", annotation_position="bottom right",
                     annotation_font=dict(color=GREEN, size=9))

    layout_cr = make_layout(360)
    layout_cr["yaxis"]["title"] = dict(text="Basis Points (bp)")
    fig_cr.update_layout(**layout_cr)
    st.plotly_chart(fig_cr, use_container_width=True)

    # HY Spread interpretation
    hy_regime = "TIGHT (risk-on)" if l_hy2 < 350 else ("ELEVATED (caution)" if l_hy2 < 600 else "WIDE (stress/risk-off)")
    hy_r_color = GREEN if l_hy2 < 350 else (AMBER if l_hy2 < 600 else RED)
    st.markdown(
        f'<div class="insight">📊 HY OAS: <b style="color:{RED}">{l_hy2:.0f}bp</b> — régimen '
        f'<b style="color:{hy_r_color}">{hy_regime}</b> (pctile {hy_pctile:.0f}% histórico). '
        f'IG OAS: <b style="color:{GREEN}">{l_ig:.0f}bp</b> (pctile {ig_pctile:.0f}%). '
        f'BBB-IG differential: <b style="color:{AMBER}">{l_bbb - l_ig:.0f}bp</b> — proxy de riesgo fallen angel.</div>',
        unsafe_allow_html=True)

    # ── Section 4: Financial Conditions (NFCI) ────────────────────────────────
    st.markdown('<div class="sec">Financial Conditions — Chicago Fed NFCI</div>', unsafe_allow_html=True)

    nfci_t = trim(data["nfci"])

    fig_nf = go.Figure()

    # Color regions
    fig_nf.add_hrect(y0=-0.3, y1=0.3, fillcolor=AMBER, opacity=0.05, line_width=0)
    fig_nf.add_hrect(y0=0.3, y1=5, fillcolor=RED, opacity=0.05, line_width=0,
                     annotation_text="Tight conditions", annotation_position="top right",
                     annotation_font=dict(color=RED, size=9))
    fig_nf.add_hrect(y0=-5, y1=-0.3, fillcolor=GREEN, opacity=0.05, line_width=0,
                     annotation_text="Loose conditions", annotation_position="bottom right",
                     annotation_font=dict(color=GREEN, size=9))

    # Positive = tight (red), negative = loose (green)
    nfci_pos = nfci_t.copy(); nfci_pos[nfci_pos < 0] = 0
    nfci_neg = nfci_t.copy(); nfci_neg[nfci_neg > 0] = 0

    fig_nf.add_trace(go.Bar(
        name="Tight (NFCI > 0)", x=nfci_pos.index, y=nfci_pos.values,
        marker_color=RED, opacity=0.7,
        hovertemplate="<b>NFCI</b>: %{y:+.3f}<extra></extra>",
    ))
    fig_nf.add_trace(go.Bar(
        name="Loose (NFCI < 0)", x=nfci_neg.index, y=nfci_neg.values,
        marker_color=GREEN, opacity=0.7,
        hovertemplate="<b>NFCI</b>: %{y:+.3f}<extra></extra>",
    ))
    fig_nf.add_hline(y=0, line_color="#888899", line_width=1)

    layout_nf = make_layout(320)
    layout_nf["barmode"] = "overlay"
    layout_nf["xaxis"]["showgrid"] = False
    fig_nf.update_layout(**layout_nf)
    st.plotly_chart(fig_nf, use_container_width=True)

    nfci_interp = ("RESTRICTIVAS" if l_nfci > 0.3
                   else ("NEUTRALES" if l_nfci > -0.3 else "LAXAS"))
    nfci_color  = RED if l_nfci > 0.3 else (AMBER if l_nfci > -0.3 else GREEN)
    st.markdown(
        f'<div class="insight">🌡️ NFCI actual: <b style="color:{nfci_color}">{l_nfci:+.3f}</b> — Condiciones financieras '
        f'<b style="color:{nfci_color}">{nfci_interp}</b>. '
        f'El NFCI resume 105 indicadores de money markets, deuda y equity. '
        f'Lecturas sostenidas > 0 históricamente preceden contracción del crédito y menor crecimiento.</div>',
        unsafe_allow_html=True)

    # ── Section 5: Real Rates Heatmap ─────────────────────────────────────────
    st.markdown('<div class="sec">Rate Snapshot — Current Levels & Key Spreads</div>', unsafe_allow_html=True)

    # Build a summary table
    snap_rows = {
        "3M T-Bill":        last(data["dgs3m"]),
        "2Y Treasury":      last(data["dgs2"]),
        "5Y Treasury":      last(data["dgs5"]),
        "10Y Treasury":     last(data["dgs10"]),
        "30Y Treasury":     last(data["dgs30"]),
        "Fed Funds":        last(data["fedfunds"]),
        "2s10s Spread":     last(data["t10y2y"]),
        "10Y-3M Spread":    last(data["t10y3m"]),
        "10Y Real (TIPS)":  last(data["tips10"]),
        "IG OAS (bp)":      last(data["ig_oas"]),
        "BBB OAS (bp)":     last(data["bbb_oas"]),
        "HY OAS (bp)":      last(data["hy_oas"]),
        "NFCI":             last(data["nfci"]),
    }

    snap_df = pd.DataFrame.from_dict(snap_rows, orient="index", columns=["Current"])

    # 3M, 6M, 1Y changes
    for label, days in [("3M Δ", 63), ("6M Δ", 126), ("1Y Δ", 252)]:
        changes = {}
        for row_name in snap_rows:
            key_map = {
                "3M T-Bill": "dgs3m", "2Y Treasury": "dgs2", "5Y Treasury": "dgs5",
                "10Y Treasury": "dgs10", "30Y Treasury": "dgs30",
                "Fed Funds": "fedfunds", "2s10s Spread": "t10y2y",
                "10Y-3M Spread": "t10y3m", "10Y Real (TIPS)": "tips10",
                "IG OAS (bp)": "ig_oas", "BBB OAS (bp)": "bbb_oas",
                "HY OAS (bp)": "hy_oas", "NFCI": "nfci",
            }
            k = key_map.get(row_name)
            if k:
                s = data[k].dropna()
                if len(s) > days:
                    changes[row_name] = s.iloc[-1] - s.iloc[-days]
                else:
                    changes[row_name] = float("nan")
        snap_df[label] = pd.Series(changes)

    def color_rate_cell(val):
        if pd.isna(val): return "background:#0d0d1a;color:#3d3d5c;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"
        return "background:#13132b;color:#9999bb;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"

    def color_delta_cell(val):
        if pd.isna(val): return "background:#0d0d1a;color:#3d3d5c;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"
        if val > 0.5:    return "background:#3d1010;color:#f87171;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"
        elif val > 0:    return "background:#2d1515;color:#fca5a5;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"
        elif val < -0.5: return "background:#0d4f2b;color:#4ade80;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"
        else:            return "background:#0a3320;color:#34d399;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"

    def fmt_snap(row_label, val):
        if pd.isna(val): return "n/a"
        if "bp" in row_label or "OAS" in row_label: return f"{val:.0f}"
        if "NFCI" in row_label: return f"{val:+.3f}"
        return f"{val:.2f}%"

    def fmt_delta(row_label, val):
        if pd.isna(val): return "n/a"
        if "bp" in row_label or "OAS" in row_label: return f"{val:+.0f}"
        if "NFCI" in row_label: return f"{val:+.3f}"
        return f"{val:+.2f}%"

    display_data = {}
    for col_name in snap_df.columns:
        display_data[col_name] = [
            fmt_snap(idx, v) if col_name == "Current" else fmt_delta(idx, v)
            for idx, v in snap_df[col_name].items()
        ]

    display_df = pd.DataFrame(display_data, index=snap_df.index)

    # Style the numeric df
    def style_cell(val):
        return "background:#13132b;color:#9999bb;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"

    styled = (snap_df
        .style
        .applymap(color_rate_cell, subset=["Current"])
        .applymap(color_delta_cell, subset=["3M Δ", "6M Δ", "1Y Δ"])
        .format({
            "Current": lambda v: f"{v:.2f}" if not pd.isna(v) else "n/a",
            "3M Δ": lambda v: f"{v:+.2f}" if not pd.isna(v) else "n/a",
            "6M Δ": lambda v: f"{v:+.2f}" if not pd.isna(v) else "n/a",
            "1Y Δ": lambda v: f"{v:+.2f}" if not pd.isna(v) else "n/a",
        })
    )
    st.dataframe(styled, use_container_width=True)

    st.markdown(
        f'<div style="color:{MUTED};font-size:0.7rem;margin-top:12px;font-family:monospace">'
        f'Sources: FRED · DGS series (Treasury), BAML indices (Credit OAS), NFCI (Chicago Fed) · '
        f'Color delta: rojo = yields subiendo / verde = yields bajando</div>',
        unsafe_allow_html=True)
