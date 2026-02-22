"""
modules/gdp.py — GDP & Components module for Macro Terminal
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests

BG    = "#0d0d1a"
BG2   = "#13132b"
GRID  = "#1e1e3a"
TEXT  = "#e8e8f0"
MUTED = "#6b6b8a"

COLORS = {
    "consumption":    "#3b82f6",
    "investment":     "#10b981",
    "government":     "#f59e0b",
    "net_exports":    "#ef4444",
    "durables":       "#60a5fa",
    "nondurables":    "#93c5fd",
    "services":       "#1d4ed8",
    "residential":    "#34d399",
    "nonresidential": "#6ee7b7",
    "inventories":    "#064e3b",
    "federal":        "#fbbf24",
    "state_local":    "#92400e",
    "exports":        "#4ade80",
    "imports":        "#f87171",
    "final_sales":    "#a78bfa",
    "inv_change":     "#7c3aed",
}

PLOT_LAYOUT = dict(
    paper_bgcolor=BG,
    plot_bgcolor=BG2,
    font=dict(family="monospace", color=TEXT, size=11),
    xaxis=dict(gridcolor=GRID, linecolor=GRID, tickfont=dict(color=MUTED)),
    yaxis=dict(gridcolor=GRID, linecolor=GRID, zeroline=True,
               zerolinecolor="#ffffff30", ticksuffix=" pp"),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT, size=10),
                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    hovermode="x unified",
    margin=dict(l=50, r=20, t=60, b=40),
)

# ── Correct series codes from T10102 ──────────────────────────────────────────
# GDP growth rate uses A191RL (Fisher Quantity Index, % change)
# All contributions use suffix RY (Quantity Contributions)
CODES = {
    "gdp":            "A191RL",
    "consumption":    "DPCERY",
    "durables":       "DDURRY",
    "nondurables":    "DNDGRY",
    "services":       "DSERRY",
    "investment":     "A006RY",
    "nonresidential": "A008RY",
    "residential":    "A011RY",
    "inventories":    "A014RY",
    "net_exports":    "A019RY",
    "exports":        "A020RY",
    "imports":        "A021RY",
    "government":     "A822RY",
    "federal":        "A823RY",
    "state_local":    "A829RY",
}


@st.cache_data(ttl=3600, show_spinner=False)
def load_bea_data():
    api_key = "081DA2FC-1900-47A0-A40B-49C31925E395"
    try:
        api_key = st.secrets["BEA_API_KEY"]
    except Exception:
        pass

    params = {
        "UserID": api_key,
        "method": "GetData",
        "DataSetName": "NIPA",
        "TableName": "T10102",
        "Frequency": "Q",
        "Year": "ALL",
        "ResultFormat": "JSON",
    }

    resp = requests.get("https://apps.bea.gov/api/data", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    rows = data["BEAAPI"]["Results"]["Data"]
    df = pd.DataFrame(rows)

    df["DataValue"] = (
        df["DataValue"].astype(str)
        .str.replace(",", "", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
    )

    def parse_period(p):
        p = str(p).strip()
        if "Q" in p:
            year, q = p.split("Q")
            month = int(q) * 3 - 2
            return pd.Timestamp(f"{year}-{month:02d}-01")
        return pd.NaT

    df["Date"] = df["TimePeriod"].apply(parse_period)
    df = df.dropna(subset=["Date"])
    return df.sort_values("Date").reset_index(drop=True)


def get_s(df, code):
    mask = df["SeriesCode"] == code
    return df[mask].set_index("Date")["DataValue"].sort_index()


def qlabel(ts):
    return f"{ts.year} Q{(ts.month - 1) // 3 + 1}"


def render():
    st.markdown("""
    <style>
    .kpi-card { background:#13132b; border:1px solid #1e1e3a; border-radius:8px;
                padding:16px 20px; text-align:center; }
    .kpi-value { font-family:monospace; font-size:1.9rem; font-weight:600; }
    .kpi-label { font-size:0.72rem; color:#6b6b8a; text-transform:uppercase;
                 letter-spacing:0.1em; margin-top:4px; }
    .kpi-sub   { font-family:monospace; font-size:0.8rem; margin-top:4px; color:#6b6b8a; }
    .sec { font-family:monospace; font-size:0.68rem; color:#6b6b8a; text-transform:uppercase;
           letter-spacing:0.15em; margin:24px 0 8px 0; border-bottom:1px solid #1e1e3a; padding-bottom:6px; }
    </style>
    """, unsafe_allow_html=True)

    with st.spinner("Fetching BEA data..."):
        try:
            df = load_bea_data()
        except Exception as e:
            st.error(f"Error fetching BEA data: {e}")
            return

    if df.empty:
        st.error("BEA returned no data.")
        return

    gdp  = get_s(df, CODES["gdp"])
    cons = get_s(df, CODES["consumption"])
    inv  = get_s(df, CODES["investment"])
    gov  = get_s(df, CODES["government"])
    nx   = get_s(df, CODES["net_exports"])

    common = gdp.index
    for s in [cons, inv, gov, nx]:
        if len(s) > 0:
            common = common.intersection(s.index)
    common = common.sort_values()

    if len(common) < 2:
        st.error(f"Not enough data. GDP points: {len(gdp)}, common: {len(common)}")
        return

    gdp  = gdp.reindex(common).fillna(0)
    cons = cons.reindex(common).fillna(0)
    inv  = inv.reindex(common).fillna(0)
    gov  = gov.reindex(common).fillna(0)
    nx   = nx.reindex(common).fillna(0)

    quarters = [qlabel(d) for d in common]

    # ── KPIs ──────────────────────────────────────────────────────────────────
    latest_gdp = gdp.iloc[-1]
    gdp_color  = "#10b981" if latest_gdp >= 0 else "#ef4444"

    cols = st.columns(5)
    kpis = [
        (f"{latest_gdp:+.1f}%", "GDP Growth",   "annualized",      gdp_color),
        (f"{cons.iloc[-1]:+.1f}", "Consumption", "contribution pp", COLORS["consumption"]),
        (f"{inv.iloc[-1]:+.1f}",  "Investment",  "contribution pp", COLORS["investment"]),
        (f"{gov.iloc[-1]:+.1f}",  "Government",  "contribution pp", COLORS["government"]),
        (f"{nx.iloc[-1]:+.1f}",   "Net Exports", "contribution pp", COLORS["net_exports"]),
    ]
    for col, (val, label, sub, color) in zip(cols, kpis):
        with col:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-value" style="color:{color}">{val}</div>
                <div class="kpi-label">{label}</div>
                <div class="kpi-sub">{sub}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown(
        f'<div style="color:{MUTED};font-size:0.7rem;margin-top:6px;font-family:monospace">'
        f'Latest: {qlabel(common[-1])} · BEA NIPA T10102 · Annualized contribution to real GDP growth</div>',
        unsafe_allow_html=True)

    # ── Main chart ─────────────────────────────────────────────────────────────
    st.markdown('<div class="sec">Contributions to Real GDP Growth</div>', unsafe_allow_html=True)

    fig = go.Figure()
    for name, series, color in [
        ("Consumption", cons, COLORS["consumption"]),
        ("Investment",  inv,  COLORS["investment"]),
        ("Government",  gov,  COLORS["government"]),
        ("Net Exports", nx,   COLORS["net_exports"]),
    ]:
        fig.add_trace(go.Bar(
            name=name, x=quarters, y=series.values,
            marker_color=color, marker_line_width=0,
            hovertemplate=f"<b>{name}</b>: %{{y:+.2f}} pp<extra></extra>",
        ))

    fig.add_trace(go.Scatter(
        name="Total GDP", x=quarters, y=gdp.values, mode="markers",
        marker=dict(symbol="diamond", size=8, color="#ffffff",
                    line=dict(color=BG2, width=1)),
        hovertemplate="<b>GDP</b>: %{y:+.2f}%<extra></extra>",
    ))

    fig.update_layout(**PLOT_LAYOUT, barmode="relative", height=400)
    st.plotly_chart(fig, use_container_width=True)

    # ── Drill-downs ────────────────────────────────────────────────────────────
    st.markdown('<div class="sec">Drill-Down</div>', unsafe_allow_html=True)

    tabs = st.tabs(["Consumption", "Investment", "Government", "Net Exports", "Final Sales"])

    with tabs[0]:
        _stacked([
            ("Durables",    get_s(df, CODES["durables"]),    COLORS["durables"]),
            ("Nondurables", get_s(df, CODES["nondurables"]), COLORS["nondurables"]),
            ("Services",    get_s(df, CODES["services"]),    COLORS["services"]),
        ], common, quarters, "Consumption Components")

    with tabs[1]:
        _stacked([
            ("Residential",    get_s(df, CODES["residential"]),    COLORS["residential"]),
            ("Nonresidential", get_s(df, CODES["nonresidential"]), COLORS["nonresidential"]),
            ("Inventories",    get_s(df, CODES["inventories"]),    COLORS["inventories"]),
        ], common, quarters, "Investment Components")

    with tabs[2]:
        _stacked([
            ("Federal",       get_s(df, CODES["federal"]),      COLORS["federal"]),
            ("State & Local", get_s(df, CODES["state_local"]),  COLORS["state_local"]),
        ], common, quarters, "Government Components")

    with tabs[3]:
        _stacked([
            ("Exports", get_s(df, CODES["exports"]), COLORS["exports"]),
            ("Imports", get_s(df, CODES["imports"]), COLORS["imports"]),
        ], common, quarters, "Net Exports Decomposition")

    with tabs[4]:
        inv_change = get_s(df, CODES["inventories"]).reindex(common).fillna(0)
        final_sales = gdp - inv_change
        _stacked([
            ("Final Sales",      final_sales, COLORS["final_sales"]),
            ("Inventory Change", inv_change,  COLORS["inv_change"]),
        ], common, quarters, "Final Sales vs Inventory Investment")

    # ── Heatmap table ──────────────────────────────────────────────────────────
    st.markdown('<div class="sec">Last 8 Quarters</div>', unsafe_allow_html=True)

    last8 = common[-8:]
    ql8   = [qlabel(d) for d in last8]

    series_map = {
        "GDP":            get_s(df, CODES["gdp"]),
        "Consumption":    get_s(df, CODES["consumption"]),
        "Durables":       get_s(df, CODES["durables"]),
        "Nondurables":    get_s(df, CODES["nondurables"]),
        "Services":       get_s(df, CODES["services"]),
        "Investment":     get_s(df, CODES["investment"]),
        "Residential":    get_s(df, CODES["residential"]),
        "Nonresidential": get_s(df, CODES["nonresidential"]),
        "Inventories":    get_s(df, CODES["inventories"]),
        "Government":     get_s(df, CODES["government"]),
        "Net Exports":    get_s(df, CODES["net_exports"]),
    }

    rows = {label: s.reindex(last8).fillna(0).values for label, s in series_map.items()}
    tbl  = pd.DataFrame(rows, index=ql8).T

    def color_cell(val):
        if val > 1.5:    return "background-color:#0d4f2b;color:#4ade80;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"
        elif val > 0.5:  return "background-color:#0a3320;color:#34d399;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"
        elif val > 0:    return "background-color:#0c2918;color:#6ee7b7;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"
        elif val > -0.5: return "background-color:#2d1515;color:#fca5a5;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"
        elif val > -1.5: return "background-color:#3d1010;color:#f87171;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"
        else:            return "background-color:#4d0a0a;color:#ef4444;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"

    styled = tbl.style.format("{:+.2f}").applymap(color_cell)
    st.dataframe(styled, use_container_width=True)


def _stacked(series_list, common, quarters, title):
    fig = go.Figure()
    for name, s, color in series_list:
        vals = s.reindex(common).fillna(0).values
        fig.add_trace(go.Bar(
            name=name, x=quarters, y=vals,
            marker_color=color, marker_line_width=0,
            hovertemplate=f"<b>{name}</b>: %{{y:+.2f}} pp<extra></extra>",
        ))
    layout = dict(**PLOT_LAYOUT, barmode="relative", height=320,
                  title=dict(text=title, font=dict(color=MUTED, size=11)))
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True)
