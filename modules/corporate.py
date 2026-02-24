"""
modules/corporate.py — Corporate Health for Macro Terminal
Sources:
  BEA NIPA Table 6.16D  → Corporate Profits by Industry (quarterly, $B SAAR)
  BEA NIPA Table 1.1.5  → Nominal GDP (for margin)
  BEA NIPA Table 6.19D  → Undistributed profits & dividends
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

# ── BEA Table / Series mapping ─────────────────────────────────────────────────
# BEA NIPA API: TableName format is "T" + table number without dots
# Table 6.16D → T61600D  |  Table 6.19D → T61900D  |  Table 1.1.5 → T10105
PROFIT_TABLE = "T61600D"
PROFIT_CODES = {
    "total":         "A446RC",
    "financial":     "A447RC",
    "nonfinancial":  "A448RC",
    "manufacturing": "A449RC",
    "wholesale":     "A780RC",
    "retail":        "A782RC",
    "information":   "A784RC",
    "other_nonfin":  "A786RC",
}

DISPOSITION_TABLE = "T61900D"
DISPOSITION_CODES = {
    "retained":  "A455RC",
    "dividends": "W009RC",
}

GDP_TABLE = "T10105"
GDP_CODE  = "A191RC"


# ── Helpers ────────────────────────────────────────────────────────────────────
def _bea_key():
    try:    return st.secrets["BEA_API_KEY"]
    except: return os.getenv("BEA_API_KEY", "081DA2FC-1900-47A0-A40B-49C31925E395")


def _fetch_nipa(table: str, frequency: str = "Q") -> pd.DataFrame:
    params = {
        "UserID":       _bea_key(),
        "method":       "GetData",
        "DataSetName":  "NIPA",
        "TableName":    table,
        "Frequency":    frequency,
        "Year":         "ALL",
        "ResultFormat": "JSON",
    }
    resp = requests.get("https://apps.bea.gov/api/data", params=params, timeout=40)
    resp.raise_for_status()
    body = resp.json().get("BEAAPI", {})

    # Surface BEA-level errors (HTTP 200 but error payload)
    if "Error" in body:
        msg = body["Error"].get("APIErrorDescription", str(body["Error"]))
        raise RuntimeError(f"BEA API error [{table}]: {msg}")

    results = body.get("Results", {})
    if "Data" not in results:
        raise RuntimeError(
            f"BEA returned no 'Data' for {table}. "
            f"Results keys: {list(results.keys())}. "
            f"Preview: {str(body)[:400]}"
        )

    df = pd.DataFrame(results["Data"])
    df["DataValue"] = pd.to_numeric(
        df["DataValue"].astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    ).fillna(0)
    df["Date"] = df["TimePeriod"].apply(_parse_period)
    return df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)


def _parse_period(p: str) -> pd.Timestamp:
    p = str(p).strip()
    if "Q" in p:
        year, q = p.split("Q")
        return pd.Timestamp(f"{year}-{int(q)*3-2:02d}-01")
    return pd.NaT


def _get(df: pd.DataFrame, code: str) -> pd.Series:
    return df[df["SeriesCode"] == code].set_index("Date")["DataValue"].sort_index()


def _ql(ts): return f"{ts.year} Q{(ts.month-1)//3+1}"


def _layout(h=380, title=""):
    d = dict(
        paper_bgcolor=BG, plot_bgcolor=BG2,
        font=dict(color=TEXT, size=11, family="monospace"),
        xaxis=dict(gridcolor=GRID, linecolor=GRID, showgrid=False),
        yaxis=dict(gridcolor=GRID, linecolor=GRID, zeroline=True, zerolinecolor="#444466"),
        hovermode="x unified", height=h,
        margin=dict(l=60, r=20, t=44 if title else 28, b=36),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT, size=10),
                    orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    if title:
        d["title"] = dict(text=title, font=dict(size=12, color=MUTED), x=0, xanchor="left")
    return d


@st.cache_data(ttl=3600, show_spinner=False)
def _load_profits():   return _fetch_nipa(PROFIT_TABLE)

@st.cache_data(ttl=3600, show_spinner=False)
def _load_disp():      return _fetch_nipa(DISPOSITION_TABLE)

@st.cache_data(ttl=3600, show_spinner=False)
def _load_gdp():
    df = _fetch_nipa(GDP_TABLE)
    return _get(df, GDP_CODE)


# ── render ─────────────────────────────────────────────────────────────────────
def render():
    st.markdown("""<style>
    .kpi-card{background:#13132b;border:1px solid #1e1e3a;border-radius:8px;padding:16px 20px;text-align:center;}
    .kpi-value{font-family:monospace;font-size:1.85rem;font-weight:600;}
    .kpi-label{font-size:0.72rem;color:#6b6b8a;text-transform:uppercase;letter-spacing:0.1em;margin-top:4px;}
    .kpi-sub{font-family:monospace;font-size:0.78rem;margin-top:4px;}
    .sec{font-family:monospace;font-size:0.68rem;color:#6b6b8a;text-transform:uppercase;
         letter-spacing:0.15em;margin:24px 0 8px 0;border-bottom:1px solid #1e1e3a;padding-bottom:6px;}
    .insight{background:#0a0a18;border-left:3px solid #00d4ff;border-radius:0 6px 6px 0;
             padding:10px 14px;font-family:monospace;font-size:0.78rem;color:#9999bb;margin:8px 0 16px 0;}
    </style>""", unsafe_allow_html=True)

    col_r, _ = st.columns([3, 7])
    with col_r:
        rng = st.radio("Range", ["5Y","10Y","20Y","All"], index=1,
                       horizontal=True, label_visibility="collapsed", key="corp_range")
    cut = {"5Y":-20,"10Y":-40,"20Y":-80,"All":0}[rng]

    # ── Load data ──────────────────────────────────────────────────────────────
    with st.spinner("Loading BEA Corporate Profits..."):
        profits_df = disp_df = gdp_s = None
        errs = []
        try:   profits_df = _load_profits()
        except Exception as e: errs.append(f"**Profits (T61600D):** {e}")
        try:   disp_df = _load_disp()
        except Exception as e: errs.append(f"**Disposition (T61900D):** {e}")
        try:   gdp_s = _load_gdp()
        except Exception as e: errs.append(f"**GDP (T10105):** {e}")

    if errs:
        for e in errs: st.error(e)
        if profits_df is None: return

    # ── Series ─────────────────────────────────────────────────────────────────
    total     = _get(profits_df, PROFIT_CODES["total"])
    financial = _get(profits_df, PROFIT_CODES["financial"])
    nonfin    = _get(profits_df, PROFIT_CODES["nonfinancial"])
    mfg       = _get(profits_df, PROFIT_CODES["manufacturing"])
    wholesale = _get(profits_df, PROFIT_CODES["wholesale"])
    retail    = _get(profits_df, PROFIT_CODES["retail"])
    info      = _get(profits_df, PROFIT_CODES["information"])
    other_nf  = _get(profits_df, PROFIT_CODES["other_nonfin"])

    # If any key series is empty, show diagnostic
    if total.empty:
        avail = sorted(profits_df["SeriesCode"].unique())
        st.error(
            f"SeriesCode '{PROFIT_CODES['total']}' not found in T61600D.\n\n"
            f"Available codes (first 40): {avail[:40]}\n\n"
            f"Please open a GitHub issue with this list to fix the mapping."
        )
        return

    common = total.index
    for s in [financial, nonfin]:
        if len(s): common = common.intersection(s.index)
    common = common.sort_values()

    def _trim(s, idx=common):
        s = s.reindex(idx).fillna(0)
        return s.iloc[cut:] if cut != 0 else s

    ql_full = [_ql(d) for d in common]
    ql_t    = ql_full[cut:] if cut != 0 else ql_full

    tot_t    = _trim(total)
    fin_t    = _trim(financial)
    nonfin_t = _trim(nonfin)
    yoy_full = total.pct_change(4) * 100
    yoy_t    = _trim(yoy_full)

    l_total  = float(total.dropna().iloc[-1])      if len(total.dropna())    else 0
    l_fin    = float(financial.dropna().iloc[-1])   if len(financial.dropna()) else 0
    l_nonfin = float(nonfin.dropna().iloc[-1])      if len(nonfin.dropna())   else 0
    l_yoy    = float(yoy_full.dropna().iloc[-1])    if len(yoy_full.dropna()) else 0

    margin = pd.Series(dtype=float)
    l_margin = 0.0
    if gdp_s is not None and len(gdp_s):
        midx   = total.index.intersection(gdp_s.index)
        margin = (total.reindex(midx) / gdp_s.reindex(midx) * 100)
        l_margin = float(margin.dropna().iloc[-1]) if len(margin.dropna()) else 0

    # ── KPIs ───────────────────────────────────────────────────────────────────
    cols = st.columns(5)
    for col, (val, label, sub, color) in zip(cols, [
        (f"${l_total/1000:.1f}T",  "Total Profits",  "SAAR annualized",   CYAN),
        (f"{l_yoy:+.1f}%",         "YoY Growth",     "vs year ago",        GREEN if l_yoy>=0 else RED),
        (f"{l_margin:.1f}%",       "Profit/GDP",     "vs nominal GDP",    AMBER),
        (f"${l_fin/1000:.1f}T",    "Financial",      "sector profits",     BLUE),
        (f"${l_nonfin/1000:.1f}T", "Non-Financial",  "sector profits",     VIOLET),
    ]):
        with col:
            st.markdown(f'<div class="kpi-card"><div class="kpi-value" style="color:{color}">{val}</div>'
                        f'<div class="kpi-label">{label}</div>'
                        f'<div class="kpi-sub" style="color:{MUTED}">{sub}</div></div>', unsafe_allow_html=True)

    st.markdown(f'<div style="color:{MUTED};font-size:0.7rem;margin-top:6px;font-family:monospace">'
                f'Latest: {_ql(common[-1])} · BEA NIPA T61600D · $B SAAR</div>', unsafe_allow_html=True)

    # ── 1. Level + YoY ─────────────────────────────────────────────────────────
    st.markdown('<div class="sec">Corporate Profits — Level & YoY Growth</div>', unsafe_allow_html=True)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(name="Profits ($B)", x=ql_t, y=tot_t.values,
        marker_color=CYAN, opacity=0.45,
        hovertemplate="<b>Profits</b>: $%{y:,.0f}B<extra></extra>"), secondary_y=False)
    fig.add_trace(go.Scatter(name="YoY %", x=ql_t, y=yoy_t.values,
        line=dict(color=AMBER, width=2.5),
        hovertemplate="<b>YoY</b>: %{y:+.1f}%<extra></extra>"), secondary_y=True)
    fig.add_hline(y=0, line_color="#444466", line_width=1, secondary_y=True)
    fig.update_layout(**_layout(360), barmode="overlay", paper_bgcolor=BG, plot_bgcolor=BG2, hovermode="x unified")
    fig.update_yaxes(title_text="$B", gridcolor=GRID, zeroline=False, secondary_y=False, title_font=dict(color=CYAN,size=10))
    fig.update_yaxes(title_text="YoY %", gridcolor="rgba(0,0,0,0)", zeroline=False, secondary_y=True, title_font=dict(color=AMBER,size=10))
    fig.update_xaxes(gridcolor=GRID, linecolor=GRID)
    st.plotly_chart(fig, use_container_width=True)

    # ── 2. Fin vs NonFin ───────────────────────────────────────────────────────
    st.markdown('<div class="sec">Financial vs Non-Financial Corporate Profits</div>', unsafe_allow_html=True)
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(name="Financial", x=ql_t, y=fin_t.values,
        line=dict(color=BLUE, width=2.5), fill="tozeroy", fillcolor="rgba(59,130,246,0.08)",
        hovertemplate="<b>Financial</b>: $%{y:,.0f}B<extra></extra>"))
    fig2.add_trace(go.Scatter(name="Non-Financial", x=ql_t, y=nonfin_t.values,
        line=dict(color=VIOLET, width=2.5), fill="tozeroy", fillcolor="rgba(167,139,250,0.08)",
        hovertemplate="<b>Non-Fin</b>: $%{y:,.0f}B<extra></extra>"))
    fig2.update_layout(**_layout(300))
    st.plotly_chart(fig2, use_container_width=True)

    denom = (fin_t + nonfin_t).replace(0, float("nan"))
    fin_share = float((fin_t / denom * 100).dropna().iloc[-1]) if len((fin_t/denom*100).dropna()) else 0
    st.markdown(f'<div class="insight">🏦 Financial share: <b style="color:{BLUE}">{fin_share:.1f}%</b> of domestic profits. '
                f'>30% históricamente señala financialization elevada.</div>', unsafe_allow_html=True)

    # ── 3. Industry Breakdown ──────────────────────────────────────────────────
    st.markdown('<div class="sec">Non-Financial Breakdown by Industry</div>', unsafe_allow_html=True)
    fig3 = go.Figure()
    for label, s, color in [
        ("Manufacturing", mfg, "#10b981"), ("Wholesale", wholesale, "#34d399"),
        ("Retail", retail, "#f59e0b"),     ("Information", info, "#a78bfa"),
        ("Other", other_nf, "#94a3b8"),
    ]:
        vals = s.reindex(common).fillna(0)
        vals = vals.iloc[cut:] if cut != 0 else vals
        fig3.add_trace(go.Bar(name=label, x=ql_t, y=vals.values,
            marker_color=color, marker_line_color=BG2, marker_line_width=0.4,
            hovertemplate=f"<b>{label}</b>: $%{{y:,.0f}}B<extra></extra>"))
    fig3.update_layout(**_layout(320), barmode="stack")
    st.plotly_chart(fig3, use_container_width=True)

    # ── 4. Profit Margin ───────────────────────────────────────────────────────
    st.markdown('<div class="sec">Profit Margin — % of Nominal GDP</div>', unsafe_allow_html=True)
    if len(margin):
        m_trim = margin.iloc[cut:] if cut != 0 else margin
        m_ql   = [_ql(d) for d in m_trim.index]
        h_avg  = float(margin.mean())
        h_peak = float(margin.max())
        fig4 = go.Figure()
        fig4.add_hrect(y0=h_avg-0.3, y1=h_avg+0.3, fillcolor=GREEN, opacity=0.06, line_width=0,
                       annotation_text=f"Avg {h_avg:.1f}%", annotation_position="top right",
                       annotation_font=dict(color=GREEN, size=9))
        fig4.add_trace(go.Scatter(name="Profit/GDP %", x=m_ql, y=m_trim.values,
            line=dict(color=TEAL, width=2.5), fill="tozeroy", fillcolor="rgba(20,184,166,0.07)",
            hovertemplate="<b>Margin</b>: %{y:.2f}%<extra></extra>"))
        fig4.add_hline(y=h_avg, line_color=GREEN, line_width=1, line_dash="dot")
        l4 = _layout(300)
        l4["yaxis"]["ticksuffix"] = "%"
        fig4.update_layout(**l4)
        st.plotly_chart(fig4, use_container_width=True)
        st.markdown(f'<div class="insight">📊 Margin: <b style="color:{TEAL}">{l_margin:.2f}%</b> · '
                    f'Avg: <b style="color:{GREEN}">{h_avg:.2f}%</b> · '
                    f'Peak: <b style="color:{AMBER}">{h_peak:.2f}%</b>. '
                    f'Persistencia por encima del promedio históricamente precede compresión.</div>', unsafe_allow_html=True)
    else:
        st.info("GDP data unavailable for margin calculation.")

    # ── 5. Retained vs Dividends ───────────────────────────────────────────────
    st.markdown('<div class="sec">Profit Disposition — Retained Earnings vs Dividends</div>', unsafe_allow_html=True)
    if disp_df is not None:
        retained  = _get(disp_df, DISPOSITION_CODES["retained"])
        dividends = _get(disp_df, DISPOSITION_CODES["dividends"])
        ret_idx   = common.intersection(retained.index).intersection(dividends.index)
        if len(ret_idx) > 4:
            ret_t = retained.reindex(ret_idx).ffill().fillna(0)
            div_t = dividends.reindex(ret_idx).ffill().fillna(0)
            ret_t = ret_t.iloc[cut:] if cut != 0 else ret_t
            div_t = div_t.iloc[cut:] if cut != 0 else div_t
            ql_r  = [_ql(d) for d in (ret_idx[cut:] if cut != 0 else ret_idx)]
            denom_d = (ret_t + div_t).replace(0, float("nan"))
            payout  = (div_t / denom_d * 100).fillna(0)
            l_pay   = float(payout.iloc[-1]) if len(payout) else 0

            fig5 = make_subplots(specs=[[{"secondary_y": True}]])
            fig5.add_trace(go.Bar(name="Retained", x=ql_r, y=ret_t.values,
                marker_color=GREEN, opacity=0.8,
                hovertemplate="<b>Retained</b>: $%{y:,.0f}B<extra></extra>"), secondary_y=False)
            fig5.add_trace(go.Bar(name="Dividends", x=ql_r, y=div_t.values,
                marker_color=PINK, opacity=0.8,
                hovertemplate="<b>Dividends</b>: $%{y:,.0f}B<extra></extra>"), secondary_y=False)
            fig5.add_trace(go.Scatter(name="Payout %", x=ql_r, y=payout.values,
                line=dict(color=AMBER, width=2, dash="dot"),
                hovertemplate="<b>Payout</b>: %{y:.1f}%<extra></extra>"), secondary_y=True)
            fig5.update_layout(**_layout(300), barmode="stack", paper_bgcolor=BG, plot_bgcolor=BG2, hovermode="x unified")
            fig5.update_yaxes(title_text="$B", gridcolor=GRID, zeroline=False, secondary_y=False, title_font=dict(color=GREEN,size=10))
            fig5.update_yaxes(title_text="Payout %", gridcolor="rgba(0,0,0,0)", zeroline=False, secondary_y=True, title_font=dict(color=AMBER,size=10))
            fig5.update_xaxes(gridcolor=GRID, linecolor=GRID)
            st.plotly_chart(fig5, use_container_width=True)
            st.markdown(f'<div class="insight">💰 Payout ratio: <b style="color:{PINK}">{l_pay:.0f}%</b> distribuido como dividendos. '
                        f'Alto = defensivo. Bajo = reinversión / recompras.</div>', unsafe_allow_html=True)
        else:
            st.info("Not enough disposition data.")
    else:
        st.info("Disposition table unavailable.")

    # ── 6. Heatmap ─────────────────────────────────────────────────────────────
    st.markdown('<div class="sec">Snapshot — Last 8 Quarters ($B SAAR)</div>', unsafe_allow_html=True)
    last8 = common[-8:]
    ql8   = [_ql(d) for d in last8]
    snap  = {"Total": total, "Financial": financial, "Non-Fin": nonfin,
             "Mfg": mfg, "Info": info, "Retail": retail, "Wholesale": wholesale}
    if len(margin): snap["Margin%"] = margin
    snap_df = pd.DataFrame({k: s.reindex(last8).fillna(0).values for k,s in snap.items()}, index=ql8).T

    def _cc(v):
        if pd.isna(v): return "background:#0d0d1a;color:#3d3d5c;text-align:center;font-family:monospace;font-size:0.78rem;padding:5px"
        if v > 1500:   return "background:#0d4f2b;color:#4ade80;text-align:center;font-family:monospace;font-size:0.78rem;padding:5px"
        elif v > 800:  return "background:#0a3320;color:#34d399;text-align:center;font-family:monospace;font-size:0.78rem;padding:5px"
        elif v > 200:  return "background:#0c2918;color:#6ee7b7;text-align:center;font-family:monospace;font-size:0.78rem;padding:5px"
        elif v >= 0:   return "background:#13132b;color:#9999bb;text-align:center;font-family:monospace;font-size:0.78rem;padding:5px"
        else:          return "background:#2d1515;color:#fca5a5;text-align:center;font-family:monospace;font-size:0.78rem;padding:5px"

    st.dataframe(snap_df.style.applymap(_cc).format(lambda v: f"{v:.2f}" if abs(v)<100 else f"${v:,.0f}"),
                 use_container_width=True)
    st.markdown(f'<div style="color:{MUTED};font-size:0.7rem;margin-top:12px;font-family:monospace">'
                f'BEA NIPA T61600D · T61900D · T10105 · Corporate Profits with IVA & CCAdj · SAAR</div>',
                unsafe_allow_html=True)
