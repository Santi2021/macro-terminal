"""
modules/corporate.py — Corporate Health for Macro Terminal
Sources:
  BEA NIPA T61600D  → Corporate Profits by Industry (A446RC style → real codes below)
  BEA NIPA T62100D  → Undistributed Corporate Profits by Industry
  BEA NIPA T10105   → Nominal GDP (for margin)
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

# ── VERIFIED SeriesCodes from T61600D (confirmed via API 2025-02) ─────────────
# Source: LineDescription → SeriesCode mapping confirmed by diagnose_bea.py
#
# PROFITS TABLE: T61600D
# "Corporate profits with IVA & CCAdj" → A051RC  (headline, includes rest of world)
# "Domestic industries" (with CCAdj)   → A390RC  (domestic total)
# "Financial" (with CCAdj)             → A392RC
# "Nonfinancial" (with CCAdj)          → A399RC
# "Domestic industries" (IVA only)     → A445RC  (alternative domestic total)
# "Financial" (IVA only)               → A587RC
# "Nonfinancial" (IVA only)            → A463RC
# "Rest of the world"                  → B394RC
# "Other financial"                    → N398RC  (sub-component)
# Industry breakdown (N-codes):
# "Manufacturing"                      → N400RC
#   "Nondurable goods"                 → N401RC
#   "Durable goods"                    → N406RC
# "Wholesale trade"                    → N414RC
# "Retail trade"                       → N415RC
# "Transportation & warehousing"       → N417RC
# "Utilities"                          → N419RC
# "Other nonfinancial"                 → N420RC
# "Computer & electronic products"     → N501RC
# "Information"                        → N502RC

PROFIT_TABLE = "T61600D"
PROFIT_CODES = {
    # Headline (domestic + rest of world)
    "headline":      "A051RC",   # Corp profits with IVA & CCAdj (total incl. RoW)
    # Domestic breakdown (with CCAdj — preferred, most complete)
    "domestic":      "A390RC",   # Domestic industries total
    "financial":     "A392RC",   # Financial domestic
    "nonfinancial":  "A399RC",   # Nonfinancial domestic
    # Industry sub-components
    "manufacturing": "N400RC",
    "wholesale":     "N414RC",
    "retail":        "N415RC",
    "information":   "N502RC",
    "transport":     "N417RC",
    "utilities":     "N419RC",
    "other_nonfin":  "N420RC",
    "other_fin":     "N398RC",
}

# UNDISTRIBUTED PROFITS: T62100D
# Need to probe codes at runtime — load and print available
UNDIST_TABLE = "T62100D"

# NOMINAL GDP: T10105
GDP_TABLE = "T10105"
GDP_CODE  = "A191RC"   # Confirmed ✅


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

    if "Error" in body:
        msg = body["Error"].get("APIErrorDescription", str(body["Error"]))
        raise RuntimeError(f"BEA [{table}]: {msg}")

    results = body.get("Results", {})
    if "Data" not in results:
        raise RuntimeError(f"BEA [{table}] no Data. Keys: {list(results.keys())}")

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
    elif len(p) == 4:
        return pd.Timestamp(f"{p}-01-01")
    return pd.NaT


def _get(df: pd.DataFrame, code: str) -> pd.Series:
    mask = df["SeriesCode"] == code
    return df[mask].set_index("Date")["DataValue"].sort_index()


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
def _load_profits():
    return _fetch_nipa(PROFIT_TABLE, "Q")

@st.cache_data(ttl=3600, show_spinner=False)
def _load_undist():
    # T62100D is Annual only — quarterly not available
    # Try Q first, fall back to A
    try:
        return _fetch_nipa(UNDIST_TABLE, "Q"), "Q"
    except Exception:
        try:
            return _fetch_nipa(UNDIST_TABLE, "A"), "A"
        except Exception:
            return pd.DataFrame(), "none"

@st.cache_data(ttl=3600, show_spinner=False)
def _load_gdp():
    df = _fetch_nipa(GDP_TABLE, "Q")
    return _get(df, GDP_CODE)


# ── render ─────────────────────────────────────────────────────────────────────
def render():
    st.markdown("""<style>
    .kpi-card{background:#13132b;border:1px solid #1e1e3a;border-radius:8px;
              padding:16px 20px;text-align:center;}
    .kpi-value{font-family:monospace;font-size:1.85rem;font-weight:600;}
    .kpi-label{font-size:0.72rem;color:#6b6b8a;text-transform:uppercase;
               letter-spacing:0.1em;margin-top:4px;}
    .kpi-sub{font-family:monospace;font-size:0.78rem;margin-top:4px;}
    .sec{font-family:monospace;font-size:0.68rem;color:#6b6b8a;text-transform:uppercase;
         letter-spacing:0.15em;margin:24px 0 8px 0;
         border-bottom:1px solid #1e1e3a;padding-bottom:6px;}
    .insight{background:#0a0a18;border-left:3px solid #00d4ff;border-radius:0 6px 6px 0;
             padding:10px 14px;font-family:monospace;font-size:0.78rem;
             color:#9999bb;margin:8px 0 16px 0;}
    </style>""", unsafe_allow_html=True)

    col_r, _ = st.columns([3, 7])
    with col_r:
        rng = st.radio("Range", ["5Y","10Y","20Y","All"], index=1,
                       horizontal=True, label_visibility="collapsed", key="corp_range")
    cut = {"5Y":-20, "10Y":-40, "20Y":-80, "All":0}[rng]

    # ── Load ───────────────────────────────────────────────────────────────────
    with st.spinner("Loading BEA Corporate Profits..."):
        profits_df = gdp_s = None
        undist_df  = pd.DataFrame()
        errs = []

        try:   profits_df = _load_profits()
        except Exception as e: errs.append(f"**Profits (T61600D):** {e}")

        try:   gdp_s = _load_gdp()
        except Exception as e: errs.append(f"**GDP (T10105):** {e}")

        try:
            undist_df, undist_freq = _load_undist()
        except Exception as e:
            errs.append(f"**Undistributed (T62100D):** {e}")
            undist_freq = "none"

    for e in errs: st.warning(e)
    if profits_df is None: return

    # ── Series from T61600D ────────────────────────────────────────────────────
    headline     = _get(profits_df, PROFIT_CODES["headline"])     # total incl RoW
    domestic     = _get(profits_df, PROFIT_CODES["domestic"])     # domestic total
    financial    = _get(profits_df, PROFIT_CODES["financial"])
    nonfinancial = _get(profits_df, PROFIT_CODES["nonfinancial"])
    mfg          = _get(profits_df, PROFIT_CODES["manufacturing"])
    wholesale    = _get(profits_df, PROFIT_CODES["wholesale"])
    retail       = _get(profits_df, PROFIT_CODES["retail"])
    info_        = _get(profits_df, PROFIT_CODES["information"])
    transport    = _get(profits_df, PROFIT_CODES["transport"])
    utilities    = _get(profits_df, PROFIT_CODES["utilities"])
    other_nf     = _get(profits_df, PROFIT_CODES["other_nonfin"])
    other_fin    = _get(profits_df, PROFIT_CODES["other_fin"])

    # Use domestic as primary (excludes rest-of-world, cleaner for analysis)
    total = domestic if len(domestic) else headline

    common = total.index
    for s in [financial, nonfinancial]:
        if len(s): common = common.intersection(s.index)
    common = common.sort_values()

    if len(common) < 4:
        st.error(f"Not enough data. Total pts: {len(total)}, common: {len(common)}")
        return

    def _tr(s):
        s = s.reindex(common).fillna(0)
        return s.iloc[cut:] if cut != 0 else s

    ql_t = [_ql(d) for d in (common[cut:] if cut != 0 else common)]

    tot_t    = _tr(total)
    fin_t    = _tr(financial)
    nonfin_t = _tr(nonfinancial)
    yoy_full = total.pct_change(4) * 100
    yoy_t    = _tr(yoy_full)

    l_total  = float(total.dropna().iloc[-1])       if len(total.dropna())       else 0
    l_fin    = float(financial.dropna().iloc[-1])    if len(financial.dropna())   else 0
    l_nonfin = float(nonfinancial.dropna().iloc[-1]) if len(nonfinancial.dropna()) else 0
    l_yoy    = float(yoy_full.dropna().iloc[-1])     if len(yoy_full.dropna())    else 0

    # Profit margin vs nominal GDP
    margin   = pd.Series(dtype=float)
    l_margin = 0.0
    if gdp_s is not None and len(gdp_s):
        midx   = total.index.intersection(gdp_s.index)
        margin = total.reindex(midx) / gdp_s.reindex(midx) * 100
        if len(margin.dropna()):
            l_margin = float(margin.dropna().iloc[-1])

    # Note: BEA reports in millions → convert to billions for display
    # Check magnitude: if values > 100_000 they're in millions
    scale = 1000 if l_total > 100_000 else 1
    unit  = "$B" if scale == 1000 else "$M"

    def _fmt_t(v): return f"${v/scale/1000:.1f}T"
    def _fmt_b(v): return f"${v/scale:.0f}B"

    # ── KPIs ───────────────────────────────────────────────────────────────────
    cols = st.columns(5)
    kpi_data = [
        (_fmt_t(l_total),    "Total Profits",   "domestic, SAAR",      CYAN),
        (f"{l_yoy:+.1f}%",   "YoY Growth",      "vs year ago",         GREEN if l_yoy >= 0 else RED),
        (f"{l_margin:.1f}%", "Profit/GDP",       "vs nominal GDP",     AMBER),
        (_fmt_b(l_fin),      "Financial",        "sector",              BLUE),
        (_fmt_b(l_nonfin),   "Non-Financial",    "sector",              VIOLET),
    ]
    for col, (val, label, sub, color) in zip(cols, kpi_data):
        with col:
            st.markdown(
                f'<div class="kpi-card">'
                f'<div class="kpi-value" style="color:{color}">{val}</div>'
                f'<div class="kpi-label">{label}</div>'
                f'<div class="kpi-sub" style="color:{MUTED}">{sub}</div>'
                f'</div>', unsafe_allow_html=True)

    st.markdown(
        f'<div style="color:{MUTED};font-size:0.7rem;margin-top:6px;font-family:monospace">'
        f'Latest: {_ql(common[-1])} · BEA NIPA T61600D · Domestic industries · '
        f'Corporate Profits with IVA & CCAdj · SAAR</div>',
        unsafe_allow_html=True)

    # ── 1. Level + YoY ─────────────────────────────────────────────────────────
    st.markdown('<div class="sec">Corporate Profits — Level & YoY Growth</div>', unsafe_allow_html=True)

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        name=f"Profits ({unit})", x=ql_t, y=(tot_t / scale).values,
        marker_color=CYAN, opacity=0.45,
        hovertemplate=f"<b>Profits</b>: $%{{y:,.0f}}{unit[1:]}<extra></extra>",
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        name="YoY %", x=ql_t, y=yoy_t.values,
        line=dict(color=AMBER, width=2.5),
        hovertemplate="<b>YoY</b>: %{y:+.1f}%<extra></extra>",
    ), secondary_y=True)
    fig.add_hline(y=0, line_color="#444466", line_width=1, secondary_y=True)
    fig.update_layout(**_layout(360), barmode="overlay",
                      paper_bgcolor=BG, plot_bgcolor=BG2, hovermode="x unified")
    fig.update_yaxes(title_text=unit, gridcolor=GRID, zeroline=False,
                     secondary_y=False, title_font=dict(color=CYAN, size=10))
    fig.update_yaxes(title_text="YoY %", gridcolor="rgba(0,0,0,0)", zeroline=False,
                     secondary_y=True, title_font=dict(color=AMBER, size=10))
    fig.update_xaxes(gridcolor=GRID, linecolor=GRID)
    st.plotly_chart(fig, use_container_width=True)

    # ── 2. Financial vs Non-Financial ──────────────────────────────────────────
    st.markdown('<div class="sec">Financial vs Non-Financial Domestic Profits</div>', unsafe_allow_html=True)

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        name="Financial", x=ql_t, y=(fin_t / scale).values,
        line=dict(color=BLUE, width=2.5),
        fill="tozeroy", fillcolor="rgba(59,130,246,0.08)",
        hovertemplate=f"<b>Financial</b>: $%{{y:,.0f}}{unit[1:]}<extra></extra>",
    ))
    fig2.add_trace(go.Scatter(
        name="Non-Financial", x=ql_t, y=(nonfin_t / scale).values,
        line=dict(color=VIOLET, width=2.5),
        fill="tozeroy", fillcolor="rgba(167,139,250,0.08)",
        hovertemplate=f"<b>Non-Fin</b>: $%{{y:,.0f}}{unit[1:]}<extra></extra>",
    ))
    fig2.update_layout(**_layout(300))
    st.plotly_chart(fig2, use_container_width=True)

    denom_fn = (fin_t + nonfin_t).replace(0, float("nan"))
    fin_share_s = (fin_t / denom_fn * 100).dropna()
    fin_share = float(fin_share_s.iloc[-1]) if len(fin_share_s) else 0
    st.markdown(
        f'<div class="insight">🏦 Financial share of domestic profits: '
        f'<b style="color:{BLUE}">{fin_share:.1f}%</b>. '
        f'Financialization elevada (>30%) históricamente precede compresión de márgenes '
        f'o estrés de crédito en el sector real.</div>',
        unsafe_allow_html=True)

    # ── 3. Non-Financial Industry Breakdown ────────────────────────────────────
    st.markdown('<div class="sec">Non-Financial Breakdown by Industry</div>', unsafe_allow_html=True)

    industries = [
        ("Manufacturing",  mfg,       "#10b981"),
        ("Wholesale",      wholesale,  "#34d399"),
        ("Retail",         retail,     "#f59e0b"),
        ("Information",    info_,      "#a78bfa"),
        ("Transport",      transport,  "#60a5fa"),
        ("Utilities",      utilities,  "#14b8a6"),
        ("Other Nonfin",   other_nf,   "#94a3b8"),
    ]
    fig3 = go.Figure()
    for label, s, color in industries:
        if s.empty: continue
        vals = s.reindex(common).fillna(0)
        vals = vals.iloc[cut:] if cut != 0 else vals
        fig3.add_trace(go.Bar(
            name=label, x=ql_t, y=(vals / scale).values,
            marker_color=color, marker_line_color=BG2, marker_line_width=0.4,
            hovertemplate=f"<b>{label}</b>: $%{{y:,.0f}}{unit[1:]}<extra></extra>",
        ))
    fig3.update_layout(**_layout(320), barmode="stack")
    st.plotly_chart(fig3, use_container_width=True)

    # ── 4. Profit Margin % GDP ─────────────────────────────────────────────────
    st.markdown('<div class="sec">Profit Margin — % of Nominal GDP</div>', unsafe_allow_html=True)

    if len(margin):
        m_trim = margin.iloc[cut:] if cut != 0 else margin
        m_ql   = [_ql(d) for d in m_trim.index]
        h_avg  = float(margin.mean())
        h_peak = float(margin.max())
        fig4 = go.Figure()
        fig4.add_hrect(y0=h_avg-0.3, y1=h_avg+0.3,
                       fillcolor=GREEN, opacity=0.06, line_width=0,
                       annotation_text=f"Avg {h_avg:.1f}%",
                       annotation_position="top right",
                       annotation_font=dict(color=GREEN, size=9))
        fig4.add_trace(go.Scatter(
            name="Profit/GDP %", x=m_ql, y=m_trim.values,
            line=dict(color=TEAL, width=2.5),
            fill="tozeroy", fillcolor="rgba(20,184,166,0.07)",
            hovertemplate="<b>Margin</b>: %{y:.2f}%<extra></extra>",
        ))
        fig4.add_hline(y=h_avg, line_color=GREEN, line_width=1, line_dash="dot")
        l4 = _layout(300)
        l4["yaxis"]["ticksuffix"] = "%"
        fig4.update_layout(**l4)
        st.plotly_chart(fig4, use_container_width=True)
        st.markdown(
            f'<div class="insight">📊 Margin: <b style="color:{TEAL}">{l_margin:.2f}%</b> · '
            f'Avg histórico: <b style="color:{GREEN}">{h_avg:.2f}%</b> · '
            f'Pico: <b style="color:{AMBER}">{h_peak:.2f}%</b>. '
            f'Margins persistentemente por encima del promedio señalan riesgo de compresión '
            f'vía presión laboral, competencia, o tributación.</div>',
            unsafe_allow_html=True)
    else:
        st.info("GDP data unavailable — margin chart skipped.")

    # ── 5. Undistributed Profits (Retained Earnings proxy) ─────────────────────
    st.markdown('<div class="sec">Undistributed Corporate Profits — Retained Earnings Proxy</div>',
                unsafe_allow_html=True)

    if len(undist_df):
        # Show all available codes in T62100D with descriptions
        # The total undistributed is typically the first/largest series
        # Try to find "Domestic industries" or total line
        undist_candidates = undist_df.groupby("SeriesCode").apply(
            lambda g: g.sort_values("Date").iloc[-1]
        ).reset_index(drop=True)[["SeriesCode","LineDescription","DataValue"]]

        # Pick the code whose LineDescription looks like the total domestic
        # Priority: contains "Domestic" > contains "Total" > first A-code
        def _pick_total(cands):
            for _, row in cands.iterrows():
                if "domestic" in row["LineDescription"].lower():
                    return row["SeriesCode"]
            for _, row in cands.iterrows():
                if "total" in row["LineDescription"].lower():
                    return row["SeriesCode"]
            # Fall back to largest absolute value (likely the aggregate)
            return cands.loc[cands["DataValue"].abs().idxmax(), "SeriesCode"]

        undist_code = _pick_total(undist_candidates)
        undist_s    = _get(undist_df, undist_code)
        undist_desc = undist_df[undist_df["SeriesCode"] == undist_code]["LineDescription"].iloc[0]

        if undist_freq == "A":
            # Annual data: resample to quarterly for display alignment (forward fill)
            undist_s = undist_s.resample("QS").ffill()
            freq_note = "Annual data (quarterly not available from BEA)"
        else:
            freq_note = "Quarterly"

        # Align with profit common index
        u_idx = common.intersection(undist_s.index)
        if len(u_idx) > 4:
            u_s   = undist_s.reindex(u_idx).ffill().fillna(0)
            u_t   = u_s.iloc[cut:] if cut != 0 else u_s
            ql_u  = [_ql(d) for d in (u_idx[cut:] if cut != 0 else u_idx)]
            tot_u = total.reindex(u_idx).fillna(0)
            tot_u = tot_u.iloc[cut:] if cut != 0 else tot_u
            # Retention rate = undistributed / total profits
            denom_u = tot_u.replace(0, float("nan"))
            ret_rate = (u_t / denom_u * 100).fillna(0)
            l_ret_rate = float(ret_rate.iloc[-1]) if len(ret_rate) else 0

            fig5 = make_subplots(specs=[[{"secondary_y": True}]])
            fig5.add_trace(go.Bar(
                name=f"Undistributed Profits ({unit})", x=ql_u, y=(u_t / scale).values,
                marker_color=GREEN, opacity=0.75,
                hovertemplate=f"<b>Undistributed</b>: $%{{y:,.0f}}{unit[1:]}<extra></extra>",
            ), secondary_y=False)
            fig5.add_trace(go.Scatter(
                name="Retention Rate %", x=ql_u, y=ret_rate.values,
                line=dict(color=AMBER, width=2, dash="dot"),
                hovertemplate="<b>Retention Rate</b>: %{y:.1f}%<extra></extra>",
            ), secondary_y=True)
            fig5.update_layout(
                **_layout(300), barmode="overlay",
                paper_bgcolor=BG, plot_bgcolor=BG2, hovermode="x unified")
            fig5.update_yaxes(title_text=unit, gridcolor=GRID, zeroline=False,
                              secondary_y=False, title_font=dict(color=GREEN, size=10))
            fig5.update_yaxes(title_text="Retention %", gridcolor="rgba(0,0,0,0)",
                              zeroline=False, secondary_y=True,
                              title_font=dict(color=AMBER, size=10))
            fig5.update_xaxes(gridcolor=GRID, linecolor=GRID)
            st.plotly_chart(fig5, use_container_width=True)
            st.markdown(
                f'<div class="insight">💰 Retention rate actual: '
                f'<b style="color:{GREEN}">{l_ret_rate:.0f}%</b> de ganancias retenidas. '
                f'Source: BEA T62100D — "{undist_desc}" · {freq_note}. '
                f'Alta retención = reinversión / capex / recompras. '
                f'Caída sostenida sugiere stress en el balance o aumento de dividendos.</div>',
                unsafe_allow_html=True)
        else:
            st.info("Not enough overlapping periods for undistributed profits chart.")
    else:
        st.info(
            "Undistributed profits (T62100D) no disponible en frecuencia quarterly. "
            "BEA solo publica esta tabla en frecuencia anual y no está actualmente accesible.")

    # ── 6. Snapshot table ──────────────────────────────────────────────────────
    st.markdown('<div class="sec">Snapshot — Last 8 Quarters</div>', unsafe_allow_html=True)

    last8 = common[-8:]
    ql8   = [_ql(d) for d in last8]

    def _snap_val(s, idx):
        return (s.reindex(idx).fillna(0) / scale).values

    snap = {
        "Total Dom.":    _snap_val(total,        last8),
        "Financial":     _snap_val(financial,    last8),
        "Non-Fin":       _snap_val(nonfinancial, last8),
        "Mfg":           _snap_val(mfg,          last8),
        "Info":          _snap_val(info_,         last8),
        "Retail":        _snap_val(retail,        last8),
        "Wholesale":     _snap_val(wholesale,     last8),
    }
    if len(margin):
        snap["Margin%"] = margin.reindex(last8).fillna(0).values

    snap_df = pd.DataFrame(snap, index=ql8).T

    def _cc(v):
        s = "text-align:center;font-family:monospace;font-size:0.78rem;padding:5px;"
        if pd.isna(v):    return f"background:#0d0d1a;color:#3d3d5c;{s}"
        if v > 1500:      return f"background:#0d4f2b;color:#4ade80;{s}"
        elif v > 600:     return f"background:#0a3320;color:#34d399;{s}"
        elif v > 100:     return f"background:#0c2918;color:#6ee7b7;{s}"
        elif v >= 0:      return f"background:#13132b;color:#9999bb;{s}"
        else:             return f"background:#2d1515;color:#fca5a5;{s}"

    def _fmt(v):
        if pd.isna(v):    return "n/a"
        if abs(v) < 50:   return f"{v:.2f}"   # margin %
        return f"${v:,.0f}"

    st.dataframe(
        snap_df.style.applymap(_cc).format(_fmt),
        use_container_width=True)

    st.markdown(
        f'<div style="color:{MUTED};font-size:0.7rem;margin-top:12px;font-family:monospace">'
        f'BEA NIPA T61600D (profits) · T62100D (undistributed) · T10105 (GDP) · '
        f'Corporate Profits with IVA & CCAdj · SAAR</div>',
        unsafe_allow_html=True)
