"""
modules/corporate.py — Corporate Health module for Macro Terminal
Sources: BEA NIPA (Corporate Profits by Industry, T11300 / T11400)
         FRED (Profit margins proxy)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import json
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

# ── BEA Series Codes ───────────────────────────────────────────────────────────
# NIPA Table 6.16D — Corporate Profits by Industry (Level, $B SAAR)
# SeriesCodes from T11300 (with IVA & CCAdj)
PROFIT_CODES = {
    # Headline
    "total":          "A446RC",   # Domestic Industries Total
    "financial":      "A447RC",   # Financial
    "nonfinancial":   "A448RC",   # Nonfinancial
    # Nonfinancial breakdown
    "manufacturing":  "A449RC",   # Manufacturing
    "wholesale":      "A780RC",   # Wholesale Trade
    "retail":         "A782RC",   # Retail Trade
    "information":    "A784RC",   # Information
    "other_nonfin":   "A786RC",   # Other Nonfinancial
    # Retained/Distributed
    "retained":       "A455RC",   # Undistributed profits (retained earnings)
    "dividends":      "W009RC",   # Net dividends paid
}

# NIPA Table T10105 — GDP for profit margin calculation
GDP_CODE = "A191RC"   # Nominal GDP, $B SAAR  (T10105 or T10101)

# ── API helpers ────────────────────────────────────────────────────────────────
def _bea_key():
    try:    return st.secrets["BEA_API_KEY"]
    except: return os.getenv("BEA_API_KEY", "081DA2FC-1900-47A0-A40B-49C31925E395")

def _fred_key():
    try:    return st.secrets["FRED_API_KEY"]
    except: return os.getenv("FRED_API_KEY", "")


@st.cache_data(ttl=3600, show_spinner=False)
def load_profits() -> pd.DataFrame:
    """Fetch NIPA T11300 — Profits by Industry."""
    params = {
        "UserID": _bea_key(),
        "method": "GetData",
        "DataSetName": "NIPA",
        "TableName": "T11300",
        "Frequency": "Q",
        "Year": "ALL",
        "ResultFormat": "JSON",
    }
    resp = requests.get("https://apps.bea.gov/api/data", params=params, timeout=30)
    resp.raise_for_status()
    rows = resp.json()["BEAAPI"]["Results"]["Data"]
    df = pd.DataFrame(rows)
    df["DataValue"] = (
        df["DataValue"].astype(str)
        .str.replace(",", "", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
    )
    df["Date"] = df["TimePeriod"].apply(_parse_period)
    return df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)


@st.cache_data(ttl=3600, show_spinner=False)
def load_nominal_gdp() -> pd.Series:
    """Fetch nominal GDP from NIPA T10105 for margin calculation."""
    params = {
        "UserID": _bea_key(),
        "method": "GetData",
        "DataSetName": "NIPA",
        "TableName": "T10105",
        "Frequency": "Q",
        "Year": "ALL",
        "ResultFormat": "JSON",
    }
    resp = requests.get("https://apps.bea.gov/api/data", params=params, timeout=30)
    resp.raise_for_status()
    rows = resp.json()["BEAAPI"]["Results"]["Data"]
    df = pd.DataFrame(rows)
    df["DataValue"] = (
        df["DataValue"].astype(str)
        .str.replace(",", "", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
    )
    df["Date"] = df["TimePeriod"].apply(_parse_period)
    df = df.dropna(subset=["Date"])
    gdp = df[df["SeriesCode"] == GDP_CODE].set_index("Date")["DataValue"]
    return gdp.sort_index()


def _parse_period(p):
    p = str(p).strip()
    if "Q" in p:
        year, q = p.split("Q")
        month = int(q) * 3 - 2
        return pd.Timestamp(f"{year}-{month:02d}-01")
    return pd.NaT


def get_s(df, code):
    return df[df["SeriesCode"] == code].set_index("Date")["DataValue"].sort_index()


def qlabel(ts):
    return f"{ts.year} Q{(ts.month - 1) // 3 + 1}"


def make_layout(height=380, title=""):
    layout = dict(
        paper_bgcolor=BG, plot_bgcolor=BG2,
        font=dict(color=TEXT, size=11),
        xaxis=dict(gridcolor=GRID, linecolor=GRID, showgrid=False),
        yaxis=dict(gridcolor=GRID, linecolor=GRID, zeroline=True, zerolinecolor="#444466"),
        hovermode="x unified",
        height=height,
        margin=dict(l=60, r=20, t=44 if title else 28, b=36),
        legend=dict(
            bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT, size=10),
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
        ),
    )
    if title:
        layout["title"] = dict(text=title, font=dict(size=12, color=MUTED), x=0, xanchor="left")
    return layout


# ── Main render ────────────────────────────────────────────────────────────────
def render():
    st.markdown("""
    <style>
    .kpi-card { background:#13132b; border:1px solid #1e1e3a; border-radius:8px;
                padding:16px 20px; text-align:center; }
    .kpi-value { font-family:monospace; font-size:1.85rem; font-weight:600; }
    .kpi-label { font-size:0.72rem; color:#6b6b8a; text-transform:uppercase;
                 letter-spacing:0.1em; margin-top:4px; }
    .kpi-sub   { font-family:monospace; font-size:0.78rem; margin-top:4px; }
    .sec { font-family:monospace; font-size:0.68rem; color:#6b6b8a; text-transform:uppercase;
           letter-spacing:0.15em; margin:24px 0 8px 0;
           border-bottom:1px solid #1e1e3a; padding-bottom:6px; }
    .insight { background:#0a0a18; border-left:3px solid #00d4ff; border-radius:0 6px 6px 0;
               padding:10px 14px; font-family:monospace; font-size:0.78rem;
               color:#9999bb; margin:8px 0 16px 0; }
    </style>
    """, unsafe_allow_html=True)

    # Range selector
    col_r, _ = st.columns([3, 7])
    with col_r:
        rng = st.radio("Range", ["5Y", "10Y", "20Y", "All"],
                       index=1, horizontal=True, label_visibility="collapsed",
                       key="corp_range")
    cuts = {"5Y": -20, "10Y": -40, "20Y": -80, "All": 0}
    cut  = cuts[rng]

    with st.spinner("Loading BEA Corporate Profits data..."):
        try:
            df  = load_profits()
            gdp = load_nominal_gdp()
        except Exception as e:
            st.error(f"Data fetch error: {e}")
            return

    if df.empty:
        st.error("No profit data returned from BEA.")
        return

    def trim(s):
        return s.iloc[cut:] if cut != 0 else s

    # ── Pull series ────────────────────────────────────────────────────────────
    total     = get_s(df, PROFIT_CODES["total"])
    financial = get_s(df, PROFIT_CODES["financial"])
    nonfin    = get_s(df, PROFIT_CODES["nonfinancial"])
    mfg       = get_s(df, PROFIT_CODES["manufacturing"])
    wholesale = get_s(df, PROFIT_CODES["wholesale"])
    retail    = get_s(df, PROFIT_CODES["retail"])
    info      = get_s(df, PROFIT_CODES["information"])
    other_nf  = get_s(df, PROFIT_CODES["other_nonfin"])
    retained  = get_s(df, PROFIT_CODES["retained"])
    dividends = get_s(df, PROFIT_CODES["dividends"])

    # Common index for all main series
    common = total.index
    for s in [financial, nonfin]:
        if len(s): common = common.intersection(s.index)
    common = common.sort_values()

    if len(common) < 4:
        st.error("Not enough overlapping data.")
        return

    # YoY growth
    def yoy(s): return s.pct_change(4) * 100

    total_yoy    = yoy(total)
    fin_yoy      = yoy(financial)
    nonfin_yoy   = yoy(nonfin)

    # Profit margin = Total Corporate Profits / Nominal GDP
    margin_idx   = total.index.intersection(gdp.index)
    margin       = (total.reindex(margin_idx) / gdp.reindex(margin_idx)) * 100

    # Latest values
    l_total  = total.dropna().iloc[-1]  if len(total.dropna())  else 0
    l_fin    = financial.dropna().iloc[-1] if len(financial.dropna()) else 0
    l_nonfin = nonfin.dropna().iloc[-1]   if len(nonfin.dropna())    else 0
    l_margin = margin.dropna().iloc[-1]   if len(margin.dropna())    else 0
    l_yoy    = total_yoy.dropna().iloc[-1] if len(total_yoy.dropna()) else 0

    latest_q = qlabel(common[-1])

    # ── KPI Cards ─────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    kpis = [
        (f"${l_total/1000:.1f}T",    "Total Profits",       "SAAR, annualized",   CYAN),
        (f"{l_yoy:+.1f}%",           "YoY Growth",          f"vs year ago",        GREEN if l_yoy >= 0 else RED),
        (f"{l_margin:.1f}%",         "Profit Margin",       "% of Nominal GDP",   AMBER),
        (f"${l_fin/1000:.1f}T",      "Financial",           "sector profits",      BLUE),
        (f"${l_nonfin/1000:.1f}T",   "Non-Financial",       "sector profits",      VIOLET),
    ]
    for col, (val, label, sub, color) in zip([c1,c2,c3,c4,c5], kpis):
        with col:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-value" style="color:{color}">{val}</div>
                <div class="kpi-label">{label}</div>
                <div class="kpi-sub" style="color:{MUTED}">{sub}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown(
        f'<div style="color:{MUTED};font-size:0.7rem;margin-top:6px;font-family:monospace">'
        f'Latest: {latest_q} · BEA NIPA T11300 · Corporate Profits with IVA & CCAdj · $B SAAR</div>',
        unsafe_allow_html=True)

    # ── Section 1: Total Profits Level + YoY ──────────────────────────────────
    st.markdown('<div class="sec">Corporate Profits — Level & YoY Growth</div>', unsafe_allow_html=True)

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    tot_t = trim(total.reindex(common))
    yoy_t = trim(total_yoy.reindex(common))
    qlabels = [qlabel(d) for d in trim(common)]

    fig.add_trace(go.Bar(
        name="Total Profits ($B)",
        x=qlabels, y=tot_t.values,
        marker_color=CYAN, opacity=0.5,
        hovertemplate="<b>Total Profits</b>: $%{y:,.0f}B<extra></extra>",
    ), secondary_y=False)

    colors_yoy = [GREEN if v >= 0 else RED for v in yoy_t.fillna(0).values]
    fig.add_trace(go.Scatter(
        name="YoY %",
        x=qlabels, y=yoy_t.values,
        line=dict(color=AMBER, width=2.5),
        hovertemplate="<b>YoY Growth</b>: %{y:+.1f}%<extra></extra>",
    ), secondary_y=True)

    fig.add_hline(y=0, line_color="#444466", line_width=1, secondary_y=True)
    fig.update_layout(**make_layout(360))
    fig.update_layout(paper_bgcolor=BG, plot_bgcolor=BG2, hovermode="x unified", barmode="overlay")
    fig.update_yaxes(title_text="Profits $B (SAAR)", gridcolor=GRID, linecolor=GRID,
                     zeroline=False, secondary_y=False, title_font=dict(color=CYAN, size=10))
    fig.update_yaxes(title_text="YoY %", gridcolor="rgba(0,0,0,0)",
                     zeroline=False, secondary_y=True, title_font=dict(color=AMBER, size=10))
    fig.update_xaxes(gridcolor=GRID, linecolor=GRID)
    st.plotly_chart(fig, use_container_width=True)

    # ── Section 2: Financial vs Non-Financial ─────────────────────────────────
    st.markdown('<div class="sec">Financial vs Non-Financial Corporate Profits</div>', unsafe_allow_html=True)

    fin_t   = trim(financial.reindex(common).fillna(0))
    nonfin_t= trim(nonfin.reindex(common).fillna(0))
    ql_t    = [qlabel(d) for d in trim(common)]

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        name="Financial", x=ql_t, y=fin_t.values,
        line=dict(color=BLUE, width=2.5),
        fill="tozeroy", fillcolor="rgba(59,130,246,0.08)",
        hovertemplate="<b>Financial</b>: $%{y:,.0f}B<extra></extra>",
    ))
    fig2.add_trace(go.Scatter(
        name="Non-Financial", x=ql_t, y=nonfin_t.values,
        line=dict(color=VIOLET, width=2.5),
        fill="tozeroy", fillcolor="rgba(167,139,250,0.08)",
        hovertemplate="<b>Non-Financial</b>: $%{y:,.0f}B<extra></extra>",
    ))
    fig2.update_layout(**make_layout(320))
    st.plotly_chart(fig2, use_container_width=True)

    # Fin vs NonFin share
    fin_share   = (fin_t / (fin_t + nonfin_t) * 100).dropna()
    latest_fin_share = fin_share.iloc[-1] if len(fin_share) else 0
    st.markdown(
        f'<div class="insight">🏦 Financial sector share of total domestic profits: '
        f'<b style="color:{BLUE}">{latest_fin_share:.1f}%</b>. '
        f'Financial > 30% historically signals financialization of the economy. '
        f'Sharp moves often precede credit stress.</div>',
        unsafe_allow_html=True)

    # ── Section 3: Nonfinancial Industry Breakdown ─────────────────────────────
    st.markdown('<div class="sec">Non-Financial Profit Breakdown by Industry</div>', unsafe_allow_html=True)

    industry_series = {
        "Manufacturing": (mfg,       "#10b981"),
        "Wholesale":     (wholesale,  "#34d399"),
        "Retail":        (retail,     "#f59e0b"),
        "Information":   (info,       "#a78bfa"),
        "Other":         (other_nf,   "#94a3b8"),
    }

    fig3 = go.Figure()
    for label, (s, color) in industry_series.items():
        st_s = trim(s.reindex(common).fillna(0))
        fig3.add_trace(go.Bar(
            name=label, x=ql_t, y=st_s.values,
            marker_color=color,
            marker_line_color=BG2, marker_line_width=0.5,
            hovertemplate=f"<b>{label}</b>: $%{{y:,.0f}}B<extra></extra>",
        ))

    fig3.update_layout(**make_layout(340), barmode="stack")
    st.plotly_chart(fig3, use_container_width=True)

    # ── Section 4: Profit Margin (Profits / GDP) ──────────────────────────────
    st.markdown('<div class="sec">Corporate Profit Margin — % of Nominal GDP</div>', unsafe_allow_html=True)

    margin_t = trim(margin)
    margin_ql = [qlabel(d) for d in margin_t.index]

    # Historical avg
    hist_avg  = margin.mean()
    hist_peak = margin.max()

    fig4 = go.Figure()
    fig4.add_hrect(
        y0=hist_avg - 0.3, y1=hist_avg + 0.3,
        fillcolor=GREEN, opacity=0.06, line_width=0,
        annotation_text=f"Hist avg {hist_avg:.1f}%",
        annotation_position="top right",
        annotation_font=dict(color=GREEN, size=9),
    )
    fig4.add_trace(go.Scatter(
        name="Profit Margin % GDP",
        x=margin_ql, y=margin_t.values,
        line=dict(color=TEAL, width=2.5),
        fill="tozeroy", fillcolor="rgba(20,184,166,0.08)",
        hovertemplate="<b>Margin</b>: %{y:.2f}% of GDP<extra></extra>",
    ))
    fig4.add_hline(y=hist_avg, line_color=GREEN, line_width=1, line_dash="dot")

    layout4 = make_layout(300)
    layout4["yaxis"]["ticksuffix"] = "%"
    fig4.update_layout(**layout4)
    st.plotly_chart(fig4, use_container_width=True)

    st.markdown(
        f'<div class="insight">📊 Profit margin actual: <b style="color:{TEAL}">{l_margin:.2f}%</b> del GDP nominal. '
        f'Media histórica: <b style="color:{GREEN}">{hist_avg:.2f}%</b>. '
        f'Pico histórico: <b style="color:{AMBER}">{hist_peak:.2f}%</b>. '
        f'Margins por encima del promedio histórico sugieren presión bajista de largo plazo '
        f'(mean reversion, presión laboral o regulatoria).</div>',
        unsafe_allow_html=True)

    # ── Section 5: Retained Earnings vs Dividends ─────────────────────────────
    st.markdown('<div class="sec">Profit Disposition — Retained Earnings vs Dividends</div>', unsafe_allow_html=True)

    ret_t = trim(retained.reindex(common).fillna(method="ffill"))
    div_t = trim(dividends.reindex(common).fillna(method="ffill"))

    # Payout ratio
    payout = (div_t / (ret_t + div_t).replace(0, float("nan")) * 100).fillna(0)
    latest_payout = payout.iloc[-1] if len(payout) else 0

    fig5 = make_subplots(specs=[[{"secondary_y": True}]])
    fig5.add_trace(go.Bar(
        name="Retained Earnings", x=ql_t, y=ret_t.values,
        marker_color=GREEN, opacity=0.8,
        hovertemplate="<b>Retained</b>: $%{y:,.0f}B<extra></extra>",
    ), secondary_y=False)
    fig5.add_trace(go.Bar(
        name="Dividends", x=ql_t, y=div_t.values,
        marker_color=PINK, opacity=0.8,
        hovertemplate="<b>Dividends</b>: $%{y:,.0f}B<extra></extra>",
    ), secondary_y=False)
    fig5.add_trace(go.Scatter(
        name="Payout Ratio %", x=ql_t, y=payout.values,
        line=dict(color=AMBER, width=2, dash="dot"),
        hovertemplate="<b>Payout Ratio</b>: %{y:.1f}%<extra></extra>",
    ), secondary_y=True)

    fig5.update_layout(**make_layout(320), barmode="stack")
    fig5.update_layout(paper_bgcolor=BG, plot_bgcolor=BG2, hovermode="x unified")
    fig5.update_yaxes(title_text="$B SAAR", gridcolor=GRID, linecolor=GRID,
                      zeroline=False, secondary_y=False, title_font=dict(color=GREEN, size=10))
    fig5.update_yaxes(title_text="Payout %", gridcolor="rgba(0,0,0,0)",
                      zeroline=False, secondary_y=True, title_font=dict(color=AMBER, size=10))
    fig5.update_xaxes(gridcolor=GRID, linecolor=GRID)
    st.plotly_chart(fig5, use_container_width=True)

    st.markdown(
        f'<div class="insight">💰 Payout ratio actual: <b style="color:{PINK}">{latest_payout:.0f}%</b> de profits distribuidos como dividendos. '
        f'Alto payout = management defensivo / menos reinversión. '
        f'Retained earnings elevados = potencial capex, M&A o buybacks futuros.</div>',
        unsafe_allow_html=True)

    # ── Heatmap: Last 8 Quarters ───────────────────────────────────────────────
    st.markdown('<div class="sec">Corporate Profits Snapshot — Last 8 Quarters ($B SAAR)</div>', unsafe_allow_html=True)

    last8 = common[-8:]
    ql8   = [qlabel(d) for d in last8]

    snap = {
        "Total":          total.reindex(last8).fillna(0),
        "Financial":      financial.reindex(last8).fillna(0),
        "Non-Financial":  nonfin.reindex(last8).fillna(0),
        "Manufacturing":  mfg.reindex(last8).fillna(0),
        "Information":    info.reindex(last8).fillna(0),
        "Retail":         retail.reindex(last8).fillna(0),
        "Retained":       retained.reindex(last8).fillna(0),
        "Dividends":      dividends.reindex(last8).fillna(0),
        "Margin % GDP":   margin.reindex(last8).fillna(0),
    }

    snap_df = pd.DataFrame({k: v.values for k, v in snap.items()}, index=ql8).T

    def color_cell(val):
        # Color based on magnitude for level data
        if val > 1500:   return "background:#0d4f2b;color:#4ade80;text-align:center;font-family:monospace;font-size:0.78rem;padding:5px"
        elif val > 800:  return "background:#0a3320;color:#34d399;text-align:center;font-family:monospace;font-size:0.78rem;padding:5px"
        elif val > 200:  return "background:#0c2918;color:#6ee7b7;text-align:center;font-family:monospace;font-size:0.78rem;padding:5px"
        elif val > 0:    return "background:#13132b;color:#9999bb;text-align:center;font-family:monospace;font-size:0.78rem;padding:5px"
        else:            return "background:#2d1515;color:#fca5a5;text-align:center;font-family:monospace;font-size:0.78rem;padding:5px"

    def fmt_cell(row_label, val):
        if row_label == "Margin % GDP":
            return f"{val:.2f}%"
        return f"${val:,.0f}"

    # Build display df with custom formatting per row
    display_rows = {}
    for row_label, vals in snap.items():
        display_rows[row_label] = [
            f"{v:.2f}%" if row_label == "Margin % GDP" else f"${v:,.0f}"
            for v in vals.values
        ]
    display_df = pd.DataFrame(display_rows, index=ql8).T

    styled = snap_df.style.applymap(color_cell)
    st.dataframe(styled, use_container_width=True)

    st.markdown(
        f'<div style="color:{MUTED};font-size:0.7rem;margin-top:12px;font-family:monospace">'
        f'Sources: BEA NIPA Table 11.3 · Corporate Profits with IVA & CCAdj · SAAR</div>',
        unsafe_allow_html=True)
